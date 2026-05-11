"""Pixel Grid schema 测试。"""

from __future__ import annotations

import pytest

from pix.grid.schema import PixelGrid, grid_from_mapping


def _grid_dict() -> dict:
    return {
        "version": 1,
        "canvas": {"width": 2, "height": 2, "transparent_index": -1},
        "palette": [
            {"id": 0, "hex": "#111111", "role": "outline"},
            {"id": 1, "hex": "FF0000", "role": "primary"},
        ],
        "pixels": [[-1, 0], [1, -1]],
        "metadata": {"name": "x"},
    }


def test_grid_schema_normalizes_hex_and_axes() -> None:
    grid = grid_from_mapping(_grid_dict())
    assert grid.palette[1].hex == "#FF0000"
    assert grid.axes.x == [0, 1]
    assert grid.axes.y == [0, 1]


def test_grid_schema_accepts_string_matrix() -> None:
    grid = grid_from_mapping({
        "version": 1,
        "canvas": {"width": 4, "height": 3, "transparent_index": -9},
        "palette": [
            {"id": 0, "hex": "#111111", "role": "outline"},
            {"id": 1, "hex": "#FF0000", "role": "primary"},
            {"id": 10, "hex": "#FFFF00", "role": "highlight"},
        ],
        "pixels": [".01A", "_110", "...."],
    })
    assert grid.pixels == [
        [-9, 0, 1, 10],
        [-9, 1, 1, 0],
        [-9, -9, -9, -9],
    ]


def test_grid_schema_rejects_bad_dimensions() -> None:
    data = _grid_dict()
    data["pixels"] = [[0]]
    with pytest.raises(ValueError):
        PixelGrid.model_validate(data)


def test_grid_schema_rejects_unknown_palette_id() -> None:
    data = _grid_dict()
    data["pixels"] = [[-1, 9], [1, -1]]
    with pytest.raises(ValueError):
        PixelGrid.model_validate(data)
