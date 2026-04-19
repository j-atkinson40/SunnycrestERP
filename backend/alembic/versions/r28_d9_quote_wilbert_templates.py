"""Bridgeable Documents Phase D-9 — seed `quote.standard` + `urn.wilbert_engraving_form`.

Two platform templates backfilled into existing databases. Matches the
D-2 seeding pattern: insert a `document_templates` row + a version-1
`document_template_versions` row, then point `current_version_id` at
the version. Skips any template_key that already exists so this is
idempotent.

No schema changes — data-only migration.

Revision ID: r28_d9_quote_wilbert_templates
Revises: r27_inbox_read_tracking
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "r28_d9_quote_wilbert_templates"
down_revision = "r27_inbox_read_tracking"
branch_labels = None
depends_on = None


# Keys we're seeding in this migration. Used on the downgrade path to
# identify rows to delete.
_D9_TEMPLATE_KEYS = ("quote.standard", "urn.wilbert_engraving_form")


def upgrade() -> None:
    # Import lazily — the seed module defines Jinja templates inline.
    from app.services.documents._template_seeds import _d9_seeds

    now = datetime.now(timezone.utc)
    conn = op.get_bind()

    for seed in _d9_seeds():
        # Idempotent: skip if (NULL company_id, template_key) already
        # exists. Same pattern as r21.
        existing = conn.execute(
            sa.text(
                "SELECT id FROM document_templates "
                "WHERE company_id IS NULL AND template_key = :key"
            ),
            {"key": seed["template_key"]},
        ).scalar_one_or_none()
        if existing is not None:
            continue

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

        conn.execute(
            sa.text(
                """
                INSERT INTO document_template_versions (
                    id, template_id, version_number, status,
                    body_template, subject_template, variable_schema,
                    css_variables, changelog, activated_at, created_at
                ) VALUES (
                    :id, :template_id, 1, 'active',
                    :body, :subject, :schema, :css, :changelog, :now, :now
                )
                """
            ),
            {
                "id": version_id,
                "template_id": template_id,
                "body": seed["body_template"],
                "subject": seed.get("subject_template"),
                "schema": variable_schema_json,
                "css": css_variables_json,
                "changelog": "D-9 seed (migrated from direct WeasyPrint call-site)",
                "now": now,
            },
        )

        conn.execute(
            sa.text(
                "UPDATE document_templates "
                "SET current_version_id = :version_id "
                "WHERE id = :template_id"
            ),
            {"version_id": version_id, "template_id": template_id},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for key in _D9_TEMPLATE_KEYS:
        tid = conn.execute(
            sa.text(
                "SELECT id FROM document_templates "
                "WHERE company_id IS NULL AND template_key = :key"
            ),
            {"key": key},
        ).scalar_one_or_none()
        if tid is None:
            continue
        # Null the FK before deleting versions (cyclic).
        conn.execute(
            sa.text(
                "UPDATE document_templates "
                "SET current_version_id = NULL WHERE id = :tid"
            ),
            {"tid": tid},
        )
        conn.execute(
            sa.text(
                "DELETE FROM document_template_versions WHERE template_id = :tid"
            ),
            {"tid": tid},
        )
        conn.execute(
            sa.text("DELETE FROM document_templates WHERE id = :tid"),
            {"tid": tid},
        )
