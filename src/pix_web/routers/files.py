"""受保护的 Web 文件访问。"""

from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from pix_web.models import User
from pix_web.security import get_db, get_settings
from sqlalchemy.orm import Session

from pix_web.config import WebSettings
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
    try:
        payload = jwt.decode(raw_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = int(payload.get("sub", "0"))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证已失效，请重新登录") from exc
    user = db.get(User, user_id)
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证已失效，请重新登录")
    return user


@router.get("")
def get_file(
    path: str,
    request: Request,
    _user: User = Depends(_file_user),
) -> FileResponse:
    resolved = resolve_web_file(path, request.app.state.web_settings)
    return FileResponse(resolved)
