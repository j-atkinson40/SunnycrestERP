"""Workflow Arc Phase 8b.5 — seed email.approval_gate_review template.

Migrates the hardcoded approval-gate email HTML from
`ApprovalGateService._build_review_email_html` into a D-2 managed
template. Single template serves all 12 agent job types via the
`job_type_label` context variable.

Idempotent: checks for existing `(company_id=NULL, template_key)`
before inserting. Matches the seed pattern in
`r23_native_signing.py`.

Revision ID: r37_approval_gate_email_template
Down Revision: r36_workflow_scope
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "r37_approval_gate_email_template"
down_revision = "r36_workflow_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.services.documents._template_seeds import _approval_gate_seeds

    now = datetime.now(timezone.utc)
    conn = op.get_bind()

    for seed in _approval_gate_seeds():
        # Idempotent guard — skip if template already seeded. Lets the
        # migration re-run cleanly on environments that may have had
        # the template inserted by a prior partial-apply attempt.
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
                "variable_schema": None,
                "css_variables": None,
                "changelog": (
                    "Phase 8b.5 seed — approval gate email migrated "
                    "from hardcoded HTML."
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
    # Remove seeded platform template — mirrors r23_native_signing
    # downgrade pattern.
    conn.execute(
        sa.text(
            "DELETE FROM document_template_versions "
            "WHERE template_id IN ("
            "SELECT id FROM document_templates "
            "WHERE template_key = :k AND company_id IS NULL)"
        ),
        {"k": "email.approval_gate_review"},
    )
    conn.execute(
        sa.text(
            "DELETE FROM document_templates "
            "WHERE template_key = :k AND company_id IS NULL"
        ),
        {"k": "email.approval_gate_review"},
    )
