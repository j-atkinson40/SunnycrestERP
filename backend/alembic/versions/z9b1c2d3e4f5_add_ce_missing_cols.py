"""Add missing columns across 4 tables to match ORM models.

Columns exist in models but were never migrated, causing 'UndefinedColumn'
errors on any query that references these tables.

Revision ID: z9b1c2d3e4f5
Revises: z9a0b1c2d3e4
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "z9b1c2d3e4f5"
down_revision = "z9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- company_entities: name cleanup tracking ---
    op.add_column(
        "company_entities",
        sa.Column("original_name", sa.String(500), nullable=True),
    )
    op.add_column(
        "company_entities",
        sa.Column("name_cleanup_actions", postgresql.JSONB, nullable=True),
    )

    # --- agent_collection_sequences ---
    op.add_column(
        "agent_collection_sequences",
        sa.Column("original_draft_body", sa.Text, nullable=True),
    )

    # --- customer_statements: review workflow ---
    op.add_column(
        "customer_statements",
        sa.Column("flagged", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "customer_statements",
        sa.Column("flag_reasons", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "customer_statements",
        sa.Column("review_status", sa.String(20), nullable=False, server_default="pending"),
    )
    op.add_column(
        "customer_statements",
        sa.Column("reviewed_by", sa.String(36), nullable=True),
    )
    op.add_column(
        "customer_statements",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "customer_statements",
        sa.Column("review_note", sa.Text, nullable=True),
    )

    # --- statement_runs: delivery tracking ---
    op.add_column(
        "statement_runs",
        sa.Column("statement_period_month", sa.Integer, nullable=True),
    )
    op.add_column(
        "statement_runs",
        sa.Column("statement_period_year", sa.Integer, nullable=True),
    )
    op.add_column(
        "statement_runs",
        sa.Column("digital_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "statement_runs",
        sa.Column("mail_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "statement_runs",
        sa.Column("none_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "statement_runs",
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "statement_runs",
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "statement_runs",
        sa.Column("initiated_by", sa.String(36), nullable=True),
    )
    op.add_column(
        "statement_runs",
        sa.Column("custom_message", sa.Text, nullable=True),
    )
    op.add_column(
        "statement_runs",
        sa.Column("zip_file_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "statement_runs",
        sa.Column("zip_generated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # --- statement_runs ---
    op.drop_column("statement_runs", "zip_generated_at")
    op.drop_column("statement_runs", "zip_file_url")
    op.drop_column("statement_runs", "custom_message")
    op.drop_column("statement_runs", "initiated_by")
    op.drop_column("statement_runs", "sent_at")
    op.drop_column("statement_runs", "generated_at")
    op.drop_column("statement_runs", "none_count")
    op.drop_column("statement_runs", "mail_count")
    op.drop_column("statement_runs", "digital_count")
    op.drop_column("statement_runs", "statement_period_year")
    op.drop_column("statement_runs", "statement_period_month")

    # --- customer_statements ---
    op.drop_column("customer_statements", "review_note")
    op.drop_column("customer_statements", "reviewed_at")
    op.drop_column("customer_statements", "reviewed_by")
    op.drop_column("customer_statements", "review_status")
    op.drop_column("customer_statements", "flag_reasons")
    op.drop_column("customer_statements", "flagged")

    # --- agent_collection_sequences ---
    op.drop_column("agent_collection_sequences", "original_draft_body")

    # --- company_entities ---
    op.drop_column("company_entities", "name_cleanup_actions")
    op.drop_column("company_entities", "original_name")
