"""Workflow Arc Phase 8d — seed email.fh_aftercare_7day template.

Replaces the phantom `template="aftercare_7day"` reference in the
pre-8d `wf_fh_aftercare_7day` seed. That key never existed in the
D-2 template registry — a send_email step using it would silently
produce no output. Phase 8d's aftercare_adapter renders this
managed template via `delivery_service.send_email_with_template`
on the triage approve action.

Idempotent: skips insert if `(company_id=NULL, template_key=
'email.fh_aftercare_7day')` already exists. Matches the pattern in
`r37_approval_gate_email_template.py`.

Revision ID: r40_aftercare_email_template
Down Revision: r39_catalog_publication_state
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "r40_aftercare_email_template"
down_revision = "r39_catalog_publication_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.services.documents._template_seeds import _aftercare_seeds

    now = datetime.now(timezone.utc)
    conn = op.get_bind()

    for seed in _aftercare_seeds():
        existing = conn.execute(
            sa.text(
                "SELECT id FROM document_templates "
                "WHERE template_key = :k AND company_id IS NULL "
                "AND deleted_at IS NULL "
                "LIMIT 1"
            ),
            {"k": seed["template_key"]},
        ).first()
        if existing is not None:
            continue

        template_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
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
                "description": seed["description"],
                "supports_variants": seed["supports_variants"],
                "now": now,
            },
        )
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
                    NULL,
                    :changelog, :now, :now
                )
                """
            ),
            {
                "id": version_id,
                "template_id": template_id,
                "body_template": seed["body_template"],
                "subject_template": seed.get("subject_template"),
                "variable_schema": (
                    '{"family_surname": {"type": "string", "required": true}, '
                    '"funeral_home_name": {"type": "string", "required": false}}'
                ),
                "changelog": (
                    "Phase 8d seed — FH aftercare 7-day email template, "
                    "replaces phantom `aftercare_7day` template key."
                ),
                "now": now,
            },
        )
        conn.execute(
            sa.text(
                "UPDATE document_templates SET current_version_id = :v "
                "WHERE id = :t"
            ),
            {"v": version_id, "t": template_id},
        )


def downgrade() -> None:
    conn = op.get_bind()
    # Soft delete — matches the D-2 registry's deleted_at convention.
    conn.execute(
        sa.text(
            "UPDATE document_templates SET deleted_at = :now "
            "WHERE template_key = 'email.fh_aftercare_7day' "
            "AND company_id IS NULL AND deleted_at IS NULL"
        ),
        {"now": datetime.now(timezone.utc)},
    )
