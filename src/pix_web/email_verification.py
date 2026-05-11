"""邮箱验证码生成与校验。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.config import WebSettings
from pix_web.models import EmailVerificationCode

REGISTER_PURPOSE = "register"


@dataclass(frozen=True)
class EmailCodeResult:
    code: str
    expires_at: datetime
    retry_after_seconds: int


class EmailCodeError(Exception):
    def __init__(self, detail: str, status_code: int = 422, retry_after_seconds: int | None = None):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def normalize_email(email: str) -> str:
    return email.strip().lower()


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(settings: WebSettings, email: str, purpose: str, code: str) -> str:
    payload = f"{normalize_email(email)}:{purpose}:{code}".encode("utf-8")
    return hmac.new(settings.jwt_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _latest_unconsumed(db: Session, email: str, purpose: str) -> EmailVerificationCode | None:
    return db.scalar(
        select(EmailVerificationCode)
        .where(
            EmailVerificationCode.email == email,
            EmailVerificationCode.purpose == purpose,
            EmailVerificationCode.consumed_at.is_(None),
        )
        .order_by(EmailVerificationCode.created_at.desc(), EmailVerificationCode.id.desc())
    )


def create_email_code(
    db: Session,
    settings: WebSettings,
    email: str,
    *,
    purpose: str = REGISTER_PURPOSE,
) -> EmailCodeResult:
    normalized = normalize_email(email)
    now = _now()
    latest = _latest_unconsumed(db, normalized, purpose)
    if latest is not None:
        available_at = _aware(latest.sent_at) + timedelta(seconds=settings.email_code_resend_seconds)
        if available_at > now:
            retry_after = max(1, int((available_at - now).total_seconds()))
            raise EmailCodeError("验证码发送太频繁，请稍后再试", 429, retry_after)

    old_codes = db.scalars(
        select(EmailVerificationCode).where(
            EmailVerificationCode.email == normalized,
            EmailVerificationCode.purpose == purpose,
            EmailVerificationCode.consumed_at.is_(None),
        )
    ).all()
    for item in old_codes:
        item.consumed_at = now

    code = generate_code()
    expires_at = now + timedelta(seconds=settings.email_code_ttl_seconds)
    record = EmailVerificationCode(
        email=normalized,
        purpose=purpose,
        code_hash=hash_code(settings, normalized, purpose, code),
        attempts=0,
        sent_at=now,
        expires_at=expires_at,
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    db.flush()
    return EmailCodeResult(
        code=code,
        expires_at=expires_at,
        retry_after_seconds=settings.email_code_resend_seconds,
    )


def consume_email_code(
    db: Session,
    settings: WebSettings,
    email: str,
    code: str,
    *,
    purpose: str = REGISTER_PURPOSE,
) -> None:
    normalized = normalize_email(email)
    record = _latest_unconsumed(db, normalized, purpose)
    now = _now()
    if record is None:
        raise EmailCodeError("请先获取邮箱验证码")
    if _aware(record.expires_at) <= now:
        record.consumed_at = now
        raise EmailCodeError("验证码已过期，请重新获取")
    if record.attempts >= settings.email_code_max_attempts:
        record.consumed_at = now
        raise EmailCodeError("验证码错误次数过多，请重新获取")

    expected = record.code_hash
    actual = hash_code(settings, normalized, purpose, code.strip())
    if not hmac.compare_digest(expected, actual):
        record.attempts += 1
        if record.attempts >= settings.email_code_max_attempts:
            record.consumed_at = now
        raise EmailCodeError("验证码错误")

    record.consumed_at = now
