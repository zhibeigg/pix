"""settings 模块读写测试。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pix.settings import (
    PROVIDERS,
    UserSettings,
    detect_provider,
    get_provider,
    load_settings,
    read_env_file,
    read_toml,
    save_settings,
    write_env_file,
    write_toml_merged,
)


class TestProviders:
    def test_packy_is_first(self) -> None:
        assert PROVIDERS[0].key == "packy"

    def test_get_provider(self) -> None:
        assert get_provider("packy").default_image_model == "gpt-image-2"
        assert get_provider("unknown").key == "custom"

    def test_detect_provider(self) -> None:
        assert detect_provider("https://www.packyapi.com").key == "packy"
        assert detect_provider("https://www.packyapi.com/").key == "packy"
        assert detect_provider("https://api.openai.com").key == "openai"
        assert detect_provider("https://my.proxy.local").key == "custom"


class TestEnvFile:
    def test_read_nonexistent(self, tmp_path: Path) -> None:
        assert read_env_file(tmp_path / "nope") == {}

    def test_read_basic(self, tmp_path: Path) -> None:
        p = tmp_path / ".env"
        p.write_text(
            "# comment\nPACKY_API_KEY=sk-abc\nX=\"has space\"\nY='single'\n",
            encoding="utf-8",
        )
        d = read_env_file(p)
        assert d == {"PACKY_API_KEY": "sk-abc", "X": "has space", "Y": "single"}

    def test_write_preserves_comments(self, tmp_path: Path) -> None:
        p = tmp_path / ".env"
        p.write_text(
            "# my comment\nPACKY_API_KEY=old-key\nOTHER=unchanged\n",
            encoding="utf-8",
        )
        write_env_file(p, {"PACKY_API_KEY": "new-key"})
        content = p.read_text(encoding="utf-8")
        assert "# my comment" in content
        assert "PACKY_API_KEY=new-key" in content
        assert "old-key" not in content
        assert "OTHER=unchanged" in content

    def test_write_adds_new_keys(self, tmp_path: Path) -> None:
        p = tmp_path / ".env"
        p.write_text("EXISTING=1\n", encoding="utf-8")
        write_env_file(p, {"PACKY_VL_API_KEY": "sk-vl"})
        text = p.read_text(encoding="utf-8")
        assert "EXISTING=1" in text
        assert "PACKY_VL_API_KEY=sk-vl" in text

    def test_empty_value_comments_out(self, tmp_path: Path) -> None:
        p = tmp_path / ".env"
        p.write_text("PACKY_API_KEY=old\n", encoding="utf-8")
        write_env_file(p, {"PACKY_API_KEY": ""})
        text = p.read_text(encoding="utf-8")
        assert "# PACKY_API_KEY=old" in text

    def test_quotes_when_needed(self, tmp_path: Path) -> None:
        p = tmp_path / ".env"
        write_env_file(p, {"PACKY_BASE_URL": "https://a b/c"})
        text = p.read_text(encoding="utf-8")
        assert 'PACKY_BASE_URL="https://a b/c"' in text


class TestTomlMerge:
    def test_create_new(self, tmp_path: Path) -> None:
        p = tmp_path / "config.toml"
        write_toml_merged(p, {"api": {"base_url": "https://x"}})
        data = read_toml(p)
        assert data["api"]["base_url"] == "https://x"

    def test_merge_preserves_other_sections(self, tmp_path: Path) -> None:
        p = tmp_path / "config.toml"
        p.write_text(
            """[api]
base_url = "https://old"
[cache]
enabled = false
""",
            encoding="utf-8",
        )
        write_toml_merged(p, {"api": {"base_url": "https://new"}})
        data = read_toml(p)
        assert data["api"]["base_url"] == "https://new"
        assert data["cache"]["enabled"] is False  # 其他小节保留

    def test_merge_preserves_other_keys_in_section(self, tmp_path: Path) -> None:
        p = tmp_path / "config.toml"
        p.write_text(
            """[image_gen]
model = "old"
size = "1024x1024"
""",
            encoding="utf-8",
        )
        write_toml_merged(p, {"image_gen": {"model": "new-model"}})
        data = read_toml(p)
        assert data["image_gen"]["model"] == "new-model"
        assert data["image_gen"]["size"] == "1024x1024"


class TestRoundtrip:
    def test_save_then_load(
        self, tmp_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PACKY_API_KEY", raising=False)
        env_path = tmp_cwd / ".env"
        cfg_path = tmp_cwd / "config.toml"
        s = UserSettings(
            provider_key="packy",
            base_url="https://www.packyapi.com",
            image_api_key="sk-image",
            vl_api_key="sk-vl",
            image_model="gpt-image-2",
            image_size="1536x1024",
            image_quality="medium",
            vision_model="gemini-2.5-pro",
        )
        result = save_settings(s, env_path, cfg_path)
        assert env_path.exists()
        assert cfg_path.exists()
        assert set(result.updated_env_keys) == {"PACKY_API_KEY", "PACKY_VL_API_KEY", "PACKY_BASE_URL"}

        env = read_env_file(env_path)
        assert env["PACKY_API_KEY"] == "sk-image"
        assert env["PACKY_VL_API_KEY"] == "sk-vl"
        assert env["PACKY_BASE_URL"] == "https://www.packyapi.com"

        # 保存后，进程环境变量也应同步
        assert os.environ["PACKY_API_KEY"] == "sk-image"

        loaded = load_settings(env_path, cfg_path)
        assert loaded.image_api_key == "sk-image"
        assert loaded.vl_api_key == "sk-vl"
        assert loaded.image_model == "gpt-image-2"
        assert loaded.image_size == "1536x1024"
        assert loaded.vision_model == "gemini-2.5-pro"
        assert loaded.provider_key == "packy"

    def test_save_empty_key_removes_env_line(
        self, tmp_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PACKY_API_KEY", raising=False)
        env_path = tmp_cwd / ".env"
        cfg_path = tmp_cwd / "config.toml"
        s = UserSettings(
            provider_key="packy",
            base_url="https://www.packyapi.com",
            image_api_key="sk-image",
            vl_api_key="",
            image_model="gpt-image-2",
            image_size="1024x1024",
            image_quality="high",
            vision_model="claude-sonnet-4-5",
        )
        save_settings(s, env_path, cfg_path)
        # VL key 没填，不应写入
        env_text = env_path.read_text(encoding="utf-8")
        assert "PACKY_VL_API_KEY=" not in env_text or "# PACKY_VL_API_KEY=" in env_text
