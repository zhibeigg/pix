"""公开系统公告接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from pix_web.announcement_service import load_announcement_list
from pix_web.schemas import AnnouncementItemResponse, AnnouncementListResponse, AnnouncementResponse
from pix_web.security import get_db
from pix_web.system_settings import PublicAnnouncement, load_public_announcement

router = APIRouter(prefix="/announcements", tags=["announcements"])


@router.get("/current", response_model=AnnouncementResponse)
def current_announcement(db: Session = Depends(get_db)) -> PublicAnnouncement:
    return load_public_announcement(db)


@router.get("/list", response_model=AnnouncementListResponse)
def list_announcements(
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
) -> AnnouncementListResponse:
    """返回已发布且 enabled 的公告列表。"""
    items = load_announcement_list(db, include_disabled=False, limit=limit)
    active_count = len(items)
    return AnnouncementListResponse(
        items=[AnnouncementItemResponse.model_validate(a) for a in items],
        active_count=active_count,
    )
