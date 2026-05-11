"""AI Pixel Grid 直绘测试（mock HTTP）。"""

from __future__ import annotations

import json

import httpx
import pytest

from pix.config import AppConfig
from pix.grid.design import design_pixel_grid


def _cfg() -> AppConfig:
    cfg = AppConfig()
    cfg.api.base_url = "https://packy.test"
    cfg.api.vl_api_key = "sk-vl"
    cfg.api.max_retries = 1
    cfg.api.timeout = 2.0
    cfg.vision.max_tokens = 1024
    return cfg


def test_design_pixel_grid_repairs_until_readable(sample_image, monkeypatch: pytest.MonkeyPatch) -> None:
    bad_grid = {
        "version": 1,
        "canvas": {"width": 8, "height": 8, "transparent_index": -1},
        "palette": [{"id": 0, "hex": "#FF0000", "role": "primary"}],
        "pixels": [
            "........",
            "........",
            "........",
            "...0....",
            "........",
            "........",
            "........",
            "........",
        ],
        "metadata": {"primary_read": "过小红点"},
    }
    good_grid = {
        "version": 1,
        "canvas": {"width": 8, "height": 8, "transparent_index": -1},
        "palette": [
            {"id": 0, "hex": "#201010", "role": "outline"},
            {"id": 1, "hex": "#B84830", "role": "primary"},
            {"id": 2, "hex": "#F0B060", "role": "highlight"},
        ],
        "pixels": [
            "........",
            "..0000..",
            ".011110.",
            ".011210.",
            ".011110.",
            "..0000..",
            "........",
            "........",
        ],
        "metadata": {"primary_read": "清晰宝石"},
    }
    responses = [bad_grid, good_grid]

    def _handler(_req: httpx.Request) -> httpx.Response:
        payload = responses.pop(0)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        )

    transport = httpx.MockTransport(_handler)
    orig = httpx.Client

    class _ClientWithMock(orig):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("pix.api.packy_client.httpx.Client", _ClientWithMock)

    grid = design_pixel_grid(_cfg(), sample_image, output_size=(8, 8), max_colors=4, retries=1)

    assert grid.metadata["generator"] == "ai_grid"
    assert grid.metadata["readability"]["ok"] is True
    assert grid.metadata["ai_grid"] == {"attempts": 2, "max_attempts": 2, "repaired": True}
    assert not responses
