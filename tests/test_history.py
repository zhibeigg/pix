"""历史记录扫描测试。"""

from __future__ import annotations

import json
from pathlib import Path

from pix.history import load_history_record, scan_history


def _write_history_run(root: Path, name: str, prompt: str, *, model: str = "gpt-image-2") -> Path:
    run_dir = root / name
    run_dir.mkdir(parents=True)
    for file_name in ("01_source.png", "02_analysis.json", "03_pixelized.png", "04_pixelized_preview.png"):
        (run_dir / file_name).write_bytes(b"x")
    meta = {
        "version": "0.2.0",
        "duration_seconds": 1.25,
        "input": {"prompt": prompt, "image_path": None},
        "image_gen": {"model": model, "size": "1024x1024", "quality": "high", "used": True},
        "vision": {"model": "claude-opus-4-7", "skipped": False, "ok": True},
        "pixelize": {
            "effective_params": {
                "output_size": [64, 64],
                "colors": 16,
                "dither": "none",
                "preset": "auto",
                "remove_bg": True,
                "bg_tolerance": 20,
                "bg_feather": 0,
                "edge_style": "hard",
            }
        },
        "outputs": {
            "source": "01_source.png",
            "analysis": "02_analysis.json",
            "pixelized": "03_pixelized.png",
            "preview": "04_pixelized_preview.png",
        },
    }
    (run_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return run_dir


def test_load_history_record(tmp_path: Path) -> None:
    run_dir = _write_history_run(tmp_path, "20260510-120000-abcd", "血气灵玉")

    record = load_history_record(run_dir)

    assert record.prompt == "血气灵玉"
    assert record.pixel_size == (64, 64)
    assert record.colors == 16
    assert record.dither == "none"
    assert record.remove_bg is True
    assert record.edge_style == "hard"
    assert record.ok is True
    assert record.pixel_path == run_dir / "03_pixelized.png"


def test_scan_history_filters_query_and_skips_bad_meta(tmp_path: Path) -> None:
    _write_history_run(tmp_path, "20260510-120000-a", "血气灵玉")
    _write_history_run(tmp_path, "20260510-120001-b", "冰魄玉髓")
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "meta.json").write_text("not json", encoding="utf-8")

    records = scan_history(tmp_path, query="冰魄", limit=10)

    assert len(records) == 1
    assert records[0].prompt == "冰魄玉髓"


def test_scan_history_limit(tmp_path: Path) -> None:
    _write_history_run(tmp_path, "20260510-120000-a", "a")
    _write_history_run(tmp_path, "20260510-120001-b", "b")

    records = scan_history(tmp_path, limit=1)

    assert len(records) == 1
