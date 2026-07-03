"""add monthly membership and daily quota

Revision ID: 0024_membership
Revises: 0023_character_library
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0024_membership"
down_revision = "0023_character_library"
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table in inspector.get_table_names()


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return any(col["name"] == column for col in inspector.get_columns(table))


def upgrade() -> None:
    # 1. credit_accounts 新增每日临时额度列
    if not _has_column("credit_accounts", "daily_quota_balance"):
        op.add_column("credit_accounts", sa.Column("daily_quota_balance", sa.Integer(), nullable=False, server_default="0"))
    if not _has_column("credit_accounts", "reserved_quota"):
        op.add_column("credit_accounts", sa.Column("reserved_quota", sa.Integer(), nullable=False, server_default="0"))
    if not _has_column("credit_accounts", "daily_quota_date"):
        op.add_column("credit_accounts", sa.Column("daily_quota_date", sa.String(length=10), nullable=False, server_default=""))

    # 2. generation_jobs 新增本次冻结的临时额度列
    if not _has_column("generation_jobs", "reserved_quota"):
        op.add_column("generation_jobs", sa.Column("reserved_quota", sa.Integer(), nullable=False, server_default="0"))
    if not _has_column("generation_jobs", "reserved_quota_date"):
        op.add_column("generation_jobs", sa.Column("reserved_quota_date", sa.String(length=10), nullable=False, server_default=""))

    # 3. payment_orders 新增订单类型与月卡档位列
    if not _has_column("payment_orders", "order_kind"):
        op.add_column("payment_orders", sa.Column("order_kind", sa.String(length=24), nullable=False, server_default="recharge"))
        op.create_index("ix_payment_orders_order_kind", "payment_orders", ["order_kind"])
    if not _has_column("payment_orders", "membership_plan_key"):
        op.add_column("payment_orders", sa.Column("membership_plan_key", sa.String(length=64), nullable=True))

    # 4. membership_plans 档位配置表
    if not _has_table("membership_plans"):
        op.create_table(
            "membership_plans",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("key", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("daily_quota", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("amount_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(length=12), nullable=False, server_default="cny"),
            sa.Column("duration_days", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_membership_plans_key", "membership_plans", ["key"], unique=True)
        op.create_index("ix_membership_plans_sort_order", "membership_plans", ["sort_order"])

    # 5. user_memberships 用户会员状态表
    if not _has_table("user_memberships"):
        op.create_table(
            "user_memberships",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("plan_key", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("daily_quota", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_user_memberships_user_id", "user_memberships", ["user_id"], unique=True)
        op.create_index("ix_user_memberships_plan_key", "user_memberships", ["plan_key"])
        op.create_index("ix_user_memberships_status", "user_memberships", ["status"])
        op.create_index("ix_user_memberships_expires_at", "user_memberships", ["expires_at"])


def downgrade() -> None:
    if _has_table("user_memberships"):
        op.drop_index("ix_user_memberships_expires_at", table_name="user_memberships")
        op.drop_index("ix_user_memberships_status", table_name="user_memberships")
        op.drop_index("ix_user_memberships_plan_key", table_name="user_memberships")
        op.drop_index("ix_user_memberships_user_id", table_name="user_memberships")
        op.drop_table("user_memberships")

    if _has_table("membership_plans"):
        op.drop_index("ix_membership_plans_sort_order", table_name="membership_plans")
        op.drop_index("ix_membership_plans_key", table_name="membership_plans")
        op.drop_table("membership_plans")

    if _has_column("payment_orders", "membership_plan_key"):
        op.drop_column("payment_orders", "membership_plan_key")
    if _has_column("payment_orders", "order_kind"):
        op.drop_index("ix_payment_orders_order_kind", table_name="payment_orders")
        op.drop_column("payment_orders", "order_kind")

    if _has_column("generation_jobs", "reserved_quota_date"):
        op.drop_column("generation_jobs", "reserved_quota_date")
    if _has_column("generation_jobs", "reserved_quota"):
        op.drop_column("generation_jobs", "reserved_quota")

    if _has_column("credit_accounts", "daily_quota_date"):
        op.drop_column("credit_accounts", "daily_quota_date")
    if _has_column("credit_accounts", "reserved_quota"):
        op.drop_column("credit_accounts", "reserved_quota")
    if _has_column("credit_accounts", "daily_quota_balance"):
        op.drop_column("credit_accounts", "daily_quota_balance")
