"""公开系统公告接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from pix_web.schemas import AnnouncementResponse
from pix_web.security import get_db
from pix_web.system_settings import PublicAnnouncement, load_public_announcement

router = APIRouter(prefix="/announcements", tags=["announcements"])


@router.get("/current", response_model=AnnouncementResponse)
def current_announcement(db: Session = Depends(get_db)) -> PublicAnnouncement:
    return load_public_announcement(db)
