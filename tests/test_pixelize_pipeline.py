"""像素化管线测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pix.analysis.schema import PixAnalysis
from pix.pixelize.core import PixelizeParams, pixelize


class TestPixelize:
    def test_without_analysis_no_preset(self, sample_image: Path) -> None:
        params = PixelizeParams(output_size=(32, 32), colors=6, dither="none", preset="auto")
        img, preview, meta = pixelize(sample_image, params)
        assert img.size == (32, 32)
        assert meta["palette_size"] <= 6
        assert meta["palette_size"] >= 2
        assert meta["used_analysis"] is False
        assert meta["effective_params"]["output_size"] == [32, 32]
        assert meta["effective_params"]["colors"] == 6
        # preview_scale 默认 4 → 应生成 128x128 的预览
        assert preview is not None
        assert preview.size == (128, 128)

    def test_preview_produced_when_scale_gt_1(self, sample_image: Path) -> None:
        params = PixelizeParams(output_size=(32, 32), colors=4, preview_scale=4)
        img, preview, _ = pixelize(sample_image, params)
        assert preview is not None
        assert preview.size == (128, 128)

    def test_preview_none_when_scale_zero(self, sample_image: Path) -> None:
        params = PixelizeParams(output_size=(32, 32), colors=4, preview_scale=0)
        img, preview, _ = pixelize(sample_image, params)
        assert preview is None

    def test_gameboy_preset_overrides(self, sample_image: Path) -> None:
        params = PixelizeParams(preset="gameboy")
        img, _, meta = pixelize(sample_image, params)
        assert img.size == (160, 144)
        # 4 色锁定
        assert meta["palette_size"] == 4
        assert meta["effective_params"]["preset"] == "gameboy"
        # 所有颜色都必须来自 GameBoy 锁定调色板
        locked = {"#0F380F", "#306230", "#8BAC0F", "#9BBC0F"}
        assert set(meta["palette"]).issubset(locked)

    def test_pico8_preset_locked(self, sample_image: Path) -> None:
        params = PixelizeParams(preset="pico8")
        _, _, meta = pixelize(sample_image, params)
        assert meta["palette_size"] == 16
        # PICO-8 16 色都应出现
        assert "#000000".upper() in meta["palette"]
        assert "#FFF1E8" in meta["palette"]

    def test_analysis_drives_palette(
        self, sample_image: Path, fake_analysis_dict: dict
    ) -> None:
        analysis = PixAnalysis.model_validate(fake_analysis_dict)
        params = PixelizeParams(output_size=(64, 64), colors=8, preset="auto")
        _, _, meta = pixelize(sample_image, params, analysis=analysis)
        assert meta["used_analysis"] is True
        # 前几位应来自 analysis palette（大小写已规范化）
        first_colors = meta["palette"][:4]
        assert "#1E5AB4" in first_colors
        assert "#F0C850" in first_colors
        # analysis 建议 ordered 抖动，在 preset=auto 时生效
        assert meta["effective_params"]["dither"] == "ordered"

    def test_user_preset_beats_analysis_recommendation(
        self, sample_image: Path, fake_analysis_dict: dict
    ) -> None:
        # 将 analysis 的 recommended_preset 改成 pico8，但用户明确指定 gameboy
        fake_analysis_dict["style"]["recommended_preset"] = "pico8"
        analysis = PixAnalysis.model_validate(fake_analysis_dict)
        params = PixelizeParams(preset="gameboy")
        img, _, meta = pixelize(sample_image, params, analysis=analysis)
        assert img.size == (160, 144)
        assert meta["effective_params"]["preset"] == "gameboy"

    def test_analysis_auto_preset_recommendation_applied(
        self, sample_image: Path, fake_analysis_dict: dict
    ) -> None:
        fake_analysis_dict["style"]["recommended_preset"] = "gameboy"
        analysis = PixAnalysis.model_validate(fake_analysis_dict)
        params = PixelizeParams(preset="auto")
        img, _, meta = pixelize(sample_image, params, analysis=analysis)
        assert img.size == (160, 144)  # 由 analysis 推荐触发
        assert meta["effective_params"]["preset"] == "gameboy"

    def test_colors_clamped(self, sample_image: Path) -> None:
        params = PixelizeParams(colors=2)
        _, _, meta = pixelize(sample_image, params)
        assert meta["palette_size"] >= 2
        assert meta["effective_params"]["colors"] == 2

    def test_dither_values_all_work(self, sample_image: Path) -> None:
        for d in ("none", "ordered", "floyd_steinberg"):
            params = PixelizeParams(output_size=(16, 16), colors=4, dither=d)
            img, _, meta = pixelize(sample_image, params)
            assert img.size == (16, 16)
            assert meta["effective_params"]["dither"] == d

    def test_accepts_pil_image_directly(self, sample_image: Path) -> None:
        img = Image.open(sample_image)
        params = PixelizeParams(output_size=(16, 16), colors=4)
        out, _, _ = pixelize(img, params)
        assert out.size == (16, 16)
