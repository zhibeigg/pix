"""SettingsDialog GUI 测试（Qt minimal 平台）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "minimal")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_dialog_builds_and_defaults(qapp, tmp_cwd: Path) -> None:
    from pix.gui.settings_dialog import SettingsDialog

    dlg = SettingsDialog(
        env_path=tmp_cwd / ".env",
        config_path=tmp_cwd / "config.toml",
    )
    try:
        # 默认有 3 个提供商
        assert dlg.provider_combo.count() >= 3
        # 切换到 custom 不崩
        dlg.provider_combo.setCurrentIndex(dlg.provider_combo.findData("custom"))
        # 切换到 openai 会填上默认模型
        dlg.provider_combo.setCurrentIndex(dlg.provider_combo.findData("openai"))
        assert dlg.base_url_edit.text() == "https://api.openai.com"
    finally:
        dlg.deleteLater()


def test_dialog_validate_empty(qapp, tmp_cwd: Path) -> None:
    """没填 key 时点保存应该给出错误列表。"""
    from pix.gui.settings_dialog import SettingsDialog, _validate

    dlg = SettingsDialog(
        env_path=tmp_cwd / ".env",
        config_path=tmp_cwd / "config.toml",
    )
    try:
        dlg.image_key_edit.setText("")
        dlg.vl_key_edit.setText("")
        s = dlg._current_from_ui()
        errs = _validate(s)
        assert any("API key" in e for e in errs)
    finally:
        dlg.deleteLater()


def test_dialog_save_persists(qapp, tmp_cwd: Path, monkeypatch) -> None:
    from pix.gui.settings_dialog import SettingsDialog

    monkeypatch.delenv("PACKY_API_KEY", raising=False)
    env_path = tmp_cwd / ".env"
    cfg_path = tmp_cwd / "config.toml"
    dlg = SettingsDialog(env_path=env_path, config_path=cfg_path)
    try:
        dlg.image_key_edit.setText("sk-test-image")
        dlg.vl_key_edit.setText("sk-test-vl")
        dlg.image_model_edit.setText("gpt-image-2")
        dlg.vision_model_edit.setText("claude-sonnet-4-5")
        dlg.image_size_edit.setText("1024x1024")
        dlg._on_save()  # 直接触发保存逻辑
        assert dlg.was_saved()
        env_text = env_path.read_text(encoding="utf-8")
        assert "PACKY_API_KEY=sk-test-image" in env_text
        assert "PACKY_VL_API_KEY=sk-test-vl" in env_text
        cfg_text = cfg_path.read_text(encoding="utf-8")
        assert "gpt-image-2" in cfg_text
        assert "claude-sonnet-4-5" in cfg_text
    finally:
        dlg.deleteLater()


def test_main_window_settings_integration(qapp, tmp_cwd: Path, monkeypatch) -> None:
    """MainWindow 暴露了 _on_open_settings 与 _reload_config；保存后应能刷新状态。"""
    from pix.gui.main_window import MainWindow

    monkeypatch.delenv("PACKY_API_KEY", raising=False)

    w = MainWindow()
    try:
        assert callable(w._on_open_settings)
        # 直接手工调用 _reload_config 不抛异常
        w._reload_config()
        # 手动把配置换成带 key 的版本，看状态栏提示
        w.cfg.api.image_api_key = "sk-yes"
        w._refresh_status_bar()
        assert "未配置" not in w._status.currentMessage()
    finally:
        w.deleteLater()
