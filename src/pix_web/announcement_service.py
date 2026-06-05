"""系统公告发布与邮件通知协调。"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pix_web.models import Announcement, SystemSetting, User

ANNOUNCEMENT_ENABLED_KEY = "site.announcement.enabled"
ANNOUNCEMENT_TITLE_KEY = "site.announcement.title"
ANNOUNCEMENT_BODY_KEY = "site.announcement.body"
ANNOUNCEMENT_LAST_EMAIL_SIGNATURE_KEY = "site.announcement.last_email_signature"
ANNOUNCEMENT_LAST_NOTIFIED_CONTENT_KEY = "site.announcement.last_notified_content"


@dataclass(frozen=True)
class AnnouncementPublishOutcome:
    announcement: Announcement
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


def _content_signature(title: str, body: str) -> str:
    payload = json.dumps(
        {"title": title, "body": body},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sync_announcement_to_settings(db: Session, announcement: Announcement) -> None:
    """将最新一条 enabled 公告同步到 system_settings（向后兼容）。"""
    title_row = _get_or_create_setting(db, ANNOUNCEMENT_TITLE_KEY)
    body_row = _get_or_create_setting(db, ANNOUNCEMENT_BODY_KEY)
    enabled_row = _get_or_create_setting(db, ANNOUNCEMENT_ENABLED_KEY, "false")
    title_row.value = announcement.title
    body_row.value = announcement.body
    enabled_row.value = "true" if announcement.enabled else "false"


def _next_sort_order(db: Session) -> int:
    max_order = db.scalar(select(func.coalesce(func.max(Announcement.sort_order), 0)))
    return int(max_order) + 1


def publish_site_announcement(db: Session, *, title: str, body: str, enabled: bool) -> AnnouncementPublishOutcome:
    """兼容旧接口：创建新公告并同步到 system_settings，返回是否需要邮件通知。"""
    clean_title = title.strip()
    clean_body = body.strip()
    if enabled and not (clean_title or clean_body):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="公告标题或正文不能为空")

    from pix_web.system_settings import ensure_default_system_settings

    ensure_default_system_settings(db)

    content_sig_row = _get_or_create_setting(db, ANNOUNCEMENT_LAST_NOTIFIED_CONTENT_KEY)
    previous_content_sig = content_sig_row.value.strip()

    announcement = Announcement(
        title=clean_title,
        body=clean_body,
        enabled=enabled,
        sort_order=_next_sort_order(db),
    )
    db.add(announcement)
    db.flush()

    effective_enabled = enabled and bool(clean_title or clean_body)
    current_content_sig = _content_signature(clean_title, clean_body) if effective_enabled else ""
    content_changed = bool(current_content_sig) and current_content_sig != previous_content_sig

    should_notify = content_changed
    skipped_reason = ""
    if should_notify:
        content_sig_row.value = current_content_sig
    elif not effective_enabled:
        skipped_reason = "disabled"
    else:
        skipped_reason = "unchanged"

    _sync_announcement_to_settings(db, announcement)
    db.commit()
    db.refresh(announcement)

    return AnnouncementPublishOutcome(
        announcement=announcement,
        should_notify=should_notify,
        skipped_reason=skipped_reason,
    )


def create_announcement(db: Session, *, title: str, body: str, enabled: bool, publish_now: bool) -> Announcement:
    """管理员创建公告。"""
    clean_title = title.strip()
    clean_body = body.strip()
    if enabled and not (clean_title or clean_body):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="公告标题或正文不能为空")

    from pix_web.system_settings import ensure_default_system_settings

    ensure_default_system_settings(db)

    now_func = func.now()
    now_val = db.scalar(now_func)
    announcement = Announcement(
        title=clean_title,
        body=clean_body,
        enabled=enabled,
        sort_order=_next_sort_order(db),
        published_at=now_val if publish_now else None,
    )
    db.add(announcement)
    db.commit()
    db.refresh(announcement)

    if publish_now and enabled:
        _sync_announcement_to_settings(db, announcement)
        db.commit()

    return announcement


def update_announcement(
    db: Session,
    announcement_id: int,
    *,
    title: str | None = None,
    body: str | None = None,
    enabled: bool | None = None,
) -> Announcement:
    """管理员编辑公告。"""
    announcement = db.get(Announcement, announcement_id)
    if announcement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公告不存在")
    if title is not None:
        announcement.title = title.strip()
    if body is not None:
        announcement.body = body.strip()
    if enabled is not None:
        announcement.enabled = enabled
    db.commit()
    db.refresh(announcement)
    return announcement


def delete_announcement(db: Session, announcement_id: int) -> None:
    """管理员删除公告。"""
    announcement = db.get(Announcement, announcement_id)
    if announcement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公告不存在")
    db.delete(announcement)
    db.commit()


def load_announcement_list(db: Session, *, include_disabled: bool = False, limit: int = 50) -> list[Announcement]:
    """加载公告列表，按 sort_order ASC, created_at DESC 排序。"""
    stmt = select(Announcement)
    if not include_disabled:
        stmt = stmt.where(Announcement.enabled.is_(True))
    stmt = stmt.order_by(Announcement.sort_order.asc(), Announcement.created_at.desc()).limit(limit)
    return list(db.scalars(stmt))


def load_latest_enabled_announcement(db: Session) -> Announcement | None:
    """加载最新的 enabled 公告（用于兼容旧接口）。"""
    return db.scalar(
        select(Announcement)
        .where(Announcement.enabled.is_(True), Announcement.published_at.isnot(None))
        .order_by(Announcement.sort_order.desc())
        .limit(1)
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
