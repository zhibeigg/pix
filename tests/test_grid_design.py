"""AI Pixel Grid 直绘测试（mock HTTP）。"""

from __future__ import annotations

import json

import httpx
from PIL import Image
import pytest

from pix.config import AppConfig
from pix.grid.design import design_pixel_grid
from pix.grid.schema import grid_from_mapping
from pix.grid.style_reference import find_style_references


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
    requests: list[dict] = []
    draft_grid = grid_from_mapping({
        "version": 1,
        "canvas": {"width": 4, "height": 4, "transparent_index": -1},
        "palette": [
            {"id": 0, "hex": "#201010", "role": "outline"},
            {"id": 1, "hex": "#B84830", "role": "primary"},
        ],
        "pixels": ["....", ".00.", ".11.", "...."],
        "metadata": {"draft_size_source": {"output_size": [4, 4], "detected_grid": 32}},
    })

    def _handler(req: httpx.Request) -> httpx.Response:
        requests.append(json.loads(req.content.decode("utf-8")))
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

    grid = design_pixel_grid(
        _cfg(),
        sample_image,
        output_size=(8, 8),
        max_colors=4,
        source_prompt="血气灵玉，RPG 材料，红色半透明宝石",
        draft_grid=draft_grid,
        retries=1,
    )

    first_content = requests[0]["messages"][0]["content"]
    first_text = first_content[0]["text"]
    assert "血气灵玉" in first_text
    assert "Python draft" in first_text
    assert "\"pixels\":[\"....\",\".00.\",\".11.\",\"....\"]" in first_text
    assert sum(1 for item in first_content if item["type"] == "image_url") == 2
    assert grid.metadata["generator"] == "ai_grid"
    assert grid.metadata["readability"]["ok"] is True
    assert grid.metadata["ai_grid"]["attempts"] == 2
    assert grid.metadata["ai_grid"]["max_attempts"] == 2
    assert grid.metadata["ai_grid"]["repaired"] is True
    assert grid.metadata["ai_grid"]["source_prompt_used"] is True
    assert grid.metadata["ai_grid"]["draft"]["canvas"] == [4, 4]
    assert not responses


def test_design_pixel_grid_sends_hand_drawn_style_references(
    sample_image,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference_dir = tmp_path / "icons"
    reference_dir.mkdir()
    Image.new("RGBA", (16, 16), (0, 0, 0, 0)).save(reference_dir / "其他.png")
    icon = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y in range(3, 13):
        for x in range(4, 12):
            icon.putpixel((x, y), (180, 30, 40, 255))
    icon.save(reference_dir / "血气灵玉.png")
    refs = find_style_references(reference_dir, query="血气灵玉", limit=1)
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
    requests: list[dict] = []

    def _handler(req: httpx.Request) -> httpx.Response:
        requests.append(json.loads(req.content.decode("utf-8")))
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(good_grid)}}]})

    transport = httpx.MockTransport(_handler)
    orig = httpx.Client

    class _ClientWithMock(orig):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("pix.api.packy_client.httpx.Client", _ClientWithMock)

    grid = design_pixel_grid(
        _cfg(),
        sample_image,
        output_size=(8, 8),
        max_colors=4,
        source_prompt="血气灵玉",
        style_references=refs,
    )

    first_content = requests[0]["messages"][0]["content"]
    first_text = first_content[0]["text"]
    assert "手绘参考" in first_text
    assert "血气灵玉.png" in first_text
    assert sum(1 for item in first_content if item["type"] == "image_url") == 2
    assert grid.metadata["ai_grid"]["style_references"] == ["血气灵玉.png"]
