"""用户角色库接口。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pix_web.config import WebSettings
from pix_web.file_ownership import resolve_owned_input_path, run_job_id_for_file
from pix_web.models import CharacterLibraryItem, GenerationJob, GenerationOutput, User
from pix_web.schemas import (
    CharacterCreateRequest,
    CharacterFromJobRequest,
    CharacterResponse,
    CharacterUpdateRequest,
)
from pix_web.security import get_current_user, get_db, get_settings

router = APIRouter(prefix="/characters", tags=["characters"])

_ACTIVE_STATUSES = {"active", "archived"}


def _clean_text(value: str | None, limit: int) -> str:
    return " ".join((value or "").strip().split())[:limit]


def _as_record(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _job_title(job: GenerationJob) -> str:
    params = _as_record(job.params_json)
    asset = _as_record(params.get("asset"))
    asset_name = str(asset.get("name") or "").strip()
    if asset_name:
        return asset_name[:160]
    prompt = (job.prompt or "").replace("\n", " ").strip()
    return prompt[:160] if prompt else f"角色 #{job.id}"


def _parameter_snapshot(job: GenerationJob, *, image_kind: str) -> dict[str, Any]:
    params = _as_record(job.params_json)
    return {
        "source": "job",
        "source_job_id": job.id,
        "image_kind": image_kind,
        "job_type": job.job_type,
        "prompt": job.prompt,
        "image_model": params.get("image_model"),
        "pixelize": params.get("pixelize") if isinstance(params.get("pixelize"), dict) else {},
        "asset": params.get("asset") if isinstance(params.get("asset"), dict) else {},
        "style_profile": params.get("style_profile") if isinstance(params.get("style_profile"), dict) else {},
    }


def _get_owned_character(db: Session, user: User, character_id: int) -> CharacterLibraryItem:
    item = db.scalar(
        select(CharacterLibraryItem).where(
            CharacterLibraryItem.id == character_id,
            CharacterLibraryItem.user_id == user.id,
            CharacterLibraryItem.status != "deleted",
        )
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    return item


def _normalize_owned_file(raw_path: str, user: User, db: Session, settings: WebSettings) -> Path:
    try:
        resolved = resolve_owned_input_path(raw_path, user, db, settings)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="角色图片路径不合法",
        ) from exc
    if not resolved.is_file():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="角色图片不存在")
    return resolved


def _source_job_id_for_file(path: Path, settings: WebSettings) -> int | None:
    return run_job_id_for_file(path.resolve(), settings)


def _path_if_file(value: str | None) -> str | None:
    if not value:
        return None
    path = Path(value)
    return str(path) if path.is_file() else None


def _output_path(output: GenerationOutput, image_kind: str) -> str:
    preferred = {
        "source": output.source_path,
        "pixelized": output.pixelized_path,
        "preview": output.preview_path,
    }.get(image_kind)
    for candidate in (
        preferred,
        output.source_path,
        output.pixelized_path,
        output.preview_path,
    ):
        found = _path_if_file(candidate)
        if found:
            return found
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="作品没有可保存为角色的图片")


def _preview_path(output: GenerationOutput, image_path: str) -> str:
    for candidate in (output.preview_path, output.pixelized_path, image_path, output.source_path):
        found = _path_if_file(candidate)
        if found:
            return found
    return image_path


def _character_response(item: CharacterLibraryItem) -> CharacterResponse:
    return CharacterResponse.model_validate(item)


@router.get("", response_model=list[CharacterResponse])
def list_characters(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 100,
) -> list[CharacterResponse]:
    stmt = (
        select(CharacterLibraryItem)
        .where(CharacterLibraryItem.user_id == user.id, CharacterLibraryItem.status.in_(_ACTIVE_STATUSES))
        .order_by(CharacterLibraryItem.updated_at.desc(), CharacterLibraryItem.created_at.desc())
        .limit(max(1, min(200, int(limit))))
    )
    return [_character_response(item) for item in db.scalars(stmt)]


@router.post("", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
def create_character(
    req: CharacterCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> CharacterResponse:
    image_file = _normalize_owned_file(req.image_path, user, db, settings)
    preview_file = _normalize_owned_file(req.preview_path, user, db, settings) if req.preview_path else image_file
    image_path = str(image_file)
    preview_path = str(preview_file)
    source_job_id = _source_job_id_for_file(image_file, settings) or _source_job_id_for_file(preview_file, settings)
    name = _clean_text(req.name, 160) or image_file.stem[:160] or "未命名角色"
    snapshot_source = "job_output" if source_job_id is not None else "upload"
    item = CharacterLibraryItem(
        user_id=user.id,
        source_job_id=source_job_id,
        status="active",
        name=name,
        description=_clean_text(req.description, 1000),
        tags_json=list(req.tags),
        image_path=image_path,
        preview_path=preview_path,
        parameter_snapshot_json={"source": snapshot_source, "source_job_id": source_job_id},
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _character_response(item)


@router.post("/jobs/{job_id}", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
def create_character_from_job(
    job_id: int,
    req: CharacterFromJobRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CharacterResponse:
    job = db.scalar(
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs))
        .where(GenerationJob.id == job_id, GenerationJob.user_id == user.id)
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品不存在")
    if job.status != "succeeded" or not job.outputs:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只能把已完成作品保存为角色")
    output = job.outputs[0]
    image_path = _output_path(output, req.image_kind)
    preview_path = _preview_path(output, image_path)
    item = CharacterLibraryItem(
        user_id=user.id,
        source_job_id=job.id,
        status="active",
        name=_clean_text(req.name, 160) or _job_title(job),
        description=_clean_text(req.description, 1000),
        tags_json=list(req.tags),
        image_path=image_path,
        preview_path=preview_path,
        parameter_snapshot_json=_parameter_snapshot(job, image_kind=req.image_kind),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _character_response(item)


@router.patch("/{character_id}", response_model=CharacterResponse)
def update_character(
    character_id: int,
    req: CharacterUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CharacterResponse:
    item = _get_owned_character(db, user, character_id)
    if req.name is not None:
        name = _clean_text(req.name, 160)
        if not name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="角色名称不能为空")
        item.name = name
    if req.description is not None:
        item.description = _clean_text(req.description, 1000)
    if req.tags is not None:
        item.tags_json = list(req.tags)
    if req.status is not None:
        item.status = req.status
    db.commit()
    db.refresh(item)
    return _character_response(item)


@router.delete("/{character_id}")
def delete_character(
    character_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    item = _get_owned_character(db, user, character_id)
    item.status = "deleted"
    db.commit()
    return {"deleted": True}
