"""Bridgeable Documents Phase D-2 — managed template registry.

Two new tables:
  document_templates            — a registered template_key (platform or
                                  tenant-scoped). Holds a pointer to the
                                  current active version.
  document_template_versions    — versioned body + subject + variable schema.
                                  status is draft / active / retired; only
                                  one active version per template enforced
                                  by the service layer.

Seeds 18 platform-global templates (company_id=NULL) covering:
  - 8 PDF templates previously in backend/app/templates/ (invoices, statements,
    price lists, disinterment)
  - 3 PDF templates migrated from inline Python strings (social service
    certificate, legacy vault print, safety program base wrapper)
  - 7 email templates migrated from email_service.py +
    legacy_email_service.py (base wrapper, statement, collections,
    invitation, accountant invitation, alert digest, legacy proof)

After this migration runs, DocumentRenderer resolves templates from the
DB (tenant-specific first, platform fallback). File-based template files
stay on disk as reference.

Revision ID: r21_document_template_registry
Revises: r20_documents_backbone
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "r21_document_template_registry"
down_revision = "r20_documents_backbone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. document_templates ─────────────────────────────────────────
    op.create_table(
        "document_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=True,  # NULL = platform-global
        ),
        sa.Column("template_key", sa.String(128), nullable=False),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("output_format", sa.String(16), nullable=False),  # pdf|html|text
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "supports_variants",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "current_version_id", sa.String(36), nullable=True
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_document_templates_template_key",
        "document_templates",
        ["template_key"],
    )
    op.create_index(
        "ix_document_templates_company_id",
        "document_templates",
        ["company_id"],
    )
    # Partial unique (company_id, template_key) WHERE deleted_at IS NULL —
    # platform (company_id=NULL) and each tenant can each own one row per key.
    op.execute(
        "CREATE UNIQUE INDEX uq_document_templates_company_key "
        "ON document_templates (company_id, template_key) "
        "WHERE deleted_at IS NULL"
    )

    # ── 2. document_template_versions ─────────────────────────────────
    op.create_table(
        "document_template_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("document_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("subject_template", sa.Text(), nullable=True),
        sa.Column(
            "variable_schema",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "sample_context", sa.dialects.postgresql.JSONB(), nullable=True
        ),
        sa.Column(
            "css_variables", sa.dialects.postgresql.JSONB(), nullable=True
        ),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "activated_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "uq_document_template_version_number",
        "document_template_versions",
        ["template_id", "version_number"],
        unique=True,
    )
    op.execute(
        "CREATE INDEX ix_document_template_versions_active "
        "ON document_template_versions (template_id) "
        "WHERE status = 'active'"
    )

    # Now that template_versions exists, add the FK from templates to it.
    # (Created after the table itself because of the circular reference.)
    op.create_foreign_key(
        "fk_document_templates_current_version",
        "document_templates",
        "document_template_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ── 3. Seed platform templates ────────────────────────────────────
    # Import the seeds lazily so the migration stays importable even if
    # the templates directory is missing in some contexts.
    from app.services.documents._template_seeds import (
        list_platform_template_seeds,
    )

    now = datetime.now(timezone.utc)
    conn = op.get_bind()

    for seed in list_platform_template_seeds():
        template_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        variable_schema_json = (
            json.dumps(seed.get("variable_schema"))
            if seed.get("variable_schema") is not None
            else None
        )
        css_variables_json = (
            json.dumps(seed.get("css_variables"))
            if seed.get("css_variables") is not None
            else None
        )

        # Insert template row (with NULL current_version_id — we update below)
        conn.execute(
            sa.text(
                """
                INSERT INTO document_templates (
                    id, company_id, template_key, document_type,
                    output_format, description, supports_variants,
                    current_version_id, is_active, created_at, updated_at
                ) VALUES (
                    :id, NULL, :template_key, :document_type,
                    :output_format, :description, :supports_variants,
                    NULL, TRUE, :now, :now
                )
                """
            ),
            {
                "id": template_id,
                "template_key": seed["template_key"],
                "document_type": seed["document_type"],
                "output_format": seed["output_format"],
                "description": seed.get("description"),
                "supports_variants": seed.get("supports_variants", False),
                "now": now,
            },
        )

        # Insert version row (status=active, version_number=1)
        conn.execute(
            sa.text(
                """
                INSERT INTO document_template_versions (
                    id, template_id, version_number, status,
                    body_template, subject_template,
                    variable_schema, css_variables,
                    changelog, activated_at, created_at
                ) VALUES (
                    :id, :template_id, 1, 'active',
                    :body_template, :subject_template,
                    CAST(:variable_schema AS jsonb),
                    CAST(:css_variables AS jsonb),
                    :changelog, :now, :now
                )
                """
            ),
            {
                "id": version_id,
                "template_id": template_id,
                "body_template": seed["body_template"],
                "subject_template": seed.get("subject_template"),
                "variable_schema": variable_schema_json,
                "css_variables": css_variables_json,
                "changelog": "Phase D-2 initial platform seed.",
                "now": now,
            },
        )

        # Point the template at its active version
        conn.execute(
            sa.text(
                "UPDATE document_templates SET current_version_id = :v "
                "WHERE id = :t"
            ),
            {"v": version_id, "t": template_id},
        )


def downgrade() -> None:
    # Drop FK first, then versions, then templates.
    op.drop_constraint(
        "fk_document_templates_current_version",
        "document_templates",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_document_template_versions_active",
        table_name="document_template_versions",
    )
    op.drop_index(
        "uq_document_template_version_number",
        table_name="document_template_versions",
    )
    op.drop_table("document_template_versions")

    op.drop_index(
        "uq_document_templates_company_key", table_name="document_templates"
    )
    op.drop_index(
        "ix_document_templates_company_id", table_name="document_templates"
    )
    op.drop_index(
        "ix_document_templates_template_key", table_name="document_templates"
    )
    op.drop_table("document_templates")
