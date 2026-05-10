"""Web 本地文件存储。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from pix_web.config import WebSettings

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}


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
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="上传图片超过大小限制")

    upload_dir = settings.storage_root / "uploads" / str(user_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_path = upload_dir / f"{uuid4().hex}{suffix}"
    stored_path.write_bytes(data)
    return StoredUpload(path=stored_path, filename=original_name, content_type=content_type, size_bytes=size)
