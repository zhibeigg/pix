"""AI 审核/修正 Pixel Grid JSON。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from pix.api.packy_client import PackyClient, PackyError
from pix.api.vision import _extract_content, _extract_json
from pix.config import AppConfig, require_vl_api_key
from pix.grid.schema import PixelGrid, load_grid, save_grid


GRID_REVIEW_SYSTEM = """你是像素游戏美术工程图审查器。
你收到的是 Pixel Grid JSON：pixels[y][x] 中 -1 表示透明，其它数字引用 palette.id。
请只在必要时微调 JSON，让它更适合作为小尺寸游戏物品图标。
要求：
1. 严格保持同一个 JSON schema，不要输出解释文字。
2. 不要增加超过原 palette 数量的颜色。
3. 保持 canvas 尺寸不变。
4. 优先修复断裂轮廓、孤立噪点、主体过小、无意义杂点、高光/阴影混乱。
5. 如果已经足够好，原样返回 JSON。
"""


def review_pixel_grid(
    cfg: AppConfig,
    grid: PixelGrid,
    *,
    model: str | None = None,
    instruction: str = "",
) -> PixelGrid:
    """调用 VL/LLM 文本模型审核并返回合法 PixelGrid。"""
    api_key = require_vl_api_key(cfg)
    client = PackyClient(
        base_url=cfg.api.base_url,
        api_key=api_key,
        timeout=cfg.api.timeout,
        max_retries=cfg.api.max_retries,
    )
    user_text = (
        "请审核并必要时修正下面的 Pixel Grid JSON。"
        "只返回修正后的 JSON。\n\n"
        f"额外要求：{instruction.strip() or '保持清晰、干净、可用于游戏。'}\n\n"
        f"```json\n{grid.to_json_text()}\n```"
    )
    payload: dict[str, Any] = {
        "model": model or cfg.vision.model,
        "messages": [
            {
                "role": "user",
                "content": f"{GRID_REVIEW_SYSTEM}\n\n{user_text}",
            }
        ],
        "temperature": min(0.4, cfg.vision.temperature),
        "max_tokens": max(cfg.vision.max_tokens, 4096),
    }

    last_raw = ""
    attempts = max(1, int(cfg.vision.retry_on_parse) + 1)
    for _ in range(attempts):
        last_raw = _extract_content(client.post_json("/v1/chat/completions", payload))
        reviewed = _try_parse_grid(last_raw)
        if reviewed is not None:
            return reviewed
        payload["messages"] = [
            {
                "role": "user",
                "content": (
                    f"{GRID_REVIEW_SYSTEM}\n\n上一次返回不是合法 Pixel Grid JSON。"
                    "请严格只返回完整 JSON，不要 Markdown，不要解释。\n\n"
                    f"原始 JSON：\n{grid.to_json_text()}\n\n"
                    f"上一次输出：\n{last_raw[:2000]}"
                ),
            }
        ]
    raise PackyError(f"AI Grid Review 返回无法解析的 JSON：{last_raw[:1500]}")


def review_grid_file(
    cfg: AppConfig,
    json_path: str | Path,
    out_path: str | Path,
    *,
    model: str | None = None,
    instruction: str = "",
) -> PixelGrid:
    grid = load_grid(json_path)
    reviewed = review_pixel_grid(cfg, grid, model=model, instruction=instruction)
    save_grid(reviewed, out_path)
    return reviewed


def _try_parse_grid(raw: str) -> PixelGrid | None:
    try:
        return PixelGrid.model_validate_json(_extract_json(raw))
    except (ValidationError, ValueError):
        return None
