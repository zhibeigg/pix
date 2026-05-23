"""add referral rewards

Revision ID: 0010_referrals
Revises: 0009_asset_pack_quotas
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010_referrals"
down_revision = "0009_asset_pack_quotas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "referral_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_referral_profiles_user_id", "referral_profiles", ["user_id"], unique=True)
    op.create_index("ix_referral_profiles_code", "referral_profiles", ["code"], unique=True)

    op.create_table(
        "referral_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referrer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("referred_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("referred_user_id", name="uq_referral_invite_referred_user"),
    )
    op.create_index("ix_referral_invites_referrer_id", "referral_invites", ["referrer_id"])
    op.create_index("ix_referral_invites_referred_user_id", "referral_invites", ["referred_user_id"])
    op.create_index("ix_referral_invites_code", "referral_invites", ["code"])
    op.create_index("ix_referral_invites_created_at", "referral_invites", ["created_at"])

    op.create_table(
        "referral_rewards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referrer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("referred_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("invite_id", sa.Integer(), sa.ForeignKey("referral_invites.id"), nullable=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("payment_orders.id"), nullable=False),
        sa.Column("order_amount_cents", sa.Integer(), nullable=False),
        sa.Column("order_credits", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("remaining_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=12), nullable=False),
        sa.Column("rate_bps", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_referral_rewards_referrer_id", "referral_rewards", ["referrer_id"])
    op.create_index("ix_referral_rewards_referred_user_id", "referral_rewards", ["referred_user_id"])
    op.create_index("ix_referral_rewards_invite_id", "referral_rewards", ["invite_id"])
    op.create_index("ix_referral_rewards_order_id", "referral_rewards", ["order_id"], unique=True)
    op.create_index("ix_referral_rewards_currency", "referral_rewards", ["currency"])
    op.create_index("ix_referral_rewards_status", "referral_rewards", ["status"])
    op.create_index("ix_referral_rewards_available_at", "referral_rewards", ["available_at"])
    op.create_index("ix_referral_rewards_created_at", "referral_rewards", ["created_at"])

    op.create_table(
        "referral_settlements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=12), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_referral_settlements_user_id", "referral_settlements", ["user_id"])
    op.create_index("ix_referral_settlements_type", "referral_settlements", ["type"])
    op.create_index("ix_referral_settlements_currency", "referral_settlements", ["currency"])
    op.create_index("ix_referral_settlements_status", "referral_settlements", ["status"])
    op.create_index("ix_referral_settlements_created_at", "referral_settlements", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_referral_settlements_created_at", table_name="referral_settlements")
    op.drop_index("ix_referral_settlements_status", table_name="referral_settlements")
    op.drop_index("ix_referral_settlements_currency", table_name="referral_settlements")
    op.drop_index("ix_referral_settlements_type", table_name="referral_settlements")
    op.drop_index("ix_referral_settlements_user_id", table_name="referral_settlements")
    op.drop_table("referral_settlements")

    op.drop_index("ix_referral_rewards_created_at", table_name="referral_rewards")
    op.drop_index("ix_referral_rewards_available_at", table_name="referral_rewards")
    op.drop_index("ix_referral_rewards_status", table_name="referral_rewards")
    op.drop_index("ix_referral_rewards_currency", table_name="referral_rewards")
    op.drop_index("ix_referral_rewards_order_id", table_name="referral_rewards")
    op.drop_index("ix_referral_rewards_invite_id", table_name="referral_rewards")
    op.drop_index("ix_referral_rewards_referred_user_id", table_name="referral_rewards")
    op.drop_index("ix_referral_rewards_referrer_id", table_name="referral_rewards")
    op.drop_table("referral_rewards")

    op.drop_index("ix_referral_invites_created_at", table_name="referral_invites")
    op.drop_index("ix_referral_invites_code", table_name="referral_invites")
    op.drop_index("ix_referral_invites_referred_user_id", table_name="referral_invites")
    op.drop_index("ix_referral_invites_referrer_id", table_name="referral_invites")
    op.drop_table("referral_invites")

    op.drop_index("ix_referral_profiles_code", table_name="referral_profiles")
    op.drop_index("ix_referral_profiles_user_id", table_name="referral_profiles")
    op.drop_table("referral_profiles")
