"""预设加载。"""

from __future__ import annotations

from pix.pixelize.presets import list_presets, load_preset


def test_list_presets_contains_builtin() -> None:
    names = set(list_presets())
    assert {"auto", "gameboy", "nes", "modern_pixel", "pico8"}.issubset(names)


def test_auto_returns_none() -> None:
    assert load_preset("auto") is None
    assert load_preset("") is None


def test_unknown_returns_none() -> None:
    assert load_preset("does-not-exist") is None


def test_gameboy_loaded_correctly() -> None:
    p = load_preset("gameboy")
    assert p is not None
    assert p.name == "gameboy"
    assert p.output_size == (160, 144)
    assert p.colors == 4
    assert p.dither == "floyd_steinberg"
    assert p.palette_lock == ["#0f380f", "#306230", "#8bac0f", "#9bbc0f"]


def test_pico8_loaded_correctly() -> None:
    p = load_preset("pico8")
    assert p is not None
    assert p.output_size == (128, 128)
    assert p.colors == 16
    assert len(p.palette_lock) == 16
    assert p.dither == "none"


def test_nes_loaded_correctly() -> None:
    p = load_preset("nes")
    assert p is not None
    assert p.output_size == (256, 240)
    assert p.palette_lock == []


def test_modern_pixel_loaded_correctly() -> None:
    p = load_preset("modern_pixel")
    assert p is not None
    assert p.colors == 32
    assert 1.0 <= p.saturation <= 1.2  # type: ignore[operator]
