"""smart resample / snap_to_grid / remove_bg 的单元测试。"""

from __future__ import annotations

import numpy as np
from PIL import Image

from pix.analysis.schema import BBoxNorm, PixAnalysis, SemanticRegion, StyleAnalysis
from pix.pixelize.bg_removal import (
    key_color_edge_speckle_mask,
    key_color_edge_spill_mask,
    key_color_mask,
    remove_background,
    remove_detached_dark_edges,
    remove_key_color,
    remove_tiny_alpha_islands,
    remove_translucent_edge_halo,
)
from pix.pixelize.core import (
    PixelizeParams,
    _detect_grid_size,
    _downsample,
    pixelize,
)
from pix.pixelize.perfect_pixel import preprocess_generated_image


def _pixel_art(size_px: int = 128, grid: int = 8, n_colors: int = 4) -> Image.Image:
    """造一张"干净的像素画"：每 grid x grid 个像素填同一种色。"""
    rng = np.random.default_rng(0)
    tiles_w = size_px // grid
    tiles_h = size_px // grid
    palette = np.array([
        [200, 60, 60],
        [60, 180, 90],
        [60, 120, 220],
        [240, 200, 80],
    ])[:n_colors]
    tile_idx = rng.integers(0, n_colors, size=(tiles_h, tiles_w))
    arr = np.zeros((size_px, size_px, 3), dtype=np.uint8)
    for y in range(tiles_h):
        for x in range(tiles_w):
            arr[y * grid : (y + 1) * grid, x * grid : (x + 1) * grid] = palette[tile_idx[y, x]]
    return Image.fromarray(arr, mode="RGB")


def _solid_bg_with_subject(
    size: int = 128, bg=(15, 23, 42), subject=(240, 120, 80)
) -> Image.Image:
    """造一张：纯色底 + 中央一个主体块。"""
    arr = np.full((size, size, 3), bg, dtype=np.uint8)
    s = size // 4
    arr[s : size - s, s : size - s] = subject
    return Image.fromarray(arr, mode="RGB")


class TestDetectGridSize:
    def test_clean_pixel_art_returns_grid(self) -> None:
        img = _pixel_art(size_px=128, grid=8)
        g = _detect_grid_size(img)
        # 允许 ±1 误差
        assert 6 <= g <= 10

    def test_photo_like_returns_one(self) -> None:
        # 纯噪点：没有明显网格
        rng = np.random.default_rng(1)
        arr = rng.integers(0, 255, (128, 128, 3), dtype=np.uint8)
        img = Image.fromarray(arr, mode="RGB")
        g = _detect_grid_size(img)
        assert g == 1


class TestDownsample:
    def test_smart_preserves_sharp_edges(self) -> None:
        img = _pixel_art(size_px=256, grid=16)
        out = _downsample(img, (32, 32), mode="smart", snap=True)
        assert out.size == (32, 32)

    def test_box_mode(self) -> None:
        img = _pixel_art(size_px=256, grid=16)
        out = _downsample(img, (32, 32), mode="box", snap=False)
        assert out.size == (32, 32)

    def test_bicubic_mode(self) -> None:
        img = _pixel_art(size_px=256, grid=16)
        out = _downsample(img, (32, 32), mode="bicubic")
        assert out.size == (32, 32)

    def test_nearest_mode(self) -> None:
        img = _pixel_art(size_px=256, grid=16)
        out = _downsample(img, (32, 32), mode="nearest")
        assert out.size == (32, 32)

    def test_preserves_aspect_ratio_with_transparent_padding(self) -> None:
        img = Image.new("RGBA", (40, 20), (255, 0, 0, 255))
        out = _downsample(img, (20, 20), mode="nearest")
        arr = np.asarray(out)

        assert out.size == (20, 20)
        assert (arr[:5, :, 3] == 0).all()
        assert (arr[15:, :, 3] == 0).all()
        assert (arr[5:15, :, 3] == 255).all()
        assert tuple(arr[10, 10, :3]) == (255, 0, 0)


