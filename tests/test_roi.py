"""语义区域处理测试。"""

from __future__ import annotations

from PIL import Image

from pix.analysis.schema import BBoxNorm, SemanticRegion
from pix.pixelize.roi import apply_semantic_regions


def test_apply_semantic_regions_preserves_alpha() -> None:
    img = Image.new("RGBA", (4, 4), (10, 20, 30, 0))
    img.putpixel((1, 1), (100, 120, 140, 255))
    region = SemanticRegion(
        label="subject",
        bbox_norm=BBoxNorm(x=0.2, y=0.2, w=0.5, h=0.5),
        palette_hint=["#FFFFFF"],
    )

    out = apply_semantic_regions(img, [region])

    assert out.mode == "RGBA"
    assert out.getpixel((0, 0))[3] == 0
    assert out.getpixel((1, 1)) == (255, 255, 255, 255)


def test_apply_semantic_regions_keeps_transparent_pixels_transparent() -> None:
    img = Image.new("RGBA", (3, 3), (0, 180, 255, 0))
    img.putpixel((1, 1), (20, 30, 40, 255))
    region = SemanticRegion(
        label="subject",
        bbox_norm=BBoxNorm(x=0.2, y=0.2, w=0.5, h=0.5),
        palette_hint=["#FF0000"],
    )

    out = apply_semantic_regions(img, [region])

    assert out.getpixel((0, 0))[3] == 0
    assert out.getpixel((1, 1)) == (255, 0, 0, 255)


def test_apply_semantic_regions_skips_full_canvas_regions() -> None:
    img = Image.new("RGBA", (3, 3), (0, 180, 255, 0))
    img.putpixel((1, 1), (20, 30, 40, 255))
    region = SemanticRegion(
        label="full_aura",
        bbox_norm=BBoxNorm(x=0, y=0, w=1, h=1),
        palette_hint=["#FF0000"],
    )

    out = apply_semantic_regions(img, [region])

    assert out.getpixel((0, 0))[3] == 0
    assert out.getpixel((1, 1)) == (20, 30, 40, 255)
