"""io_utils 测试。"""

from __future__ import annotations

from pathlib import Path

from pix.io_utils import (
    b64_to_bytes,
    ensure_dir,
    image_to_base64_data_url,
    new_run_dir,
    sha256_of,
    sha256_of_file,
    write_bytes,
)


def test_ensure_dir(tmp_path: Path) -> None:
    p = tmp_path / "a/b/c"
    assert ensure_dir(p).exists()


def test_new_run_dir_unique(tmp_path: Path) -> None:
    a = new_run_dir(tmp_path, seed="abc")
    b = new_run_dir(tmp_path, seed="abc")
    assert a != b
    assert a.exists() and b.exists()
    assert a.parent == tmp_path


def test_write_bytes_creates_parents(tmp_path: Path) -> None:
    target = tmp_path / "x/y/z.bin"
    write_bytes(target, b"hello")
    assert target.read_bytes() == b"hello"


def test_sha256_stable() -> None:
    a = sha256_of(b"abc")
    b = sha256_of("abc")
    assert a == b
    assert a != sha256_of("abcd")


def test_sha256_file(tmp_path: Path) -> None:
    p = tmp_path / "t.bin"
    p.write_bytes(b"hello world")
    assert sha256_of_file(p) == sha256_of(b"hello world")


def test_image_to_base64_data_url(sample_image: Path) -> None:
    url = image_to_base64_data_url(sample_image)
    assert url.startswith("data:image/png;base64,")
    head = url.split(",", 1)[1]
    data = b64_to_bytes(head)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
