"""点数账户与流水。

账户由两部分组成：
- available_credits：永久点数（充值 / 奖励 / 邀请划转）。
- daily_quota_balance：月卡会员每日临时额度，当天有效、次日按业务时区刷新，
  仅用于生成任务（reserve 链路），且优先于永久点数消耗。

生成任务扣点走 reserve → consume/settle/refund；作品库、素材包扩容等一次性消费
走 spend_credits，只使用永久点数。
"""

from __future__ import annotations

from datetime import datetime

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


def ensure_daily_quota(db: Session, account: CreditAccount, *, now: datetime | None = None) -> CreditAccount:
    """按业务时区惰性刷新每日临时额度。

    - 有有效会员且业务日已切换：把 daily_quota_balance 重置为会员每日额度、更新 date。
    - 无有效会员：清零当日额度（会员到期后立即失去临时额度）。
    - 冻结中的临时额度（reserved_quota）不受刷新影响，由任务结算/退款单独处理。
    """
    # 延迟导入避免与 membership.py 循环依赖。
    from pix_web.membership import business_day_key, active_daily_quota
    from pix_web.system_settings import resolve_site_timezone

    tz = resolve_site_timezone(db)
    today = business_day_key(tz, now)
    quota_limit = active_daily_quota(db, account.user_id, now)

    if quota_limit <= 0:
        # 无有效会员：清空当日可用临时额度（不动已冻结部分）。
        if account.daily_quota_balance != 0:
            account.daily_quota_balance = 0
        account.daily_quota_date = today
        return account

    if account.daily_quota_date != today:
        account.daily_quota_date = today
        account.daily_quota_balance = quota_limit
    return account


def daily_quota_limit(db: Session, account: CreditAccount, *, now: datetime | None = None) -> int:
    from pix_web.membership import active_daily_quota

    return active_daily_quota(db, account.user_id, now)


def build_balance_response(db: Session, account: CreditAccount):
    """构造包含会员临时额度的余额响应。"""
    from pix_web.membership import get_user_membership, is_active
    from pix_web.schemas import CreditBalanceResponse

    ensure_daily_quota(db, account)
    membership = get_user_membership(db, account.user_id)
    active = is_active(membership)
    limit = daily_quota_limit(db, account)
    return CreditBalanceResponse(
        available_credits=account.available_credits,
        reserved_credits=account.reserved_credits,
        total_recharged=account.total_recharged,
        total_consumed=account.total_consumed,
        daily_quota_balance=account.daily_quota_balance,
        daily_quota_limit=limit,
        reserved_quota=account.reserved_quota,
        available_total=available_total(account),
        membership_plan_key=membership.plan_key if active and membership is not None else None,
        membership_status=membership.status if membership is not None else None,
        membership_expires_at=membership.expires_at if active and membership is not None else None,
    )


def available_total(account: CreditAccount) -> int:
    """可用总量 = 当日临时额度 + 永久点数（用于余额判断与展示）。"""
    return account.daily_quota_balance + account.available_credits


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


def reward_share_credits(db: Session, user: User, amount: int, *, job_id: int | None = None, note: str = "") -> CreditTransaction | None:
    if amount <= 0:
        return None
    account = ensure_credit_account(db, user)
    account.available_credits += amount
    account.total_recharged += amount
    return add_transaction(
        db,
        user_id=user.id,
        type="share_reward",
        amount=amount,
        balance_after=account.available_credits,
        job_id=job_id,
        note=note or "公开分享作品奖励",
    )


def spend_credits(db: Session, user: User, amount: int, note: str = "") -> CreditTransaction:
    """一次性消费（作品库 / 素材包扩容等），仅使用永久点数，不动临时额度。"""
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
    """创建生成任务时冻结点数：优先冻结当日临时额度，不足部分用永久点数。

    临时额度部分记 job.reserved_quota + reserved_quota_date（用于退款时判断是否同日）；
    永久点数部分记 job.reserved_credits。返回最后一笔冻结流水。
    """
    if amount <= 0:
        job.reserved_credits = 0
        job.reserved_quota = 0
        return None
    account = ensure_credit_account(db, user)
    ensure_daily_quota(db, account)
    if available_total(account) < amount:
        raise InsufficientCreditsError("点数不足")

    quota_part = min(account.daily_quota_balance, amount)
    credit_part = amount - quota_part

    last_tx: CreditTransaction | None = None
    if quota_part > 0:
        account.daily_quota_balance -= quota_part
        account.reserved_quota += quota_part
        job.reserved_quota = quota_part
        job.reserved_quota_date = account.daily_quota_date
        last_tx = add_transaction(
            db,
            user_id=user.id,
            type="quota_reserve",
            amount=-quota_part,
            balance_after=account.available_credits,
            job_id=job.id,
            note=f"创建生成任务冻结每日额度 {quota_part} 点",
        )
    else:
        job.reserved_quota = 0
        job.reserved_quota_date = ""

    if credit_part > 0:
        account.available_credits -= credit_part
        account.reserved_credits += credit_part
        job.reserved_credits = credit_part
        last_tx = add_transaction(
            db,
            user_id=user.id,
            type="reserve",
            amount=-credit_part,
            balance_after=account.available_credits,
            job_id=job.id,
            note="创建生成任务时冻结点数",
        )
    else:
        job.reserved_credits = 0
    return last_tx


