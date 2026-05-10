"""GUI 共享的 combobox 值 → i18n key 映射。"""

from __future__ import annotations

QUALITY_VALUES: list[str] = ["low", "medium", "high", "auto"]
QUALITY_KEYS: dict[str, str] = {
    "low": "quality_low",
    "medium": "quality_medium",
    "high": "quality_high",
    "auto": "quality_auto",
}

DITHER_VALUES: list[str] = ["none", "ordered", "floyd_steinberg"]
DITHER_KEYS: dict[str, str] = {
    "none": "dither_none",
    "ordered": "dither_ordered",
    "floyd_steinberg": "dither_floyd_steinberg",
}

PRESET_KEYS: dict[str, str] = {
    "auto": "preset_auto",
    "gameboy": "preset_gameboy",
    "nes": "preset_nes",
    "modern_pixel": "preset_modern_pixel",
    "pico8": "preset_pico8",
}
