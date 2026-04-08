"""Add accounting agent infrastructure tables.

Creates agent_run_steps, period_locks, agent_anomalies, agent_schedules tables
and extends the existing agent_jobs table with new columns for the accounting
agent framework (approval workflow, period tracking, structured reporting).

Revision ID: r10_agent_infra
Revises: r9_document_r2
Create Date: 2026-04-08
"""

import sqlalchemy as sa
from alembic import op

revision = "r10_agent_infra"
down_revision = "r9_document_r2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extend existing agent_jobs table ─────────────────────────────────
    op.add_column("agent_jobs", sa.Column("period_start", sa.Date(), nullable=True))
    op.add_column("agent_jobs", sa.Column("period_end", sa.Date(), nullable=True))
    op.add_column("agent_jobs", sa.Column("dry_run", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("agent_jobs", sa.Column("triggered_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("agent_jobs", sa.Column("trigger_type", sa.String(50), nullable=False, server_default="manual"))
    op.add_column("agent_jobs", sa.Column("run_log", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("agent_jobs", sa.Column("report_payload", sa.JSON(), nullable=True))
    op.add_column("agent_jobs", sa.Column("report_pdf_path", sa.String(500), nullable=True))
    op.add_column("agent_jobs", sa.Column("anomaly_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("agent_jobs", sa.Column("approval_token", sa.String(200), nullable=True))
    op.add_column("agent_jobs", sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("agent_jobs", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agent_jobs", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column("agent_jobs", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))

    # Widen job_type column from 50 → 100 for new enum values
    op.alter_column("agent_jobs", "job_type", type_=sa.String(100))
    # Widen status column from 20 → 50 for 'awaiting_approval'
    op.alter_column("agent_jobs", "status", type_=sa.String(50))

    op.create_index("ix_agent_jobs_status", "agent_jobs", ["status"])
    op.create_index("ix_agent_jobs_job_type", "agent_jobs", ["job_type"])
    op.create_index("ix_agent_jobs_period", "agent_jobs", ["period_start", "period_end"])
    op.create_index("ix_agent_jobs_created_at", "agent_jobs", ["created_at"])
    op.create_index("ix_agent_jobs_approval_token", "agent_jobs", ["approval_token"], unique=True)

    # ── agent_run_steps ──────────────────────────────────────────────────
    op.create_table(
        "agent_run_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent_job_id", sa.String(36), sa.ForeignKey("agent_jobs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("input_summary", sa.JSON(), nullable=True),
        sa.Column("output_summary", sa.JSON(), nullable=True),
        sa.Column("anomalies", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_agent_run_steps_step_number", "agent_run_steps", ["agent_job_id", "step_number"])

    # ── period_locks ─────────────────────────────────────────────────────
    op.create_table(
        "period_locks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("locked_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("lock_reason", sa.Text(), nullable=True),
        sa.Column("agent_job_id", sa.String(36), sa.ForeignKey("agent_jobs.id"), nullable=True),
        sa.Column("unlocked_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_period_locks_tenant_period", "period_locks", ["tenant_id", "period_start"])
    op.create_index("ix_period_locks_active", "period_locks", ["is_active"])
    # Partial unique index: only one active lock per tenant+period
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_period_locks_active "
        "ON period_locks (tenant_id, period_start, period_end) "
        "WHERE is_active = true"
    )

    # ── agent_anomalies ──────────────────────────────────────────────────
    op.create_table(
        "agent_anomalies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent_job_id", sa.String(36), sa.ForeignKey("agent_jobs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agent_run_step_id", sa.String(36), sa.ForeignKey("agent_run_steps.id"), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("anomaly_type", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=True),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("resolved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_agent_anomalies_severity", "agent_anomalies", ["severity"])
    op.create_index("ix_agent_anomalies_type", "agent_anomalies", ["anomaly_type"])
    op.create_index("ix_agent_anomalies_resolved", "agent_anomalies", ["resolved"])
    op.create_index("ix_agent_anomalies_entity", "agent_anomalies", ["entity_id"])

    # ── agent_schedules ──────────────────────────────────────────────────
    op.create_table(
        "agent_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("job_type", sa.String(100), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("cron_expression", sa.String(100), nullable=True),
        sa.Column("run_day_of_month", sa.Integer(), nullable=True),
        sa.Column("run_hour", sa.Integer(), nullable=True),
        sa.Column("timezone", sa.String(100), nullable=False, server_default="'America/New_York'"),
        sa.Column("auto_approve", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notify_emails", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_job_id", sa.String(36), sa.ForeignKey("agent_jobs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("uq_agent_schedules_tenant_type", "agent_schedules", ["tenant_id", "job_type"], unique=True)


def downgrade() -> None:
    op.drop_table("agent_schedules")
    op.drop_table("agent_anomalies")
    op.drop_table("period_locks")
    op.drop_table("agent_run_steps")

    # Remove added columns from agent_jobs
    for col in [
        "period_start", "period_end", "dry_run", "triggered_by",
        "trigger_type", "run_log", "report_payload", "report_pdf_path",
        "anomaly_count", "approval_token", "approved_by", "approved_at",
        "rejection_reason", "updated_at",
    ]:
        op.drop_column("agent_jobs", col)

    op.drop_index("ix_agent_jobs_status", table_name="agent_jobs")
    op.drop_index("ix_agent_jobs_job_type", table_name="agent_jobs")
    op.drop_index("ix_agent_jobs_period", table_name="agent_jobs")
    op.drop_index("ix_agent_jobs_created_at", table_name="agent_jobs")
    op.drop_index("ix_agent_jobs_approval_token", table_name="agent_jobs")
