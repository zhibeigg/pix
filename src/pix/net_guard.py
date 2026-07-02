"""出站下载 SSRF 防护。

生图上游（如胜算云）出图后有时只返回图片 URL、Ark 视频任务返回视频 URL，
服务端需要主动下载这些资源。若不校验目标地址，被污染/被劫持的上游即可诱导服务端
访问内网、云元数据（169.254.169.254）等敏感地址。

本模块提供：

- :func:`assert_safe_download_url` —— 解析 URL 的主机名到 IP，拒绝回环 / 私网 /
  链路本地 / 保留地址，只允许 http(s)；
- :func:`safe_get_with_redirects` —— 手动跟随有限跳数的重定向，对每一跳都重新执行
  地址校验（防 302 绕过与 DNS 重绑定）。

可用环境变量 ``PIX_ALLOW_PRIVATE_DOWNLOAD=true`` 关闭校验（仅限自建可信内网上游的
特殊部署场景，默认关闭）。
"""

from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlsplit

import httpx

DEFAULT_MAX_REDIRECTS = 3


class UnsafeDownloadURLError(ValueError):
    """目标下载地址被 SSRF 防护拒绝。"""


def _allow_private_downloads() -> bool:
    return os.getenv("PIX_ALLOW_PRIVATE_DOWNLOAD", "").strip().lower() in {"1", "true", "yes", "on"}


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # IPv4-mapped IPv6（如 ::ffff:169.254.169.254）需还原成 IPv4 再判定。
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _resolved_ips(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    # 主机名可能直接是 IP 字面量。
    try:
        return [ipaddress.ip_address(host.strip("[]"))]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeDownloadURLError(f"无法解析下载地址主机：{host}") from exc
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        sockaddr = info[4]
        if sockaddr and isinstance(sockaddr[0], str):
            try:
                ips.append(ipaddress.ip_address(sockaddr[0]))
            except ValueError:
                continue
    if not ips:
        raise UnsafeDownloadURLError(f"无法解析下载地址主机：{host}")
    return ips


def assert_safe_download_url(url: str) -> None:
    """校验单个下载 URL 是否安全，非法时抛 :class:`UnsafeDownloadURLError`。"""
    if _allow_private_downloads():
        return
    parts = urlsplit(url)
    scheme = (parts.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise UnsafeDownloadURLError(f"不允许的下载协议：{scheme or '(空)'}")
    host = parts.hostname
    if not host:
        raise UnsafeDownloadURLError("下载地址缺少主机名")
    for ip in _resolved_ips(host):
        if _is_blocked_ip(ip):
            raise UnsafeDownloadURLError(f"下载地址指向受限网络：{host} -> {ip}")


def safe_get_with_redirects(
    client: httpx.Client,
    url: str,
    *,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    stream: bool = False,
):
    """手动跟随有限跳数的重定向，对每一跳都执行 :func:`assert_safe_download_url`。

    返回值与 ``client.get`` / ``client.stream`` 上下文管理器语义一致：
    ``stream=False`` 返回已读取的 ``httpx.Response``；``stream=True`` 返回一个
    响应上下文管理器（调用方需 ``with`` 使用）。
    """
    current = url
    for _ in range(max_redirects + 1):
        assert_safe_download_url(current)
        if stream:
            ctx = client.stream("GET", current)
            response = ctx.__enter__()
            if response.is_redirect and response.headers.get("location"):
                location = str(response.url.join(response.headers["location"]))
                ctx.__exit__(None, None, None)
                current = location
                continue
            return _StreamHandle(ctx, response)
        response = client.get(current, follow_redirects=False)
        if response.is_redirect and response.headers.get("location"):
            current = str(response.url.join(response.headers["location"]))
            continue
        return response
    raise UnsafeDownloadURLError(f"下载重定向次数超过上限（{max_redirects}）：{url}")


class _StreamHandle:
    """包装 stream 上下文，让调用方以 ``with safe_get_with_redirects(...) as resp`` 使用。"""

    def __init__(self, ctx, response: httpx.Response) -> None:
        self._ctx = ctx
        self._response = response

    def __enter__(self) -> httpx.Response:
        return self._response

    def __exit__(self, exc_type, exc, tb) -> None:
        self._ctx.__exit__(exc_type, exc, tb)
