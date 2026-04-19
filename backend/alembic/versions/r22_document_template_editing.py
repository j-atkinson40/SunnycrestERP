"""Bridgeable Documents Phase D-3 — template editing + audit log.

Adds:
  - documents.is_test_render (Boolean, default False) + partial index
    filtering WHERE is_test_render = True
  - document_template_audit_log table mirroring intelligence_prompt_audit_log

Test renders from the admin template editor land in the documents table
flagged as test renders. The Document Log excludes them by default; admin
UI exposes an opt-in toggle.

Revision ID: r22_document_template_editing
Revises: r21_document_template_registry
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r22_document_template_editing"
down_revision = "r21_document_template_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. documents.is_test_render ────────────────────────────────────
    op.add_column(
        "documents",
        sa.Column(
            "is_test_render",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # Partial index — only test renders need the index; production queries
    # use the default path (is_test_render = FALSE) and rely on other
    # existing indexes.
    op.execute(
        "CREATE INDEX ix_documents_is_test_render "
        "ON documents (is_test_render) "
        "WHERE is_test_render = TRUE"
    )

    # ── 2. document_template_audit_log ─────────────────────────────────
    op.create_table(
        "document_template_audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey(
                "document_templates.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "version_id",
            sa.String(36),
            sa.ForeignKey(
                "document_template_versions.id", ondelete="SET NULL"
            ),
            nullable=True,
        ),
        # create_draft | update_draft | delete_draft | activate |
        # rollback | fork_to_tenant
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("changelog_summary", sa.Text(), nullable=True),
        sa.Column(
            "meta_json",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_document_template_audit_log_template_created",
        "document_template_audit_log",
        ["template_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_document_template_audit_log_version_id",
        "document_template_audit_log",
        ["version_id"],
    )
    op.create_index(
        "ix_document_template_audit_log_actor_user_id",
        "document_template_audit_log",
        ["actor_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_template_audit_log_actor_user_id",
        table_name="document_template_audit_log",
    )
    op.drop_index(
        "ix_document_template_audit_log_version_id",
        table_name="document_template_audit_log",
    )
    op.drop_index(
        "ix_document_template_audit_log_template_created",
        table_name="document_template_audit_log",
    )
    op.drop_table("document_template_audit_log")

    op.execute("DROP INDEX IF EXISTS ix_documents_is_test_render")
    op.drop_column("documents", "is_test_render")
