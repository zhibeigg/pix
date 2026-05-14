"""Ramp 调色板：色相组 × 明度阶梯的结构化调色板。

与原 K-means 路径的区别：
- K-means 按"密度"聚类，容易得到色相相近但缺乏明度阶梯的塑料感调色板。
- Ramp 按"色相组 × 明度阶梯"分层：outline / shadow / mid / highlight 沿固定 L* 轴分布。
- VL 负责出 ramp 设计；VL 失败时本地从图片按 HSL 聚合兜底；量化在 CIELAB 空间找最近色。
"""

from __future__ import annotations

import colorsys
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

import numpy as np
from PIL import Image
from pydantic import BaseModel, Field, ValidationError, field_validator

from pix.api.packy_client import PackyClient
from pix.api.vision import _extract_content, _extract_json
from pix.config import AppConfig, require_vl_api_key
from pix.io_utils import image_to_base64_data_url
from pix.pixelize.ramp_prompts import (
    RAMP_SYSTEM_PROMPT,
    build_ramp_repair_prompt,
    build_ramp_user_prompt,
)


RampStepRole = Literal["outline", "shadow", "mid", "highlight", "accent"]


_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")
_DEFAULT_ROLE_ORDER: tuple[RampStepRole, ...] = ("outline", "shadow", "mid", "highlight")


@dataclass(frozen=True)
class RampStep:
    hex: str
    role: RampStepRole
    rgb: tuple[int, int, int]
    lab: tuple[float, float, float]


@dataclass(frozen=True)
class ColorRamp:
    name: str
    hue: str
    steps: tuple[RampStep, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "hue": self.hue,
            "steps": [{"hex": s.hex, "role": s.role} for s in self.steps],
        }


@dataclass(frozen=True)
class RampPalette:
    """VL 或本地生成的 ramp 调色板。

    `rgb_list` 是最终量化时使用的扁平 RGB 列表；`step_meta` 提供每个颜色的 ramp/step/role，
    便于 meta 落盘和后续的 outline 加深 / highlight 聚焦等微调。
    """

    ramps: tuple[ColorRamp, ...]
    source: Literal["vl", "local", "manual"] = "local"

    @property
    def steps(self) -> list[RampStep]:
        return [step for ramp in self.ramps for step in ramp.steps]

    @property
    def rgb_list(self) -> list[tuple[int, int, int]]:
        seen: dict[tuple[int, int, int], None] = {}
        for step in self.steps:
            seen.setdefault(step.rgb, None)
        return list(seen.keys())

    @property
    def step_meta(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[tuple[int, int, int]] = set()
        for ramp_index, ramp in enumerate(self.ramps):
            for step_index, step in enumerate(ramp.steps):
                if step.rgb in seen:
                    continue
                seen.add(step.rgb)
                result.append({
                    "hex": step.hex,
                    "role": step.role,
                    "ramp": ramp.name,
                    "ramp_hue": ramp.hue,
                    "ramp_index": ramp_index,
                    "step_index": step_index,
                })
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "ramps": [r.to_dict() for r in self.ramps],
            "step_meta": self.step_meta,
            "colors": ["#{:02X}{:02X}{:02X}".format(*rgb) for rgb in self.rgb_list],
        }

    def role_index_map(self) -> dict[RampStepRole, list[int]]:
        """每个 role 在 rgb_list 中对应哪些 palette 索引；用于 outline/highlight 后处理。"""
        index_by_rgb = {rgb: idx for idx, rgb in enumerate(self.rgb_list)}
        mapping: dict[RampStepRole, list[int]] = {}
        for step in self.steps:
            mapping.setdefault(step.role, []).append(index_by_rgb[step.rgb])
        return mapping



class _RampStepModel(BaseModel):
    hex: str
    role: str = "mid"

    @field_validator("hex")
    @classmethod
    def _v_hex(cls, value: str) -> str:
        v = value.strip()
        if not _HEX_RE.match(v):
            raise ValueError(f"非法 hex：{value}")
        return "#" + v.lstrip("#").upper()


