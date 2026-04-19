"""Bridgeable Documents Phase D-7 — delivery abstraction.

New table `document_deliveries` — one row per send attempt across any
channel (email today; SMS stub; future native email / push / webhook).
Every email that leaves the platform gets a row here, with the full
provider response captured for debugging and a complete linkage graph
back to document / workflow / intelligence / signature envelope.

Extends `intelligence_executions` with `caller_delivery_id` — closes
the last symmetric-linkage loop: an Intelligence execution that
generates outreach content is traceable to the delivery that sent it.

Revision ID: r26_delivery_abstraction
Revises: r25_document_sharing
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r26_delivery_abstraction"
down_revision = "r25_document_sharing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # email | sms | webhook (future) | push (future)
        sa.Column("channel", sa.String(32), nullable=False),
        # email_address | phone_number | user_id | contact_id
        sa.Column("recipient_type", sa.String(32), nullable=False),
        sa.Column("recipient_value", sa.String(255), nullable=False),
        sa.Column("recipient_name", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("body_preview", sa.Text(), nullable=True),
        sa.Column("template_key", sa.String(128), nullable=True),
        # pending | sending | sent | delivered | bounced | failed | rejected
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("provider", sa.String(32), nullable=True),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column(
            "provider_response",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "max_retries",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("3"),
        ),
        sa.Column(
            "scheduled_for", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "delivered_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        # Source linkage
        sa.Column("caller_module", sa.String(256), nullable=True),
        sa.Column(
            "caller_workflow_run_id",
            sa.String(36),
            sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "caller_workflow_step_id", sa.String(36), nullable=True
        ),
        sa.Column(
            "caller_intelligence_execution_id",
            sa.String(36),
            sa.ForeignKey(
                "intelligence_executions.id", ondelete="SET NULL"
            ),
            nullable=True,
        ),
        sa.Column(
            "caller_signature_envelope_id",
            sa.String(36),
            sa.ForeignKey("signature_envelopes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "metadata_json",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_doc_delivery_company_created",
        "document_deliveries",
        ["company_id", sa.text("created_at DESC")],
    )
    op.execute(
        "CREATE INDEX ix_doc_delivery_document_id "
        "ON document_deliveries (document_id) "
        "WHERE document_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_doc_delivery_status_active "
        "ON document_deliveries (status) "
        "WHERE status IN ('pending','sending')"
    )
    op.create_index(
        "ix_doc_delivery_channel_status",
        "document_deliveries",
        ["channel", "status"],
    )
    op.execute(
        "CREATE INDEX ix_doc_delivery_provider_msg_id "
        "ON document_deliveries (provider_message_id) "
        "WHERE provider_message_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_doc_delivery_workflow_run "
        "ON document_deliveries (caller_workflow_run_id) "
        "WHERE caller_workflow_run_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_doc_delivery_intelligence_exec "
        "ON document_deliveries (caller_intelligence_execution_id) "
        "WHERE caller_intelligence_execution_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_doc_delivery_signature_envelope "
        "ON document_deliveries (caller_signature_envelope_id) "
        "WHERE caller_signature_envelope_id IS NOT NULL"
    )

    # intelligence_executions.caller_delivery_id — closes the loop
    op.add_column(
        "intelligence_executions",
        sa.Column(
            "caller_delivery_id",
            sa.String(36),
            sa.ForeignKey(
                "document_deliveries.id", ondelete="SET NULL"
            ),
            nullable=True,
        ),
    )
    op.execute(
        "CREATE INDEX ix_intel_exec_caller_delivery "
        "ON intelligence_executions (caller_delivery_id) "
        "WHERE caller_delivery_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_intel_exec_caller_delivery")
    op.drop_column("intelligence_executions", "caller_delivery_id")

    for idx in (
        "ix_doc_delivery_signature_envelope",
        "ix_doc_delivery_intelligence_exec",
        "ix_doc_delivery_workflow_run",
        "ix_doc_delivery_provider_msg_id",
        "ix_doc_delivery_status_active",
        "ix_doc_delivery_document_id",
    ):
        op.execute(f"DROP INDEX IF EXISTS {idx}")
    op.drop_index(
        "ix_doc_delivery_channel_status",
        table_name="document_deliveries",
    )
    op.drop_index(
        "ix_doc_delivery_company_created",
        table_name="document_deliveries",
    )
    op.drop_table("document_deliveries")
