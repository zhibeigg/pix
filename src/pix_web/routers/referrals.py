"""邀请奖励接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from pix_web.config import WebSettings
from pix_web.models import ReferralSettlement, User
from pix_web.referrals import (
    create_withdrawal_request,
    referral_summary,
    transfer_available_rewards_to_credits,
)
from pix_web.schemas import ReferralSummaryResponse, ReferralTransferRequest, ReferralWithdrawalRequest, ReferralSettlementResponse
from pix_web.security import get_current_user, get_db, get_settings
from pix_web.system_settings import load_effective_web_settings

router = APIRouter(prefix="/referrals", tags=["referrals"])


@router.get("/summary", response_model=ReferralSummaryResponse)
def summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> dict:
    effective = load_effective_web_settings(db, settings)
    data = referral_summary(db, user, public_base_url=effective.public_base_url)
    db.commit()
    return data


@router.post("/transfer", response_model=ReferralSettlementResponse)
def transfer(
    req: ReferralTransferRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReferralSettlement:
    settlement = transfer_available_rewards_to_credits(db, user, currency=req.currency)
    db.commit()
    db.refresh(settlement)
    return settlement


@router.post("/withdrawals", response_model=ReferralSettlementResponse)
def create_withdrawal(
    req: ReferralWithdrawalRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReferralSettlement:
    settlement = create_withdrawal_request(
        db,
        user,
        amount_cents=req.amount_cents,
        currency=req.currency,
        note=req.note,
    )
    db.commit()
    db.refresh(settlement)
    return settlement
