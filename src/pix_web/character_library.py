"""角色库共享服务。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.models import CharacterLibraryItem, GenerationJob, GenerationOutput


def clean_character_text(value: str | None, limit: int) -> str:
    """压缩空白并截断角色库文本字段。"""
    return " ".join((value or "").strip().split())[:limit]


def _as_record(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def character_job_title(job: GenerationJob) -> str:
    """从任务参数中推导适合作为角色名称的标题。"""
    params = _as_record(job.params_json)
    asset = _as_record(params.get("asset"))
    asset_name = str(asset.get("name") or "").strip()
    if asset_name:
        return asset_name[:160]
    prompt = (job.prompt or "").replace("\n", " ").strip()
    return prompt[:160] if prompt else f"角色 #{job.id}"


def character_parameter_snapshot(
    job: GenerationJob,
    *,
    image_kind: str,
    source: str = "job",
    auto_saved: bool = False,
) -> dict[str, Any]:
    """生成角色记录使用的安全参数快照。"""
    params = _as_record(job.params_json)
    snapshot = {
        "source": source,
        "source_job_id": job.id,
        "image_kind": image_kind,
        "job_type": job.job_type,
        "prompt": job.prompt,
        "image_model": params.get("image_model"),
        "pixelize": params.get("pixelize") if isinstance(params.get("pixelize"), dict) else {},
        "asset": params.get("asset") if isinstance(params.get("asset"), dict) else {},
        "style_profile": params.get("style_profile") if isinstance(params.get("style_profile"), dict) else {},
    }
    if auto_saved:
        snapshot["auto_saved"] = True
    return snapshot


def _path_if_file(value: str | None) -> str | None:
    if not value:
        return None
    path = Path(value)
    return str(path) if path.is_file() else None


def character_output_path(output: GenerationOutput, image_kind: str) -> str:
    """按优先级选择可保存为角色的图片路径。"""
    preferred = {
        "source": output.source_path,
        "pixelized": output.pixelized_path,
        "preview": output.preview_path,
    }.get(image_kind)
    for candidate in (preferred, output.pixelized_path, output.preview_path, output.source_path):
        found = _path_if_file(candidate)
        if found:
            return found
    raise ValueError("作品没有可保存为角色的图片")


def character_preview_path(output: GenerationOutput, image_path: str) -> str:
    """选择角色库卡片预览路径。"""
    for candidate in (output.preview_path, output.pixelized_path, image_path, output.source_path):
        found = _path_if_file(candidate)
        if found:
            return found
    return image_path


def create_character_item_from_job(
    db: Session,
    job: GenerationJob,
    output: GenerationOutput,
    *,
    name: str = "",
    description: str = "",
    tags: list[str] | tuple[str, ...] | None = None,
    image_kind: str = "pixelized",
    source: str = "job",
    auto_saved: bool = False,
) -> CharacterLibraryItem:
    """从已完成任务输出创建角色库记录；调用方负责 commit。"""
    image_path = character_output_path(output, image_kind)
    preview_path = character_preview_path(output, image_path)
    item = CharacterLibraryItem(
        user_id=job.user_id,
        source_job_id=job.id,
        status="active",
        name=clean_character_text(name, 160) or character_job_title(job),
        description=clean_character_text(description, 1000),
        tags_json=list(tags or []),
        image_path=image_path,
        preview_path=preview_path,
        parameter_snapshot_json=character_parameter_snapshot(
            job,
            image_kind=image_kind,
            source=source,
            auto_saved=auto_saved,
        ),
    )
    db.add(item)
    return item


def _is_character_asset_job(job: GenerationJob) -> bool:
    params = _as_record(job.params_json)
    asset = _as_record(params.get("asset"))
    return job.job_type == "asset" and str(asset.get("asset_kind") or "") == "character"


def auto_save_character_for_job(
    db: Session,
    job: GenerationJob,
    output: GenerationOutput,
) -> CharacterLibraryItem | None:
    """角色素材任务成功后自动进入角色库；同一源任务只创建一次。"""
    if not _is_character_asset_job(job):
        return None
    existing = db.scalar(
        select(CharacterLibraryItem).where(
            CharacterLibraryItem.user_id == job.user_id,
            CharacterLibraryItem.source_job_id == job.id,
            CharacterLibraryItem.status != "deleted",
        )
    )
    if existing is not None:
        return existing
    return create_character_item_from_job(
        db,
        job,
        output,
        image_kind="pixelized",
        source="auto_asset_character",
        auto_saved=True,
    )
