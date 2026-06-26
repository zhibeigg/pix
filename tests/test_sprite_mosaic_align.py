from __future__ import annotations

import numpy as np
from PIL import Image

from pix.sprite import _paste_content_to_canvas
from pix.sprite_mosaic import _widest_gap_center


def test_widest_gap_center_picks_center_of_widest_run() -> None:
    """窗口内有一窄一宽两条空白柱时，切线落在最宽柱（gutter）的中心。"""
    # 前景=10、空白=0：narrow gap 在 idx 4..5，wide gap 在 idx 9..14。
    window = np.array(
        [10, 10, 10, 10, 0, 0, 10, 10, 10, 0, 0, 0, 0, 0, 0, 10, 10, 10, 10],
        dtype=np.int64,
    )
    center = _widest_gap_center(window, offset=100, fg_threshold=0, ideal=100.0)
    # 最宽段 idx9..14 中心 = (9+14)/2 = 11.5 → +offset 100
    assert center in (111, 112)


def test_widest_gap_center_none_when_no_gutter() -> None:
    """主体填满、窗口内无空白柱时返回 None，交回调用方走前景最少点回退。"""
    window = np.array([5, 6, 7, 8, 9], dtype=np.int64)
    assert _widest_gap_center(window, offset=0, fg_threshold=0, ideal=2.0) is None


def _content_with_arm(arm: bool) -> Image.Image:
    """紧贴主体的帧内容：左侧 10px 满高身体，可选在远右侧伸出一条细手臂。"""
    width = 40 if arm else 10
    arr = np.zeros((20, width, 4), dtype=np.uint8)
    arr[:, 0:10] = (200, 50, 50, 255)  # 身体：满高
    if arm:
        arr[9:11, 36:40] = (200, 50, 50, 255)  # 细手臂：仅 2px 高，远在右侧
    return Image.fromarray(arr, "RGBA")


def _body_center_x(canvas: Image.Image) -> float:
    """画布上「满高列」(身体) 的平均 x —— 用于衡量身体重心落点。"""
    alpha = np.asarray(canvas)[..., 3]
    col_counts = (alpha > 8).sum(axis=0)
    body_cols = np.where(col_counts == col_counts.max())[0]
    return float(body_cols.mean())


def test_paste_centroid_keeps_body_stable_against_extended_limb() -> None:
    """伸出的手臂不应把身体带偏：有/无手臂两帧，身体重心落点应几乎一致。

    旧实现按 bbox 中心居中，带手臂帧 bbox 宽 40 → 身体被推到左侧（~14.5），
    与无手臂帧（~30）相差十几像素 = 播放时横向抖动。质心对齐后两者都贴近画布中心。
    """
    size = (60, 20)
    plain = _paste_content_to_canvas(_content_with_arm(arm=False), size=size, anchor="bottom_center")
    with_arm = _paste_content_to_canvas(_content_with_arm(arm=True), size=size, anchor="bottom_center")

    body_plain = _body_center_x(plain)
    body_arm = _body_center_x(with_arm)
    center = size[0] / 2

    # 旧实现（bbox 居中）下带手臂帧身体重心的落点，用于对照「新法严格更优」。
    old_bbox_body_arm = ((size[0] - 40) // 2) + 4.5  # = 14.5
    assert abs(body_arm - center) < abs(old_bbox_body_arm - center)
    # 无手臂帧身体几乎正中；两帧间横向抖动从旧法的 ~15px 实质降低。
    assert abs(body_plain - center) <= 3
    assert abs(body_plain - body_arm) <= 8
