"""SQLAlchemy 数据模型。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    credit_account: Mapped["CreditAccount"] = relationship(back_populates="user", uselist=False)


class EmailVerificationCode(Base):
    __tablename__ = "email_verification_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    purpose: Mapped[str] = mapped_column(String(32), index=True)
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
    error_message: Mapped[str] = mapped_column(Text, default="")
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
