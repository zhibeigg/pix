"""AI Grid 局部修补：让 VL 只重写 readability 警告涉及的像素。

与 `design_pixel_grid`（整图重画）的区别：
- 输入：当前 draft PixelGrid + readability 报告
- VL 只返回 patch 列表 [{"xy":[x,y], "value": palette_id}]，不会改 palette
- Python 把 patch 合并回 draft，返回新 PixelGrid

适合可读性只有 warning（孤立像素、高光过多、bbox 偏小等）的场景。
严重 blocking 仍然走整图重画。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from pix.api.packy_client import PackyClient, PackyError
from pix.api.vision import _extract_content, _extract_json
from pix.config import AppConfig, require_vl_api_key
from pix.grid.readability import GridReadabilityReport, evaluate_grid_readability
from pix.grid.schema import PixelGrid
from pix.io_utils import image_to_base64_data_url


REPAIR_SYSTEM_PROMPT = """你是像素画修补师。给定一张 PixelGrid 工程图和它的可读性诊断，
你的任务是只对诊断指出的问题区域做最小修改：
- 删孤立像素：把被指为 isolated 的像素改成相邻主色或透明
- 减少高光：把过多的 highlight 像素改回 mid 或 shadow
- 边缘修复：把超出画布或紧贴边缘的像素改为透明留白
- 不要改 palette；不要重画整张图；只输出需要变更的格子

返回 JSON：{"patches":[{"xy":[x,y],"value":palette_id_or_-1}]}
- xy 必须在画布范围内
- value 是 palette 内已有的 id；用 -1 表示透明
- 修补总数 ≤ canvas_pixels * 0.25，否则视为整图重画请求
- 不要加任何解释文字
"""


class _Patch(BaseModel):
    xy: list[int] = Field(min_length=2, max_length=2)
    value: int


class _PatchPayload(BaseModel):
    patches: list[_Patch] = Field(default_factory=list)


class GridRepairError(RuntimeError):
    """局部修补失败。"""


def build_repair_mask(report: GridReadabilityReport) -> dict[str, Any]:
    """把 readability 警告映射成 VL 可读的"诊断要点"。"""
    return {
        "ok": report.ok,
        "blocking": [issue.__dict__ for issue in report.blocking],
        "warnings": [issue.__dict__ for issue in report.warnings],
        "color_count": report.color_count,
        "isolated_pixels": report.isolated_pixels,
        "highlight_ratio": report.highlight_ratio,
        "outline_ratio": report.outline_ratio,
        "bbox_coverage": report.bbox_coverage,
    }


def _grid_string_pixels(grid: PixelGrid) -> list[str]:
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    transparent = grid.canvas.transparent_index
    out: list[str] = []
    for row in grid.pixels:
        line = []
        for value in row:
            if value == transparent:
                line.append(".")
            elif 0 <= value < len(chars):
                line.append(chars[value])
            else:
                line.append("?")
        out.append("".join(line))
    return out


def repair_pixel_grid(
    cfg: AppConfig,
    grid: PixelGrid,
    report: GridReadabilityReport,
    *,
    image_path: str | Path,
    model: str | None = None,
    max_patches_ratio: float = 0.25,
) -> PixelGrid:
    """让 VL 输出 patches 修补 draft；返回合并后的新 PixelGrid。"""
    api_key = require_vl_api_key(cfg)
    client = PackyClient(
        base_url=cfg.api.base_url,
        api_key=api_key,
        timeout=cfg.api.timeout,
        max_retries=cfg.api.max_retries,
    )
    width = grid.canvas.width
    height = grid.canvas.height
    palette_ids = sorted({c.id for c in grid.palette})
    diagnostic = build_repair_mask(report)
    string_pixels = _grid_string_pixels(grid)

    user_prompt = f"""画布：{width}x{height}（transparent_index={grid.canvas.transparent_index}）。
palette 可用 id：{palette_ids}
当前 pixels（每行一个字符串，'.' 表示透明）：
{json.dumps(string_pixels, ensure_ascii=False)}

诊断报告：
{json.dumps(diagnostic, ensure_ascii=False)}

只返回 JSON：{{"patches":[{{"xy":[x,y],"value":palette_id_or_-1}}]}}
"""
    data_url = image_to_base64_data_url(image_path)
    payload: dict[str, Any] = {
        "model": model or cfg.vision.model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{REPAIR_SYSTEM_PROMPT}\n\n{user_prompt}"},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "temperature": min(0.25, cfg.vision.temperature),
        "max_tokens": max(cfg.vision.max_tokens, 1024),
    }
    raw = _extract_content(client.post_json("/v1/chat/completions", payload))
    try:
        data = json.loads(_extract_json(raw))
        parsed = _PatchPayload.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise GridRepairError(f"VL 修补返回无法解析：{exc}") from exc

    canvas_pixels = max(1, width * height)
    if len(parsed.patches) > canvas_pixels * max_patches_ratio:
        raise GridRepairError(
            f"修补量 {len(parsed.patches)} 超过画布 {max_patches_ratio:.0%}，应当走整图重画"
        )

    new_pixels = [list(row) for row in grid.pixels]
    palette_id_set = set(palette_ids)
    transparent = grid.canvas.transparent_index
    applied = 0
    for patch in parsed.patches:
        x, y = patch.xy
        if not (0 <= x < width and 0 <= y < height):
            continue
        if patch.value != transparent and patch.value not in palette_id_set:
            continue
        new_pixels[y][x] = int(patch.value)
        applied += 1

    new_grid = grid.model_copy(deep=True)
    new_grid.pixels = new_pixels
    metadata = dict(new_grid.metadata)
    metadata.setdefault("ai_grid", {})
    metadata["ai_grid"] = {
        **metadata.get("ai_grid", {}),
        "repair": {
            "applied_patches": applied,
            "total_patches": len(parsed.patches),
            "max_ratio": max_patches_ratio,
        },
    }
    new_grid.metadata = metadata
    return new_grid


def repair_or_passthrough(
    cfg: AppConfig,
    grid: PixelGrid,
    *,
    image_path: str | Path,
    model: str | None = None,
    max_colors: int,
    repair_mode: str = "auto",
) -> tuple[PixelGrid, dict[str, Any]]:
    """根据 readability 自动决定是否调用 VL 修补。

    repair_mode:
        off  —— 不修补
        auto —— 没 blocking 也没 warning 时跳过；只有 warning 时调修补；blocking 时让上层走整图
        force —— 强制修补
    """
    info: dict[str, Any] = {"mode": repair_mode, "applied": False, "reason": None, "error": None}
    if repair_mode == "off":
        info["reason"] = "off"
        return grid, info

    report = evaluate_grid_readability(grid, max_colors=max_colors)
    if repair_mode == "auto":
        if not report.warnings and report.ok:
            info["reason"] = "no_issues"
            return grid, info
        if report.blocking:
            info["reason"] = "has_blocking_skip_repair"
            return grid, info

    try:
        repaired = repair_pixel_grid(cfg, grid, report, image_path=image_path, model=model)
    except (GridRepairError, PackyError) as exc:
        info["error"] = str(exc)
        info["reason"] = "repair_failed"
        return grid, info

    after = evaluate_grid_readability(repaired, max_colors=max_colors)
    info["applied"] = True
    info["before"] = {"warnings": len(report.warnings), "blocking": len(report.blocking)}
    info["after"] = {"warnings": len(after.warnings), "blocking": len(after.blocking)}
    info["reason"] = "repaired"
    return repaired, info
