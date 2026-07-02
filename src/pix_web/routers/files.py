"""受保护的 Web 文件访问。"""

from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from pix_web.models import User
from pix_web.security import create_file_ticket, decode_file_ticket, get_current_user, get_db, get_settings
from sqlalchemy.orm import Session

from pix_web.config import WebSettings
from pix_web.file_ownership import user_owns_file
from pix_web.schemas import FileTicketResponse
from pix_web.storage import resolve_web_file

router = APIRouter(prefix="/files", tags=["files"])


def _file_user(
    request: Request,
    token: str | None = None,
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> User:
    bearer = request.headers.get("authorization", "")
    raw_token = token or (bearer.removeprefix("Bearer ").strip() if bearer.lower().startswith("bearer ") else "")
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证已失效，请重新登录")
    # 优先按短时效文件票据校验（scope=file）；失败再回退旧的完整登录 token（过渡兼容）。
    user_id = decode_file_ticket(raw_token, settings)
    if user_id is None:
        try:
            payload = jwt.decode(raw_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            user_id = int(payload.get("sub", "0"))
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证已失效，请重新登录") from exc
    user = db.get(User, user_id)
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证已失效，请重新登录")
    return user


@router.post("/ticket", response_model=FileTicketResponse)
def issue_file_ticket(
    user: User = Depends(get_current_user),
    settings: WebSettings = Depends(get_settings),
) -> FileTicketResponse:
    """签发短时效文件访问票据，供前端拼到 <img>/下载 URL，避免暴露长期登录 token。"""
    from pix_web.security import FILE_TICKET_TTL_SECONDS

    ticket = create_file_ticket(user, settings)
    return FileTicketResponse(ticket=ticket, expires_in=FILE_TICKET_TTL_SECONDS)


@router.get("")
def get_file(
    path: str,
    request: Request,
    user: User = Depends(_file_user),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> FileResponse:
    resolved = resolve_web_file(path, settings)
    if not user_owns_file(resolved, user, db, settings):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="文件不允许访问")
    return FileResponse(resolved)
