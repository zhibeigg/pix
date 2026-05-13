"""Ramp 调色板核心行为测试。

重点覆盖：
- schema 解析（VL 返回的 JSON）
- 本地 ramp 构建（VL 不可用兜底）
- Lab 量化（保留透明通道；颜色集合收敛到 ramp）
- `pixelize` 主链路上 palette_mode="ramp" 时走 ramp 分支
"""

from __future__ import annotations

import pytest
from PIL import Image

from pix.pixelize.core import PixelizeParams, pixelize
from pix.pixelize.ramp import (
    RampPalette,
    RampValidationError,
    build_local_ramp,
    hex_to_rgb,
    parse_ramp_payload,
    quantize_to_ramp,
    ramp_to_meta,
    rgb_to_lab,
)


class TestParsing:
    def test_parses_valid_payload(self) -> None:
        raw = """
        {
          "ramps": [
            {
              "name": "metal",
              "hue": "metal",
              "steps": [
                {"hex": "#1A1612", "role": "outline"},
                {"hex": "#4C4238", "role": "shadow"},
                {"hex": "#8C7C68", "role": "mid"},
                {"hex": "#D6C7A0", "role": "highlight"}
              ]
            }
          ]
        }
        """
        palette = parse_ramp_payload(raw, max_colors=8)
        assert palette.source == "vl"
        assert len(palette.ramps) == 1
        ramp = palette.ramps[0]
        assert ramp.name == "metal"
        assert [s.role for s in ramp.steps] == ["outline", "shadow", "mid", "highlight"]
        # 明度必须严格递增
        lums = [s.lab[0] for s in ramp.steps]
        assert all(a < b for a, b in zip(lums, lums[1:]))

    def test_tolerates_json_code_block(self) -> None:
        raw = """```json
        {"ramps":[{"name":"gold","hue":"gold","steps":[{"hex":"#332500","role":"outline"},{"hex":"#AA8330","role":"mid"},{"hex":"#FFE07A","role":"highlight"}]}]}
        ```"""
        palette = parse_ramp_payload(raw, max_colors=6)
        assert len(palette.ramps[0].steps) == 3

    def test_reassigns_roles_when_all_mid(self) -> None:
        raw = """
        {
          "ramps": [
            {
              "name": "wood",
              "hue": "wood",
              "steps": [
                {"hex": "#2A1208"},
                {"hex": "#7A3516"},
                {"hex": "#C07824"},
                {"hex": "#F0C85A"}
              ]
            }
          ]
        }
        """
        palette = parse_ramp_payload(raw, max_colors=8)
        roles = [s.role for s in palette.ramps[0].steps]
        assert roles == ["outline", "shadow", "mid", "highlight"]

    def test_trims_to_max_colors(self) -> None:
        # 2 个 ramp 各 4 step 共 8 色，预算 6 时应当裁剪
        raw = """
        {
          "ramps": [
            {
              "name": "metal",
              "hue": "metal",
              "steps": [
                {"hex": "#1A1612", "role": "outline"},
                {"hex": "#4C4238", "role": "shadow"},
                {"hex": "#8C7C68", "role": "mid"},
                {"hex": "#D6C7A0", "role": "highlight"}
              ]
            },
            {
              "name": "gem",
              "hue": "gem",
              "steps": [
                {"hex": "#0B2B4A", "role": "outline"},
                {"hex": "#1E5A99", "role": "shadow"},
                {"hex": "#3A8FD4", "role": "mid"},
                {"hex": "#B3E0FF", "role": "highlight"}
              ]
            }
          ]
        }
        """
        palette = parse_ramp_payload(raw, max_colors=6)
        assert len(palette.rgb_list) <= 6
        # 每个 ramp 仍然至少保留 3 个 step
        for ramp in palette.ramps:
            assert len(ramp.steps) >= 3

    def test_raises_on_invalid(self) -> None:
        with pytest.raises(RampValidationError):
            parse_ramp_payload("not json", max_colors=4)
        with pytest.raises(RampValidationError):
            parse_ramp_payload('{"ramps": []}', max_colors=4)


