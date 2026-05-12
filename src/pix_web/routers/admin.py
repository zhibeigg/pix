"""管理员接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pix_web.config import WebSettings
from pix_web.credits import adjust_credits
from pix_web.dashboard import admin_dashboard
from pix_web.email_sender import EmailDeliveryError, send_verification_email
from pix_web.email_verification import generate_code
from pix_web.models import CreditPackage, GenerationJob, PricingRule, User
from pix_web.schemas import (
    AdminAdjustCreditsRequest,
    AdminDashboardResponse,
    CreditPackageCreateRequest,
    CreditPackageResponse,
    CreditPackageUpdateRequest,
    CreditTransactionResponse,
    EmailTestRequest,
    EmailTestResponse,
    JobResponse,
    PricingRuleResponse,
    PricingRuleUpdateRequest,
    SystemSettingResponse,
    SystemSettingUpdateRequest,
    UserResponse,
)
from pix_web.security import get_db, get_settings, require_admin
from pix_web.system_settings import AdminSettingView, list_admin_settings, load_effective_web_settings, update_system_setting

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard", response_model=AdminDashboardResponse)
def dashboard(_admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, int | float]:
    return admin_dashboard(db)


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


@router.get("/packages", response_model=list[CreditPackageResponse])
def packages(_admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[CreditPackage]:
    return list(
        db.scalars(
            select(CreditPackage).order_by(CreditPackage.sort_order.asc(), CreditPackage.amount_cents.asc())
        )
    )


@router.post("/packages", response_model=CreditPackageResponse)
def create_package(
    req: CreditPackageCreateRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CreditPackage:
    existing = db.scalar(select(CreditPackage).where(CreditPackage.key == req.key))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="充值套餐 key 已存在")
    package = CreditPackage(**req.model_dump())
    db.add(package)
    db.commit()
    db.refresh(package)
    return package


@router.put("/packages/{key}", response_model=CreditPackageResponse)
def update_package(
    key: str,
    req: CreditPackageUpdateRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CreditPackage:
    package = db.scalar(select(CreditPackage).where(CreditPackage.key == key))
    if package is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="充值套餐不存在")
    package.name = req.name
    package.credits = req.credits
    package.amount_cents = req.amount_cents
    package.currency = req.currency
    package.enabled = req.enabled
    package.sort_order = req.sort_order
    db.commit()
    db.refresh(package)
    return package


@router.get("/settings", response_model=list[SystemSettingResponse])
def settings(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    web_settings: WebSettings = Depends(get_settings),
) -> list[AdminSettingView]:
    return list_admin_settings(db, web_settings)


@router.put("/settings/{key}", response_model=SystemSettingResponse)
def update_setting(
    key: str,
    req: SystemSettingUpdateRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    web_settings: WebSettings = Depends(get_settings),
) -> AdminSettingView:
    update_system_setting(db, key, req.value or "", clear=req.clear)
    return next(item for item in list_admin_settings(db, web_settings) if item.key == key)


@router.post("/settings/test-email", response_model=EmailTestResponse)
def test_email_setting(
    req: EmailTestRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    web_settings: WebSettings = Depends(get_settings),
) -> EmailTestResponse:
    effective = load_effective_web_settings(db, web_settings)
    code = generate_code()
    try:
        send_verification_email(effective, str(req.email), code)
    except EmailDeliveryError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return EmailTestResponse(
        message="测试邮件已发送" if effective.email_provider == "smtp" else "console 测试验证码已生成",
        debug_code=code if effective.email_debug_codes or effective.email_provider == "console" else None,
    )
