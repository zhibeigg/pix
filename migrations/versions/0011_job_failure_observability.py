"""add generation job failure observability

Revision ID: 0011_job_failure_observability
Revises: 0010_referrals
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0011_job_failure_observability"
down_revision = "0010_referrals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generation_jobs", sa.Column("failure_type", sa.String(length=64), nullable=False, server_default=""))
    op.add_column("generation_jobs", sa.Column("failure_source", sa.String(length=64), nullable=False, server_default=""))
    op.add_column("generation_jobs", sa.Column("failure_code", sa.String(length=128), nullable=False, server_default=""))
    op.add_column("generation_jobs", sa.Column("candidate_failure_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("generation_jobs", sa.Column("pipeline_warning_count", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_generation_jobs_failure_type", "generation_jobs", ["failure_type"])
    op.create_index("ix_generation_jobs_failure_source", "generation_jobs", ["failure_source"])
    op.create_index("ix_generation_jobs_failure_code", "generation_jobs", ["failure_code"])

    op.create_table(
        "generation_policy_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("generation_jobs.id"), nullable=True),
        sa.Column("job_type", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="pre_create"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("prompt_excerpt", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_generation_policy_events_user_id", "generation_policy_events", ["user_id"])
    op.create_index("ix_generation_policy_events_job_id", "generation_policy_events", ["job_id"])
    op.create_index("ix_generation_policy_events_job_type", "generation_policy_events", ["job_type"])
    op.create_index("ix_generation_policy_events_source", "generation_policy_events", ["source"])
    op.create_index("ix_generation_policy_events_created_at", "generation_policy_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_generation_policy_events_created_at", table_name="generation_policy_events")
    op.drop_index("ix_generation_policy_events_source", table_name="generation_policy_events")
    op.drop_index("ix_generation_policy_events_job_type", table_name="generation_policy_events")
    op.drop_index("ix_generation_policy_events_job_id", table_name="generation_policy_events")
    op.drop_index("ix_generation_policy_events_user_id", table_name="generation_policy_events")
    op.drop_table("generation_policy_events")

    op.drop_index("ix_generation_jobs_failure_code", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_failure_source", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_failure_type", table_name="generation_jobs")
    op.drop_column("generation_jobs", "pipeline_warning_count")
    op.drop_column("generation_jobs", "candidate_failure_count")
    op.drop_column("generation_jobs", "failure_code")
    op.drop_column("generation_jobs", "failure_source")
    op.drop_column("generation_jobs", "failure_type")
