"""Pixel Grid 提取测试。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

import pix.grid.extract as extract_mod
from pix.grid.extract import extract_pixel_grid, infer_grid_aligned_output_size
from pix.pixelize.perfect_pixel import GeneratedPreprocessResult
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


def test_extract_generated_preprocess_records_meta(tmp_path: Path) -> None:
    src = _scaled_grid(tmp_path / "generated.png")

    grid = extract_pixel_grid(
        src,
        output_size=(4, 4),
        max_colors=4,
        auto_crop=False,
        remove_bg=False,
        generated_preprocess_method="perfect_pixel",
    )

    meta = grid.metadata["generated_preprocess"]
    assert meta["applied"] is True
    assert meta["backend"] in {"perfectPixel-main/noCV2", "builtin_numpy"}
    assert meta["refined_size"] == [4, 4]
    assert grid.metadata["preprocess_order"] == [
        "perfect_pixel",
        "auto_crop",
        "remove_background",
        "transparent_canvas_pad",
    ]
    assert grid.metadata["processed_size"] == [4, 4]


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


def test_extract_removes_closed_background_hole_after_alignment(tmp_path: Path) -> None:
    base = Image.new("RGBA", (16, 16), (255, 0, 255, 255))
    arr = np.asarray(base).copy()
    arr[5:11, 5] = [20, 12, 10, 255]
    arr[5:11, 10] = [20, 12, 10, 255]
    arr[5, 5:11] = [20, 12, 10, 255]
    arr[10, 5:11] = [20, 12, 10, 255]
    src = tmp_path / "closed-hole.png"
    Image.fromarray(arr, mode="RGBA").resize((128, 128), Image.Resampling.NEAREST).save(src)

    grid = extract_pixel_grid(
        src,
        output_size=(16, 16),
        max_colors=4,
        auto_crop=False,
        remove_bg=True,
        bg_tolerance=4,
        generated_preprocess_method="perfect_pixel",
    )

    assert grid.pixels[0][0] == -1
    assert grid.pixels[7][7] == -1
    assert grid.pixels[5][5] != -1
    rendered = render_pixel_grid(grid)
    out = np.asarray(rendered)
    assert out[7, 7, 3] == 0


def test_extract_pads_tight_perfect_pixel_crop_to_rounded_square(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (128, 128), (255, 0, 255)).save(source)
    preprocessed = Image.new("RGBA", (20, 15), (220, 40, 60, 255))

    def fake_preprocess(*args, **kwargs):
        return GeneratedPreprocessResult(
            image=preprocessed,
            meta={"applied": True, "backend": "test", "refined_size": [20, 15]},
        )

    monkeypatch.setattr(extract_mod, "preprocess_generated_image", fake_preprocess)

    grid = extract_pixel_grid(
        source,
        output_size=(16, 16),
        max_colors=4,
        auto_crop=True,
        remove_bg=False,
        generated_preprocess_method="perfect_pixel",
    )

    assert (grid.canvas.width, grid.canvas.height) == (24, 24)
    assert grid.metadata["requested_output_size"] == [16, 16]
    assert grid.metadata["effective_output_size"] == [24, 24]
    assert grid.metadata["canvas_pad"] == {
        "applied": True,
        "source_size": [20, 15],
        "output_size": [24, 24],
        "round_step": 8,
        "offset": [2, 4],
    }
    rendered = render_pixel_grid(grid)
    assert rendered.size == (24, 24)
    assert rendered.getchannel("A").getbbox() == (2, 4, 22, 19)


def test_extract_handles_crop_smaller_than_output_grid(tmp_path: Path) -> None:
    img = Image.new("RGBA", (3, 2), (0, 0, 0, 0))
    img.putpixel((1, 0), (220, 40, 60, 255))
    img.putpixel((1, 1), (30, 20, 20, 255))
    src = tmp_path / "tiny-crop.png"
    img.save(src)

    grid = extract_pixel_grid(
        src,
        output_size=(16, 16),
        max_colors=4,
        auto_crop=False,
        remove_bg=False,
        generated_preprocess_method="none",
    )

    assert grid.canvas.width == 16
    assert grid.canvas.height == 16
    assert any(v != -1 for row in grid.pixels for v in row)


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
