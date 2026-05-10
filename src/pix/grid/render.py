"""Pixel Grid JSON → 精确 PNG 渲染。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from pix.pixelize.palette import hex_to_rgb
from pix.grid.schema import PixelGrid, load_grid


def render_pixel_grid(grid: PixelGrid) -> Image.Image:
    """把 PixelGrid 确定性渲染成 RGBA 图片。"""
    width = grid.canvas.width
    height = grid.canvas.height
    transparent = grid.canvas.transparent_index
    palette = {c.id: hex_to_rgb(c.hex) for c in grid.palette}
    arr = np.zeros((height, width, 4), dtype=np.uint8)

    for y, row in enumerate(grid.pixels):
        for x, idx in enumerate(row):
            if idx == transparent:
                arr[y, x] = [0, 0, 0, 0]
                continue
            rgb = palette[idx]
            arr[y, x] = [rgb[0], rgb[1], rgb[2], 255]
    return Image.fromarray(arr, mode="RGBA")


def render_grid_file(
    json_path: str | Path,
    out_path: str | Path,
    *,
    preview_scale: int = 0,
) -> tuple[Path, Path | None]:
    """从 .grid.json 渲染 PNG，并可选输出 nearest 放大预览。"""
    grid = load_grid(json_path)
    image = render_pixel_grid(grid)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)

    preview_path: Path | None = None
    scale = max(0, int(preview_scale))
    if scale > 1:
        preview_path = out.with_name(out.stem + "_preview.png")
        image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST).save(
            preview_path
        )
    return out, preview_path
