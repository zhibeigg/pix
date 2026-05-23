"""add user asset packs

Revision ID: 0008_asset_packs
Revises: 0007_alipay_gateway_messages
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_asset_packs"
down_revision = "0007_alipay_gateway_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_packs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_asset_packs_user_id", "asset_packs", ["user_id"])
    op.create_index("ix_asset_packs_status", "asset_packs", ["status"])
    op.create_index("ix_asset_packs_created_at", "asset_packs", ["created_at"])

    op.create_table(
        "asset_pack_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("pack_id", sa.Integer(), sa.ForeignKey("asset_packs.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("generation_jobs.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("pack_id", "job_id", name="uq_asset_pack_item_pack_job"),
    )
    op.create_index("ix_asset_pack_items_user_id", "asset_pack_items", ["user_id"])
    op.create_index("ix_asset_pack_items_pack_id", "asset_pack_items", ["pack_id"])
    op.create_index("ix_asset_pack_items_job_id", "asset_pack_items", ["job_id"])
    op.create_index("ix_asset_pack_items_position", "asset_pack_items", ["position"])
    op.create_index("ix_asset_pack_items_created_at", "asset_pack_items", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_asset_pack_items_created_at", table_name="asset_pack_items")
    op.drop_index("ix_asset_pack_items_position", table_name="asset_pack_items")
    op.drop_index("ix_asset_pack_items_job_id", table_name="asset_pack_items")
    op.drop_index("ix_asset_pack_items_pack_id", table_name="asset_pack_items")
    op.drop_index("ix_asset_pack_items_user_id", table_name="asset_pack_items")
    op.drop_table("asset_pack_items")
    op.drop_index("ix_asset_packs_created_at", table_name="asset_packs")
    op.drop_index("ix_asset_packs_status", table_name="asset_packs")
    op.drop_index("ix_asset_packs_user_id", table_name="asset_packs")
    op.drop_table("asset_packs")
