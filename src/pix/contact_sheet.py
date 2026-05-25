"""受控生图 contact sheet 与动态 key-color 后处理工具。"""

from __future__ import annotations

import math
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image

from pix.config import AppConfig


KEY_COLOR_CANDIDATES = (
    ("#FF00FF", (255, 0, 255), {"pink", "magenta", "purple", "violet", "rose", "romance", "otome", "cyberpunk", "neon", "粉", "品红", "紫", "玫瑰", "赛博", "霓虹"}),
    ("#FF0000", (255, 0, 0), {"red", "crimson", "blood", "fire", "flame", "ruby", "warning", "红", "赤", "绯", "血", "火", "猩红"}),
    ("#00FFFF", (0, 255, 255), {"cyan", "teal", "blue", "ice", "ocean", "sea", "sci-fi", "holographic", "青", "蓝", "冰", "海", "深海", "科幻", "全息"}),
    ("#00FF00", (0, 255, 0), {"green", "jade", "leaf", "grass", "jungle", "toxic", "poison", "solar", "forest", "绿", "玉", "叶", "草", "森林", "丛林", "毒", "太阳朋克"}),
    ("#FFFF00", (255, 255, 0), {"yellow", "gold", "sun", "lightning", "amber", "brass", "黄", "金", "太阳", "闪电", "琥珀", "黄铜"}),
    ("#0000FF", (0, 0, 255), {"blue", "cyan", "ocean", "ice", "sky", "lapis", "蓝", "青", "海", "冰", "天空", "青金石"}),
    ("#FF7F00", (255, 127, 0), {"orange", "gold", "fire", "flame", "brass", "copper", "desert", "sun", "橙", "金", "火", "铜", "沙", "太阳"}),
    ("#7F00FF", (127, 0, 255), {"purple", "violet", "lavender", "nebula", "cosmic", "dream", "紫", "薰衣草", "星云", "宇宙", "梦"}),
)


@dataclass(frozen=True)
class ContactSheetCandidate:
    index: int
    row: int
    col: int
    path: Path
    bbox: tuple[int, int, int, int] | None
    score: float | None = None
    rank: int | None = None
    reason: str = ""
    selected: bool = False

    def to_metadata(self, run_dir: Path, *, selected: bool | None = None) -> dict[str, Any]:
        try:
            rel_path = self.path.relative_to(run_dir)
            path_text = rel_path.as_posix()
        except ValueError:
            path_text = str(self.path)
        is_selected = self.selected if selected is None else selected
        return {
            "index": self.index,
            "row": self.row,
            "col": self.col,
            "path": path_text,
            "bbox": list(self.bbox) if self.bbox else None,
            "score": self.score,
            "rank": self.rank,
            "reason": self.reason,
            "selected": bool(is_selected),
        }


@dataclass(frozen=True)
class ContactSheetResult:
    sheet_path: Path
    candidates: list[ContactSheetCandidate]
    selected_index: int

    @property
    def selected(self) -> ContactSheetCandidate:
        if not self.candidates:
            raise IndexError("contact sheet 没有候选图")
        safe_index = min(max(0, self.selected_index), len(self.candidates) - 1)
        return self.candidates[safe_index]

    def to_metadata(self, run_dir: Path, *, enabled: bool, effective_prompt: str, user_prompt: str) -> dict[str, Any]:
        try:
            sheet_path = self.sheet_path.relative_to(run_dir).as_posix()
        except ValueError:
            sheet_path = str(self.sheet_path)
        return {
            "enabled": enabled,
            "sheet": sheet_path,
            "rows": self.rows,
            "cols": self.cols,
            "count": len(self.candidates),
            "selected_index": self.selected.index if self.candidates else 0,
            "user_prompt": user_prompt,
            "effective_prompt": effective_prompt,
            "candidates": [candidate.to_metadata(run_dir, selected=candidate.index == self.selected.index) for candidate in self.candidates],
        }

    @property
    def rows(self) -> int:
        if not self.candidates:
            return 0
        return max(candidate.row for candidate in self.candidates) + 1

    @property
    def cols(self) -> int:
        if not self.candidates:
            return 0
        return max(candidate.col for candidate in self.candidates) + 1


def contact_sheet_enabled(cfg: AppConfig, *, has_prompt: bool) -> bool:
    """是否启用"候选生成 + VL 评分"模式（与 n_sample / contact_sheet 子模式独立）。"""
    return bool(has_prompt and cfg.image_gen.contact_sheet_enabled)


def candidate_mode(cfg: AppConfig) -> str:
    """返回 `n_sample` 或 `contact_sheet`；默认 n_sample。"""
    mode = str(getattr(cfg.image_gen, "candidate_mode", "n_sample") or "n_sample").lower().strip()
    if mode not in ("n_sample", "contact_sheet"):
        return "n_sample"
    return mode


