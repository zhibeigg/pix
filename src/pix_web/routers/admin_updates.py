"""Administrator release check and updater-agent control plane."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, status

from pix import __version__
from pix_web.config import WebSettings
from pix_web.models import User
from pix_web.release_updates import (
    ReleaseCheckResult,
    ReleaseUpdateChecker,
    TrustedRelease,
    is_newer_version,
)
from pix_web.schemas import (
    AdminUpdateApplyRequest,
    AdminUpdateRollbackRequest,
    AdminUpdateStatusResponse,
    UpdateAgentStatusResponse,
    UpdateOperationResponse,
    UpdateReleaseResponse,
    UpdaterAgentOperation,
    UpdaterAgentStatus,
)
from pix_web.security import get_settings, require_admin, require_update_step_up
from pix_web.update_agent_client import UpdateAgentClient, UpdateAgentError

router = APIRouter(prefix="/admin/updates", tags=["admin-updates"])


def _checker(request: Request) -> ReleaseUpdateChecker:
    return request.app.state.release_update_checker


def _agent_client(request: Request) -> UpdateAgentClient:
    return request.app.state.update_agent_client


def _release_response(release: TrustedRelease | None) -> UpdateReleaseResponse | None:
    if release is None:
        return None
    return UpdateReleaseResponse(
        version=release.version,
        tag=release.tag,
        commit=release.commit,
        notes=release.notes,
        manifest_sha256=release.manifest_sha256,
        alembic_head=release.alembic_head,
        rollback_supported=release.rollback_supported,
        trusted=release.trusted,
    )


def _operation_response(operation: UpdaterAgentOperation) -> UpdateOperationResponse:
    return UpdateOperationResponse.model_validate(operation.model_dump())


async def _load_agent_status(client: UpdateAgentClient) -> UpdateAgentStatusResponse:
    if not client.configured:
        return UpdateAgentStatusResponse(error="agent_not_configured")
    try:
        payload = await client.get_status()
    except UpdateAgentError as exc:
        return UpdateAgentStatusResponse(
            configured=True,
            available=False,
            state="offline",
            error=exc.code,
        )
    ready = payload.state not in {"disabled", "not_ready"}
    return UpdateAgentStatusResponse(
        configured=True,
        available=ready,
        state=payload.state,
        updater_version=payload.updater_version,
        current_version=payload.current_version,
        can_rollback=payload.can_rollback,
        active_operation_id=payload.active_operation_id,
        error=None if ready else f"agent_{payload.state}",
    )


def _update_available(result: ReleaseCheckResult) -> bool:
    if result.release is None:
        return False
    try:
        return is_newer_version(result.release.version, __version__)
    except ValueError:
        return False


def _status_response(
    settings: WebSettings,
    release_result: ReleaseCheckResult,
    agent: UpdateAgentStatusResponse,
) -> AdminUpdateStatusResponse:
    release = release_result.release
    available = _update_available(release_result)
    trusted = release is not None and release.trusted and not release_result.stale
    can_apply = bool(
        settings.update_apply_enabled and available and trusted and agent.available
    )
    # 回滚是故障恢复路径，不应在 GitHub 暂时不可用时被远程检查结果阻断。
    can_rollback = bool(
        settings.update_apply_enabled
        and agent.available
        and agent.can_rollback
    )
    if not settings.update_check_enabled:
        update_state = "check_disabled"
    elif release_result.error and release is None:
        update_state = "check_failed"
    elif release_result.stale:
        update_state = "stale"
    elif release is None:
        update_state = "up_to_date"
    elif not available:
        update_state = "up_to_date"
    elif not settings.update_apply_enabled:
        update_state = "available_read_only"
    elif not agent.available:
        update_state = "agent_unavailable"
    else:
        update_state = "available"
    error = release_result.error
    if error is None and agent.configured and not agent.available:
        error = agent.error
    return AdminUpdateStatusResponse(
        current_version=__version__,
        latest_release=_release_response(release),
        update_state=update_state,
        update_available=available,
        check_enabled=settings.update_check_enabled,
        apply_enabled=settings.update_apply_enabled,
        agent=agent,
        can_apply=can_apply,
        can_rollback=can_rollback,
        error=error,
    )


async def _combined_status(
    request: Request,
    settings: WebSettings,
    *,
    force: bool,
) -> AdminUpdateStatusResponse:
    release_task = _checker(request).check(force=force)
    agent_client = _agent_client(request)
    agent_task = _load_agent_status(agent_client)
    release_result, agent = await asyncio.gather(release_task, agent_task)
    return _status_response(settings, release_result, agent)


@router.get("/status", response_model=AdminUpdateStatusResponse)
async def update_status(
    request: Request,
    _admin: User = Depends(require_admin),
    settings: WebSettings = Depends(get_settings),
) -> AdminUpdateStatusResponse:
    return await _combined_status(request, settings, force=False)


@router.post("/check", response_model=AdminUpdateStatusResponse)
async def check_updates(
    request: Request,
    _admin: User = Depends(require_admin),
    settings: WebSettings = Depends(get_settings),
) -> AdminUpdateStatusResponse:
    return await _combined_status(request, settings, force=True)


def _raise_agent_error(exc: UpdateAgentError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.code)


async def _trusted_action_release(request: Request, settings: WebSettings) -> TrustedRelease:
    if not settings.update_apply_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="update_apply_disabled")
    result = await _checker(request).check(force=True)
    if result.release is None or result.error or result.stale or not result.release.trusted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="trusted_release_unavailable",
        )
    return result.release


async def _available_agent(client: UpdateAgentClient) -> UpdaterAgentStatus:
    if not client.configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="agent_not_configured",
        )
    try:
        payload = await client.get_status()
    except UpdateAgentError as exc:
        _raise_agent_error(exc)
        raise AssertionError("unreachable")
    if payload.state in {"disabled", "not_ready"}:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"agent_{payload.state}",
        )
    return payload


@router.post(
    "/apply",
    response_model=AdminUpdateStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def apply_update(
    req: AdminUpdateApplyRequest,
    request: Request,
    _admin: User = Depends(require_update_step_up),
    settings: WebSettings = Depends(get_settings),
) -> AdminUpdateStatusResponse:
    release = await _trusted_action_release(request, settings)
    if req.target_version != release.version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="target_release_changed")
    if req.expected_manifest_sha256.lower() != release.manifest_sha256:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="manifest_changed")
    if not is_newer_version(release.version, __version__):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="update_not_available")
    client = _agent_client(request)
    agent_status = await _available_agent(client)
    try:
        operation = await client.apply(
            target_version=req.target_version,
            expected_manifest_sha256=req.expected_manifest_sha256.lower(),
            idempotency_key=req.idempotency_key,
        )
    except UpdateAgentError as exc:
        _raise_agent_error(exc)
        raise AssertionError("unreachable")
    agent = UpdateAgentStatusResponse(
        configured=True,
        available=True,
        state=agent_status.state,
        updater_version=agent_status.updater_version,
        current_version=agent_status.current_version,
        can_rollback=agent_status.can_rollback,
        active_operation_id=operation.operation_id,
    )
    response = _status_response(
        settings,
        ReleaseCheckResult(release=release),
        agent,
    )
    response.operation = _operation_response(operation)
    response.update_state = operation.state
    response.can_apply = False
    return response


@router.get("/operations/{operation_id}", response_model=UpdateOperationResponse)
async def get_update_operation(
    operation_id: str,
    request: Request,
    _admin: User = Depends(require_admin),
) -> UpdateOperationResponse:
    try:
        operation = await _agent_client(request).get_operation(operation_id)
    except UpdateAgentError as exc:
        _raise_agent_error(exc)
        raise AssertionError("unreachable")
    return _operation_response(operation)


@router.post(
    "/rollback",
    response_model=AdminUpdateStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def rollback_update(
    req: AdminUpdateRollbackRequest,
    request: Request,
    _admin: User = Depends(require_update_step_up),
    settings: WebSettings = Depends(get_settings),
) -> AdminUpdateStatusResponse:
    if not settings.update_apply_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="update_apply_disabled")
    client = _agent_client(request)
    agent_status = await _available_agent(client)
    if not agent_status.can_rollback:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="rollback_not_available")
    try:
        operation = await client.rollback(idempotency_key=req.idempotency_key)
    except UpdateAgentError as exc:
        _raise_agent_error(exc)
        raise AssertionError("unreachable")
    agent = UpdateAgentStatusResponse(
        configured=True,
        available=True,
        state=agent_status.state,
        updater_version=agent_status.updater_version,
        current_version=agent_status.current_version,
        can_rollback=agent_status.can_rollback,
        active_operation_id=operation.operation_id,
    )
    release_result = await _checker(request).check(force=False)
    response = _status_response(settings, release_result, agent)
    response.operation = _operation_response(operation)
    response.update_state = operation.state
    response.can_apply = False
    response.can_rollback = False
    return response
