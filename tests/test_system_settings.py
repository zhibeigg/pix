from __future__ import annotations

from pix_web.system_settings import SETTING_DEFINITIONS


def test_legacy_provider_secret_settings_are_hidden_from_admin_settings() -> None:
    keys = {item.key for item in SETTING_DEFINITIONS}

    assert "pix.api.base_url" not in keys
    assert "pix.api.image_api_key" not in keys
    assert "pix.api.vl_api_key" not in keys
    assert "pix.api.gemini_api_key" not in keys


def test_provider_runtime_strategy_settings_remain_visible() -> None:
    keys = {item.key for item in SETTING_DEFINITIONS}

    assert "pix.api.timeout" in keys
    assert "pix.api.max_retries" in keys
    assert "pix.api.trust_env_proxies" in keys
    assert "pix.api.proxy" in keys
    assert "pix.image_gen.model" in keys
