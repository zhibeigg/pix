"""dual-grid 双瓦片纯算法：16 角掩码 → 单瓦片合成 → 4×4 图集 → 应用预览。

零网络、零 I/O。无缝性由「边不变量」构造保证：每条瓦片边只由该边两端两个角 + 中点二分
决定；相邻显示瓦片共享边 → 共享该边两端两个角 → 边逐像素归属一致。rounded 过渡用
双线性角场阈值：沿任一边，场只由该边两端角线性插值 → 阈值点恒在中点，故边规则成立；
内部是曲线 → 圆角。
"""
from __future__ import annotations

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
