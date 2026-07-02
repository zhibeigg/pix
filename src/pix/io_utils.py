"""IO helpers：图片读写、URL 下载、base64 编解码、运行目录管理。"""

from __future__ import annotations

import base64
import hashlib
import mimetypes
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from types import TracebackType

import httpx

from pix.net_guard import assert_safe_download_url, safe_get_with_redirects


class FileLockTimeout(TimeoutError):
    """等待文件锁超时。"""


class FileLock:
    """跨进程排他文件锁，用于保护本地 CPU/磁盘重处理阶段。"""

    def __init__(self, path: str | Path, *, timeout: float = 1800.0, poll_interval: float = 0.1) -> None:
        self.path = Path(path)
        self.timeout = max(0.0, float(timeout))
        self.poll_interval = max(0.01, float(poll_interval))
        self._fp = None

    def __enter__(self) -> "FileLock":
        ensure_dir(self.path.parent)
        self._fp = open(self.path, "a+b")
        self._ensure_lock_byte()
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self._try_acquire()
                return self
            except BlockingIOError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._close()
                    raise FileLockTimeout(f"等待本地处理锁超时: {self.path}")
                time.sleep(min(self.poll_interval, remaining))

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            self._release()
        finally:
            self._close()

    def _ensure_lock_byte(self) -> None:
        assert self._fp is not None
        self._fp.seek(0, os.SEEK_END)
        if self._fp.tell() == 0:
            self._fp.write(b"\0")
            self._fp.flush()
        self._fp.seek(0)

    def _try_acquire(self) -> None:
        assert self._fp is not None
        self._fp.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(self._fp.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise BlockingIOError from exc
        else:
            import fcntl

            try:
                fcntl.flock(self._fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise BlockingIOError from exc

    def _release(self) -> None:
        if self._fp is None:
            return
        self._fp.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self._fp.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(self._fp.fileno(), fcntl.LOCK_UN)

    def _close(self) -> None:
        if self._fp is not None:
            self._fp.close()
            self._fp = None


def file_lock(path: str | Path, *, timeout: float = 1800.0, poll_interval: float = 0.1) -> FileLock:
    return FileLock(path, timeout=timeout, poll_interval=poll_interval)



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


def download(
    url: str,
    dest: str | Path,
    timeout: float = 600.0,
    *,
    chunk_size: int = 64 * 1024,
    connect_timeout: float | None = None,
    trust_env: bool = False,
    proxy: str | None = None,
    max_retries: int = 3,
) -> Path:
    """下载远程图片到本地。

    仅作为 URL 响应格式的兼容兜底；Packy gpt-image-2 主路径使用 ``b64_json`` 直接写入文件。
    ``connect_timeout`` 只控制连接握手阶段，默认沿用 ``timeout``。
    ``trust_env`` 默认关闭，避免 Windows 系统代理在生图等长 idle 连接上提前断开；
    需要走代理时显式传入 ``trust_env=True`` 或 ``proxy``。

    远端图片通常由模型 API 返回的临时 URL / CDN URL 承载，偶发会出现响应体未传完就被网关关闭
    （httpx.RemoteProtocolError: received N bytes, expected M）。这里按完整文件从头重试，避免临时断流
    直接导致整条生图任务失败。``chunk_size`` 保留为兼容旧调用，当前实现不再使用流式读取。
    """
    dest_path = Path(dest)
    ensure_dir(dest_path.parent)
    # SSRF 防护：下载前先校验目标地址，非法（私网/回环/元数据等）直接抛错，不再重试。
    assert_safe_download_url(url)
    httpx_timeout = httpx.Timeout(
        connect=connect_timeout if connect_timeout is not None else timeout,
        read=timeout,
        write=timeout,
        pool=timeout,
    )
    tmp_path = dest_path.with_suffix(dest_path.suffix + ".part")
    client_kwargs: dict[str, object] = {
        "timeout": httpx_timeout,
        # 逐跳复验重定向目标（防 302 绕内网 / DNS 重绑定），不使用 httpx 自动跟随。
        "follow_redirects": False,
        "trust_env": trust_env,
    }
    if proxy:
        client_kwargs["proxy"] = proxy

    attempts = max(1, int(max_retries))
    last_exc: httpx.HTTPError | None = None
    for attempt in range(1, attempts + 1):
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        try:
            with httpx.Client(**client_kwargs) as client:
                resp = safe_get_with_redirects(client, url)
                resp.raise_for_status()
                expected_length_header = resp.headers.get("content-length")
                expected_length = int(expected_length_header) if expected_length_header and expected_length_header.isdigit() else None
                data = resp.content
                bytes_received = len(data)
                if expected_length is not None and bytes_received != expected_length:
                    raise httpx.RemoteProtocolError(
                        f"peer closed connection without sending complete message body "
                        f"(received {bytes_received} bytes, expected {expected_length})"
                    )
                write_bytes(tmp_path, data)
            tmp_path.replace(dest_path)
            return dest_path
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            status_code = exc.response.status_code
            if status_code < 500 and status_code != 429:
                raise
            if attempt >= attempts:
                raise
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt >= attempts:
                raise
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    assert last_exc is not None
    raise last_exc


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
