"""add payment order paid_at index for dashboard queries

Revision ID: 0027_admin_dashboard_paid_at_index
Revises: 0026_promo_order_snapshots
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0027_admin_dashboard_paid_at_index"
down_revision = "0026_promo_order_snapshots"
branch_labels = None
depends_on = None

_INDEX_NAME = "ix_payment_orders_paid_at"


def _has_index(table: str, index: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return any(item["name"] == index for item in inspector.get_indexes(table))


def upgrade() -> None:
    if not _has_index("payment_orders", _INDEX_NAME):
        op.create_index(_INDEX_NAME, "payment_orders", ["paid_at"])


def downgrade() -> None:
    if _has_index("payment_orders", _INDEX_NAME):
        op.drop_index(_INDEX_NAME, table_name="payment_orders")
