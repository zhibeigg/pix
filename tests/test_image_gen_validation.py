"""image_gen.validate_size 边界测试。"""

from __future__ import annotations

import pytest

from pix.api.image_gen import validate_size


class TestValidateSize:
    @pytest.mark.parametrize(
        "size",
        [
            "1024x1024",
            "1536x1024",
            "1024x1536",
            "2048x2048",
            "2048x1152",
            "3840x2160",
            "2160x3840",
            "auto",
        ],
    )
    def test_accepts_common_sizes(self, size: str) -> None:
        validate_size(size)  # 不抛异常即通过

    @pytest.mark.parametrize(
        "size, reason",
        [
            ("1x1", "16"),           # 不是 16 的倍数
            ("1024x1023", "16"),     # 高度不是 16 的倍数
            ("4000x4000", "3840"),   # 超最大边
            ("3840x3840", "8294"),   # 总像素超上限
            ("16x16", "655"),        # 总像素少于下限
            ("3840x1024", "比例"),    # ratio > 3
            ("1024x300", "16"),      # 格式匹配但 300 不是 16 倍数
            ("abc", "格式"),          # 不合法字符串
            ("1024", "格式"),         # 缺少 x
            ("1024x1024x1024", "格式"),
        ],
    )
    def test_rejects(self, size: str, reason: str) -> None:
        with pytest.raises(ValueError) as exc:
            validate_size(size)
        assert reason in str(exc.value) or "格式" in str(exc.value)
