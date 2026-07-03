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
        # 默认 character_views="single"：保持单张角色参考语义不变。
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
        # 单图模式不应出现三视图措辞。
        self.assertNotIn("FRONT view", prompt)

    def test_character_three_view_prompt_describes_front_side_back(self) -> None:
        # 三视图模式：宽度已由调用方 ×3（192 = 64*3），prompt 需明确正/侧/背与列宽。
        prompt = build_asset_prompt(
            "",
            "蓝袍骑士",
            size=(192, 64),
            asset_kind="character",
            subject_kind="single_character",
            character_views="three_view",
            max_colors=32,
        )
        self.assertIn("FRONT view", prompt)
        self.assertIn("SIDE view", prompt)
        self.assertIn("BACK view", prompt)
        self.assertIn("TURNAROUND SHEET", prompt)
        self.assertIn("192x64", prompt)
        self.assertIn("64x64 pixels each", prompt)
        # 三视图仍需保留纯色背景 chroma-key 与像素网格约束。
        for needle in ANTI_PATTERNS:
            self.assertIn(needle, prompt, f"three-view prompt missing: {needle}")

    def test_three_view_flag_ignored_for_non_character_asset(self) -> None:
        # 非角色类型即便误带 character_views，也不应触发三视图 prompt。
        prompt = build_asset_prompt(
            "",
            "蓝色魔法剑",
            size=(64, 64),
            asset_kind="item_icon",
            subject_kind="single_prop",
            character_views="three_view",
            max_colors=8,
        )
        self.assertNotIn("FRONT view", prompt)
        self.assertNotIn("TURNAROUND SHEET", prompt)


if __name__ == "__main__":
    unittest.main()
