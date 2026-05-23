"""add asset pack quotas

Revision ID: 0009_asset_pack_quotas
Revises: 0008_asset_packs
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_asset_pack_quotas"
down_revision = "0008_asset_packs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_pack_quotas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("pack_limit", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_asset_pack_quotas_user_id", "asset_pack_quotas", ["user_id"], unique=True)
    op.execute("UPDATE asset_packs SET capacity = 100 WHERE capacity < 100")


def downgrade() -> None:
    op.drop_index("ix_asset_pack_quotas_user_id", table_name="asset_pack_quotas")
    op.drop_table("asset_pack_quotas")
