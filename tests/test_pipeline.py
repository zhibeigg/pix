"""Pipeline 编排测试（mock API）。"""

from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
import pytest
from PIL import Image

from pix.analysis.schema import PixAnalysis
from pix.config import AppConfig
from pix.pipeline import PipelineInput, run_pipeline
from pix.pixelize.core import PixelizeParams


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (100, 100, 100)).save(buf, format="PNG")
    return buf.getvalue()


_ANALYSIS_BLOCK = """```json
{
  "description": "mock",
  "style": {"style_tags": ["a"], "recommended_preset": "auto",
            "target_color_count": 8, "suggested_dither": "floyd_steinberg",
            "contrast_level": "mid"},
  "palette": [{"hex": "#112233", "weight": 1.0, "role": "primary"}],
  "main_subjects": [],
  "semantic_regions": []
}
```"""


def _cfg(tmp_path: Path) -> AppConfig:
    cfg = AppConfig()
    cfg.api.base_url = "https://packy.test"
    cfg.api.image_api_key = "sk-i"
    cfg.api.vl_api_key = "sk-v"
    cfg.api.max_retries = 1
    cfg.api.timeout = 2.0
    cfg.cache.dir = str(tmp_path / "cache")
    cfg.output.root = str(tmp_path / "outs")
    return cfg


def _install_mock(monkeypatch: pytest.MonkeyPatch, handler):
    transport = httpx.MockTransport(handler)
    orig = httpx.Client

    class _Patched(orig):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("pix.api.packy_client.httpx.Client", _Patched)
    monkeypatch.setattr("pix.io_utils.httpx.Client", _Patched)
    monkeypatch.setattr("pix.api.packy_client.time.sleep", lambda _s: None)


def test_pipeline_from_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_analysis_dict: dict
) -> None:
    png = _png_bytes()
    gen_calls = {"n": 0}
    vl_calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path == "/v1/images/generations":
            gen_calls["n"] += 1
            return httpx.Response(
                200,
                json={"data": [{"url": "https://cdn.test/img.png"}]},
            )
        if req.url.host == "cdn.test":
            return httpx.Response(200, content=png)
        if path == "/v1/chat/completions":
            vl_calls["n"] += 1
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": _ANALYSIS_BLOCK}}]},
            )
        return httpx.Response(404)

    _install_mock(monkeypatch, handler)
    cfg = _cfg(tmp_path)
    inputs = PipelineInput(
        prompt="a cat",
        pixelize_params=PixelizeParams(output_size=(16, 16), colors=4, preview_scale=2),
        use_cache=True,
    )
    events: list[str] = []
    result = run_pipeline(cfg, inputs, progress=lambda s, _p: events.append(s))

    assert gen_calls["n"] == 1
    assert vl_calls["n"] == 1
    assert result.source_path.exists()
    assert result.analysis is not None
    assert result.analysis.description == "mock"
    assert result.pixel_path.exists()
    assert result.preview_path is not None and result.preview_path.exists()
    assert result.meta["vision"]["ok"] is True
    assert "source_ready" in events
    assert "analysis_ready" in events
    assert "pixelize_ready" in events

    # 再跑一次应命中缓存：网络不再被调
    result2 = run_pipeline(cfg, inputs)
    assert gen_calls["n"] == 1  # 没变
    assert vl_calls["n"] == 1
    assert result2.analysis is not None


def test_pipeline_skip_vl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    png = _png_bytes()
    vl_calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/v1/images/generations":
            return httpx.Response(200, json={"data": [{"url": "https://cdn.test/a.png"}]})
        if req.url.host == "cdn.test":
            return httpx.Response(200, content=png)
        if req.url.path == "/v1/chat/completions":
            vl_calls["n"] += 1
            return httpx.Response(500, text="should not be called")
        return httpx.Response(404)

    _install_mock(monkeypatch, handler)
    cfg = _cfg(tmp_path)
    inputs = PipelineInput(
        prompt="a cat",
        pixelize_params=PixelizeParams(output_size=(16, 16), colors=4, preview_scale=0),
        skip_vl=True,
        use_cache=False,
    )
    result = run_pipeline(cfg, inputs)
    assert vl_calls["n"] == 0
    assert result.analysis is None
    assert result.analysis_path is None
    assert result.pixel_path.exists()


def test_pipeline_from_image(tmp_path: Path, sample_image: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vl_calls = {"n": 0}
    gen_calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/v1/images/generations":
            gen_calls["n"] += 1
            return httpx.Response(500, text="should not be called")
        if req.url.path == "/v1/chat/completions":
            vl_calls["n"] += 1
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": _ANALYSIS_BLOCK}}]},
            )
        return httpx.Response(404)

    _install_mock(monkeypatch, handler)
    cfg = _cfg(tmp_path)
    inputs = PipelineInput(
        image_path=sample_image,
        pixelize_params=PixelizeParams(output_size=(16, 16), colors=4, preview_scale=0),
        use_cache=False,
    )
    result = run_pipeline(cfg, inputs)
    assert gen_calls["n"] == 0  # 不应调用生图
    assert vl_calls["n"] == 1
    assert result.pixel_path.exists()
    assert result.analysis is not None


def test_pipeline_requires_input(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    with pytest.raises(ValueError):
        run_pipeline(cfg, PipelineInput())


def test_pipeline_vl_failure_falls_back(
    tmp_path: Path, sample_image: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/v1/chat/completions":
            return httpx.Response(200, json={
                "choices": [{"message": {"content": "not a json"}}]
            })
        return httpx.Response(404)

    _install_mock(monkeypatch, handler)
    cfg = _cfg(tmp_path)
    inputs = PipelineInput(
        image_path=sample_image,
        pixelize_params=PixelizeParams(output_size=(16, 16), colors=4, preview_scale=0),
        use_cache=False,
    )
    # VL 解析失败，应不阻塞像素化
    result = run_pipeline(cfg, inputs)
    assert result.pixel_path.exists()
    assert result.analysis is None
    # 02_analysis.json 里应写入错误描述
    assert result.analysis_path is not None
    err_payload = json.loads(result.analysis_path.read_text(encoding="utf-8"))
    assert "error" in err_payload
