from __future__ import annotations

from PIL import Image

from pix.pixelize.core import next_power_of_two, pad_to_power_of_two


def test_next_power_of_two() -> None:
    assert next_power_of_two(1) == 1
    assert next_power_of_two(60) == 64
    assert next_power_of_two(64) == 64
    assert next_power_of_two(65) == 128
    assert next_power_of_two(158) == 256
    assert next_power_of_two(156) == 256
    assert next_power_of_two(256) == 256
    assert next_power_of_two(300) == 512


def test_pad_no_target_uses_pow2() -> None:
    img = Image.new("RGBA", (158, 156), (255, 0, 0, 255))
    out, size = pad_to_power_of_two(img)
    assert size == (256, 256)
    assert out.size == (256, 256)


def test_pad_centers_content_transparently() -> None:
    img = Image.new("RGBA", (60, 60), (0, 200, 0, 255))
    out, size = pad_to_power_of_two(img, target=(64, 64))
    assert size == (64, 64)
    # 四角应透明，中心应不透明（居中填充）
    arr = out.load()
    assert arr[0, 0][3] == 0
    assert arr[32, 32][3] == 255


def test_pad_target_larger_than_pow2() -> None:
    # 成品 60x60 -> pow2 64；但目标 128 更大，按目标定版
    img = Image.new("RGBA", (60, 60), (0, 0, 200, 255))
    out, size = pad_to_power_of_two(img, target=(128, 128))
    assert size == (128, 128)


def test_pad_non_power_of_two_target_when_content_fits() -> None:
    img = Image.new("RGBA", (20, 20), (180, 20, 20, 255))
    out, size = pad_to_power_of_two(img, target=(24, 24))
    assert size == (24, 24)
    assert out.size == (24, 24)
    arr = out.load()
    assert arr[0, 0][3] == 0
    assert arr[12, 12][3] == 255


def test_pad_content_larger_than_target_uses_pow2() -> None:
    # 成品 158x156（perfectPixel 检测）大于目标 64，不裁内容，填充到 256
    img = Image.new("RGBA", (158, 156), (200, 200, 0, 255))
    out, size = pad_to_power_of_two(img, target=(64, 64))
    assert size == (256, 256)


def test_pad_already_pow2_no_change() -> None:
    img = Image.new("RGBA", (64, 64), (10, 20, 30, 255))
    out, size = pad_to_power_of_two(img, target=(64, 64))
    assert size == (64, 64)
    assert out.size == (64, 64)
