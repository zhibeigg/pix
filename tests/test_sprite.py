from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from pix.config import AppConfig
from pix.pixelize.core import PixelizeParams
from pix.sprite import (
    SpritePipelineInput,
    build_sprite_sheet_prompt,
    compose_gif,
    compose_horizontal_sprite_sheet,
    pixelize_sprite_frames,
    run_sprite_pipeline,
    split_sprite_sheet,
)


def _animation_sheet(path: Path) -> Path:
    image = Image.new("RGB", (90, 90), (0, 255, 0))
    draw = ImageDraw.Draw(image)
    colors = [
        (220, 30, 60),
        (230, 80, 40),
        (240, 140, 30),
        (210, 190, 40),
        (80, 180, 70),
        (40, 160, 170),
        (60, 110, 220),
        (130, 80, 220),
        (210, 70, 190),
    ]
    for index, color in enumerate(colors):
        row, col = divmod(index, 3)
        x = col * 30 + 7 + (index % 3)
        y = row * 30 + 8
        draw.rectangle((x, y, x + 12, y + 11), fill=color)
    image.save(path)
    return path


def test_build_sprite_sheet_prompt_uses_3x3_constraints() -> None:
    cfg = AppConfig()
    prompt = build_sprite_sheet_prompt(cfg, "暗黑骑士挥剑", target_size=(64, 64))

    assert "3x3" in prompt
    assert "9" in prompt
    assert "暗黑骑士挥剑" in prompt
    assert "64x64" in prompt
    assert "left-to-right" in prompt


def test_split_pixelize_compose_sprite_outputs(tmp_path: Path) -> None:
    source = _animation_sheet(tmp_path / "sheet.png")
    split = split_sprite_sheet(
        source,
        tmp_path / "raw",
        rows=3,
        cols=3,
        key_color="#00FF00",
        tolerance=8,
    )

    assert len(split.raw_frames) == 9
    assert split.crop_box is not None
    for frame in split.raw_frames:
        with Image.open(frame) as opened:
            rgba = opened.convert("RGBA")
            assert rgba.getpixel((0, 0))[3] == 0
            assert any(pixel[3] > 0 for pixel in rgba.getdata())

    frame_paths, meta = pixelize_sprite_frames(
        split.raw_frames,
        tmp_path / "frames",
        PixelizeParams(output_size=(16, 16), colors=6, dither="none", preview_scale=0),
        shared_palette=True,
    )
    assert len(frame_paths) == 9
    assert meta["shared_palette"] is True
    assert len(meta["shared_palette_colors"]) <= 6

    sheet = compose_horizontal_sprite_sheet(frame_paths, tmp_path / "sprite_sheet.png")
    gif = compose_gif(frame_paths, tmp_path / "sprite.gif", duration_ms=80, loop=0)
    with Image.open(sheet) as opened:
        assert opened.size == (16 * 9, 16)
    with Image.open(gif) as opened:
        assert getattr(opened, "n_frames", 1) == 9


def test_run_sprite_pipeline_with_mocked_generation(tmp_path: Path, monkeypatch) -> None:
    def fake_generate(_cfg, _prompt, dest_path, **_kwargs):
        return _animation_sheet(Path(dest_path))

    monkeypatch.setattr("pix.sprite.generate_image", fake_generate)
    cfg = AppConfig()
    cfg.output.root = str(tmp_path / "outs")
    cfg.cache.enabled = False
    cfg.image_gen.prompt_guard_remote = False
    cfg.sprite.pixel_size = (16, 16)
    cfg.sprite.colors = 6
    inputs = SpritePipelineInput(
        prompt="暗黑骑士挥剑",
        pixelize_params=PixelizeParams(output_size=(16, 16), colors=6, dither="none", preview_scale=0),
        use_cache=False,
        duration_ms=90,
    )

    result = run_sprite_pipeline(cfg, inputs)

    assert result.source_path.exists()
    assert result.pixel_path.exists()
    assert result.preview_path is not None and result.preview_path.exists()
    assert len(result.frame_paths) == 9
    meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
    assert meta["sprite"]["count"] == 9
    assert meta["sprite"]["duration_ms"] == 90
    assert meta["outputs"]["sprite_sheet"] == "04_sprite_sheet.png"
    assert meta["outputs"]["sprite_gif"] == "05_sprite.gif"
