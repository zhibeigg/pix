from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

import pix.api.image_gen as ig
from pix.api.image_gen import (
    SizeRetryConfig,
    build_size_directive,
    edit_image,
    generate_image,
    generate_images_batch,
)
from pix.config import AppConfig


# ---------- build_size_directive 文案 ----------

class BuildSizeDirectiveTests(unittest.TestCase):
    def test_base_square(self) -> None:
        d = build_size_directive((1024, 1024))
        assert "1024x1024" in d
        assert "aspect ratio 1:1" in d
        assert "square" in d
        assert "[OUTPUT SIZE]" in d
        # 负面约束
        assert "padding" in d and "letterbox" in d and "crop" in d
        # 基础版不含 retry 前缀
        assert "RETRY" not in d

    def test_base_landscape_ratio_simplified(self) -> None:
        d = build_size_directive((1536, 1024))
        assert "1536x1024" in d
        assert "aspect ratio 3:2" in d          # 化简
        assert "landscape" in d

    def test_base_portrait(self) -> None:
        d = build_size_directive((1024, 1536))
        assert "portrait" in d
        assert "aspect ratio 2:3" in d

    def test_retry_attempt_2_includes_wrong_size(self) -> None:
        d = build_size_directive((1024, 1024), attempt=2, last_wrong=(1536, 1024))
        assert "[STRICT RETRY]" in d
        assert "1536x1024" in d                 # 上次错误尺寸
        assert "1024x1024" in d
        # 升级版仍包含基础版
        assert "[OUTPUT SIZE]" in d

    def test_retry_attempt_3_is_critical_uppercase(self) -> None:
        d = build_size_directive((1024, 1024), attempt=3, last_wrong=(2048, 1024))
        assert "[CRITICAL SIZE RETRY #3]" in d
        assert "DISCARDED" in d
        assert "2048x1024" in d

    def test_attempt_2_without_last_wrong_is_base_only(self) -> None:
        # 没有 last_wrong（如 batch 路径）即使 attempt>=2 也只返回基础版
        d = build_size_directive((1024, 1024), attempt=2, last_wrong=None)
        assert "RETRY" not in d
        assert "[OUTPUT SIZE]" in d


# ---------- 注入：generate_image / edit_image ----------

class _FakeImage:
    def __init__(self, protocol: str) -> None:
        self.url = None
        self.b64_json = None
        self.protocol = protocol


class _FakeDispatch:
    def __init__(self, protocol: str) -> None:
        self.image = _FakeImage(protocol)


class SizeDirectiveInjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = AppConfig()
        self.tmpdir = Path(tempfile.mkdtemp())
        self.prompts: list[str] = []
        self.calls = 0

    def _patch(self, sizes: list[tuple[int, int]], protocol: str = "openai_images"):
        def fake_write(entry, dest, **kw):
            idx = min(self.calls, len(sizes) - 1)
            w, h = sizes[idx]
            self.calls += 1
            Image.new("RGB", (w, h), (1, 2, 3)).save(dest)
            return Path(dest)

        def fake_dispatch(cfg, *, prompt, **kw):
            self.prompts.append(prompt)
            return _FakeDispatch(protocol)

        return (
            mock.patch.object(ig, "dispatch_image_request", fake_dispatch),
            mock.patch.object(ig, "_write_entry", fake_write),
        )

    def test_generate_injects_directive(self) -> None:
        p_disp, p_write = self._patch([(1024, 1024)])
        with p_disp, p_write:
            generate_image(self.cfg, "a cat", self.tmpdir / "a.png", size="1024x1024")
        assert len(self.prompts) == 1
        assert "a cat" in self.prompts[0]
        assert "[OUTPUT SIZE]" in self.prompts[0]
        assert "1024x1024" in self.prompts[0]

    def test_auto_size_not_injected(self) -> None:
        p_disp, p_write = self._patch([(1024, 1024)])
        with p_disp, p_write:
            generate_image(self.cfg, "a cat", self.tmpdir / "b.png", size="auto")
        assert self.prompts[0] == "a cat"       # 原样，无注入

    def test_disabled_flag_skips_injection(self) -> None:
        self.cfg.image_gen.size_directive_enabled = False
        p_disp, p_write = self._patch([(1024, 1024)])
        with p_disp, p_write:
            generate_image(self.cfg, "a cat", self.tmpdir / "c.png", size="1024x1024")
        assert self.prompts[0] == "a cat"

    def test_retry_escalates_with_last_wrong(self) -> None:
        # 第一次出 1536x1024（错），第二次 1024x1024（对）；第二次 prompt 应含上次错误尺寸
        p_disp, p_write = self._patch([(1536, 1024), (1024, 1024)])
        retry = SizeRetryConfig(enabled=True, max_attempts=3, expected_size=(1024, 1024))
        with p_disp, p_write:
            generate_image(self.cfg, "a cat", self.tmpdir / "d.png", size="1024x1024", size_retry=retry)
        assert len(self.prompts) == 2
        assert "RETRY" not in self.prompts[0]            # 第一次基础版
        assert "[STRICT RETRY]" in self.prompts[1]       # 第二次升级
        assert "1536x1024" in self.prompts[1]            # 含上次错误尺寸

    def test_edit_injects_directive(self) -> None:
        src = self.tmpdir / "src.png"
        Image.new("RGB", (1024, 1024), (9, 9, 9)).save(src)
        p_disp, p_write = self._patch([(1024, 1024)])
        with p_disp, p_write:
            edit_image(self.cfg, src, "redraw", self.tmpdir / "e.png", size="1024x1024")
        assert "[OUTPUT SIZE]" in self.prompts[0]

    def test_batch_injects_base_only(self) -> None:
        p_disp, p_write = self._patch([(1024, 1024)])
        with p_disp, p_write:
            generate_images_batch(self.cfg, "a cat", self.tmpdir, n=2, size="1024x1024")
        assert len(self.prompts) == 2
        for p in self.prompts:
            assert "[OUTPUT SIZE]" in p
            assert "RETRY" not in p              # batch 不逐次升级


# ---------- asset 场景：双尺寸措辞正交 ----------

class AssetDualSizeTests(unittest.TestCase):
    def test_asset_prompt_plus_directive_orthogonal(self) -> None:
        # 素材直出 prompt 含像素网格尺寸（32x32），注入指令用「output image file resolution」（1024x1024）
        from pix.asset import build_asset_prompt

        asset_prompt = build_asset_prompt("", "frost", size=(32, 32))
        assert "32x32" in asset_prompt
        directive = build_size_directive((1024, 1024))
        combined = f"{asset_prompt}\n\n{directive}"
        # 两个尺寸都在，且分属不同措辞，不会是同一句
        assert "32x32" in combined and "1024x1024" in combined
        assert "output image file resolution" in directive.lower()
        # 注入指令不使用 "canvas" 字样（避免与素材 prompt 的 canvas 冲突）
        assert "canvas" not in directive.lower()


if __name__ == "__main__":
    unittest.main()
