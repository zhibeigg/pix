"""点数账户与流水。"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.models import CreditAccount, CreditTransaction, GenerationJob, User


class InsufficientCreditsError(RuntimeError):
    pass


def ensure_credit_account(db: Session, user: User) -> CreditAccount:
    account = db.scalar(select(CreditAccount).where(CreditAccount.user_id == user.id))
    if account is not None:
        return account
    account = CreditAccount(user_id=user.id)
    db.add(account)
    db.flush()
    return account


def add_transaction(
    db: Session,
    *,
    user_id: int,
    type: str,
    amount: int,
    balance_after: int,
    job_id: int | None = None,
    note: str = "",
) -> CreditTransaction:
    tx = CreditTransaction(
        user_id=user_id,
        type=type,
        amount=amount,
        balance_after=balance_after,
        job_id=job_id,
        note=note,
    )
    db.add(tx)
    db.flush()
    return tx


def adjust_credits(db: Session, user: User, amount: int, note: str = "") -> CreditTransaction:
    account = ensure_credit_account(db, user)
    account.available_credits += amount
    if amount > 0:
        account.total_recharged += amount
    return add_transaction(
        db,
        user_id=user.id,
        type="adjustment",
        amount=amount,
        balance_after=account.available_credits,
        note=note,
    )


def recharge_credits(db: Session, user: User, amount: int, note: str = "") -> CreditTransaction:
    account = ensure_credit_account(db, user)
    account.available_credits += amount
    account.total_recharged += max(0, amount)
    return add_transaction(
        db,
        user_id=user.id,
        type="recharge",
        amount=amount,
        balance_after=account.available_credits,
        note=note,
    )


def spend_credits(db: Session, user: User, amount: int, note: str = "") -> CreditTransaction:
    if amount <= 0:
        raise ValueError("消费点数必须大于 0")
    account = ensure_credit_account(db, user)
    if account.available_credits < amount:
        raise InsufficientCreditsError("点数不足")
    account.available_credits -= amount
    account.total_consumed += amount
    return add_transaction(
        db,
        user_id=user.id,
        type="consume",
        amount=-amount,
        balance_after=account.available_credits,
        note=note,
    )


def reserve_credits(db: Session, user: User, job: GenerationJob, amount: int) -> CreditTransaction | None:
    if amount <= 0:
        job.reserved_credits = 0
        return None
    account = ensure_credit_account(db, user)
    if account.available_credits < amount:
        raise InsufficientCreditsError("点数不足")
    account.available_credits -= amount
    account.reserved_credits += amount
    job.reserved_credits = amount
    return add_transaction(
        db,
        user_id=user.id,
        type="reserve",
        amount=-amount,
        balance_after=account.available_credits,
        job_id=job.id,
        note="创建生成任务时冻结点数",
    )


def consume_reserved(db: Session, job: GenerationJob) -> CreditTransaction | None:
    if job.reserved_credits <= 0:
        return None
    user = db.get(User, job.user_id)
    if user is None:
        raise RuntimeError(f"任务用户不存在: {job.user_id}")
    account = ensure_credit_account(db, user)
    amount = job.reserved_credits
    account.reserved_credits = max(0, account.reserved_credits - amount)
    account.total_consumed += amount
    job.reserved_credits = 0
    return add_transaction(
        db,
        user_id=user.id,
        type="consume",
        amount=0,
        balance_after=account.available_credits,
        job_id=job.id,
        note=f"任务成功，确认消费 {amount} 点",
    )


def settle_partial_reserved(
    db: Session,
    job: GenerationJob,
    *,
    consume_amount: int,
    note: str = "",
) -> CreditTransaction | None:
    """按实际消费结算预扣点数：实扣 consume_amount，退还其余。

    用于尺寸重试等"下单按最坏情况预扣、成功后按实际尝试次数结算"的场景。
    consume_amount 会被夹在 [0, reserved] 区间。返回最后一笔流水（退款流水，
    若无退款则返回消费流水）。账目守恒：reserved 全部清零，消费部分计入
    total_consumed，剩余部分退回 available。
    """
    reserved = job.reserved_credits
    if reserved <= 0:
        return None
    user = db.get(User, job.user_id)
    if user is None:
        raise RuntimeError(f"任务用户不存在: {job.user_id}")
    account = ensure_credit_account(db, user)

    consume = max(0, min(int(consume_amount), reserved))
    refund = reserved - consume

    account.reserved_credits = max(0, account.reserved_credits - reserved)
    job.reserved_credits = 0

    last_tx: CreditTransaction | None = None
    if consume > 0:
        account.total_consumed += consume
        last_tx = add_transaction(
            db,
            user_id=user.id,
            type="consume",
            amount=0,
            balance_after=account.available_credits,
            job_id=job.id,
            note=note or f"任务成功，按实际尝试确认消费 {consume} 点",
        )
    if refund > 0:
        account.available_credits += refund
        last_tx = add_transaction(
            db,
            user_id=user.id,
            type="refund",
            amount=refund,
            balance_after=account.available_credits,
            job_id=job.id,
            note=f"尺寸重试结算，退还未使用的 {refund} 点",
        )
    return last_tx


def refund_reserved(db: Session, job: GenerationJob, note: str = "任务失败自动退款") -> CreditTransaction | None:
    if job.reserved_credits <= 0:
        return None
    user = db.get(User, job.user_id)
    if user is None:
        raise RuntimeError(f"任务用户不存在: {job.user_id}")
    account = ensure_credit_account(db, user)
    amount = job.reserved_credits
    account.reserved_credits = max(0, account.reserved_credits - amount)
    account.available_credits += amount
    job.reserved_credits = 0
    return add_transaction(
        db,
        user_id=user.id,
        type="refund",
        amount=amount,
        balance_after=account.available_credits,
        job_id=job.id,
        note=note,
    )


def insufficient_credits_http() -> HTTPException:
    return HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="点数不足，请先充值")