class TestLocalRamp:
    def test_single_color_image(self) -> None:
        img = Image.new("RGB", (32, 32), (120, 60, 40))
        palette = build_local_ramp(img, max_colors=6)
        assert len(palette.ramps) >= 1
        assert palette.source == "local"
        # 保证 outline/highlight 明度分化
        ramp = palette.ramps[0]
        lums = [s.lab[0] for s in ramp.steps]
        assert max(lums) - min(lums) >= 20.0

    def test_two_hue_image_gives_two_ramps(self) -> None:
        img = Image.new("RGB", (64, 64), (200, 180, 90))
        for y in range(64):
            for x in range(32):
                img.putpixel((x, y), (40, 80, 170))
        palette = build_local_ramp(img, max_colors=12, max_ramps=3)
        assert len(palette.ramps) >= 2

    def test_all_transparent_fallback(self) -> None:
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        palette = build_local_ramp(img, max_colors=4)
        assert len(palette.ramps) >= 1


class TestQuantize:
    def test_quantized_colors_are_subset_of_ramp(self) -> None:
        img = Image.new("RGB", (24, 24), (200, 50, 60))
        for y in range(24):
            for x in range(12):
                img.putpixel((x, y), (50, 70, 180))
        palette = build_local_ramp(img, max_colors=8)
        quantized = quantize_to_ramp(img, palette)
        assert quantized.mode == "RGBA"
        unique = {tuple(p[:3]) for p in quantized.getdata()}
        allowed = set(palette.rgb_list)
        assert unique.issubset(allowed)

    def test_preserves_alpha(self) -> None:
        img = Image.new("RGBA", (16, 16), (180, 120, 60, 0))
        for y in range(16):
            for x in range(8):
                img.putpixel((x, y), (180, 120, 60, 255))
        palette = build_local_ramp(img, max_colors=5)
        q = quantize_to_ramp(img, palette)
        # alpha 通道原样保留
        alphas = {pix[3] for pix in q.getdata()}
        assert 0 in alphas
        assert 255 in alphas

    def test_floyd_steinberg_runs(self) -> None:
        img = Image.new("RGB", (16, 16), (120, 90, 60))
        palette = build_local_ramp(img, max_colors=4)
        q = quantize_to_ramp(img, palette, dither="floyd_steinberg")
        assert q.size == (16, 16)


class TestPixelizeIntegration:
    def test_pixelize_with_palette_mode_ramp_populates_meta(self, sample_image) -> None:
        params = PixelizeParams(
            output_size=(32, 32),
            colors=8,
            palette_mode="ramp",
            preview_scale=0,
        )
        img, _, meta = pixelize(sample_image, params)
        assert img.size == (32, 32)
        assert meta["effective_params"]["palette_mode"] == "ramp"
        assert "ramp" in meta
        assert meta["ramp"]["ramp_count"] >= 1
        assert meta["ramp_info"]["source"] in ("local", "local_fallback")

    def test_pixelize_without_ramp_keeps_default_path(self, sample_image) -> None:
        params = PixelizeParams(
            output_size=(32, 32),
            colors=6,
            palette_mode="auto",
            preview_scale=0,
        )
        _, _, meta = pixelize(sample_image, params)
        assert "ramp" not in meta


class TestColorSpace:
    def test_rgb_to_lab_known_values(self) -> None:
        # 纯白和纯黑的 L 应当接近极值
        l_white, _, _ = rgb_to_lab((255, 255, 255))
        l_black, _, _ = rgb_to_lab((0, 0, 0))
        assert l_white > 99.0
        assert l_black < 1.0

    def test_hex_to_rgb(self) -> None:
        assert hex_to_rgb("#FF00AA") == (255, 0, 170)
        assert hex_to_rgb("ff00aa") == (255, 0, 170)


