"""对外程序调用的版本化 API。"""

from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pix_web.character_library import clean_character_text, create_character_item_from_job, is_character_asset_job
from pix_web.config import WebSettings
from pix_web.credits import build_balance_response, ensure_credit_account
from pix_web.external_api_keys import ExternalApiPrincipal, require_external_scope
from pix_web.file_ownership import resolve_owned_input_path, run_job_id_for_file
from pix_web.jobs import create_job, create_jobs_batch
from pix_web.models import CharacterLibraryItem, GenerationJob
from pix_web.queue import enqueue_jobs
from pix_web.routers.settings import ImageModelsResponse, available_image_models
from pix_web.schemas import (
    CharacterCreateRequest,
    CharacterFromJobRequest,
    CharacterResponse,
    CharacterUpdateRequest,
    CreditBalanceResponse,
    ExternalMeResponse,
    JobBatchCreateRequest,
    JobBatchCreateResponse,
    JobCreateRequest,
    JobResponse,
    UploadResponse,
    public_job_response,
)
from pix_web.security import get_db, get_settings
from pix_web.storage import file_url, store_uploaded_image
from pix_web.system_settings import enforce_upload_limit, record_upload_event

router = APIRouter(prefix="/external/v1", tags=["external-v1"])


def _external_client_request_id(value: str) -> str:
    clean = " ".join((value or "").strip().split())
    if not clean:
        return ""
    if len(clean) <= 100:
        return f"external:{clean}"
    return f"external:{hashlib.sha256(clean.encode('utf-8')).hexdigest()}"


def _job_for_principal(db: Session, principal: ExternalApiPrincipal, job_id: int) -> GenerationJob:
    job = db.scalar(
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs))
        .where(GenerationJob.id == job_id, GenerationJob.user_id == principal.user.id)
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return job


def _normalize_character_path(raw_path: str, principal: ExternalApiPrincipal, db: Session, settings: WebSettings) -> Path:
    try:
        resolved = resolve_owned_input_path(raw_path, principal.user, db, settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="角色图片路径不合法") from exc
    if not resolved.is_file():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="角色图片不存在")
    return resolved


def _source_job_id_for_file(path: Path, settings: WebSettings) -> int | None:
    return run_job_id_for_file(path.resolve(), settings)


def _require_character_asset_source_job(
    db: Session,
    principal: ExternalApiPrincipal,
    source_job_id: int | None,
) -> GenerationJob:
    if source_job_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只有像素直出的角色类型作品才能成为角色")
    job = _job_for_principal(db, principal, source_job_id)
    if not is_character_asset_job(job):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只有像素直出的角色类型作品才能成为角色")
    return job


def _external_character_response(item: CharacterLibraryItem) -> CharacterResponse:
    return CharacterResponse.model_validate(item)


