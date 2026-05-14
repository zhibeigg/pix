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


def test_resolve_asset_generation_policy_blocks_sub16_except_8x8() -> None:
    assert resolve_asset_generation_policy((8, 8)) == "ai_grid_required"
    assert resolve_asset_generation_policy((16, 16)) == "extract"
    with pytest.raises(AssetSizePolicyError):
        resolve_asset_generation_policy((12, 12))
    with pytest.raises(AssetSizePolicyError):
        resolve_asset_generation_policy((16, 8))


def test_resolve_size_strategy_per_size() -> None:
    s8 = resolve_size_strategy((8, 8))
    # 8x8 沿用 AI Grid 直绘（硬约束在 resolve_asset_generation_policy / web jobs 处）
    assert s8.grid_mode == "ai" and s8.ai_grid is True and s8.repair_mode == "force"
    s16 = resolve_size_strategy((16, 16))
    # 16x16 实测 extract 路线效果最稳（A/B vs C/D 对比）
    assert s16.grid_mode == "extract" and s16.ai_grid is False and s16.repair_mode == "auto"
    s32 = resolve_size_strategy((32, 32))
    assert s32.grid_mode == "extract" and s32.ai_grid is False and s32.repair_mode == "auto"
    s64 = resolve_size_strategy((64, 64))
    assert s64.grid_mode == "off" and s64.repair_mode == "off"
    # 全部启用 ramp
    for s in (s8, s16, s32, s64):
        assert s.palette_mode == "ramp"
    assert isinstance(s8, AssetSizeStrategy)
    assert "8x8" in s8.notes


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
