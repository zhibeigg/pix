"""add promo links (discount registration links)

Revision ID: 0025_promo_links
Revises: 0024_membership
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0025_promo_links"
down_revision = "0024_membership"
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
    # 1. promo_links 优惠链接配置表
    if not _has_table("promo_links"):
        op.create_table(
            "promo_links",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("discount_rate", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("note", sa.Text(), nullable=False, server_default=""),
            sa.Column("signup_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_promo_links_code", "promo_links", ["code"], unique=True)
        op.create_index("ix_promo_links_created_at", "promo_links", ["created_at"])

    # 2. users 新增绑定的优惠码
    if not _has_column("users", "promo_code"):
        op.add_column("users", sa.Column("promo_code", sa.String(length=32), nullable=False, server_default=""))
        op.create_index("ix_users_promo_code", "users", ["promo_code"])

    # 3. payment_orders 新增下单时的优惠码（用于统计与审计）
    if not _has_column("payment_orders", "promo_code"):
        op.add_column("payment_orders", sa.Column("promo_code", sa.String(length=32), nullable=False, server_default=""))
        op.create_index("ix_payment_orders_promo_code", "payment_orders", ["promo_code"])


def downgrade() -> None:
    if _has_column("payment_orders", "promo_code"):
        op.drop_index("ix_payment_orders_promo_code", table_name="payment_orders")
        op.drop_column("payment_orders", "promo_code")

    if _has_column("users", "promo_code"):
        op.drop_index("ix_users_promo_code", table_name="users")
        op.drop_column("users", "promo_code")

    if _has_table("promo_links"):
        op.drop_index("ix_promo_links_created_at", table_name="promo_links")
        op.drop_index("ix_promo_links_code", table_name="promo_links")
        op.drop_table("promo_links")
