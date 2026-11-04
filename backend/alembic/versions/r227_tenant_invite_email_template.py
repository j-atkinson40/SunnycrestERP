"""Seed `email.tenant_user_invite` — the only channel the invite link travels.

Payroll 2, ruling 4. The invite link is a CREDENTIAL: whoever holds it sets her
password. So it goes to her inbox and nowhere else.

⚠️ **THIS IS WHY THE INVITE ENDPOINT CANNOT RETURN THE LINK TO THE ADMIN, AND
WHY THAT MAKES THIS MIGRATION LOAD-BEARING RATHER THAN COSMETIC.** James's
ruling is *"Admin never sees or sets it."* An admin holding the link can set her
password, which is the same power as being handed it — so a response body
carrying the link would satisfy the letter of "no password in a response" and
break the thing the ruling protects. With the link emailed only, the invite
endpoint has no credential to leak, and the email path stops being a
convenience.

Consequence, stated because it is a real operational cost: **if email delivery
is not configured for a tenant, inviting a user cannot complete.** The route
surfaces that as a failure rather than falling back to returning the link, and
`POST /users` with a temporary password remains available for exactly that case
(it is one of the six password-in-body callers ruling 4 deliberately keeps).

Idempotent on `(company_id=NULL, template_key)`, the same shape as `r37`, `r40`
and `r43`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "r227_tenant_invite_email_template"
down_revision = "r226_tenant_user_invites"
branch_labels = None
depends_on = None

TEMPLATE_KEY = "email.tenant_user_invite"

_BODY_TEMPLATE = """\
<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.5; color: #1a1a1a; max-width: 560px; margin: 0 auto; padding: 24px;">
<p>Hi {{ first_name }},</p>

<p>{{ inviter_name }} has set up an account for you on {{ tenant_name }}.</p>

<p>Use the link below to choose your own password. Nobody else &mdash; including whoever set the account up &mdash; can see or set it.</p>

<p><a href="{{ invite_url }}" style="display: inline-block; padding: 12px 20px; background-color: #9C5640; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 500;">Set your password</a></p>

<p style="color: #525252; font-size: 14px;">This link works once and expires in {{ expires_in }}. If it has already expired, ask {{ inviter_name }} to send you another.</p>

<p style="color: #525252; font-size: 14px;">If you weren&rsquo;t expecting this, you can ignore it &mdash; the account cannot be used until the link is opened.</p>

<p style="color: #737373; font-size: 12px; margin-top: 32px;">&mdash; {{ tenant_name }}</p>
</body>
</html>
"""

_SUBJECT_TEMPLATE = "{{ tenant_name }} — set up your account"


def upgrade() -> None:
    now = datetime.now(timezone.utc)
    conn = op.get_bind()

    existing = conn.execute(
        sa.text(
            "SELECT id FROM document_templates "
            "WHERE template_key = :k AND company_id IS NULL "
            "AND deleted_at IS NULL LIMIT 1"
        ),
        {"k": TEMPLATE_KEY},
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
                'Tenant user invite email (Payroll 2 ruling 4). Carries the '
                'single-use invite link; the only channel it travels.',
                FALSE, NULL, TRUE, :now, :now
            )
            """
        ),
        {"id": template_id, "template_key": TEMPLATE_KEY, "now": now},
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
                '"inviter_name": {"type": "string", "required": true}, '
                '"tenant_name": {"type": "string", "required": true}, '
                '"invite_url": {"type": "string", "required": true}, '
                '"expires_in": {"type": "string", "required": true}}'
            ),
            "changelog": "Payroll 2 ruling 4 seed — tenant user invite email.",
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
    row = conn.execute(
        sa.text(
            "SELECT id FROM document_templates "
            "WHERE template_key = :k AND company_id IS NULL LIMIT 1"
        ),
        {"k": TEMPLATE_KEY},
    ).first()
    if row is None:
        return
    conn.execute(
        sa.text("UPDATE document_templates SET current_version_id = NULL "
                "WHERE id = :t"),
        {"t": row[0]},
    )
    conn.execute(
        sa.text("DELETE FROM document_template_versions WHERE template_id = :t"),
        {"t": row[0]},
    )
    conn.execute(
        sa.text("DELETE FROM document_templates WHERE id = :t"), {"t": row[0]}
    )
