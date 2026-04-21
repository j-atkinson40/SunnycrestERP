"""Workflow Arc Phase 8e.2 — seed email.portal_password_recovery template.

Portal password-recovery flow sends the recovery-token link through
the D-7 delivery layer (`delivery_service.send_email_with_template`).
This migration seeds the managed template the flow references.

Idempotent: skips insert if `(company_id=NULL, template_key=
'email.portal_password_recovery')` already exists. Matches the pattern
in r37_approval_gate_email_template + r40_aftercare_email_template.

Revision ID: r43_portal_password_email_template
Down Revision: r42_portal_users
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "r43_portal_password_email_template"
down_revision = "r42_portal_users"
branch_labels = None
depends_on = None


_BODY_TEMPLATE = """\
<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.5; color: #1a1a1a; max-width: 560px; margin: 0 auto; padding: 24px;">
<p>Hi {{ first_name }},</p>

<p>We received a request to reset your {{ tenant_name }} portal password.</p>

<p><a href="{{ reset_url }}" style="display: inline-block; padding: 12px 20px; background-color: #1E40AF; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 500;">Reset your password</a></p>

<p style="color: #525252; font-size: 14px;">This link expires in {{ expires_in }}. If you didn&rsquo;t request this, you can safely ignore this email — your password won&rsquo;t change.</p>

<p style="color: #737373; font-size: 12px; margin-top: 32px;">— {{ tenant_name }}</p>
</body>
</html>
"""


_SUBJECT_TEMPLATE = "{{ tenant_name }} — Reset your portal password"


def upgrade() -> None:
    now = datetime.now(timezone.utc)
    conn = op.get_bind()

    template_key = "email.portal_password_recovery"
    existing = conn.execute(
        sa.text(
            "SELECT id FROM document_templates "
            "WHERE template_key = :k AND company_id IS NULL "
            "AND deleted_at IS NULL LIMIT 1"
        ),
        {"k": template_key},
    ).first()
    if existing is not None:
        return

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
                :id, NULL, :template_key, 'email',
                'html',
                'Portal password recovery email (Workflow Arc Phase 8e.2).',
                FALSE, NULL, TRUE, :now, :now
            )
            """
        ),
        {
            "id": template_id,
            "template_key": template_key,
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
                :body, :subject,
                CAST(:variable_schema AS jsonb),
                NULL,
                :changelog, :now, :now
            )
            """
        ),
        {
            "id": version_id,
            "template_id": template_id,
            "body": _BODY_TEMPLATE,
            "subject": _SUBJECT_TEMPLATE,
            "variable_schema": (
                '{"first_name": {"type": "string", "required": true}, '
                '"tenant_name": {"type": "string", "required": true}, '
                '"reset_url": {"type": "string", "required": true}, '
                '"expires_in": {"type": "string", "required": true}}'
            ),
            "changelog": (
                "Phase 8e.2 seed — portal password recovery email."
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
    conn.execute(
        sa.text(
            "UPDATE document_templates SET deleted_at = :now "
            "WHERE template_key = 'email.portal_password_recovery' "
            "AND company_id IS NULL AND deleted_at IS NULL"
        ),
        {"now": datetime.now(timezone.utc)},
    )
