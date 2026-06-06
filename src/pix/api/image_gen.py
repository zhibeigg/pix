"""通用 Provider 生图/图生图入口。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pix.api.http_client import ProviderError
from pix.api.image_dispatcher import dispatch_image_request
from pix.api.image_model_registry import IMAGE_TO_IMAGE, TEXT_TO_IMAGE
from pix.config import AppConfig, is_gemini_model
from pix.io_utils import b64_to_bytes, download, ensure_dir, write_bytes


_SIZE_RE = re.compile(r"^(\d+)x(\d+)$")

# Packy 文档约束
_MAX_EDGE = 3840
_MIN_PIXELS = 655_360
_MAX_PIXELS = 8_294_400
_RATIO_LIMIT = 3.0
# Packy gpt-image-2 Images API 文档约束：n 仅支持 1；stream / partial_images 不支持。
_ONE_IMAGE_N = 1
_IMAGE_RESPONSE_FORMAT = "b64_json"


def validate_size(size: str, *, model: str | None = None) -> None:
    """按 API 文档校验尺寸。auto 跳过校验。Gemini 模型使用更宽松的约束。"""
    if size == "auto":
        return
    m = _SIZE_RE.match(size)
    if not m:
        raise ValueError(f"size 格式必须为 'WIDTHxHEIGHT' 或 'auto'，收到: {size}")
    w, h = int(m.group(1)), int(m.group(2))
    pixels = w * h
    ratio = max(w, h) / min(w, h)
    if is_gemini_model(model or ""):
        # Gemini 尺寸约束：不要求 16 倍数，最大 4096
        if max(w, h) > 4096:
            raise ValueError(f"Gemini 最大边长不能超过 4096，收到 {w}x{h}")
        if pixels < 256 * 256:
            raise ValueError(f"Gemini 总像素不能少于 65536，收到 {pixels}")
        if ratio > 4.0 + 1e-9:
            raise ValueError(f"Gemini 长短边比例不能超过 4:1，收到 {ratio:.2f}")
    else:
        # gpt-image-2 原有约束
        if max(w, h) > _MAX_EDGE:
            raise ValueError(f"最大边长不能超过 {_MAX_EDGE}，收到 {w}x{h}")
        if w % 16 != 0 or h % 16 != 0:
            raise ValueError(f"宽高必须是 16 的倍数，收到 {w}x{h}")
        if pixels < _MIN_PIXELS:
            raise ValueError(f"总像素不能少于 {_MIN_PIXELS}，收到 {pixels}")
        if pixels > _MAX_PIXELS:
            raise ValueError(f"总像素不能超过 {_MAX_PIXELS}，收到 {pixels}")
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


def _ensure_single_image_n(n: int, *, endpoint: str) -> None:
    if int(n) != _ONE_IMAGE_N:
        raise ValueError(f"Packy gpt-image-2 {endpoint} 仅支持 n=1；多图请在调用方循环请求")


def _with_prompt_variation(prompt: str, variations: list[str], index: int) -> str:
    if index <= 0 or not variations:
        return prompt
    suffix = variations[(index - 1) % len(variations)]
    return (prompt + f" {suffix}").strip()


def _generation_payload(
    cfg: AppConfig,
    prompt: str,
    *,
    size: str,
    quality: str | None,
    model: str | None,
    output_format: str | None,
) -> dict[str, Any]:
    effective_model = model or cfg.image_gen.model
    payload: dict[str, Any] = {
        "model": effective_model,
        "prompt": prompt,
        "size": size,
        "response_format": _IMAGE_RESPONSE_FORMAT,
        "n": _ONE_IMAGE_N,
    }
    if not is_gemini_model(effective_model):
        payload["quality"] = quality or cfg.image_gen.quality
        payload["output_format"] = output_format or cfg.image_gen.output_format
    return payload


def _edit_payload(
    cfg: AppConfig,
    prompt: str,
    *,
    size: str,
    quality: str | None,
    model: str | None,
    output_format: str | None,
    input_fidelity: str | None,
) -> dict[str, Any]:
    effective_model = model or cfg.image_gen.model
    payload: dict[str, Any] = {
        "model": effective_model,
        "prompt": prompt,
        "size": size,
        "response_format": _IMAGE_RESPONSE_FORMAT,
        "n": str(_ONE_IMAGE_N),
    }
    if not is_gemini_model(effective_model):
        payload["quality"] = quality or cfg.image_gen.quality
        payload["output_format"] = output_format or cfg.image_gen.output_format
        payload["input_fidelity"] = input_fidelity or cfg.image_gen.edit_input_fidelity
    return payload


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
    raise ProviderError("图片响应条目缺少 url 和 b64_json", category="empty_response")


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
    """通过 dispatcher 调用可用 Provider 文生图并落盘。

    Args:
        dest_path: 目标 PNG 路径。
    Returns:
        实际保存的路径。
    """
    _model = model or cfg.image_gen.model
    _ensure_single_image_n(n, endpoint="文生图")
    _size = size or cfg.image_gen.size
    validate_size(_size, model=_model)

    result = dispatch_image_request(
        cfg,
        operation=TEXT_TO_IMAGE,
        prompt=prompt,
        model=_model,
        size=_size,
        quality=quality or cfg.image_gen.quality,
        output_format=output_format or cfg.image_gen.output_format,
    )
    return _write_entry(
        (result.image.url, result.image.b64_json),
        dest_path,
        timeout=cfg.api.timeout,
        trust_env=cfg.api.trust_env_proxies,
        proxy=cfg.api.proxy,
        max_retries=cfg.api.max_retries,
    )


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
    """通过 dispatcher 调用可用 Provider 图生图并落盘。"""
    _model = model or cfg.image_gen.model
    _ensure_single_image_n(n, endpoint="图片编辑")
    _size = size or cfg.image_gen.size
    validate_size(_size, model=_model)
    image_path = Path(image_path)
    result = dispatch_image_request(
        cfg,
        operation=IMAGE_TO_IMAGE,
        prompt=prompt,
        model=_model,
        size=_size,
        quality=quality or cfg.image_gen.quality,
        output_format=output_format or cfg.image_gen.output_format,
        input_fidelity=input_fidelity or cfg.image_gen.edit_input_fidelity,
        image_path=image_path,
    )
    return _write_entry(
        (result.image.url, result.image.b64_json),
        dest_path,
        timeout=cfg.api.timeout,
        trust_env=cfg.api.trust_env_proxies,
        proxy=cfg.api.proxy,
        max_retries=cfg.api.max_retries,
    )


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
    """n-sample 文生图。

    多 Provider 兼容路径统一按 N 次单图请求循环实现，方便每张候选独立失败切换。
    默认请求 ``b64_json``，若远端只返回 URL，则作为兼容兜底下载。

    Args:
        prompt: 基础 prompt；若 prompt_variations 非空，则从第 2 张开始追加一句变体。
        filename_template: 支持 {index} / {index:02d} 占位。
    """
    assert n >= 1
    ensure_dir(dest_dir)
    _model = model or cfg.image_gen.model
    _size = size or cfg.image_gen.size
    validate_size(_size, model=_model)

    variations = [v for v in (prompt_variations or []) if v.strip()]
    paths: list[Path] = []
    for index in range(1, n + 1):
        variant_prompt = _with_prompt_variation(prompt, variations, index - 1)
        result = dispatch_image_request(
            cfg,
            operation=TEXT_TO_IMAGE,
            prompt=variant_prompt,
            model=_model,
            size=_size,
            quality=quality or cfg.image_gen.quality,
            output_format=output_format or cfg.image_gen.output_format,
        )
        name = filename_template.format(index=index)
        paths.append(
            _write_entry(
                (result.image.url, result.image.b64_json),
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
    """n-sample 图生图：循环请求多张编辑结果，并允许逐张 Provider 失败切换。"""
    assert n >= 1
    ensure_dir(dest_dir)
    _model = model or cfg.image_gen.model
    _size = size or cfg.image_gen.size
    validate_size(_size, model=_model)
    image_path = Path(image_path)

    variations = [v for v in (prompt_variations or []) if v.strip()]
    paths: list[Path] = []
    for index in range(1, n + 1):
        variant_prompt = _with_prompt_variation(prompt, variations, index - 1)
        result = dispatch_image_request(
            cfg,
            operation=IMAGE_TO_IMAGE,
            prompt=variant_prompt,
            model=_model,
            size=_size,
            quality=quality or cfg.image_gen.quality,
            output_format=output_format or cfg.image_gen.output_format,
            input_fidelity=input_fidelity or cfg.image_gen.edit_input_fidelity,
            image_path=image_path,
        )
        name = filename_template.format(index=index)
        paths.append(
            _write_entry(
                (result.image.url, result.image.b64_json),
                dest_dir / name,
                timeout=cfg.api.timeout,
                trust_env=cfg.api.trust_env_proxies,
                proxy=cfg.api.proxy,
                max_retries=cfg.api.max_retries,
            )
        )
    return paths
