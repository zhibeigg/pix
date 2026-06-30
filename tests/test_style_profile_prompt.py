from __future__ import annotations

import unittest

from fastapi import HTTPException

from pix.asset import build_asset_prompt
from pix.config import AppConfig, AssetConfig
from pix.prompt_style import compile_style_profile
from pix.sprite_mosaic import build_mosaic_prompt
from pix_web.jobs import params_json_from_request
from pix_web.prompt_preview import build_prompt_preview
from pix_web.schemas import AssetParamsSchema, JobCreateRequest, PixelizeParamsSchema, SpriteParamsSchema, StyleProfileSchema


STYLE = {
    "project_name": "Crystal Dungeon",
    "palette": "cyan, violet, deep navy",
    "line_style": "thin bright outline",
    "lighting": "soft rim light",
    "view_rule": "strict front-facing sprites",
    "avoid_elements": "modern weapons",
}


class StyleProfilePromptTests(unittest.TestCase):
    def test_compile_style_profile_skips_empty_fields(self) -> None:
        compiled = compile_style_profile({"palette": " cyan ", "lighting": ""})

        self.assertIn("Color palette: cyan.", compiled.prompt)
        self.assertEqual(compiled.applied_rules, ["配色方案：cyan"])
        self.assertEqual(compiled.data, {"palette": "cyan"})

    def test_asset_prompt_injects_style_before_extra_prompt(self) -> None:
        prompt = build_asset_prompt(
            AssetConfig().prompt_template,
            "冰霜之心",
            size=(32, 32),
            extra_prompt="extra sparkle note",
            asset_kind="item_icon",
            subject_kind="single_prop",
            style_profile=STYLE,
        )

        self.assertIn("Project style constraints", prompt)
        self.assertIn("Color palette: cyan, violet, deep navy.", prompt)
        self.assertIn("Do not include: modern weapons.", prompt)
        self.assertLess(prompt.index("Project style constraints"), prompt.index("extra sparkle note"))
        self.assertIn("TRUE pixel-art", prompt)

    def test_tile_prompt_keeps_seam_rules_with_style_profile(self) -> None:
        prompt = build_asset_prompt(
            AssetConfig().prompt_template,
            "苔藓石墙",
            size=(32, 32),
            asset_kind="tile_texture",
            subject_kind="tileable_pattern",
            texture_kind="wall_surface",
            style_profile=STYLE,
        )

        self.assertIn("left edge must continue smoothly into the right edge", prompt)
        self.assertIn("Project style constraints", prompt)
        self.assertIn("Do not include: modern weapons.", prompt)

    def test_sprite_mosaic_prompt_injects_style_without_losing_geometry(self) -> None:
        prompt = build_mosaic_prompt(
            AppConfig(),
            "火焰法师",
            rows=1,
            cols=8,
            row_prompts=["挥杖施法"],
            sheet_pixel_size=(512, 64),
            frame_pixel_size=(64, 64),
            api_size_pixel=(3072, 1024),
            anchor="bottom_center",
            key_color="#00FF00",
            key_tolerance=48,
            max_colors=16,
            use_reference=False,
            style_profile=STYLE,
        )

        self.assertIn("384x1024", prompt)
        self.assertIn("Project style constraints", prompt)
        self.assertIn("Color palette: cyan, violet, deep navy.", prompt)
        self.assertIn("grid lines", prompt)

    def test_params_json_saves_style_profile(self) -> None:
        req = JobCreateRequest(
            job_type="asset",
            asset=AssetParamsSchema(name="冰霜之心"),
            style_profile=StyleProfileSchema(**STYLE),
        )

        data = params_json_from_request(req)

        self.assertEqual(data["style_profile"]["project_name"], "Crystal Dungeon")
        self.assertEqual(data["style_profile"]["avoid_elements"], "modern weapons")

    def test_prompt_preview_asset_uses_backend_prompt_builder(self) -> None:
        req = JobCreateRequest(
            job_type="asset",
            asset=AssetParamsSchema(name="冰霜之心", asset_kind="item_icon"),
            pixelize=PixelizeParamsSchema(output_size=(32, 32), colors=12),
            style_profile=StyleProfileSchema(**STYLE),
        )

        preview = build_prompt_preview(req, AppConfig())

        self.assertEqual(preview.mode, "asset")
        self.assertIn("TRUE pixel-art", preview.positive_prompt)
        self.assertIn("Project style constraints", preview.positive_prompt)
        self.assertIn("避免元素：modern weapons", preview.applied_style_profile)

    def test_prompt_preview_dual_grid_returns_material_prompts(self) -> None:
        req = JobCreateRequest(
            job_type="asset",
            asset=AssetParamsSchema(
                name="草地泥土过渡",
                asset_kind="dual_grid",
                material_a="草地",
                material_b="泥土",
            ),
            pixelize=PixelizeParamsSchema(output_size=(32, 32), colors=12),
            style_profile=StyleProfileSchema(**STYLE),
        )

        preview = build_prompt_preview(req, AppConfig())

        self.assertEqual(preview.mode, "dual_grid")
        self.assertIn("Material A prompt", preview.positive_prompt)
        self.assertIn("Material B prompt", preview.positive_prompt)
        self.assertIn("Project style constraints", preview.positive_prompt)

    def test_prompt_preview_local_mode_has_no_prompt(self) -> None:
        req = JobCreateRequest(job_type="local_pixelize")

        with self.assertRaises(HTTPException) as ctx:
            build_prompt_preview(req, AppConfig())

        self.assertEqual(ctx.exception.status_code, 422)

    def test_prompt_preview_sprite_uses_mosaic_builder(self) -> None:
        req = JobCreateRequest(
            job_type="sprite_sheet",
            prompt="火焰法师",
            sprite=SpriteParamsSchema(rows=1, cols=8, row_prompts=["挥杖施法"]),
            pixelize=PixelizeParamsSchema(output_size=(64, 64), colors=16),
            style_profile=StyleProfileSchema(**STYLE),
        )

        preview = build_prompt_preview(req, AppConfig())

        self.assertEqual(preview.mode, "sprite_sheet")
        self.assertIn("Project style constraints", preview.positive_prompt)
        self.assertIn("火焰法师", preview.positive_prompt)
        self.assertIn("配色方案：cyan, violet, deep navy", preview.applied_style_profile)


if __name__ == "__main__":
    unittest.main()
