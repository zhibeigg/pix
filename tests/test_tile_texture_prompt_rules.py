from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pix.asset import build_asset_prompt, resolve_tile_texture_kind
from pix.config import AssetConfig
from pix.pipeline import GridDesignInput, PipelineInput, PipelineResult
from pix.pixelize.core import PixelizeParams
from pix_web.models import GenerationJob
from pix_web.pipeline_adapter import _write_asset_meta
from pix_web.schemas import AssetParamsSchema


class TileTexturePromptRuleTests(unittest.TestCase):
    def test_explicit_wall_texture_injects_wall_rules(self) -> None:
        prompt = build_asset_prompt(
            AssetConfig().prompt_template,
            "青苔石墙",
            size=(32, 32),
            asset_kind="tile_texture",
            subject_kind="tileable_pattern",
            texture_kind="wall_surface",
            max_colors=12,
        )

        self.assertIn("Texture subtype: wall or rock surface", prompt)
        self.assertIn("vertical wall, cliff, cave", prompt)
        self.assertIn("do not show floor perspective", prompt)
        self.assertIn("NO transparent areas", prompt)
        self.assertIn("left edge must continue smoothly into the right edge", prompt)

    def test_explicit_water_texture_injects_liquid_rules(self) -> None:
        prompt = build_asset_prompt(
            "",
            "毒液水面",
            size=(32, 32),
            asset_kind="tile_texture",
            subject_kind="tileable_pattern",
            texture_kind="water_liquid",
            max_colors=10,
        )

        self.assertIn("Texture subtype: water or liquid surface", prompt)
        self.assertIn("animated-ready liquid surface base tile", prompt)
        self.assertIn("avoid shorelines", prompt)

    def test_auto_texture_kind_uses_keyword_inference(self) -> None:
        self.assertEqual(
            resolve_tile_texture_kind("auto", name="苔藓石板路面"),
            "path_floor",
        )
        self.assertEqual(
            resolve_tile_texture_kind("auto", name="科幻金属面板"),
            "metal_panel",
        )
        self.assertEqual(
            resolve_tile_texture_kind("auto", name="未知魔法材质"),
            "generic_texture",
        )

    def test_asset_schema_defaults_texture_kind_to_auto(self) -> None:
        params = AssetParamsSchema(asset_kind="tile_texture")

        self.assertEqual(params.subject_kind, "tileable_pattern")
        self.assertEqual(params.texture_kind, "auto")

    def test_asset_meta_records_requested_and_resolved_texture_kind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta_path = root / "meta.json"
            result = PipelineResult(
                run_dir=root,
                source_path=root / "01_source.png",
                analysis_path=None,
                analysis=None,
                pixel_path=root / "03_pixelized.png",
                preview_path=None,
                meta_path=meta_path,
                meta={},
                grid_path=None,
            )
            job = GenerationJob(
                job_type="asset",
                prompt="苔藓石板路面",
                params_json={
                    "asset": {
                        "name": "苔藓石板路面",
                        "asset_kind": "tile_texture",
                        "subject_kind": "tileable_pattern",
                        "texture_kind": "auto",
                    }
                },
            )
            inputs = PipelineInput(
                prompt="tile prompt",
                pixelize_params=PixelizeParams(output_size=(32, 32), colors=12),
                grid=GridDesignInput(mode="off"),
                skip_vl=True,
            )

            _write_asset_meta(result, job, inputs)

            asset_meta = json.loads(meta_path.read_text(encoding="utf-8"))["asset"]
            self.assertEqual(asset_meta["requested_texture_kind"], "auto")
            self.assertEqual(asset_meta["resolved_texture_kind"], "path_floor")


if __name__ == "__main__":
    unittest.main()
