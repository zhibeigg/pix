from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from pix.config import AppConfig
from pix.contact_sheet import apply_candidate_ranking, build_contact_sheet_prompt, split_contact_sheet


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
    assert "#00FF00" in prompt
    assert "暗紫色魔法水晶" in prompt
    assert "16x16" in prompt


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
