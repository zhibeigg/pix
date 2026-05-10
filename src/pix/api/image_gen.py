"""Packy gpt-image-2 文生图。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pix.api.packy_client import PackyClient, PackyError
from pix.config import AppConfig, require_image_api_key
from pix.io_utils import b64_to_bytes, download, ensure_dir, write_bytes


_SIZE_RE = re.compile(r"^(\d+)x(\d+)$")

# Packy 文档约束
_MAX_EDGE = 3840
_MIN_PIXELS = 655_360
_MAX_PIXELS = 8_294_400
_RATIO_LIMIT = 3.0


def validate_size(size: str) -> None:
    """按 Packy 文档校验尺寸。auto 跳过校验。"""
    if size == "auto":
        return
    m = _SIZE_RE.match(size)
    if not m:
        raise ValueError(f"size 格式必须为 'WIDTHxHEIGHT' 或 'auto'，收到: {size}")
    w, h = int(m.group(1)), int(m.group(2))
    if max(w, h) > _MAX_EDGE:
        raise ValueError(f"最大边长不能超过 {_MAX_EDGE}，收到 {w}x{h}")
    if w % 16 != 0 or h % 16 != 0:
        raise ValueError(f"宽高必须是 16 的倍数，收到 {w}x{h}")
    pixels = w * h
    if pixels < _MIN_PIXELS:
        raise ValueError(f"总像素不能少于 {_MIN_PIXELS}，收到 {pixels}")
    if pixels > _MAX_PIXELS:
        raise ValueError(f"总像素不能超过 {_MAX_PIXELS}，收到 {pixels}")
    ratio = max(w, h) / min(w, h)
    if ratio > _RATIO_LIMIT + 1e-9:
        raise ValueError(f"长短边比例不能超过 3:1，收到 {ratio:.2f}")


def _pick_image_url(resp: dict[str, Any]) -> tuple[str | None, str | None]:
    """从响应中取出 (url, b64)；两者可能只有其一。"""
    data = resp.get("data") or []
    if not data:
        return None, None
    first = data[0]
    url = first.get("url")
    b64 = first.get("b64_json")
    return url, b64


def generate_image(
    cfg: AppConfig,
    prompt: str,
    dest_path: Path,
    *,
    size: str | None = None,
    quality: str | None = None,
    model: str | None = None,
    output_format: str | None = None,
    n: int = 1,
) -> Path:
    """调 Packy /v1/images/generations 生图并落盘。

    Args:
        dest_path: 目标 PNG 路径。
    Returns:
        实际保存的路径。
    """
    api_key = require_image_api_key(cfg)
    client = PackyClient(
        base_url=cfg.api.base_url,
        api_key=api_key,
        timeout=cfg.api.timeout,
        max_retries=cfg.api.max_retries,
    )
    _size = size or cfg.image_gen.size
    validate_size(_size)

    payload: dict[str, Any] = {
        "model": model or cfg.image_gen.model,
        "prompt": prompt,
        "size": _size,
        "quality": quality or cfg.image_gen.quality,
        "output_format": output_format or cfg.image_gen.output_format,
        "response_format": "url",
        "n": n,
    }
    resp = client.post_json("/v1/images/generations", payload)
    url, b64 = _pick_image_url(resp)

    ensure_dir(dest_path.parent)
    if b64:
        write_bytes(dest_path, b64_to_bytes(b64))
        return dest_path
    if url:
        return download(url, dest_path, timeout=cfg.api.timeout)
    raise PackyError(f"图片生成响应缺少 url 和 b64_json：{str(resp)[:500]}")
