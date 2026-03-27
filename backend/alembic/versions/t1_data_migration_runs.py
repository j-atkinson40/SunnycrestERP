"""Add data_migration_runs table

Revision ID: t1_data_migration_runs
Revises: s3b4c5d6e7f8
Create Date: 2026-03-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "t1_data_migration_runs"
down_revision = "s3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "data_migration_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("cutover_date", sa.Date, nullable=False),
        sa.Column("source_system", sa.String(50), nullable=True),
        sa.Column("gl_accounts_imported", sa.Integer, server_default="0"),
        sa.Column("gl_accounts_skipped", sa.Integer, server_default="0"),
        sa.Column("customers_imported", sa.Integer, server_default="0"),
        sa.Column("customers_skipped", sa.Integer, server_default="0"),
        sa.Column("ar_invoices_imported", sa.Integer, server_default="0"),
        sa.Column("ar_invoices_skipped", sa.Integer, server_default="0"),
        sa.Column("vendors_imported", sa.Integer, server_default="0"),
        sa.Column("vendors_skipped", sa.Integer, server_default="0"),
        sa.Column("ap_bills_imported", sa.Integer, server_default="0"),
        sa.Column("ap_bills_skipped", sa.Integer, server_default="0"),
        sa.Column("total_ar_balance", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_ap_balance", sa.Numeric(12, 2), nullable=True),
        sa.Column("warnings", postgresql.JSONB, server_default="[]"),
        sa.Column("errors", postgresql.JSONB, server_default="[]"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("initiated_by", sa.String(50), nullable=True),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rolled_back_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    )


def downgrade():
    op.drop_table("data_migration_runs")
