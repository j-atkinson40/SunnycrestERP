"""Workflow Arc Phase 8e.2.1 — seed email.portal_invite template.

Distinct from `email.portal_password_recovery` (r43). Onboarding copy
("Welcome to the <tenant> driver portal. Set up your account to see
today's deliveries, mark stops complete, and log mileage.") vs. the
recovery template's "reset your password" framing.

Idempotent: skips insert if `(company_id=NULL, template_key=
'email.portal_invite')` already exists. Same pattern as r43.

Revision ID: r45_portal_invite_email_template
Down Revision: r44_drivers_employee_id_nullable
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "r45_portal_invite_email_template"
down_revision = "r44_drivers_employee_id_nullable"
branch_labels = None
depends_on = None


_BODY_TEMPLATE = """\
<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.5; color: #1a1a1a; max-width: 560px; margin: 0 auto; padding: 24px;">
<p>Hi {{ first_name }},</p>

<p>You've been invited to the <strong>{{ tenant_name }}</strong> driver portal.</p>

<p>Once you're set up, you can see today's deliveries, mark stops complete, and log mileage — all from your phone.</p>

<p><a href="{{ invite_url }}" style="display: inline-block; padding: 12px 20px; background-color: #1E40AF; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 500;">Set up your account</a></p>

<p style="color: #525252; font-size: 14px;">This link expires in {{ expires_in }}. If you weren&rsquo;t expecting this invitation, you can safely ignore this email.</p>

<p style="color: #737373; font-size: 12px; margin-top: 32px;">— {{ tenant_name }}</p>
</body>
</html>
"""


_SUBJECT_TEMPLATE = "Welcome to the {{ tenant_name }} driver portal"


def upgrade() -> None:
    now = datetime.now(timezone.utc)
    conn = op.get_bind()

    template_key = "email.portal_invite"
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
                'Portal user invite email — first-time password setup (Phase 8e.2.1).',
                FALSE, NULL, TRUE, :now, :now
            )
            """
        ),
        {"id": template_id, "template_key": template_key, "now": now},
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
                '"invite_url": {"type": "string", "required": true}, '
                '"expires_in": {"type": "string", "required": true}}'
            ),
            "changelog": (
                "Phase 8e.2.1 seed — portal user invite email (distinct "
                "from password recovery: onboarding copy)."
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
            "WHERE template_key = 'email.portal_invite' "
            "AND company_id IS NULL AND deleted_at IS NULL"
        ),
        {"now": datetime.now(timezone.utc)},
    )
