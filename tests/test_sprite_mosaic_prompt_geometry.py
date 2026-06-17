from __future__ import annotations

import unittest

from pix.config import AppConfig
from pix.sprite_mosaic import build_mosaic_prompt


class SpriteMosaicPromptGeometryTests(unittest.TestCase):
    """竖长单元格场景下，mosaic prompt 的几何数字必须自洽（B 方案：自适应帧高）。

    复现 job-1324：请求 64x64、1x8 横排，API 受 3:1 约束被撑成 3072x1024，
    每格 384x1024（比例 1:2.67）。旧 prompt 同时声明「每格 384x1024」+「64x64
    sprite」+「6x6 方块」，三者矛盾（64*6=384≠1024），模型只能瞎猜高度。
    """

    def _tall_prompt(self) -> str:
        cfg = AppConfig()
        return build_mosaic_prompt(
            cfg,
            "聂小倩",
            rows=1,
            cols=8,
            row_prompts=["待机动作"],
            sheet_pixel_size=(512, 64),  # 64*8 x 64*1（像素艺术粒度）
            frame_pixel_size=(64, 64),
            api_size_pixel=(3072, 1024),
            anchor="bottom_center",
            key_color="#FF00FF",
            key_tolerance=48,
            max_colors=24,
            use_reference=False,
        )

    def test_tall_cell_prompt_describes_real_cell_grid(self) -> None:
        prompt = self._tall_prompt()
        # cell_render = 384x1024，upscale = min(384//64, 1024//64) = 6，
        # 因此每格真实可绘像素网格 = (384//6)x(1024//6) = 64x170。
        self.assertIn("384x1024", prompt)  # 单元格渲染尺寸
        self.assertIn("64x170", prompt)  # 单元格像素网格（与 upscale 自洽）

    def test_tall_cell_prompt_drops_contradictory_square_claim(self) -> None:
        prompt = self._tall_prompt()
        # 旧措辞把整格当成 64x64 sprite —— 与 384x1024 单元格矛盾，必须移除。
        self.assertNotIn("64x64 pixel-art sprite", prompt)

    def test_tall_cell_prompt_anchors_and_fills_background(self) -> None:
        prompt = self._tall_prompt()
        lowered = prompt.lower()
        # 自适应帧高的关键：主体按自然比例锚定单元格底部，上方留白填背景键色。
        self.assertIn("bottom", lowered)
        self.assertIn("natural proportions", lowered)

    def test_tall_cell_prompt_keeps_background_hardening(self) -> None:
        prompt = self._tall_prompt()
        # 既有的背景/网格线约束不能被回退。
        self.assertIn("NO gradient", prompt)
        self.assertIn("grid lines", prompt)


if __name__ == "__main__":
    unittest.main()
