from __future__ import annotations

import json

import numpy as np
from PIL import Image

from pix.config import AppConfig
from pix_web.config import WebSettings
from pix_web.models import GenerationJob
from pix_web.pipeline_adapter import run_local_bg_remove_job_pipeline


def test_local_bg_remove_pipeline_uses_color_to_alpha(tmp_path) -> None:
    input_path = tmp_path / "input.png"
    image = Image.new("RGBA", (5, 5), (255, 255, 255, 255))
    image.putpixel((1, 2), (220, 220, 220, 255))
    image.putpixel((2, 2), (0, 0, 0, 255))
    image.save(input_path)

    job = GenerationJob(
        id=7001,
        user_id=1,
        job_type="local_bg_remove",
        status="running",
        input_image_path=str(input_path),
        params_json={
            "pixelize": {
                "output_size": [128, 128],
                "colors": 16,
                "remove_bg": True,
                "bg_tolerance": 12,
                "bg_feather": 0,
                "edge_style": "hard",
                "bg_removal_algorithm": "color_to_alpha",
            }
        },
    )
    settings = WebSettings(storage_root=tmp_path / "web_outputs")

    result = run_local_bg_remove_job_pipeline(job, settings, AppConfig())
    alpha = np.asarray(Image.open(result.pixel_path).convert("RGBA"))[..., 3]
    meta = json.loads(result.meta_path.read_text(encoding="utf-8"))

    assert int(alpha[0, 0]) == 0
    assert 0 < int(alpha[2, 1]) < 255
    assert int(alpha[2, 2]) == 255
    assert meta["image_gen"]["used"] is False
    assert meta["pixelize"]["mode"] == "local_bg_remove"
    assert meta["pixelize"]["bg_removal_algorithm"] == "color_to_alpha"