class _RampModel(BaseModel):
    name: str = ""
    hue: str = ""
    steps: list[_RampStepModel] = Field(default_factory=list, min_length=3, max_length=8)


class _RampPayload(BaseModel):
    ramps: list[_RampModel] = Field(default_factory=list, min_length=1, max_length=6)



def hex_to_rgb(value: str) -> tuple[int, int, int]:
    v = value.strip().lstrip("#")
    if len(v) != 6:
        raise ValueError(f"非法 hex：{value}")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _srgb_to_linear(channel: float) -> float:
    c = channel / 255.0
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def rgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """sRGB → XYZ(D65) → Lab。返回 (L, a, b)。"""
    r, g, b = (_srgb_to_linear(float(c)) for c in rgb)
    # D65
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041

    # 相对参考白
    xn, yn, zn = 0.95047, 1.0, 1.08883
    fx = _lab_f(x / xn)
    fy = _lab_f(y / yn)
    fz = _lab_f(z / zn)
    lab_l = 116.0 * fy - 16.0
    lab_a = 500.0 * (fx - fy)
    lab_b = 200.0 * (fy - fz)
    return lab_l, lab_a, lab_b


def _lab_f(t: float) -> float:
    if t > 0.008856:
        return t ** (1.0 / 3.0)
    return 7.787 * t + 16.0 / 116.0


def _rgb_array_to_lab(rgb_arr: np.ndarray) -> np.ndarray:
    """整图 sRGB(0-255) → Lab，向量化实现。"""
    arr = rgb_arr.astype(np.float32) / 255.0
    linear = np.where(arr <= 0.04045, arr / 12.92, ((arr + 0.055) / 1.055) ** 2.4)
    m = np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ], dtype=np.float32)
    xyz = linear @ m.T
    ref = np.array([0.95047, 1.0, 1.08883], dtype=np.float32)
    t = xyz / ref
    delta = 0.008856
    f = np.where(t > delta, np.cbrt(t), 7.787 * t + 16.0 / 116.0)
    lab_l = 116.0 * f[..., 1] - 16.0
    lab_a = 500.0 * (f[..., 0] - f[..., 1])
    lab_b = 200.0 * (f[..., 1] - f[..., 2])
    return np.stack([lab_l, lab_a, lab_b], axis=-1)


def _hue_angle(rgb: tuple[int, int, int]) -> float:
    r, g, b = (c / 255.0 for c in rgb)
    h, _l, _s = colorsys.rgb_to_hls(r, g, b)
    return (h * 360.0) % 360.0


def _hue_delta(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)



class RampValidationError(ValueError):
    """Ramp schema 校验失败。"""


def _build_step(hex_value: str, role: str) -> RampStep:
    rgb = hex_to_rgb(hex_value)
    lab = rgb_to_lab(rgb)
    safe_role: RampStepRole = role if role in ("outline", "shadow", "mid", "highlight", "accent") else "mid"
    return RampStep(hex=rgb_to_hex(rgb), role=safe_role, rgb=rgb, lab=lab)


def _order_steps(steps: list[RampStep]) -> list[RampStep]:
    """按明度升序排列 step。"""
    return sorted(steps, key=lambda s: s.lab[0])


def _autoassign_roles(steps: list[RampStep]) -> list[RampStep]:
    """若 role 全部缺失或重复严重，按明度序重分配 outline→shadow→mid→highlight。"""
    ordered = _order_steps(steps)
    n = len(ordered)
    if n == 0:
        return ordered
    # 角色模板
    roles_by_count: dict[int, tuple[RampStepRole, ...]] = {
        3: ("outline", "mid", "highlight"),
        4: ("outline", "shadow", "mid", "highlight"),
        5: ("outline", "shadow", "mid", "highlight", "accent"),
        6: ("outline", "shadow", "shadow", "mid", "highlight", "accent"),
    }
    template = roles_by_count.get(n) or (
        ("outline",) + ("shadow",) * max(0, n - 3) + ("mid", "highlight")
    )
    if len(template) < n:
        template = template + ("accent",) * (n - len(template))
    return [
        RampStep(hex=step.hex, role=template[i] if i < len(template) else step.role, rgb=step.rgb, lab=step.lab)
        for i, step in enumerate(ordered)
    ]


