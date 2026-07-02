"""add review fields to shared_works

Revision ID: 0022_shared_work_review
Revises: 0021_shared_works
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0022_shared_work_review"
down_revision = "0021_shared_works"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col["name"] == column for col in inspector.get_columns(table))


def upgrade() -> None:
    # 幂等：老部署若已手工补列则跳过。SQLite 用 batch 模式安全加列。
    # 注意：SQLite batch 加带 FK 的列需要显式命名约束，否则报 "Constraint must have a name"。
    with op.batch_alter_table("shared_works") as batch:
        if not _has_column("shared_works", "reviewed_at"):
            batch.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
        if not _has_column("shared_works", "review_note"):
            batch.add_column(sa.Column("review_note", sa.String(length=500), nullable=False, server_default=""))
        if not _has_column("shared_works", "reviewed_by_user_id"):
            batch.add_column(
                sa.Column(
                    "reviewed_by_user_id",
                    sa.Integer(),
                    sa.ForeignKey("users.id", name="fk_shared_works_reviewed_by_user_id"),
                    nullable=True,
                )
            )


def downgrade() -> None:
    with op.batch_alter_table("shared_works") as batch:
        if _has_column("shared_works", "reviewed_by_user_id"):
            batch.drop_column("reviewed_by_user_id")
        if _has_column("shared_works", "review_note"):
            batch.drop_column("review_note")
        if _has_column("shared_works", "reviewed_at"):
            batch.drop_column("reviewed_at")
