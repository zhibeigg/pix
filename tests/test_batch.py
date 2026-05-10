"""pix.batch 单元测试：不走网络，只验证批量流程。"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from pix.batch import (
    DEFAULT_EXTS,
    BatchItem,
    iter_inputs,
    run_batch,
)
from pix.config import AppConfig
from pix.pixelize.core import PixelizeParams


def _make_image(path: Path, color: tuple[int, int, int] = (100, 150, 200)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (128, 128), color)
    draw = ImageDraw.Draw(img)
    draw.rectangle((16, 16, 112, 112), fill=(240, 200, 80))
    img.save(path)
    return path


@pytest.fixture
def input_dir(tmp_path: Path) -> Path:
    d = tmp_path / "in"
    d.mkdir()
    _make_image(d / "a.png")
    _make_image(d / "b.png", color=(50, 80, 40))
    _make_image(d / "sub" / "c.png", color=(200, 60, 60))
    # 非位图文件应被忽略
    (d / "readme.txt").write_text("not an image")
    return d


@pytest.fixture
def cfg() -> AppConfig:
    c = AppConfig()
    c.cache.enabled = False
    return c


class TestIterInputs:
    def test_recursive(self, input_dir: Path) -> None:
        files = iter_inputs(input_dir)
        names = sorted(p.name for p in files)
        assert names == ["a.png", "b.png", "c.png"]

    def test_custom_patterns(self, input_dir: Path) -> None:
        # .txt 不应匹配默认模式
        files = iter_inputs(input_dir, patterns=("*.txt",))
        assert [p.name for p in files] == ["readme.txt"]


class TestRunBatch:
    def test_basic_batch(self, input_dir: Path, tmp_path: Path, cfg: AppConfig) -> None:
        out = tmp_path / "out"
        params = PixelizeParams(output_size=(32, 32), colors=4, preview_scale=0)
        result = run_batch(
            cfg, input_dir, out,
            pixelize_params=params,
            use_vl=False, workers=1,
        )
        assert len(result.ok) == 3
        assert len(result.failed) == 0
        assert (out / "a.png").exists()
        assert (out / "b.png").exists()
        assert (out / "sub" / "c.png").exists()
        # sidecar 默认开
        assert (out / "a.meta.json").exists()

    def test_skip_existing(self, input_dir: Path, tmp_path: Path, cfg: AppConfig) -> None:
        out = tmp_path / "out"
        params = PixelizeParams(output_size=(16, 16), colors=4, preview_scale=0)
        run_batch(cfg, input_dir, out, pixelize_params=params, workers=1)
        # 再跑一次应当全部 skipped
        result2 = run_batch(cfg, input_dir, out, pixelize_params=params, workers=1)
        assert len(result2.skipped) == 3
        assert len(result2.ok) == 0

    def test_overwrite(self, input_dir: Path, tmp_path: Path, cfg: AppConfig) -> None:
        out = tmp_path / "out"
        params = PixelizeParams(output_size=(16, 16), colors=4, preview_scale=0)
        run_batch(cfg, input_dir, out, pixelize_params=params, workers=1)
        result2 = run_batch(
            cfg, input_dir, out,
            pixelize_params=params, workers=1, overwrite=True,
        )
        assert len(result2.ok) == 3
        assert len(result2.skipped) == 0

    def test_no_sidecars(self, input_dir: Path, tmp_path: Path, cfg: AppConfig) -> None:
        out = tmp_path / "out"
        params = PixelizeParams(output_size=(16, 16), colors=4, preview_scale=0)
        run_batch(
            cfg, input_dir, out,
            pixelize_params=params, workers=1, write_sidecars=False,
        )
        assert (out / "a.png").exists()
        assert not (out / "a.meta.json").exists()

    def test_callback_invoked(self, input_dir: Path, tmp_path: Path, cfg: AppConfig) -> None:
        events: list[tuple[str, int, int]] = []

        def cb(item: BatchItem, done: int, total: int) -> None:
            events.append((item.status, done, total))

        out = tmp_path / "out"
        params = PixelizeParams(output_size=(16, 16), colors=4, preview_scale=0)
        run_batch(
            cfg, input_dir, out,
            pixelize_params=params, workers=1, on_item_done=cb,
        )
        assert len(events) == 3
        assert all(t == 3 for _, _, t in events)
        # done 值递增
        dones = [d for _, d, _ in events]
        assert dones == [1, 2, 3]

    def test_parallel(self, input_dir: Path, tmp_path: Path, cfg: AppConfig) -> None:
        out = tmp_path / "out"
        params = PixelizeParams(output_size=(16, 16), colors=4, preview_scale=0)
        result = run_batch(
            cfg, input_dir, out,
            pixelize_params=params, workers=4,
        )
        assert len(result.ok) == 3

    def test_failure_isolated(self, tmp_path: Path, cfg: AppConfig) -> None:
        """损坏的图不应阻塞其它任务。"""
        in_dir = tmp_path / "in"
        in_dir.mkdir()
        _make_image(in_dir / "ok.png")
        bad = in_dir / "bad.png"
        bad.write_bytes(b"not-a-real-png")

        out = tmp_path / "out"
        params = PixelizeParams(output_size=(16, 16), colors=4, preview_scale=0)
        result = run_batch(cfg, in_dir, out, pixelize_params=params, workers=1)
        assert len(result.ok) == 1
        assert len(result.failed) == 1
        assert result.failed[0].src.name == "bad.png"

    def test_empty_input(self, tmp_path: Path, cfg: AppConfig) -> None:
        in_dir = tmp_path / "in"
        in_dir.mkdir()
        out = tmp_path / "out"
        result = run_batch(cfg, in_dir, out, workers=1)
        assert result.items == []

    def test_missing_input_dir(self, tmp_path: Path, cfg: AppConfig) -> None:
        with pytest.raises(FileNotFoundError):
            run_batch(cfg, tmp_path / "no_such", tmp_path / "out", workers=1)

    def test_summary(self, input_dir: Path, tmp_path: Path, cfg: AppConfig) -> None:
        out = tmp_path / "out"
        params = PixelizeParams(output_size=(16, 16), colors=4, preview_scale=0)
        result = run_batch(cfg, input_dir, out, pixelize_params=params, workers=1)
        s = result.summary()
        assert "total=3" in s and "ok=3" in s
