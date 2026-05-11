"""prepare china payment providers"""

from __future__ import annotations

from alembic import op

revision = "0005_china_payment_providers"
down_revision = "0004_abuse_protection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE credit_packages SET currency = 'cny' WHERE key IN ('starter', 'studio', 'pro')")


def downgrade() -> None:
    op.execute("UPDATE credit_packages SET currency = 'usd' WHERE key IN ('starter', 'studio', 'pro')")
