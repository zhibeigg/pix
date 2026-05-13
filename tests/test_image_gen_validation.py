"""image_gen.validate_size 边界测试。"""

from __future__ import annotations

import io
from pathlib import Path

import httpx
import pytest
from PIL import Image

from pix.api.image_gen import generate_images_batch, validate_size
from pix.config import AppConfig


class TestValidateSize:
    @pytest.mark.parametrize(
        "size",
        [
            "1024x1024",
            "1536x1024",
            "1024x1536",
            "2048x2048",
            "2048x1152",
            "3840x2160",
            "2160x3840",
            "auto",
        ],
    )
    def test_accepts_common_sizes(self, size: str) -> None:
        validate_size(size)  # 不抛异常即通过

    @pytest.mark.parametrize(
        "size, reason",
        [
            ("1x1", "16"),           # 不是 16 的倍数
            ("1024x1023", "16"),     # 高度不是 16 的倍数
            ("4000x4000", "3840"),   # 超最大边
            ("3840x3840", "8294"),   # 总像素超上限
            ("16x16", "655"),        # 总像素少于下限
            ("3840x1024", "比例"),    # ratio > 3
            ("1024x300", "16"),      # 格式匹配但 300 不是 16 倍数
            ("abc", "格式"),          # 不合法字符串
            ("1024", "格式"),         # 缺少 x
            ("1024x1024x1024", "格式"),
        ],
    )
    def test_rejects(self, size: str, reason: str) -> None:
        with pytest.raises(ValueError) as exc:
            validate_size(size)
        assert reason in str(exc.value) or "格式" in str(exc.value)


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (200, 100, 50)).save(buf, format="PNG")
    return buf.getvalue()


class TestGenerateImagesBatch:
    def test_returns_n_paths_when_provider_returns_n(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        png = _png_bytes()
        gen_calls = {"n": 0, "requested_n": []}

        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.path == "/v1/images/generations":
                import json

                body = json.loads(req.content.decode("utf-8"))
                gen_calls["requested_n"].append(int(body.get("n", 1)))
                gen_calls["n"] += 1
                # 假设 provider 一次性返回 n 张
                n = int(body.get("n", 1))
                return httpx.Response(
                    200,
                    json={"data": [{"url": f"https://cdn.test/{i}.png"} for i in range(n)]},
                )
            if req.url.host == "cdn.test":
                return httpx.Response(200, content=png)
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        orig = httpx.Client

        class _Patched(orig):
            def __init__(self, *args, **kwargs):
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        monkeypatch.setattr("pix.api.packy_client.httpx.Client", _Patched)
        monkeypatch.setattr("pix.io_utils.httpx.Client", _Patched)
        monkeypatch.setattr("pix.api.packy_client.time.sleep", lambda _s: None)

        cfg = AppConfig()
        cfg.api.base_url = "https://packy.test"
        cfg.api.image_api_key = "sk-i"
        cfg.api.max_retries = 1
        cfg.api.timeout = 2.0

        paths = generate_images_batch(
            cfg,
            "a sword",
            tmp_path / "samples",
            n=4,
        )
        assert len(paths) == 4
        for p in paths:
            assert p.exists()
            assert p.read_bytes() == png
        assert gen_calls["n"] == 1  # 一次 batch 调用即可
        assert gen_calls["requested_n"] == [4]

    def test_falls_back_to_single_calls_when_response_short(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        png = _png_bytes()
        gen_calls = {"requested_n": []}

        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.path == "/v1/images/generations":
                import json

                body = json.loads(req.content.decode("utf-8"))
                gen_calls["requested_n"].append(int(body.get("n", 1)))
                # provider 仅返回 1 张
                return httpx.Response(200, json={"data": [{"url": "https://cdn.test/x.png"}]})
            if req.url.host == "cdn.test":
                return httpx.Response(200, content=png)
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        orig = httpx.Client

        class _Patched(orig):
            def __init__(self, *args, **kwargs):
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        monkeypatch.setattr("pix.api.packy_client.httpx.Client", _Patched)
        monkeypatch.setattr("pix.io_utils.httpx.Client", _Patched)
        monkeypatch.setattr("pix.api.packy_client.time.sleep", lambda _s: None)

        cfg = AppConfig()
        cfg.api.base_url = "https://packy.test"
        cfg.api.image_api_key = "sk-i"
        cfg.api.max_retries = 1
        cfg.api.timeout = 2.0

        paths = generate_images_batch(
            cfg,
            "a shield",
            tmp_path / "samples",
            n=3,
            prompt_variations=["v1", "v2"],
        )
        assert len(paths) == 3
        # 第一次 n=3，后续 fallback 是 n=1（×2）
        assert gen_calls["requested_n"][0] == 3
        assert gen_calls["requested_n"][1:] == [1, 1]
