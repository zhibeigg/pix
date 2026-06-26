"""序列帧通用工具与数据类。

历史上 `sprite.py` 既包含逐帧（iterative）pipeline，也包含工具函数。从 1.47.0 起
逐帧模式被移除，序列帧统一走单图（mosaic，见 `sprite_mosaic.py`）。本模块只保留
mosaic pipeline 复用的数据类与小工具，避免大改 import 路径。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from pix.config import AppConfig
from pix.pixelize.palette import build_palette_image, kmeans_palette, rgb_to_hex


@dataclass(frozen=True)
class SpriteFrame:
    """单帧输出信息。"""

    index: int
    raw_path: Path
    reference_path: Path
    path: Path
    sheet_rect: dict[str, int]
    action_phase: str
    bbox: tuple[int, int, int, int] | None = None

    @property
    def row(self) -> int:
        return 0

    @property
    def col(self) -> int:
        return self.index - 1

    def to_metadata(self, run_dir: Path) -> dict[str, Any]:
        return {
            "index": self.index,
            "row": self.row,
            "col": self.col,
            "raw_path": _rel(self.raw_path, run_dir),
            "reference_path": _rel(self.reference_path, run_dir),
            "path": _rel(self.path, run_dir),
            "sheet_rect": dict(self.sheet_rect),
            "action_phase": self.action_phase,
            "bbox": list(self.bbox) if self.bbox else None,
        }


@dataclass
class SpritePipelineResult:
    """序列帧 pipeline 输出汇总。"""

    run_dir: Path
    source_path: Path
    frame_paths: list[Path]
    pixel_path: Path
    preview_path: Path | None
    meta_path: Path
    meta: dict[str, Any]
    analysis_path: Path | None = None

    @property
    def gif_path(self) -> Path | None:
        return self.preview_path


# ---- 通用工具 ----


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _ceil_to_multiple(value: int, divisor: int) -> int:
    safe_divisor = max(1, int(divisor))
    safe_value = max(1, int(value))
    return ((safe_value + safe_divisor - 1) // safe_divisor) * safe_divisor


def _visible_bbox(image: Image.Image, threshold: int = 8) -> tuple[int, int, int, int] | None:
    alpha = np.asarray(image.convert("RGBA"))[..., 3]
    visible = alpha > threshold
    if not visible.any():
        return None
    ys, xs = np.where(visible)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _paste_content_to_canvas(content: Image.Image, *, size: tuple[int, int], anchor: str) -> Image.Image:
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    frame = content.convert("RGBA")
    # 水平对齐用「不透明像素质心」而非 bbox 中心：单帧伸出的手臂 / 武器 / 裙摆会撑宽
    # bbox 并把 bbox 中心带偏，导致逐帧居中后身体左右抖动；质心对几个外伸像素几乎不敏感，
    # 因此各帧主体重心能稳定对齐。无可见像素时退回 bbox 居中。夹取保证不出画布。
    x = max(0, (size[0] - frame.width) // 2)
    alpha = np.asarray(frame)[..., 3]
    xs = np.where(alpha > 8)[1]
    if xs.size:
        centroid_x = float(xs.mean())
        x = int(round(size[0] / 2.0 - centroid_x))
        x = max(0, min(x, size[0] - frame.width))
    anchor_key = (anchor or "bottom_center").strip().lower()
    if anchor_key in {"center", "middle", "center_center"}:
        y = max(0, (size[1] - frame.height) // 2)
    else:
        y = max(0, size[1] - frame.height)
    canvas.alpha_composite(frame, (x, y))
    return canvas


def _sprite_bg_removal_options(cfg: AppConfig | None, *, tolerance: int) -> dict[str, Any]:
    asset = getattr(cfg, "asset", None)
    if asset is None:
        return {
            "bg_removal_algorithm": "pixel_bg",
            "color_to_alpha_transparency": max(0, int(tolerance)),
        }
    return {
        "bg_removal_algorithm": getattr(asset, "bg_removal_algorithm", "pixel_bg"),
        "color_to_alpha_shape": getattr(asset, "color_to_alpha_shape", "sphere"),
        "color_to_alpha_transparency": max(0, int(tolerance)),
        "color_to_alpha_opacity": getattr(asset, "color_to_alpha_opacity", 255),
        "color_to_alpha_interpolation": getattr(asset, "color_to_alpha_interpolation", "linear"),
    }


# ---- 调色板共享与 sheet/GIF 合成 ----


def _compose_mosaic(frames: list[Image.Image]) -> Image.Image:
    if not frames:
        raise ValueError("没有可用于合成的帧")
    width = sum(frame.width for frame in frames)
    height = max(frame.height for frame in frames)
    sheet = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    x = 0
    for frame in frames:
        sheet.alpha_composite(frame.convert("RGBA"), (x, (height - frame.height) // 2))
        x += frame.width
    return sheet


def _quantize_with_palette(
    image: Image.Image,
    palette_rgb: list[tuple[int, int, int]],
    *,
    dither: str,
) -> Image.Image:
    pal_img = build_palette_image(palette_rgb)
    dither_method = Image.Dither.FLOYDSTEINBERG if dither == "floyd_steinberg" else Image.Dither.NONE
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    quantized = rgba.convert("RGB").quantize(palette=pal_img, dither=dither_method)
    out = quantized.convert("RGBA")
    out.putalpha(alpha)
    return out


def _apply_shared_palette(images: list[Image.Image], *, colors: int, dither: str) -> tuple[list[Image.Image], list[str]]:
    if not images:
        return [], []
    mosaic = _compose_mosaic(images)
    palette = kmeans_palette(mosaic, max(2, min(256, int(colors))))
    return [_quantize_with_palette(img, palette, dither=dither) for img in images], [rgb_to_hex(rgb) for rgb in palette]


def compose_horizontal_sprite_sheet(frame_paths: list[Path], out_path: str | Path) -> Path:
    frames = []
    for path in frame_paths:
        with Image.open(path) as opened:
            frames.append(opened.convert("RGBA"))
    if not frames:
        raise ValueError("没有可用于合成精灵表的帧")
    sheet = _compose_mosaic(frames)
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target)
    return target


def compose_grid_sprite_sheet(
    frame_paths: list[Path],
    out_path: str | Path,
    *,
    rows: int,
    cols: int,
    frame_size: tuple[int, int],
) -> Path:
    """把 rows×cols 帧排成网格 sheet，每帧统一占 frame_size。

    用于多行 mosaic 的整张预览：行间纵向堆叠，列间横向铺开。每帧按底部居中
    贴齐到固定单元格内，便于直接和原 sprite_mosaic.png 对照。
    """
    safe_rows = max(1, int(rows))
    safe_cols = max(1, int(cols))
    cell_w, cell_h = max(1, int(frame_size[0])), max(1, int(frame_size[1]))
    expected = safe_rows * safe_cols
    if len(frame_paths) != expected:
        raise ValueError(f"帧数量 {len(frame_paths)} 与 rows×cols={expected} 不匹配")
    sheet = Image.new("RGBA", (cell_w * safe_cols, cell_h * safe_rows), (0, 0, 0, 0))
    for index, path in enumerate(frame_paths):
        row_index = index // safe_cols
        col_index = index % safe_cols
        with Image.open(path) as opened:
            frame = opened.convert("RGBA")
        # 底部居中贴齐到单元格
        offset_x = col_index * cell_w + max(0, (cell_w - frame.width) // 2)
        offset_y = row_index * cell_h + max(0, cell_h - frame.height)
        sheet.alpha_composite(frame, (offset_x, offset_y))
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target)
    return target


def compose_gif(frame_paths: list[Path], out_path: str | Path, *, duration_ms: int, loop: int = 0) -> Path:
    frames: list[Image.Image] = []
    for path in frame_paths:
        with Image.open(path) as opened:
            frames.append(opened.convert("RGBA"))
    if not frames:
        raise ValueError("没有可用于合成 GIF 的帧")
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    first, rest = frames[0], frames[1:]
    first.save(
        target,
        save_all=True,
        append_images=rest,
        duration=max(20, int(duration_ms)),
        loop=max(0, int(loop)),
        disposal=2,
    )
    return target