def consume_reserved(db: Session, job: GenerationJob) -> CreditTransaction | None:
    """任务成功：确认消费全部冻结（临时额度 + 永久点数）。"""
    if job.reserved_credits <= 0 and job.reserved_quota <= 0:
        return None
    user = db.get(User, job.user_id)
    if user is None:
        raise RuntimeError(f"任务用户不存在: {job.user_id}")
    account = ensure_credit_account(db, user)

    quota_amount = job.reserved_quota
    credit_amount = job.reserved_credits
    total = quota_amount + credit_amount

    if quota_amount > 0:
        account.reserved_quota = max(0, account.reserved_quota - quota_amount)
        job.reserved_quota = 0
    if credit_amount > 0:
        account.reserved_credits = max(0, account.reserved_credits - credit_amount)
        job.reserved_credits = 0
    account.total_consumed += total

    return add_transaction(
        db,
        user_id=user.id,
        type="consume",
        amount=0,
        balance_after=account.available_credits,
        job_id=job.id,
        note=f"任务成功，确认消费 {total} 点（含临时额度 {quota_amount} 点）" if quota_amount > 0 else f"任务成功，确认消费 {total} 点",
    )


def settle_partial_reserved(
    db: Session,
    job: GenerationJob,
    *,
    consume_amount: int,
    note: str = "",
) -> CreditTransaction | None:
    """按实际消费结算预扣点数：实扣 consume_amount，退还其余。

    结算顺序与冻结一致——优先消耗临时额度，其次永久点数；退还顺序相反（先退永久点数，
    再退临时额度）。临时额度退还时若已跨业务日则作废（不退回，仅记 note）。
    """
    reserved = job.reserved_quota + job.reserved_credits
    if reserved <= 0:
        return None
    user = db.get(User, job.user_id)
    if user is None:
        raise RuntimeError(f"任务用户不存在: {job.user_id}")
    account = ensure_credit_account(db, user)
    ensure_daily_quota(db, account)

    consume = max(0, min(int(consume_amount), reserved))

    # 消费优先扣临时额度，其次永久点数。
    quota_consume = min(job.reserved_quota, consume)
    credit_consume = consume - quota_consume
    # 退还部分。
    quota_refund = job.reserved_quota - quota_consume
    credit_refund = job.reserved_credits - credit_consume

    # 先清冻结账。
    account.reserved_quota = max(0, account.reserved_quota - job.reserved_quota)
    account.reserved_credits = max(0, account.reserved_credits - job.reserved_credits)
    reserved_quota_date = job.reserved_quota_date
    job.reserved_quota = 0
    job.reserved_credits = 0

    last_tx: CreditTransaction | None = None
    total_consume = quota_consume + credit_consume
    if total_consume > 0:
        account.total_consumed += total_consume
        last_tx = add_transaction(
            db,
            user_id=user.id,
            type="consume",
            amount=0,
            balance_after=account.available_credits,
            job_id=job.id,
            note=note or f"任务成功，按实际尝试确认消费 {total_consume} 点",
        )
    # 永久点数退还。
    if credit_refund > 0:
        account.available_credits += credit_refund
        last_tx = add_transaction(
            db,
            user_id=user.id,
            type="refund",
            amount=credit_refund,
            balance_after=account.available_credits,
            job_id=job.id,
            note=f"尺寸重试结算，退还未使用的 {credit_refund} 点",
        )
    # 临时额度退还：同一业务日退回当日额度，跨日作废。
    if quota_refund > 0:
        if reserved_quota_date and reserved_quota_date == account.daily_quota_date:
            account.daily_quota_balance += quota_refund
            last_tx = add_transaction(
                db,
                user_id=user.id,
                type="quota_refund",
                amount=quota_refund,
                balance_after=account.available_credits,
                job_id=job.id,
                note=f"尺寸重试结算，退回当日临时额度 {quota_refund} 点",
            )
        else:
            last_tx = add_transaction(
                db,
                user_id=user.id,
                type="quota_refund",
                amount=0,
                balance_after=account.available_credits,
                job_id=job.id,
                note=f"尺寸重试结算，临时额度 {quota_refund} 点已跨日作废",
            )
    return last_tx


def refund_reserved(db: Session, job: GenerationJob, note: str = "任务失败自动退款") -> CreditTransaction | None:
    """任务失败：退还全部冻结。永久点数退回可用余额；临时额度同日退回、跨日作废。"""
    if job.reserved_credits <= 0 and job.reserved_quota <= 0:
        return None
    user = db.get(User, job.user_id)
    if user is None:
        raise RuntimeError(f"任务用户不存在: {job.user_id}")
    account = ensure_credit_account(db, user)
    ensure_daily_quota(db, account)

    quota_amount = job.reserved_quota
    credit_amount = job.reserved_credits
    reserved_quota_date = job.reserved_quota_date

    account.reserved_quota = max(0, account.reserved_quota - quota_amount)
    account.reserved_credits = max(0, account.reserved_credits - credit_amount)
    job.reserved_quota = 0
    job.reserved_credits = 0

    last_tx: CreditTransaction | None = None
    if credit_amount > 0:
        account.available_credits += credit_amount
        last_tx = add_transaction(
            db,
            user_id=user.id,
            type="refund",
            amount=credit_amount,
            balance_after=account.available_credits,
            job_id=job.id,
            note=note,
        )
    if quota_amount > 0:
        if reserved_quota_date and reserved_quota_date == account.daily_quota_date:
            account.daily_quota_balance += quota_amount
            last_tx = add_transaction(
                db,
                user_id=user.id,
                type="quota_refund",
                amount=quota_amount,
                balance_after=account.available_credits,
                job_id=job.id,
                note=f"{note}（退回当日临时额度 {quota_amount} 点）",
            )
        else:
            last_tx = add_transaction(
                db,
                user_id=user.id,
                type="quota_refund",
                amount=0,
                balance_after=account.available_credits,
                job_id=job.id,
                note=f"{note}（临时额度 {quota_amount} 点已跨日作废）",
            )
    return last_tx


def insufficient_credits_http() -> HTTPException:
    return HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="点数不足，请先充值")
