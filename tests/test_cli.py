"""CLI 冒烟测试（使用 typer.testing.CliRunner）。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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


def test_validate_cli_game_asset(tmp_path: Path, tmp_cwd: Path) -> None:
    from PIL import Image

    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y in range(4, 12):
        for x in range(4, 12):
            img.putpixel((x, y), (200, 40, 60, 255))
    path = tmp_path / "asset.png"
    img.save(path)

    result = runner.invoke(
        app,
        ["validate", str(path), "--pixel-size", "16x16", "--max-colors", "4"],
    )
    assert result.exit_code == 0, result.stdout
    assert "OK" in result.stdout


def test_grid_extract_and_render_cli(tmp_path: Path, tmp_cwd: Path) -> None:
    from PIL import Image

    img = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    img.putpixel((1, 1), (255, 0, 0, 255))
    img.putpixel((2, 1), (255, 0, 0, 255))
    src = tmp_path / "source.png"
    img.resize((64, 64), Image.Resampling.NEAREST).save(src)
    grid_json = tmp_path / "item.grid.json"
    rendered = tmp_path / "item.png"

    result = runner.invoke(
        app,
        [
            "grid-extract", str(src),
            "--pixel-size", "4x4",
            "--colors", "4",
            "--out", str(grid_json),
            "--render", str(rendered),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert grid_json.exists()
    assert rendered.exists()

    rendered2 = tmp_path / "item2.png"
    result2 = runner.invoke(app, ["grid-render", str(grid_json), "--out", str(rendered2)])
    assert result2.exit_code == 0, result2.stdout
    assert rendered2.exists()


def test_asset_cli_direct_output(tmp_path: Path, tmp_cwd: Path, monkeypatch) -> None:
    from PIL import Image

    def fake_run_pipeline(cfg, inputs, progress=None):
        assert "血气灵玉" in inputs.prompt
        assert inputs.skip_vl is True
        assert inputs.pixelize_params.output_size == (16, 16)
        assert inputs.pixelize_params.dither == "none"
        assert inputs.pixelize_params.remove_bg is True
        assert inputs.pixelize_params.auto_crop is True
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        source_path = run_dir / "01_source.png"
        pixel_path = run_dir / "03_pixelized.png"
        preview_path = run_dir / "04_pixelized_preview.png"
        img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        for y in range(4, 12):
            for x in range(4, 12):
                img.putpixel((x, y), (180, 20, 40, 255))
        img.save(pixel_path)
        img.resize((128, 128), Image.Resampling.NEAREST).save(source_path)
        img.resize((192, 192), Image.Resampling.NEAREST).save(preview_path)
        meta = {"vision": {"ok": False}, "pixelize": {"effective_params": {}}}
        return SimpleNamespace(
            run_dir=run_dir,
            source_path=source_path,
            analysis_path=None,
            meta_path=run_dir / "meta.json",
            pixel_path=pixel_path,
            preview_path=preview_path,
            analysis=None,
            meta=meta,
        )

    monkeypatch.setattr("pix.cli.run_pipeline", fake_run_pipeline)
    out = tmp_path / "血气灵玉.png"
    result = runner.invoke(
        app,
        ["asset", "血气灵玉", "--out", str(out)],
    )

    assert result.exit_code == 0, result.stdout
    assert out.exists()
    assert out.with_name("血气灵玉_preview.png").exists()
    assert out.with_name("血气灵玉_source.png").exists()
    assert out.with_name("血气灵玉.grid.json").exists()
    sidecar = out.with_name("血气灵玉.asset.json").read_text(encoding="utf-8")
    assert "血气灵玉_source.png" in sidecar


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
