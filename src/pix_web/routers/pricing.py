"""公开价格规则接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.models import PricingRule
from pix_web.promo import clean_code, get_active_promo_link
from pix_web.schemas import PricingDiscountResponse, PromoLinkInfoResponse, PricingRuleResponse
from pix_web.security import get_db
from pix_web.system_settings import load_pricing_discount

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.get("", response_model=list[PricingRuleResponse])
def pricing(db: Session = Depends(get_db)) -> list[PricingRule]:
    return list(db.scalars(select(PricingRule).order_by(PricingRule.key.asc())))


@router.get("/discount", response_model=PricingDiscountResponse)
def pricing_discount(db: Session = Depends(get_db)) -> PricingDiscountResponse:
    discount = load_pricing_discount(db)
    return PricingDiscountResponse(active=discount.active, rate=discount.rate, label=discount.label)


@router.get("/promo/{code}", response_model=PromoLinkInfoResponse)
def promo_info(code: str, db: Session = Depends(get_db)) -> PromoLinkInfoResponse:
    """公开查询优惠码是否有效及其折扣倍率，供注册页展示。"""
    normalized = clean_code(code)
    link = get_active_promo_link(db, normalized)
    if link is None:
        return PromoLinkInfoResponse(code=normalized, active=False, discount_rate=1.0)
    return PromoLinkInfoResponse(code=link.code, active=True, discount_rate=link.discount_rate, name=link.name)
