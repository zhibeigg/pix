"""游戏素材直出辅助测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pix.asset import (
    AssetSizePolicyError,
    AssetSizeStrategy,
    build_asset_prompt,
    resolve_asset_generation_policy,
    resolve_size_strategy,
    safe_asset_filename,
    validate_asset_image,
)


def test_safe_asset_filename_keeps_chinese_and_removes_invalid_chars() -> None:
    assert safe_asset_filename(' 血气:灵玉* ') == "血气_灵玉"
    assert safe_asset_filename("   ") == "asset"


def test_resolve_asset_generation_policy_blocks_sub16() -> None:
    assert resolve_asset_generation_policy((16, 16)) == "extract"
    assert resolve_asset_generation_policy((32, 32)) == "extract"
    with pytest.raises(AssetSizePolicyError):
        resolve_asset_generation_policy((8, 8))
    with pytest.raises(AssetSizePolicyError):
        resolve_asset_generation_policy((12, 12))
    with pytest.raises(AssetSizePolicyError):
        resolve_asset_generation_policy((16, 8))


def test_resolve_size_strategy_always_extract_with_classic_palette() -> None:
    for size in ((16, 16), (32, 32), (64, 64), (128, 128)):
        strategy = resolve_size_strategy(size)
        assert isinstance(strategy, AssetSizeStrategy)
        assert strategy.grid_mode == "extract"
        assert strategy.palette_mode == "auto"
        assert "classic" in strategy.notes or "经典" in strategy.notes


def test_build_asset_prompt_formats_template() -> None:
    prompt = build_asset_prompt(
        "Icon of {name}, target {width}x{height}.",
        "血气灵玉",
        size=(16, 16),
        extra_prompt="red glow",
    )
    assert "血气灵玉" in prompt
    assert "16x16" in prompt
    assert prompt.endswith("red glow")


def test_validate_asset_image_ok(tmp_path: Path) -> None:
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y in range(4, 12):
        for x in range(4, 12):
            img.putpixel((x, y), (200, 80, 60, 255))
    path = tmp_path / "ok.png"
    img.save(path)

    report = validate_asset_image(path, expected_size=(16, 16), max_colors=4)

    assert report.ok
    assert report.visible_color_count == 1
    assert report.alpha_bbox == (4, 4, 12, 12)


def test_validate_asset_image_reports_errors(tmp_path: Path) -> None:
    img = Image.new("RGB", (32, 16), (255, 0, 0))
    path = tmp_path / "bad.png"
    img.save(path)

    report = validate_asset_image(path, expected_size=(16, 16), max_colors=1)

    assert not report.ok
    codes = {issue.code for issue in report.errors}
    assert "size_mismatch" in codes
    assert "missing_alpha" in codes
    assert "no_transparency" in codes
