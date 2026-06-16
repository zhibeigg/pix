"""add external api keys

Revision ID: 0020_external_api_keys
Revises: 0019_job_error_diagnostics
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0020_external_api_keys"
down_revision = "0019_job_error_diagnostics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("key_prefix", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("key_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("scopes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("key_hash", name="uq_external_api_keys_hash"),
    )
    op.create_index("ix_external_api_keys_user_id", "external_api_keys", ["user_id"])
    op.create_index("ix_external_api_keys_key_prefix", "external_api_keys", ["key_prefix"])
    op.create_index("ix_external_api_keys_key_hash", "external_api_keys", ["key_hash"])
    op.create_index("ix_external_api_keys_revoked_at", "external_api_keys", ["revoked_at"])
    op.create_index("ix_external_api_keys_created_at", "external_api_keys", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_external_api_keys_created_at", table_name="external_api_keys")
    op.drop_index("ix_external_api_keys_revoked_at", table_name="external_api_keys")
    op.drop_index("ix_external_api_keys_key_hash", table_name="external_api_keys")
    op.drop_index("ix_external_api_keys_key_prefix", table_name="external_api_keys")
    op.drop_index("ix_external_api_keys_user_id", table_name="external_api_keys")
    op.drop_table("external_api_keys")
