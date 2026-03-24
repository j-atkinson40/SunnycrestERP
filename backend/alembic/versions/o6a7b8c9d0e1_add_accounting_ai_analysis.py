"""Add accounting AI analysis tables.

Revision ID: o6a7b8c9d0e1
Revises: o5a6b7c8d9e0
Create Date: 2026-03-24
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "o6a7b8c9d0e1"
down_revision = "o5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Staging table for extracted accounting data before analysis
    op.create_table(
        "tenant_accounting_import_staging",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("data_type", sa.String(30), nullable=False),  # coa, customer, vendor, product
        sa.Column("raw_data", JSONB, nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(30), nullable=True),  # quickbooks, sage_csv
        sa.Column("extracted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("status", sa.String(20), server_default="extracted"),  # extracted, analyzing, analyzed, confirmed
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # AI analysis results — one row per mapped item
    op.create_table(
        "tenant_accounting_analysis",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("analysis_run_id", sa.String(36), nullable=False, index=True),
        sa.Column("mapping_type", sa.String(30), nullable=False),  # gl_account, customer, vendor, product
        sa.Column("source_id", sa.String(100), nullable=True),  # account number, customer ID, etc.
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("source_data", JSONB, nullable=True),  # full source record
        sa.Column("platform_category", sa.String(100), nullable=True),  # mapped platform category
        sa.Column("confidence", sa.Numeric(3, 2), nullable=True),  # 0.00 to 1.00
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("alternative", sa.String(100), nullable=True),  # second best guess
        sa.Column("is_stale", sa.Boolean(), server_default="false"),
        sa.Column("status", sa.String(20), server_default="pending"),  # pending, confirmed, ignored, archived
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Confirmed GL mappings — live reference table
    op.create_table(
        "tenant_gl_mappings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("platform_category", sa.String(100), nullable=False),
        sa.Column("account_number", sa.String(50), nullable=True),
        sa.Column("account_name", sa.String(255), nullable=False),
        sa.Column("provider_account_id", sa.String(100), nullable=True),  # QB/Sage ID
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "platform_category", "account_number", name="uq_gl_mapping"),
    )

    # Tenant alerts — used by background agent checks
    op.create_table(
        "tenant_alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("action_label", sa.String(100), nullable=True),
        sa.Column("action_url", sa.String(500), nullable=True),
        sa.Column("severity", sa.String(20), server_default="info"),  # info, warning, critical
        sa.Column("resolved", sa.Boolean(), server_default="false"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Add analysis tracking to accounting_connections
    op.add_column("accounting_connections", sa.Column("ai_analysis_run_id", sa.String(36), nullable=True))
    op.add_column("accounting_connections", sa.Column("ai_analysis_status", sa.String(20), nullable=True))
    op.add_column("accounting_connections", sa.Column("ai_analysis_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("accounting_connections", sa.Column("ai_analysis_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("accounting_connections", sa.Column("ai_auto_approved_count", sa.Integer(), nullable=True))
    op.add_column("accounting_connections", sa.Column("ai_review_required_count", sa.Integer(), nullable=True))
    op.add_column("accounting_connections", sa.Column("first_sync_validation_pending", sa.Boolean(), server_default="false"))


def downgrade() -> None:
    op.drop_column("accounting_connections", "first_sync_validation_pending")
    op.drop_column("accounting_connections", "ai_review_required_count")
    op.drop_column("accounting_connections", "ai_auto_approved_count")
    op.drop_column("accounting_connections", "ai_analysis_completed_at")
    op.drop_column("accounting_connections", "ai_analysis_started_at")
    op.drop_column("accounting_connections", "ai_analysis_status")
    op.drop_column("accounting_connections", "ai_analysis_run_id")
    op.drop_table("tenant_alerts")
    op.drop_table("tenant_gl_mappings")
    op.drop_table("tenant_accounting_analysis")
    op.drop_table("tenant_accounting_import_staging")
