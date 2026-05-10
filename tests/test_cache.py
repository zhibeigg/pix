"""Cache 行为测试。"""

from __future__ import annotations

from pathlib import Path

from pix.cache import Cache


def test_cache_disabled_is_noop(tmp_path: Path) -> None:
    c = Cache(tmp_path / "c", enabled=False)
    assert c.lookup("imagegen", {"a": 1}, "png") is None
    assert c.store("imagegen", {"a": 1}, "png", b"data") is None


def test_cache_store_and_lookup(tmp_path: Path) -> None:
    c = Cache(tmp_path / "c", enabled=True)
    material = {"prompt": "hi", "size": "1024x1024"}
    stored = c.store("imagegen", material, "png", b"\x89PNG")
    assert stored is not None and stored.exists()
    hit = c.lookup("imagegen", material, "png")
    assert hit == stored


def test_cache_key_differs_by_material(tmp_path: Path) -> None:
    c = Cache(tmp_path / "c", enabled=True)
    a = c.store("imagegen", {"p": "a"}, "png", b"data-a")
    b = c.store("imagegen", {"p": "b"}, "png", b"data-b")
    assert a != b


def test_cache_key_stable(tmp_path: Path) -> None:
    c = Cache(tmp_path / "c", enabled=True)
    a = c.store("imagegen", {"x": 1, "y": 2}, "png", b"d")
    b_hit = c.lookup("imagegen", {"y": 2, "x": 1}, "png")  # 顺序不同
    assert b_hit == a


def test_cache_store_text(tmp_path: Path) -> None:
    c = Cache(tmp_path / "c", enabled=True)
    stored = c.store("vl", {"m": "x"}, "json", "{\"a\": 1}")
    assert stored is not None
    assert stored.read_text(encoding="utf-8") == "{\"a\": 1}"


def test_cache_store_copy(tmp_path: Path) -> None:
    src = tmp_path / "src.png"
    src.write_bytes(b"x")
    c = Cache(tmp_path / "c", enabled=True)
    stored = c.store_copy("imagegen", {"p": "q"}, "png", src)
    assert stored is not None and stored.read_bytes() == b"x"


def test_cache_clear(tmp_path: Path) -> None:
    c = Cache(tmp_path / "c", enabled=True)
    c.store("imagegen", {"p": "x"}, "png", b"y")
    c.clear()
    assert c.lookup("imagegen", {"p": "x"}, "png") is None
