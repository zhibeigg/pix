"""add provider column to generation_jobs

Revision ID: 0016_job_provider
Revises: 0015_imagemagick_bg_removal_default
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0016_job_provider"
down_revision = "0015_imagemagick_bg_removal_default"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_jobs",
        sa.Column("provider", sa.String(length=32), nullable=False, server_default=""),
    )
    op.create_index("ix_generation_jobs_provider", "generation_jobs", ["provider"])


def downgrade() -> None:
    op.drop_index("ix_generation_jobs_provider", table_name="generation_jobs")
    op.drop_column("generation_jobs", "provider")
