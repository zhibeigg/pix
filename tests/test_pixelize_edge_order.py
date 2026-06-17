from __future__ import annotations

import unittest

from PIL import Image

from pix.pixelize.core import PixelizeParams, pixelize, _edge_reserve_margin


class EdgeReserveMarginTests(unittest.TestCase):
    """描边/羽化需要在标准尺寸内预留边距，否则描边向外扩会超界被裁（#5）。"""

    def test_outline_reserves_margin_above_feather(self) -> None:
        # 描边向外膨胀 feather 层、且最外圈被跳过，至少留 feather+1。
        self.assertEqual(_edge_reserve_margin("outline", 2), 3)

    def test_outline_reserves_at_least_one(self) -> None:
        self.assertEqual(_edge_reserve_margin("outline", 0), 2)

    def test_feather_reserves_feather_width(self) -> None:
        self.assertEqual(_edge_reserve_margin("feather", 2), 2)

    def test_hard_reserves_nothing(self) -> None:
        self.assertEqual(_edge_reserve_margin("hard", 5), 0)


class PixelizeEdgeOrderTests(unittest.TestCase):
    """#5+#6：单道抠图（早期）+ 描边单独放量化后 + 最后定版标准尺寸、描边不被裁。"""

    def _frame_filling_subject(self) -> Image.Image:
        # 洋红背景（四角=背景，便于抠图）+ 几乎填满的红色主体。
        img = Image.new("RGBA", (96, 96), (255, 0, 255, 255))
        for x in range(3, 93):
            for y in range(3, 93):
                img.putpixel((x, y), (200, 30, 30, 255))
        return img

    def _params(self, **over) -> PixelizeParams:
        base = dict(
            output_size=(64, 64),
            colors=4,
            dither="none",
            preset="auto",
            preview_scale=0,
            resample="nearest",
            snap_to_grid=False,
            remove_bg=True,
            bg_feather=2,
            edge_style="outline",
            auto_crop=True,
            palette_mode="kmeans",
        )
        base.update(over)
        return PixelizeParams(**base)

    def test_single_bg_pass_recorded(self) -> None:
        out, _, meta = pixelize(self._frame_filling_subject(), self._params())
        self.assertEqual(meta["bg_removal_passes"], 1)

    def test_outline_margin_reserved(self) -> None:
        out, _, meta = pixelize(self._frame_filling_subject(), self._params())
        self.assertGreater(meta["edge_margin"], 0)

    def test_outline_not_clipped_border_transparent(self) -> None:
        out, _, _ = pixelize(self._frame_filling_subject(), self._params())
        self.assertEqual(out.size, (64, 64))
        alpha = out.convert("RGBA").getchannel("A")
        w, h = out.size
        # 最外圈应全透明 —— 主体已内缩、描边落在预留边距内，没有顶边被裁。
        border = (
            [alpha.getpixel((x, 0)) for x in range(w)]
            + [alpha.getpixel((x, h - 1)) for x in range(w)]
            + [alpha.getpixel((0, y)) for y in range(h)]
            + [alpha.getpixel((w - 1, y)) for y in range(h)]
        )
        self.assertEqual(max(border), 0)

    def test_hard_edge_no_margin(self) -> None:
        out, _, meta = pixelize(self._frame_filling_subject(), self._params(edge_style="hard", bg_feather=0))
        self.assertEqual(meta["edge_margin"], 0)


if __name__ == "__main__":
    unittest.main()