def candidate_count(cfg: AppConfig) -> int:
    if candidate_mode(cfg) == "n_sample":
        return max(1, int(getattr(cfg.image_gen, "n_sample_count", 4)))
    return max(1, int(cfg.image_gen.contact_sheet_rows) * int(cfg.image_gen.contact_sheet_cols))


def build_sample_prompt(
    cfg: AppConfig,
    description: str,
    *,
    target_size: tuple[int, int] | None = None,
) -> str:
    """n_sample 模式下的单图 prompt（不含 rows/cols）。"""
    width, height = target_size or cfg.asset.pixel_size
    template = (getattr(cfg.image_gen, "n_sample_prompt_template", "") or "").strip()
    key_hex, _key_rgb = resolve_key_color(cfg.image_gen.green_screen_color, description)
    values = {
        "description": description.strip(),
        "name": description.strip(),
        "green": key_hex,
        "key_color": key_hex,
        "key_tolerance": int(cfg.image_gen.green_screen_tolerance),
        "width": int(width),
        "height": int(height),
    }
    if template:
        try:
            return template.format(**values).strip()
        except Exception:
            pass
    return (
        "Convert the input image or described subject into a TRUE perler bead pixel pattern designed for physical bead crafting, not digital illustration. "
        f"Subject: {values['description']}. Canvas size must be exactly {values['width']}x{values['height']} pixels, where each pixel represents exactly one perler bead. "
        "Use extremely large, chunky pixels with very few active pixels overall. Simplicity is critical. "
        "For human characters, make sure the face is flat and no shadow. "
        "The subject must be centered with clear empty bead rows around all edges to allow easy mounting on a bead board. "
        f"Use pure solid key-color {values['green']} for all empty/background cells for chroma-key removal; keep every visible subject color outside the maximum key-color tolerance ({values['key_tolerance']} RGB Euclidean distance) from {values['green']}. "
        "No anti-aliasing or smoothing — every pixel must be a perfect square bead aligned to the grid. "
        "The output image should be pixel-perfect, each grid only contains one color. No text, no watermark, no UI frame, no labels."
    )


