"""add missing promo order snapshot columns

Revision ID: 0026_promo_order_snapshots
Revises: 0025_promo_links
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0026_promo_order_snapshots"
down_revision = "0025_promo_links"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return any(item["name"] == column for item in inspector.get_columns(table))


def upgrade() -> None:
    if not _has_column("payment_orders", "promo_discount_rate"):
        op.add_column(
            "payment_orders",
            sa.Column(
                "promo_discount_rate",
                sa.Float(),
                nullable=False,
                server_default="1.0",
            ),
        )

    if not _has_column("payment_orders", "original_amount_cents"):
        op.add_column(
            "payment_orders",
            sa.Column(
                "original_amount_cents",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )
        op.execute(
            sa.text(
                "UPDATE payment_orders "
                "SET original_amount_cents = amount_cents"
            )
        )


def downgrade() -> None:
    if _has_column("payment_orders", "original_amount_cents"):
        op.drop_column("payment_orders", "original_amount_cents")
    if _has_column("payment_orders", "promo_discount_rate"):
        op.drop_column("payment_orders", "promo_discount_rate")
