from __future__ import annotations

import unittest

from pix.config import ImageGenConfig, SpriteConfig
from pix.contact_sheet import _fallback_prompt
from pix.sprite_mosaic import _fallback_mosaic_prompt

# 候选/序列帧模板也曾用 "grid cell / aligned to the grid / pure solid background" 措辞，
# 缺反渐变/铺满/禁网格线约束，Gemini 同样会画方格纸/渐变背景。锁住修复后的措辞。
VALUES = dict(
    rows=3,
    cols=3,
    count=9,
    description="金币",
    width=64,
    height=64,
    green="#FF00FF",
    key_tolerance=48,
    max_colors=8,
    render_width=1024,
    render_height=1024,
    cell_render_width=341,
    cell_render_height=341,
    frame_width=64,
    frame_height=64,
    upscale=5,
    cell_art_width=68,
    cell_art_height=68,
    anchor_text="bottom center",
    row_block="Row 1: walk cycle",
)


class CandidateSpritePromptBackgroundTests(unittest.TestCase):
    def _formatted(self, template: str) -> str:
        out = template.format(**VALUES)
        # 占位符必须全部被替换，不能留下 { } 破坏后续使用。
        self.assertNotIn("{", out)
        self.assertNotIn("}", out)
        return out

    def test_contact_sheet_template_hardened(self) -> None:
        out = self._formatted(ImageGenConfig().contact_sheet_prompt_template)
        self.assertIn("NO gradient", out)
        self.assertIn("do not draw any visible grid lines", out)
        self.assertNotIn("one square grid cell", out)

    def test_n_sample_template_hardened(self) -> None:
        out = self._formatted(ImageGenConfig().n_sample_prompt_template)
        self.assertIn("NO gradient", out)
        self.assertIn("do not draw any visible grid lines", out)
        self.assertNotIn("one square grid cell", out)

    def test_mosaic_template_hardened(self) -> None:
        out = self._formatted(SpriteConfig().mosaic_prompt_template)
        self.assertIn("NO gradient", out)
        # mosaic 本就禁止画出网格线（rows×cols 是布局语义，不能破坏）。
        self.assertIn("grid lines", out)

    def test_contact_sheet_fallback_hardened(self) -> None:
        out = _fallback_prompt(**VALUES)
        self.assertIn("NO gradient", out)
        self.assertIn("do not draw any visible grid lines", out)

    def test_mosaic_fallback_hardened(self) -> None:
        out = _fallback_mosaic_prompt(**VALUES)
        self.assertIn("NO gradient", out)


if __name__ == "__main__":
    unittest.main()
