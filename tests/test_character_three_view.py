"""角色三视图（正/侧/背横向拼合图）相关逻辑测试。

覆盖三层：
1. schema 默认值与归一（AssetParamsSchema.character_views）。
2. 后端尺寸换算（asset_pixelize_params_from_json 把角色三视图 output_size 横向 ×3，
   并强制关闭 auto_crop / crop_square）。
3. prompt 组装（build_asset_prompt 三视图分支）。
"""

from __future__ import annotations

import unittest

from pix.asset import build_asset_prompt
from pix.config import AppConfig
from pix_web.pipeline_adapter import (
    _apply_character_three_view_size,
    _character_views_mode,
    asset_pixelize_params_from_json,
)
from pix_web.schemas import AssetParamsSchema


class CharacterViewsSchemaTests(unittest.TestCase):
    def test_default_is_three_view_for_character(self) -> None:
        self.assertEqual(AssetParamsSchema(asset_kind="character").character_views, "three_view")

    def test_explicit_single_is_kept_for_character(self) -> None:
        params = AssetParamsSchema(asset_kind="character", character_views="single")
        self.assertEqual(params.character_views, "single")

    def test_non_character_falls_back_to_single(self) -> None:
        for kind in ("item_icon", "ui_component", "tile_texture", "game_logo", "dual_grid"):
            params = AssetParamsSchema(asset_kind=kind, character_views="three_view")
            self.assertEqual(params.character_views, "single", kind)


class CharacterThreeViewSizeTests(unittest.TestCase):
    def _data(self, kind: str, views: str) -> dict:
        return {
            "asset": {"asset_kind": kind, "character_views": views},
            "pixelize": {"output_size": [64, 64]},
            "output_size": [64, 64],
        }

    def test_views_mode_only_active_for_character(self) -> None:
        self.assertEqual(_character_views_mode(self._data("character", "three_view")), "three_view")
        self.assertEqual(_character_views_mode(self._data("character", "single")), "single")
        self.assertEqual(_character_views_mode(self._data("item_icon", "three_view")), "single")

    def test_apply_size_triples_width_for_three_view(self) -> None:
        self.assertEqual(
            _apply_character_three_view_size((64, 64), self._data("character", "three_view")),
            (192, 64),
        )
        self.assertEqual(
            _apply_character_three_view_size((48, 96), self._data("character", "three_view")),
            (144, 96),
        )

    def test_apply_size_unchanged_for_single_or_non_character(self) -> None:
        self.assertEqual(
            _apply_character_three_view_size((64, 64), self._data("character", "single")),
            (64, 64),
        )
        self.assertEqual(
            _apply_character_three_view_size((64, 64), self._data("item_icon", "three_view")),
            (64, 64),
        )

    def test_pixelize_params_triples_width_and_disables_crop(self) -> None:
        cfg = AppConfig()
        params = asset_pixelize_params_from_json(self._data("character", "three_view"), cfg)
        self.assertEqual(params.output_size, (192, 64))
        # 三视图必须保留三列并排：强制关闭自动裁剪 / 方形裁剪。
        self.assertFalse(params.auto_crop)
        self.assertFalse(params.crop_square)

    def test_pixelize_params_single_view_keeps_original_size(self) -> None:
        cfg = AppConfig()
        params = asset_pixelize_params_from_json(self._data("character", "single"), cfg)
        self.assertEqual(params.output_size, (64, 64))


class CharacterThreeViewPromptTests(unittest.TestCase):
    def test_prompt_mentions_three_views_and_per_view_width(self) -> None:
        prompt = build_asset_prompt(
            "",
            "红发法师",
            size=(192, 64),
            asset_kind="character",
            subject_kind="single_character",
            character_views="three_view",
            max_colors=32,
        )
        self.assertIn("FRONT view", prompt)
        self.assertIn("SIDE view", prompt)
        self.assertIn("BACK view", prompt)
        self.assertIn("64x64 pixels each", prompt)
        self.assertIn("same character", prompt.lower())

    def test_single_view_prompt_has_no_turnaround(self) -> None:
        prompt = build_asset_prompt(
            "",
            "红发法师",
            size=(64, 64),
            asset_kind="character",
            subject_kind="single_character",
            character_views="single",
            max_colors=32,
        )
        self.assertNotIn("TURNAROUND SHEET", prompt)
        self.assertNotIn("FRONT view", prompt)


if __name__ == "__main__":
    unittest.main()
