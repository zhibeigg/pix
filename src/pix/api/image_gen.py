"""通用 Provider 生图/图生图入口。"""

from __future__ import annotations

import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from PIL import Image

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
# n-sample 多候选并发上限：每张候选是一次独立上游请求，并发出图而非串行，
# 同时限流避免打爆 Provider。n=1（默认）时不开线程，行为与串行完全一致。
_MAX_PARALLEL_SAMPLES = 4

# 仅按宽高比生成、不保证绝对像素尺寸的 Provider 协议。命中这些协议时，
# 尺寸重试无意义（无法精确匹配 WxH），第一次尝试后即停止重试。
ASPECT_RATIO_PROTOCOLS = frozenset({"midjourney", "ideogram", "kling"})


@dataclass(frozen=True)
class SizeRetryConfig:
    """尺寸重试配置。

    enabled 且 expected_size 可用时，落盘后比较实际像素尺寸与期望尺寸；
    不一致则重新生成，直到匹配或达到 max_attempts。命中宽高比类 Provider
    协议时（无法保证绝对像素），第一次尝试后即停止。
    """

    enabled: bool = False
    max_attempts: int = 1
    expected_size: tuple[int, int] | None = None

    @property
    def active(self) -> bool:
        return self.enabled and self.expected_size is not None and self.max_attempts > 1


@dataclass(frozen=True)
class SizeRetryOutcome:
    """单次 generate_image / edit_image 调用的尺寸重试结果。"""

    enabled: bool
    max_attempts: int
    actual_attempts: int
    matched: bool
    expected_size: tuple[int, int] | None
    actual_size: tuple[int, int] | None
    aspect_ratio_protocol: bool = False

    def to_metadata(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "max_attempts": self.max_attempts,
            "actual_attempts": self.actual_attempts,
            "matched": self.matched,
            "expected_size": list(self.expected_size) if self.expected_size else None,
            "actual_size": list(self.actual_size) if self.actual_size else None,
            "aspect_ratio_protocol": self.aspect_ratio_protocol,
        }


# 用 thread-local 记录最近一次 generate_image / edit_image 的尺寸重试结果，
# 让 pipeline 在调用后取用并写入 meta，同时保持函数返回 Path 不破坏既有调用点。
# 与 image_dispatcher._HISTORY 同思路；并发 worker 下每个线程各自独立。
_SIZE_RETRY_STATE = threading.local()


def _record_size_retry_outcome(outcome: SizeRetryOutcome | None) -> None:
    _SIZE_RETRY_STATE.last = outcome


def last_size_retry_outcome() -> SizeRetryOutcome | None:
    """读取当前线程最近一次生图的尺寸重试结果（无则 None）。"""
    return getattr(_SIZE_RETRY_STATE, "last", None)


def parse_size(size: str | None) -> tuple[int, int] | None:
    """把 'WIDTHxHEIGHT' 解析成 (w, h)；'auto' 或非法格式返回 None。"""
    if not size:
        return None
    match = _SIZE_RE.match(size.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _read_image_size(path: Path) -> tuple[int, int] | None:
    try:
        with Image.open(path) as im:
            return (int(im.width), int(im.height))
    except (OSError, ValueError):
        return None


def _run_sample_batch(make_one: Callable[[int], Path], n: int) -> list[Path]:
    """并发执行 n 张候选生成，保持返回顺序与 index 一致。

    单张失败时（与原串行实现一致）向外抛出首个异常。executor.map 按提交顺序
    产出结果，因此 paths[i] 始终对应 index=i+1。
    """
    if n <= 1:
        return [make_one(1)]
    max_workers = min(n, _MAX_PARALLEL_SAMPLES)
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="pix-sample") as executor:
        return list(executor.map(make_one, range(1, n + 1)))


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
        if "gpt-image-1" in effective_model.lower():
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


def _dispatch_and_write(
    cfg: AppConfig,
    *,
    operation: str,
    prompt: str,
    model: str | None,
    size: str,
    quality: str | None,
    output_format: str | None,
    dest_path: Path,
    input_fidelity: str | None = None,
    image_path: Path | None = None,
) -> tuple[Path, str]:
    """执行一次 dispatch + 落盘，返回 (落盘路径, 命中 provider 协议)。"""
    result = dispatch_image_request(
        cfg,
        operation=operation,
        prompt=prompt,
        model=model,
        size=size,
        quality=quality,
        output_format=output_format,
        input_fidelity=input_fidelity,
        image_path=image_path,
    )
    path = _write_entry(
        (result.image.url, result.image.b64_json),
        dest_path,
        timeout=cfg.api.timeout,
        trust_env=cfg.api.trust_env_proxies,
        proxy=cfg.api.proxy,
        max_retries=cfg.api.max_retries,
    )
    return path, str(result.image.protocol or "")


