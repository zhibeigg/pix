"""游戏素材直出与资源校验辅助。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image


IssueLevel = Literal["error", "warning"]
AssetGenerationPolicy = Literal["extract", "ai_grid_required"]
AssetPaletteMode = Literal["auto", "ramp", "kmeans"]


class AssetSizePolicyError(ValueError):
    """素材尺寸不符合直出策略。"""


def resolve_asset_generation_policy(size: tuple[int, int]) -> AssetGenerationPolicy:
    """返回游戏素材直出策略。

    规则：16x16 以下默认禁止，唯一例外是 8x8，且 8x8 必须由 AI Grid 直绘。
    """
    width, height = int(size[0]), int(size[1])
    if width <= 0 or height <= 0:
        raise AssetSizePolicyError("素材尺寸必须为正整数")
    if (width, height) == (8, 8):
        return "ai_grid_required"
    if width < 16 or height < 16:
        raise AssetSizePolicyError("16x16 以下仅允许 8x8，且 8x8 必须使用 AI Grid 直绘")
    return "extract"


@dataclass(frozen=True)
class AssetSizeStrategy:
    """按目标尺寸推荐的 pipeline 策略；调用方仍可显式覆盖。"""

    palette_mode: str
    grid_mode: str  # off | extract | ai
    ai_grid: bool
    repair_mode: str  # off | auto | force
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "palette_mode": self.palette_mode,
            "grid_mode": self.grid_mode,
            "ai_grid": self.ai_grid,
            "repair_mode": self.repair_mode,
            "notes": self.notes,
        }


def resolve_size_strategy(size: tuple[int, int]) -> AssetSizeStrategy:
    """根据目标尺寸推荐 pipeline 组合（基于 0.59→0.60 的实测结论）。

    - 8x8: extract Pixel Grid（先按源图比例缩到 32 再聚合到 8）+ ramp + auto 修补；
      AI Grid 在 8x8 直画容易铺满画布，已不作为默认。
    - 16x16: extract + ramp + auto 修补 —— 主流尺寸，源图信息量足够，构图最稳。
    - 32x32: extract + ramp + auto 修补 —— 4 路实测最佳。
    - 64+: 普通像素化 + ramp（grid_mode=off）；source 已是抠好的透明素材，
      调用方应让 pipeline 主动启用 ``auto_skip_redundant_bg``，避免重复抠图。

    AI Grid（grid_mode="ai"）退回到兜底定位：仅当 extract 出来明显失败时才启用。
    """
    short = max(1, min(int(size[0]), int(size[1])))
    if short <= 8:
        # 8x8 仍维持 AI Grid 直绘的硬约束（resolve_asset_generation_policy / web jobs 都依赖），
        # 但已知会容易铺满画布 —— 后续改进窗口；这里保持 force 修补尝试救正。
        return AssetSizeStrategy(
            palette_mode="ramp",
            grid_mode="ai",
            ai_grid=True,
            repair_mode="force",
            notes="8x8 沿用 AI Grid 直绘 + force 修补 + ramp（已知 8x8 铺满画布是当前短板）",
        )
    if short <= 16:
        return AssetSizeStrategy(
            palette_mode="ramp",
            grid_mode="extract",
            ai_grid=False,
            repair_mode="auto",
            notes="16x16 推荐 extract + ramp + auto 修补（构图最稳，AI Grid 仅作兜底）",
        )
    if short <= 32:
        return AssetSizeStrategy(
            palette_mode="ramp",
            grid_mode="extract",
            ai_grid=False,
            repair_mode="auto",
            notes="32x32 推荐 extract + ramp + auto 修补（实测最佳）",
        )
    return AssetSizeStrategy(
        palette_mode="ramp",
        grid_mode="off",
        ai_grid=False,
        repair_mode="off",
        notes="64+ 推荐普通像素化 + ramp；调用方应启用 auto_skip_redundant_bg 避免重复抠图",
    )


@dataclass(frozen=True)
class AssetValidationIssue:
    level: IssueLevel
    code: str
    message: str


@dataclass
class AssetValidationReport:
    path: Path
    size: tuple[int, int] | None = None
    mode: str | None = None
    visible_color_count: int = 0
    alpha_bbox: tuple[int, int, int, int] | None = None
    issues: list[AssetValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)

    @property
    def warnings(self) -> list[AssetValidationIssue]:
        return [issue for issue in self.issues if issue.level == "warning"]

    @property
    def errors(self) -> list[AssetValidationIssue]:
        return [issue for issue in self.issues if issue.level == "error"]


def safe_asset_filename(name: str, fallback: str = "asset") -> str:
    """把资源名转换成适合跨平台文件名的字符串，保留中文。"""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name.strip())
    cleaned = re.sub(r"\s+", "_", cleaned).strip(" ._")
    return cleaned or fallback


def build_asset_prompt(
    template: str,
    name: str,
    *,
    size: tuple[int, int],
    extra_prompt: str = "",
) -> str:
    """按游戏素材模板生成最终生图 prompt。"""
    width, height = size
    try:
        prompt = template.format(name=name, width=width, height=height)
    except Exception:
        prompt = (
            f"A single fantasy pixel game inventory item icon of {name}. "
            f"Designed to become a {width}x{height} RPG inventory sprite."
        )
    if extra_prompt.strip():
        prompt = f"{prompt} {extra_prompt.strip()}"
    return prompt.strip()


def validate_asset_image(
    path: str | Path,
    *,
    expected_size: tuple[int, int] | None = None,
    max_colors: int | None = 16,
    require_alpha: bool = True,
    require_transparency: bool = True,
    alpha_threshold: int = 8,
    min_subject_coverage: float = 0.06,
    max_subject_coverage: float = 0.92,
) -> AssetValidationReport:
    """检查 PNG 是否适合作为小尺寸游戏素材。"""
    p = Path(path)
    report = AssetValidationReport(path=p)

    if p.suffix.lower() != ".png":
        report.issues.append(AssetValidationIssue("error", "not_png", "文件扩展名不是 .png"))

    try:
        with Image.open(p) as opened:
            original_bands = opened.getbands()
            original_has_transparency = "transparency" in opened.info
            image = opened.convert("RGBA")
            report.size = opened.size
            report.mode = opened.mode
    except Exception as exc:
        report.issues.append(AssetValidationIssue("error", "cannot_open", f"无法读取图片：{exc}"))
        return report

    if expected_size is not None and report.size != expected_size:
        report.issues.append(
            AssetValidationIssue(
                "error",
                "size_mismatch",
                f"尺寸应为 {expected_size[0]}x{expected_size[1]}，实际为 {report.size[0]}x{report.size[1]}",
            )
        )

    original_has_alpha = "A" in original_bands or original_has_transparency
    if require_alpha and not original_has_alpha:
        report.issues.append(AssetValidationIssue("error", "missing_alpha", "图片不含 alpha/透明通道"))

    rgba = np.asarray(image, dtype=np.uint8)
    alpha = rgba[..., 3]
    visible_mask = alpha > max(0, int(alpha_threshold))
    if visible_mask.any():
        visible_rgb = rgba[..., :3][visible_mask]
        report.visible_color_count = int(np.unique(visible_rgb.reshape(-1, 3), axis=0).shape[0])
    else:
        report.visible_color_count = 0

    if max_colors is not None and report.visible_color_count > max_colors:
        report.issues.append(
            AssetValidationIssue(
                "error",
                "too_many_colors",
                f"可见颜色数 {report.visible_color_count} 超过限制 {max_colors}",
            )
        )

    if require_transparency and int(alpha.min()) > 0:
        report.issues.append(AssetValidationIssue("error", "no_transparency", "图片没有透明背景像素"))

    semi_transparent = int(((alpha > 0) & (alpha < 255)).sum())
    if semi_transparent > 0:
        report.issues.append(
            AssetValidationIssue(
                "warning",
                "semi_transparent_pixels",
                f"存在 {semi_transparent} 个半透明像素，像素游戏中可能形成脏边",
            )
        )

    mask_img = Image.fromarray(np.where(visible_mask, 255, 0).astype(np.uint8), mode="L")
    report.alpha_bbox = mask_img.getbbox()
    if report.alpha_bbox is None:
        report.issues.append(AssetValidationIssue("error", "empty_subject", "没有检测到可见主体像素"))
        return report

    width, height = report.size or image.size
    left, top, right, bottom = report.alpha_bbox
    bbox_area = max(1, right - left) * max(1, bottom - top)
    coverage = bbox_area / max(1, width * height)
    if coverage < min_subject_coverage:
        report.issues.append(
            AssetValidationIssue("warning", "subject_too_small", f"主体 bbox 占比 {coverage:.1%}，可能过小")
        )
    if coverage > max_subject_coverage:
        report.issues.append(
            AssetValidationIssue("warning", "subject_too_large", f"主体 bbox 占比 {coverage:.1%}，可能过满")
        )
    if left <= 0 or top <= 0 or right >= width or bottom >= height:
        report.issues.append(AssetValidationIssue("warning", "subject_touches_edge", "主体触碰画布边缘"))

    return report