def _validate_ramp_internal(ramp: ColorRamp, *, min_l_gap: float = 8.0, max_hue_drift: float = 40.0) -> list[str]:
    """返回 ramp 内部违规消息列表；用于诊断，但宽容度比 prompt 描述宽一些，避免 VL 在边界值上反复重试。"""
    issues: list[str] = []
    if len(ramp.steps) < 3:
        issues.append(f"ramp {ramp.name!r} step 数少于 3")
        return issues
    ordered = _order_steps(list(ramp.steps))
    for i in range(1, len(ordered)):
        gap = ordered[i].lab[0] - ordered[i - 1].lab[0]
        if gap < min_l_gap:
            issues.append(f"ramp {ramp.name!r} step {i} 明度差 {gap:.1f} < {min_l_gap}")
    base_hue = _hue_angle(ordered[len(ordered) // 2].rgb)
    for step in ordered:
        # 近黑/近白不检查色相
        if step.lab[0] < 15.0 or step.lab[0] > 92.0:
            continue
        drift = _hue_delta(_hue_angle(step.rgb), base_hue)
        if drift > max_hue_drift:
            issues.append(f"ramp {ramp.name!r} 色相漂移 {drift:.1f}° > {max_hue_drift}°")
    return issues


def parse_ramp_payload(raw_text: str, *, max_colors: int) -> RampPalette:
    """解析 VL 返回的 JSON（容忍 Markdown 包裹），做基础结构校验。"""
    candidate = _extract_json(raw_text)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise RampValidationError(f"无法解析 JSON：{exc}") from exc
    try:
        payload = _RampPayload.model_validate(data)
    except ValidationError as exc:
        raise RampValidationError(f"schema 校验失败：{exc}") from exc

    ramps: list[ColorRamp] = []
    total = 0
    for ramp_idx, ramp_model in enumerate(payload.ramps):
        if not ramp_model.steps:
            continue
        steps = [_build_step(s.hex, s.role) for s in ramp_model.steps]
        # 若 role 在模型里没给或全是 mid，根据明度重新分配
        unique_roles = {s.role for s in steps}
        if unique_roles == {"mid"} or not unique_roles:
            steps = _autoassign_roles(steps)
        else:
            steps = _order_steps(steps)
        name = (ramp_model.name or ramp_model.hue or f"ramp_{ramp_idx + 1}").strip() or f"ramp_{ramp_idx + 1}"
        hue = (ramp_model.hue or name).strip() or "unknown"
        ramps.append(ColorRamp(name=name, hue=hue, steps=tuple(steps)))
        total += len(steps)

    if not ramps:
        raise RampValidationError("ramps 为空")

    if total > max_colors:
        # 超出 max_colors：优先保留每个 ramp 的外轮廓/中间色/高光，裁掉 shadow/accent。
        ramps = _trim_ramps_to_budget(ramps, max_colors)

    return RampPalette(ramps=tuple(ramps), source="vl")


def _trim_ramps_to_budget(ramps: Sequence[ColorRamp], budget: int) -> list[ColorRamp]:
    """在总 step 超预算时，按 role 优先级逐步删掉最不重要的 step。"""
    priority = ("accent", "shadow", "highlight", "mid", "outline")  # 删除时优先丢 accent
    remaining = [
        ColorRamp(name=r.name, hue=r.hue, steps=tuple(r.steps))
        for r in ramps
    ]
    total = sum(len(r.steps) for r in remaining)
    for target_role in priority:
        if total <= budget:
            break
        new_remaining: list[ColorRamp] = []
        for ramp in remaining:
            if total <= budget:
                new_remaining.append(ramp)
                continue
            keep: list[RampStep] = []
            for step in ramp.steps:
                if total > budget and step.role == target_role and len(keep) + sum(1 for s in ramp.steps[len(keep) + 1:]) >= 3:
                    total -= 1
                    continue
                keep.append(step)
            if len(keep) >= 3:
                new_remaining.append(ColorRamp(name=ramp.name, hue=ramp.hue, steps=tuple(keep)))
            else:
                new_remaining.append(ramp)
        remaining = new_remaining
    # 仍超预算：最后一档直接按明度对齐截断（每个 ramp 保留 3 个 step）。
    if total > budget:
        clipped: list[ColorRamp] = []
        for ramp in remaining:
            if total <= budget:
                clipped.append(ramp)
                continue
            steps = list(ramp.steps)
            while len(steps) > 3 and total > budget:
                # 丢掉最靠中间的第二个 step
                steps.pop(len(steps) // 2)
                total -= 1
            clipped.append(ColorRamp(name=ramp.name, hue=ramp.hue, steps=tuple(steps)))
        remaining = clipped
    return remaining



def ramp_from_vl(
    cfg: AppConfig,
    image_path: str | Path,
    *,
    max_colors: int,
    output_size: tuple[int, int],
    model: str | None = None,
    description: str = "",
    draft_palette_hex: list[str] | None = None,
    retries: int = 1,
) -> RampPalette:
    """调 VL 产出 ramp JSON，解析校验后返回。

    失败时抛 `RampValidationError` 或 `PackyError`，由调用方决定兜底。
    """
    api_key = require_vl_api_key(cfg)
    client = PackyClient(
        base_url=cfg.api.base_url,
        api_key=api_key,
        timeout=cfg.api.timeout,
        max_retries=cfg.api.max_retries,
    )
    data_url = image_to_base64_data_url(image_path)

    user_prompt = build_ramp_user_prompt(
        max_colors=max_colors,
        output_size=output_size,
        description=description,
        draft_palette_hex=draft_palette_hex,
    )

    messages = _build_messages(data_url, f"{RAMP_SYSTEM_PROMPT}\n\n{user_prompt}")
    payload: dict[str, Any] = {
        "model": model or cfg.vision.model,
        "messages": messages,
        "temperature": min(0.35, cfg.vision.temperature),
        "max_tokens": max(cfg.vision.max_tokens, 1024),
    }

    attempts = max(1, int(retries) + 1)
    last_raw = ""
    last_error = ""
    for _ in range(attempts):
        last_raw = _extract_content(client.post_json("/v1/chat/completions", payload))
        try:
            return parse_ramp_payload(last_raw, max_colors=max_colors)
        except RampValidationError as exc:
            last_error = str(exc)
            payload["messages"] = _build_messages(
                data_url,
                build_ramp_repair_prompt(
                    max_colors=max_colors,
                    output_size=output_size,
                    previous_output=last_raw,
                    error_detail=last_error,
                ),
            )
    raise RampValidationError(f"Ramp VL 多次返回无法解析：{last_error}")


def _build_messages(data_url: str, text: str) -> list[dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]



def build_local_ramp(
    image: Image.Image,
    *,
    max_colors: int,
    max_ramps: int = 2,
) -> RampPalette:
    """VL 不可用时的兜底：本地按 HSL 聚类成 1~max_ramps 个 ramp。

    策略：
    1. 取可见像素，HLS 空间按色相分 n 个簇（n = min(max_ramps, ceil(max_colors/3))）。
    2. 每个簇内部按亮度分位数取 3~4 个 step，保证 outline/shadow/mid/highlight。
    3. 仅当簇内像素数占比 ≥ 8% 才保留，避免少量杂色被单独切成 ramp。
    """
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    alpha = rgba[..., 3]
    rgb = rgba[..., :3].reshape(-1, 3)
    alpha_flat = alpha.reshape(-1)
    if (alpha_flat > 8).any():
        visible = rgb[alpha_flat > 8]
    else:
        visible = rgb
    if visible.size == 0:
        # 整张图都是透明：返回一个灰色 ramp
        return _default_gray_ramp(max_colors=max_colors)

    # HLS 分簇
    hls = np.array([colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0) for r, g, b in visible], dtype=np.float32)
    hue = hls[:, 0] * 360.0
    sat = hls[:, 2]

    n_ramps = max(1, min(int(max_ramps), max(1, max_colors // 3)))

    # 低饱和像素归到"neutral"单桶，避免灰度污染彩色 ramp
    neutral_mask = sat < 0.1
    neutral_pixels = visible[neutral_mask]
    color_pixels = visible[~neutral_mask]
    color_hue = hue[~neutral_mask]

    hue_centers: list[float] = []
    if color_pixels.size > 0:
        hue_centers = _cluster_hues(color_hue, n_ramps)

    ramps: list[ColorRamp] = []
    budget = max(max_colors, 3)
    per_ramp = max(3, min(5, budget // max(1, len(hue_centers) + (1 if neutral_pixels.size > 0 else 0))))

    for i, center in enumerate(hue_centers):
        mask = np.array([_hue_delta(float(h), center) <= max(20.0, 180.0 / max(1, len(hue_centers))) for h in color_hue], dtype=bool)
        cluster = color_pixels[mask]
        if cluster.shape[0] < max(20, int(visible.shape[0] * 0.04)):
            continue
        steps = _build_ramp_steps_from_pixels(cluster, per_ramp)
        if len(steps) < 3:
            continue
        ramps.append(ColorRamp(
            name=f"auto_{i + 1}",
            hue=f"h{int(center):03d}",
            steps=tuple(_autoassign_roles(steps)),
        ))

    if neutral_pixels.shape[0] >= max(30, int(visible.shape[0] * 0.06)) and len(ramps) < n_ramps + 1:
        steps = _build_ramp_steps_from_pixels(neutral_pixels, per_ramp)
        if len(steps) >= 3:
            ramps.append(ColorRamp(
                name="neutral",
                hue="neutral",
                steps=tuple(_autoassign_roles(steps)),
            ))

    if not ramps:
        steps = _build_ramp_steps_from_pixels(visible, max(3, min(budget, 5)))
        ramps.append(ColorRamp(
            name="main",
            hue="main",
            steps=tuple(_autoassign_roles(steps)),
        ))

    # 预算控制
    ramps = _trim_ramps_to_budget(ramps, max_colors)
    return RampPalette(ramps=tuple(ramps), source="local")


def _default_gray_ramp(*, max_colors: int) -> RampPalette:
    count = max(3, min(4, max_colors))
    lums = np.linspace(30, 220, count, dtype=np.int32)
    steps = [_build_step(rgb_to_hex((int(v), int(v), int(v))), "mid") for v in lums]
    steps = _autoassign_roles(steps)
    return RampPalette(ramps=(ColorRamp(name="gray", hue="neutral", steps=tuple(steps)),), source="local")


def _cluster_hues(hue: np.ndarray, k: int) -> list[float]:
    """环形 K-means 简化版：把色相轴切成 k 个等间距初始中心，迭代收敛几次。"""
    if hue.size == 0:
        return []
    k = max(1, min(int(k), 6))
    centers = np.linspace(0.0, 360.0, k, endpoint=False)
    for _ in range(8):
        # 环形距离到每个中心
        dists = np.stack([np.minimum(np.abs(hue - c), 360.0 - np.abs(hue - c)) for c in centers], axis=1)
        labels = dists.argmin(axis=1)
        new_centers = []
        for i in range(k):
            cluster = hue[labels == i]
            if cluster.size == 0:
                new_centers.append(centers[i])
                continue
            # 环形均值
            rad = np.deg2rad(cluster)
            x = np.cos(rad).mean()
            y = np.sin(rad).mean()
            mean = (np.rad2deg(np.arctan2(y, x)) + 360.0) % 360.0
            new_centers.append(float(mean))
        centers = np.array(new_centers, dtype=np.float32)
    return [float(c) for c in centers]


def _build_ramp_steps_from_pixels(pixels: np.ndarray, count: int) -> list[RampStep]:
    """在给定像素集合里，按明度分位数取 count 个 step。"""
    if pixels.size == 0:
        return []
    count = max(3, min(int(count), 6))
    lab = _rgb_array_to_lab(pixels)
    order = np.argsort(lab[:, 0])
    pixels_sorted = pixels[order]
    indices = np.linspace(0, pixels_sorted.shape[0] - 1, count).astype(int)

    # 对首尾略作拓展：outline/highlight 往两端再压一步，制造明度阶梯感。
    steps: list[RampStep] = []
    for i, idx in enumerate(indices):
        r, g, b = (int(v) for v in pixels_sorted[idx])
        if i == 0:
            scale = 0.6
            r, g, b = int(r * scale), int(g * scale), int(b * scale)
        elif i == len(indices) - 1:
            # 向白色插值 20%
            r = min(255, int(r + (255 - r) * 0.18))
            g = min(255, int(g + (255 - g) * 0.18))
            b = min(255, int(b + (255 - b) * 0.18))
        steps.append(_build_step(rgb_to_hex((r, g, b)), "mid"))
    # 可能出现同色：去重后如果少于 3 个就补回
    dedup: list[RampStep] = []
    seen: set[tuple[int, int, int]] = set()
    for s in steps:
        if s.rgb in seen:
            continue
        seen.add(s.rgb)
        dedup.append(s)
    return _order_steps(dedup)



QuantizeDither = Literal["none", "floyd_steinberg"]


def quantize_to_ramp(
    image: Image.Image,
    ramp: RampPalette,
    *,
    dither: QuantizeDither = "none",
) -> Image.Image:
    """按 Lab 最近色把 image 量化到 ramp 的 rgb_list，可选 Floyd-Steinberg 抖动。

    保留原 alpha 通道。
    """
    if not ramp.rgb_list:
        raise RampValidationError("ramp 没有可用颜色")
    src = image.convert("RGBA")
    rgba = np.asarray(src, dtype=np.uint8).copy()
    alpha = rgba[..., 3]
    rgb = rgba[..., :3]

    palette_rgb = np.asarray(ramp.rgb_list, dtype=np.int16)
    palette_lab = np.asarray([rgb_to_lab(tuple(int(v) for v in c)) for c in palette_rgb], dtype=np.float32)

    if dither == "floyd_steinberg":
        quantized_rgb = _quantize_floyd_steinberg(rgb, palette_rgb, palette_lab)
    else:
        lab_arr = _rgb_array_to_lab(rgb)
        # 计算每像素到每个 palette 点的 Lab 距离
        flat_lab = lab_arr.reshape(-1, 3)
        # 分块避免 ImageNet 尺寸占显存
        indices = _nearest_lab_indices(flat_lab, palette_lab)
        quantized_rgb = palette_rgb[indices].reshape(rgb.shape).astype(np.uint8)

    out = np.dstack([quantized_rgb, alpha]).astype(np.uint8)
    return Image.fromarray(out, mode="RGBA")


def _nearest_lab_indices(flat_lab: np.ndarray, palette_lab: np.ndarray, *, chunk: int = 65536) -> np.ndarray:
    result = np.empty(flat_lab.shape[0], dtype=np.int32)
    for start in range(0, flat_lab.shape[0], chunk):
        end = min(start + chunk, flat_lab.shape[0])
        block = flat_lab[start:end]  # (N, 3)
        diff = block[:, None, :] - palette_lab[None, :, :]  # (N, K, 3)
        dist = (diff * diff).sum(axis=-1)
        result[start:end] = dist.argmin(axis=1)
    return result


def _quantize_floyd_steinberg(
    rgb: np.ndarray,
    palette_rgb: np.ndarray,
    palette_lab: np.ndarray,
) -> np.ndarray:
    """Floyd-Steinberg：误差在 RGB 空间传播，最近邻匹配用 Lab 保证感知准确。"""
    work = rgb.astype(np.float32).copy()
    h, w, _ = work.shape
    out = np.zeros_like(rgb)
    palette_rgb_f = palette_rgb.astype(np.float32)
    for y in range(h):
        for x in range(w):
            pixel = np.clip(work[y, x], 0, 255)
            lab = np.asarray(rgb_to_lab(tuple(int(v) for v in pixel)), dtype=np.float32)
            diff = palette_lab - lab
            idx = int(np.argmin((diff * diff).sum(axis=-1)))
            chosen = palette_rgb_f[idx]
            out[y, x] = chosen.astype(np.uint8)
            err = pixel - chosen
            if x + 1 < w:
                work[y, x + 1] += err * (7.0 / 16.0)
            if y + 1 < h:
                if x > 0:
                    work[y + 1, x - 1] += err * (3.0 / 16.0)
                work[y + 1, x] += err * (5.0 / 16.0)
                if x + 1 < w:
                    work[y + 1, x + 1] += err * (1.0 / 16.0)
    return out



def ramp_to_rgb_palette(ramp: RampPalette) -> list[tuple[int, int, int]]:
    """供 `build_palette_image` 使用的扁平 RGB 列表。"""
    return ramp.rgb_list


def ramp_to_meta(ramp: RampPalette) -> dict[str, Any]:
    """落入 meta.json 的 ramp 描述。"""
    meta = ramp.to_dict()
    meta["ramp_count"] = len(ramp.ramps)
    meta["step_count"] = len(ramp.steps)
    meta["internal_issues"] = {r.name: _validate_ramp_internal(r) for r in ramp.ramps}
    return meta


def ramp_from_dict(data: dict[str, Any]) -> RampPalette:
    """从已落盘的 dict 反序列化（测试/缓存复用）。"""
    payload = _RampPayload.model_validate(data)
    ramps: list[ColorRamp] = []
    for idx, ramp_model in enumerate(payload.ramps):
        steps = [_build_step(s.hex, s.role) for s in ramp_model.steps]
        name = (ramp_model.name or ramp_model.hue or f"ramp_{idx + 1}").strip() or f"ramp_{idx + 1}"
        hue = (ramp_model.hue or name).strip() or "unknown"
        ramps.append(ColorRamp(name=name, hue=hue, steps=tuple(_order_steps(steps))))
    return RampPalette(ramps=tuple(ramps), source="manual")


def remap_palette_to_ramp(rgb_palette: list[tuple[int, int, int]], ramp: RampPalette) -> list[tuple[int, int, int]]:
    """把 K-means 出的扁平 palette 按 Lab 最近色映射到 ramp 颜色。

    用途：PixelGrid 走 extract 路径出来后，palette 是 K-means 聚出来的；
    我们保留 pixels 索引不变，只把 palette 颜色替换成 ramp 上最近的色，
    立刻获得"手绘色阶感"而不需要重新生成像素布局。
    """
    if not rgb_palette or not ramp.rgb_list:
        return list(rgb_palette)
    palette_lab = np.asarray([rgb_to_lab(rgb) for rgb in rgb_palette], dtype=np.float32)
    ramp_lab = np.asarray([rgb_to_lab(rgb) for rgb in ramp.rgb_list], dtype=np.float32)
    diff = palette_lab[:, None, :] - ramp_lab[None, :, :]
    dist = (diff * diff).sum(axis=-1)
    indices = dist.argmin(axis=1)
    return [ramp.rgb_list[int(i)] for i in indices]

