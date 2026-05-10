"""initial web schema"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_web_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "credit_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("available_credits", sa.Integer(), nullable=False),
        sa.Column("reserved_credits", sa.Integer(), nullable=False),
        sa.Column("total_recharged", sa.Integer(), nullable=False),
        sa.Column("total_consumed", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_credit_accounts_user_id", "credit_accounts", ["user_id"], unique=True)

    op.create_table(
        "pricing_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("price_credits", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pricing_rules_key", "pricing_rules", ["key"], unique=True)

    op.create_table(
        "generation_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_generation_batches_user_id", "generation_batches", ["user_id"])
    op.create_index("ix_generation_batches_mode", "generation_batches", ["mode"])
    op.create_index("ix_generation_batches_status", "generation_batches", ["status"])
    op.create_index("ix_generation_batches_created_at", "generation_batches", ["created_at"])

    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("generation_batches.id"), nullable=True),
        sa.Column("client_request_id", sa.String(length=128), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("input_image_path", sa.Text(), nullable=True),
        sa.Column("params_json", sa.JSON(), nullable=False),
        sa.Column("price_credits", sa.Integer(), nullable=False),
        sa.Column("reserved_credits", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("queue_priority", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "client_request_id", name="uq_job_user_request"),
    )
    op.create_index("ix_generation_jobs_user_id", "generation_jobs", ["user_id"])
    op.create_index("ix_generation_jobs_batch_id", "generation_jobs", ["batch_id"])
    op.create_index("ix_generation_jobs_client_request_id", "generation_jobs", ["client_request_id"])
    op.create_index("ix_generation_jobs_job_type", "generation_jobs", ["job_type"])
    op.create_index("ix_generation_jobs_status", "generation_jobs", ["status"])
    op.create_index("ix_generation_jobs_queue_priority", "generation_jobs", ["queue_priority"])
    op.create_index("ix_generation_jobs_created_at", "generation_jobs", ["created_at"])

    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("generation_jobs.id"), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_credit_transactions_user_id", "credit_transactions", ["user_id"])
    op.create_index("ix_credit_transactions_type", "credit_transactions", ["type"])
    op.create_index("ix_credit_transactions_job_id", "credit_transactions", ["job_id"])

    op.create_table(
        "generation_outputs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("generation_jobs.id"), nullable=False),
        sa.Column("run_dir", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("pixelized_path", sa.Text(), nullable=False),
        sa.Column("preview_path", sa.Text(), nullable=True),
        sa.Column("analysis_json_path", sa.Text(), nullable=True),
        sa.Column("meta_json_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_generation_outputs_job_id", "generation_outputs", ["job_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_generation_outputs_job_id", table_name="generation_outputs")
    op.drop_table("generation_outputs")
    op.drop_index("ix_credit_transactions_job_id", table_name="credit_transactions")
    op.drop_index("ix_credit_transactions_type", table_name="credit_transactions")
    op.drop_index("ix_credit_transactions_user_id", table_name="credit_transactions")
    op.drop_table("credit_transactions")
    op.drop_index("ix_generation_jobs_created_at", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_queue_priority", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_status", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_job_type", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_client_request_id", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_batch_id", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_user_id", table_name="generation_jobs")
    op.drop_table("generation_jobs")
    op.drop_index("ix_generation_batches_created_at", table_name="generation_batches")
    op.drop_index("ix_generation_batches_status", table_name="generation_batches")
    op.drop_index("ix_generation_batches_mode", table_name="generation_batches")
    op.drop_index("ix_generation_batches_user_id", table_name="generation_batches")
    op.drop_table("generation_batches")
    op.drop_index("ix_pricing_rules_key", table_name="pricing_rules")
    op.drop_table("pricing_rules")
    op.drop_index("ix_credit_accounts_user_id", table_name="credit_accounts")
    op.drop_table("credit_accounts")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
