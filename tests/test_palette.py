"""调色板工具函数测试。"""

from __future__ import annotations

import pytest
from PIL import Image

from pix.analysis.schema import ColorSwatch
from pix.pixelize.palette import (
    build_palette_image,
    hex_to_rgb,
    kmeans_palette,
    merge_palette,
    rgb_to_hex,
    swatches_to_rgb_list,
)


def test_hex_roundtrip() -> None:
    assert hex_to_rgb("#FF00AA") == (255, 0, 170)
    assert hex_to_rgb("ff00aa") == (255, 0, 170)
    assert rgb_to_hex((255, 0, 170)) == "#FF00AA"


def test_swatches_sorted_by_weight() -> None:
    palette = [
        ColorSwatch(hex="#000000", weight=0.1, role="primary"),
        ColorSwatch(hex="#FFFFFF", weight=0.8, role="background"),
        ColorSwatch(hex="#FF0000", weight=0.5, role="accent"),
    ]
    ordered = swatches_to_rgb_list(palette)
    assert ordered[0] == (255, 255, 255)
    assert ordered[1] == (255, 0, 0)
    assert ordered[2] == (0, 0, 0)


class TestMergePalette:
    def test_locked_take_priority(self) -> None:
        locked = [(10, 20, 30), (40, 50, 60)]
        extra = [(70, 80, 90)]
        result = merge_palette(locked, extra, target_k=3)
        assert result == [(10, 20, 30), (40, 50, 60), (70, 80, 90)]

    def test_dedupes(self) -> None:
        locked = [(10, 20, 30)]
        extra = [(10, 20, 30), (40, 50, 60)]
        result = merge_palette(locked, extra, target_k=3)
        assert result == [(10, 20, 30), (40, 50, 60)]

    def test_truncates_to_target(self) -> None:
        locked = [(0, 0, 0)]
        extra = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        result = merge_palette(locked, extra, target_k=2)
        assert result == [(0, 0, 0), (255, 0, 0)]


def test_kmeans_returns_k_colors() -> None:
    img = Image.new("RGB", (32, 32), (100, 100, 100))
    # 部分像素为红
    for x in range(10):
        for y in range(10):
            img.putpixel((x, y), (200, 0, 0))
    k = 4
    palette = kmeans_palette(img, k, sample=256)
    assert len(palette) == k
    for c in palette:
        assert len(c) == 3
        assert all(0 <= v <= 255 for v in c)


def test_build_palette_image_is_P_mode() -> None:
    palette = [(0, 0, 0), (255, 255, 255), (255, 0, 0)]
    img = build_palette_image(palette)
    assert img.mode == "P"
    pal = img.getpalette()
    assert pal is not None
    # 调色板前三组应与给定一致
    assert pal[0:3] == [0, 0, 0]
    assert pal[3:6] == [255, 255, 255]
    assert pal[6:9] == [255, 0, 0]
