"""add alipay gateway messages"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_alipay_gateway_messages"
down_revision = "0006_email_verification_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alipay_gateway_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("notify_id", sa.String(length=160), nullable=False),
        sa.Column("msg_method", sa.String(length=160), nullable=False),
        sa.Column("app_id", sa.String(length=64), nullable=False),
        sa.Column("biz_content_json", sa.JSON(), nullable=False),
        sa.Column("raw_payload_json", sa.JSON(), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_alipay_gateway_messages_notify_id", "alipay_gateway_messages", ["notify_id"], unique=True)
    op.create_index("ix_alipay_gateway_messages_msg_method", "alipay_gateway_messages", ["msg_method"])
    op.create_index("ix_alipay_gateway_messages_app_id", "alipay_gateway_messages", ["app_id"])
    op.create_index("ix_alipay_gateway_messages_received_at", "alipay_gateway_messages", ["received_at"])


def downgrade() -> None:
    op.drop_index("ix_alipay_gateway_messages_received_at", table_name="alipay_gateway_messages")
    op.drop_index("ix_alipay_gateway_messages_app_id", table_name="alipay_gateway_messages")
    op.drop_index("ix_alipay_gateway_messages_msg_method", table_name="alipay_gateway_messages")
    op.drop_index("ix_alipay_gateway_messages_notify_id", table_name="alipay_gateway_messages")
    op.drop_table("alipay_gateway_messages")
