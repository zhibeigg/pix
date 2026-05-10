"""用户上传接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile

from pix_web.models import User
from pix_web.schemas import UploadResponse
from pix_web.security import get_current_user
from pix_web.storage import file_url, store_uploaded_image

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/image", response_model=UploadResponse)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
) -> UploadResponse:
    stored = await store_uploaded_image(request.app.state.web_settings, user.id, file)
    return UploadResponse(
        path=str(stored.path),
        url=file_url(stored.path),
        filename=stored.filename,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
    )
