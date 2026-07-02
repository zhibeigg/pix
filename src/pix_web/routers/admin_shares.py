"""管理员：用户分享作品审核接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pix_web.config import WebSettings
from pix_web.credits import reward_share_credits
from pix_web.models import SharedWork, User, utcnow
from pix_web.routers.shares import (
    SHARE_STATUS_ACTIVE,
    SHARE_STATUS_DELETED,
    SHARE_STATUS_HIDDEN,
    SHARE_STATUS_REJECTED,
    _file_ticket_user,
    _reward_amount_for_publish,
)
from pix_web.schemas import AdminSharedWorkListResponse, AdminSharedWorkResponse, ShareRejectRequest
from pix_web.security import get_db, get_settings, require_admin
from pix_web.storage import resolve_web_file

router = APIRouter(prefix="/admin/shares", tags=["admin"])


def _admin_response(share: SharedWork, *, user_email: str = "") -> AdminSharedWorkResponse:
    snapshot = share.parameter_snapshot_json if isinstance(share.parameter_snapshot_json, dict) else {}
    return AdminSharedWorkResponse(
        id=share.id,
        job_id=share.job_id,
        user_id=share.user_id,
        user_email=user_email,
        status=share.status,
        title=share.title,
        asset_kind=share.asset_kind,
        preview_url=f"/admin/shares/{share.id}/preview",
        parameter_snapshot=snapshot,
        like_count=share.like_count,
        download_count=share.download_count,
        reward_credits=share.reward_credits,
        review_note=share.review_note or "",
        reviewed_at=share.reviewed_at,
        reviewed_by_user_id=share.reviewed_by_user_id,
        published_at=share.published_at,
        created_at=share.created_at,
        updated_at=share.updated_at,
    )


@router.get("", response_model=AdminSharedWorkListResponse)
def list_admin_shares(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    status_filter: str = Query(default="pending", alias="status"),
    limit: int = Query(default=48, ge=1, le=120),
    offset: int = Query(default=0, ge=0),
) -> AdminSharedWorkListResponse:
    conditions = [SharedWork.status != SHARE_STATUS_DELETED]
    if status_filter and status_filter != "all":
        conditions = [SharedWork.status == status_filter]
    total = int(db.scalar(select(func.count()).select_from(SharedWork).where(*conditions)) or 0)
    shares = list(db.scalars(
        select(SharedWork)
        .where(*conditions)
        # 待审核优先按提交时间正序（先到先审），其余按更新时间倒序。
        .order_by(SharedWork.updated_at.desc(), SharedWork.id.desc())
        .offset(offset)
        .limit(limit)
    ))
    emails: dict[int, str] = {}
    if shares:
        user_ids = {share.user_id for share in shares}
        for uid, email in db.execute(select(User.id, User.email).where(User.id.in_(user_ids))):
            emails[int(uid)] = email or ""
    return AdminSharedWorkListResponse(
        items=[_admin_response(share, user_email=emails.get(share.user_id, "")) for share in shares],
        total=total,
        limit=limit,
        offset=offset,
    )


def _load_share(db: Session, share_id: int) -> SharedWork:
    share = db.get(SharedWork, share_id)
    if share is None or share.status == SHARE_STATUS_DELETED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享作品不存在")
    return share


@router.post("/{share_id}/approve", response_model=AdminSharedWorkResponse)
def approve_share(
    share_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminSharedWorkResponse:
    share = _load_share(db, share_id)
    if share.status == SHARE_STATUS_ACTIVE:
        return _admin_response(share)
    now = utcnow()
    share.status = SHARE_STATUS_ACTIVE
    share.published_at = now
    share.review_note = ""
    share.reviewed_at = now
    share.reviewed_by_user_id = admin.id
    share.updated_at = now

    # 奖励发给作品作者（share.user_id），而非当前操作管理员；日限也按作者计。
    if share.rewarded_at is None:
        author = db.get(User, share.user_id)
        if author is not None:
            reward = _reward_amount_for_publish(db, author)
            share.reward_credits = reward
            share.rewarded_at = now
            if reward > 0:
                reward_share_credits(db, author, reward, job_id=share.job_id, note=f"公开分享作品审核通过 #{share.job_id} 奖励")

    db.commit()
    db.refresh(share)
    return _admin_response(share)


@router.post("/{share_id}/reject", response_model=AdminSharedWorkResponse)
def reject_share(
    share_id: int,
    req: ShareRejectRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminSharedWorkResponse:
    share = _load_share(db, share_id)
    now = utcnow()
    share.status = SHARE_STATUS_REJECTED
    share.review_note = (req.note or "").strip()[:500]
    share.reviewed_at = now
    share.reviewed_by_user_id = admin.id
    share.published_at = None
    share.updated_at = now
    db.commit()
    db.refresh(share)
    return _admin_response(share)


@router.post("/{share_id}/unpublish", response_model=AdminSharedWorkResponse)
def admin_unpublish_share(
    share_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminSharedWorkResponse:
    share = _load_share(db, share_id)
    now = utcnow()
    share.status = SHARE_STATUS_HIDDEN
    share.reviewed_at = now
    share.reviewed_by_user_id = admin.id
    share.updated_at = now
    db.commit()
    db.refresh(share)
    return _admin_response(share)


@router.get("/{share_id}/preview")
def admin_shared_preview(
    share_id: int,
    request: Request,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> FileResponse:
    # 票据 / Bearer 解析出用户后二次校验管理员角色：普通用户即便持票据也无法访问待审核图。
    user = _file_ticket_user(request, token, db, settings)
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    share = db.get(SharedWork, share_id)
    if share is None or share.status == SHARE_STATUS_DELETED or not share.preview_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享作品不存在")
    resolved = resolve_web_file(share.preview_path, settings)
    return FileResponse(resolved, filename=resolved.name, content_disposition_type="inline")
