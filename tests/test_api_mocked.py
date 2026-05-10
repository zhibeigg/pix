"""PackyClient + image_gen + vision 用 mock transport 测试。"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import httpx
import pytest
from PIL import Image

from pix.api.image_gen import generate_image
from pix.api.packy_client import PackyClient, PackyError
from pix.api.vision import VisionParseError, analyze_image
from pix.config import AppConfig


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _cfg_with_keys() -> AppConfig:
    cfg = AppConfig()
    cfg.api.base_url = "https://packy.test"
    cfg.api.image_api_key = "sk-image"
    cfg.api.vl_api_key = "sk-vl"
    cfg.api.max_retries = 2
    cfg.api.timeout = 5.0
    cfg.vision.retry_on_parse = 1
    return cfg


def _patch_httpx_client(
    monkeypatch: pytest.MonkeyPatch, handler
) -> list[httpx.Request]:
    """把 httpx.Client 换成 MockTransport 版本，返回一个列表收集请求。"""
    captured: list[httpx.Request] = []

    def _handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return handler(req)

    transport = httpx.MockTransport(_handler)
    orig_client = httpx.Client

    class _ClientWithMock(orig_client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("pix.api.packy_client.httpx.Client", _ClientWithMock)
    monkeypatch.setattr("pix.io_utils.httpx.Client", _ClientWithMock)
    return captured


class TestPackyClient:
    def test_success_roundtrip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_httpx_client(
            monkeypatch,
            lambda req: httpx.Response(200, json={"ok": True}),
        )
        client = PackyClient("https://packy.test", "sk-x", timeout=2.0, max_retries=1)
        assert client.post_json("/v1/ping", {"q": 1}) == {"ok": True}

    def test_retries_on_500(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = {"n": 0}

        def handler(_req: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] < 2:
                return httpx.Response(500, text="err")
            return httpx.Response(200, json={"ok": True})

        _patch_httpx_client(monkeypatch, handler)
        # 为避免指数退避真的 sleep，monkeypatch time.sleep
        monkeypatch.setattr("pix.api.packy_client.time.sleep", lambda _s: None)
        client = PackyClient("https://packy.test", "sk", timeout=2.0, max_retries=3)
        assert client.post_json("/x", {}) == {"ok": True}
        assert calls["n"] == 2

    def test_no_retry_on_4xx(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = {"n": 0}

        def handler(_req: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(400, text="bad")

        _patch_httpx_client(monkeypatch, handler)
        monkeypatch.setattr("pix.api.packy_client.time.sleep", lambda _s: None)
        client = PackyClient("https://packy.test", "sk", timeout=2.0, max_retries=3)
        with pytest.raises(PackyError) as exc:
            client.post_json("/x", {})
        assert exc.value.status_code == 400
        assert calls["n"] == 1  # 不重试

    def test_non_json_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_httpx_client(
            monkeypatch, lambda req: httpx.Response(200, text="<html>")
        )
        monkeypatch.setattr("pix.api.packy_client.time.sleep", lambda _s: None)
        client = PackyClient("https://packy.test", "sk", timeout=2.0, max_retries=1)
        with pytest.raises(PackyError):
            client.post_json("/x", {})

    def test_bearer_header_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = _patch_httpx_client(
            monkeypatch, lambda req: httpx.Response(200, json={})
        )
        PackyClient("https://packy.test", "sk-abc", max_retries=1).post_json("/x", {})
        assert captured[0].headers.get("authorization") == "Bearer sk-abc"


class TestGenerateImage:
    def test_saves_png_from_url(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        png = _png_bytes()

        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.path == "/v1/images/generations":
                body = json.loads(req.content.decode())
                assert body["prompt"] == "a cat"
                assert body["model"] == "gpt-image-2"
                return httpx.Response(
                    200,
                    json={
                        "created": 1,
                        "data": [{"url": "https://cdn.packy.test/img.png"}],
                    },
                )
            if req.url.host == "cdn.packy.test":
                return httpx.Response(200, content=png)
            return httpx.Response(404, text="nope")

        _patch_httpx_client(monkeypatch, handler)
        dest = tmp_path / "out.png"
        cfg = _cfg_with_keys()
        generate_image(cfg, "a cat", dest)
        assert dest.read_bytes() == png

    def test_saves_png_from_b64(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        png = _png_bytes()
        b64 = base64.b64encode(png).decode("ascii")

        def handler(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": [{"b64_json": b64}]})

        _patch_httpx_client(monkeypatch, handler)
        dest = tmp_path / "out.png"
        cfg = _cfg_with_keys()
        generate_image(cfg, "b cat", dest)
        assert dest.read_bytes() == png

    def test_raises_when_response_has_neither(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_httpx_client(
            monkeypatch,
            lambda _req: httpx.Response(200, json={"data": [{}]}),
        )
        cfg = _cfg_with_keys()
        with pytest.raises(PackyError):
            generate_image(cfg, "x", tmp_path / "out.png")

    def test_validates_size_before_request(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cfg = _cfg_with_keys()
        with pytest.raises(ValueError):
            generate_image(cfg, "x", tmp_path / "out.png", size="100x100")


_JSON_ANALYSIS_OK = """```json
{
  "description": "x",
  "style": {"style_tags": ["a"], "recommended_preset": "auto",
            "target_color_count": 8, "suggested_dither": "ordered",
            "contrast_level": "mid"},
  "palette": [{"hex": "#FF00AA", "weight": 0.5, "role": "primary"}],
  "main_subjects": [],
  "semantic_regions": []
}
```"""


class TestAnalyzeImage:
    def test_parses_json_block(
        self, sample_image: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            body = json.loads(req.content.decode())
            assert body["messages"][0]["role"] == "user"
            # 用户消息应包含系统约束文本与 image_url
            user = body["messages"][0]
            assert any(isinstance(p, dict) and p.get("type") == "text" for p in user["content"])
            assert any(isinstance(p, dict) and p.get("type") == "image_url" for p in user["content"])
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": _JSON_ANALYSIS_OK}}
                    ]
                },
            )

        _patch_httpx_client(monkeypatch, handler)
        cfg = _cfg_with_keys()
        result = analyze_image(cfg, sample_image)
        assert result.description == "x"
        assert result.palette[0].hex == "#FF00AA"

    def test_retry_on_parse_failure(
        self, sample_image: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = {"n": 0}

        def handler(_req: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(200, json={
                    "choices": [{"message": {"content": "not a json at all"}}]
                })
            return httpx.Response(200, json={
                "choices": [{"message": {"content": _JSON_ANALYSIS_OK}}]
            })

        _patch_httpx_client(monkeypatch, handler)
        cfg = _cfg_with_keys()
        result = analyze_image(cfg, sample_image)
        assert calls["n"] == 2
        assert result.description == "x"

    def test_fails_after_retries(
        self, sample_image: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_httpx_client(
            monkeypatch,
            lambda _req: httpx.Response(200, json={
                "choices": [{"message": {"content": "garbage"}}]
            }),
        )
        cfg = _cfg_with_keys()
        cfg.vision.retry_on_parse = 1
        with pytest.raises(VisionParseError):
            analyze_image(cfg, sample_image)

    def test_accepts_structured_content_array(
        self, sample_image: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_httpx_client(
            monkeypatch,
            lambda _req: httpx.Response(200, json={
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": _JSON_ANALYSIS_OK}
                            ]
                        }
                    }
                ]
            }),
        )
        cfg = _cfg_with_keys()
        result = analyze_image(cfg, sample_image)
        assert result.description == "x"
