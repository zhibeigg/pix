"""认证接口。"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pix_web.config import WebSettings
from pix_web.credits import ensure_credit_account, recharge_credits
from pix_web.email_sender import EmailDeliveryError, send_verification_email
from pix_web.email_verification import (
    EmailCodeError,
    consume_email_code,
    create_email_code,
    normalize_email,
)
from pix_web.models import User
from pix_web.referrals import bind_referral_invite
from pix_web.schemas import (
    BootstrapAdminRequest,
    BootstrapAdminResponse,
    EmailCodeRequest,
    EmailCodeResponse,
    LoginRequest,
    RegisterRequest,
    SetupStatusResponse,
    TokenResponse,
    UserResponse,
)
from pix_web.system_settings import load_effective_web_settings, load_operational_settings, load_referral_settings
from pix_web.security import (
    create_access_token,
    find_user_by_email,
    get_current_user,
    get_db,
    get_settings,
    hash_password,
    is_local_request,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

LOCAL_TEST_ACCOUNT_EMAIL = "local-test@pix.example"
LOCAL_TEST_ACCOUNT_DISPLAY_NAME = "本地测试账号"
LOCAL_TEST_ACCOUNT_CREDITS = 1000


def _user_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User)) or 0


def _admin_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User).where(User.role == "admin")) or 0


def _raise_email_code_error(exc: EmailCodeError) -> None:
    headers = {}
    if exc.retry_after_seconds is not None:
        headers["Retry-After"] = str(exc.retry_after_seconds)
    raise HTTPException(status_code=exc.status_code, detail=exc.detail, headers=headers)


def _random_disabled_password_hash() -> str:
    return hash_password(secrets.token_urlsafe(48))


def _ensure_local_test_user(db: Session) -> User:
    user = find_user_by_email(db, LOCAL_TEST_ACCOUNT_EMAIL)
    if user is None:
        user = User(
            email=LOCAL_TEST_ACCOUNT_EMAIL,
            password_hash=_random_disabled_password_hash(),
            display_name=LOCAL_TEST_ACCOUNT_DISPLAY_NAME,
            role="user",
            status="active",
        )
        db.add(user)
        db.flush()
    else:
        user.password_hash = _random_disabled_password_hash()
        user.display_name = LOCAL_TEST_ACCOUNT_DISPLAY_NAME
        user.role = "user"
        user.status = "active"
    account = ensure_credit_account(db, user)
    if account.available_credits < LOCAL_TEST_ACCOUNT_CREDITS:
        recharge_credits(
            db,
            user,
            LOCAL_TEST_ACCOUNT_CREDITS - account.available_credits,
            note="本地测试账号点数补足",
        )
    return user


@router.get("/setup-status", response_model=SetupStatusResponse)
def setup_status(
    request: Request,
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> SetupStatusResponse:
    effective = load_effective_web_settings(db, settings)
    admins = _admin_count(db)
    users = _user_count(db)
    ops = load_operational_settings(db)
    local_test_available = is_local_request(request)
    return SetupStatusResponse(
        needs_admin=admins == 0,
        user_count=users,
        admin_count=admins,
        email_provider=effective.email_provider,
        debug_codes_available=effective.email_debug_codes or effective.email_provider == "console",
        registration_bonus_credits=ops.registration_bonus_credits,
        local_test_login_available=local_test_available,
        local_test_account_email=LOCAL_TEST_ACCOUNT_EMAIL if local_test_available else None,
    )


@router.post("/bootstrap-admin", response_model=BootstrapAdminResponse)
def bootstrap_admin(
    req: BootstrapAdminRequest,
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> BootstrapAdminResponse:
    if _admin_count(db) != 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="站点已完成初始化")
    email = normalize_email(str(req.email))
    user = User(
        email=email,
        password_hash=hash_password(req.password),
        display_name=req.display_name.strip() or email.split("@", 1)[0],
        role="admin",
    )
    db.add(user)
    db.flush()
    ensure_credit_account(db, user)
    ops = load_operational_settings(db)
    if ops.registration_bonus_credits > 0:
        recharge_credits(db, user, ops.registration_bonus_credits, note="注册赠送")
    db.commit()
    db.refresh(user)
    effective = load_effective_web_settings(db, settings)
    return BootstrapAdminResponse(
        access_token=create_access_token(user, effective),
        user=UserResponse.model_validate(user),
    )


@router.post("/local-test-login", response_model=TokenResponse)
def local_test_login(
    request: Request,
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> TokenResponse:
    if not is_local_request(request):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    effective = load_effective_web_settings(db, settings)
    user = _ensure_local_test_user(db)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user, effective, local_only=True))


@router.post("/register-code", response_model=EmailCodeResponse)
def request_register_code(
    req: EmailCodeRequest,
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> EmailCodeResponse:
    effective = load_effective_web_settings(db, settings)
    email = normalize_email(str(req.email))
    if find_user_by_email(db, email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="邮箱已注册")
    try:
        result = create_email_code(db, effective, email)
    except EmailCodeError as exc:
        db.rollback()
        _raise_email_code_error(exc)
    try:
        send_verification_email(effective, email, result.code)
    except EmailDeliveryError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    db.commit()
    return EmailCodeResponse(
        retry_after_seconds=result.retry_after_seconds,
        expires_in_seconds=effective.email_code_ttl_seconds,
        debug_code=result.code if effective.email_debug_codes or effective.email_provider == "console" else None,
    )


@router.post("/register", response_model=UserResponse)
def register(
    req: RegisterRequest,
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> User:
    effective = load_effective_web_settings(db, settings)
    email = normalize_email(str(req.email))
    if find_user_by_email(db, email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="邮箱已注册")
    try:
        consume_email_code(db, effective, email, req.verification_code)
    except EmailCodeError as exc:
        db.commit()
        _raise_email_code_error(exc)
    user_count = _user_count(db)
    user = User(
        email=email,
        password_hash=hash_password(req.password),
        display_name=req.display_name.strip() or email.split("@", 1)[0],
        role="admin" if user_count == 0 else "user",
    )
    db.add(user)
    db.flush()
    ensure_credit_account(db, user)
    referral_settings = load_referral_settings(db)
    bind_referral_invite(db, user, req.referral_code, referral_settings)
    ops = load_operational_settings(db)
    if ops.registration_bonus_credits > 0:
        recharge_credits(db, user, ops.registration_bonus_credits, note="注册赠送")
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    req: LoginRequest,
    db: Session = Depends(get_db),
    settings=Depends(get_settings),
) -> TokenResponse:
    effective = load_effective_web_settings(db, settings)
    user = find_user_by_email(db, req.email.lower())
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号不可用")
    return TokenResponse(access_token=create_access_token(user, effective))


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> User:
    return user
