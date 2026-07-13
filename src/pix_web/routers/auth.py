"""认证接口。"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pix_web.config import WebSettings
from pix_web.captcha import is_turnstile_active, verify_turnstile_token
from pix_web.credits import ensure_credit_account, recharge_credits
from pix_web.email_sender import EmailDeliveryError, send_password_reset_email, send_verification_email
from pix_web.email_verification import (
    PASSWORD_RESET_PURPOSE,
    REGISTER_PURPOSE,
    EmailCodeError,
    consume_email_code,
    count_recent_email_code_requests,
    count_recent_ip_code_requests,
    create_email_code,
    normalize_email,
)
from pix_web.models import User
from pix_web.rate_limit import (
    EMAIL_CODE_RATE_LIMIT,
    LOGIN_RATE_LIMIT,
    PASSWORD_RESET_RATE_LIMIT,
    REGISTER_RATE_LIMIT,
    limiter,
)
from pix_web.promo import bind_user_promo
from pix_web.referrals import bind_referral_invite
from pix_web.schemas import (
    BootstrapAdminRequest,
    BootstrapAdminResponse,
    EmailCodeRequest,
    EmailCodeResponse,
    LoginRequest,
    RegisterRequest,
    ResetCodeRequest,
    ResetPasswordRequest,
    SetupStatusResponse,
    StepUpUpdateRequest,
    StepUpUpdateResponse,
    TokenResponse,
    UserResponse,
)
from pix_web.system_settings import load_effective_web_settings, load_operational_settings, load_referral_settings
from pix_web.security import (
    clear_session_cookie,
    create_access_token,
    create_update_step_up_token,
    find_user_by_email,
    get_current_user,
    get_db,
    get_settings,
    hash_password,
    is_local_request,
    require_browser_origin,
    require_cookie_admin,
    set_session_cookie,
    set_update_step_up_cookie,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

LOCAL_TEST_ACCOUNT_EMAIL = "local-test@pix.example"
LOCAL_TEST_ACCOUNT_DISPLAY_NAME = "本地测试账号"
LOCAL_TEST_ACCOUNT_CREDITS = 1000
TURNSTILE_REQUIRED_DETAIL = "请求较频繁，请完成人机校验后再发送验证码"


def _client_ip(request: Request) -> str | None:
    forwarded_for = (request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
    if forwarded_for:
        return forwarded_for[:64]
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip[:64]
    return request.client.host[:64] if request.client and request.client.host else None


def _turnstile_required_for_email_code(
    db: Session,
    settings: WebSettings,
    email: str,
    purpose: str,
    request_ip: str | None,
) -> bool:
    if not is_turnstile_active(settings):
        return False
    email_limit = settings.turnstile_email_max_without_challenge
    if email_limit > 0:
        email_count = count_recent_email_code_requests(
            db,
            email,
            purpose,
            settings.turnstile_email_window_seconds,
        )
        if email_count >= email_limit:
            return True
    ip_limit = settings.turnstile_ip_max_without_challenge
    if ip_limit > 0:
        ip_count = count_recent_ip_code_requests(
            db,
            request_ip,
            purpose,
            settings.turnstile_ip_window_seconds,
        )
        if ip_count >= ip_limit:
            return True
    return False


def _verify_turnstile_when_required(
    db: Session,
    settings: WebSettings,
    email: str,
    purpose: str,
    request_ip: str | None,
    token: str,
) -> None:
    if not _turnstile_required_for_email_code(db, settings, email, purpose, request_ip):
        return
    if not (token or "").strip():
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail=TURNSTILE_REQUIRED_DETAIL,
        )
    verify_turnstile_token(settings, token, remote_ip=request_ip)


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
        turnstile_enabled=is_turnstile_active(effective),
        turnstile_site_key=effective.turnstile_site_key if is_turnstile_active(effective) else "",
    )


def _create_bootstrap_admin(req: BootstrapAdminRequest, db: Session) -> User:
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
    return user


@router.post("/bootstrap-admin", response_model=BootstrapAdminResponse)
def bootstrap_admin(
    req: BootstrapAdminRequest,
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> BootstrapAdminResponse:
    user = _create_bootstrap_admin(req, db)
    effective = load_effective_web_settings(db, settings)
    return BootstrapAdminResponse(
        access_token=create_access_token(user, effective),
        user=UserResponse.model_validate(user),
    )


@router.post("/session/bootstrap-admin", response_model=UserResponse)
def session_bootstrap_admin(
    req: BootstrapAdminRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> User:
    require_browser_origin(request, settings)
    user = _create_bootstrap_admin(req, db)
    effective = load_effective_web_settings(db, settings)
    set_session_cookie(response, create_access_token(user, effective), effective)
    return user


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


@router.post("/session/local-test-login", response_model=UserResponse)
def session_local_test_login(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> User:
    require_browser_origin(request, settings)
    if not is_local_request(request):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    effective = load_effective_web_settings(db, settings)
    user = _ensure_local_test_user(db)
    db.commit()
    db.refresh(user)
    set_session_cookie(response, create_access_token(user, effective, local_only=True), effective)
    return user


@router.post("/register-code", response_model=EmailCodeResponse)
@limiter.limit(EMAIL_CODE_RATE_LIMIT)
def request_register_code(
    req: EmailCodeRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> EmailCodeResponse:
    effective = load_effective_web_settings(db, settings)
    request_ip = _client_ip(request)
    email = normalize_email(str(req.email))
    if find_user_by_email(db, email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="邮箱已注册")
    _verify_turnstile_when_required(
        db,
        effective,
        email,
        REGISTER_PURPOSE,
        request_ip,
        req.turnstile_token,
    )
    try:
        result = create_email_code(db, effective, email, request_ip=request_ip)
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
@limiter.limit(REGISTER_RATE_LIMIT)
def register(
    req: RegisterRequest,
    request: Request,
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
    bind_user_promo(db, user, req.promo_code)
    ops = load_operational_settings(db)
    if ops.registration_bonus_credits > 0:
        recharge_credits(db, user, ops.registration_bonus_credits, note="注册赠送")
    db.commit()
    db.refresh(user)
    return user


def _authenticate_user(req: LoginRequest, db: Session) -> User:
    user = find_user_by_email(db, req.email.lower())
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号不可用")
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit(LOGIN_RATE_LIMIT)
def login(
    req: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> TokenResponse:
    effective = load_effective_web_settings(db, settings)
    user = _authenticate_user(req, db)
    return TokenResponse(access_token=create_access_token(user, effective))


@router.post("/session/login", response_model=UserResponse)
@limiter.limit(LOGIN_RATE_LIMIT)
def session_login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> User:
    require_browser_origin(request, settings)
    effective = load_effective_web_settings(db, settings)
    user = _authenticate_user(req, db)
    set_session_cookie(response, create_access_token(user, effective), effective)
    return user


@router.post("/session/step-up-update", response_model=StepUpUpdateResponse)
def session_step_up_update(
    req: StepUpUpdateRequest,
    response: Response,
    admin: User = Depends(require_cookie_admin),
    settings: WebSettings = Depends(get_settings),
) -> StepUpUpdateResponse:
    if not verify_password(req.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="密码错误",
        )
    set_update_step_up_cookie(
        response,
        create_update_step_up_token(admin, settings),
        settings,
    )
    return StepUpUpdateResponse(expires_in_seconds=max(30, settings.update_step_up_ttl_seconds))


@router.post("/reset-code", response_model=EmailCodeResponse)
@limiter.limit(EMAIL_CODE_RATE_LIMIT)
def request_reset_code(
    req: ResetCodeRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> EmailCodeResponse:
    """发送密码重置验证码。不暴露用户是否存在。"""
    effective = load_effective_web_settings(db, settings)
    request_ip = _client_ip(request)
    email = normalize_email(str(req.email))
    _verify_turnstile_when_required(
        db,
        effective,
        email,
        PASSWORD_RESET_PURPOSE,
        request_ip,
        req.turnstile_token,
    )
    user = find_user_by_email(db, email)
    if user is None:
        # 不暴露用户是否存在：假装已发送，但不实际发送
        return EmailCodeResponse(
            retry_after_seconds=effective.email_code_resend_seconds,
            expires_in_seconds=effective.email_code_ttl_seconds,
        )
    try:
        result = create_email_code(db, effective, email, purpose=PASSWORD_RESET_PURPOSE, request_ip=request_ip)
    except EmailCodeError as exc:
        db.rollback()
        _raise_email_code_error(exc)
    try:
        send_password_reset_email(effective, email, result.code)
    except EmailDeliveryError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    db.commit()
    return EmailCodeResponse(
        retry_after_seconds=result.retry_after_seconds,
        expires_in_seconds=effective.email_code_ttl_seconds,
        debug_code=result.code if effective.email_debug_codes or effective.email_provider == "console" else None,
    )


def _reset_password_user(
    req: ResetPasswordRequest,
    db: Session,
    settings: WebSettings,
) -> User:
    email = normalize_email(str(req.email))
    user = find_user_by_email(db, email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误或已过期")
    try:
        consume_email_code(db, settings, email, req.verification_code, purpose=PASSWORD_RESET_PURPOSE)
    except EmailCodeError as exc:
        db.commit()
        _raise_email_code_error(exc)
    user.password_hash = hash_password(req.new_password)
    db.commit()
    db.refresh(user)
    return user


@router.post("/reset-password", response_model=TokenResponse)
@limiter.limit(PASSWORD_RESET_RATE_LIMIT)
def reset_password(
    req: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> TokenResponse:
    """验证邮箱验证码后重置密码，成功后返回新 token 自动登录。"""
    effective = load_effective_web_settings(db, settings)
    user = _reset_password_user(req, db, effective)
    return TokenResponse(access_token=create_access_token(user, effective))


@router.post("/session/reset-password", response_model=UserResponse)
@limiter.limit(PASSWORD_RESET_RATE_LIMIT)
def session_reset_password(
    req: ResetPasswordRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> User:
    require_browser_origin(request, settings)
    effective = load_effective_web_settings(db, settings)
    user = _reset_password_user(req, db, effective)
    set_session_cookie(response, create_access_token(user, effective), effective)
    return user


@router.post("/session/logout", status_code=status.HTTP_204_NO_CONTENT)
def session_logout(
    request: Request,
    response: Response,
    settings: WebSettings = Depends(get_settings),
) -> Response:
    require_browser_origin(request, settings)
    clear_session_cookie(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> User:
    return user
