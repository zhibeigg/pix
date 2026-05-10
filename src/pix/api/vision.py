"""多模态视觉分析：通过 Packy /v1/chat/completions 调 Claude/Gemini/gpt-4o。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from pix.analysis.prompts import SYSTEM_PROMPT, USER_PROMPT, repair_prompt
from pix.analysis.schema import PixAnalysis
from pix.api.packy_client import PackyClient, PackyError
from pix.config import AppConfig, require_vl_api_key
from pix.io_utils import image_to_base64_data_url


_JSON_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)
_LOOSE_JSON_RE = re.compile(r"\{[\s\S]*\}")


class VisionParseError(RuntimeError):
    pass


def _extract_json(text: str) -> str:
    """从模型返回里抽出第一段 JSON；支持 ```json``` 代码块或裸 JSON。"""
    m = _JSON_BLOCK_RE.search(text)
    if m:
        return m.group(1).strip()
    m = _LOOSE_JSON_RE.search(text)
    if m:
        return m.group(0).strip()
    return text.strip()


def _build_messages(data_url: str, user_text: str) -> list[dict[str, Any]]:
    """构造 OpenAI 兼容的 vision messages。

    部分 OpenAI-compatible Claude 端点会拒绝 system role（只允许 user/assistant），
    因此把系统约束合并进首条 user 文本，保证 Claude / Gemini / gpt-4o 都能接收。
    """
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"{SYSTEM_PROMPT}\n\n{user_text}"},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]


def _extract_content(resp: dict[str, Any]) -> str:
    choices = resp.get("choices") or []
    if not choices:
        raise PackyError(f"响应缺少 choices: {str(resp)[:500]}")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    # 某些提供商返回结构化 content 数组
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    raise PackyError(f"无法解析响应 content: {str(resp)[:500]}")


def analyze_image(
    cfg: AppConfig,
    image_path: str | Path,
    *,
    model: str | None = None,
) -> PixAnalysis:
    """对单张图片做 VL 分析，返回经 schema 校验的 PixAnalysis。"""
    api_key = require_vl_api_key(cfg)
    client = PackyClient(
        base_url=cfg.api.base_url,
        api_key=api_key,
        timeout=cfg.api.timeout,
        max_retries=cfg.api.max_retries,
    )

    data_url = image_to_base64_data_url(image_path)
    messages = _build_messages(data_url, USER_PROMPT)

    payload: dict[str, Any] = {
        "model": model or cfg.vision.model,
        "messages": messages,
        "temperature": cfg.vision.temperature,
        "max_tokens": cfg.vision.max_tokens,
    }

    raw = _extract_content(client.post_json("/v1/chat/completions", payload))
    analysis = _try_parse(raw)
    if analysis is not None:
        return analysis

    # 解析失败 → 带修正提示重试
    retries = max(0, int(cfg.vision.retry_on_parse))
    last_raw = raw
    for _ in range(retries):
        messages2 = _build_messages(data_url, repair_prompt(last_raw, "schema 校验失败，请重输"))
        payload["messages"] = messages2
        last_raw = _extract_content(client.post_json("/v1/chat/completions", payload))
        analysis = _try_parse(last_raw)
        if analysis is not None:
            return analysis

    raise VisionParseError(
        f"多次尝试后仍无法解析 VL 输出的 JSON：\n{last_raw[:1500]}"
    )


def _try_parse(raw: str) -> PixAnalysis | None:
    candidate = _extract_json(raw)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    try:
        return PixAnalysis.model_validate(data)
    except ValidationError:
        return None