class TestGeneratedPerfectPixelPreprocess:
    def _transparent_pixel_source(self) -> Image.Image:
        base = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        arr = np.asarray(base).copy()
        arr[1, 1] = [220, 40, 60, 255]
        arr[2, 1] = [40, 20, 25, 255]
        arr[1, 2] = [40, 20, 25, 255]
        arr[2, 2] = [220, 40, 60, 255]
        return Image.fromarray(arr, mode="RGBA").resize((64, 64), Image.Resampling.NEAREST)

    def test_wrapper_preserves_alpha_and_target_size(self) -> None:
        result = preprocess_generated_image(
            self._transparent_pixel_source(),
            method="perfect_pixel",
            target_size=(4, 4),
        )

        assert result.meta["applied"] is True
        assert result.meta["backend"] in {"perfectPixel-main/noCV2", "builtin_numpy"}
        assert result.image.size == (4, 4)
        rgba = np.asarray(result.image.convert("RGBA"))
        assert rgba[0, 0, 3] == 0
        assert rgba[1, 1, 3] == 255

    def test_pixelize_local_default_keeps_legacy_preprocess(self) -> None:
        _, _, meta = pixelize(
            self._transparent_pixel_source(),
            PixelizeParams(output_size=(4, 4), colors=4, dither="none", preview_scale=0),
        )

        assert meta["generated_preprocess"]["method"] == "legacy"
        assert meta["generated_preprocess"]["applied"] is False

    def test_pixelize_generated_input_applies_preprocess(self) -> None:
        result, _, meta = pixelize(
            self._transparent_pixel_source(),
            PixelizeParams(output_size=(4, 4), colors=4, dither="none", preview_scale=0),
            generated_preprocess_method="perfect_pixel",
        )

        assert result.size == (4, 4)
        assert meta["generated_preprocess"]["applied"] is True
        assert meta["generated_preprocess"]["refined_size"] == [4, 4]
        assert meta["preprocess_order"][0] == "perfect_pixel"


class TestPixelizeWithSmart:
    def test_smart_is_default(self) -> None:
        img = _pixel_art(size_px=256, grid=16)
        result, _, meta = pixelize(img, PixelizeParams(output_size=(32, 32), colors=4, preview_scale=0))
        assert result.size == (32, 32)
        assert meta["effective_params"]["resample"] == "smart"
        assert meta["detected_grid"] is not None
        assert meta["detected_grid"] >= 2
        assert meta["aspect_fit"]["content_size"] == [32, 32]

    def test_box_mode_runs(self) -> None:
        img = _pixel_art(size_px=256, grid=16)
        result, _, meta = pixelize(
            img,
            PixelizeParams(output_size=(32, 32), colors=4, resample="box", preview_scale=0),
        )
        assert result.size == (32, 32)
        assert meta["effective_params"]["resample"] == "box"


class TestAutoCrop:
    def test_auto_crop_solid_background_before_downsample(self) -> None:
        img = _solid_bg_with_subject(size=128)
        result, _, meta = pixelize(
            img,
            PixelizeParams(
                output_size=(16, 16),
                colors=4,
                dither="none",
                auto_crop=True,
                crop_padding=0.1,
                preview_scale=0,
            ),
        )
        assert result.size == (16, 16)
        assert meta["effective_params"]["auto_crop"] is True
        assert meta["crop_bbox"] is not None
        left, top, right, bottom = meta["crop_bbox"]
        assert right - left < 128
        assert bottom - top < 128

    def test_auto_crop_transparent_input(self) -> None:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        arr = np.asarray(img).copy()
        arr[20:44, 18:42] = [240, 80, 80, 255]
        img = Image.fromarray(arr, mode="RGBA")

        result, _, meta = pixelize(
            img,
            PixelizeParams(
                output_size=(16, 16),
                colors=4,
                dither="none",
                auto_crop=True,
                preview_scale=0,
            ),
        )

        assert result.size == (16, 16)
        assert meta["crop_bbox"] is not None
        assert result.mode == "RGBA"


