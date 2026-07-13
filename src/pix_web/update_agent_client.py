"""Async client for the internal Pix updater agent."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urlsplit

import anyio
import httpx
from pydantic import BaseModel, ValidationError

from pix_web.config import WebSettings
from pix_web.schemas import UpdaterAgentOperation, UpdaterAgentStatus

_ResponseModel = TypeVar("_ResponseModel", bound=BaseModel)
_OPERATION_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SAFE_AGENT_STATUS_CODES = frozenset({400, 409, 412, 422, 429, 503})


class UpdateAgentError(RuntimeError):
    def __init__(self, code: str, *, status_code: int = 503) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class UpdateAgentClient:
    def __init__(self, settings: WebSettings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        if not self.settings.update_agent_url or self.settings.update_agent_token_file is None:
            return False
        try:
            parsed = urlsplit(self.settings.update_agent_url)
        except ValueError:
            return False
        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
        )

    async def _read_token(self) -> str:
        token_file = self.settings.update_agent_token_file
        if token_file is None:
            raise UpdateAgentError("agent_not_configured")
        try:
            async with await anyio.open_file(Path(token_file), "r", encoding="utf-8") as opened:
                token = (await opened.read()).strip()
        except (OSError, UnicodeError):
            raise UpdateAgentError("agent_token_unavailable")
        if not token or len(token) > 8192 or any(char.isspace() for char in token):
            raise UpdateAgentError("agent_token_invalid")
        return token

    async def _request(
        self,
        method: str,
        path: str,
        model: type[_ResponseModel],
        *,
        json: dict[str, Any] | None = None,
    ) -> _ResponseModel:
        if not self.configured:
            raise UpdateAgentError("agent_not_configured")
        token = await self._read_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        timeout = httpx.Timeout(min(5.0, max(0.5, self.settings.update_timeout_seconds)))
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.update_agent_url,
                timeout=timeout,
                follow_redirects=False,
            ) as client:
                response = await client.request(method, path, headers=headers, json=json)
        except (httpx.TimeoutException, httpx.NetworkError):
            raise UpdateAgentError("agent_offline")
        if response.status_code >= 400:
            safe_status = (
                response.status_code if response.status_code in _SAFE_AGENT_STATUS_CODES else 503
            )
            code = "agent_conflict" if response.status_code == 409 else "agent_request_failed"
            raise UpdateAgentError(code, status_code=safe_status)
        try:
            return model.model_validate(response.json())
        except (ValueError, ValidationError, TypeError):
            raise UpdateAgentError("agent_invalid_response")

    async def get_status(self) -> UpdaterAgentStatus:
        return await self._request("GET", "/v1/status", UpdaterAgentStatus)

    async def apply(
        self,
        *,
        target_version: str,
        expected_manifest_sha256: str,
        idempotency_key: str,
    ) -> UpdaterAgentOperation:
        return await self._request(
            "POST",
            "/v1/apply",
            UpdaterAgentOperation,
            json={
                "target_version": target_version,
                "expected_manifest_sha256": expected_manifest_sha256,
                "idempotency_key": idempotency_key,
            },
        )

    async def get_operation(self, operation_id: str) -> UpdaterAgentOperation:
        if _OPERATION_ID_RE.fullmatch(operation_id) is None:
            raise UpdateAgentError("invalid_operation_id", status_code=422)
        return await self._request(
            "GET", f"/v1/operations/{operation_id}", UpdaterAgentOperation
        )

    async def rollback(self, *, idempotency_key: str) -> UpdaterAgentOperation:
        return await self._request(
            "POST",
            "/v1/rollback",
            UpdaterAgentOperation,
            json={"idempotency_key": idempotency_key},
        )
