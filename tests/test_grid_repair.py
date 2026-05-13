"""AI Grid 局部修补测试。

mock VL 返回 patch JSON，校验合并行为；同时覆盖 auto 跳过逻辑。
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from PIL import Image

from pix.config import AppConfig
from pix.grid.readability import evaluate_grid_readability
from pix.grid.repair import GridRepairError, build_repair_mask, repair_or_passthrough, repair_pixel_grid
from pix.grid.schema import PixelGrid, PixelGridCanvas, PixelGridColor


def _toy_grid() -> PixelGrid:
    palette = [
        PixelGridColor(id=0, hex="#101010", role="outline"),
        PixelGridColor(id=1, hex="#A03020", role="primary"),
        PixelGridColor(id=2, hex="#FFEEAA", role="highlight"),
    ]
    # 16x16 主体，故意让 highlight 占比 > 16% 触发 warning
    pixels = [[-1] * 16 for _ in range(16)]
    for y in range(3, 13):
        for x in range(3, 13):
            pixels[y][x] = 1
    # 大量高光区
    for y in range(4, 8):
        for x in range(4, 9):
            pixels[y][x] = 2
    return PixelGrid(
        canvas=PixelGridCanvas(width=16, height=16, transparent_index=-1),
        palette=palette,
        pixels=pixels,
    )


def _cfg(tmp_path: Path) -> AppConfig:
    cfg = AppConfig()
    cfg.api.base_url = "https://packy.test"
    cfg.api.image_api_key = "sk-i"
    cfg.api.vl_api_key = "sk-v"
    cfg.api.max_retries = 1
    cfg.api.timeout = 2.0
    cfg.cache.dir = str(tmp_path / "cache")
    return cfg


def _install_mock(monkeypatch: pytest.MonkeyPatch, content_text: str) -> dict:
    state = {"calls": 0, "last_body": None}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/v1/chat/completions":
            state["calls"] += 1
            state["last_body"] = req.content
            return httpx.Response(200, json={"choices": [{"message": {"content": content_text}}]})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    orig = httpx.Client

    class _Patched(orig):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("pix.api.packy_client.httpx.Client", _Patched)
    monkeypatch.setattr("pix.api.packy_client.time.sleep", lambda _s: None)
    return state


def _png(tmp_path: Path) -> Path:
    p = tmp_path / "src.png"
    Image.new("RGB", (16, 16), (160, 90, 60)).save(p)
    return p


def test_build_repair_mask_summarizes_report() -> None:
    grid = _toy_grid()
    report = evaluate_grid_readability(grid, max_colors=8)
    info = build_repair_mask(report)
    assert "warnings" in info and "blocking" in info
    assert info["color_count"] in (2, 3)


def test_repair_pixel_grid_applies_patches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    grid = _toy_grid()
    _install_mock(monkeypatch, '{"patches":[{"xy":[5,5],"value":1},{"xy":[6,6],"value":1}]}')
    cfg = _cfg(tmp_path)
    image_path = _png(tmp_path)
    report = evaluate_grid_readability(grid, max_colors=8)
    new_grid = repair_pixel_grid(cfg, grid, report, image_path=image_path)
    assert new_grid.pixels[5][5] == 1
    assert new_grid.pixels[6][6] == 1
    assert new_grid.metadata["ai_grid"]["repair"]["applied_patches"] == 2


def test_repair_pixel_grid_rejects_too_many_patches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    grid = _toy_grid()
    big = ",".join(f'{{"xy":[{x},{y}],"value":-1}}' for y in range(16) for x in range(16))
    _install_mock(monkeypatch, '{"patches":[' + big + ']}')
    cfg = _cfg(tmp_path)
    image_path = _png(tmp_path)
    report = evaluate_grid_readability(grid, max_colors=8)
    with pytest.raises(GridRepairError):
        repair_pixel_grid(cfg, grid, report, image_path=image_path)


def test_repair_or_passthrough_off(tmp_path: Path) -> None:
    grid = _toy_grid()
    cfg = _cfg(tmp_path)
    image_path = _png(tmp_path)
    out, info = repair_or_passthrough(cfg, grid, image_path=image_path, max_colors=8, repair_mode="off")
    assert out is grid
    assert info["applied"] is False
    assert info["reason"] == "off"


def test_repair_or_passthrough_auto_invokes_vl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    grid = _toy_grid()
    state = _install_mock(monkeypatch, '{"patches":[{"xy":[5,5],"value":1}]}')
    cfg = _cfg(tmp_path)
    image_path = _png(tmp_path)
    out, info = repair_or_passthrough(cfg, grid, image_path=image_path, max_colors=8, repair_mode="auto")
    # auto 模式：grid 有 highlight_too_much warning，应该触发 VL
    assert state["calls"] == 1
    assert info["applied"] is True
    assert info["reason"] == "repaired"
    assert out.pixels[5][5] == 1


def test_repair_or_passthrough_auto_skips_when_blocking(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 主体过小：构造 1×1 主体 → 触发 subject_too_small blocking
    palette = [PixelGridColor(id=0, hex="#222222", role="primary")]
    pixels = [[-1] * 8 for _ in range(8)]
    pixels[3][3] = 0
    grid = PixelGrid(
        canvas=PixelGridCanvas(width=8, height=8, transparent_index=-1),
        palette=palette,
        pixels=pixels,
    )
    state = _install_mock(monkeypatch, '{"patches":[]}')
    cfg = _cfg(tmp_path)
    image_path = _png(tmp_path)
    _, info = repair_or_passthrough(cfg, grid, image_path=image_path, max_colors=4, repair_mode="auto")
    # 有 blocking，auto 模式应当跳过；不调用 VL
    assert state["calls"] == 0
    assert info["applied"] is False
    assert info["reason"] == "has_blocking_skip_repair"


def test_repair_or_passthrough_failure_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    grid = _toy_grid()
    _install_mock(monkeypatch, "not json at all")
    cfg = _cfg(tmp_path)
    image_path = _png(tmp_path)
    out, info = repair_or_passthrough(cfg, grid, image_path=image_path, max_colors=8, repair_mode="force")
    assert out is grid
    assert info["applied"] is False
    assert info["reason"] == "repair_failed"
    assert info["error"]
