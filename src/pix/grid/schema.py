"""Pixel Grid JSON schema。

该 schema 是 pix 的“像素工程图”中间表示：每个 JSON cell 对应最终 PNG 的一个像素，
AI 只能审核/修正结构化 JSON，最终图片由 Python 确定性渲染。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")


def normalize_hex(value: str) -> str:
    """规范化 #RRGGBB 颜色。"""
    v = value.strip()
    if not _HEX_RE.match(v):
        raise ValueError(f"非法 hex 颜色：{value}")
    return "#" + v.lstrip("#").upper()


class PixelGridCanvas(BaseModel):
    width: int = Field(ge=1, le=1024)
    height: int = Field(ge=1, le=1024)
    transparent_index: int = -1


class PixelGridAxes(BaseModel):
    x: list[int] = Field(default_factory=list)
    y: list[int] = Field(default_factory=list)


class PixelGridColor(BaseModel):
    id: int = Field(ge=0, le=255)
    hex: str
    role: Literal["outline", "shadow", "primary", "secondary", "accent", "highlight"] = "primary"
    name: str | None = None

    @field_validator("hex")
    @classmethod
    def _v_hex(cls, value: str) -> str:
        return normalize_hex(value)


class PixelGrid(BaseModel):
    version: int = 1
    canvas: PixelGridCanvas
    axes: PixelGridAxes = Field(default_factory=PixelGridAxes)
    palette: list[PixelGridColor] = Field(default_factory=list)
    pixels: list[list[int]]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_grid(self) -> "PixelGrid":
        width = self.canvas.width
        height = self.canvas.height
        transparent = self.canvas.transparent_index

        if len(self.pixels) != height:
            raise ValueError(f"pixels 行数应为 {height}，实际为 {len(self.pixels)}")
        for idx, row in enumerate(self.pixels):
            if len(row) != width:
                raise ValueError(f"pixels[{idx}] 列数应为 {width}，实际为 {len(row)}")

        ids = [c.id for c in self.palette]
        if len(ids) != len(set(ids)):
            raise ValueError("palette id 不能重复")
        id_set = set(ids)
        for y, row in enumerate(self.pixels):
            for x, value in enumerate(row):
                if value == transparent:
                    continue
                if value not in id_set:
                    raise ValueError(f"pixels[{y}][{x}] 引用了不存在的 palette id：{value}")

        if not self.axes.x:
            self.axes.x = list(range(width))
        if not self.axes.y:
            self.axes.y = list(range(height))
        if len(self.axes.x) != width:
            raise ValueError(f"axes.x 长度应为 {width}，实际为 {len(self.axes.x)}")
        if len(self.axes.y) != height:
            raise ValueError(f"axes.y 长度应为 {height}，实际为 {len(self.axes.y)}")
        return self

    def to_json_text(self, *, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)


def load_grid(path: str | Path) -> PixelGrid:
    return PixelGrid.model_validate_json(Path(path).read_text(encoding="utf-8"))


def save_grid(grid: PixelGrid, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(grid.to_json_text(), encoding="utf-8")
    return p


def grid_from_mapping(data: dict[str, Any]) -> PixelGrid:
    """测试和外部 API 入口使用的显式构造函数。"""
    # json roundtrip 可以避免调用方传入 tuple 等非 JSON 类型后表现不一致。
    return PixelGrid.model_validate_json(json.dumps(data, ensure_ascii=False))
