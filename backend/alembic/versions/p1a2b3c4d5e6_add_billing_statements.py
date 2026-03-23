"""Add billing statement system tables.

Revision ID: p1a2b3c4d5e6
Revises: o5a6b7c8d9e0
Create Date: 2026-03-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "p1a2b3c4d5e6"
down_revision = "o5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add billing fields to customers
    op.add_column("customers", sa.Column("billing_contact_name", sa.String(255), nullable=True))
    op.add_column("customers", sa.Column("billing_email", sa.String(255), nullable=True))
    op.add_column("customers", sa.Column("statement_delivery_method", sa.String(20), server_default="digital"))
    op.add_column("customers", sa.Column("statement_template_key", sa.String(100), nullable=True))
    op.add_column("customers", sa.Column("receives_statements", sa.Boolean(), server_default="true"))
    op.add_column("customers", sa.Column("statement_notes", sa.Text(), nullable=True))

    # Statement templates — platform seed data
    op.create_table(
        "statement_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("template_key", sa.String(100), nullable=False),
        sa.Column("template_name", sa.String(200), nullable=False),
        sa.Column("customer_type", sa.String(50), nullable=False, server_default="all"),
        sa.Column("is_default_for_type", sa.Boolean(), server_default="false"),
        sa.Column("sections", JSONB, server_default='["header","period","account_number","balance_summary","invoice_list","aging_summary","payment_instructions","custom_message"]'),
        sa.Column("logo_enabled", sa.Boolean(), server_default="true"),
        sa.Column("show_aging_summary", sa.Boolean(), server_default="true"),
        sa.Column("show_account_number", sa.Boolean(), server_default="true"),
        sa.Column("show_payment_instructions", sa.Boolean(), server_default="true"),
        sa.Column("remittance_address", sa.Text(), nullable=True),
        sa.Column("payment_instructions", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Statement runs — one per monthly cycle
    op.create_table(
        "statement_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("statement_period_month", sa.Integer(), nullable=False),
        sa.Column("statement_period_year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("total_customers", sa.Integer(), server_default="0"),
        sa.Column("digital_count", sa.Integer(), server_default="0"),
        sa.Column("mail_count", sa.Integer(), server_default="0"),
        sa.Column("none_count", sa.Integer(), server_default="0"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("initiated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("custom_message", sa.Text(), nullable=True),
        sa.Column("zip_file_url", sa.String(500), nullable=True),
        sa.Column("zip_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "statement_period_month", "statement_period_year", name="uq_statement_run_period"),
    )

    # Customer statements — one per customer per run
    op.create_table(
        "customer_statements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("statement_runs.id"), nullable=False, index=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("statement_period_month", sa.Integer(), nullable=False),
        sa.Column("statement_period_year", sa.Integer(), nullable=False),
        sa.Column("delivery_method", sa.String(20), nullable=False),
        sa.Column("template_key", sa.String(100), nullable=True),
        sa.Column("previous_balance", sa.Numeric(12, 2), server_default="0"),
        sa.Column("new_charges", sa.Numeric(12, 2), server_default="0"),
        sa.Column("payments_received", sa.Numeric(12, 2), server_default="0"),
        sa.Column("balance_due", sa.Numeric(12, 2), server_default="0"),
        sa.Column("invoice_ids", JSONB, server_default="[]"),
        sa.Column("invoice_count", sa.Integer(), server_default="0"),
        sa.Column("statement_pdf_url", sa.String(500), nullable=True),
        sa.Column("statement_pdf_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_sent_to", sa.String(255), nullable=True),
        sa.Column("send_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "customer_id", name="uq_customer_statement_per_run"),
    )

    # Seed default templates
    op.execute("""
        INSERT INTO statement_templates (id, template_key, template_name, customer_type, is_default_for_type)
        VALUES
        ('tmpl_funeral_home_std', 'funeral_home_standard', 'Funeral Home Statement', 'funeral_home', true),
        ('tmpl_general_std', 'general_standard', 'Standard Statement', 'general', true)
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("customer_statements")
    op.drop_table("statement_runs")
    op.drop_table("statement_templates")
    op.drop_column("customers", "statement_notes")
    op.drop_column("customers", "receives_statements")
    op.drop_column("customers", "statement_template_key")
    op.drop_column("customers", "statement_delivery_method")
    op.drop_column("customers", "billing_email")
    op.drop_column("customers", "billing_contact_name")
