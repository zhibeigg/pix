"""GUI 切语言后的 retranslate 行为。"""

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


@pytest.fixture(autouse=True)
def _reset_language():
    from pix.i18n import clear_hooks, set_language

    clear_hooks()
    set_language("zh-CN")
    yield
    clear_hooks()
    set_language("zh-CN")


def test_main_window_retranslates(qapp) -> None:
    from pix.gui.main_window import MainWindow
    from pix.i18n import set_language

    w = MainWindow()
    try:
        # 中文默认
        assert "运行" in w.run_btn.text()
        set_language("en")
        assert w.run_btn.text() == "Run"
        set_language("ja")
        assert w.run_btn.text() == "実行"
    finally:
        w.deleteLater()


def test_combo_data_stable_across_language_switch(qapp) -> None:
    """切语言只改显示文字，combobox 的 itemData（真值）保持不变。"""
    from pix.gui.main_window import MainWindow
    from pix.i18n import set_language

    w = MainWindow()
    try:
        preset_data_zh = [
            w.preset_combo.itemData(i) for i in range(w.preset_combo.count())
        ]
        set_language("en")
        preset_data_en = [
            w.preset_combo.itemData(i) for i in range(w.preset_combo.count())
        ]
        assert preset_data_zh == preset_data_en

        dither_data = [
            w.dither_combo.itemData(i) for i in range(w.dither_combo.count())
        ]
        assert "floyd_steinberg" in dither_data
    finally:
        w.deleteLater()


def test_saving_settings_updates_language(qapp, tmp_cwd: Path, monkeypatch) -> None:
    """保存设置对话框里选择的语言，主窗口 reload 后 retranslate 到新语言。"""
    from pix.gui.main_window import MainWindow
    from pix.gui.settings_dialog import SettingsDialog

    monkeypatch.delenv("PACKY_API_KEY", raising=False)
    env_path = tmp_cwd / ".env"
    cfg_path = tmp_cwd / "config.toml"

    w = MainWindow(config_file=cfg_path)
    try:
        # 初始中文
        assert "运行" in w.run_btn.text()

        dlg = SettingsDialog(parent=w, env_path=env_path, config_path=cfg_path)
        try:
            # 填最少信息让保存通过
            dlg.image_key_edit.setText("sk-test")
            idx = dlg.language_combo.findData("en")
            dlg.language_combo.setCurrentIndex(idx)
            dlg._on_save()
            assert dlg.was_saved()
        finally:
            dlg.deleteLater()

        # 主窗口 reload 并同步到英文
        w._reload_config()
        assert w.run_btn.text() == "Run"

        cfg_text = cfg_path.read_text(encoding="utf-8")
        assert '"en"' in cfg_text or "= \"en\"" in cfg_text
    finally:
        w.deleteLater()


def test_settings_dialog_preview_language(qapp, tmp_cwd: Path) -> None:
    """对话框内改语言下拉会立即 preview，但取消时恢复。"""
    from pix.gui.settings_dialog import SettingsDialog
    from pix.i18n import get_language

    env_path = tmp_cwd / ".env"
    cfg_path = tmp_cwd / "config.toml"

    dlg = SettingsDialog(env_path=env_path, config_path=cfg_path)
    try:
        assert get_language() == "zh-CN"
        idx = dlg.language_combo.findData("ja")
        dlg.language_combo.setCurrentIndex(idx)
        assert get_language() == "ja"
        # 取消
        dlg.reject()
        assert get_language() == "zh-CN"
    finally:
        dlg.deleteLater()
