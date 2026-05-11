"""AI 直接设计 Pixel Grid JSON。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from pix.api.packy_client import PackyClient, PackyError
from pix.api.vision import _extract_content, _extract_json
from pix.config import AppConfig, require_vl_api_key
from pix.grid.readability import evaluate_grid_readability, format_blocking_issues
from pix.grid.schema import PixelGrid
from pix.io_utils import image_to_base64_data_url

AI_GRID_SYSTEM = """你是资深像素游戏美工，正在为低像素游戏资源直接绘制 Pixel Grid JSON。
你必须像美工画 16x16 图标一样思考：先读轮廓，再删细节，最后用少量颜色表达材质。

严格要求：
1. 只输出一个 JSON 对象，不要 Markdown，不要解释。
2. JSON 必须符合 Pix PixelGrid schema：version、canvas、palette、pixels、metadata。
3. canvas.transparent_index 固定使用 -1。
4. palette 不包含透明色；透明像素只在 pixels 字符串中用 . 或 _ 表示。
5. pixels 可以使用字符串矩阵：. 表示透明，0-9A-Z 表示 palette id。
6. palette 颜色数不能超过要求；必须优先包含 outline / shadow / primary / highlight 角色。
7. 低像素下最多表达一个主语 + 一个属性，删除背景、纹理、小裂纹、小光点等噪声。
8. 主体要大、轮廓要清晰，高光要少而集中。
"""


def design_pixel_grid(
    cfg: AppConfig,
    image_path: str | Path,
    *,
    output_size: tuple[int, int] = (16, 16),
    max_colors: int = 8,
    model: str | None = None,
    instruction: str = "",
    retries: int = 1,
) -> PixelGrid:
    """让 VL/LLM 根据参考图直接返回可渲染 PixelGrid。"""
    api_key = require_vl_api_key(cfg)
    client = PackyClient(
        base_url=cfg.api.base_url,
        api_key=api_key,
        timeout=cfg.api.timeout,
        max_retries=cfg.api.max_retries,
    )
    width, height = output_size
    data_url = image_to_base64_data_url(image_path)
    prompt = _design_prompt(width, height, max_colors=max_colors, instruction=instruction)
    payload: dict[str, Any] = {
        "model": model or cfg.vision.model,
        "messages": _build_messages(data_url, prompt),
        "temperature": min(0.35, cfg.vision.temperature),
        "max_tokens": max(cfg.vision.max_tokens, 4096),
    }

    attempts = max(1, int(retries) + 1)
    last_raw = ""
    last_error = ""
    best_grid: PixelGrid | None = None
    for attempt in range(attempts):
        last_raw = _extract_content(client.post_json("/v1/chat/completions", payload))
        try:
            grid = PixelGrid.model_validate_json(_extract_json(last_raw))
        except (ValidationError, ValueError) as exc:
            last_error = f"schema 校验失败：{exc}"
            payload["messages"] = _build_messages(
                data_url,
                _repair_prompt(width, height, max_colors, instruction, last_error, last_raw),
            )
            continue

        report = evaluate_grid_readability(grid, max_colors=max_colors)
        grid.metadata.update({
            "generator": "ai_grid",
            "readability": report.to_dict(),
            "ai_grid": {
                "attempts": attempt + 1,
                "max_attempts": attempts,
                "repaired": attempt > 0,
            },
        })
        if report.ok:
            return grid
        best_grid = grid
        last_error = "可读性阻塞问题：\n" + format_blocking_issues(report)
        if attempt >= attempts - 1:
            break
        payload["messages"] = _build_messages(
            data_url,
            _repair_prompt(width, height, max_colors, instruction, last_error, grid.to_json_text()),
        )

    if best_grid is not None:
        raise PackyError(f"AI Pixel Grid 可读性不达标：{last_error}")
    raise PackyError(f"AI Pixel Grid 返回无法解析：{last_error or last_raw[:1500]}")


def _build_messages(data_url: str, prompt: str) -> list[dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"{AI_GRID_SYSTEM}\n\n{prompt}"},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]


def _design_prompt(width: int, height: int, *, max_colors: int, instruction: str) -> str:
    extra = instruction.strip() or "无额外要求"
    return f"""请把参考图重新设计成 {width}x{height} 的游戏像素图标工程图。

美工取舍：
- 保留一眼可读的大轮廓，不要照抄高清细节。
- 主体 bbox 的短轴至少占画布短边 45%，推荐主体占画布 60%-85%。
- 使用最多 {max_colors} 个可见颜色。
- 使用深色 outline 包住主体，shadow/mid/highlight 表达体积。
- 高光只放在关键边缘，不要铺满。
- 不要背景、不要文字、不要 UI 框。

额外要求：{extra}

输出 JSON 示例结构：
{{
  "version": 1,
  "canvas": {{"width": {width}, "height": {height}, "transparent_index": -1}},
  "palette": [
    {{"id": 0, "hex": "#2A1208", "role": "outline"}},
    {{"id": 1, "hex": "#7A3516", "role": "shadow"}},
    {{"id": 2, "hex": "#C07824", "role": "primary"}},
    {{"id": 3, "hex": "#F0C85A", "role": "highlight"}}
  ],
  "pixels": ["....0000...."],
  "metadata": {{"primary_read": "简短说明", "drop_details": ["细纹理", "背景光效"]}}
}}

注意：pixels 必须正好 {height} 行，每行正好 {width} 个字符。只返回 JSON。"""


def _repair_prompt(
    width: int,
    height: int,
    max_colors: int,
    instruction: str,
    error_detail: str,
    previous_output: str,
) -> str:
    extra = instruction.strip() or "无额外要求"
    return f"""上一次 Pixel Grid 不合格：
{error_detail}

请重新输出完整 JSON，必须满足：
- canvas 为 {width}x{height}，transparent_index=-1。
- palette 不超过 {max_colors} 色，不包含透明色。
- pixels 使用字符串矩阵，. 表示透明，0-9A-Z 引用 palette id。
- 主体更大、更清晰，outline 连续，高光更集中。
- 额外要求：{extra}

上一次输出：
{previous_output[:4000]}

只返回 JSON，不要解释。"""
