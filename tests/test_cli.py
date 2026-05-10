"""CLI 冒烟测试（使用 typer.testing.CliRunner）。"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from pix.cli import app


runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "pix" in result.stdout


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_presets_command() -> None:
    result = runner.invoke(app, ["presets"])
    assert result.exit_code == 0
    for name in ("auto", "gameboy", "nes", "pico8", "modern_pixel"):
        assert name in result.stdout


def test_pixelize_offline(sample_image: Path, tmp_path: Path, tmp_cwd: Path) -> None:
    out = tmp_path / "out.png"
    result = runner.invoke(
        app,
        [
            "pixelize",
            str(sample_image),
            "--out", str(out),
            "--pixel-size", "32x32",
            "--colors", "8",
            "--preset", "pico8",
            "--preview-scale", "0",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists()


def test_pixelize_with_analysis(
    sample_image: Path, tmp_path: Path, tmp_cwd: Path, fake_analysis_dict: dict
) -> None:
    import json
    analysis_path = tmp_path / "analysis.json"
    analysis_path.write_text(json.dumps(fake_analysis_dict), encoding="utf-8")
    out = tmp_path / "out.png"
    result = runner.invoke(
        app,
        [
            "pixelize", str(sample_image),
            "--analysis", str(analysis_path),
            "--out", str(out),
            "--pixel-size", "16x16",
            "--colors", "6",
            "--preset", "auto",
            "--preview-scale", "0",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists()


def test_batch_cli(sample_image: Path, tmp_path: Path, tmp_cwd: Path) -> None:
    in_dir = tmp_path / "batch_in"
    in_dir.mkdir()
    # 拷贝两份
    import shutil
    shutil.copy(sample_image, in_dir / "a.png")
    shutil.copy(sample_image, in_dir / "b.png")

    out_dir = tmp_path / "batch_out"
    result = runner.invoke(
        app,
        [
            "batch", str(in_dir), str(out_dir),
            "--pixel-size", "16x16",
            "--colors", "4",
            "--workers", "1",
            "--no-sidecars",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert (out_dir / "a.png").exists()
    assert (out_dir / "b.png").exists()
