"""轻量级 i18n 运行时。

选择自己实现而不是 Qt .ts/.qm 的理由：
- 不需要 lrelease / pyside6-linguist 预编译
- 开发时直接在 Python 里改 key 和译文，热切换更顺手
- 需要 combobox 选项翻译时直接 tr() 即可，与 Qt 的 translator 无冲突

用法：
    from pix.i18n import tr, set_language, add_retranslate_hook
    label.setText(tr("run"))
    set_language("en")   # 会触发所有注册的 retranslate 回调
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pix.i18n_catalog import CATALOG, DEFAULT_LANGUAGE


@dataclass(frozen=True)
class Language:
    code: str
    label: str              # 界面里显示的名字（用自身语言写）
    english_label: str      # 便于调试


# 支持的语言列表，顺序决定下拉框里的顺序
LANGUAGES: list[Language] = [
    Language("zh-CN", "简体中文", "Simplified Chinese"),
    Language("zh-TW", "繁體中文", "Traditional Chinese"),
    Language("en", "English", "English"),
    Language("ja", "日本語", "Japanese"),
    Language("ko", "한국어", "Korean"),
    Language("fr", "Français", "French"),
    Language("de", "Deutsch", "German"),
    Language("es", "Español", "Spanish"),
    Language("ru", "Русский", "Russian"),
]

_LANG_CODES = {lang.code for lang in LANGUAGES}


# ---------- 状态 ----------


_current_language: str = DEFAULT_LANGUAGE
_retranslate_hooks: list[Callable[[], None]] = []


def get_language() -> str:
    return _current_language


def normalize_language(code: str | None) -> str:
    """规范化语言 code；未知则回退到默认语言。"""
    if not code:
        return DEFAULT_LANGUAGE
    code = code.strip()
    if code in _LANG_CODES:
        return code
    # 只认短语（en-US → en、zh-Hans-CN → zh-CN 近似归并）
    lower = code.lower().replace("_", "-")
    if lower.startswith("zh-hans") or lower == "zh" or lower.startswith("zh-cn"):
        return "zh-CN"
    if lower.startswith("zh-hant") or lower.startswith("zh-tw") or lower.startswith("zh-hk"):
        return "zh-TW"
    prefix = lower.split("-", 1)[0]
    for lang in LANGUAGES:
        if lang.code.startswith(prefix):
            return lang.code
    return DEFAULT_LANGUAGE


def set_language(code: str) -> str:
    """切换当前语言并通知所有注册的 retranslate hook。返回实际生效的 code。"""
    global _current_language
    normalized = normalize_language(code)
    if normalized == _current_language:
        return _current_language
    _current_language = normalized
    # 触发全部重翻译；即使某个 hook 异常也不要影响其它
    for hook in list(_retranslate_hooks):
        try:
            hook()
        except Exception:  # pragma: no cover
            pass
    return _current_language


def add_retranslate_hook(hook: Callable[[], None]) -> Callable[[], None]:
    """注册一个"重翻译"回调，返回反注册函数。"""
    _retranslate_hooks.append(hook)

    def _remove() -> None:
        try:
            _retranslate_hooks.remove(hook)
        except ValueError:
            pass

    return _remove


def clear_hooks() -> None:
    """清空所有 hook，主要给测试用。"""
    _retranslate_hooks.clear()


# ---------- 翻译查表 ----------


def tr(key: str, **kwargs) -> str:
    """翻译 key；找不到时回退到默认语言，再找不到就返回 key 本身。

    可选 **kwargs 用于 str.format 风格占位，例如：
        tr("saved_to", env=".env", config="config.toml")
    """
    lang_map = CATALOG.get(_current_language, {})
    text = lang_map.get(key)
    if text is None:
        text = CATALOG.get(DEFAULT_LANGUAGE, {}).get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text


def available_languages() -> list[Language]:
    return list(LANGUAGES)