def test_ramp_to_meta_contains_expected_keys() -> None:
    img = Image.new("RGB", (24, 24), (100, 60, 180))
    palette = build_local_ramp(img, max_colors=5)
    meta = ramp_to_meta(palette)
    for key in ("ramps", "ramp_count", "step_count", "colors", "source"):
        assert key in meta


def test_ramp_palette_rgb_list_dedupe() -> None:
    # 手工构造 ramp，相邻 step 颜色相同
    raw = """
    {
      "ramps": [
        {"name":"a","hue":"a","steps":[
          {"hex":"#111111","role":"outline"},
          {"hex":"#111111","role":"shadow"},
          {"hex":"#888888","role":"mid"},
          {"hex":"#EEEEEE","role":"highlight"}
        ]}
      ]
    }
    """
    palette = parse_ramp_payload(raw, max_colors=8)
    # rgb_list 应当去重
    assert len(palette.rgb_list) == 3


class TestVlRampEndToEnd:
    """Mock Packy 返回一段 ramp JSON，验证 ramp_from_vl 能闭环。"""

    def test_ramp_from_vl_success(self, tmp_path, monkeypatch) -> None:
        from pix.config import AppConfig
        from pix.pixelize import ramp as ramp_module

        img_path = tmp_path / "src.png"
        Image.new("RGB", (64, 64), (180, 120, 60)).save(img_path)
        cfg = AppConfig()
        cfg.api.vl_api_key = "sk-test"

        payload = """{"ramps":[{"name":"wood","hue":"wood","steps":[
          {"hex":"#2A1208","role":"outline"},
          {"hex":"#7A3516","role":"shadow"},
          {"hex":"#C07824","role":"mid"},
          {"hex":"#F0C85A","role":"highlight"}
        ]}]}"""

        def fake_post_json(self, path, payload_in):
            return {"choices": [{"message": {"content": payload}}]}

        monkeypatch.setattr(
            "pix.pixelize.ramp.PackyClient.post_json", fake_post_json, raising=True
        )

        palette = ramp_module.ramp_from_vl(
            cfg,
            img_path,
            max_colors=8,
            output_size=(16, 16),
        )
        assert palette.source == "vl"
        assert len(palette.rgb_list) == 4

    def test_ramp_from_vl_retries_then_fails(self, tmp_path, monkeypatch) -> None:
        from pix.config import AppConfig
        from pix.pixelize import ramp as ramp_module

        img_path = tmp_path / "src.png"
        Image.new("RGB", (32, 32), (50, 50, 50)).save(img_path)
        cfg = AppConfig()
        cfg.api.vl_api_key = "sk-test"

        def fake_post_json(self, path, payload_in):
            return {"choices": [{"message": {"content": "no ramp here"}}]}

        monkeypatch.setattr(
            "pix.pixelize.ramp.PackyClient.post_json", fake_post_json, raising=True
        )

        with pytest.raises(RampValidationError):
            ramp_module.ramp_from_vl(cfg, img_path, max_colors=6, output_size=(16, 16), retries=1)

    def test_pixelize_ramp_falls_back_to_local_on_vl_error(self, tmp_path, monkeypatch) -> None:
        from pix.config import AppConfig
        from pix.pixelize import ramp as ramp_module

        img_path = tmp_path / "src.png"
        Image.new("RGB", (48, 48), (200, 100, 70)).save(img_path)
        cfg = AppConfig()
        cfg.api.vl_api_key = "sk-test"

        def fake_post_json(self, path, payload_in):
            raise ramp_module.PackyError("simulated network error")

        monkeypatch.setattr(
            "pix.pixelize.ramp.PackyClient.post_json", fake_post_json, raising=True
        )

        params = PixelizeParams(output_size=(16, 16), colors=6, palette_mode="ramp", preview_scale=0)
        _, _, meta = pixelize(img_path, params, cfg=cfg, source_description="木箱")
        assert meta["ramp_info"]["source"] == "local_fallback"
        assert "simulated" in (meta["ramp_info"].get("vl_error") or "")
