"""项目风格档案的 prompt 编译辅助。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


STYLE_PROFILE_POLICY_MAX_CHARS = 1000

STYLE_PROFILE_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("project_name", "Project reference", "项目风格参考"),
    ("palette", "Color palette", "配色方案"),
    ("line_style", "Line style", "线条风格"),
    ("lighting", "Lighting rule", "光照规则"),
    ("view_rule", "View rule", "视角规则"),
    ("avoid_elements", "Do not include", "避免元素"),
)


@dataclass(frozen=True)
class CompiledStyleProfile:
    """编译后的风格档案。"""

    prompt: str = ""
    applied: list[str] | None = None
    normalized: dict[str, str] | None = None

    @property
    def applied_rules(self) -> list[str]:
        return list(self.applied or [])

    @property
    def data(self) -> dict[str, str]:
        return dict(self.normalized or {})


def _as_mapping(value: Mapping[str, Any] | Any | None) -> Mapping[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        return dumped if isinstance(dumped, Mapping) else {}
    return {}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    # prompt 片段需要保持简洁；把换行、连续空白压成单空格，避免用户输入撑坏模板结构。
    return " ".join(str(value).strip().split())


def normalize_style_profile(style_profile: Mapping[str, Any] | Any | None) -> dict[str, str]:
    """清理风格档案，去掉空字段。"""

    source = _as_mapping(style_profile)
    normalized: dict[str, str] = {}
    for key, _prompt_label, _display_label in STYLE_PROFILE_FIELDS:
        text = _clean_text(source.get(key))
        if text:
            normalized[key] = text
    return normalized


def compile_style_profile(style_profile: Mapping[str, Any] | Any | None) -> CompiledStyleProfile:
    """把结构化风格档案编译为可注入 prompt 的补充段。"""

    normalized = normalize_style_profile(style_profile)
    if not normalized:
        return CompiledStyleProfile(prompt="", applied=[], normalized={})

    prompt_parts: list[str] = []
    applied: list[str] = []
    for key, prompt_label, display_label in STYLE_PROFILE_FIELDS:
        text = normalized.get(key)
        if not text:
            continue
        prompt_parts.append(f"{prompt_label}: {text}.")
        applied.append(f"{display_label}：{text}")

    return CompiledStyleProfile(
        prompt="Project style constraints: " + " ".join(prompt_parts),
        applied=applied,
        normalized=normalized,
    )


def style_profile_policy_text(style_profile: Mapping[str, Any] | Any | None) -> str:
    """返回用于 prompt policy 审核的用户可控风格文本。"""

    normalized = normalize_style_profile(style_profile)
    return "\n".join(normalized.values())
