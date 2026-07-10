"""add shared works

Revision ID: 0021_shared_works
Revises: 0020_external_api_keys
"""

from __future__ import annotations

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0021_shared_works"
down_revision = "0020_external_api_keys"
branch_labels = None
depends_on = None

_SHARE_DEFAULTS = {
    "share.reward_enabled": "true",
    "share.reward_credits": "1",
    "share.daily_reward_limit": "0",
}


def upgrade() -> None:
    op.create_table(
        "shared_works",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("generation_jobs.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("title", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("asset_kind", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("preview_path", sa.Text(), nullable=False, server_default=""),
        sa.Column("parameter_snapshot_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("download_manifest_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("like_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("download_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reward_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("job_id", name="uq_shared_works_job_id"),
    )
    op.create_index("ix_shared_works_job_id", "shared_works", ["job_id"])
    op.create_index("ix_shared_works_user_id", "shared_works", ["user_id"])
    op.create_index("ix_shared_works_status", "shared_works", ["status"])
    op.create_index("ix_shared_works_asset_kind", "shared_works", ["asset_kind"])
    op.create_index("ix_shared_works_like_count", "shared_works", ["like_count"])
    op.create_index("ix_shared_works_published_at", "shared_works", ["published_at"])
    op.create_index("ix_shared_works_created_at", "shared_works", ["created_at"])

    op.create_table(
        "shared_work_likes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shared_work_id", sa.Integer(), sa.ForeignKey("shared_works.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("shared_work_id", "user_id", name="uq_shared_work_likes_work_user"),
    )
    op.create_index("ix_shared_work_likes_shared_work_id", "shared_work_likes", ["shared_work_id"])
    op.create_index("ix_shared_work_likes_user_id", "shared_work_likes", ["user_id"])
    op.create_index("ix_shared_work_likes_created_at", "shared_work_likes", ["created_at"])

    conn = op.get_bind()
    now = datetime.now(timezone.utc)
    insert_default = sa.text(
        "INSERT INTO system_settings (key, value, updated_at) "
        "SELECT :insert_key, :value, :updated_at "
        "WHERE NOT EXISTS (SELECT 1 FROM system_settings WHERE key = :lookup_key)"
    ).bindparams(
        sa.bindparam("insert_key", type_=sa.String(length=96)),
        sa.bindparam("lookup_key", type_=sa.String(length=96)),
        sa.bindparam("value", type_=sa.Text()),
        sa.bindparam("updated_at", type_=sa.DateTime(timezone=True)),
    )
    for key, value in _SHARE_DEFAULTS.items():
        conn.execute(
            insert_default,
            {"insert_key": key, "lookup_key": key, "value": value, "updated_at": now},
        )


def downgrade() -> None:
    op.execute("DELETE FROM system_settings WHERE key IN ('share.reward_enabled', 'share.reward_credits', 'share.daily_reward_limit')")

    op.drop_index("ix_shared_work_likes_created_at", table_name="shared_work_likes")
    op.drop_index("ix_shared_work_likes_user_id", table_name="shared_work_likes")
    op.drop_index("ix_shared_work_likes_shared_work_id", table_name="shared_work_likes")
    op.drop_table("shared_work_likes")

    op.drop_index("ix_shared_works_created_at", table_name="shared_works")
    op.drop_index("ix_shared_works_published_at", table_name="shared_works")
    op.drop_index("ix_shared_works_like_count", table_name="shared_works")
    op.drop_index("ix_shared_works_asset_kind", table_name="shared_works")
    op.drop_index("ix_shared_works_status", table_name="shared_works")
    op.drop_index("ix_shared_works_user_id", table_name="shared_works")
    op.drop_index("ix_shared_works_job_id", table_name="shared_works")
    op.drop_table("shared_works")
