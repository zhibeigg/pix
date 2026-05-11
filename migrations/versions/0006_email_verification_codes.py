"""add email verification codes"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_email_verification_codes"
down_revision = "0005_china_payment_providers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_verification_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_email_verification_codes_email", "email_verification_codes", ["email"])
    op.create_index("ix_email_verification_codes_purpose", "email_verification_codes", ["purpose"])
    op.create_index("ix_email_verification_codes_expires_at", "email_verification_codes", ["expires_at"])
    op.create_index("ix_email_verification_codes_consumed_at", "email_verification_codes", ["consumed_at"])


def downgrade() -> None:
    op.drop_index("ix_email_verification_codes_consumed_at", table_name="email_verification_codes")
    op.drop_index("ix_email_verification_codes_expires_at", table_name="email_verification_codes")
    op.drop_index("ix_email_verification_codes_purpose", table_name="email_verification_codes")
    op.drop_index("ix_email_verification_codes_email", table_name="email_verification_codes")
    op.drop_table("email_verification_codes")
