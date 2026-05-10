"""受保护的 Web 文件访问。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse

from pix_web.models import User
from pix_web.security import get_current_user
from pix_web.storage import resolve_web_file

router = APIRouter(prefix="/files", tags=["files"])


@router.get("")
def get_file(
    path: str,
    request: Request,
    _user: User = Depends(get_current_user),
) -> FileResponse:
    resolved = resolve_web_file(path, request.app.state.web_settings)
    return FileResponse(resolved)
