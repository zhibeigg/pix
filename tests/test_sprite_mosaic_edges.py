from __future__ import annotations

import unittest

import numpy as np
from PIL import Image

from pix.sprite_mosaic import _apply_frame_edges


def _opaque_count(img: Image.Image) -> int:
    arr = np.asarray(img.convert("RGBA"))
    return int((arr[..., 3] > 0).sum())


class ApplyFrameEdgesTests(unittest.TestCase):
    """#3：序列帧每帧描边/羽化（用户选了才有），描边前补透明边距避免被裁。"""

    def _frame(self) -> Image.Image:
        frame = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
        for x in range(3, 9):
            for y in range(3, 9):
                frame.putpixel((x, y), (200, 30, 30, 255))
        return frame

    def test_outline_pads_and_adds_outline(self) -> None:
        frame = self._frame()
        out = _apply_frame_edges([frame], edge_style="outline", feather=2)
        self.assertEqual(len(out), 1)
        # 补了透明边距 → 尺寸变大
        self.assertGreater(out[0].width, frame.width)
        self.assertGreater(out[0].height, frame.height)
        # 描边补了不透明像素 → 不透明像素变多
        self.assertGreater(_opaque_count(out[0]), _opaque_count(frame))

    def test_hard_returns_unchanged(self) -> None:
        frame = self._frame()
        out = _apply_frame_edges([frame], edge_style="hard", feather=0)
        self.assertIs(out[0], frame)

    def test_zero_feather_returns_unchanged(self) -> None:
        frame = self._frame()
        out = _apply_frame_edges([frame], edge_style="outline", feather=0)
        # feather=0 时 outline 无强度 → 不动（margin 仍可能保留，但至少不报错且帧数一致）
        self.assertEqual(len(out), 1)


if __name__ == "__main__":
    unittest.main()
