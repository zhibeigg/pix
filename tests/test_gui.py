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


def test_enable_faulthandler_tolerates_missing_stderr(monkeypatch) -> None:
    from pix.gui import app as gui_app

    monkeypatch.setattr(gui_app.sys, "stderr", None)
    gui_app._enable_faulthandler_safely()


def test_main_window_builds(qapp) -> None:
    from pix.gui.main_window import MainWindow

    w = MainWindow()
    try:
        assert "pix" in w.windowTitle()
        assert not w.windowIcon().isNull()
        presets_data = [w.preset_combo.itemData(i) for i in range(w.preset_combo.count())]
        assert "gameboy" in presets_data
        pixel_sizes = [w.pixel_size_edit.itemText(i) for i in range(w.pixel_size_edit.count())]
        assert "64x64" in pixel_sizes
        assert w.pixel_size_edit.isEditable()
        # prompt / image 切换
        assert w.rb_prompt.isChecked()
        assert w._act_history.text().strip() != ""
        top_actions = [a for a in w.menuBar().actions() if a.text()]
        assert w._act_history in top_actions
        assert w._act_settings in top_actions
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
        w.pixel_size_edit.setEditText("64x64")
        w.colors_spin.setValue(8)
        idx = w.edge_style_combo.findData("outline")
        assert idx >= 0
        w.edge_style_combo.setCurrentIndex(idx)
        w.bg_feather_spin.setValue(2)
        inputs = w._collect_inputs()
        assert inputs.prompt == "pixel cat"
        assert inputs.pixelize_params.output_size == (64, 64)
        assert inputs.pixelize_params.colors == 8
        assert inputs.pixelize_params.edge_style == "outline"
        assert inputs.pixelize_params.bg_feather == 2
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


def test_history_dialog_opens_non_modal(qapp) -> None:
    from pix.gui.main_window import MainWindow

    w = MainWindow()
    try:
        w._on_open_history()
        assert w._history_dialog is not None
        assert w._history_dialog.isModal() is False
        assert w.isEnabled() is True
        w._history_dialog.close()
    finally:
        w.deleteLater()


def test_load_history_record_updates_main_window(qapp, tmp_path) -> None:
    import json
    from datetime import datetime

    from PIL import Image

    from pix.gui.main_window import MainWindow
    from pix.history import HistoryRecord

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    source = run_dir / "01_source.png"
    pixel = run_dir / "03_pixelized.png"
    analysis = run_dir / "02_analysis.json"
    meta_path = run_dir / "meta.json"
    Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(source)
    Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(pixel)
    analysis.write_text('{"description":"ok"}', encoding="utf-8")
    meta_path.write_text(json.dumps({"pixelize": {}}), encoding="utf-8")
    record = HistoryRecord(
        run_dir=run_dir,
        created_at=datetime.now(),
        prompt="历史 prompt",
        image_path=None,
        source_path=source,
        analysis_path=analysis,
        pixel_path=pixel,
        preview_path=None,
        meta_path=meta_path,
        image_model="gpt-image-2",
        vision_model="claude-opus-4-7",
        pixel_size=(32, 32),
        colors=12,
        dither="none",
        preset="auto",
        remove_bg=True,
        bg_tolerance=20,
        bg_feather=0,
        edge_style="hard",
        duration_seconds=1.0,
        ok=True,
        version="0.2.0",
    )

    w = MainWindow()
    try:
        w._load_history_record(record)
        assert w.prompt_edit.toPlainText() == "历史 prompt"
        assert w.pixel_size_edit.currentText() == "32x32"
        assert w.colors_spin.value() == 12
        assert w.remove_bg_chk.isChecked() is True
        assert w._last_result is not None
        assert w._last_result.run_dir == run_dir
        assert not w.source_panel._pixmap_item.pixmap().isNull()
        assert not w.pixel_panel._pixmap_item.pixmap().isNull()
    finally:
        w.deleteLater()
