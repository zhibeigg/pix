"""smart resample / snap_to_grid / remove_bg 的单元测试。"""

from __future__ import annotations

import numpy as np
from PIL import Image

from pix.analysis.schema import PixAnalysis, StyleAnalysis
from pix.pixelize.bg_removal import remove_background
from pix.pixelize.core import (
    PixelizeParams,
    _detect_grid_size,
    _downsample,
    pixelize,
)


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


class TestPixelizeWithSmart:
    def test_smart_is_default(self) -> None:
        img = _pixel_art(size_px=256, grid=16)
        result, _, meta = pixelize(img, PixelizeParams(output_size=(32, 32), colors=4, preview_scale=0))
        assert result.size == (32, 32)
        assert meta["effective_params"]["resample"] == "smart"
        assert meta["detected_grid"] is not None
        assert meta["detected_grid"] >= 2

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

    def test_feather_preserves_subject_edge(self) -> None:
        img = _solid_bg_with_subject(size=64)
        out_no = remove_background(img, tolerance=12, feather=0)
        out_feather = remove_background(img, tolerance=12, feather=2)
        # feather 后透明像素应更少（保留了主体边缘一圈）
        alpha_no = np.asarray(out_no)[..., 3]
        alpha_fe = np.asarray(out_feather)[..., 3]
        assert (alpha_fe == 0).sum() <= (alpha_no == 0).sum()

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
