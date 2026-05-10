"""公开价格规则接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.models import PricingRule
from pix_web.schemas import PricingRuleResponse
from pix_web.security import get_db

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.get("", response_model=list[PricingRuleResponse])
def pricing(db: Session = Depends(get_db)) -> list[PricingRule]:
    return list(db.scalars(select(PricingRule).order_by(PricingRule.key.asc())))
