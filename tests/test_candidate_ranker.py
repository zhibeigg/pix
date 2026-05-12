from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from PIL import Image

from pix.api.candidate_ranker import CandidateRankingParseError, fallback_ranking, rank_candidates
from pix.config import AppConfig


def _cfg() -> AppConfig:
    cfg = AppConfig()
    cfg.api.base_url = "https://packy.test"
    cfg.api.vl_api_key = "sk-v"
    cfg.api.max_retries = 1
    cfg.api.timeout = 2.0
    return cfg


def _images(tmp_path: Path, count: int = 9) -> list[tuple[int, Path]]:
    items: list[tuple[int, Path]] = []
    for index in range(1, count + 1):
        path = tmp_path / f"candidate_{index:02d}.png"
        Image.new("RGBA", (12, 12), (index * 20 % 255, 0, 120, 255)).save(path)
        items.append((index, path))
    return items


def test_rank_candidates_sends_all_images_and_sorts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen = {"images": 0, "prompt": ""}

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content.decode("utf-8"))
        content = body["messages"][0]["content"]
        seen["images"] = sum(1 for item in content if item.get("type") == "image_url")
        seen["prompt"] = content[0]["text"]
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "selected_index": 7,
            "candidates": [
                {"index": 7, "rank": 1, "score": 95, "reason": "主体最好"},
                {"index": 3, "rank": 2, "score": 80, "reason": "清晰"},
                {"index": 1, "rank": 3, "score": 20, "reason": "一般"},
            ],
        }, ensure_ascii=False)}}]})

    transport = httpx.MockTransport(handler)
    orig = httpx.Client

    class _Patched(orig):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("pix.api.packy_client.httpx.Client", _Patched)
    monkeypatch.setattr("pix.api.packy_client.time.sleep", lambda _s: None)

    ranking = rank_candidates(_cfg(), _images(tmp_path), user_prompt="紫色水晶", target_size=(16, 16))

    assert seen["images"] == 9
    assert "紫色水晶" in seen["prompt"]
    assert ranking.selected_index == 7
    assert ranking.candidates[0].index == 7
    assert ranking.candidates[0].rank == 1
    assert len(ranking.candidates) == 9


def test_rank_candidates_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})

    transport = httpx.MockTransport(handler)
    orig = httpx.Client

    class _Patched(orig):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("pix.api.packy_client.httpx.Client", _Patched)
    monkeypatch.setattr("pix.api.packy_client.time.sleep", lambda _s: None)

    with pytest.raises(CandidateRankingParseError):
        rank_candidates(_cfg(), _images(tmp_path, count=2), user_prompt="水晶", target_size=(16, 16))


def test_fallback_ranking_keeps_original_order() -> None:
    ranking = fallback_ranking([1, 2, 3], model="vl", error="boom")

    assert ranking.mode == "fallback"
    assert ranking.selected_index == 1
    assert [item.index for item in ranking.candidates] == [1, 2, 3]
