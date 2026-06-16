from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from pix.config import AppConfig
from pix.pixelize.core import PixelizeParams, pixelize
from pix.pixelize.perfect_pixel import GeneratedPreprocessResult
from pix_web.pipeline_adapter import asset_pipeline_input_from_job, pipeline_input_from_job


class LocalPixelizePostprocessTests(unittest.TestCase):
    def test_ui_component_asset_defaults_image_size_to_auto(self) -> None:
        cfg = AppConfig()
        cfg.image_gen.size = "1024x1024"
        job = SimpleNamespace(
            id=77,
            job_type="asset",
            prompt="修仙副本队伍面板",
            input_image_path=None,
            params_json={
                "image_size": None,
                "image_quality": "low",
                "pixelize": {"output_size": [32, 32], "colors": 12},
                "asset": {
                    "name": "修仙副本队伍面板",
                    "asset_kind": "ui_component",
                    "subject_kind": "single_ui",
                },
                "grid": {"mode": "extract"},
            },
        )
        settings = SimpleNamespace(storage_root=Path("web_outputs"))

        inputs = asset_pipeline_input_from_job(job, settings, cfg)  # type: ignore[arg-type]

        self.assertEqual(inputs.image_size, "auto")

    def test_asset_reference_uses_asset_prompt_redraw_constraints(self) -> None:
        cfg = AppConfig()
        job = SimpleNamespace(
            id=88,
            job_type="asset",
            prompt="幻影斩技能书",
            input_image_path="/tmp/reference.png",
            params_json={
                "pixelize": {"output_size": [16, 16], "colors": 8},
                "asset": {
                    "name": "幻影斩技能书",
                    "extra_prompt": "蓝色幻影剑气",
                    "asset_kind": "item_icon",
                    "subject_kind": "single_prop",
                },
                "grid": {"mode": "extract"},
            },
        )
        settings = SimpleNamespace(storage_root=Path("web_outputs"))

        inputs = asset_pipeline_input_from_job(job, settings, cfg)  # type: ignore[arg-type]

        self.assertEqual(inputs.image_path, Path("/tmp/reference.png"))
        self.assertEqual(inputs.prompt_guard_text, "幻影斩技能书\n蓝色幻影剑气")
        self.assertIn("TRUE pixel-art game item icon", inputs.prompt or "")
        self.assertIn("First convert the reference", inputs.prompt or "")
        self.assertIn("Do not simply trace", inputs.prompt or "")
        self.assertIn("do not copy readable text", inputs.prompt or "")

    def test_local_pixelize_uses_generated_source_postprocess(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "local.png"
            Image.new("RGBA", (8, 8), (255, 0, 255, 255)).save(image_path)
            job = SimpleNamespace(
                id=42,
                job_type="local_pixelize",
                prompt=None,
                input_image_path=str(image_path),
                params_json={
                    "skip_vl": True,
                    "source_only": False,
                    "pixelize": {"output_size": [48, 48], "colors": 8},
                    "grid": {"mode": "off"},
                },
            )
            settings = SimpleNamespace(storage_root=Path(tmp))

            inputs = pipeline_input_from_job(job, settings)  # type: ignore[arg-type]

        self.assertTrue(inputs.input_is_generated_source)
        self.assertEqual(inputs.pixelize_params.output_size, (48, 48))

    def test_pixelize_can_preserve_perfect_pixel_detected_size(self) -> None:
        detected = Image.new("RGBA", (13, 17), (50, 40, 90, 255))
        params = PixelizeParams(
            output_size=(48, 48),
            colors=2,
            dither="none",
            resample="nearest",
            preview_scale=0,
            generated_preprocess_method="perfect_pixel",
        )

        with patch(
            "pix.pixelize.core.preprocess_generated_image",
            return_value=GeneratedPreprocessResult(
                image=detected,
                meta={
                    "method": "perfect_pixel",
                    "applied": True,
                    "output_size": [13, 17],
                    "refined_size": [13, 17],
                },
            ),
        ):
            out, preview, meta = pixelize(
                Image.new("RGBA", (64, 64), (255, 0, 255, 255)),
                params,
                generated_preprocess_method="perfect_pixel",
                preserve_preprocessed_size=True,
            )

        self.assertEqual(out.size, (13, 17))
        self.assertIsNone(preview)
        self.assertEqual(meta["effective_params"]["output_size"], [13, 17])
        self.assertEqual(meta["requested_output_size"], [48, 48])
        self.assertTrue(meta["preserve_preprocessed_size"])
        self.assertTrue(meta["adopted_preprocessed_size"])


if __name__ == "__main__":
    unittest.main()
