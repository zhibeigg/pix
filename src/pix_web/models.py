"""SQLAlchemy 数据模型。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    display_name: Mapped[str] = mapped_column(String(120), default="")
    role: Mapped[str] = mapped_column(String(32), default="user")
    status: Mapped[str] = mapped_column(String(32), default="active")
    # 优惠链接绑定：注册时通过 ?promo=xxx 进入的用户永久绑定该优惠码，之后所有充值/月卡按折扣计费。
    promo_code: Mapped[str] = mapped_column(String(32), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    credit_account: Mapped["CreditAccount"] = relationship(back_populates="user", uselist=False)
    shared_works: Mapped[list["SharedWork"]] = relationship(back_populates="user", foreign_keys="SharedWork.user_id")
    shared_work_likes: Mapped[list["SharedWorkLike"]] = relationship(back_populates="user")
    characters: Mapped[list["CharacterLibraryItem"]] = relationship(back_populates="user")


class ExternalApiKey(Base):
    __tablename__ = "external_api_keys"
    __table_args__ = (UniqueConstraint("key_hash", name="uq_external_api_keys_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    key_prefix: Mapped[str] = mapped_column(String(32), default="", index=True)
    key_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    scopes: Mapped[list[Any]] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class EmailVerificationCode(Base):
    __tablename__ = "email_verification_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    purpose: Mapped[str] = mapped_column(String(32), index=True)
    request_ip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    code_hash: Mapped[str] = mapped_column(String(128))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CreditAccount(Base):
    __tablename__ = "credit_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    available_credits: Mapped[int] = mapped_column(Integer, default=0)
    reserved_credits: Mapped[int] = mapped_column(Integer, default=0)
    total_recharged: Mapped[int] = mapped_column(Integer, default=0)
    total_consumed: Mapped[int] = mapped_column(Integer, default=0)
    # 月卡会员每日临时额度：当日剩余量 + 已冻结量 + 所属业务日（YYYY-MM-DD）。
    # 临时额度当天有效、次日按业务时区刷新，仅用于生成任务且优先于永久点数消耗。
    daily_quota_balance: Mapped[int] = mapped_column(Integer, default=0)
    reserved_quota: Mapped[int] = mapped_column(Integer, default=0)
    daily_quota_date: Mapped[str] = mapped_column(String(10), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="credit_account")


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("generation_jobs.id"), nullable=True, index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PricingRule(Base):
    __tablename__ = "pricing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    price_credits: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CreditPackage(Base):
    __tablename__ = "credit_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    credits: Mapped[int] = mapped_column(Integer, default=0)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(12), default="usd")
    enabled: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PaymentOrder(Base):
    __tablename__ = "payment_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("credit_packages.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(32), default="mock", index=True)
    provider_order_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(12), default="usd")
    credits: Mapped[int] = mapped_column(Integer, default=0)
    # 订单类型：recharge=点数充值；membership=月卡会员。membership 订单 credits=0，
    # 到账时激活/续期会员而非直接充值永久点数。
    order_kind: Mapped[str] = mapped_column(String(24), default="recharge", index=True)
    membership_plan_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 下单用户绑定的优惠码（快照），用于统计各优惠链接的下单/付费金额。
    promo_code: Mapped[str] = mapped_column(String(32), default="", index=True)
    # 该订单实际享受的优惠折扣率（0~1）；未享受优惠为 1.0。仅统计/展示用。
    promo_discount_rate: Mapped[float] = mapped_column(default=1.0)
    # 未打折时的原始金额（分），用于统计优惠减免总额；无优惠时等于 amount_cents。
    original_amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), default="mock", index=True)
    provider_event_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("payment_orders.id"), nullable=True, index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    processed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MembershipPlan(Base):
    """月卡会员档位配置（可后台增删改）。"""

    __tablename__ = "membership_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    daily_quota: Mapped[int] = mapped_column(Integer, default=0)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(12), default="cny")
    duration_days: Mapped[int] = mapped_column(Integer, default=30)
    enabled: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class UserMembership(Base):
    """用户当前会员状态（每用户唯一，续期顺延 expires_at）。"""

    __tablename__ = "user_memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    plan_key: Mapped[str] = mapped_column(String(64), default="", index=True)
    daily_quota: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ReferralProfile(Base):
    __tablename__ = "referral_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReferralInvite(Base):
    __tablename__ = "referral_invites"
    __table_args__ = (UniqueConstraint("referred_user_id", name="uq_referral_invite_referred_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referrer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    referred_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class ReferralReward(Base):
    __tablename__ = "referral_rewards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referrer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    referred_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    invite_id: Mapped[int | None] = mapped_column(ForeignKey("referral_invites.id"), nullable=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("payment_orders.id"), unique=True, index=True)
    order_amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    order_credits: Mapped[int] = mapped_column(Integer, default=0)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    remaining_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(12), default="cny", index=True)
    rate_bps: Mapped[int] = mapped_column(Integer, default=1000)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReferralSettlement(Base):
    __tablename__ = "referral_settlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(12), default="cny", index=True)
    credits: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PromoLink(Base):
    """优惠链接：管理员创建的优惠码，设置折扣倍率。

    通过 ?promo=CODE 链接注册的用户永久绑定该码，之后所有充值/月卡订单按折扣计费。
    used_count / signup_count 冗余统计各链接使用量，付费统计实时按订单聚合。
    """

    __tablename__ = "promo_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    # 折扣倍率（0~1）：0.8 = 8 折付款；0 = 限免；1 = 不打折。
    discount_rate: Mapped[float] = mapped_column(default=1.0)
    enabled: Mapped[bool] = mapped_column(default=True)
    note: Mapped[str] = mapped_column(Text, default="")
    # 通过该链接注册的用户数（绑定时 +1）。
    signup_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AlipayGatewayMessage(Base):
    __tablename__ = "alipay_gateway_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notify_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    msg_method: Mapped[str] = mapped_column(String(160), index=True)
    app_id: Mapped[str] = mapped_column(String(64), index=True)
    biz_content_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    raw_payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    processed: Mapped[bool] = mapped_column(default=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class UploadEvent(Base):
    __tablename__ = "upload_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(260), default="")
    content_type: Mapped[str] = mapped_column(String(120), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class GenerationBatch(Base):
    __tablename__ = "generation_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    mode: Mapped[str] = mapped_column(String(32), default="mixed", index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    jobs: Mapped[list["GenerationJob"]] = relationship(back_populates="batch")


class AssetPackQuota(Base):
    __tablename__ = "asset_pack_quotas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    pack_limit: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class GalleryQuota(Base):
    __tablename__ = "gallery_quotas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    retained_limit: Mapped[int] = mapped_column(Integer, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AssetPack(Base):
    __tablename__ = "asset_packs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    capacity: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    items: Mapped[list["AssetPackItem"]] = relationship(back_populates="pack", cascade="all, delete-orphan")


class AssetPackItem(Base):
    __tablename__ = "asset_pack_items"
    __table_args__ = (UniqueConstraint("pack_id", "job_id", name="uq_asset_pack_item_pack_job"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    pack_id: Mapped[int] = mapped_column(ForeignKey("asset_packs.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("generation_jobs.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    pack: Mapped[AssetPack] = relationship(back_populates="items")
    job: Mapped["GenerationJob"] = relationship(back_populates="pack_items")


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (UniqueConstraint("user_id", "client_request_id", name="uq_job_user_request"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("generation_batches.id"), nullable=True, index=True)
    client_request_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    job_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    params_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    price_credits: Mapped[int] = mapped_column(Integer, default=0)
    reserved_credits: Mapped[int] = mapped_column(Integer, default=0)
    # 本次任务从会员每日临时额度冻结的点数（reserved_credits 为永久点数部分）。
    reserved_quota: Mapped[int] = mapped_column(Integer, default=0)
    # 冻结临时额度时所属的业务日（YYYY-MM-DD）；退款时据此判断是否同日退回，跨日作废。
    reserved_quota_date: Mapped[str] = mapped_column(String(10), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    user_error_message: Mapped[str] = mapped_column(Text, default="")
    error_diagnostics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    failure_type: Mapped[str] = mapped_column(String(64), default="", index=True)
    failure_source: Mapped[str] = mapped_column(String(64), default="", index=True)
    failure_code: Mapped[str] = mapped_column(String(128), default="", index=True)
    provider: Mapped[str] = mapped_column(String(32), default="", index=True)
    candidate_failure_count: Mapped[int] = mapped_column(Integer, default=0)
    pipeline_warning_count: Mapped[int] = mapped_column(Integer, default=0)
    queue_priority: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    batch: Mapped[GenerationBatch | None] = relationship(back_populates="jobs")
    pack_items: Mapped[list[AssetPackItem]] = relationship(back_populates="job")
    outputs: Mapped[list["GenerationOutput"]] = relationship(back_populates="job")
    shared_work: Mapped["SharedWork | None"] = relationship(back_populates="job", uselist=False)
    character_items: Mapped[list["CharacterLibraryItem"]] = relationship(back_populates="source_job")


class GenerationPolicyEvent(Base):
    __tablename__ = "generation_policy_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("generation_jobs.id"), nullable=True, index=True)
    job_type: Mapped[str] = mapped_column(String(32), default="", index=True)
    source: Mapped[str] = mapped_column(String(64), default="pre_create", index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    prompt_excerpt: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class GenerationOutput(Base):
    __tablename__ = "generation_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("generation_jobs.id"), unique=True, index=True)
    run_dir: Mapped[str] = mapped_column(Text, default="")
    source_path: Mapped[str] = mapped_column(Text, default="")
    pixelized_path: Mapped[str] = mapped_column(Text, default="")
    preview_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_json_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_json_path: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[GenerationJob] = relationship(back_populates="outputs")


class CharacterLibraryItem(Base):
    __tablename__ = "character_library_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source_job_id: Mapped[int | None] = mapped_column(ForeignKey("generation_jobs.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    tags_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    image_path: Mapped[str] = mapped_column(Text, default="")
    preview_path: Mapped[str] = mapped_column(Text, default="")
    parameter_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="characters")
    source_job: Mapped[GenerationJob | None] = relationship(back_populates="character_items")


class SharedWork(Base):
    __tablename__ = "shared_works"
    __table_args__ = (UniqueConstraint("job_id", name="uq_shared_works_job_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("generation_jobs.id"), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    title: Mapped[str] = mapped_column(String(160), default="")
    asset_kind: Mapped[str] = mapped_column(String(64), default="", index=True)
    preview_path: Mapped[str] = mapped_column(Text, default="")
    parameter_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    download_manifest_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    like_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    reward_credits: Mapped[int] = mapped_column(Integer, default=0)
    rewarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str] = mapped_column(String(500), default="")
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="shared_works", foreign_keys=[user_id])
    job: Mapped[GenerationJob | None] = relationship(back_populates="shared_work")
    likes: Mapped[list["SharedWorkLike"]] = relationship(back_populates="shared_work", cascade="all, delete-orphan")


class SharedWorkLike(Base):
    __tablename__ = "shared_work_likes"
    __table_args__ = (UniqueConstraint("shared_work_id", "user_id", name="uq_shared_work_likes_work_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shared_work_id: Mapped[int] = mapped_column(ForeignKey("shared_works.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    shared_work: Mapped[SharedWork] = relationship(back_populates="likes")
    user: Mapped[User] = relationship(back_populates="shared_work_likes")


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(80), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ImageProvider(Base):
    """后台可管理的上游生图供应商；DB 为真相源，运行时叠加进 AppConfig。"""

    __tablename__ = "image_providers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    enabled: Mapped[bool] = mapped_column(default=True)
    base_url: Mapped[str] = mapped_column(Text, default="")
    api_key: Mapped[str] = mapped_column(Text, default="")
    api_key_env: Mapped[str] = mapped_column(String(96), default="")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    protocols: Mapped[list[Any]] = mapped_column(JSON, default=list)
    discover_models: Mapped[bool] = mapped_column(default=False)
    models: Mapped[list[Any]] = mapped_column(JSON, default=list)
    preset_key: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
