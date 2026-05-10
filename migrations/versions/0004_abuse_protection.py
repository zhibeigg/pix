"""add abuse protection controls"""

from __future__ import annotations

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0004_abuse_protection"
down_revision = "0003_billing"
branch_labels = None
depends_on = None

_DEFAULTS = {
    "blocked_prompt_terms": "",
    "max_uploads_per_user_per_day": "50",
}


def upgrade() -> None:
    op.create_table(
        "upload_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(length=260), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_upload_events_user_id", "upload_events", ["user_id"])
    op.create_index("ix_upload_events_created_at", "upload_events", ["created_at"])

    table = sa.table(
        "system_settings",
        sa.column("key", sa.String(length=96)),
        sa.column("value", sa.Text()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(table, [{"key": key, "value": value, "updated_at": now} for key, value in _DEFAULTS.items()])


def downgrade() -> None:
    op.execute("DELETE FROM system_settings WHERE key IN ('blocked_prompt_terms', 'max_uploads_per_user_per_day')")
    op.drop_index("ix_upload_events_created_at", table_name="upload_events")
    op.drop_index("ix_upload_events_user_id", table_name="upload_events")
    op.drop_table("upload_events")
