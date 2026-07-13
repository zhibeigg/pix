"""Web 本地文件存储。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from pix_web.config import WebSettings

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_DOWNLOAD_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | {".json", ".txt", ".gif"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
ALLOWED_FILE_ROOTS = ("outputs",)


def file_url(path: str | Path | None) -> str | None:
    if path is None:
        return None
    raw = str(path)
    if not raw:
        return None
    return f"/files?path={quote(raw, safe='')}"


@dataclass(frozen=True)
class StoredUpload:
    path: Path
    filename: str
    content_type: str
    size_bytes: int


async def store_uploaded_image(settings: WebSettings, user_id: int, file: UploadFile) -> StoredUpload:
    """保存用户上传图片到本地存储目录。"""
    original_name = file.filename or "image"
    suffix = Path(original_name).suffix.lower()
    content_type = file.content_type or "application/octet-stream"
    if suffix not in ALLOWED_IMAGE_EXTENSIONS or content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 PNG/JPG/WebP 图片")

    data = await file.read()
    size = len(data)
    if size == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传文件为空")
    if size > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"上传图片超过大小限制（最大 {limit_mb:.0f} MB）",
        )

    upload_dir = settings.storage_root / "uploads" / str(user_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_path = upload_dir / f"{uuid4().hex}{suffix}"
    stored_path.write_bytes(data)
    return StoredUpload(path=stored_path, filename=original_name, content_type=content_type, size_bytes=size)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_storage_path(raw_path: str | Path, settings: WebSettings) -> Path:
    """解析存储路径，并把显式配置的旧根目录安全映射到当前存储根。"""
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    resolved = candidate.resolve()
    storage_root = settings.storage_root.resolve()
    if _is_relative_to(resolved, storage_root):
        return resolved

    for raw_legacy_root in settings.legacy_storage_roots:
        legacy_root = Path(raw_legacy_root).expanduser()
        if not legacy_root.is_absolute():
            legacy_root = Path.cwd() / legacy_root
        try:
            relative = resolved.relative_to(legacy_root.resolve())
        except ValueError:
            continue
        rebased = (storage_root / relative).resolve()
        if _is_relative_to(rebased, storage_root):
            return rebased

    return resolved


def resolve_web_file(raw_path: str, settings: WebSettings) -> Path:
    """解析并限制 Web 可访问文件范围。"""
    resolved = resolve_storage_path(raw_path, settings)
    allowed_roots = [settings.storage_root.resolve()]
    allowed_roots.extend((Path.cwd() / root).resolve() for root in ALLOWED_FILE_ROOTS)
    if not any(_is_relative_to(resolved, root) for root in allowed_roots):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="文件不允许访问")
    if not resolved.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    if resolved.suffix.lower() not in ALLOWED_DOWNLOAD_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅允许访问图片、JSON 或文本产物")
    return resolved
