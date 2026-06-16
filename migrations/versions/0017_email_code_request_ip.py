"""add request ip to email verification codes

Revision ID: 0017_email_code_request_ip
Revises: 0016_job_provider
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0017_email_code_request_ip"
down_revision = "0016_job_provider"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_verification_codes",
        sa.Column("request_ip", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_email_verification_codes_request_ip",
        "email_verification_codes",
        ["request_ip"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_verification_codes_request_ip", table_name="email_verification_codes")
    op.drop_column("email_verification_codes", "request_ip")
