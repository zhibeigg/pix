"""i18n 核心功能测试。"""

from __future__ import annotations

import pytest

from pix.i18n import (
    LANGUAGES,
    add_retranslate_hook,
    available_languages,
    clear_hooks,
    get_language,
    normalize_language,
    set_language,
    tr,
)


@pytest.fixture(autouse=True)
def _reset_state():
    """每个用例前都把语言恢复成默认，并清空钩子。"""
    clear_hooks()
    set_language("zh-CN")
    yield
    clear_hooks()
    set_language("zh-CN")


def test_default_language_is_zh_cn() -> None:
    assert get_language() == "zh-CN"


def test_available_languages_returns_nine() -> None:
    langs = available_languages()
    codes = [l.code for l in langs]
    assert "zh-CN" in codes
    assert "en" in codes
    assert "ja" in codes
    assert len(codes) == 9


@pytest.mark.parametrize(
    "inp, expected",
    [
        ("en", "en"),
        ("zh-CN", "zh-CN"),
        ("en-US", "en"),
        ("zh_CN", "zh-CN"),
        ("zh-Hans", "zh-CN"),
        ("zh-Hant-HK", "zh-TW"),
        ("fr-CA", "fr"),
        (None, "zh-CN"),
        ("", "zh-CN"),
        ("xx", "zh-CN"),
    ],
)
def test_normalize_language(inp, expected) -> None:
    assert normalize_language(inp) == expected


def test_set_language_triggers_hooks() -> None:
    calls = {"n": 0}
    add_retranslate_hook(lambda: calls.__setitem__("n", calls["n"] + 1))
    set_language("en")
    assert calls["n"] == 1
    # 切到相同语言不应重复触发
    set_language("en")
    assert calls["n"] == 1
    set_language("ja")
    assert calls["n"] == 2


def test_tr_fallback_chain() -> None:
    # 未知 key：返回 key 本身
    assert tr("__no_such_key__") == "__no_such_key__"
    # zh-CN 翻译
    assert tr("btn_run") == "运行"
    set_language("en")
    assert tr("btn_run") == "Run"
    set_language("ja")
    assert tr("btn_run") == "実行"


def test_tr_with_format() -> None:
    set_language("zh-CN")
    s = tr("log_run_ok", path="/tmp/out")
    assert "/tmp/out" in s


def test_tr_missing_key_returns_key_literally() -> None:
    assert tr("zz_doesnt_exist") == "zz_doesnt_exist"


def test_languages_have_all_default_keys() -> None:
    """保证每种语言都覆盖了默认语言的全部 key，避免漏译。"""
    from pix.i18n_catalog import CATALOG

    ref = set(CATALOG["zh-CN"].keys())
    for code, mapping in CATALOG.items():
        missing = ref - set(mapping.keys())
        assert not missing, f"语言 {code} 缺少 key: {sorted(missing)[:5]}"


def test_hook_can_be_removed() -> None:
    calls = {"n": 0}
    remove = add_retranslate_hook(lambda: calls.__setitem__("n", calls["n"] + 1))
    set_language("en")
    assert calls["n"] == 1
    remove()
    set_language("ja")
    assert calls["n"] == 1


def test_hook_exception_does_not_break_others() -> None:
    calls = {"ok": 0}

    def bad():
        raise RuntimeError("boom")

    add_retranslate_hook(bad)
    add_retranslate_hook(lambda: calls.__setitem__("ok", calls["ok"] + 1))
    set_language("en")
    assert calls["ok"] == 1
