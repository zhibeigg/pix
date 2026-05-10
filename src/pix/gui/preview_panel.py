"""可缩放/拖拽的图片预览面板：左键平移、滚轮缩放、双击复位、右键菜单。"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QMimeData, QRectF, Qt, QUrl
from PySide6.QtGui import (
    QAction,
    QDesktopServices,
    QGuiApplication,
    QImage,
    QMouseEvent,
    QPainter,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QMenu,
    QMessageBox,
)

from pix.i18n import add_retranslate_hook, tr


class ZoomablePreview(QGraphicsView):
    """图片预览 widget。

    - 左键拖拽平移（ScrollHandDrag）
    - 滚轮以鼠标位置为锚点缩放
    - 双击回到适屏
    - 右键菜单：复制 / 另存为 / 复制路径 / 打开所在文件夹 / 重置 / 1:1
    - pixel_mode=True 用 NEAREST 插值，保留像素边缘
    """

    MIN_SCALE = 0.05
    MAX_SCALE = 40.0
    ZOOM_FACTOR = 1.2

    def __init__(self, pixel_mode: bool = False) -> None:
        super().__init__()
        self._pixel_mode = pixel_mode

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._pixmap_item = QGraphicsPixmapItem()
        transform_mode = (
            Qt.TransformationMode.FastTransformation
            if pixel_mode
            else Qt.TransformationMode.SmoothTransformation
        )
        self._pixmap_item.setTransformationMode(transform_mode)
        self._scene.addItem(self._pixmap_item)

        self._placeholder = QGraphicsSimpleTextItem("(no image)")
        self._placeholder.setBrush(Qt.GlobalColor.gray)
        self._scene.addItem(self._placeholder)

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, not pixel_mode)
        self.setBackgroundBrush(Qt.GlobalColor.darkGray)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

        self._current_path: Optional[Path] = None
        self._user_zoomed = False

        # 预创建 actions，方便 retranslate
        self._act_copy = QAction(self)
        self._act_copy.triggered.connect(self._copy_image_to_clipboard)
        self._act_save_as = QAction(self)
        self._act_save_as.triggered.connect(self._save_as)
        self._act_copy_path = QAction(self)
        self._act_copy_path.triggered.connect(self._copy_path)
        self._act_reveal = QAction(self)
        self._act_reveal.triggered.connect(self._reveal_in_explorer)
        self._act_reset = QAction(self)
        self._act_reset.triggered.connect(self.reset_view)
        self._act_actual_size = QAction(self)
        self._act_actual_size.triggered.connect(self.actual_size)

        self._retranslate()
        self._unregister = add_retranslate_hook(self._retranslate)

    # ---------- 对外 API ----------

    def show_image(self, path: Path) -> None:
        pix = QPixmap(str(path))
        if pix.isNull():
            self._pixmap_item.setPixmap(QPixmap())
            self._placeholder.setText(tr("preview_cannot_load", path=str(path)))
            self._placeholder.setVisible(True)
            self._scene.setSceneRect(self._placeholder.boundingRect())
        else:
            self._pixmap_item.setPixmap(pix)
            self._placeholder.setVisible(False)
            self._scene.setSceneRect(QRectF(pix.rect()))
            self.reset_view()
        self._current_path = path

    def clear_image(self) -> None:
        self._pixmap_item.setPixmap(QPixmap())
        self._placeholder.setText(tr("preview_placeholder"))
        self._placeholder.setVisible(True)
        self._scene.setSceneRect(self._placeholder.boundingRect())
        self._current_path = None

    def reset_view(self) -> None:
        """复位到适屏状态。"""
        self.resetTransform()
        if not self._pixmap_item.pixmap().isNull():
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        self._user_zoomed = False

    def actual_size(self) -> None:
        """把缩放重置到 1:1。"""
        self.resetTransform()
        self._user_zoomed = True

    # ---------- 右键菜单 ----------

    def _on_context_menu(self, pos) -> None:
        if self._pixmap_item.pixmap().isNull():
            return
        menu = QMenu(self)
        menu.addAction(self._act_copy)
        menu.addAction(self._act_save_as)
        menu.addSeparator()
        # 只有从落盘路径加载的图才能显示"复制路径/打开文件夹"
        has_path = self._current_path is not None and self._current_path.exists()
        self._act_copy_path.setEnabled(has_path)
        self._act_reveal.setEnabled(has_path)
        menu.addAction(self._act_copy_path)
        menu.addAction(self._act_reveal)
        menu.addSeparator()
        menu.addAction(self._act_reset)
        menu.addAction(self._act_actual_size)
        menu.exec(self.viewport().mapToGlobal(pos))

    def _copy_image_to_clipboard(self) -> None:
        pix = self._pixmap_item.pixmap()
        if pix.isNull():
            return

        mime = QMimeData()
        image = QImage()
        copied_file_bytes = False
        if self._current_path is not None and self._current_path.exists():
            # 从源文件重新读取，避免复制 QGraphicsView 当前显示/缩放状态或 QPixmap 后端格式。
            image = QImage(str(self._current_path))
            mime.setUrls([QUrl.fromLocalFile(str(self._current_path))])
            mime_type = _mime_from_suffix(self._current_path.suffix)
            if mime_type:
                try:
                    raw = self._current_path.read_bytes()
                    mime.setData(mime_type, raw)
                    # Windows 剪贴板里不少程序识别注册格式 PNG，而不是 MIME 名 image/png。
                    if mime_type == "image/png":
                        mime.setData("PNG", raw)
                    copied_file_bytes = True
                except OSError:
                    pass
        if image.isNull():
            image = pix.toImage()
        if image.isNull():
            return
        # 对带 alpha 的 PNG，不再设置 imageData：Qt/Windows 会同时导出 CF_DIB，
        # 很多目标程序优先读取 DIB，透明通道会被灰/白背景合成。只放原始 PNG 字节。
        if not (copied_file_bytes and image.hasAlphaChannel()):
            mime.setImageData(image)
        QGuiApplication.clipboard().setMimeData(mime)

    def _save_as(self) -> None:
        pix = self._pixmap_item.pixmap()
        if pix.isNull():
            return
        suggested = ""
        if self._current_path is not None:
            suggested = self._current_path.name
        dest, selected_filter = QFileDialog.getSaveFileName(
            self,
            tr("preview_save_as_title"),
            suggested,
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp);;WebP (*.webp)",
        )
        if not dest:
            return
        # 根据扩展名决定格式；没有扩展名时按过滤器补 .png
        dest_path = Path(dest)
        if dest_path.suffix == "":
            dest_path = dest_path.with_suffix(".png")
        fmt = _format_from_suffix(dest_path.suffix)
        ok = pix.save(str(dest_path), fmt)
        if not ok:
            QMessageBox.warning(
                self, tr("preview_save_failed_title"),
                tr("preview_save_failed_body", path=str(dest_path)),
            )

    def _copy_path(self) -> None:
        if self._current_path is None:
            return
        QGuiApplication.clipboard().setText(str(self._current_path))

    def _reveal_in_explorer(self) -> None:
        if self._current_path is None or not self._current_path.exists():
            return
        _reveal_in_os_file_manager(self._current_path)

    # ---------- 翻译 ----------

    def _retranslate(self) -> None:
        self._act_copy.setText(tr("preview_ctx_copy"))
        self._act_save_as.setText(tr("preview_ctx_save_as"))
        self._act_copy_path.setText(tr("preview_ctx_copy_path"))
        self._act_reveal.setText(tr("preview_ctx_reveal"))
        self._act_reset.setText(tr("preview_ctx_reset"))
        self._act_actual_size.setText(tr("preview_ctx_actual_size"))
        # 占位文字（如果当前没图）
        if self._pixmap_item.pixmap().isNull() and self._current_path is None:
            self._placeholder.setText(tr("preview_placeholder"))

    # ---------- 交互 ----------

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._pixmap_item.pixmap().isNull():
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return
        factor = self.ZOOM_FACTOR if delta > 0 else 1 / self.ZOOM_FACTOR
        current = self.transform().m11()
        new_scale = current * factor
        if new_scale < self.MIN_SCALE or new_scale > self.MAX_SCALE:
            event.accept()
            return
        self.scale(factor, factor)
        self._user_zoomed = True
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.reset_view()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if not self._user_zoomed and not self._pixmap_item.pixmap().isNull():
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if not self._user_zoomed and not self._pixmap_item.pixmap().isNull():
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)


def _mime_from_suffix(suffix: str) -> str | None:
    s = suffix.lower().lstrip(".")
    if s == "png":
        return "image/png"
    if s in ("jpg", "jpeg"):
        return "image/jpeg"
    if s == "bmp":
        return "image/bmp"
    if s == "webp":
        return "image/webp"
    return None


def _format_from_suffix(suffix: str) -> str:
    s = suffix.lower().lstrip(".")
    if s in ("jpg", "jpeg"):
        return "JPEG"
    if s == "png":
        return "PNG"
    if s == "bmp":
        return "BMP"
    if s == "webp":
        return "WEBP"
    return "PNG"


def _reveal_in_os_file_manager(path: Path) -> None:
    """跨平台在资源管理器中选中并显示该文件。"""
    p = str(path)
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.Popen(["explorer", "/select,", p])
            return
        if system == "Darwin":
            subprocess.Popen(["open", "-R", p])
            return
        # Linux / BSD：没统一的"选中"接口，退而打开所在目录
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
    except Exception:
        # 兜底：Qt 打开父目录
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
