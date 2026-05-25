from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from pix.config import AppConfig
from pix.contact_sheet import (
    apply_candidate_ranking,
    build_contact_sheet_prompt,
    build_sample_prompt,
    candidate_count,
    candidate_mode,
    collect_independent_candidates,
    resolve_key_color,
    split_contact_sheet,
)


def _sheet(path: Path) -> Path:
    image = Image.new("RGB", (90, 90), (0, 255, 0))
    draw = ImageDraw.Draw(image)
    colors = [
        (255, 0, 0),
        (0, 0, 255),
        (255, 255, 0),
        (255, 0, 255),
        (0, 255, 255),
        (128, 64, 32),
        (255, 128, 0),
        (64, 64, 64),
        (255, 255, 255),
    ]
    for index, color in enumerate(colors):
        row, col = divmod(index, 3)
        x = col * 30 + 9
        y = row * 30 + 9
        draw.rectangle((x, y, x + 11, y + 11), fill=color)
    image.save(path)
    return path


def test_build_contact_sheet_prompt_uses_server_constraints() -> None:
    cfg = AppConfig()
    prompt = build_contact_sheet_prompt(cfg, "暗紫色魔法水晶", target_size=(16, 16))

    assert "3x3" in prompt
    assert "#FF0000" in prompt
    assert "TRUE perler bead pixel pattern" in prompt
    assert "maximum key-color tolerance (48 RGB Euclidean distance)" in prompt
    assert "暗紫色魔法水晶" in prompt
    assert "exactly 16x16 pixels" in prompt


def test_resolve_key_color_avoids_prompt_color_conflicts() -> None:
    hex_value, rgb = resolve_key_color("auto", "jade green forest toxic leaf item")

    assert hex_value != "#00FF00"
    assert rgb != (0, 255, 0)


def test_resolve_key_color_understands_chinese_conflicts() -> None:
    hex_value, _rgb = resolve_key_color("auto", "紫色水晶与粉色玫瑰")

    assert hex_value == "#FF0000"


def test_resolve_key_color_uses_red_for_purple_cyan_gold_jade_prompt() -> None:
    hex_value, _rgb = resolve_key_color("auto", "cyan purple gold jade cultivation items")

    assert hex_value == "#FF0000"


def test_split_contact_sheet_removes_green_screen(tmp_path: Path) -> None:
    src = _sheet(tmp_path / "sheet.png")
    result = split_contact_sheet(
        src,
        tmp_path / "candidates",
        rows=3,
        cols=3,
        green_screen_color="#00FF00",
        tolerance=8,
    )

    assert len(result.candidates) == 9
    first = result.candidates[0].path
    with Image.open(first) as opened:
        rgba = opened.convert("RGBA")
        assert rgba.getpixel((0, 0))[3] == 0
        assert any(pixel[3] > 0 for pixel in rgba.getdata())


def test_apply_candidate_ranking_sorts_and_marks_selected(tmp_path: Path) -> None:
    result = split_contact_sheet(
        _sheet(tmp_path / "sheet.png"),
        tmp_path / "candidates",
        rows=3,
        cols=3,
        green_screen_color="#00FF00",
        tolerance=8,
    )

    ranked = apply_candidate_ranking(result, [
        {"index": 5, "rank": 1, "score": 93, "reason": "最好"},
        {"index": 2, "rank": 2, "score": 80, "reason": "次好"},
    ])
    meta = ranked.to_metadata(tmp_path, enabled=True, effective_prompt="effective", user_prompt="user")

    assert ranked.selected.index == 5
    assert meta["selected_index"] == 5
    assert meta["candidates"][0]["index"] == 5
    assert meta["candidates"][0]["selected"] is True
    assert meta["candidates"][0]["score"] == 93


def _single_sample(path: Path, color: tuple[int, int, int]) -> Path:
    img = Image.new("RGB", (40, 40), (0, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle((8, 8, 32, 32), fill=color)
    img.save(path)
    return path


def test_candidate_mode_defaults_to_n_sample() -> None:
    cfg = AppConfig()
    assert candidate_mode(cfg) == "n_sample"
    assert candidate_count(cfg) == 4


def test_candidate_mode_falls_back_to_contact_sheet_with_count() -> None:
    cfg = AppConfig()
    cfg.image_gen.candidate_mode = "contact_sheet"
    cfg.image_gen.contact_sheet_rows = 2
    cfg.image_gen.contact_sheet_cols = 3
    assert candidate_mode(cfg) == "contact_sheet"
    assert candidate_count(cfg) == 6


def test_build_sample_prompt_no_rows_cols() -> None:
    cfg = AppConfig()
    prompt = build_sample_prompt(cfg, "魔法水晶", target_size=(16, 16))
    assert "魔法水晶" in prompt
    assert "TRUE perler bead pixel pattern" in prompt
    assert "maximum key-color tolerance (48 RGB Euclidean distance)" in prompt
    # 不能再出现 sheet/rows 用法
    assert "{rows}" not in prompt
    assert "contact sheet" not in prompt.lower()
    assert "exactly 16x16 pixels" in prompt


def test_collect_independent_candidates(tmp_path: Path) -> None:
    paths = [
        _single_sample(tmp_path / "s1.png", (255, 0, 0)),
        _single_sample(tmp_path / "s2.png", (0, 0, 255)),
        _single_sample(tmp_path / "s3.png", (255, 255, 0)),
    ]
    result = collect_independent_candidates(
        paths,
        tmp_path / "candidates",
        green_screen_color="#00FF00",
        tolerance=8,
    )
    assert len(result.candidates) == 3
    for cand in result.candidates:
        with Image.open(cand.path) as opened:
            rgba = opened.convert("RGBA")
            assert rgba.getpixel((0, 0))[3] == 0
            assert any(pixel[3] > 0 for pixel in rgba.getdata())
