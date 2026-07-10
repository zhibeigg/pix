from __future__ import annotations

from pix.pixelize.presets import list_presets, load_preset


def test_builtin_presets_are_packaged_and_loadable() -> None:
    expected = {"gameboy", "modern_pixel", "nes", "pico8"}

    assert expected.issubset(set(list_presets()))
    for name in expected:
        preset = load_preset(name)
        assert preset is not None
        assert preset.name == name


def test_auto_preset_returns_none() -> None:
    assert load_preset("auto") is None
