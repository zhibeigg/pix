# PyInstaller spec for pix — Windows-friendly single-file build.
#
# 用法：
#   pyinstaller build_tools/pix_onefile.spec
#
# 输出：
#   dist/pix.exe             — 可单独移动运行的 Windows GUI/CLI 程序

from pathlib import Path

from PyInstaller.building.api import EXE, PYZ
from PyInstaller.building.build_main import Analysis


APP_NAME = "pix"
PROJECT_ROOT = Path(SPECPATH).resolve().parent

entry = str(PROJECT_ROOT / "build_tools" / "launcher.py")
assets_dir = str(PROJECT_ROOT / "assets")
pix_assets_dir = str(PROJECT_ROOT / "src" / "pix" / "assets")
icon_ico = PROJECT_ROOT / "src" / "pix" / "assets" / "icons" / "pix_logo.ico"

# one-file 模式会把 datas 打进 exe，运行时解压到 sys._MEIPASS。
datas = [(assets_dir, "assets"), (pix_assets_dir, "pix/assets")]

hiddenimports = [
    "pix",
    "pix.cli",
    "pix.gui.app",
    "pix.gui.main_window",
    "pix.gui.settings_dialog",
    "pix.gui.history_dialog",
    "pix.gui.preview_panel",
    "pix.gui.worker",
    "pix.gui.combo_keys",
    "pix.i18n",
    "pix.i18n_catalog",
    "pix.resources",
    "pix.history",
    "pix.pipeline",
    "pix.asset",
    "pix.grid.schema",
    "pix.grid.extract",
    "pix.grid.render",
    "pix.grid.postprocess",
    "pix.grid.review",
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(icon_ico) if icon_ico.exists() else None,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