def _generate_with_size_retry(
    attempt_once: Callable[[], tuple[Path, str]],
    *,
    size_retry: SizeRetryConfig | None,
) -> Path:
    """围绕单次生图+落盘的尺寸重试循环。

    - 未启用或无期望尺寸：执行一次，记录 disabled outcome。
    - 启用：重复生成直到实际尺寸匹配期望，或达到 max_attempts；命中宽高比类
      Provider 协议（无法保证绝对像素）时第一次后即停止。
    全程不 sleep，避免阻塞 worker 线程。
    """
    config = size_retry or SizeRetryConfig()
    if not config.active:
        path, protocol = attempt_once()
        _record_size_retry_outcome(
            SizeRetryOutcome(
                enabled=config.enabled,
                max_attempts=1,
                actual_attempts=1,
                matched=False,
                expected_size=config.expected_size,
                actual_size=_read_image_size(path),
                aspect_ratio_protocol=protocol in ASPECT_RATIO_PROTOCOLS,
            )
        )
        return path

    expected = config.expected_size
    max_attempts = max(1, config.max_attempts)
    last_path: Path | None = None
    last_size: tuple[int, int] | None = None
    attempts = 0
    matched = False
    aspect_ratio_protocol = False
    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        last_path, protocol = attempt_once()
        last_size = _read_image_size(last_path)
        if protocol in ASPECT_RATIO_PROTOCOLS:
            # 宽高比类 Provider 无法保证绝对像素，重试无意义，第一次后即停。
            aspect_ratio_protocol = True
            break
        if last_size == expected:
            matched = True
            break
    _record_size_retry_outcome(
        SizeRetryOutcome(
            enabled=True,
            max_attempts=max_attempts,
            actual_attempts=attempts,
            matched=matched,
            expected_size=expected,
            actual_size=last_size,
            aspect_ratio_protocol=aspect_ratio_protocol,
        )
    )
    assert last_path is not None
    return last_path


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
    size_retry: SizeRetryConfig | None = None,
) -> Path:
    """通过 dispatcher 调用可用 Provider 文生图并落盘。

    Args:
        dest_path: 目标 PNG 路径。
        size_retry: 可选尺寸重试配置；启用后会重复生成直到实际尺寸匹配期望尺寸
            或达到上限。结果可通过 ``last_size_retry_outcome()`` 读取。
    Returns:
        实际保存的路径。
    """
    _model = model or cfg.image_gen.model
    _ensure_single_image_n(n, endpoint="文生图")
    _size = size or cfg.image_gen.size
    validate_size(_size, model=_model)

    def _attempt() -> tuple[Path, str]:
        return _dispatch_and_write(
            cfg,
            operation=TEXT_TO_IMAGE,
            prompt=prompt,
            model=model,
            size=_size,
            quality=quality or cfg.image_gen.quality,
            output_format=output_format or cfg.image_gen.output_format,
            dest_path=dest_path,
        )

    return _generate_with_size_retry(_attempt, size_retry=size_retry)


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
    size_retry: SizeRetryConfig | None = None,
) -> Path:
    """通过 dispatcher 调用可用 Provider 图生图并落盘。"""
    _model = model or cfg.image_gen.model
    _ensure_single_image_n(n, endpoint="图片编辑")
    _size = size or cfg.image_gen.size
    validate_size(_size, model=_model)
    image_path = Path(image_path)

    def _attempt() -> tuple[Path, str]:
        return _dispatch_and_write(
            cfg,
            operation=IMAGE_TO_IMAGE,
            prompt=prompt,
            model=model,
            size=_size,
            quality=quality or cfg.image_gen.quality,
            output_format=output_format or cfg.image_gen.output_format,
            input_fidelity=input_fidelity or cfg.image_gen.edit_input_fidelity,
            image_path=image_path,
            dest_path=dest_path,
        )

    return _generate_with_size_retry(_attempt, size_retry=size_retry)


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

    def _make_one(index: int) -> Path:
        variant_prompt = _with_prompt_variation(prompt, variations, index - 1)
        result = dispatch_image_request(
            cfg,
            operation=TEXT_TO_IMAGE,
            prompt=variant_prompt,
            model=model,
            size=_size,
            quality=quality or cfg.image_gen.quality,
            output_format=output_format or cfg.image_gen.output_format,
        )
        name = filename_template.format(index=index)
        return _write_entry(
            (result.image.url, result.image.b64_json),
            dest_dir / name,
            timeout=cfg.api.timeout,
            trust_env=cfg.api.trust_env_proxies,
            proxy=cfg.api.proxy,
            max_retries=cfg.api.max_retries,
        )

    return _run_sample_batch(_make_one, n)


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

    def _make_one(index: int) -> Path:
        variant_prompt = _with_prompt_variation(prompt, variations, index - 1)
        result = dispatch_image_request(
            cfg,
            operation=IMAGE_TO_IMAGE,
            prompt=variant_prompt,
            model=model,
            size=_size,
            quality=quality or cfg.image_gen.quality,
            output_format=output_format or cfg.image_gen.output_format,
            input_fidelity=input_fidelity or cfg.image_gen.edit_input_fidelity,
            image_path=image_path,
        )
        name = filename_template.format(index=index)
        return _write_entry(
            (result.image.url, result.image.b64_json),
            dest_dir / name,
            timeout=cfg.api.timeout,
            trust_env=cfg.api.trust_env_proxies,
            proxy=cfg.api.proxy,
            max_retries=cfg.api.max_retries,
        )

    return _run_sample_batch(_make_one, n)
