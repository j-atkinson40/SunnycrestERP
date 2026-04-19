"""Intelligence Phase 2c-0a — extend intelligence_executions linkage columns.

Adds six new caller_* linkage columns on intelligence_executions so Phase 2c
migrations can populate tight entity references:

  caller_accounting_analysis_run_id  — TenantAccountingAnalysis.analysis_run_id (no FK; UUID groups rows)
  caller_price_list_import_id        — FK price_list_imports.id
  caller_fh_case_id                  — FK fh_cases.id
  caller_ringcentral_call_log_id     — FK ringcentral_call_log.id (singular table name)
  caller_kb_document_id              — FK kb_documents.id
  caller_import_session_id           — transient staging id (no FK)

Revision ID: r17_intelligence_linkage_extensions
Revises: r16_bridgeable_intelligence
"""

from alembic import op
import sqlalchemy as sa


revision = "r17_intelligence_linkage_extensions"
down_revision = "r16_bridgeable_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "intelligence_executions",
        sa.Column("caller_accounting_analysis_run_id", sa.String(36), nullable=True),
    )
    op.add_column(
        "intelligence_executions",
        sa.Column(
            "caller_price_list_import_id",
            sa.String(36),
            sa.ForeignKey("price_list_imports.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "intelligence_executions",
        sa.Column(
            "caller_fh_case_id",
            sa.String(36),
            sa.ForeignKey("fh_cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "intelligence_executions",
        sa.Column(
            "caller_ringcentral_call_log_id",
            sa.String(36),
            sa.ForeignKey("ringcentral_call_log.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "intelligence_executions",
        sa.Column(
            "caller_kb_document_id",
            sa.String(36),
            sa.ForeignKey("kb_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "intelligence_executions",
        sa.Column("caller_import_session_id", sa.String(36), nullable=True),
    )

    # Partial indexes — only index rows that actually carry the linkage.
    # Postgres supports `WHERE` clauses on CREATE INDEX; keeps index small.
    op.create_index(
        "ix_intel_exec_accounting_run",
        "intelligence_executions",
        ["caller_accounting_analysis_run_id"],
        postgresql_where=sa.text("caller_accounting_analysis_run_id IS NOT NULL"),
    )
    op.create_index(
        "ix_intel_exec_price_list_import",
        "intelligence_executions",
        ["caller_price_list_import_id"],
        postgresql_where=sa.text("caller_price_list_import_id IS NOT NULL"),
    )
    op.create_index(
        "ix_intel_exec_fh_case",
        "intelligence_executions",
        ["caller_fh_case_id"],
        postgresql_where=sa.text("caller_fh_case_id IS NOT NULL"),
    )
    op.create_index(
        "ix_intel_exec_rc_call_log",
        "intelligence_executions",
        ["caller_ringcentral_call_log_id"],
        postgresql_where=sa.text("caller_ringcentral_call_log_id IS NOT NULL"),
    )
    op.create_index(
        "ix_intel_exec_kb_document",
        "intelligence_executions",
        ["caller_kb_document_id"],
        postgresql_where=sa.text("caller_kb_document_id IS NOT NULL"),
    )
    op.create_index(
        "ix_intel_exec_import_session",
        "intelligence_executions",
        ["caller_import_session_id"],
        postgresql_where=sa.text("caller_import_session_id IS NOT NULL"),
    )


def downgrade() -> None:
    for ix in (
        "ix_intel_exec_import_session",
        "ix_intel_exec_kb_document",
        "ix_intel_exec_rc_call_log",
        "ix_intel_exec_fh_case",
        "ix_intel_exec_price_list_import",
        "ix_intel_exec_accounting_run",
    ):
        op.drop_index(ix, table_name="intelligence_executions")

    for col in (
        "caller_import_session_id",
        "caller_kb_document_id",
        "caller_ringcentral_call_log_id",
        "caller_fh_case_id",
        "caller_price_list_import_id",
        "caller_accounting_analysis_run_id",
    ):
        op.drop_column("intelligence_executions", col)
