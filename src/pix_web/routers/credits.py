"""点数接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.credits import ensure_credit_account
from pix_web.models import CreditTransaction, User
from pix_web.schemas import CreditBalanceResponse, CreditTransactionResponse
from pix_web.security import get_current_user, get_db

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("/balance", response_model=CreditBalanceResponse)
def balance(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CreditBalanceResponse:
    account = ensure_credit_account(db, user)
    return CreditBalanceResponse(
        available_credits=account.available_credits,
        reserved_credits=account.reserved_credits,
        total_recharged=account.total_recharged,
        total_consumed=account.total_consumed,
    )


@router.get("/transactions", response_model=list[CreditTransactionResponse])
def transactions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
) -> list[CreditTransaction]:
    stmt = (
        select(CreditTransaction)
        .where(CreditTransaction.user_id == user.id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(max(1, min(200, limit)))
    )
    return list(db.scalars(stmt))
