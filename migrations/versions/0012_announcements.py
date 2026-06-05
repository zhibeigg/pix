"""add announcements table

Revision ID: 0012_announcements
Revises: 0011_job_failure_observability
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0012_announcements"
down_revision = "0011_job_failure_observability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "announcements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_announcements_sort_order", "announcements", ["sort_order"])
    op.create_index("ix_announcements_published_at", "announcements", ["published_at"])
    op.create_index("ix_announcements_created_at", "announcements", ["created_at"])

    # Migrate existing announcement data from system_settings to announcements table
    conn = op.get_bind()
    settings = conn.execute(
        sa.text("SELECT key, value FROM system_settings WHERE key IN (:k1, :k2, :k3)"),
        {"k1": "site.announcement.title", "k2": "site.announcement.body", "k3": "site.announcement.enabled"},
    ).fetchall()
    settings_map = {row.key: row.value for row in settings}
    title = (settings_map.get("site.announcement.title", "") or "").strip()
    body = (settings_map.get("site.announcement.body", "") or "").strip()
    enabled_str = (settings_map.get("site.announcement.enabled", "false") or "false").strip().lower()
    if title or body:
        now = conn.execute(sa.func.now()).scalar()
        conn.execute(
            sa.text(
                "INSERT INTO announcements (title, body, enabled, sort_order, published_at, created_at, updated_at)"
                " VALUES (:title, :body, :enabled, 0, :now, :now, :now)"
            ),
            {"title": title, "body": body, "enabled": enabled_str == "true", "now": now},
        )


def downgrade() -> None:
    op.drop_index("ix_announcements_created_at", table_name="announcements")
    op.drop_index("ix_announcements_published_at", table_name="announcements")
    op.drop_index("ix_announcements_sort_order", table_name="announcements")
    op.drop_table("announcements")
