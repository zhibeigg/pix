"""PixAnalysis Pydantic schema。"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")


def _normalize_hex(v: str) -> str:
    v = v.strip()
    if not _HEX_RE.match(v):
        raise ValueError(f"非法 hex 颜色：{v}")
    return ("#" + v.lstrip("#")).upper()


class ColorSwatch(BaseModel):
    hex: str
    weight: float = Field(ge=0.0, le=1.0)
    role: Literal[
        "primary", "secondary", "accent", "shadow", "highlight", "background"
    ] = "primary"
    name: str | None = None

    @field_validator("hex")
    @classmethod
    def _v_hex(cls, v: str) -> str:
        return _normalize_hex(v)


class BBoxNorm(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    w: float = Field(gt=0.0, le=1.0)
    h: float = Field(gt=0.0, le=1.0)


class ROI(BaseModel):
    label: str
    bbox_norm: BBoxNorm
    importance: float = Field(ge=0.0, le=1.0, default=0.5)
    sharpness_hint: Literal["sharp", "smooth"] = "sharp"


class SemanticRegion(BaseModel):
    label: str
    bbox_norm: BBoxNorm
    palette_hint: list[str] = Field(default_factory=list)

    @field_validator("palette_hint")
    @classmethod
    def _v_palette(cls, v: list[str]) -> list[str]:
        return [_normalize_hex(x) for x in v]


class StyleAnalysis(BaseModel):
    style_tags: list[str] = Field(default_factory=list)
    recommended_preset: Literal[
        "auto", "gameboy", "nes", "modern_pixel", "pico8"
    ] = "auto"
    target_color_count: int = Field(ge=2, le=256, default=16)
    suggested_dither: Literal["none", "ordered", "floyd_steinberg"] = "floyd_steinberg"
    contrast_level: Literal["low", "mid", "high"] = "mid"
    notes: str | None = None


class PixAnalysis(BaseModel):
    description: str
    style: StyleAnalysis
    palette: list[ColorSwatch] = Field(default_factory=list)
    main_subjects: list[ROI] = Field(default_factory=list)
    semantic_regions: list[SemanticRegion] = Field(default_factory=list)


# JSON Schema（用于注入 VL prompt）
SCHEMA_HINT = """{
  "description": "一句话描述画面内容",
  "style": {
    "style_tags": ["cyberpunk", "chibi"],
    "recommended_preset": "auto | gameboy | nes | modern_pixel | pico8",
    "target_color_count": 16,
    "suggested_dither": "none | ordered | floyd_steinberg",
    "contrast_level": "low | mid | high",
    "notes": "可选备注"
  },
  "palette": [
    {
      "hex": "#RRGGBB",
      "weight": 0.25,
      "role": "primary | secondary | accent | shadow | highlight | background",
      "name": "可选中文名"
    }
  ],
  "main_subjects": [
    {
      "label": "主体名",
      "bbox_norm": {"x": 0.1, "y": 0.2, "w": 0.6, "h": 0.6},
      "importance": 0.9,
      "sharpness_hint": "sharp | smooth"
    }
  ],
  "semantic_regions": [
    {
      "label": "sky | grass | character_skin | ...",
      "bbox_norm": {"x": 0, "y": 0, "w": 1, "h": 0.4},
      "palette_hint": ["#88CCEE", "#BBDDFF"]
    }
  ]
}"""
