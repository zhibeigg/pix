from __future__ import annotations

import unittest

from pix.sprite_mosaic import _cell_detect_target_size, _frame_size_report


class CellDetectTargetSizeTests(unittest.TestCase):
    """perfect_pixel 的检测目标应按 API 单元格长宽比走，而非请求的方形。

    job-1324：64x64 的 1x8 被 API ≤3:1 约束撑成 3072x1024，每格 384x1024。
    用方形 64x64 当检测目标必然触发 target_size_mismatch；改用与单元格比例
    一致的期望尺寸，让检测/标注锚定真实形状（perfect_pixel 仍自动检测，输出不变）。
    """

    def test_detect_target_follows_tall_cell_aspect(self) -> None:
        # 每格 384x1024，期望高度 ≈ 64 * 1024 / 384 = 170.67 → 171，宽度恒为请求宽度。
        self.assertEqual(_cell_detect_target_size((64, 64), (3072, 1024), 1, 8), (64, 171))

    def test_detect_target_keeps_square_when_cell_square(self) -> None:
        # 3x3 的 64x64，API 1024x1024 → 每格 ~341x341（≈1:1），高度不放大。
        self.assertEqual(_cell_detect_target_size((64, 64), (1024, 1024), 3, 3), (64, 64))

    def test_detect_target_never_below_requested_height(self) -> None:
        # 宽扁单元格也不应把高度压到请求以下（下限 = 请求高度）。
        self.assertEqual(_cell_detect_target_size((64, 64), (1024, 1024), 1, 1)[1], 64)

    def test_detect_target_falls_back_without_api_size(self) -> None:
        self.assertEqual(_cell_detect_target_size((64, 64), None, 1, 8), (64, 64))


class FrameSizeReportTests(unittest.TestCase):
    """如实标注「请求尺寸 vs 实际交付尺寸」，让 64x64 → 64x128 不再是隐性 mismatch。"""

    def test_marks_adapted_when_delivered_differs(self) -> None:
        report = _frame_size_report((64, 64), (64, 128))
        self.assertTrue(report["frame_size_adapted"])
        self.assertEqual(report["requested_frame_size"], [64, 64])
        self.assertEqual(report["delivered_frame_size"], [64, 128])

    def test_not_adapted_when_delivered_matches(self) -> None:
        report = _frame_size_report((64, 64), (64, 64))
        self.assertFalse(report["frame_size_adapted"])
        self.assertEqual(report["delivered_frame_size"], [64, 64])


if __name__ == "__main__":
    unittest.main()
