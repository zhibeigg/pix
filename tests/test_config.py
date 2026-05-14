"""Config 合并优先级测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from pix.config import load_config, require_image_api_key, require_vl_api_key


def test_defaults(tmp_cwd: Path) -> None:
    cfg = load_config(config_file=None, env_file=None)
    assert cfg.api.base_url == "https://www.packyapi.com"
    assert cfg.image_gen.model == "gpt-image-2"
    assert cfg.image_gen.edit_input_fidelity == "high"
    assert cfg.image_gen.contact_sheet_enabled is True
    assert cfg.image_gen.contact_sheet_rows == 3
    assert cfg.image_gen.green_screen_color == "auto"
    assert cfg.image_gen.prompt_guard_enabled is True
    assert cfg.image_gen.candidate_vl_ranking_enabled is True
    assert cfg.image_gen.candidate_vl_ranking_failure_policy == "first"
    assert cfg.pixelize.output_size == (128, 128)
    assert cfg.asset.palette_mode == "auto"
    assert cfg.asset.grid_cleanup is False
    assert cfg.asset.grid_outline is False
    assert cfg.asset.fit_canvas is False
    assert "plain white background" in cfg.asset.prompt_template
    assert cfg.cache.enabled is True


def test_toml_overrides_defaults(tmp_cwd: Path) -> None:
    (tmp_cwd / "config.toml").write_text(
        """
[api]
base_url = "https://example.com"
[image_gen]
size = "1536x1024"
[pixelize]
output_size = [64, 48]
colors = 32
""",
        encoding="utf-8",
    )
    cfg = load_config(env_file=None)
    assert cfg.api.base_url == "https://example.com"
    assert cfg.image_gen.size == "1536x1024"
    assert cfg.pixelize.output_size == (64, 48)
    assert cfg.pixelize.colors == 32


def test_env_overrides_toml(
    tmp_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_cwd / "config.toml").write_text(
        """[api]
base_url = "https://foo.local"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("PACKY_BASE_URL", "https://env.example.com")
    monkeypatch.setenv("PACKY_API_KEY", "sk-image")
    monkeypatch.setenv("PACKY_VL_API_KEY", "sk-vl")
    cfg = load_config(env_file=None)
    assert cfg.api.base_url == "https://env.example.com"
    assert cfg.api.image_api_key == "sk-image"
    assert cfg.api.vl_api_key == "sk-vl"


def test_vl_key_falls_back_to_image_key(
    tmp_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PACKY_API_KEY", "sk-only")
    cfg = load_config(env_file=None)
    assert cfg.api.image_api_key == "sk-only"
    assert cfg.api.vl_api_key == "sk-only"


def test_overrides_beat_env(tmp_cwd: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PACKY_BASE_URL", "https://from-env")
    cfg = load_config(
        env_file=None,
        overrides={"api": {"base_url": "https://from-override"}},
    )
    assert cfg.api.base_url == "https://from-override"


def test_require_image_api_key_raises_when_missing(tmp_cwd: Path) -> None:
    cfg = load_config(env_file=None)
    with pytest.raises(RuntimeError):
        require_image_api_key(cfg)


def test_require_vl_api_key_uses_image_if_no_dedicated(
    tmp_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PACKY_API_KEY", "sk-image")
    cfg = load_config(env_file=None)
    assert require_vl_api_key(cfg) == "sk-image"


def test_overrides_list_coerced_to_tuple(tmp_cwd: Path) -> None:
    cfg = load_config(
        env_file=None,
        overrides={"pixelize": {"output_size": [32, 40]}},
    )
    assert cfg.pixelize.output_size == (32, 40)
