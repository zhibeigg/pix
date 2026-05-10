"""GUI 共享的 combobox 值 → i18n key 映射。"""

from __future__ import annotations

IMAGE_SIZE_PRESETS: list[str] = ["1024x1024", "1536x1024", "1024x1536"]
PIXEL_SIZE_PRESETS: list[str] = ["16x16", "32x32", "48x48", "64x64", "96x96", "128x128", "256x256"]

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

EDGE_STYLE_VALUES: list[str] = ["hard", "feather", "outline"]
EDGE_STYLE_KEYS: dict[str, str] = {
    "hard": "edge_style_hard",
    "feather": "edge_style_feather",
    "outline": "edge_style_outline",
}

RESAMPLE_VALUES: list[str] = ["smart", "box", "bicubic", "lanczos", "nearest"]
RESAMPLE_KEYS: dict[str, str] = {
    "smart": "resample_smart",
    "box": "resample_box",
    "bicubic": "resample_bicubic",
    "lanczos": "resample_lanczos",
    "nearest": "resample_nearest",
}
