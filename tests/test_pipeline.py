"""Pipeline 编排测试（mock API）。"""

from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
import numpy as np
import pytest
from PIL import Image

from pix.config import AppConfig
from pix.pipeline import GridDesignInput, PipelineInput, run_pipeline
from pix.pixelize.core import PixelizeParams


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (100, 100, 100)).save(buf, format="PNG")
    return buf.getvalue()


def _white_square_source(path: Path) -> Path:
    img = Image.new("RGB", (64, 64), (255, 255, 255))
    for y in range(20, 44):
        for x in range(20, 44):
            img.putpixel((x, y), (220, 40, 60))
    img.save(path)
    return path


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
    # 这些用例锁定旧 3x3 contact sheet 行为，n_sample 路径有专门测试。
    cfg.image_gen.candidate_mode = "contact_sheet"
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
            body = json.loads(req.content.decode("utf-8"))
            content = body["messages"][0]["content"]
            if isinstance(content, str):
                return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"allowed": True, "reason": "", "normalized_description": "a cat"})}}]})
            image_count = sum(1 for item in content if isinstance(item, dict) and item.get("type") == "image_url")
            if image_count > 1:
                return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"selected_index": 2, "candidates": [{"index": 2, "rank": 1, "score": 91, "reason": "best"}, {"index": 1, "rank": 2, "score": 40, "reason": "ok"}]})}}]})
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
    assert vl_calls["n"] == 3  # prompt guard + 候选评分 + 图片分析
    assert result.source_path.exists()
    assert result.analysis is not None
    assert result.analysis.description == "mock"
    assert result.pixel_path.exists()
    assert result.preview_path is not None and result.preview_path.exists()
    assert result.meta["vision"]["ok"] is True
    assert result.meta["image_gen"]["contact_sheet"]["count"] == 9
    assert result.meta["image_gen"]["contact_sheet"]["selected_index"] == 2
    assert result.meta["image_gen"]["contact_sheet"]["candidates"][0]["index"] == 2
    assert result.meta["image_gen"]["contact_sheet"]["candidates"][0]["score"] == 91
    candidates = result.meta["image_gen"]["contact_sheet"]["candidates"]
    assert len([item for item in candidates if item.get("pixelized_path")]) == 9
    selected = candidates[0]
    assert selected["selected"] is True
    assert selected["pixelized_path"].startswith("candidate_outputs/")
    assert (result.run_dir / selected["pixelized_path"]).read_bytes() == result.pixel_path.read_bytes()
    assert result.meta["pixelize"]["candidate_outputs"]["count"] == 9
    assert result.meta["outputs"]["contact_sheet"] == "01_contact_sheet.png"
    assert result.meta["outputs"]["candidate_scores"] == "01_candidate_scores.json"
    assert result.meta["outputs"]["candidate_outputs"] == "candidate_outputs"
    assert "source_ready" in events
    assert "analysis_ready" in events
    assert "pixelize_ready" in events

    # 再跑一次应命中缓存：网络不再被调
    result2 = run_pipeline(cfg, inputs)
    assert gen_calls["n"] == 1  # 没变
    assert vl_calls["n"] == 5  # 第二次仍会审核用户输入并重评候选，但图片分析命中缓存
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
    assert vl_calls["n"] == 1  # skip_vl 不跳过用户描述审核
    assert result.analysis is None
    assert result.analysis_path is None
    assert result.pixel_path.exists()


def test_pipeline_local_stage_context_starts_after_image_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    png = _png_bytes()
    events: list[str] = []

    class LocalStageRecorder:
        def __enter__(self):
            events.append("lock_enter")

        def __exit__(self, exc_type, exc, tb):
            events.append("lock_exit")

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/v1/images/generations":
            events.append("image_gen")
            return httpx.Response(200, json={"data": [{"url": "https://cdn.test/a.png"}]})
        if req.url.host == "cdn.test":
            return httpx.Response(200, content=png)
        if req.url.path == "/v1/chat/completions":
            events.append("prompt_guard")
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"allowed": True, "reason": "", "normalized_description": "a cat"})}}]})
        return httpx.Response(404)

    _install_mock(monkeypatch, handler)
    cfg = _cfg(tmp_path)
    cfg.image_gen.contact_sheet_enabled = False
    inputs = PipelineInput(
        prompt="a cat",
        pixelize_params=PixelizeParams(output_size=(16, 16), colors=4, preview_scale=0),
        skip_vl=True,
        use_cache=False,
        local_stage_context=lambda: LocalStageRecorder(),
    )

    result = run_pipeline(cfg, inputs)

    assert result.pixel_path.exists()
    assert events.index("image_gen") < events.index("lock_enter")
    assert events[-1] == "lock_exit"


def test_pipeline_from_image_edit(
    tmp_path: Path, sample_image: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    png = _png_bytes()
    edit_calls = {"n": 0}
    vl_calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/v1/images/edits":
            edit_calls["n"] += 1
            assert req.headers["content-type"].startswith("multipart/form-data")
            assert b'name="prompt"' in req.content
            assert b"make it warmer" in req.content
            assert b'name="image"' in req.content
            return httpx.Response(200, json={"data": [{"url": "https://cdn.test/edited.png"}]})
        if req.url.host == "cdn.test":
            return httpx.Response(200, content=png)
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
        prompt="make it warmer",
        image_path=sample_image,
        pixelize_params=PixelizeParams(output_size=(16, 16), colors=4, preview_scale=0),
        use_cache=False,
    )
    events: list[str] = []
    result = run_pipeline(cfg, inputs, progress=lambda s, _p: events.append(s))

    assert edit_calls["n"] == 1
    assert vl_calls["n"] == 3
    assert result.source_path.exists()
    assert result.meta["image_gen"]["mode"] == "edited_contact_sheet"
    assert result.meta["image_gen"]["used"] is True
    assert "image_edit_start" in events
    assert "source_ready" in events


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


