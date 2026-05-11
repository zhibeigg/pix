"""Pixel Grid 提取测试。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from pix.grid.extract import extract_pixel_grid, infer_grid_aligned_output_size
from pix.grid.render import render_pixel_grid


def _scaled_grid(path: Path) -> Path:
    base = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    pixels = base.load()
    red = (220, 40, 60, 255)
    dark = (40, 20, 25, 255)
    pixels[1, 1] = dark
    pixels[2, 1] = red
    pixels[1, 2] = red
    pixels[2, 2] = dark
    base.resize((128, 128), Image.Resampling.NEAREST).save(path)
    return path


def test_infer_grid_aligned_output_size_uses_detected_source_grid(tmp_path: Path) -> None:
    src = _scaled_grid(tmp_path / "source.png")

    inferred = infer_grid_aligned_output_size(
        src,
        auto_crop=False,
        remove_bg=False,
        max_axis=64,
    )

    assert inferred.output_size == (4, 4)
    assert inferred.detected_grid >= 2
    assert inferred.fallback is False
    assert inferred.capped is False


def test_extract_scaled_pixel_grid(tmp_path: Path) -> None:
    src = _scaled_grid(tmp_path / "source.png")

    grid = extract_pixel_grid(
        src,
        output_size=(4, 4),
        max_colors=4,
        auto_crop=False,
        remove_bg=False,
    )

    assert grid.canvas.width == 4
    assert grid.canvas.height == 4
    assert len(grid.palette) == 2
    assert grid.pixels[0] == [-1, -1, -1, -1]
    assert grid.pixels[1][1] != -1
    assert grid.pixels[2][2] != -1
    assert grid.metadata["source_cell_size"] == [32.0, 32.0]

    rendered = render_pixel_grid(grid)
    arr = np.asarray(rendered)
    assert arr[0, 0, 3] == 0
    assert arr[1, 1, 3] == 255


def test_extract_auto_crop_keeps_subject(tmp_path: Path) -> None:
    img = Image.new("RGB", (128, 128), (255, 255, 255))
    for y in range(40, 88):
        for x in range(44, 84):
            img.putpixel((x, y), (180, 30, 50))
    src = tmp_path / "crop.png"
    img.save(src)

    grid = extract_pixel_grid(src, output_size=(4, 4), max_colors=2, auto_crop=True, remove_bg=True)

    assert grid.metadata["crop_bbox"] is not None
    assert any(v != -1 for row in grid.pixels for v in row)
