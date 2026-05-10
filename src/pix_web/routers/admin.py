"""管理员接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pix_web.credits import adjust_credits
from pix_web.models import GenerationJob, PricingRule, SystemSetting, User
from pix_web.schemas import (
    AdminAdjustCreditsRequest,
    CreditTransactionResponse,
    JobResponse,
    PricingRuleResponse,
    PricingRuleUpdateRequest,
    SystemSettingResponse,
    SystemSettingUpdateRequest,
    UserResponse,
)
from pix_web.security import get_db, require_admin
from pix_web.system_settings import list_system_settings, update_system_setting

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserResponse])
def users(_admin: User = Depends(require_admin), db: Session = Depends(get_db), limit: int = 100) -> list[User]:
    stmt = select(User).order_by(User.created_at.desc()).limit(max(1, min(500, limit)))
    return list(db.scalars(stmt))


@router.post("/users/{user_id}/adjust-credits", response_model=CreditTransactionResponse)
def adjust_user_credits(
    user_id: int,
    req: AdminAdjustCreditsRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    tx = adjust_credits(db, user, req.amount, req.note or "管理员调整点数")
    db.commit()
    db.refresh(tx)
    return tx


@router.get("/jobs", response_model=list[JobResponse])
def jobs(_admin: User = Depends(require_admin), db: Session = Depends(get_db), limit: int = 100) -> list[GenerationJob]:
    stmt = (
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs))
        .order_by(GenerationJob.created_at.desc())
        .limit(max(1, min(500, limit)))
    )
    return list(db.scalars(stmt))


@router.get("/pricing", response_model=list[PricingRuleResponse])
def pricing(_admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[PricingRule]:
    return list(db.scalars(select(PricingRule).order_by(PricingRule.key.asc())))


@router.put("/pricing/{key}", response_model=PricingRuleResponse)
def update_pricing(
    key: str,
    req: PricingRuleUpdateRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PricingRule:
    rule = db.scalar(select(PricingRule).where(PricingRule.key == key))
    if rule is None:
        rule = PricingRule(key=key)
        db.add(rule)
    rule.price_credits = req.price_credits
    rule.enabled = req.enabled
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/settings", response_model=list[SystemSettingResponse])
def settings(_admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[SystemSetting]:
    return list_system_settings(db)


@router.put("/settings/{key}", response_model=SystemSettingResponse)
def update_setting(
    key: str,
    req: SystemSettingUpdateRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SystemSetting:
    return update_system_setting(db, key, req.value)
