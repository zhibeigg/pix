"""游戏素材直出与资源校验辅助。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image


IssueLevel = Literal["error", "warning"]
AssetGenerationPolicy = Literal["extract"]
AssetPaletteMode = Literal["auto", "ramp", "kmeans"]


class AssetSizePolicyError(ValueError):
    """素材尺寸不符合直出策略。"""


def resolve_asset_generation_policy(size: tuple[int, int]) -> AssetGenerationPolicy:
    """返回游戏素材直出策略。

    规则：仅支持 ≥16×16 的素材，统一走 Pixel Grid extract 流程。AI Grid / 普通 resize
    分支已在 0.60.0 版本删除，更小尺寸由调用方负责再做下采样。
    """
    width, height = int(size[0]), int(size[1])
    if width <= 0 or height <= 0:
        raise AssetSizePolicyError("素材尺寸必须为正整数")
    if width < 16 or height < 16:
        raise AssetSizePolicyError("最低支持 16x16 素材")
    return "extract"


@dataclass(frozen=True)
class AssetSizeStrategy:
    """按目标尺寸推荐的 pipeline 策略；调用方仍可显式覆盖。"""

    palette_mode: str
    grid_mode: str  # 仅 "extract"
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "palette_mode": self.palette_mode,
            "grid_mode": self.grid_mode,
            "notes": self.notes,
        }


def resolve_size_strategy(size: tuple[int, int]) -> AssetSizeStrategy:
    """所有支持尺寸统一推荐 extract + auto/K-means。

    AI Grid / 普通 resize 分支已废弃；默认保留经典单图纯色背景效果：
    从源图反推像素格 → 按原始 K-means/auto 调色 → 精确渲染。
    """
    return AssetSizeStrategy(
        palette_mode="auto",
        grid_mode="extract",
        notes="extract Pixel Grid + auto/K-means（经典单图纯色背景风格，AI Grid / resize 路径已删除）",
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


ASSET_KIND_LABELS: dict[str, str] = {
    "item_icon": "item icon",
    "ui_component": "UI component",
}
SUBJECT_KIND_LABELS: dict[str, str] = {
    "single_prop": "single prop",
    "single_ui": "single UI element",
}
COMPATIBLE_SUBJECT_KINDS: dict[str, set[str]] = {
    "item_icon": {"single_prop"},
    "ui_component": {"single_ui"},
}


@dataclass(frozen=True)
class AssetPromptProfile:
    default_subject_kind: str
    usage_label: str
    placement_context: str
    forbidden_elements: str


ASSET_PROMPT_PROFILES: dict[str, AssetPromptProfile] = {
    "item_icon": AssetPromptProfile(
        default_subject_kind="single_prop",
        usage_label="inventory use",
        placement_context="easy placement in inventory slots",
        forbidden_elements="No text, no watermark, no frame, no labels.",
    ),
    "ui_component": AssetPromptProfile(
        default_subject_kind="single_ui",
        usage_label="game interface use",
        placement_context="easy placement in HUD or menu layouts",
        forbidden_elements="No text, no watermark, no unrelated outer frame, no labels.",
    ),
}


def _canonical_asset_prompt(
    name: str,
    width: int,
    height: int,
    key_tolerance: int,
    max_colors: int,
    asset_kind_label: str,
    subject_kind_label: str,
    profile: AssetPromptProfile,
) -> str:
    return (
        f"Convert the input image or described subject into a TRUE pixel-art game {asset_kind_label} "
        f"designed for {profile.usage_label}, not a painted digital illustration. "
        f"Subject: {name}. Subject kind: {subject_kind_label}. "
        f"Canvas size must be exactly {width}x{height} pixels, "
        "where each pixel is one square grid cell. Use large, chunky readable pixels, "
        "limited colors, and a simple silhouette. "
        f"Use no more than {max_colors} visible subject colors; background color does not count. "
        "For human characters, make sure the face is flat and no shadow. "
        "The subject must be centered with clear empty pixel rows around all edges for safe sprite "
        f"padding and {profile.placement_context}. "
        "Use a pure solid single-color background for chroma-key removal; choose a background color "
        "that is not close to any visible subject color, with color-distance greater than the removal "
        f"tolerance ({key_tolerance} RGB Euclidean distance). "
        "No anti-aliasing or smoothing — every pixel must be a perfect square aligned to the grid. "
        "The output image should be pixel-perfect, each grid cell only contains one color. "
        f"{profile.forbidden_elements}"
    )


def _asset_kind_key(value: str) -> str:
    key = (value or "item_icon").strip()
    return key if key in ASSET_KIND_LABELS else "item_icon"


def _subject_kind_key(asset_kind: str, subject_kind: str) -> str:
    profile = ASSET_PROMPT_PROFILES[asset_kind]
    key = (subject_kind or profile.default_subject_kind).strip()
    if key not in COMPATIBLE_SUBJECT_KINDS[asset_kind]:
        return profile.default_subject_kind
    return key


def _legacy_template_to_type_aware(template: str) -> str:
    return (
        template
        .replace(
            "TRUE pixel-art game asset designed for game inventory/UI use",
            "TRUE pixel-art game {asset_kind_label} designed for {asset_usage_label}",
        )
        .replace("easy placement in game UI", "{placement_context}")
        .replace("No text, no watermark, no UI frame, no labels.", "{forbidden_elements}")
    )


def build_asset_prompt(
    template: str,
    name: str,
    *,
    size: tuple[int, int],
    extra_prompt: str = "",
    asset_kind: str = "item_icon",
    subject_kind: str = "single_prop",
    key_color: str = "#00FF00",
    key_tolerance: int = 48,
    max_colors: int = 16,
) -> str:
    """按游戏素材模板生成最终生图 prompt。"""
    width, height = size
    size_label = f"{width}×{height}"
    asset_kind_key = _asset_kind_key(asset_kind)
    subject_kind_key = _subject_kind_key(asset_kind_key, subject_kind)
    profile = ASSET_PROMPT_PROFILES[asset_kind_key]
    asset_kind_label = ASSET_KIND_LABELS[asset_kind_key]
    subject_kind_label = SUBJECT_KIND_LABELS[subject_kind_key]
    canvas_shape = "正方形画幅" if width == height else f"适配 {size_label} 画幅"
    values = {
        "name": name,
        "width": width,
        "height": height,
        "size_label": size_label,
        "asset_kind": asset_kind_key,
        "asset_kind_label": asset_kind_label,
        "asset_usage_label": profile.usage_label,
        "subject_kind": subject_kind_key,
        "subject_kind_label": subject_kind_label,
        "placement_context": profile.placement_context,
        "forbidden_elements": profile.forbidden_elements,
        "canvas_shape": canvas_shape,
        "green": key_color,
        "key_color": key_color,
        "key_tolerance": int(key_tolerance),
        "colors": int(max_colors),
        "max_colors": int(max_colors),
    }
    template_text = _legacy_template_to_type_aware((template or "").strip())
    if template_text:
        try:
            prompt = template_text.format(**values)
        except Exception:
            prompt = _canonical_asset_prompt(
                name,
                width,
                height,
                int(key_tolerance),
                int(max_colors),
                asset_kind_label,
                subject_kind_label,
                profile,
            )
    else:
        prompt = _canonical_asset_prompt(
            name,
            width,
            height,
            int(key_tolerance),
            int(max_colors),
            asset_kind_label,
            subject_kind_label,
            profile,
        )
    if extra_prompt.strip():
        prompt = f"{prompt.strip()} {extra_prompt.strip()}"
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
