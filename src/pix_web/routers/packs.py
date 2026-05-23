"""用户手动素材包接口。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from pix_web.credits import InsufficientCreditsError, insufficient_credits_http, spend_credits
from pix_web.models import AssetPack, AssetPackItem, GenerationJob, GenerationOutput, User
from pix_web.schemas import AssetPackAddItemRequest, AssetPackCreateRequest, AssetPackResponse, AssetPackUpdateRequest, JobResponse
from pix_web.security import get_current_user, get_db

router = APIRouter(prefix="/packs", tags=["packs"])

DEFAULT_ASSET_PACK_CAPACITY = 10
ASSET_PACK_EXPAND_PRICE_CREDITS = 99


def _safe_zip_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value.strip())
    return cleaned.strip("-")[:80] or "asset-pack"


def _add_output_file(zip_file: ZipFile, path_value: str | None, archive_name: str) -> bool:
    if not path_value:
        return False
    path = Path(path_value)
    if not path.is_file():
        return False
    zip_file.write(path, archive_name)
    return True


def _pack_response(pack: AssetPack) -> AssetPackResponse:
    items = list(pack.items)
    item_count = len(items)
    return AssetPackResponse(
        id=pack.id,
        name=pack.name,
        status=pack.status,
        capacity=pack.capacity,
        item_count=item_count,
        remaining_capacity=max(0, pack.capacity - item_count),
        created_at=pack.created_at,
        updated_at=pack.updated_at,
    )


def _get_owned_pack(db: Session, user: User, pack_id: int, *, with_items: bool = False) -> AssetPack:
    stmt = select(AssetPack).where(AssetPack.id == pack_id, AssetPack.user_id == user.id)
    if with_items:
        stmt = stmt.options(selectinload(AssetPack.items).selectinload(AssetPackItem.job).selectinload(GenerationJob.outputs))
    pack = db.scalar(stmt)
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材包不存在")
    return pack


def _ensure_active(pack: AssetPack) -> None:
    if pack.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="素材包已归档，恢复后才能继续操作")


def _next_position(db: Session, pack_id: int) -> int:
    current = db.scalar(select(func.max(AssetPackItem.position)).where(AssetPackItem.pack_id == pack_id))
    return int(current or 0) + 1


def _build_pack_zip(pack: AssetPack) -> bytes:
    buffer = BytesIO()
    added = 0
    root = f"pack-{pack.id}-{_safe_zip_name(pack.name)}"
    items = sorted(pack.items, key=lambda item: (item.position, item.created_at, item.id))
    with ZipFile(buffer, "w", ZIP_DEFLATED) as zip_file:
        for item in items:
            job = item.job
            if job.status != "succeeded" or not job.outputs:
                continue
            output: GenerationOutput = job.outputs[0]
            item_dir = f"{root}/job-{job.id}"
            added += int(_add_output_file(zip_file, output.source_path, f"{item_dir}/01_source.png"))
            added += int(_add_output_file(zip_file, output.analysis_json_path, f"{item_dir}/02_analysis.json"))
            added += int(_add_output_file(zip_file, output.pixelized_path, f"{item_dir}/03_pixelized.png"))
            added += int(_add_output_file(zip_file, output.preview_path, f"{item_dir}/04_preview.png"))
            added += int(_add_output_file(zip_file, output.meta_json_path, f"{item_dir}/meta.json"))
    if added == 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="没有可下载的成功作品")
    return buffer.getvalue()


@router.get("", response_model=list[AssetPackResponse])
def list_packs(user: User = Depends(get_current_user), db: Session = Depends(get_db), limit: int = 100) -> list[AssetPackResponse]:
    stmt = (
        select(AssetPack)
        .options(selectinload(AssetPack.items))
        .where(AssetPack.user_id == user.id)
        .order_by(AssetPack.created_at.desc())
        .limit(max(1, min(200, limit)))
    )
    return [_pack_response(pack) for pack in db.scalars(stmt)]


@router.post("", response_model=AssetPackResponse)
def create_pack(req: AssetPackCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AssetPackResponse:
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="素材包名称不能为空")
    pack = AssetPack(user_id=user.id, name=name, capacity=DEFAULT_ASSET_PACK_CAPACITY)
    db.add(pack)
    db.commit()
    db.refresh(pack)
    return _pack_response(pack)


@router.patch("/{pack_id}", response_model=AssetPackResponse)
def update_pack(pack_id: int, req: AssetPackUpdateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AssetPackResponse:
    pack = _get_owned_pack(db, user, pack_id, with_items=True)
    if req.name is not None:
        name = req.name.strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="素材包名称不能为空")
        pack.name = name
    if req.status is not None:
        if req.status not in {"active", "archived"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="素材包状态无效")
        pack.status = req.status
    db.commit()
    db.refresh(pack)
    return _pack_response(pack)


@router.delete("/{pack_id}")
def delete_pack(pack_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, bool]:
    pack = _get_owned_pack(db, user, pack_id, with_items=True)
    if pack.items:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只能删除空素材包")
    db.delete(pack)
    db.commit()
    return {"deleted": True}


@router.get("/{pack_id}/jobs", response_model=list[JobResponse])
def list_pack_jobs(pack_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[GenerationJob]:
    _get_owned_pack(db, user, pack_id)
    stmt = (
        select(GenerationJob)
        .join(AssetPackItem, AssetPackItem.job_id == GenerationJob.id)
        .options(selectinload(GenerationJob.outputs), selectinload(GenerationJob.batch))
        .where(AssetPackItem.pack_id == pack_id, AssetPackItem.user_id == user.id)
        .order_by(AssetPackItem.position.asc(), AssetPackItem.created_at.asc())
    )
    return list(db.scalars(stmt).unique())


@router.post("/{pack_id}/items", response_model=AssetPackResponse)
def add_pack_item(pack_id: int, req: AssetPackAddItemRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AssetPackResponse:
    pack = _get_owned_pack(db, user, pack_id, with_items=True)
    _ensure_active(pack)
    job = db.scalar(
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs))
        .where(GenerationJob.id == req.job_id, GenerationJob.user_id == user.id)
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品不存在")
    if job.status != "succeeded" or not job.outputs:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只能保存已完成作品")
    existing = db.scalar(select(AssetPackItem).where(AssetPackItem.pack_id == pack.id, AssetPackItem.job_id == job.id))
    if existing is not None:
        return _pack_response(pack)
    if len(pack.items) >= pack.capacity:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="素材包容量已满，请先扩容")
    item = AssetPackItem(user_id=user.id, pack_id=pack.id, job_id=job.id, position=_next_position(db, pack.id))
    db.add(item)
    db.commit()
    db.refresh(pack)
    pack = _get_owned_pack(db, user, pack_id, with_items=True)
    return _pack_response(pack)


@router.delete("/{pack_id}/items/{job_id}", response_model=AssetPackResponse)
def remove_pack_item(pack_id: int, job_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AssetPackResponse:
    pack = _get_owned_pack(db, user, pack_id, with_items=True)
    _ensure_active(pack)
    item = db.scalar(select(AssetPackItem).where(AssetPackItem.pack_id == pack.id, AssetPackItem.job_id == job_id, AssetPackItem.user_id == user.id))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材包内没有该作品")
    db.delete(item)
    db.commit()
    pack = _get_owned_pack(db, user, pack_id, with_items=True)
    return _pack_response(pack)


@router.post("/{pack_id}/expand", response_model=AssetPackResponse)
def expand_pack(pack_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AssetPackResponse:
    pack = _get_owned_pack(db, user, pack_id, with_items=True)
    _ensure_active(pack)
    try:
        spend_credits(db, user, ASSET_PACK_EXPAND_PRICE_CREDITS, note=f"素材包 #{pack.id} 扩容 +1")
    except InsufficientCreditsError as exc:
        raise insufficient_credits_http() from exc
    pack.capacity += 1
    db.commit()
    db.refresh(pack)
    return _pack_response(pack)


@router.get("/{pack_id}/download")
def download_pack(pack_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    pack = _get_owned_pack(db, user, pack_id, with_items=True)
    data = _build_pack_zip(pack)
    filename = f"pix-pack-{pack.id}.zip"
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
