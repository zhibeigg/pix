"""GUI 冒烟测试：在 Qt minimal 平台下实例化主窗口。"""

from __future__ import annotations

import os
import sys

import pytest


pytest.importorskip("PySide6")


@pytest.fixture(scope="session")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "minimal")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_main_window_builds(qapp) -> None:
    from pix.gui.main_window import MainWindow

    w = MainWindow()
    try:
        assert "pix" in w.windowTitle()
        presets_data = [w.preset_combo.itemData(i) for i in range(w.preset_combo.count())]
        assert "gameboy" in presets_data
        # prompt / image 切换
        assert w.rb_prompt.isChecked()
        w.rb_image.setChecked(True)
        assert not w.prompt_edit.isEnabled()
        w.rb_prompt.setChecked(True)
        assert w.prompt_edit.isEnabled()
    finally:
        w.deleteLater()


def test_collect_inputs_prompt_mode(qapp) -> None:
    from pix.gui.main_window import MainWindow

    w = MainWindow()
    try:
        w.rb_prompt.setChecked(True)
        w.prompt_edit.setPlainText("pixel cat")
        w.pixel_size_edit.setText("64x64")
        w.colors_spin.setValue(8)
        inputs = w._collect_inputs()
        assert inputs.prompt == "pixel cat"
        assert inputs.pixelize_params.output_size == (64, 64)
        assert inputs.pixelize_params.colors == 8
    finally:
        w.deleteLater()


def test_collect_inputs_image_mode_requires_existing_path(qapp, tmp_path) -> None:
    from pix.gui.main_window import MainWindow

    w = MainWindow()
    try:
        w.rb_image.setChecked(True)
        w.image_path_edit.setText(str(tmp_path / "missing.png"))
        import pytest as _pt

        with _pt.raises(ValueError):
            w._collect_inputs()
    finally:
        w.deleteLater()


def test_collect_inputs_image_mode_with_real_path(qapp, sample_image) -> None:
    from pix.gui.main_window import MainWindow

    w = MainWindow()
    try:
        w.rb_image.setChecked(True)
        w.image_path_edit.setText(str(sample_image))
        inputs = w._collect_inputs()
        assert inputs.prompt is None
        assert inputs.image_path == sample_image
    finally:
        w.deleteLater()
