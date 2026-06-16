"""add job user error and diagnostics

Revision ID: 0019_job_error_diagnostics
Revises: 0018_email_code_request_ip
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0019_job_error_diagnostics"
down_revision = "0018_email_code_request_ip"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_jobs",
        sa.Column("user_error_message", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("error_diagnostics_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("generation_jobs", "error_diagnostics_json")
    op.drop_column("generation_jobs", "user_error_message")
