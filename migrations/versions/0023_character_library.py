"""add character library

Revision ID: 0023_character_library
Revises: 0022_shared_work_review
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0023_character_library"
down_revision = "0022_shared_work_review"
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table in inspector.get_table_names()


def upgrade() -> None:
    if _has_table("character_library_items"):
        return
    op.create_table(
        "character_library_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_job_id", sa.Integer(), sa.ForeignKey("generation_jobs.id"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("name", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("tags_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("image_path", sa.Text(), nullable=False, server_default=""),
        sa.Column("preview_path", sa.Text(), nullable=False, server_default=""),
        sa.Column("parameter_snapshot_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_character_library_items_user_id", "character_library_items", ["user_id"])
    op.create_index("ix_character_library_items_source_job_id", "character_library_items", ["source_job_id"])
    op.create_index("ix_character_library_items_status", "character_library_items", ["status"])
    op.create_index("ix_character_library_items_created_at", "character_library_items", ["created_at"])


def downgrade() -> None:
    if not _has_table("character_library_items"):
        return
    op.drop_index("ix_character_library_items_created_at", table_name="character_library_items")
    op.drop_index("ix_character_library_items_status", table_name="character_library_items")
    op.drop_index("ix_character_library_items_source_job_id", table_name="character_library_items")
    op.drop_index("ix_character_library_items_user_id", table_name="character_library_items")
    op.drop_table("character_library_items")
