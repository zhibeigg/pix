"""add gallery quota table

Revision ID: 0013_gallery_quotas
Revises: 0012_announcements
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0013_gallery_quotas"
down_revision = "0012_announcements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gallery_quotas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("retained_limit", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_gallery_quotas_user_id"),
    )
    op.create_index("ix_gallery_quotas_user_id", "gallery_quotas", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_gallery_quotas_user_id", table_name="gallery_quotas")
    op.drop_table("gallery_quotas")
