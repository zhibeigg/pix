"""火山方舟视频生成客户端。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from pix.api.http_client import ProviderError, ProviderHttpClient, category_for_status
from pix.config import AppConfig
from pix.net_guard import UnsafeDownloadURLError, safe_get_with_redirects


@dataclass(frozen=True)
class ArkVideoTaskCreateResult:
    id: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class ArkVideoTaskStatus:
    id: str
    status: str
    content: dict[str, Any]
    error: dict[str, Any] | None
    usage: dict[str, Any]
    resolution: str | None
    ratio: str | None
    duration: int | None
    frames: int | None
    framespersecond: int | None
    generate_audio: bool | None
    raw: dict[str, Any]

    @property
    def video_url(self) -> str | None:
        value = self.content.get("video_url") if isinstance(self.content, dict) else None
        return str(value) if value else None


class ArkVideoError(ProviderError):
    """Ark 视频生成异常。"""


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class ArkVideoClient:
    """火山方舟内容生成任务 API 的轻量同步客户端。"""

    def __init__(self, cfg: AppConfig):
        video_cfg = cfg.video_bridge
        api_key = (video_cfg.api_key or "").strip()
        if not api_key:
            raise ArkVideoError("未配置 Ark API Key，请设置 ARK_API_KEY 或 pix.video_bridge.api_key", category="auth")
        self._http = ProviderHttpClient(
            provider_id="ark_video",
            base_url=video_cfg.base_url,
            api_key=api_key,
            timeout=cfg.api.timeout,
            max_retries=cfg.api.max_retries,
            trust_env=cfg.api.trust_env_proxies,
            proxy=cfg.api.proxy,
            error_type=ArkVideoError,
        )

    def create_task(
        self,
        *,
        prompt: str,
        first_frame_data_url: str,
        last_frame_data_url: str | None = None,
        model: str,
        resolution: str,
        ratio: str,
        duration: int,
        generate_audio: bool = False,
        watermark: bool = False,
    ) -> ArkVideoTaskCreateResult:
        content: list[dict[str, Any]] = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {"url": first_frame_data_url},
                "role": "first_frame",
            },
        ]
        if last_frame_data_url:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": last_frame_data_url},
                    "role": "last_frame",
                }
            )
        payload: dict[str, Any] = {
            "model": model,
            "content": content,
            "resolution": resolution,
            "ratio": ratio,
            "duration": max(1, int(duration)),
            "generate_audio": bool(generate_audio),
            "watermark": bool(watermark),
        }
        raw = self._http.post_json("/contents/generations/tasks", payload)
        task_id = str(raw.get("id") or raw.get("task_id") or "").strip()
        if not task_id:
            raise ArkVideoError(f"Ark 创建视频任务响应缺少 id：{raw}", category="malformed_response")
        return ArkVideoTaskCreateResult(id=task_id, raw=raw)

    def get_task(self, task_id: str) -> ArkVideoTaskStatus:
        raw = self._http.get_json(f"/contents/generations/tasks/{task_id}")
        status = str(raw.get("status") or "").strip()
        if not status:
            raise ArkVideoError(f"Ark 查询视频任务响应缺少 status：{raw}", category="malformed_response")
        content = _as_dict(raw.get("content"))
        error = raw.get("error") if isinstance(raw.get("error"), dict) else None
        return ArkVideoTaskStatus(
            id=str(raw.get("id") or task_id),
            status=status,
            content=content,
            error=error,
            usage=_as_dict(raw.get("usage")),
            resolution=str(raw.get("resolution")) if raw.get("resolution") is not None else None,
            ratio=str(raw.get("ratio")) if raw.get("ratio") is not None else None,
            duration=_as_optional_int(raw.get("duration")),
            frames=_as_optional_int(raw.get("frames")),
            framespersecond=_as_optional_int(raw.get("framespersecond")),
            generate_audio=bool(raw.get("generate_audio")) if raw.get("generate_audio") is not None else None,
            raw=raw,
        )

    def download_video(self, video_url: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        timeout_config = httpx.Timeout(connect=60.0, read=600.0, write=120.0, pool=600.0)
        try:
            # SSRF 防护：逐跳复验重定向目标，禁止指向内网/元数据地址。
            with httpx.Client(timeout=timeout_config, follow_redirects=False) as client:
                with safe_get_with_redirects(client, video_url, stream=True) as response:
                    if response.status_code >= 400:
                        body = response.read().decode("utf-8", errors="ignore")
                        raise ArkVideoError(
                            f"下载 Ark 视频失败 HTTP {response.status_code}: {body[:500]}",
                            category=category_for_status(response.status_code, body),
                            status_code=response.status_code,
                            body=body[:2000],
                            provider_id="ark_video",
                        )
                    with dest.open("wb") as fh:
                        for chunk in response.iter_bytes():
                            if chunk:
                                fh.write(chunk)
        except UnsafeDownloadURLError as exc:
            retryable = bool(getattr(exc, "retryable", False))
            raise ArkVideoError(
                str(exc),
                category="network" if retryable else "client_error",
                provider_id="ark_video",
                retryable=retryable,
            ) from exc
        except httpx.TimeoutException as exc:
            raise ArkVideoError(str(exc), category="timeout", provider_id="ark_video") from exc
        except httpx.HTTPError as exc:
            raise ArkVideoError(str(exc), category="network", provider_id="ark_video") from exc
        return dest