class TestRemoveBackground:
    def test_corner_bg_becomes_transparent(self) -> None:
        img = _solid_bg_with_subject(size=64)
        out = remove_background(img, tolerance=8)
        assert out.mode == "RGBA"
        arr = np.asarray(out)
        # 左上角应该透明
        assert arr[0, 0, 3] == 0
        # 中心主体应该仍然不透明
        assert arr[32, 32, 3] == 255

    def test_tolerance_zero_still_works(self) -> None:
        img = _solid_bg_with_subject(size=32)
        out = remove_background(img, tolerance=0)
        arr = np.asarray(out)
        assert arr[0, 0, 3] == 0

    def test_feather_softens_subject_edge_alpha(self) -> None:
        img = _solid_bg_with_subject(size=64)
        out_no = remove_background(img, tolerance=12, feather=0)
        out_feather = remove_background(img, tolerance=12, feather=2, edge_style="feather")
        # feather 后背景仍全透明，但主体边缘 alpha 会降低成半透明。
        alpha_no = np.asarray(out_no)[..., 3]
        alpha_fe = np.asarray(out_feather)[..., 3]
        assert (alpha_fe == 0).sum() == (alpha_no == 0).sum()
        assert alpha_fe[0, 0] == 0
        assert (alpha_fe[0, :] == 0).all()
        assert (alpha_fe[:, 0] == 0).all()
        assert 0 < alpha_fe[16, 16] < 255
        assert alpha_fe[32, 32] == 255

    def test_keep_border_bleed_when_corners_differ(self) -> None:
        """当四角颜色差异大（主体可能压到边），不硬抠。"""
        arr = np.zeros((64, 64, 3), dtype=np.uint8)
        arr[:32, :32] = [255, 0, 0]
        arr[:32, 32:] = [0, 255, 0]
        arr[32:, :32] = [0, 0, 255]
        arr[32:, 32:] = [255, 255, 0]
        img = Image.fromarray(arr, mode="RGB")
        out = remove_background(img, tolerance=8)
        # 四角色不一致，应原样返回（全不透明）
        a = np.asarray(out)[..., 3]
        assert (a == 255).all()

    def test_key_background_with_slight_corner_variation_is_removed(self) -> None:
        img = Image.new("RGB", (64, 64), (252, 3, 251))
        arr = np.asarray(img).copy()
        arr[:8, -8:] = [246, 15, 241]
        arr[-8:, :8] = [238, 34, 236]
        arr[-8:, -8:] = [242, 29, 239]
        arr[24:40, 24:40] = [238, 210, 128]
        img = Image.fromarray(arr, mode="RGB")

        out = remove_background(img, tolerance=26)
        alpha = np.asarray(out)[..., 3]

        assert alpha[0, 0] == 0
        assert alpha[4, 60] == 0
        assert alpha[60, 4] == 0
        assert alpha[32, 32] == 255

    def test_feather_uses_diagonal_neighbors(self) -> None:
        img = Image.new("RGB", (5, 5), (240, 240, 240))
        for x, y in ((2, 2), (1, 2), (2, 1), (3, 2), (2, 3)):
            img.putpixel((x, y), (20, 20, 20))

        out = remove_background(img, tolerance=4, feather=1, edge_style="feather")
        alpha = np.asarray(out)[..., 3]

        # 中心像素只有对角方向接触背景；8 邻域羽化应覆盖它。
        assert 0 < alpha[2, 2] < 255

    def test_remove_background_clears_closed_background_holes(self) -> None:
        img = Image.new("RGBA", (12, 12), (255, 0, 255, 255))
        arr = np.asarray(img).copy()
        arr[3:9, 3] = [20, 20, 20, 255]
        arr[3:9, 8] = [20, 20, 20, 255]
        arr[3, 3:9] = [20, 20, 20, 255]
        arr[8, 3:9] = [20, 20, 20, 255]
        img = Image.fromarray(arr, mode="RGBA")

        out = remove_background(img, tolerance=4)
        out_arr = np.asarray(out)

        assert out_arr[0, 0, 3] == 0
        assert out_arr[5, 5, 3] == 0
        assert tuple(out_arr[5, 5, :3]) == (0, 0, 0)
        assert out_arr[3, 3, 3] == 255

    def test_remove_key_color_clears_closed_holes(self) -> None:
        img = Image.new("RGBA", (12, 12), (255, 0, 255, 255))
        arr = np.asarray(img).copy()
        # 造一个黑色闭环，中间仍是 key color。flood-fill 类方法通常清不到这个孔洞。
        arr[3:9, 3] = [20, 20, 20, 255]
        arr[3:9, 8] = [20, 20, 20, 255]
        arr[3, 3:9] = [20, 20, 20, 255]
        arr[8, 3:9] = [20, 20, 20, 255]
        img = Image.fromarray(arr, mode="RGBA")

        out = remove_key_color(img, key_rgb=(255, 0, 255), tolerance=4)
        out_arr = np.asarray(out)

        assert out_arr[0, 0, 3] == 0
        assert out_arr[5, 5, 3] == 0
        assert tuple(out_arr[0, 0, :3]) == (0, 0, 0)
        assert tuple(out_arr[5, 5, :3]) == (0, 0, 0)
        assert out_arr[3, 3, 3] == 255
        assert not key_color_mask(out_arr, (255, 0, 255), tolerance=4, visible_only=False).any()

    def test_key_color_edge_speckle_removes_small_dark_edge_dots(self) -> None:
        img = Image.new("RGBA", (9, 9), (0, 0, 0, 0))
        arr = np.asarray(img).copy()
        arr[2:7, 2:7] = [20, 20, 20, 255]
        arr[1, 2] = [128, 0, 128, 255]
        arr[7, 6] = [150, 0, 150, 255]
        img = Image.fromarray(arr, mode="RGBA")

        out = remove_key_color(
            img,
            key_rgb=(255, 0, 255),
            tolerance=8,
            edge_speckle=True,
            edge_speckle_max_area=4,
            edge_speckle_radius=2,
        )
        out_arr = np.asarray(out)

        assert out_arr[1, 2, 3] == 0
        assert out_arr[7, 6, 3] == 0
        assert out_arr[3, 3, 3] == 255

    def test_key_color_edge_speckle_removes_thin_edge_strip(self) -> None:
        img = Image.new("RGBA", (24, 12), (0, 0, 0, 0))
        arr = np.asarray(img).copy()
        arr[5:9, 4:20] = [20, 20, 20, 255]
        arr[4, 6:18] = [130, 0, 130, 255]
        img = Image.fromarray(arr, mode="RGBA")

        out = remove_key_color(
            img,
            key_rgb=(255, 0, 255),
            tolerance=8,
            edge_speckle=True,
            edge_speckle_max_area=4,
            edge_speckle_max_thickness=2,
            edge_speckle_radius=1,
        )
        out_arr = np.asarray(out)

        assert (out_arr[4, 6:18, 3] == 0).all()
        assert out_arr[5, 6, 3] == 255

    def test_key_color_edge_speckle_preserves_larger_content_region(self) -> None:
        img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        arr = np.asarray(img).copy()
        arr[3:7, 3:7] = [150, 0, 150, 255]
        img = Image.fromarray(arr, mode="RGBA")

        mask = key_color_edge_speckle_mask(
            np.asarray(img),
            (255, 0, 255),
            max_area=4,
            radius=2,
        )

        assert not mask.any()

    def test_key_color_edge_speckle_runs_multiple_passes(self) -> None:
        img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        arr = np.asarray(img).copy()
        arr[3:5, 3:5] = [20, 20, 20, 255]
        arr[2, 3] = [140, 0, 140, 255]
        arr[1, 3] = [130, 0, 130, 255]
        img = Image.fromarray(arr, mode="RGBA")

        out = remove_key_color(
            img,
            key_rgb=(255, 0, 255),
            tolerance=8,
            edge_speckle=True,
            edge_speckle_max_area=4,
            edge_speckle_radius=1,
            edge_speckle_passes=2,
        )
        out_arr = np.asarray(out)

        assert out_arr[2, 3, 3] == 0
        assert out_arr[1, 3, 3] == 0
        assert out_arr[3, 3, 3] == 255

    def test_key_color_edge_spill_mask_finds_quantized_purple_halo(self) -> None:
        img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        arr = np.asarray(img).copy()
        arr[3:7, 3:7] = [32, 24, 16, 255]
        arr[2, 3:7] = [196, 0, 196, 255]
        arr[7, 3:7] = [66, 3, 71, 255]
        img = Image.fromarray(arr, mode="RGBA")

        mask = key_color_edge_spill_mask(np.asarray(img), (255, 0, 255), radius=2)

        assert int(mask.sum()) == 8
        assert not mask[3:7, 3:7].any()

    def test_remove_key_color_clears_quantized_edge_spill(self) -> None:
        img = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
        arr = np.asarray(img).copy()
        arr[4:8, 4:8] = [32, 24, 16, 255]
        arr[3, 4:8] = [196, 0, 196, 255]
        arr[2, 4:8] = [66, 3, 71, 255]
        img = Image.fromarray(arr, mode="RGBA")

        out = remove_key_color(
            img,
            key_rgb=(255, 0, 255),
            tolerance=8,
            edge_spill=True,
            edge_spill_radius=2,
            edge_spill_passes=3,
        )
        out_arr = np.asarray(out)

        assert (out_arr[2:4, 4:8, 3] == 0).all()
        assert (out_arr[2:4, 4:8, :3] == 0).all()
        assert (out_arr[4:8, 4:8, 3] == 255).all()

    def test_remove_key_color_can_turn_edge_spill_into_outline(self) -> None:
        img = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
        arr = np.asarray(img).copy()
        arr[4:8, 4:8] = [220, 150, 40, 255]
        arr[4:8, 4] = [0, 0, 0, 255]
        arr[3, 4:8] = [196, 0, 196, 255]
        arr[2, 4:8] = [66, 3, 71, 255]
        img = Image.fromarray(arr, mode="RGBA")

        out = remove_key_color(
            img,
            key_rgb=(255, 0, 255),
            tolerance=8,
            edge_spill=True,
            edge_spill_radius=2,
            edge_spill_passes=3,
            edge_spill_outline=True,
        )
        out_arr = np.asarray(out)

        assert (out_arr[3, 4:8, 3] == 255).all()
        assert (out_arr[3, 4:8, :3] == 0).all()
        # 外侧第二圈离主体太远，仍应抠透明，避免凭空加粗描边。
        assert (out_arr[2, 4:8, 3] == 0).all()
        assert (out_arr[4:8, 4:8, 3] == 255).all()
        assert not key_color_edge_spill_mask(out_arr, (255, 0, 255), radius=2).any()

    def test_remove_detached_dark_edges_clears_floating_outline(self) -> None:
        img = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
        arr = np.asarray(img).copy()
        arr[5:8, 5:8] = [220, 150, 40, 255]
        arr[4, 5:8] = [0, 0, 0, 255]
        arr[2, 5:8] = [0, 0, 0, 255]
        arr[6, 6] = [0, 0, 0, 255]  # 主体内部暗色不能被删
        img = Image.fromarray(arr, mode="RGBA")

        out = remove_detached_dark_edges(img)
        out_arr = np.asarray(out)

        assert (out_arr[2, 5:8, 3] == 0).all()
        assert (out_arr[4, 5:8, 3] == 255).all()
        assert out_arr[6, 6, 3] == 255

    def test_remove_detached_dark_edges_clears_desaturated_floating_fragment(self) -> None:
        img = Image.new("RGBA", (14, 14), (0, 0, 0, 0))
        arr = np.asarray(img).copy()
        arr[6:9, 6:9] = [60, 150, 220, 255]
        arr[5, 6:9] = [118, 118, 112, 255]
        arr[3, 6:9] = [112, 112, 108, 255]
        img = Image.fromarray(arr, mode="RGBA")

        out = remove_detached_dark_edges(img)
        out_arr = np.asarray(out)

        assert (out_arr[3, 6:9, 3] == 0).all()
        assert (out_arr[5, 6:9, 3] == 255).all()
        assert (out_arr[6:9, 6:9, 3] == 255).all()

    def test_remove_translucent_edge_halo_clears_key_color_fringe(self) -> None:
        img = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
        arr = np.asarray(img).copy()
        arr[4:8, 4:8] = [220, 220, 235, 255]
        arr[3, 4:8] = [125, 30, 146, 150]
        arr[8, 4:8] = [125, 30, 146, 224]
        arr[5, 5] = [125, 30, 146, 255]
        img = Image.fromarray(arr, mode="RGBA")

        out = remove_translucent_edge_halo(img, key_rgb=(255, 0, 255), alpha_cutoff=128, key_alpha_cutoff=224)
        out_arr = np.asarray(out)

        assert (out_arr[3, 4:8, 3] == 0).all()
        assert (out_arr[8, 4:8, 3] == 0).all()
        assert (out_arr[4:8, 4:8, 3] == 255).all()
        assert out_arr[5, 5, 3] == 255

    def test_remove_tiny_alpha_islands_clears_small_detached_component(self) -> None:
        img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        arr = np.asarray(img).copy()
        arr[5:12, 5:12] = [220, 150, 40, 255]
        arr[2:4, 2:4] = [80, 80, 80, 255]
        img = Image.fromarray(arr, mode="RGBA")

        out = remove_tiny_alpha_islands(img, max_area=8, max_axis=4)
        out_arr = np.asarray(out)

        assert (out_arr[2:4, 2:4, 3] == 0).all()
        assert (out_arr[5:12, 5:12, 3] == 255).all()

    def test_remove_key_color_preserves_nearby_content_color(self) -> None:
        img = Image.new("RGBA", (4, 4), (255, 0, 255, 255))
        arr = np.asarray(img).copy()
        arr[1:3, 1:3] = [230, 0, 230, 255]
        img = Image.fromarray(arr, mode="RGBA")

        out = remove_key_color(img, key_rgb=(255, 0, 255), tolerance=8, spill_tolerance=20)
        out_arr = np.asarray(out)

        assert out_arr[0, 0, 3] == 0
        assert out_arr[1, 1, 3] == 255
        assert tuple(out_arr[1, 1, :3]) == (230, 0, 230)

    def test_outline_edge_style_adds_opaque_outline(self) -> None:
        img = Image.new("RGB", (8, 8), (240, 240, 240))
        img.putpixel((3, 3), (120, 200, 240))
        img.putpixel((4, 3), (120, 200, 240))
        img.putpixel((3, 4), (120, 200, 240))
        img.putpixel((4, 4), (120, 200, 240))

        out = remove_background(img, tolerance=4, edge_style="outline", feather=1)
        arr = np.asarray(out)

        assert arr[0, 0, 3] == 0
        assert arr[2, 3, 3] == 255
        assert tuple(arr[2, 3, :3]) != (240, 240, 240)
        assert arr[3, 3, 3] == 255

    def test_outline_does_not_thicken_existing_dark_border(self) -> None:
        img = Image.new("RGB", (7, 7), (240, 240, 240))
        for x, y in (
            (2, 2), (3, 2), (4, 2),
            (2, 3), (4, 3),
            (2, 4), (3, 4), (4, 4),
        ):
            img.putpixel((x, y), (12, 12, 18))
        img.putpixel((3, 3), (120, 200, 240))

        out = remove_background(img, tolerance=4, edge_style="outline", feather=1)
        arr = np.asarray(out)

        assert arr[2, 3, 3] == 255
        assert tuple(arr[2, 3, :3]) == (12, 12, 18)
        assert arr[1, 3, 3] == 0
        assert arr[3, 1, 3] == 0
        assert arr[3, 5, 3] == 0
        assert arr[5, 3, 3] == 0

    def test_hard_edge_style_ignores_feather_strength(self) -> None:
        img = _solid_bg_with_subject(size=32)
        out = remove_background(img, tolerance=12, feather=3, edge_style="hard")
        alpha = np.asarray(out)[..., 3]
        assert set(np.unique(alpha)).issubset({0, 255})

    def test_checkerboard_fake_transparency_removed_from_edges(self) -> None:
        arr = np.zeros((64, 64, 3), dtype=np.uint8)
        for y in range(64):
            for x in range(64):
                arr[y, x] = [255, 255, 255] if ((x // 8 + y // 8) % 2 == 0) else [232, 242, 248]
        arr[24:40, 24:40] = [0, 120, 255]
        arr[29:35, 29:35] = [255, 255, 255]  # 主体内部高光，不应因边缘抠背景被删
        img = Image.fromarray(arr, mode="RGB")

        out = remove_background(img, tolerance=18)
        a = np.asarray(out)[..., 3]

        assert a[0, 0] == 0
        assert a[12, 12] == 0
        assert a[26, 26] == 255
        assert a[31, 31] == 255


class TestPixelizeRemoveBg:
    def test_remove_bg_flag_produces_rgba(self) -> None:
        img = _solid_bg_with_subject(size=128)
        result, _, meta = pixelize(
            img,
            PixelizeParams(
                output_size=(32, 32),
                colors=4,
                remove_bg=True,
                bg_tolerance=16,
                preview_scale=0,
            ),
        )
        assert result.mode == "RGBA"
        arr = np.asarray(result)
        # 至少有一些透明像素
        assert (arr[..., 3] == 0).any()
        assert meta["effective_params"]["remove_bg"] is True

    def test_low_pixel_remove_bg_respects_feather_choice(self) -> None:
        img = _solid_bg_with_subject(size=128)
        result, _, meta = pixelize(
            img,
            PixelizeParams(
                output_size=(16, 16),
                colors=4,
                remove_bg=True,
                bg_tolerance=16,
                bg_feather=3,
                edge_style="feather",
                preview_scale=0,
            ),
        )

        assert meta["effective_params"]["edge_style"] == "feather"
        assert meta["effective_params"]["bg_feather"] == 3
        assert meta["edge_policy"]["applied"] is False
        assert meta["edge_policy"]["reason"] == "user_edge_style_respected"
        alpha = np.asarray(result.convert("RGBA"))[..., 3]
        assert any(0 < value < 255 for value in np.unique(alpha))

    def test_low_pixel_remove_bg_can_skip_extra_edge_treatment(self) -> None:
        img = _solid_bg_with_subject(size=128)
        result, _, meta = pixelize(
            img,
            PixelizeParams(
                output_size=(16, 16),
                colors=4,
                remove_bg=True,
                bg_tolerance=16,
                bg_feather=3,
                edge_style="hard",
                preview_scale=0,
            ),
        )

        assert meta["effective_params"]["edge_style"] == "hard"
        assert meta["edge_policy"]["reason"] == "user_edge_style_respected"
        alpha = np.asarray(result.convert("RGBA"))[..., 3]
        assert set(np.unique(alpha)).issubset({0, 255})

    def test_low_pixel_existing_alpha_uses_outline_without_remove_bg(self) -> None:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        for y in range(20, 44):
            for x in range(20, 44):
                alpha = 128 if x in {20, 43} or y in {20, 43} else 255
                img.putpixel((x, y), (180, 80, 240, alpha))

        result, _, meta = pixelize(
            img,
            PixelizeParams(
                output_size=(16, 16),
                colors=4,
                remove_bg=False,
                bg_feather=1,
                edge_style="outline",
                preview_scale=0,
            ),
        )

        assert meta["effective_params"]["edge_style"] == "outline"
        assert meta["effective_params"]["bg_feather"] == 1
        assert meta["edge_policy"]["source_alpha"] is True
        alpha = np.asarray(result.convert("RGBA"))[..., 3]
        assert set(np.unique(alpha)).issubset({0, 255})

    def test_large_pixel_can_still_use_feather(self) -> None:
        img = _solid_bg_with_subject(size=128)
        result, _, meta = pixelize(
            img,
            PixelizeParams(
                output_size=(64, 64),
                colors=4,
                remove_bg=True,
                bg_tolerance=16,
                bg_feather=2,
                edge_style="feather",
                preview_scale=0,
            ),
        )

        assert meta["effective_params"]["edge_style"] == "feather"
        assert meta["edge_policy"]["applied"] is False
        alpha = np.asarray(result.convert("RGBA"))[..., 3]
        assert any(0 < value < 255 for value in np.unique(alpha))

    def test_remove_bg_default_off(self) -> None:
        img = _solid_bg_with_subject(size=64)
        result, _, _meta = pixelize(
            img,
            PixelizeParams(output_size=(16, 16), colors=4, preview_scale=0),
        )
        # 默认不抠，应是 RGB 或 RGBA 但全不透明
        if result.mode == "RGBA":
            assert (np.asarray(result)[..., 3] == 255).all()

    def test_remove_bg_preserved_when_analysis_present(self) -> None:
        img = _solid_bg_with_subject(size=128)
        analysis = PixAnalysis(
            description="mock",
            style=StyleAnalysis(
                recommended_preset="auto",
                target_color_count=4,
                suggested_dither="none",
            ),
            palette=[],
            main_subjects=[],
            semantic_regions=[],
        )

        result, _, meta = pixelize(
            img,
            PixelizeParams(
                output_size=(32, 32),
                colors=4,
                dither="none",
                remove_bg=True,
                bg_tolerance=16,
                preview_scale=0,
            ),
            analysis=analysis,
        )

        assert meta["effective_params"]["remove_bg"] is True
        assert meta["effective_params"]["bg_tolerance"] == 16
        assert (np.asarray(result.convert("RGBA"))[..., 3] == 0).any()

    def test_remove_bg_before_semantic_regions_handles_fake_checkerboard(self) -> None:
        arr = np.zeros((128, 128, 3), dtype=np.uint8)
        for y in range(128):
            for x in range(128):
                arr[y, x] = [255, 255, 255] if ((x // 16 + y // 16) % 2 == 0) else [232, 242, 248]
        arr[44:84, 44:84] = [0, 160, 255]
        img = Image.fromarray(arr, mode="RGB")
        analysis = PixAnalysis(
            description="mock",
            style=StyleAnalysis(recommended_preset="auto", target_color_count=4, suggested_dither="none"),
            palette=[],
            main_subjects=[],
            semantic_regions=[
                SemanticRegion(
                    label="aura",
                    bbox_norm=BBoxNorm(x=0, y=0, w=1, h=1),
                    palette_hint=["#80E8FF"],
                )
            ],
        )

        result, _, meta = pixelize(
            img,
            PixelizeParams(
                output_size=(32, 32),
                colors=4,
                dither="none",
                remove_bg=True,
                bg_tolerance=18,
                preview_scale=0,
            ),
            analysis=analysis,
        )

        rgba = np.asarray(result.convert("RGBA"))
        assert meta["effective_params"]["remove_bg"] is True
        assert (rgba[..., 3] == 0).any()
        assert rgba[16, 16, 3] == 255


class TestAutoSkipRedundantBg:
    """已抠图源图传入时，auto_skip_redundant_bg=True 应跳过 remove_bg/auto_crop。"""

    def _transparent_subject(self) -> Image.Image:
        # 64x64 RGBA，主体（24x24）在中央，其他全透明 —— alpha=0 占比 ~86%
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        arr = np.asarray(img).copy()
        arr[20:44, 20:44] = [200, 100, 60, 255]
        return Image.fromarray(arr, mode="RGBA")

    def test_skip_active_when_transparency_high(self) -> None:
        img = self._transparent_subject()
        _, _, meta = pixelize(
            img,
            PixelizeParams(
                output_size=(32, 32),
                colors=4,
                dither="none",
                remove_bg=True,
                auto_crop=True,
                preview_scale=0,
            ),
            auto_skip_redundant_bg=True,
        )
        assert meta["skipped_remove_bg"] is True
        assert meta["skipped_auto_crop"] is True
        assert meta["input_transparency_ratio"] >= 0.10
        # 跳过后 crop_bbox 不会被设置
        assert meta["crop_bbox"] is None

    def test_skip_disabled_by_default(self) -> None:
        img = self._transparent_subject()
        _, _, meta = pixelize(
            img,
            PixelizeParams(
                output_size=(32, 32),
                colors=4,
                dither="none",
                remove_bg=True,
                auto_crop=True,
                preview_scale=0,
            ),
        )
        # 默认不开自动跳过：尊重 params.auto_crop=True
        assert meta["skipped_remove_bg"] is False
        assert meta["skipped_auto_crop"] is False

    def test_skip_inactive_when_no_transparency(self) -> None:
        # 实心 RGB 图：transparency_ratio=0，即使开启 auto_skip 也不跳过
        img = Image.new("RGB", (64, 64), (180, 90, 40))
        _, _, meta = pixelize(
            img,
            PixelizeParams(
                output_size=(32, 32),
                colors=4,
                dither="none",
                remove_bg=True,
                auto_crop=True,
                preview_scale=0,
            ),
            auto_skip_redundant_bg=True,
        )
        assert meta["skipped_remove_bg"] is False
        assert meta["skipped_auto_crop"] is False
        assert meta["input_transparency_ratio"] == 0.0
