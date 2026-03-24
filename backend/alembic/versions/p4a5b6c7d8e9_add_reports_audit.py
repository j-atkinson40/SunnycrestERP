"""Add report runs, audit packages, health checks, and report schedules.

Revision ID: p4a5b6c7d8e9
Revises: p3a4b5c6d7e8
Create Date: 2026-03-24
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision = "p4a5b6c7d8e9"
down_revision = "p3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("parameters", JSONB, server_default="{}"),
        sa.Column("status", sa.String(20), server_default="running"),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("generated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audit_package_id", sa.String(36), nullable=True),
    )

    op.create_table(
        "audit_packages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("package_name", sa.String(200), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default="generating"),
        sa.Column("reports_included", JSONB, server_default="[]"),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column("pdf_page_count", sa.Integer(), nullable=True),
        sa.Column("pdf_file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("natural_language_input", sa.Text(), nullable=True),
        sa.Column("generated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "audit_health_checks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("check_date", sa.Date(), nullable=False),
        sa.Column("overall_score", sa.String(10), nullable=True),
        sa.Column("green_count", sa.Integer(), server_default="0"),
        sa.Column("amber_count", sa.Integer(), server_default="0"),
        sa.Column("red_count", sa.Integer(), server_default="0"),
        sa.Column("findings", JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "check_date", name="uq_health_check_date"),
    )

    op.create_table(
        "report_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=True),
        sa.Column("next_run_date", sa.Date(), nullable=True),
        sa.Column("recipient_user_ids", JSONB, nullable=True),
        sa.Column("parameters", JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("report_schedules")
    op.drop_table("audit_health_checks")
    op.drop_table("audit_packages")
    op.drop_table("report_runs")
