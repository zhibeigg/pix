"""ZoomablePreview 基础行为测试。"""

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


def test_show_and_clear(qapp, sample_image: Path) -> None:
    from pix.gui.preview_panel import ZoomablePreview

    p = ZoomablePreview(pixel_mode=False)
    try:
        p.show_image(sample_image)
        assert not p._pixmap_item.pixmap().isNull()
        p.clear_image()
        assert p._pixmap_item.pixmap().isNull()
    finally:
        p.deleteLater()


def test_pixel_mode_uses_fast_transform(qapp, sample_image: Path) -> None:
    from PySide6.QtCore import Qt

    from pix.gui.preview_panel import ZoomablePreview

    p = ZoomablePreview(pixel_mode=True)
    try:
        p.show_image(sample_image)
        assert p._pixmap_item.transformationMode() == Qt.TransformationMode.FastTransformation
    finally:
        p.deleteLater()


def test_reset_view_resets_user_zoom(qapp, sample_image: Path) -> None:
    from pix.gui.preview_panel import ZoomablePreview

    p = ZoomablePreview()
    try:
        p.show_image(sample_image)
        p._user_zoomed = True
        p.reset_view()
        assert p._user_zoomed is False
    finally:
        p.deleteLater()


def test_missing_file_shows_error(qapp, tmp_path: Path) -> None:
    from pix.gui.preview_panel import ZoomablePreview

    p = ZoomablePreview()
    try:
        p.show_image(tmp_path / "missing.png")
        # placeholder 可见，pixmap 为空
        assert p._placeholder.isVisible()
        assert p._pixmap_item.pixmap().isNull()
    finally:
        p.deleteLater()


def test_context_menu_actions_present(qapp, sample_image: Path) -> None:
    from pix.gui.preview_panel import ZoomablePreview

    p = ZoomablePreview()
    try:
        p.show_image(sample_image)
        # 所有右键 action 都存在且有翻译文案
        for act in [
            p._act_copy, p._act_save_as, p._act_copy_path,
            p._act_reveal, p._act_reset, p._act_actual_size,
        ]:
            assert act.text().strip() != ""
    finally:
        p.deleteLater()


def test_copy_to_clipboard(qapp, sample_image: Path) -> None:
    from PySide6.QtGui import QGuiApplication, QImage

    from pix.gui.preview_panel import ZoomablePreview

    p = ZoomablePreview()
    try:
        p.show_image(sample_image)
        # 先清掉剪贴板，再触发复制
        QGuiApplication.clipboard().clear()
        p._copy_image_to_clipboard()
        mime = QGuiApplication.clipboard().mimeData()
        assert mime is not None
        assert mime.hasImage()
        assert mime.hasUrls()
        assert Path(mime.urls()[0].toLocalFile()) == sample_image
        assert mime.hasFormat("image/png")
        copied = QImage(mime.imageData())
        original = QImage(str(sample_image))
        assert copied.size() == original.size()
    finally:
        p.deleteLater()


def test_copy_transparent_png_prefers_original_png_bytes(qapp, tmp_path: Path) -> None:
    from PIL import Image
    from PySide6.QtGui import QGuiApplication

    from pix.gui.preview_panel import ZoomablePreview

    image_path = tmp_path / "transparent.png"
    Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(image_path)

    p = ZoomablePreview(pixel_mode=True)
    try:
        p.show_image(image_path)
        QGuiApplication.clipboard().clear()
        p._copy_image_to_clipboard()
        mime = QGuiApplication.clipboard().mimeData()
        assert mime is not None
        assert mime.hasUrls()
        assert Path(mime.urls()[0].toLocalFile()) == image_path
        assert mime.hasFormat("image/png")
        assert mime.hasFormat("PNG")
        assert bytes(mime.data("image/png")) == image_path.read_bytes()
        # 同时提供标准 imageData，保证只识别位图剪贴板格式的目标程序也能粘贴。
        assert mime.hasImage()
    finally:
        p.deleteLater()


def test_save_as_writes_file(qapp, sample_image: Path, tmp_path: Path, monkeypatch) -> None:
    """绕过 QFileDialog，直接调内部保存逻辑。"""
    from pix.gui.preview_panel import ZoomablePreview

    dest = tmp_path / "exported.png"
    monkeypatch.setattr(
        "pix.gui.preview_panel.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(dest), "PNG (*.png)"),
    )

    p = ZoomablePreview()
    try:
        p.show_image(sample_image)
        p._save_as()
        assert dest.exists() and dest.stat().st_size > 0
    finally:
        p.deleteLater()


def test_copy_path_puts_path_on_clipboard(qapp, sample_image: Path) -> None:
    from PySide6.QtGui import QGuiApplication

    from pix.gui.preview_panel import ZoomablePreview

    p = ZoomablePreview()
    try:
        p.show_image(sample_image)
        QGuiApplication.clipboard().clear()
        p._copy_path()
        assert QGuiApplication.clipboard().text() == str(sample_image)
    finally:
        p.deleteLater()


def test_actual_size_sets_unit_transform(qapp, sample_image: Path) -> None:
    from pix.gui.preview_panel import ZoomablePreview

    p = ZoomablePreview()
    try:
        p.show_image(sample_image)
        p.actual_size()
        t = p.transform()
        assert abs(t.m11() - 1.0) < 1e-6
        assert abs(t.m22() - 1.0) < 1e-6
        assert p._user_zoomed is True
    finally:
        p.deleteLater()
