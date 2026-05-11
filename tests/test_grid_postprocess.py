"""Pixel Grid 后处理测试。"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from pix.cli import app
from pix.grid.postprocess import fit_pixel_grid_to_canvas, polish_pixel_grid
from pix.grid.schema import grid_from_mapping, save_grid

runner = CliRunner()


def _grid_bbox(pixels: list[list[int]], transparent: int = -1) -> tuple[int, int, int, int]:
    xs: list[int] = []
    ys: list[int] = []
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            if value != transparent:
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


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


def test_outline_does_not_fill_diagonal_only_gaps() -> None:
    grid = grid_from_mapping({
        "canvas": {"width": 5, "height": 5, "transparent_index": -1},
        "palette": [
            {"id": 0, "hex": "#101010", "role": "outline"},
            {"id": 1, "hex": "#DD3344", "role": "primary"},
        ],
        "pixels": [
            [-1, -1, -1, -1, -1],
            [-1, 1, -1, -1, -1],
            [-1, -1, -1, -1, -1],
            [-1, -1, -1, 1, -1],
            [-1, -1, -1, -1, -1],
        ],
    })

    out = polish_pixel_grid(grid, cleanup=False, outline=True, max_colors=4)

    assert out.pixels[2][2] == -1
    assert out.pixels[1][2] == 0
    assert out.pixels[2][1] == 0
    assert out.pixels[2][3] == 0
    assert out.pixels[3][2] == 0


def test_fit_canvas_smart_stretches_only_underfilled_ui_axis() -> None:
    grid = grid_from_mapping({
        "canvas": {"width": 12, "height": 8, "transparent_index": -1},
        "palette": [{"id": 0, "hex": "#DD3344", "role": "primary"}],
        "pixels": [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1],
            [-1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        ],
    })

    out = fit_pixel_grid_to_canvas(grid, padding=1, mode="smart", min_axis_coverage=0.7)

    assert _grid_bbox(out.pixels) == (1, 1, 11, 7)
    assert out.metadata["fit_canvas"]["old_axis_coverage"] == [10 / 12, 2 / 8]
    assert out.metadata["fit_canvas"]["new_axis_coverage"] == [10 / 12, 6 / 8]


def test_fit_canvas_contain_respects_padding() -> None:
    grid = grid_from_mapping({
        "canvas": {"width": 8, "height": 8, "transparent_index": -1},
        "palette": [{"id": 0, "hex": "#33DD44", "role": "primary"}],
        "pixels": [
            [-1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, 0, 0, -1, -1, -1],
            [-1, -1, -1, 0, 0, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1],
        ],
    })

    out = fit_pixel_grid_to_canvas(grid, padding=2, mode="contain")

    assert _grid_bbox(out.pixels) == (2, 2, 6, 6)
    assert all(v == -1 for v in out.pixels[0])
    assert all(v == -1 for v in out.pixels[-1])


def test_outline_and_fit_canvas_keep_hard_border() -> None:
    grid = grid_from_mapping({
        "canvas": {"width": 8, "height": 8, "transparent_index": -1},
        "palette": [
            {"id": 0, "hex": "#101010", "role": "outline"},
            {"id": 1, "hex": "#DD3344", "role": "primary"},
        ],
        "pixels": [
            [-1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, 1, 1, -1, -1, -1],
            [-1, -1, -1, 1, 1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1],
        ],
    })

    polished = polish_pixel_grid(grid, cleanup=False, outline=True, max_colors=4)
    out = fit_pixel_grid_to_canvas(polished, padding=1, mode="contain")

    assert _grid_bbox(out.pixels) == (1, 1, 7, 7)
    assert 0 in {v for row in out.pixels for v in row}
    assert 1 in {v for row in out.pixels for v in row}
    assert out.pixels[1][3] == 0


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
