"""认证接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pix_web.credits import ensure_credit_account
from pix_web.models import User
from pix_web.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from pix_web.security import (
    create_access_token,
    find_user_by_email,
    get_current_user,
    get_db,
    get_settings,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> User:
    email = req.email.lower()
    if find_user_by_email(db, email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="邮箱已注册")
    user_count = db.scalar(select(func.count()).select_from(User)) or 0
    user = User(
        email=email,
        password_hash=hash_password(req.password),
        display_name=req.display_name.strip() or email.split("@", 1)[0],
        role="admin" if user_count == 0 else "user",
    )
    db.add(user)
    db.flush()
    ensure_credit_account(db, user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    req: LoginRequest,
    db: Session = Depends(get_db),
    settings=Depends(get_settings),
) -> TokenResponse:
    user = find_user_by_email(db, req.email.lower())
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号不可用")
    return TokenResponse(access_token=create_access_token(user, settings))


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> User:
    return user
