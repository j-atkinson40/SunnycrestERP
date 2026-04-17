"""Workflow Engine Phase W-1: workflows, steps, runs, enrollments, schedules."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "fh_03_workflows"
down_revision = "fh_02_cross_tenant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─────────────────────────────────────────────────────────
    # workflows — definitions (platform + tenant)
    # ─────────────────────────────────────────────────────────
    op.create_table(
        "workflows",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=True),
        # NULL = platform workflow available to all tenants
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("keywords", JSONB, nullable=True),
        sa.Column("tier", sa.Integer, nullable=False, server_default="2"),
        # 1=platform-locked, 2=default on, 3=available off, 4=custom tenant
        sa.Column("vertical", sa.String(50), nullable=True),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("trigger_config", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("command_bar_priority", sa.Integer, nullable=False, server_default="10"),
        sa.Column("created_by_user_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workflows_company_id", "workflows", ["company_id"])
    op.create_index("ix_workflows_vertical_active", "workflows", ["vertical", "is_active"])

    # ─────────────────────────────────────────────────────────
    # workflow_steps
    # ─────────────────────────────────────────────────────────
    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_id", sa.String(36), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_order", sa.Integer, nullable=False),
        sa.Column("step_key", sa.String(100), nullable=False),
        sa.Column("step_type", sa.String(50), nullable=False),
        # input | action | condition | notification | output
        sa.Column("config", JSONB, nullable=False),
        sa.Column("next_step_id", sa.String(36), nullable=True),
        sa.Column("condition_true_step_id", sa.String(36), nullable=True),
        sa.Column("condition_false_step_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_steps_workflow_id", "workflow_steps", ["workflow_id", "step_order"])
    op.create_index("uq_workflow_step_key", "workflow_steps", ["workflow_id", "step_key"], unique=True)

    # ─────────────────────────────────────────────────────────
    # workflow_runs
    # ─────────────────────────────────────────────────────────
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_id", sa.String(36), sa.ForeignKey("workflows.id"), nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("triggered_by_user_id", sa.String(36), nullable=True),
        sa.Column("trigger_source", sa.String(50), nullable=False),
        # command_bar | button | schedule | record_event | cross_tenant
        sa.Column("trigger_context", JSONB, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        # running | awaiting_input | completed | failed | cancelled
        sa.Column("input_data", JSONB, nullable=True),
        sa.Column("output_data", JSONB, nullable=True),
        sa.Column("current_step_id", sa.String(36), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_workflow_runs_company_status", "workflow_runs", ["company_id", "status"])

    # ─────────────────────────────────────────────────────────
    # workflow_run_steps
    # ─────────────────────────────────────────────────────────
    op.create_table(
        "workflow_run_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", sa.String(36), sa.ForeignKey("workflow_steps.id"), nullable=False),
        sa.Column("step_key", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        # pending | running | completed | failed | skipped
        sa.Column("input_data", JSONB, nullable=True),
        sa.Column("output_data", JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_run_steps_run", "workflow_run_steps", ["run_id"])

    # ─────────────────────────────────────────────────────────
    # workflow_enrollments — tenant opt-in for tier-3, override for tier-2
    # ─────────────────────────────────────────────────────────
    op.create_table(
        "workflow_enrollments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_id", sa.String(36), sa.ForeignKey("workflows.id"), nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("config_overrides", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("uq_workflow_enrollments", "workflow_enrollments", ["workflow_id", "company_id"], unique=True)

    # ─────────────────────────────────────────────────────────
    # workflow_schedules — scheduled time-based jobs
    # ─────────────────────────────────────────────────────────
    op.create_table(
        "workflow_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_id", sa.String(36), sa.ForeignKey("workflows.id"), nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("cron_expression", sa.String(100), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_schedules_next_run", "workflow_schedules", ["next_run_at", "is_active"])


def downgrade() -> None:
    op.drop_table("workflow_schedules")
    op.drop_index("uq_workflow_enrollments", table_name="workflow_enrollments")
    op.drop_table("workflow_enrollments")
    op.drop_index("ix_workflow_run_steps_run", table_name="workflow_run_steps")
    op.drop_table("workflow_run_steps")
    op.drop_index("ix_workflow_runs_company_status", table_name="workflow_runs")
    op.drop_table("workflow_runs")
    op.drop_index("uq_workflow_step_key", table_name="workflow_steps")
    op.drop_index("ix_workflow_steps_workflow_id", table_name="workflow_steps")
    op.drop_table("workflow_steps")
    op.drop_index("ix_workflows_vertical_active", table_name="workflows")
    op.drop_index("ix_workflows_company_id", table_name="workflows")
    op.drop_table("workflows")
