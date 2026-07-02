from __future__ import annotations

import unittest

from pix.asset import build_asset_prompt
from pix.config import AssetConfig

# Gemini 把背景画成渐变/方格纸的根因是 prompt 缺这些显式约束，必须保证两条路径都带上。
ANTI_PATTERNS = [
    "NO gradient",
    "NO vignette",
    "do NOT draw any visible grid lines",
    "edge to edge",
]


class AssetPromptBackgroundTests(unittest.TestCase):
    def test_default_template_forbids_gradient_and_grid_lines(self) -> None:
        prompt = build_asset_prompt(
            AssetConfig().prompt_template,
            "蓝色魔法剑",
            size=(64, 64),
            asset_kind="item_icon",
            subject_kind="single_prop",
            max_colors=8,
        )
        for needle in ANTI_PATTERNS:
            self.assertIn(needle, prompt, f"default template missing: {needle}")

    def test_canonical_fallback_forbids_gradient_and_grid_lines(self) -> None:
        # 空模板会回退到 _canonical_asset_prompt，必须同样硬约束。
        prompt = build_asset_prompt(
            "",
            "蓝色魔法剑",
            size=(64, 64),
            asset_kind="item_icon",
            subject_kind="single_prop",
            max_colors=8,
        )
        for needle in ANTI_PATTERNS:
            self.assertIn(needle, prompt, f"canonical fallback missing: {needle}")

    def test_character_asset_prompt_is_reusable_single_character_reference(self) -> None:
        prompt = build_asset_prompt(
            "",
            "蓝袍骑士",
            size=(64, 64),
            asset_kind="character",
            subject_kind="single_prop",
            max_colors=32,
        )
        self.assertIn("character reference", prompt)
        self.assertIn("single character", prompt)
        self.assertIn("full character readable", prompt)
        self.assertIn("no multiple characters", prompt)


if __name__ == "__main__":
    unittest.main()
