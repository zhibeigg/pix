from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pix.config import load_config
from pix_web.config import WebSettings
from pix_web.models import GenerationJob
from pix_web.pipeline_adapter import (
    RAW_REFERENCE_IMAGE_ALIAS,
    image_to_image_pipeline_input_from_job,
)

USER_PROMPT = "戏台：中式风格，黑白红为主色调"


class ImageToImagePixelPromptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.settings = WebSettings(
            database_url=f"sqlite:///{root / 't.db'}",
            storage_root=root / "outputs",
            queue_backend="database",
            jwt_secret="test",
        )
        self.cfg = load_config()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _job(self, **params) -> GenerationJob:
        params_json: dict = {"pixelize": {"output_size": [128, 128], "colors": 8, "remove_bg": True}}
        params_json.update(params)
        return GenerationJob(
            job_type="image_to_image",
            prompt=USER_PROMPT,
            input_image_path="ref.png",
            params_json=params_json,
        )

    def test_pixelized_image_to_image_wraps_with_asset_pixel_prompt(self) -> None:
        """像素化的参考图微调会复用素材直出的像素风模板 + 参考图 appendix + 图1 约定。"""
        inp = image_to_image_pipeline_input_from_job(self._job(), self.settings, self.cfg)
        self.assertIn("TRUE pixel-art", inp.prompt or "")
        self.assertIn("reference image", inp.prompt or "")
        self.assertIn(RAW_REFERENCE_IMAGE_ALIAS, inp.prompt or "")
        self.assertIn("戏台", inp.prompt or "")
        # prompt guard 仍只审核用户原文，而不是注入后的模板。
        self.assertEqual(inp.prompt_guard_text, USER_PROMPT)

    def test_source_only_image_to_image_keeps_literal_prompt(self) -> None:
        """source_only（原生出大图）不应套像素风模板。"""
        inp = image_to_image_pipeline_input_from_job(self._job(source_only=True), self.settings, self.cfg)
        self.assertEqual(inp.prompt, USER_PROMPT)
        self.assertNotIn("TRUE pixel-art", inp.prompt or "")

    def test_toggle_off_keeps_literal_prompt(self) -> None:
        """关闭开关后回退原始 prompt 直传。"""
        self.cfg.image_gen.image_to_image_pixel_prompt = False
        inp = image_to_image_pipeline_input_from_job(self._job(), self.settings, self.cfg)
        self.assertEqual(inp.prompt, USER_PROMPT)

    def test_image_to_image_defaults_to_item_icon(self) -> None:
        """未携带素材类型时仍按物品图标重绘（默认行为不变）。"""
        inp = image_to_image_pipeline_input_from_job(self._job(), self.settings, self.cfg)
        # 模板签名短语，区别于参考图 appendix 里泛指的“item icons and UI components”
        self.assertIn("game item icon", inp.prompt or "")

    def test_image_to_image_respects_ui_component_asset_kind(self) -> None:
        """复用 UI 组件作品做参考图微调时，应沿用 UI 组件模板而非写死的物品图标。"""
        inp = image_to_image_pipeline_input_from_job(
            self._job(asset={"asset_kind": "ui_component"}), self.settings, self.cfg
        )
        self.assertIn("game UI component", inp.prompt or "")
        self.assertNotIn("game item icon", inp.prompt or "")

    def test_image_to_image_respects_game_logo_asset_kind(self) -> None:
        """复用游戏 Logo 作品时，应沿用 Logo 模板与 Logo 专用参考图说明。"""
        inp = image_to_image_pipeline_input_from_job(
            self._job(asset={"asset_kind": "game_logo"}), self.settings, self.cfg
        )
        self.assertIn("game logo", inp.prompt or "")
        # game_logo 的参考图 appendix 使用 logo 专属措辞，而不是普通素材重绘说明
        self.assertIn("emblem silhouette", inp.prompt or "")


if __name__ == "__main__":
    unittest.main()
