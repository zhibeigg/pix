from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from pix.pixelize.core import PixelizeParams, pixelize
from pix.pixelize.perfect_pixel import GeneratedPreprocessResult
from pix_web.pipeline_adapter import pipeline_input_from_job


class LocalPixelizePostprocessTests(unittest.TestCase):
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
