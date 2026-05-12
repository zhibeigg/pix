"""Pixel Grid 可读性评分测试。"""

from __future__ import annotations

from pix.grid.readability import evaluate_grid_readability, format_blocking_issues
from pix.grid.schema import grid_from_mapping


def test_readability_accepts_clear_low_pixel_icon() -> None:
    grid = grid_from_mapping({
        "canvas": {"width": 8, "height": 8, "transparent_index": -1},
        "palette": [
            {"id": 0, "hex": "#201010", "role": "outline"},
            {"id": 1, "hex": "#B84830", "role": "primary"},
            {"id": 2, "hex": "#F0B060", "role": "highlight"},
        ],
        "pixels": [
            "........",
            "..0000..",
            ".011110.",
            ".011210.",
            ".011110.",
            "..0000..",
            "........",
            "........",
        ],
    })

    report = evaluate_grid_readability(grid, max_colors=4)

    assert report.ok is True
    assert report.color_count == 3
    assert report.component_count == 1
    assert report.bbox == (1, 1, 7, 6)
    assert report.highlight_ratio < 0.16


def test_readability_blocks_fragmented_or_tiny_icon() -> None:
    grid = grid_from_mapping({
        "canvas": {"width": 8, "height": 8, "transparent_index": -1},
        "palette": [{"id": 0, "hex": "#FF0000", "role": "primary"}],
        "pixels": [
            "........",
            ".0..0...",
            "........",
            "...0....",
            "........",
            ".....0..",
            "........",
            ".......0",
        ],
    })

    report = evaluate_grid_readability(grid, max_colors=4)
    blocking_codes = {issue.code for issue in report.blocking}

    assert report.ok is False
    assert "too_fragmented" in blocking_codes
    assert report.isolated_pixels == 5
    assert "too_fragmented" in format_blocking_issues(report)


def test_readability_blocks_dense_8x8_scaled_blob() -> None:
    grid = grid_from_mapping({
        "canvas": {"width": 8, "height": 8, "transparent_index": -1},
        "palette": [
            {"id": 0, "hex": "#201010", "role": "outline"},
            {"id": 1, "hex": "#B84830", "role": "primary"},
        ],
        "pixels": [
            "00000000",
            "01111110",
            "01111110",
            "01111110",
            "01111110",
            "01111110",
            "01111110",
            "00000000",
        ],
    })

    report = evaluate_grid_readability(grid, max_colors=4)
    blocking_codes = {issue.code for issue in report.blocking}

    assert report.ok is False
    assert "tiny_touches_edge" in blocking_codes
    assert "tiny_bbox_too_large" in blocking_codes
