"""disable multi-candidate image defaults

Revision ID: 0014_disable_multi_candidate_defaults
Revises: 0013_gallery_quotas
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0014_disable_multi_candidate_defaults"
down_revision = "0013_gallery_quotas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE system_settings "
            "SET value = 'false' "
            "WHERE key = 'pix.image_gen.contact_sheet_enabled' "
            "AND lower(trim(value)) IN ('1', 'true', 'yes', 'on', 'enabled')"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE system_settings "
            "SET value = '1' "
            "WHERE key = 'pix.image_gen.n_sample_count' "
            "AND trim(value) IN ('4', '5', '6', '7', '8', '9')"
        )
    )


def downgrade() -> None:
    pass
