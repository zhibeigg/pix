"""PyInstaller 打包入口。

行为：
- 无命令行参数时（比如用户双击 .exe/.app）直接启动 GUI
- 有参数时按 CLI 处理（`pix gen "..."`、`pix pixelize a.png` 等）
"""

from __future__ import annotations

import sys


def main() -> int:
    # 至少包含 argv[0]；argv 长度 1 表示用户直接启动，没带子命令
    if len(sys.argv) <= 1:
        from pix.gui.app import run_gui

        return int(run_gui() or 0)

    from pix.cli import app

    app()  # Typer 会自己 sys.exit
    return 0


if __name__ == "__main__":
    sys.exit(main())
