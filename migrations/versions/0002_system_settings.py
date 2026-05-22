"""add operational system settings"""

from __future__ import annotations

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0002_system_settings"
down_revision = "0001_web_schema"
branch_labels = None
depends_on = None

_DEFAULTS = {
    "generation_enabled": "true",
    "max_pending_jobs_per_user": "0",
    "daily_job_limit_per_user": "50",
}


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=96), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"], unique=True)

    table = sa.table(
        "system_settings",
        sa.column("key", sa.String(length=96)),
        sa.column("value", sa.Text()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(table, [{"key": key, "value": value, "updated_at": now} for key, value in _DEFAULTS.items()])


def downgrade() -> None:
    op.drop_index("ix_system_settings_key", table_name="system_settings")
    op.drop_table("system_settings")
