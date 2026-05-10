"""QApplication 入口。"""

from __future__ import annotations

import faulthandler
import sys
from pathlib import Path


def _enable_faulthandler_safely() -> None:
    """在有 stderr 时开启 faulthandler；兼容 PyInstaller windowed 模式。

    Windows 上 PyInstaller `console=False` 启动时 `sys.stderr` 可能是 None，
    直接调用 `faulthandler.enable()` 会 RuntimeError 并导致 GUI 启动前崩溃。
    """
    if sys.stderr is None:
        return
    try:
        faulthandler.enable(file=sys.stderr)
    except (RuntimeError, ValueError):
        return


def run_gui(config_file: Path | None = None) -> int:
    """阻塞式启动 GUI。"""
    # 打开 faulthandler，捕获 native 层崩溃的 Python 栈；windowed 打包时需安全降级。
    _enable_faulthandler_safely()

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from pix.gui.main_window import MainWindow
    from pix.resources import app_icon_path

    app = QApplication.instance() or QApplication(sys.argv)
    icon = QIcon(str(app_icon_path()))
    if not icon.isNull():
        app.setWindowIcon(icon)
    window = MainWindow(config_file=config_file)
    window.show()
    return app.exec()
