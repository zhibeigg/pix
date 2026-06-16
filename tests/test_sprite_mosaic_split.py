from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from pix.sprite_mosaic import _split_sheet_to_cells


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
