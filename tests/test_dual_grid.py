from __future__ import annotations

import numpy as np
import pytest

from pix.dual_grid import (
    TL,
    TR,
    BL,
    BR,
    compose_atlas,
    compose_tile,
    material_mask,
    preview_seed,
    render_preview,
)


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


def _solid(w: int, h: int, rgba: tuple[int, int, int, int]) -> np.ndarray:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[:, :] = rgba
    return arr


def test_compose_tile_fills_a_and_b() -> None:
    mat_a = _solid(32, 32, (10, 200, 10, 255))
    mat_b = _solid(32, 32, (10, 10, 200, 255))
    mask = material_mask(TL, 32, 32, "hard")
    tile = compose_tile(mask, mat_a, mat_b, "hard", (0, 0, 0))
    assert tuple(tile[0, 0]) == (10, 200, 10, 255)      # TL 象限 = A
    assert tuple(tile[0, 31]) == (10, 10, 200, 255)     # TR 象限 = B


def test_compose_tile_transparent_b() -> None:
    mat_a = _solid(32, 32, (10, 200, 10, 255))
    mask = material_mask(TL, 32, 32, "rounded")
    tile = compose_tile(mask, mat_a, None, "rounded", (0, 0, 0))
    assert tile[~mask, 3].max() == 0          # B 区透明
    assert tile[mask, 3].min() == 255         # A 区不透明


def test_compose_tile_outline_borders_a_side() -> None:
    mat_a = _solid(32, 32, (10, 200, 10, 255))
    mask = material_mask(TL, 32, 32, "outline")
    tile = compose_tile(mask, mat_a, None, "outline", (0, 0, 0))
    # 存在被描边的 A 像素（A 区内缘）
    outlined = np.all(tile[:, :, :3] == (0, 0, 0), axis=2) & (tile[:, :, 3] == 255)
    assert outlined.any()
    # 描边只落在 A 区（mask 为 True 处）
    assert not (outlined & ~mask).any()


def test_compose_atlas_layout_and_mapping() -> None:
    mat_a = _solid(16, 16, (10, 200, 10, 255))
    mat_b = _solid(16, 16, (10, 10, 200, 255))
    atlas, tiles, mapping = compose_atlas(mat_a, mat_b, "hard", (0, 0, 0))
    assert atlas.shape == (64, 64, 4)         # 4×4 × 16
    assert len(tiles) == 16 and len(mapping) == 16
    for idx, entry in enumerate(mapping):
        assert entry["bitmask"] == idx
        r, c = entry["row"], entry["col"]
        assert (r, c) == (idx // 4, idx % 4)
        sub = atlas[r * 16:(r + 1) * 16, c * 16:(c + 1) * 16]
        assert np.array_equal(sub, tiles[idx])


def test_render_preview_size_and_determinism() -> None:
    mat_a = _solid(16, 16, (10, 200, 10, 255))
    mat_b = _solid(16, 16, (10, 10, 200, 255))
    _atlas, tiles, _ = compose_atlas(mat_a, mat_b, "hard", (0, 0, 0))
    seed = preview_seed("草地泥土", "草地", "泥土", "rounded")
    p1 = render_preview(tiles, 16, 16, seed, cells=8)
    p2 = render_preview(tiles, 16, 16, seed, cells=8)
    assert p1.shape == (7 * 16, 7 * 16, 4)   # (cells-1) × tile
    assert np.array_equal(p1, p2)            # 同种子可复现


def test_preview_seed_is_deterministic() -> None:
    assert preview_seed("n", "a", "b", "rounded") == preview_seed("n", "a", "b", "rounded")
    assert preview_seed("n", "a", "b", "rounded") != preview_seed("n", "a", "b", "hard")


def test_render_preview_rejects_too_few_cells() -> None:
    mat_a = _solid(8, 8, (10, 200, 10, 255))
    mat_b = _solid(8, 8, (10, 10, 200, 255))
    _atlas, tiles, _ = compose_atlas(mat_a, mat_b, "hard", (0, 0, 0))
    with pytest.raises(ValueError):
        render_preview(tiles, 8, 8, seed=0, cells=1)
