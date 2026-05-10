"""add billing orders"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_billing"
down_revision = "0002_system_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_packages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=12), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_credit_packages_key", "credit_packages", ["key"], unique=True)
    op.create_index("ix_credit_packages_sort_order", "credit_packages", ["sort_order"])

    op.create_table(
        "payment_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("credit_packages.id"), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_order_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=12), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_payment_orders_user_id", "payment_orders", ["user_id"])
    op.create_index("ix_payment_orders_package_id", "payment_orders", ["package_id"])
    op.create_index("ix_payment_orders_provider", "payment_orders", ["provider"])
    op.create_index("ix_payment_orders_provider_order_id", "payment_orders", ["provider_order_id"])
    op.create_index("ix_payment_orders_status", "payment_orders", ["status"])
    op.create_index("ix_payment_orders_created_at", "payment_orders", ["created_at"])

    op.create_table(
        "payment_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_event_id", sa.String(length=160), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("payment_orders.id"), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_payment_events_provider", "payment_events", ["provider"])
    op.create_index("ix_payment_events_provider_event_id", "payment_events", ["provider_event_id"], unique=True)
    op.create_index("ix_payment_events_order_id", "payment_events", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_events_order_id", table_name="payment_events")
    op.drop_index("ix_payment_events_provider_event_id", table_name="payment_events")
    op.drop_index("ix_payment_events_provider", table_name="payment_events")
    op.drop_table("payment_events")
    op.drop_index("ix_payment_orders_created_at", table_name="payment_orders")
    op.drop_index("ix_payment_orders_status", table_name="payment_orders")
    op.drop_index("ix_payment_orders_provider_order_id", table_name="payment_orders")
    op.drop_index("ix_payment_orders_provider", table_name="payment_orders")
    op.drop_index("ix_payment_orders_package_id", table_name="payment_orders")
    op.drop_index("ix_payment_orders_user_id", table_name="payment_orders")
    op.drop_table("payment_orders")
    op.drop_index("ix_credit_packages_sort_order", table_name="credit_packages")
    op.drop_index("ix_credit_packages_key", table_name="credit_packages")
    op.drop_table("credit_packages")
