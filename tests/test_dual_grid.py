from __future__ import annotations

import numpy as np
import pytest

from pix.dual_grid import TL, TR, BL, BR, material_mask


def test_mask_index_0_all_b_and_15_all_a() -> None:
    assert not material_mask(0, 32, 32, "hard").any()
    assert material_mask(15, 32, 32, "hard").all()
    assert not material_mask(0, 32, 32, "rounded").any()
    assert material_mask(15, 32, 32, "rounded").all()


def test_mask_quadrant_corner_mapping_hard() -> None:
    # 仅 TL 角为 A → 左上象限为 A，其余 B
    m = material_mask(TL, 32, 32, "hard")
    assert m[:16, :16].all()
    assert not m[:16, 16:].any()
    assert not m[16:, :16].any()
    assert not m[16:, 16:].any()


def _shares_horizontal_edge(left: int, right: int) -> bool:
    # 水平相邻：左瓦片右两角(TR,BR) == 右瓦片左两角(TL,BL)
    return (bool(left & TR) == bool(right & TL)) and (bool(left & BR) == bool(right & BL))


def _shares_vertical_edge(top: int, bottom: int) -> bool:
    # 竖直相邻：上瓦片下两角(BL,BR) == 下瓦片上两角(TL,TR)
    return (bool(top & BL) == bool(bottom & TL)) and (bool(top & BR) == bool(bottom & TR))


@pytest.mark.parametrize("style", ["hard", "rounded", "outline"])
@pytest.mark.parametrize("size", [(32, 32), (33, 31), (16, 16)])
def test_seamless_shared_edges_match(style: str, size: tuple[int, int]) -> None:
    """核心无缝性：任意两张共享一条边的瓦片，沿共享边逐像素归属一致。"""
    w, h = size
    masks = [material_mask(i, w, h, style) for i in range(16)]
    for a in range(16):
        for b in range(16):
            if _shares_horizontal_edge(a, b):
                assert np.array_equal(masks[a][:, -1], masks[b][:, 0]), f"H {a}->{b} {style} {size}"
            if _shares_vertical_edge(a, b):
                assert np.array_equal(masks[a][-1, :], masks[b][0, :]), f"V {a}->{b} {style} {size}"
