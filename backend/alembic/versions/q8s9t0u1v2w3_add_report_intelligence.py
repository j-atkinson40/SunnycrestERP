"""Add report intelligence — snapshots, commentary, forecasts, preflight.

Revision ID: q8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-03-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "q8s9t0u1v2w3"
down_revision = "q7r8s9t0u1v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Report snapshots for trend detection
    op.create_table(
        "report_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("key_metrics", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_report_snapshot", "report_snapshots", ["tenant_id", "report_type", "snapshot_date"])
    op.create_index("idx_rs_tenant_type", "report_snapshots", ["tenant_id", "report_type", sa.text("snapshot_date DESC")])

    # Report commentary
    op.create_table(
        "report_commentary",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("report_run_id", sa.String(36), nullable=True),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default="generating"),
        sa.Column("executive_summary", sa.Text(), nullable=True),
        sa.Column("key_findings", JSONB, server_default="[]"),
        sa.Column("trend_summary", sa.Text(), nullable=True),
        sa.Column("forecast_note", sa.Text(), nullable=True),
        sa.Column("attention_items", JSONB, server_default="[]"),
        sa.Column("comparison_periods_used", sa.Integer(), server_default="0"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generation_duration_ms", sa.Integer(), nullable=True),
        sa.Column("cache_key", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_rc_cache", "report_commentary", ["tenant_id", "cache_key"])

    # Report forecasts
    op.create_table(
        "report_forecasts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("forecast_type", sa.String(50), nullable=False),
        sa.Column("generated_date", sa.Date(), nullable=False),
        sa.Column("data_points", sa.Integer(), nullable=False),
        sa.Column("current_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("forecast_periods", JSONB, server_default="[]"),
        sa.Column("trend_direction", sa.String(10), nullable=True),
        sa.Column("trend_rate_monthly", sa.Numeric(6, 3), nullable=True),
        sa.Column("milestone_projections", JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_report_forecast", "report_forecasts", ["tenant_id", "forecast_type", "generated_date"])

    # Audit preflight results
    op.create_table(
        "audit_preflight_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("audit_package_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), server_default="running"),
        sa.Column("blocking_issues", JSONB, server_default="[]"),
        sa.Column("warning_issues", JSONB, server_default="[]"),
        sa.Column("passed_checks", JSONB, server_default="[]"),
        sa.Column("override_by", sa.String(36), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("override_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("audit_preflight_results")
    op.drop_table("report_forecasts")
    op.drop_table("report_commentary")
    op.drop_table("report_snapshots")
