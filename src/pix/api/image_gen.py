"""Packy gpt-image-2 文生图。"""

from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from typing import Any

from pix.api.packy_client import PackyError, make_packy_client
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
    """从响应中取出 (url, b64)；两者可能只有其一（仅第一张）。"""
    data = resp.get("data") or []
    if not data:
        return None, None
    first = data[0]
    url = first.get("url")
    b64 = first.get("b64_json")
    return url, b64


def _collect_image_entries(resp: dict[str, Any]) -> list[tuple[str | None, str | None]]:
    """收集响应里所有图片条目，按顺序返回 (url, b64)。"""
    data = resp.get("data") or []
    entries: list[tuple[str | None, str | None]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        entries.append((item.get("url"), item.get("b64_json")))
    return entries


def _write_entry(
    entry: tuple[str | None, str | None],
    dest: Path,
    *,
    timeout: float,
    trust_env: bool = False,
    proxy: str | None = None,
    max_retries: int = 3,
) -> Path:
    url, b64 = entry
    ensure_dir(dest.parent)
    if b64:
        write_bytes(dest, b64_to_bytes(b64))
        return dest
    if url:
        return download(url, dest, timeout=timeout, trust_env=trust_env, proxy=proxy, max_retries=max_retries)
    raise PackyError("图片响应条目缺少 url 和 b64_json")


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
    client = make_packy_client(cfg, api_key)
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
        return download(
            url,
            dest_path,
            timeout=cfg.api.timeout,
            trust_env=cfg.api.trust_env_proxies,
            proxy=cfg.api.proxy,
            max_retries=cfg.api.max_retries,
        )
    raise PackyError(f"图片生成响应缺少 url 和 b64_json：{str(resp)[:500]}")


def edit_image(
    cfg: AppConfig,
    image_path: Path,
    prompt: str,
    dest_path: Path,
    *,
    size: str | None = None,
    quality: str | None = None,
    model: str | None = None,
    output_format: str | None = None,
    input_fidelity: str | None = None,
    n: int = 1,
) -> Path:
    """调 Packy /v1/images/edits 图生图并落盘。"""
    api_key = require_image_api_key(cfg)
    client = make_packy_client(cfg, api_key)
    _size = size or cfg.image_gen.size
    validate_size(_size)
    image_path = Path(image_path)
    mime = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
    data: dict[str, Any] = {
        "model": model or cfg.image_gen.model,
        "prompt": prompt,
        "size": _size,
        "quality": quality or cfg.image_gen.quality,
        "output_format": output_format or cfg.image_gen.output_format,
        "response_format": "url",
        "n": str(n),
        "input_fidelity": input_fidelity or cfg.image_gen.edit_input_fidelity,
    }
    files = {"image": (image_path.name, image_path.read_bytes(), mime)}
    resp = client.post_multipart("/v1/images/edits", data=data, files=files)
    url, b64 = _pick_image_url(resp)

    ensure_dir(dest_path.parent)
    if b64:
        write_bytes(dest_path, b64_to_bytes(b64))
        return dest_path
    if url:
        return download(
            url,
            dest_path,
            timeout=cfg.api.timeout,
            trust_env=cfg.api.trust_env_proxies,
            proxy=cfg.api.proxy,
            max_retries=cfg.api.max_retries,
        )
    raise PackyError(f"图片编辑响应缺少 url 和 b64_json：{str(resp)[:500]}")


def generate_images_batch(
    cfg: AppConfig,
    prompt: str,
    dest_dir: Path,
    *,
    n: int,
    size: str | None = None,
    quality: str | None = None,
    model: str | None = None,
    output_format: str | None = None,
    filename_template: str = "sample_{index:02d}.png",
    prompt_variations: list[str] | None = None,
) -> list[Path]:
    """n-sample 文生图：优先用 provider 的 n=N 单次返回；若响应不足 N 张再循环补齐。

    Args:
        prompt: 基础 prompt；若 prompt_variations 非空，则每次 fallback 追加一句变体。
        filename_template: 支持 {index} / {index:02d} 占位。
    """
    assert n >= 1
    ensure_dir(dest_dir)
    api_key = require_image_api_key(cfg)
    client = make_packy_client(cfg, api_key)
    _size = size or cfg.image_gen.size
    validate_size(_size)

    collected: list[tuple[str | None, str | None]] = []

    # 1. 先尝试单次 n=N
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
    collected.extend(_collect_image_entries(resp))

    # 2. 如果返回不足，用单次调用补齐；可选带 prompt 变体
    variations = [v for v in (prompt_variations or []) if v.strip()]
    attempt = 0
    while len(collected) < n and attempt < n * 2:  # 安全上限
        attempt += 1
        var_suffix = f" {variations[(attempt - 1) % len(variations)]}" if variations else ""
        variant_prompt = (prompt + var_suffix).strip()
        single_payload = dict(payload)
        single_payload["prompt"] = variant_prompt
        single_payload["n"] = 1
        resp = client.post_json("/v1/images/generations", single_payload)
        collected.extend(_collect_image_entries(resp))

    if not collected:
        raise PackyError("n-sample 文生图没有任何返回数据")

    collected = collected[:n]
    paths: list[Path] = []
    for index, entry in enumerate(collected, start=1):
        name = filename_template.format(index=index)
        paths.append(
            _write_entry(
                entry,
                dest_dir / name,
                timeout=cfg.api.timeout,
                trust_env=cfg.api.trust_env_proxies,
                proxy=cfg.api.proxy,
                max_retries=cfg.api.max_retries,
            )
        )
    return paths


def edit_images_batch(
    cfg: AppConfig,
    image_path: Path,
    prompt: str,
    dest_dir: Path,
    *,
    n: int,
    size: str | None = None,
    quality: str | None = None,
    model: str | None = None,
    output_format: str | None = None,
    input_fidelity: str | None = None,
    filename_template: str = "sample_{index:02d}.png",
    prompt_variations: list[str] | None = None,
) -> list[Path]:
    """n-sample 图生图：保持与 `generate_images_batch` 相同的合同。"""
    assert n >= 1
    ensure_dir(dest_dir)
    api_key = require_image_api_key(cfg)
    client = make_packy_client(cfg, api_key)
    _size = size or cfg.image_gen.size
    validate_size(_size)
    image_path = Path(image_path)
    mime = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
    image_bytes = image_path.read_bytes()

    collected: list[tuple[str | None, str | None]] = []

    base_data: dict[str, Any] = {
        "model": model or cfg.image_gen.model,
        "prompt": prompt,
        "size": _size,
        "quality": quality or cfg.image_gen.quality,
        "output_format": output_format or cfg.image_gen.output_format,
        "response_format": "url",
        "n": str(n),
        "input_fidelity": input_fidelity or cfg.image_gen.edit_input_fidelity,
    }
    files = {"image": (image_path.name, image_bytes, mime)}
    resp = client.post_multipart("/v1/images/edits", data=base_data, files=files)
    collected.extend(_collect_image_entries(resp))

    variations = [v for v in (prompt_variations or []) if v.strip()]
    attempt = 0
    while len(collected) < n and attempt < n * 2:
        attempt += 1
        var_suffix = f" {variations[(attempt - 1) % len(variations)]}" if variations else ""
        variant_prompt = (prompt + var_suffix).strip()
        data = dict(base_data)
        data["prompt"] = variant_prompt
        data["n"] = "1"
        resp = client.post_multipart("/v1/images/edits", data=data, files=files)
        collected.extend(_collect_image_entries(resp))

    if not collected:
        raise PackyError("n-sample 图生图没有任何返回数据")

    collected = collected[:n]
    paths: list[Path] = []
    for index, entry in enumerate(collected, start=1):
        name = filename_template.format(index=index)
        paths.append(
            _write_entry(
                entry,
                dest_dir / name,
                timeout=cfg.api.timeout,
                trust_env=cfg.api.trust_env_proxies,
                proxy=cfg.api.proxy,
                max_retries=cfg.api.max_retries,
            )
        )
    return paths
