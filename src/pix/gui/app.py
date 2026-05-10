"""QApplication 入口。"""

from __future__ import annotations

import faulthandler
import sys
from pathlib import Path


def run_gui(config_file: Path | None = None) -> int:
    """阻塞式启动 GUI。"""
    # 打开 faulthandler，捕获 native 层崩溃的 Python 栈
    faulthandler.enable()

    from PySide6.QtWidgets import QApplication

    from pix.gui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(config_file=config_file)
    window.show()
    return app.exec()