def collect_independent_candidates(
    image_paths: Iterable[Path],
    dest_dir: str | Path,
    *,
    green_screen_color: str,
    tolerance: int,
    crop_padding: float = 0.12,
    crop_square: bool = True,
) -> ContactSheetResult:
    """把一组独立单图当作候选：每张单独做 chroma-key + 裁剪，走和 split_contact_sheet 相同的结构。

    用于 n_sample 模式替代 split_contact_sheet；保持 ContactSheetResult 不变，
    下游（ranking、render_candidate_pixel_outputs）零改动。
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    green = parse_hex_color(green_screen_color)
    candidates: list[ContactSheetCandidate] = []
    first_source: Path | None = None
    for index, image_path in enumerate(image_paths, start=1):
        image_path = Path(image_path)
        if first_source is None:
            first_source = image_path
        with Image.open(image_path) as opened:
            image = opened.convert("RGBA")
        processed, bbox = remove_green_screen(
            image,
            green_rgb=green,
            tolerance=tolerance,
            crop_padding=crop_padding,
            crop_square=crop_square,
        )
        candidate_path = dest / f"candidate_{index:02d}.png"
        processed.save(candidate_path)
        candidates.append(
            ContactSheetCandidate(
                index=index,
                row=0,
                col=index - 1,
                path=candidate_path,
                bbox=bbox,
            )
        )
    if not candidates:
        raise ValueError("n-sample 模式下没有任何候选图片")
    # sheet_path 用第一张原图，仅为 meta 展示；与 split_contact_sheet 保持合同
    return ContactSheetResult(
        sheet_path=first_source if first_source is not None else candidates[0].path,
        candidates=candidates,
        selected_index=0,
    )


def normalize_hex_color(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def resolve_key_color(value: str, description: str = "") -> tuple[str, tuple[int, int, int]]:
    """解析或按 prompt 动态选择背景抠色。

    `auto` / `dynamic` 会避开 prompt 中出现的颜色语义，降低素材本体和背景色撞色的概率。
    """
    text = (value or "").strip().lower()
    if text in {"auto", "dynamic", ""}:
        lowered = (description or "").lower()
        scored = []
        for order, (hex_value, rgb, conflicts) in enumerate(KEY_COLOR_CANDIDATES):
            conflict_count = sum(1 for word in conflicts if word in lowered)
            scored.append((conflict_count, order, hex_value, rgb))
        _score, _order, hex_value, rgb = min(scored, key=lambda item: (item[0], item[1]))
        return hex_value, rgb
    rgb = parse_hex_color(value, fallback=KEY_COLOR_CANDIDATES[0][1])
    return normalize_hex_color(rgb), rgb


def parse_hex_color(value: str, fallback: tuple[int, int, int] = (255, 0, 255)) -> tuple[int, int, int]:
    text = (value or "").strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return fallback
    try:
        return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return fallback


def build_contact_sheet_prompt(
    cfg: AppConfig,
    description: str,
    *,
    target_size: tuple[int, int] | None = None,
) -> str:
    rows = max(1, int(cfg.image_gen.contact_sheet_rows))
    cols = max(1, int(cfg.image_gen.contact_sheet_cols))
    width, height = target_size or cfg.asset.pixel_size
    template = cfg.image_gen.contact_sheet_prompt_template.strip()
    key_hex, _key_rgb = resolve_key_color(cfg.image_gen.green_screen_color, description)
    values = {
        "description": description.strip(),
        "name": description.strip(),
        "rows": rows,
        "cols": cols,
        "count": rows * cols,
        "green": key_hex,
        "key_color": key_hex,
        "key_tolerance": int(cfg.image_gen.green_screen_tolerance),
        "width": int(width),
        "height": int(height),
    }
    try:
        return template.format(**values).strip()
    except Exception:
        return _fallback_prompt(**values)


def _fallback_prompt(**values: Any) -> str:
    return (
        f"Create a {values['rows']}x{values['cols']} contact sheet with {values['count']} distinct variations of this TRUE perler bead pixel pattern subject: {values['description']}. "
        "In every cell, convert the subject into a TRUE perler bead pixel pattern designed for physical bead crafting, not digital illustration. "
        f"Canvas size for each candidate must be exactly {values['width']}x{values['height']} pixels, where each pixel represents exactly one perler bead. "
        "Use extremely large, chunky pixels with very few active pixels overall. Simplicity is critical. "
        "For human characters, make sure the face is flat and no shadow. "
        "The subject must be centered with clear empty bead rows around all edges to allow easy mounting on a bead board. "
        f"Use pure solid key-color {values['green']} for all empty/background cells for chroma-key removal; keep every visible subject color outside the maximum key-color tolerance ({values['key_tolerance']} RGB Euclidean distance) from {values['green']}. "
        "No anti-aliasing or smoothing — every pixel must be a perfect square bead aligned to the grid. "
        "The output image should be pixel-perfect, each grid only contains one color. No text, no watermark, no UI frame, no labels."
    )


def split_contact_sheet(
    image_path: str | Path,
    dest_dir: str | Path,
    *,
    rows: int,
    cols: int,
    green_screen_color: str,
    tolerance: int,
    crop_padding: float = 0.12,
    crop_square: bool = True,
) -> ContactSheetResult:
    """把一张 contact sheet 等分为候选，并把纯色 key background 转为透明。"""
    sheet_path = Path(image_path)
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    safe_rows = max(1, int(rows))
    safe_cols = max(1, int(cols))
    green = parse_hex_color(green_screen_color)
    candidates: list[ContactSheetCandidate] = []
    with Image.open(sheet_path) as opened:
        image = opened.convert("RGBA")
        cell_w = image.width / safe_cols
        cell_h = image.height / safe_rows
        for row in range(safe_rows):
            for col in range(safe_cols):
                left = int(round(col * cell_w))
                top = int(round(row * cell_h))
                right = int(round((col + 1) * cell_w))
                bottom = int(round((row + 1) * cell_h))
                cell = image.crop((left, top, right, bottom))
                processed, bbox = remove_green_screen(
                    cell,
                    green_rgb=green,
                    tolerance=tolerance,
                    crop_padding=crop_padding,
                    crop_square=crop_square,
                )
                index = row * safe_cols + col + 1
                candidate_path = dest / f"candidate_{index:02d}.png"
                processed.save(candidate_path)
                candidates.append(ContactSheetCandidate(index=index, row=row, col=col, path=candidate_path, bbox=bbox))
    return ContactSheetResult(sheet_path=sheet_path, candidates=candidates, selected_index=0)


def remove_green_screen(
    image: Image.Image,
    *,
    green_rgb: tuple[int, int, int] = (0, 255, 0),
    tolerance: int = 48,
    crop_padding: float = 0.12,
    crop_square: bool = True,
) -> tuple[Image.Image, tuple[int, int, int, int] | None]:
    """针对纯色 key background 做透明化，并按主体 bbox 裁剪留白。

    处理步骤：
    1. 全局移除与 key-color 距离 <= tolerance 的像素
    2. 对紧邻透明区域的半透明边缘做 decontaminate（去除 key-color 对 RGB 的污染）
    3. 完全透明像素 RGB 置黑（防止缩放时渗出背景色）
    """
    rgba = np.asarray(image.convert("RGBA")).copy()
    h, w = rgba.shape[:2]
    rgb = rgba[..., :3].astype(np.float64)
    ref = np.array(green_rgb, dtype=np.float64)
    dist = np.sqrt(((rgb - ref) ** 2).sum(axis=2))

    # 1. 全局移除背景
    bg_mask = dist <= max(0, int(tolerance))
    rgba[bg_mask, 3] = 0

    # 2. Decontaminate 半透明边缘
    transparent = rgba[..., 3] == 0
    near_transparent = np.zeros((h, w), dtype=bool)
    if h > 1:
        near_transparent[1:, :] |= transparent[:-1, :]
        near_transparent[:-1, :] |= transparent[1:, :]
    if w > 1:
        near_transparent[:, 1:] |= transparent[:, :-1]
        near_transparent[:, :-1] |= transparent[:, 1:]

    semi_mask = near_transparent & (rgba[..., 3] > 0) & (rgba[..., 3] < 255)
    if semi_mask.any():
        a = rgba[semi_mask, 3].astype(np.float64) / 255.0
        for c in range(3):
            channel = rgba[semi_mask, c].astype(np.float64)
            decontaminated = (channel - ref[c] * (1.0 - a)) / np.maximum(a, 0.01)
            rgba[semi_mask, c] = np.clip(decontaminated, 0, 255).astype(np.uint8)

    # 3. 透明像素 RGB 置黑
    fully_transparent = rgba[..., 3] == 0
    rgba[fully_transparent, :3] = 0

    alpha = rgba[..., 3]
    visible = alpha > 8
    if not visible.any():
        return Image.fromarray(rgba, mode="RGBA"), None

    ys, xs = np.where(visible)
    bbox = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    cropped = _crop_with_padding(Image.fromarray(rgba, mode="RGBA"), bbox, crop_padding=crop_padding, crop_square=crop_square)
    return cropped, bbox


def _crop_with_padding(
    image: Image.Image,
    bbox: tuple[int, int, int, int],
    *,
    crop_padding: float,
    crop_square: bool,
) -> Image.Image:
    left, top, right, bottom = bbox
    subject_w = max(1, right - left)
    subject_h = max(1, bottom - top)
    pad = max(0, int(round(max(subject_w, subject_h) * max(0.0, float(crop_padding)))))
    crop_left = max(0, left - pad)
    crop_top = max(0, top - pad)
    crop_right = min(image.width, right + pad)
    crop_bottom = min(image.height, bottom + pad)
    cropped = image.crop((crop_left, crop_top, crop_right, crop_bottom))
    if not crop_square:
        return cropped

    side = max(cropped.width, cropped.height)
    side = max(1, int(math.ceil(side)))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.alpha_composite(cropped, ((side - cropped.width) // 2, (side - cropped.height) // 2))
    return canvas


def apply_candidate_ranking(result: ContactSheetResult, ranking_items: Iterable[dict[str, Any]]) -> ContactSheetResult:
    """按 VL 排名重排候选，并把最高分候选标记为 selected。"""
    by_index = {candidate.index: candidate for candidate in result.candidates}
    ranked: list[ContactSheetCandidate] = []
    seen: set[int] = set()
    for position, item in enumerate(ranking_items, start=1):
        try:
            index = int(item.get("index"))
        except (AttributeError, TypeError, ValueError):
            continue
        candidate = by_index.get(index)
        if candidate is None or index in seen:
            continue
        seen.add(index)
        score_value = item.get("score")
        try:
            score = float(score_value) if score_value is not None else None
        except (TypeError, ValueError):
            score = None
        try:
            rank = int(item.get("rank") or position)
        except (TypeError, ValueError):
            rank = position
        ranked.append(replace(
            candidate,
            score=score,
            rank=rank,
            reason=str(item.get("reason") or "").strip(),
            selected=False,
        ))
    for candidate in result.candidates:
        if candidate.index not in seen:
            ranked.append(replace(candidate, selected=False))
    if not ranked:
        return result
    ranked.sort(key=lambda candidate: (candidate.rank if candidate.rank is not None else 9999, -(candidate.score or 0), candidate.index))
    normalized = [replace(candidate, rank=rank, selected=rank == 1) for rank, candidate in enumerate(ranked, start=1)]
    return ContactSheetResult(sheet_path=result.sheet_path, candidates=normalized, selected_index=0)


def copy_selected_candidate(result: ContactSheetResult, dest_path: str | Path) -> Path:
    target = Path(dest_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(result.selected.path, target)
    return target
