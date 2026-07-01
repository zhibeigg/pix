from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from pix.sprite_mosaic import _axis_transition_splits, _key_color_foreground_mask, _split_sheet_to_cells


def _count_col_runs(cell: Image.Image, key_rgb: tuple[int, int, int], tol: int) -> int:
    """统计单格内「水平方向上互相分开的前景块」数量（= 该格里的精灵个数）。"""
    arr = np.asarray(cell.convert("RGBA"))[..., :3]
    fg = _key_color_foreground_mask(arr, key_rgb, tol)
    col_has_fg = fg.any(axis=0)
    runs = 0
    prev = False
    for value in col_has_fg.tolist():
        if value and not prev:
            runs += 1
        prev = value
    return runs


def _make_row_sheet(
    sprite_w: int,
    sprite_h: int,
    gaps: list[int],
    *,
    margin: int = 30,
    height: int = 724,
    key_rgb: tuple[int, int, int] = (255, 0, 255),
) -> Image.Image:
    """画一行 len(gaps)+1 个精灵、精灵间留指定间隙的 mosaic（品红背景）。"""
    count = len(gaps) + 1
    width = margin * 2 + sprite_w * count + sum(gaps)
    image = Image.new("RGBA", (width, height), (*key_rgb, 255))
    draw = ImageDraw.Draw(image)
    top = (height - sprite_h) // 2
    x = margin
    for i in range(count):
        draw.rectangle((x, top, x + sprite_w - 1, top + sprite_h - 1), fill=(16, 16, 16, 255))
        x += sprite_w
        if i < len(gaps):
            x += gaps[i]
    return image


def test_axis_transition_splits_use_gap_between_subject_runs() -> None:
    """切线取「主体结束后的空白」与「下一主体开始」的中值，而不是贴着主体边缘。"""

    projection = np.zeros(80, dtype=np.int64)
    projection[5:25] = 16
    projection[46:70] = 16

    splits = _axis_transition_splits(projection, total=80, segments=2)

    assert splits is not None
    assert splits.tolist() == [0, 36, 80]


def test_split_multi_action_cuts_rows_before_per_row_columns(tmp_path: Path) -> None:
    """多动作 mosaic 先按上下动作组切行，再在每行动作图内独立横向切帧。"""

    key_rgb = (255, 0, 255)
    image = Image.new("RGBA", (360, 180), (*key_rgb, 255))
    draw = ImageDraw.Draw(image)
    for row_top in (20, 110):
        for left in (20, 140, 260):
            draw.rectangle((left, row_top, left + 45, row_top + 39), fill=(16, 16, 16, 255))
    sheet_path = tmp_path / "multi_action.png"
    image.save(sheet_path)

    cells, meta = _split_sheet_to_cells(sheet_path, rows=2, cols=3, key_rgb=key_rgb, key_tolerance=8)

    assert meta["rows"] == 2
    assert meta["cols"] == 3
    assert len(cells) == 6
    assert meta["row_splits"][1] in range(85, 96)
    for row_splits in meta["col_splits_per_row"]:
        assert row_splits[1] in range(90, 111)
        assert row_splits[2] in range(210, 231)


def test_split_preserves_requested_action_rows_when_projection_merges_rows(tmp_path: Path) -> None:
    """动作行数是用户请求的结构，不能被前景投影误降级。"""

    key_rgb = (255, 0, 255)
    image = Image.new("RGBA", (800, 400), (*key_rgb, 255))
    draw = ImageDraw.Draw(image)
    # 前两行动物在垂直投影上几乎连在一起，会让自动行数检测倾向 3 行。
    row_boxes = [
        (30, 20, 760, 185),
        (30, 170, 760, 220),
        (30, 260, 760, 300),
        (30, 350, 760, 390),
    ]
    for top_left_x, top_left_y, bottom_right_x, bottom_right_y in row_boxes:
        for col in range(8):
            left = top_left_x + col * 90
            draw.rectangle((left, top_left_y, min(left + 36, bottom_right_x), bottom_right_y), fill=(16, 16, 16, 255))
    sheet_path = tmp_path / "sprite_mosaic.png"
    image.save(sheet_path)

    cells, meta = _split_sheet_to_cells(sheet_path, rows=4, cols=8, key_rgb=key_rgb, key_tolerance=8)

    assert meta["requested_rows"] == 4
    assert meta["detected_rows"] != 4
    assert meta["rows"] == 4
    assert len(cells) == 32


def test_split_honors_requested_cols_when_one_real_gap_is_narrow(tmp_path: Path) -> None:
    """模型正确画了 8 列、但某条真实间隙偏窄时，不能被误判成 7 列把两个精灵并进一格。

    复现真实 bug：铃铛动画里相邻帧主体靠得近，第 5 条间隙只有 ~30px，旧的「绝对宽度
    阈值」启发式会漏掉这条真实间隙 → 检测成 7 列 → 某一格出现两个铃铛。
    """
    key_rgb = (255, 0, 255)
    gaps = [70, 70, 70, 70, 30, 70, 70]  # 7 条间隙，第 5 条故意很窄
    image = _make_row_sheet(200, 360, gaps, key_rgb=key_rgb)
    sheet_path = tmp_path / "sprite_mosaic.png"
    image.save(sheet_path)

    cells, meta = _split_sheet_to_cells(sheet_path, rows=1, cols=8, key_rgb=key_rgb, key_tolerance=48)

    assert meta["cols"] == 8
    assert len(cells) == 8
    for index, cell in enumerate(cells, start=1):
        blobs = _count_col_runs(cell, key_rgb, 48)
        assert blobs == 1, f"cell{index} 含 {blobs} 个精灵，期望恰好 1 个（不应合并）"


def test_split_falls_back_when_model_draws_fewer_cols(tmp_path: Path) -> None:
    """模型确实少画时（请求 8 列只画了 7 个精灵）回退到检测值，不硬凑 8 列把精灵劈成两半。"""
    key_rgb = (255, 0, 255)
    gaps = [70, 70, 70, 70, 70, 70]  # 6 条间隙 = 7 个精灵
    image = _make_row_sheet(220, 360, gaps, key_rgb=key_rgb)
    sheet_path = tmp_path / "sprite_mosaic.png"
    image.save(sheet_path)

    cells, meta = _split_sheet_to_cells(sheet_path, rows=1, cols=8, key_rgb=key_rgb, key_tolerance=48)

    assert meta["requested_cols"] == 8
    assert meta["cols"] == 7  # 真实间隙不足 → 回退到检测到的 7
    assert len(cells) == 7
    for index, cell in enumerate(cells, start=1):
        blobs = _count_col_runs(cell, key_rgb, 48)
        assert blobs == 1, f"cell{index} 含 {blobs} 个精灵，期望恰好 1 个（不应劈裂）"
