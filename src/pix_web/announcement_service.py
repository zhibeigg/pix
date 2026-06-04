"""系统公告发布与邮件通知协调。"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.models import SystemSetting, User
from pix_web.system_settings import PublicAnnouncement, ensure_default_system_settings, load_public_announcement

ANNOUNCEMENT_ENABLED_KEY = "site.announcement.enabled"
ANNOUNCEMENT_TITLE_KEY = "site.announcement.title"
ANNOUNCEMENT_BODY_KEY = "site.announcement.body"
ANNOUNCEMENT_LAST_EMAIL_SIGNATURE_KEY = "site.announcement.last_email_signature"


@dataclass(frozen=True)
class AnnouncementPublishOutcome:
    announcement: PublicAnnouncement
    should_notify: bool
    skipped_reason: str


def _get_or_create_setting(db: Session, key: str, default: str = "") -> SystemSetting:
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if setting is not None:
        return setting
    setting = SystemSetting(key=key, value=default)
    db.add(setting)
    db.flush()
    return setting


def _announcement_signature(title: str, body: str) -> str:
    payload = json.dumps(
        {"title": title, "body": body},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def publish_site_announcement(db: Session, *, title: str, body: str, enabled: bool) -> AnnouncementPublishOutcome:
    """一次性发布系统公告，并返回是否需要发送邮件通知。"""
    clean_title = title.strip()
    clean_body = body.strip()
    if enabled and not (clean_title or clean_body):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="公告标题或正文不能为空")

    ensure_default_system_settings(db)
    title_row = _get_or_create_setting(db, ANNOUNCEMENT_TITLE_KEY)
    body_row = _get_or_create_setting(db, ANNOUNCEMENT_BODY_KEY)
    enabled_row = _get_or_create_setting(db, ANNOUNCEMENT_ENABLED_KEY, "false")
    signature_row = _get_or_create_setting(db, ANNOUNCEMENT_LAST_EMAIL_SIGNATURE_KEY)

    title_row.value = clean_title
    body_row.value = clean_body
    enabled_row.value = "true" if enabled else "false"

    effective_enabled = enabled and bool(clean_title or clean_body)
    signature = _announcement_signature(clean_title, clean_body) if effective_enabled else ""
    should_notify = bool(signature and signature_row.value != signature)
    skipped_reason = ""
    if should_notify:
        signature_row.value = signature
    elif not effective_enabled:
        skipped_reason = "disabled"
    else:
        skipped_reason = "unchanged"

    db.commit()
    announcement = load_public_announcement(db)
    return AnnouncementPublishOutcome(
        announcement=announcement,
        should_notify=should_notify,
        skipped_reason=skipped_reason,
    )


def active_user_emails(db: Session) -> list[str]:
    """返回去重后的活跃用户邮箱列表。"""
    emails: list[str] = []
    seen: set[str] = set()
    stmt = select(User.email).where(User.status == "active").order_by(User.id.asc())
    for raw_email in db.scalars(stmt):
        email = raw_email.strip()
        key = email.lower()
        if not email or key in seen:
            continue
        seen.add(key)
        emails.append(email)
    return emails
