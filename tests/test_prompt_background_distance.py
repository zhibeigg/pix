from __future__ import annotations

import unittest

from pix.asset import build_asset_prompt
from pix.config import AppConfig, AssetConfig, ImageGenConfig, SpriteConfig
from pix.contact_sheet import _fallback_prompt, build_sample_prompt
from pix.sprite_mosaic import _fallback_mosaic_prompt, build_mosaic_prompt

# 1.92.3 修复：所有生图模板的背景色约束从「距离 > tolerance」弱约束升级为
# maximin（最大化与所有主体色的最小 RGB 距离）+ 目标 ≥150 + 互补/对立高饱和色相。
# 锁住这些措辞，防止任何模板回退到旧的弱约束导致背景与主体撞色。
MAXIMIN_NEEDLES = (
    "MAXIMIZES the MINIMUM RGB Euclidean distance",
    "150 RGB Euclidean distance",
    "complementary",
)

# 共享 values，覆盖候选/序列帧模板所需的全部占位符。
CANDIDATE_VALUES = dict(
    rows=3,
    cols=3,
    count=9,
    description="蓝色魔法剑",
    width=64,
    height=64,
    green="#FF00FF",
    key_tolerance=48,
    max_colors=8,
    render_width=1024,
    render_height=1024,
    cell_render_width=341,
    cell_render_height=341,
    frame_width=64,
    frame_height=64,
    upscale=5,
    cell_art_width=68,
    cell_art_height=68,
    anchor_text="bottom center",
    row_block="Row 1: walk cycle",
)


class PromptBackgroundDistanceTests(unittest.TestCase):
    def _assert_maximin(self, prompt: str, *, context: str) -> None:
        for needle in MAXIMIN_NEEDLES:
            self.assertIn(needle, prompt, f"{context} 缺少 maximin 约束: {needle}")
        # 不能再保留旧的弱约束措辞。
        self.assertNotIn("is not close to any visible subject color", prompt, context)
        self.assertNotIn("outside the maximum key-color tolerance", prompt, context)

    def test_asset_default_template_maximin(self) -> None:
        prompt = build_asset_prompt(
            AssetConfig().prompt_template,
            "蓝色魔法剑",
            size=(64, 64),
            asset_kind="item_icon",
            subject_kind="single_prop",
            max_colors=8,
        )
        self._assert_maximin(prompt, context="asset 默认模板")

    def test_asset_canonical_fallback_maximin(self) -> None:
        # 空模板会回退到 _canonical_asset_prompt。
        prompt = build_asset_prompt(
            "",
            "蓝色魔法剑",
            size=(64, 64),
            asset_kind="item_icon",
            subject_kind="single_prop",
            max_colors=8,
        )
        self._assert_maximin(prompt, context="asset canonical fallback")

    def test_contact_sheet_template_maximin(self) -> None:
        out = ImageGenConfig().contact_sheet_prompt_template.format(**CANDIDATE_VALUES)
        self._assert_maximin(out, context="contact_sheet 模板")

    def test_n_sample_template_maximin(self) -> None:
        out = ImageGenConfig().n_sample_prompt_template.format(**CANDIDATE_VALUES)
        self._assert_maximin(out, context="n_sample 模板")

    def test_mosaic_template_maximin(self) -> None:
        out = SpriteConfig().mosaic_prompt_template.format(**CANDIDATE_VALUES)
        self._assert_maximin(out, context="mosaic 模板")

    def test_contact_sheet_fallback_maximin(self) -> None:
        out = _fallback_prompt(**CANDIDATE_VALUES)
        self._assert_maximin(out, context="contact_sheet fallback")

    def test_mosaic_fallback_maximin(self) -> None:
        out = _fallback_mosaic_prompt(**CANDIDATE_VALUES)
        self._assert_maximin(out, context="mosaic fallback")

    def test_sample_prompt_builder_maximin(self) -> None:
        cfg = AppConfig()
        out = build_sample_prompt(cfg, "蓝色魔法剑", target_size=(64, 64))
        self._assert_maximin(out, context="build_sample_prompt")

    def test_mosaic_prompt_builder_maximin(self) -> None:
        cfg = AppConfig()
        out = build_mosaic_prompt(
            cfg,
            "聂小倩",
            rows=1,
            cols=8,
            row_prompts=["待机动作"],
            sheet_pixel_size=(512, 64),
            frame_pixel_size=(64, 64),
            api_size_pixel=(3072, 1024),
            anchor="bottom_center",
            key_color="#FF00FF",
            key_tolerance=48,
            max_colors=24,
            use_reference=False,
        )
        self._assert_maximin(out, context="build_mosaic_prompt")


if __name__ == "__main__":
    unittest.main()
