"""Pixel Grid AI review 测试（mock HTTP）。"""

from __future__ import annotations


import httpx
import pytest

from pix.config import AppConfig
from pix.grid.review import review_pixel_grid
from pix.grid.schema import grid_from_mapping


def _cfg() -> AppConfig:
    cfg = AppConfig()
    cfg.api.base_url = "https://packy.test"
    cfg.api.vl_api_key = "sk-vl"
    cfg.api.max_retries = 1
    cfg.api.timeout = 2.0
    return cfg


def test_review_pixel_grid_parses_returned_json(monkeypatch: pytest.MonkeyPatch) -> None:
    grid = grid_from_mapping({
        "canvas": {"width": 2, "height": 2, "transparent_index": -1},
        "palette": [{"id": 0, "hex": "#FF0000", "role": "primary"}],
        "pixels": [[-1, 0], [0, -1]],
    })
    reviewed_json = grid.model_copy(update={"metadata": {"reviewed": True}}).to_json_text()

    transport = httpx.MockTransport(
        lambda _req: httpx.Response(
            200,
            json={"choices": [{"message": {"content": f"```json\n{reviewed_json}\n```"}}]},
        )
    )
    orig = httpx.Client

    class _ClientWithMock(orig):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("pix.api.packy_client.httpx.Client", _ClientWithMock)

    reviewed = review_pixel_grid(_cfg(), grid)

    assert reviewed.metadata["reviewed"] is True
