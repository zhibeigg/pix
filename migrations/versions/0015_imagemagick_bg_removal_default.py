"""switch default background removal algorithm to pixel_bg

Revision ID: 0015_imagemagick_bg_removal_default
Revises: 0014_disable_multi_candidate_defaults
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0015_imagemagick_bg_removal_default"
down_revision = "0014_disable_multi_candidate_defaults"
branch_labels = None
depends_on = None

NEW_ALGORITHM = "pixel_bg"


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE system_settings "
            "SET value = :new_value "
            "WHERE key = 'pix.asset.bg_removal_algorithm' "
            "AND trim(value) = 'color_to_alpha'"
        ),
        {"new_value": NEW_ALGORITHM},
    )


def downgrade() -> None:
    pass
