# PyInstaller spec for pix — cross-platform one-dir build.
#
# 用法：
#   pyinstaller build_tools/pix.spec
#
# 输出：
#   dist/pix/               — Windows / Linux 目录式 bundle（含 pix.exe 或 pix）
#   dist/pix.app/           — macOS 应用 bundle（仅 macOS 平台）

from pathlib import Path
import sys

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.building.osx import BUNDLE


APP_NAME = "pix"
PROJECT_ROOT = Path(SPECPATH).resolve().parent

entry = str(PROJECT_ROOT / "build_tools" / "launcher.py")
assets_dir = str(PROJECT_ROOT / "assets")

# 所有内置预设都要打包进去
datas = [(assets_dir, "assets")]

# 让 PyInstaller 能找到动态 import 的子模块
hiddenimports = [
    "pix",
    "pix.cli",
    "pix.gui.app",
    "pix.gui.main_window",
    "pix.gui.settings_dialog",
    "pix.gui.preview_panel",
    "pix.gui.worker",
    "pix.gui.combo_keys",
    "pix.i18n",
    "pix.i18n_catalog",
    "pix.pipeline",
    "pix.api.packy_client",
    "pix.api.image_gen",
    "pix.api.vision",
    "pix.analysis.schema",
    "pix.analysis.prompts",
    "pix.pixelize.core",
    "pix.pixelize.palette",
    "pix.pixelize.presets",
    "pix.pixelize.roi",
    "pix.cache",
    "pix.config",
    "pix.settings",
    "pix.io_utils",
]

excludes = [
    "tkinter",
    "matplotlib",
    "pandas",
    "pytest",
    "IPython",
    "notebook",
]

a = Analysis(
    [entry],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,               # 无控制台窗口（双击 GUI）；CLI 子命令仍会输出到启动它的 shell
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,            # 由 runner 平台决定
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

# macOS 再额外产出 .app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=None,
        bundle_identifier="com.zhibeigg.pix",
        info_plist={
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "MIT © 纸杯 (zhibeigg)",
            "CFBundleShortVersionString": "0.1.0",
            "CFBundleVersion": "0.1.0",
        },
    )
