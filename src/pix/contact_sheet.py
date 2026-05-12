"""受控生图 contact sheet 与绿幕后处理工具。"""

from __future__ import annotations

import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from pix.config import AppConfig


@dataclass(frozen=True)
class ContactSheetCandidate:
    index: int
    row: int
    col: int
    path: Path
    bbox: tuple[int, int, int, int] | None

    def to_metadata(self, run_dir: Path) -> dict[str, Any]:
        try:
            rel_path = self.path.relative_to(run_dir)
            path_text = rel_path.as_posix()
        except ValueError:
            path_text = str(self.path)
        return {
            "index": self.index,
            "row": self.row,
            "col": self.col,
            "path": path_text,
            "bbox": list(self.bbox) if self.bbox else None,
        }


@dataclass(frozen=True)
class ContactSheetResult:
    sheet_path: Path
    candidates: list[ContactSheetCandidate]
    selected_index: int

    @property
    def selected(self) -> ContactSheetCandidate:
        return self.candidates[self.selected_index]

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
            "selected_index": self.selected_index + 1,
            "user_prompt": user_prompt,
            "effective_prompt": effective_prompt,
            "candidates": [candidate.to_metadata(run_dir) for candidate in self.candidates],
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
    return bool(has_prompt and cfg.image_gen.contact_sheet_enabled)


def parse_hex_color(value: str, fallback: tuple[int, int, int] = (0, 255, 0)) -> tuple[int, int, int]:
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
    values = {
        "description": description.strip(),
        "name": description.strip(),
        "rows": rows,
        "cols": cols,
        "count": rows * cols,
        "green": cfg.image_gen.green_screen_color.strip() or "#00FF00",
        "width": int(width),
        "height": int(height),
    }
    try:
        return template.format(**values).strip()
    except Exception:
        return _fallback_prompt(**values)


def _fallback_prompt(**values: Any) -> str:
    return (
        f"Create a {values['rows']}x{values['cols']} contact sheet with {values['count']} distinct "
        f"game item icon variations of: {values['description']}. Use a pure green screen "
        f"background {values['green']}. No text, no watermark, no UI frame. Each cell contains "
        f"one centered isolated object with clear spacing, readable silhouette and pixel-art friendly "
        f"details for a {values['width']}x{values['height']} RPG inventory sprite."
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
    """把一张 contact sheet 等分为候选，并把绿幕背景转为透明。"""
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
    """针对纯绿幕背景做透明化，并按主体 bbox 裁剪留白。"""
    rgba = np.asarray(image.convert("RGBA")).copy()
    rgb = rgba[..., :3].astype(np.int32)
    ref = np.array(green_rgb, dtype=np.int32)
    dist = np.sqrt(((rgb - ref) ** 2).sum(axis=2))
    mask_green = dist <= max(0, int(tolerance))
    rgba[mask_green, 3] = 0

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


def copy_selected_candidate(result: ContactSheetResult, dest_path: str | Path) -> Path:
    target = Path(dest_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(result.selected.path, target)
    return target
