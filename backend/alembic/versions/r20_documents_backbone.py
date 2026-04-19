"""Bridgeable Documents Phase D-1 — canonical Document model + versions.

Two new tables:
  documents                     — canonical document record (tenant-scoped,
                                  polymorphic entity linkage + specialty FKs)
  document_versions             — immutable per-render history; exactly one
                                  row per document has is_current=True

One column added to intelligence_executions:
  caller_document_id            — links AI-generated content back to the
                                  Document it produced (partial index where
                                  NOT NULL)

The canonical Document model is designed fresh — it does NOT extend the
legacy `documents` table (which actually used a different column shape).
The legacy `Document` model (app/models/document.py as of r19) continues
to exist for now; Phase D-later deprecates it once callers migrate.

Since the existing Document model already maps to `documents`, this
migration must RENAME the legacy table before creating the new one.

Revision ID: r20_documents_backbone
Revises: r19_intelligence_test_execution_flag
"""

from alembic import op
import sqlalchemy as sa


revision = "r20_documents_backbone"
down_revision = "r19_intelligence_test_execution_flag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Rename legacy `documents` → `documents_legacy` ──────────────
    # The Phase 1-era Document model owns the `documents` table name. We
    # claim that name for the canonical Document and push the legacy one
    # to `documents_legacy`. The legacy model's __tablename__ is
    # updated in the same commit.
    op.rename_table("documents", "documents_legacy")
    # PostgreSQL keeps old index names when a table is renamed. Rename
    # every `ix_documents_*` index to `ix_documents_legacy_*` to free
    # the old names for the new canonical table below. Use
    # `ALTER INDEX IF EXISTS` so fresh databases (which may not have
    # run all original index-creating migrations) still apply cleanly.
    conn = op.get_bind()
    for old_name, new_name in (
        ("ix_documents_company_id", "ix_documents_legacy_company_id"),
        ("ix_documents_document_type", "ix_documents_legacy_document_type"),
        ("ix_documents_entity_id", "ix_documents_legacy_entity_id"),
        ("ix_documents_entity_type", "ix_documents_legacy_entity_type"),
    ):
        conn.execute(
            sa.text(
                f"ALTER INDEX IF EXISTS {old_name} RENAME TO {new_name}"
            )
        )
    conn.execute(
        sa.text(
            "ALTER INDEX IF EXISTS documents_pkey "
            "RENAME TO documents_legacy_pkey"
        )
    )

    # ── 2. Create canonical documents table ─────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Document classification + presentation
        sa.Column("document_type", sa.String(64), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        # Storage — R2 only, no local disk fallback on this model
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column(
            "mime_type",
            sa.String(100),
            nullable=False,
            server_default="application/pdf",
        ),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="draft",
        ),
        # Template identity (template_key references the loader; in D-2 this
        # becomes an FK to document_templates)
        sa.Column("template_key", sa.String(128), nullable=True),
        sa.Column("template_version", sa.Integer, nullable=True),
        # Render metadata
        sa.Column(
            "rendered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "rendered_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rendering_duration_ms", sa.Integer, nullable=True),
        sa.Column(
            "rendering_context_hash",
            sa.String(64),
            nullable=True,
        ),
        # Polymorphic entity linkage — either use these or the specialty
        # FKs below. Both are valid; the specialty FKs exist because they
        # make JOINs practical for the most common cases.
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("entity_id", sa.String(36), nullable=True),
        # Specialty linkage — common enough to deserve proper FKs + indexes.
        # Each is nullable; multiple can be populated on the same row (e.g.
        # an invoice document linked to both sales_order_id and invoice_id).
        sa.Column(
            "sales_order_id",
            sa.String(36),
            sa.ForeignKey("sales_orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "fh_case_id",
            sa.String(36),
            sa.ForeignKey("fh_cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "disinterment_case_id",
            sa.String(36),
            sa.ForeignKey("disinterment_cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "invoice_id",
            sa.String(36),
            sa.ForeignKey("invoices.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "customer_statement_id",
            sa.String(36),
            sa.ForeignKey("customer_statements.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "price_list_version_id",
            sa.String(36),
            sa.ForeignKey("price_list_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "safety_program_generation_id",
            sa.String(36),
            sa.ForeignKey(
                "safety_program_generations.id", ondelete="SET NULL"
            ),
            nullable=True,
        ),
        # Source linkage — what produced this document
        sa.Column("caller_module", sa.String(256), nullable=True),
        sa.Column(
            "caller_workflow_run_id",
            sa.String(36),
            sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("caller_workflow_step_id", sa.String(36), nullable=True),
        sa.Column(
            "intelligence_execution_id",
            sa.String(36),
            sa.ForeignKey(
                "intelligence_executions.id", ondelete="SET NULL"
            ),
            nullable=True,
        ),
        # Timestamps + soft delete
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "deleted_at", sa.DateTime(timezone=True), nullable=True
        ),
    )

    # Indexes on documents — the tenant-by-type-by-date pattern is the
    # primary list-page query
    op.create_index(
        "ix_documents_company_type_created",
        "documents",
        ["company_id", "document_type", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_documents_company_entity",
        "documents",
        ["company_id", "entity_type", "entity_id"],
        postgresql_where=sa.text("entity_type IS NOT NULL"),
    )
    op.create_index(
        "ix_documents_company_status",
        "documents",
        ["company_id", "status"],
    )
    # Partial indexes on specialty linkage — each enables cheap
    # "documents for this entity" lookups
    for col in (
        "sales_order_id",
        "fh_case_id",
        "disinterment_case_id",
        "invoice_id",
        "customer_statement_id",
        "price_list_version_id",
        "safety_program_generation_id",
        "intelligence_execution_id",
    ):
        op.create_index(
            f"ix_documents_{col}",
            "documents",
            [col],
            postgresql_where=sa.text(f"{col} IS NOT NULL"),
        )

    # ── 3. Create document_versions table ──────────────────────────────
    op.create_table(
        "document_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column(
            "mime_type",
            sa.String(100),
            nullable=False,
            server_default="application/pdf",
        ),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column(
            "rendered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "rendered_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "rendering_context_hash", sa.String(64), nullable=True
        ),
        sa.Column("render_reason", sa.String(255), nullable=True),
        sa.Column(
            "is_current",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_index(
        "ix_document_versions_document_version",
        "document_versions",
        ["document_id", "version_number"],
        unique=True,
    )
    # Partial index: exactly one is_current=true per document
    op.create_index(
        "ix_document_versions_current",
        "document_versions",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )

    # ── 4. intelligence_executions.caller_document_id ──────────────────
    op.add_column(
        "intelligence_executions",
        sa.Column(
            "caller_document_id",
            sa.String(36),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_intelligence_executions_caller_document_id",
        "intelligence_executions",
        ["caller_document_id"],
        postgresql_where=sa.text("caller_document_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_intelligence_executions_caller_document_id",
        table_name="intelligence_executions",
    )
    op.drop_column("intelligence_executions", "caller_document_id")
    op.drop_index(
        "ix_document_versions_current", table_name="document_versions"
    )
    op.drop_index(
        "ix_document_versions_document_version",
        table_name="document_versions",
    )
    op.drop_table("document_versions")
    for col in (
        "intelligence_execution_id",
        "safety_program_generation_id",
        "price_list_version_id",
        "customer_statement_id",
        "invoice_id",
        "disinterment_case_id",
        "fh_case_id",
        "sales_order_id",
    ):
        op.drop_index(f"ix_documents_{col}", table_name="documents")
    op.drop_index(
        "ix_documents_company_status", table_name="documents"
    )
    op.drop_index(
        "ix_documents_company_entity", table_name="documents"
    )
    op.drop_index(
        "ix_documents_company_type_created", table_name="documents"
    )
    op.drop_table("documents")
    # Restore the legacy documents table name + its original index names
    op.rename_table("documents_legacy", "documents")
    conn = op.get_bind()
    for new_name, old_name in (
        ("ix_documents_legacy_company_id", "ix_documents_company_id"),
        ("ix_documents_legacy_document_type", "ix_documents_document_type"),
        ("ix_documents_legacy_entity_id", "ix_documents_entity_id"),
        ("ix_documents_legacy_entity_type", "ix_documents_entity_type"),
    ):
        conn.execute(
            sa.text(
                f"ALTER INDEX IF EXISTS {new_name} RENAME TO {old_name}"
            )
        )
    conn.execute(
        sa.text(
            "ALTER INDEX IF EXISTS documents_legacy_pkey "
            "RENAME TO documents_pkey"
        )
    )
