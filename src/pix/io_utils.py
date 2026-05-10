"""IO helpers：图片读写、URL 下载、base64 编解码、运行目录管理。"""

from __future__ import annotations

import base64
import hashlib
import mimetypes
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

import httpx


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def new_run_dir(root: str | Path, seed: str = "") -> Path:
    """创建唯一的运行目录：outputs/{YYYYMMDD-HHMMSS}-{hash8}"""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    # uuid4 保证同一进程内多次调用不碰撞；seed 让人类读起来有区分
    unique = uuid.uuid4().hex
    digest = hashlib.sha1(f"{seed}-{unique}".encode()).hexdigest()[:8]
    path = Path(root) / f"{ts}-{digest}"
    # 极端情况若目录已存在（时间戳 + hash 同时撞上），再换一次
    while path.exists():
        unique = uuid.uuid4().hex
        digest = hashlib.sha1(f"{seed}-{unique}".encode()).hexdigest()[:8]
        path = Path(root) / f"{ts}-{digest}"
    return ensure_dir(path)


def read_bytes(path: str | Path) -> bytes:
    return Path(path).read_bytes()


def write_bytes(path: str | Path, data: bytes) -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    p.write_bytes(data)
    return p


def download(url: str, dest: str | Path, timeout: float = 60.0) -> Path:
    """下载远程图片到本地。"""
    dest_path = Path(dest)
    ensure_dir(dest_path.parent)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        dest_path.write_bytes(resp.content)
    return dest_path


def guess_mime(path: str | Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "image/png"


def image_to_base64_data_url(path: str | Path) -> str:
    """返回 data:{mime};base64,xxx 形式的字符串。"""
    data = read_bytes(path)
    b64 = base64.b64encode(data).decode("ascii")
    mime = guess_mime(path)
    return f"data:{mime};base64,{b64}"


def b64_to_bytes(b64: str) -> bytes:
    return base64.b64decode(b64)


def sha256_of(data: bytes | str) -> str:
    h = hashlib.sha256()
    if isinstance(data, str):
        data = data.encode("utf-8")
    h.update(data)
    return h.hexdigest()


def sha256_of_file(path: str | Path, chunk: int = 65536) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for block in iter(lambda: fp.read(chunk), b""):
            h.update(block)
    return h.hexdigest()
