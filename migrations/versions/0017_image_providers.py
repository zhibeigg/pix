"""create image_providers table

Revision ID: 0017_image_providers
Revises: 0016_job_provider
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0017_image_providers"
down_revision = "0016_job_provider"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_providers",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("display_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("base_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("api_key", sa.Text(), nullable=False, server_default=""),
        sa.Column("api_key_env", sa.String(length=96), nullable=False, server_default=""),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("protocols", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("discover_models", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("models", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("preset_key", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("image_providers")
