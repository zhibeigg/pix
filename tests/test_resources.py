"""内置资源路径测试。"""

from __future__ import annotations

from pix.resources import app_icon_path, macos_icon_path, resource_path, windows_icon_path


def test_icon_resources_exist() -> None:
    assert app_icon_path().exists()
    assert app_icon_path().suffix == ".png"
    assert windows_icon_path().exists()
    assert windows_icon_path().suffix == ".ico"
    assert macos_icon_path().exists()
    assert macos_icon_path().suffix == ".icns"


def test_resource_path_falls_back_to_package_assets() -> None:
    assert resource_path("icons", "pix_logo_64.png") == app_icon_path()
