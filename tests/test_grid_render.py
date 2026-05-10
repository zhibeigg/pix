"""Pixel Grid 渲染测试。"""

from __future__ import annotations

import numpy as np

from pix.grid.render import render_pixel_grid
from pix.grid.schema import grid_from_mapping


def test_render_pixel_grid_exact_rgba() -> None:
    grid = grid_from_mapping({
        "canvas": {"width": 2, "height": 2, "transparent_index": -1},
        "palette": [
            {"id": 0, "hex": "#FF0000", "role": "primary"},
            {"id": 1, "hex": "#00FF00", "role": "highlight"},
        ],
        "pixels": [[-1, 0], [1, -1]],
    })

    image = render_pixel_grid(grid)
    arr = np.asarray(image)

    assert image.size == (2, 2)
    assert tuple(arr[0, 0]) == (0, 0, 0, 0)
    assert tuple(arr[0, 1]) == (255, 0, 0, 255)
    assert tuple(arr[1, 0]) == (0, 255, 0, 255)