def _character_for_principal(db: Session, principal: ExternalApiPrincipal, character_id: int) -> CharacterLibraryItem:
    item = db.scalar(
        select(CharacterLibraryItem).where(
            CharacterLibraryItem.id == character_id,
            CharacterLibraryItem.user_id == principal.user.id,
            CharacterLibraryItem.status != "deleted",
        )
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    return item


def _read_meta(path: str | None) -> dict:
    if not path:
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_meta_path(meta_path: str | None, value: object) -> str:
    if not meta_path or not value:
        return ""
    path = Path(str(value))
    if path.is_absolute():
        return str(path)
    return str(Path(meta_path).parent / path)


def _output_path(job: GenerationJob, kind: str) -> str:
    if not job.outputs:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未产生输出")
    output = job.outputs[0]
    direct = {
        "source": output.source_path,
        "pixelized": output.pixelized_path,
        "preview": output.preview_path,
    }.get(kind)
    if direct:
        return direct
    meta = _read_meta(output.meta_json_path)
    outputs = meta.get("outputs") if isinstance(meta.get("outputs"), dict) else {}
    sprite = meta.get("sprite") if isinstance(meta.get("sprite"), dict) else {}
    by_kind = {
        "sprite-sheet": outputs.get("sprite_sheet") or sprite.get("horizontal_sheet"),
        "sprite-mosaic": outputs.get("sprite_mosaic") or sprite.get("mosaic_sheet"),
        "sprite-grid": outputs.get("sprite_sheet_grid") or sprite.get("grid_sheet"),
    }
    return _resolve_meta_path(output.meta_json_path, by_kind.get(kind))


def _download_response(path: str, filename: str = "") -> FileResponse:
    if not path or not Path(path).is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    return FileResponse(path, filename=filename or Path(path).name)


def _safe_file_part(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (value or "").strip())
    return cleaned.strip("._")[:80]


def _job_file_prefix(job: GenerationJob) -> str:
    params = job.params_json if isinstance(job.params_json, dict) else {}
    asset = params.get("asset") if isinstance(params, dict) else None
    asset_name = asset.get("name") if isinstance(asset, dict) else None
    if isinstance(asset_name, str) and asset_name.strip():
        base = _safe_file_part(asset_name)
    elif job.prompt and job.prompt.strip():
        base = _safe_file_part(job.prompt)
    else:
        base = "job"
    return f"{base or 'job'}_{job.id}"


@router.get("/me", response_model=ExternalMeResponse)
def external_me(principal: ExternalApiPrincipal = Depends(require_external_scope("me:read"))) -> ExternalMeResponse:
    return ExternalMeResponse(user=principal.user, scopes=list(principal.scopes), key_prefix=principal.api_key.key_prefix)


@router.get("/balance", response_model=CreditBalanceResponse)
def external_balance(
    principal: ExternalApiPrincipal = Depends(require_external_scope("balance:read")),
    db: Session = Depends(get_db),
) -> CreditBalanceResponse:
    account = ensure_credit_account(db, principal.user)
    return build_balance_response(db, account)


@router.get("/models", response_model=ImageModelsResponse)
def external_models(
    _principal: ExternalApiPrincipal = Depends(require_external_scope("models:read")),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> ImageModelsResponse:
    return available_image_models(db=db, web_settings=settings)


@router.get("/characters", response_model=list[CharacterResponse])
def external_list_characters(
    principal: ExternalApiPrincipal = Depends(require_external_scope("characters:read")),
    db: Session = Depends(get_db),
    limit: int = 100,
) -> list[CharacterResponse]:
    stmt = (
        select(CharacterLibraryItem)
        .where(
            CharacterLibraryItem.user_id == principal.user.id,
            CharacterLibraryItem.status.in_(["active", "archived"]),
        )
        .order_by(CharacterLibraryItem.updated_at.desc(), CharacterLibraryItem.created_at.desc())
        .limit(max(1, min(200, int(limit))))
    )
    return [_external_character_response(item) for item in db.scalars(stmt)]


@router.post("/characters", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
def external_create_character(
    req: CharacterCreateRequest,
    principal: ExternalApiPrincipal = Depends(require_external_scope("characters:write")),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> CharacterResponse:
    image_file = _normalize_character_path(req.image_path, principal, db, settings)
    preview_file = _normalize_character_path(req.preview_path, principal, db, settings) if req.preview_path else image_file
    source_job_id = _source_job_id_for_file(image_file, settings) or _source_job_id_for_file(preview_file, settings)
    _require_character_asset_source_job(db, principal, source_job_id)
    image_path = str(image_file)
    preview_path = str(preview_file)
    snapshot_source = "asset_character_job_output"
    name = clean_character_text(req.name, 160) or image_file.stem[:160] or "未命名角色"
    item = CharacterLibraryItem(
        user_id=principal.user.id,
        source_job_id=source_job_id,
        status="active",
        name=name,
        description=clean_character_text(req.description, 1000),
        tags_json=list(req.tags),
        image_path=image_path,
        preview_path=preview_path,
        parameter_snapshot_json={"source": snapshot_source, "source_job_id": source_job_id},
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _external_character_response(item)


@router.post("/characters/jobs/{job_id}", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
def external_create_character_from_job(
    job_id: int,
    req: CharacterFromJobRequest,
    principal: ExternalApiPrincipal = Depends(require_external_scope("characters:write")),
    db: Session = Depends(get_db),
) -> CharacterResponse:
    job = _job_for_principal(db, principal, job_id)
    if job.status != "succeeded" or not job.outputs:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只能把已完成任务保存为角色")
    try:
        item = create_character_item_from_job(
            db,
            job,
            job.outputs[0],
            name=req.name,
            description=req.description,
            tags=req.tags,
            image_kind=req.image_kind,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    db.refresh(item)
    return _external_character_response(item)


@router.patch("/characters/{character_id}", response_model=CharacterResponse)
def external_update_character(
    character_id: int,
    req: CharacterUpdateRequest,
    principal: ExternalApiPrincipal = Depends(require_external_scope("characters:write")),
    db: Session = Depends(get_db),
) -> CharacterResponse:
    item = _character_for_principal(db, principal, character_id)
    if req.name is not None:
        name = clean_character_text(req.name, 160)
        if not name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="角色名称不能为空")
        item.name = name
    if req.description is not None:
        item.description = clean_character_text(req.description, 1000)
    if req.tags is not None:
        item.tags_json = list(req.tags)
    if req.status is not None:
        item.status = req.status
    db.commit()
    db.refresh(item)
    return _external_character_response(item)


@router.delete("/characters/{character_id}")
def external_delete_character(
    character_id: int,
    principal: ExternalApiPrincipal = Depends(require_external_scope("characters:write")),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    item = _character_for_principal(db, principal, character_id)
    item.status = "deleted"
    db.commit()
    return {"deleted": True}


@router.post("/uploads/images", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def external_upload_image(
    request: Request,
    file: UploadFile = File(...),
    principal: ExternalApiPrincipal = Depends(require_external_scope("uploads:create")),
    db: Session = Depends(get_db),
) -> UploadResponse:
    enforce_upload_limit(db, principal.user)
    stored = await store_uploaded_image(request.app.state.web_settings, principal.user.id, file)
    record_upload_event(db, principal.user, filename=stored.filename, content_type=stored.content_type, size_bytes=stored.size_bytes)
    return UploadResponse(
        path=str(stored.path),
        url=file_url(stored.path),
        filename=stored.filename,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
    )


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def external_create_job(
    req: JobCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: ExternalApiPrincipal = Depends(require_external_scope("jobs:create")),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> dict:
    if not req.client_request_id and idempotency_key:
        req = req.model_copy(update={"client_request_id": _external_client_request_id(idempotency_key)})
    job = create_job(db, principal.user, req, settings)
    if job.status == "pending":
        enqueue_jobs(settings, [job.id])
    return public_job_response(job)


@router.post(
    "/jobs/batch", response_model=JobBatchCreateResponse, status_code=status.HTTP_202_ACCEPTED
)
def external_create_jobs_batch(
    req: JobBatchCreateRequest,
    principal: ExternalApiPrincipal = Depends(require_external_scope("jobs:create")),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> JobBatchCreateResponse:
    jobs, total_price, batch = create_jobs_batch(
        db,
        principal.user,
        req.jobs,
        batch_name=req.batch_name,
        mode=req.mode,
        settings=settings,
    )
    enqueue_jobs(settings, [job.id for job in jobs if job.status == "pending"])
    return JobBatchCreateResponse(
        jobs=[JobResponse.model_validate(public_job_response(job)) for job in jobs],
        total_price_credits=total_price,
        batch_id=batch.id if batch else None,
    )


@router.get("/jobs", response_model=list[JobResponse])
def external_list_jobs(
    principal: ExternalApiPrincipal = Depends(require_external_scope("jobs:read")),
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    before_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    stmt = (
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs))
        .where(GenerationJob.user_id == principal.user.id)
        .order_by(GenerationJob.id.desc())
        .limit(max(1, min(200, limit)))
    )
    if status_filter:
        stmt = stmt.where(GenerationJob.status == status_filter)
    if before_id is not None:
        stmt = stmt.where(GenerationJob.id < before_id)
    return [public_job_response(job) for job in db.scalars(stmt)]


@router.get("/jobs/{job_id}", response_model=JobResponse)
def external_get_job(
    job_id: int,
    principal: ExternalApiPrincipal = Depends(require_external_scope("jobs:read")),
    db: Session = Depends(get_db),
) -> dict:
    return public_job_response(_job_for_principal(db, principal, job_id))


@router.get("/jobs/{job_id}/outputs/sprite-actions.zip")
def external_download_sprite_actions(
    job_id: int,
    principal: ExternalApiPrincipal = Depends(require_external_scope("files:read")),
    db: Session = Depends(get_db),
) -> Response:
    job = _job_for_principal(db, principal, job_id)
    if not job.outputs:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未产生输出")
    output = job.outputs[0]
    meta = _read_meta(output.meta_json_path)
    sprite = meta.get("sprite") if isinstance(meta.get("sprite"), dict) else {}
    rows = sprite.get("rows_outputs") if isinstance(sprite.get("rows_outputs"), list) else []
    prefix = _job_file_prefix(job)
    buffer = BytesIO()
    added = 0
    with ZipFile(buffer, "w", ZIP_DEFLATED) as zip_file:
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            sheet = _resolve_meta_path(output.meta_json_path, row.get("sheet"))
            if not sheet or not Path(sheet).is_file():
                continue
            row_index = int(row.get("row_index")) if isinstance(row.get("row_index"), int) else index
            phase = _safe_file_part(str(row.get("action_phase") or ""))
            name = f"{prefix}_action{row_index + 1:02d}_{phase}.png" if phase else f"{prefix}_action{row_index + 1:02d}.png"
            zip_file.write(sheet, name)
            added += 1
    if added == 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="没有可打包的动作图")
    filename = f"{prefix}_sprite_actions.zip"
    ascii_name = filename.encode("ascii", "ignore").decode().strip("_") or "sprite_actions.zip"
    disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    return Response(content=buffer.getvalue(), media_type="application/zip", headers={"Content-Disposition": disposition})


@router.get("/jobs/{job_id}/outputs/{kind}")
def external_download_output(
    job_id: int,
    kind: str,
    principal: ExternalApiPrincipal = Depends(require_external_scope("files:read")),
    db: Session = Depends(get_db),
):
    allowed = {"source", "pixelized", "preview", "sprite-sheet", "sprite-mosaic", "sprite-grid"}
    if kind not in allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="输出类型不存在")
    job = _job_for_principal(db, principal, job_id)
    path = _output_path(job, kind)
    return _download_response(path, f"{_job_file_prefix(job)}_{kind}.png")
