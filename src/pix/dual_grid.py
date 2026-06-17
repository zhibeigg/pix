"""dual-grid 双瓦片纯算法：16 角掩码 → 单瓦片合成 → 4×4 图集 → 应用预览。

零网络、零 I/O。无缝性由「边不变量」构造保证：每条瓦片边只由该边两端两个角 + 中点二分
决定；相邻显示瓦片共享边 → 共享该边两端两个角 → 边逐像素归属一致。rounded 过渡用
双线性角场阈值：沿任一边，场只由该边两端角线性插值 → 阈值点恒在中点，故边规则成立；
内部是曲线 → 圆角。
"""
from __future__ import annotations

import hashlib
from typing import Literal

import numpy as np

# 角位：TL=bit0, TR=bit1, BL=bit2, BR=bit3；A=1, B=0
TL, TR, BL, BR = 1, 2, 4, 8
ATLAS_ROWS = ATLAS_COLS = 4
CONVENTION = "pix-dualgrid-v1"

TransitionStyle = Literal["rounded", "hard", "outline"]


def material_mask(idx: int, w: int, h: int, style: str) -> np.ndarray:
    """返回 (h, w) 的布尔掩码：True = 该像素归材质 A。idx ∈ [0,15] 的角位组合。"""
    sw, sh = max(1, int(w)), max(1, int(h))
    tl, tr, bl, br = (idx & TL) != 0, (idx & TR) != 0, (idx & BL) != 0, (idx & BR) != 0
    if style == "hard":
        mx, my = sw // 2, sh // 2
        m = np.empty((sh, sw), dtype=bool)
        m[:my, :mx] = tl
        m[:my, mx:] = tr
        m[my:, :mx] = bl
        m[my:, mx:] = br
        return m
    # rounded / outline 共用双线性角场（outline 的描边在合成阶段叠加）
    xs = np.linspace(0.0, 1.0, sw) if sw > 1 else np.zeros(1)
    ys = np.linspace(0.0, 1.0, sh) if sh > 1 else np.zeros(1)
    u = xs[None, :]
    v = ys[:, None]
    field = (
        float(tl) * (1 - u) * (1 - v)
        + float(tr) * u * (1 - v)
        + float(bl) * (1 - u) * v
        + float(br) * u * v
    )
    return field >= 0.5


def _a_side_border(mask: np.ndarray) -> np.ndarray:
    """A 区内缘：mask 为 True、且 4 邻域里存在非 A 像素的位置。"""
    non_a = ~mask
    nb = np.zeros_like(mask)
    nb[:-1, :] |= non_a[1:, :]
    nb[1:, :] |= non_a[:-1, :]
    nb[:, :-1] |= non_a[:, 1:]
    nb[:, 1:] |= non_a[:, :-1]
    return mask & nb


def compose_tile(
    mask: np.ndarray,
    mat_a: np.ndarray,
    mat_b: np.ndarray | None,
    style: str,
    outline_rgb: tuple[int, int, int],
) -> np.ndarray:
    """按归属掩码采样材质（本地坐标）合成单瓦片 RGBA。mat_b=None 即透明模式。"""
    h, w = mask.shape
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[mask] = mat_a[mask]
    if mat_b is not None:
        out[~mask] = mat_b[~mask]
    if style == "outline":
        border = _a_side_border(mask)
        out[border, :3] = np.array(outline_rgb, dtype=np.uint8)
        out[border, 3] = 255
    return out


def compose_atlas(
    mat_a: np.ndarray,
    mat_b: np.ndarray | None,
    style: str,
    outline_rgb: tuple[int, int, int],
) -> tuple[np.ndarray, list[np.ndarray], list[dict]]:
    """生成 16 瓦片 + 4×4 图集 + bitmask→cell 映射表。"""
    h, w = mat_a.shape[:2]
    atlas = np.zeros((h * ATLAS_ROWS, w * ATLAS_COLS, 4), dtype=np.uint8)
    tiles: list[np.ndarray] = []
    mapping: list[dict] = []
    for idx in range(16):
        mask = material_mask(idx, w, h, style)
        tile = compose_tile(mask, mat_a, mat_b, style, outline_rgb)
        tiles.append(tile)
        row, col = idx // ATLAS_COLS, idx % ATLAS_COLS
        atlas[row * h:(row + 1) * h, col * w:(col + 1) * w] = tile
        mapping.append({
            "bitmask": idx,
            "row": row,
            "col": col,
            "corners": {"tl": bool(idx & TL), "tr": bool(idx & TR),
                        "bl": bool(idx & BL), "br": bool(idx & BR)},
        })
    return atlas, tiles, mapping


def preview_seed(name: str, material_a: str, material_b: str, style: str) -> int:
    """从参数确定性派生 32-bit 预览种子（同参数同预览，测试稳定）。"""
    raw = f"{name}\n{material_a}\n{material_b}\n{style}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:4], "big")


def render_preview(
    tiles: list[np.ndarray], w: int, h: int, seed: int, cells: int = 8
) -> np.ndarray:
    """随机 cells×cells 世界格 → (cells-1)×(cells-1) 显示瓦片，验证无缝拼接。"""
    rng = np.random.default_rng(int(seed))
    world = rng.integers(0, 2, size=(cells, cells))
    disp = max(1, cells - 1)
    out = np.zeros((disp * h, disp * w, 4), dtype=np.uint8)
    for i in range(disp):
        for j in range(disp):
            idx = (int(world[i, j]) * TL | int(world[i, j + 1]) * TR
                   | int(world[i + 1, j]) * BL | int(world[i + 1, j + 1]) * BR)
            out[i * h:(i + 1) * h, j * w:(j + 1) * w] = tiles[idx]
    return out
