"""Pixel Grid 后处理测试。"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from pix.cli import app
from pix.grid.postprocess import polish_pixel_grid
from pix.grid.render import render_pixel_grid
from pix.grid.schema import grid_from_mapping, save_grid

runner = CliRunner()


def test_cleanup_removes_isolated_pixel() -> None:
    grid = grid_from_mapping({
        "canvas": {"width": 3, "height": 3, "transparent_index": -1},
        "palette": [{"id": 0, "hex": "#FF0000", "role": "primary"}],
        "pixels": [[-1, -1, -1], [-1, 0, -1], [-1, -1, -1]],
    })

    out = polish_pixel_grid(grid, cleanup=True, outline=False, min_neighbors=1, max_colors=4)

    assert all(v == -1 for row in out.pixels for v in row)


def test_outline_adds_outer_outline_without_eating_subject() -> None:
    grid = grid_from_mapping({
        "canvas": {"width": 5, "height": 5, "transparent_index": -1},
        "palette": [
            {"id": 0, "hex": "#101010", "role": "outline"},
            {"id": 1, "hex": "#DD3344", "role": "primary"},
        ],
        "pixels": [
            [-1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1],
            [-1, -1, 1, -1, -1],
            [-1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1],
        ],
    })

    out = polish_pixel_grid(grid, cleanup=False, outline=True, max_colors=4)

    assert out.pixels[2][2] == 1
    assert out.pixels[1][2] == 0
    assert out.pixels[2][1] == 0
    assert out.pixels[2][3] == 0
    assert out.pixels[3][2] == 0
    assert out.palette[0].role == "outline"


def test_palette_compaction_removes_unused() -> None:
    grid = grid_from_mapping({
        "canvas": {"width": 2, "height": 2, "transparent_index": -1},
        "palette": [
            {"id": 0, "hex": "#101010", "role": "outline"},
            {"id": 1, "hex": "#DD3344", "role": "primary"},
            {"id": 2, "hex": "#33DD44", "role": "accent"},
        ],
        "pixels": [[-1, 1], [1, -1]],
    })

    out = polish_pixel_grid(grid, cleanup=False, outline=False, max_colors=2)

    assert len(out.palette) == 1
    assert out.palette[0].id == 0
    assert out.pixels == [[-1, 0], [0, -1]]


def test_grid_polish_cli(tmp_path: Path, tmp_cwd: Path) -> None:
    grid = grid_from_mapping({
        "canvas": {"width": 3, "height": 3, "transparent_index": -1},
        "palette": [{"id": 0, "hex": "#FF0000", "role": "primary"}],
        "pixels": [[-1, -1, -1], [-1, 0, -1], [-1, -1, -1]],
    })
    src = tmp_path / "in.grid.json"
    out = tmp_path / "out.grid.json"
    png = tmp_path / "out.png"
    save_grid(grid, src)

    result = runner.invoke(
        app,
        [
            "grid-polish", str(src),
            "--out", str(out),
            "--render", str(png),
            "--no-outline",
            "--cleanup",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert out.exists()
    assert png.exists()