def test_grid_pipeline_applies_outline_edge_style(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    src = _white_square_source(tmp_path / "square.png")
    inputs = PipelineInput(
        image_path=src,
        skip_vl=True,
        use_cache=False,
        grid=GridDesignInput(mode="extract"),
        pixelize_params=PixelizeParams(
            output_size=(16, 16),
            colors=4,
            preview_scale=0,
            remove_bg=True,
            bg_tolerance=16,
            bg_feather=1,
            edge_style="outline",
        ),
    )

    result = run_pipeline(cfg, inputs)

    arr = np.asarray(Image.open(result.pixel_path).convert("RGBA"))
    assert result.grid_path is not None and result.grid_path.exists()
    assert result.meta["pixelize"]["effective_params"]["edge_style"] == "outline"
    assert result.meta["pixelize"]["effective_params"]["bg_feather"] == 1
    assert result.meta["pixelize"]["grid"]["edge_treatment"]["applied"] == "grid_outline"
    visible_rgb = arr[arr[..., 3] > 0][:, :3]
    unique_rgb = np.unique(visible_rgb, axis=0)
    luma = unique_rgb[:, 0] * 0.2126 + unique_rgb[:, 1] * 0.7152 + unique_rgb[:, 2] * 0.0722
    assert len(unique_rgb) >= 2
    assert float(luma.min()) < float(luma.max()) * 0.7


def test_grid_pipeline_applies_feather_edge_style_to_rendered_png(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    src = _white_square_source(tmp_path / "square.png")
    inputs = PipelineInput(
        image_path=src,
        skip_vl=True,
        use_cache=False,
        grid=GridDesignInput(mode="extract"),
        pixelize_params=PixelizeParams(
            output_size=(16, 16),
            colors=4,
            preview_scale=0,
            remove_bg=True,
            bg_tolerance=16,
            bg_feather=2,
            edge_style="feather",
        ),
    )

    result = run_pipeline(cfg, inputs)

    alpha = np.asarray(Image.open(result.pixel_path).convert("RGBA"))[..., 3]
    assert result.meta["pixelize"]["effective_params"]["edge_style"] == "feather"
    assert result.meta["pixelize"]["effective_params"]["bg_feather"] == 2
    assert result.meta["pixelize"]["grid"]["edge_treatment"]["applied"] == "render_feather"
    assert any(0 < value < 255 for value in np.unique(alpha))


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


def test_pipeline_n_sample_from_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """n_sample 模式：每次生图返回 1 张，应循环补齐到 n=4 张候选。"""
    png = _png_bytes()
    gen_calls = {"n": 0, "requested_n": []}

    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path == "/v1/images/generations":
            body = json.loads(req.content.decode("utf-8"))
            gen_calls["n"] += 1
            gen_calls["requested_n"].append(int(body.get("n", 1)))
            return httpx.Response(200, json={"data": [{"url": "https://cdn.test/sample.png"}]})
        if req.url.host == "cdn.test":
            return httpx.Response(200, content=png)
        if path == "/v1/chat/completions":
            body = json.loads(req.content.decode("utf-8"))
            content = body["messages"][0]["content"]
            if isinstance(content, str):
                return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"allowed": True, "reason": "", "normalized_description": "a sword"})}}]})
            image_count = sum(1 for item in content if isinstance(item, dict) and item.get("type") == "image_url")
            if image_count > 1:
                return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"selected_index": 1, "candidates": [{"index": 1, "rank": 1, "score": 88, "reason": "best"}]})}}]})
            return httpx.Response(200, json={"choices": [{"message": {"content": _ANALYSIS_BLOCK}}]})
        return httpx.Response(404)

    _install_mock(monkeypatch, handler)
    cfg = AppConfig()
    cfg.api.base_url = "https://packy.test"
    cfg.api.image_api_key = "sk-i"
    cfg.api.vl_api_key = "sk-v"
    cfg.api.max_retries = 1
    cfg.api.timeout = 2.0
    cfg.cache.dir = str(tmp_path / "cache")
    cfg.output.root = str(tmp_path / "outs")
    cfg.image_gen.candidate_mode = "n_sample"
    cfg.image_gen.n_sample_count = 4

    inputs = PipelineInput(
        prompt="a sword",
        pixelize_params=PixelizeParams(output_size=(16, 16), colors=4, preview_scale=0),
        use_cache=False,
        skip_vl=True,  # 简化：跳过图片分析 VL
    )
    result = run_pipeline(cfg, inputs)
    # 第一次 n=4，由于每次只返回 1 张，需要 fallback 3 次单图
    assert gen_calls["requested_n"][0] == 4
    assert sum(1 for n in gen_calls["requested_n"] if n == 1) == 3
    sheet_meta = result.meta["image_gen"]["contact_sheet"]
    assert sheet_meta["candidate_mode"] == "n_sample"
    assert sheet_meta["count"] == 4
    assert result.meta["pixelize"]["candidate_outputs"]["count"] == 4
