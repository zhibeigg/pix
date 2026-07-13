from __future__ import annotations

import secrets
from contextlib import asynccontextmanager

import anyio
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status

from pix_updater.config import UpdaterSettings
from pix_updater.models import AgentOperationResponse, AgentStatusResponse, ApplyRequest, RollbackRequest
from pix_updater.service import BusyError, NotReadyError, UpdateService


async def _read_token(settings: UpdaterSettings) -> str:
    try:
        async with await anyio.open_file(settings.token_file, "r", encoding="utf-8") as opened:
            token = await opened.read()
    except (OSError, UnicodeError):
        return ""
    return token.strip()


def create_app(settings: UpdaterSettings | None = None, service: UpdateService | None = None) -> FastAPI:
    active_settings = settings or UpdaterSettings()
    active_service = service or UpdateService(active_settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await active_service.initialize()
        yield

    app = FastAPI(
        title="Pix Update Agent",
        version="1",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = active_settings
    app.state.update_service = active_service

    async def authenticate(authorization: str | None = Header(default=None)) -> None:
        expected = await _read_token(active_settings)
        supplied = ""
        if authorization and authorization.startswith("Bearer "):
            supplied = authorization[7:]
        if len(expected) < 32 or not secrets.compare_digest(supplied.encode(), expected.encode()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    auth = Depends(authenticate)

    @app.get("/v1/status", response_model=AgentStatusResponse, dependencies=[auth])
    async def get_status(request: Request) -> AgentStatusResponse:
        return AgentStatusResponse.model_validate(await request.app.state.update_service.status())

    @app.post(
        "/v1/apply",
        response_model=AgentOperationResponse,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[auth],
    )
    async def apply_release(payload: ApplyRequest, request: Request) -> AgentOperationResponse:
        try:
            operation = await request.app.state.update_service.request_apply(payload)
        except NotReadyError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
        except BusyError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        return AgentOperationResponse.from_operation(operation)

    @app.get(
        "/v1/operations/{operation_id}",
        response_model=AgentOperationResponse,
        dependencies=[auth],
    )
    async def get_operation(operation_id: str, request: Request) -> AgentOperationResponse:
        if len(operation_id) != 32 or any(char not in "0123456789abcdef" for char in operation_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="operation not found")
        operation = request.app.state.update_service.get_operation(operation_id)
        if operation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="operation not found")
        return AgentOperationResponse.from_operation(operation)

    @app.post(
        "/v1/rollback",
        response_model=AgentOperationResponse,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[auth],
    )
    async def rollback(payload: RollbackRequest, request: Request) -> AgentOperationResponse:
        try:
            operation = await request.app.state.update_service.request_rollback(payload)
        except NotReadyError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
        except BusyError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        return AgentOperationResponse.from_operation(operation)

    return app


app = create_app()
