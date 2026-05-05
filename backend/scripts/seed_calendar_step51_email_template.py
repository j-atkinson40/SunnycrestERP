"""Seed Calendar Step 5.1 managed email template.

Phase W-4b Layer 1 Calendar Step 5.1 — bounded follow-on closure of
Calendar Step 5 substrate. Seeds the managed email template
``email.calendar_consent_upgrade_request`` used by
``ptr_consent_service.request_upgrade(send_email=True)`` to dispatch
cross-tenant calendar consent upgrade emails to partner tenant admins.

Idempotent seed canonical (Phase 6 + Phase 8b + Phase 8d.1 pattern):
  - Fresh install (no row matching template_key)        → create v1 active
  - Exactly 1 version + body+subject MATCHES seed       → no-op
  - Exactly 1 version + body or subject DIFFERS         → deactivate v1,
                                                          create v2 active
                                                          (platform update)
  - Multiple versions exist (admin has customized)      → skip with
                                                          warning log;
                                                          manual reconcile
                                                          via Intelligence
                                                          admin UI

This preserves admin customizations without separate source-tracking
infrastructure. Future maintainers: the "multiple versions" branch is
deliberate — DO NOT change it to overwrite.

Template shape parallels ``email.portal_invite`` (r45) +
``email.portal_password_recovery`` (r43) canonical — notification-
style email to admin recipients with magic-link URL to a settings
page.

Run:
    cd backend && source .venv/bin/activate
    DATABASE_URL=<url> python scripts/seed_calendar_step51_email_template.py
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.document_template import (
    DocumentTemplate,
    DocumentTemplateVersion,
)


_log = logging.getLogger(__name__)


# ── Template shape ──────────────────────────────────────────────────


_TEMPLATE_KEY = "email.calendar_consent_upgrade_request"


# Subject is Jinja-templatable per r43/r45 canonical. Bounded to
# ≤120 chars (typical email-client truncation point) per email canon.
_SUBJECT_TEMPLATE = (
    "{{ requesting_tenant_name }} requests calendar consent upgrade"
)


# Body parallels r45 portal_invite shape verbatim — HTML wrapper +
# tenant identity context + clear CTA + privacy/expiration footer.
# Inline styles only (email clients strip <style> tags inconsistently).
_BODY_TEMPLATE = """\
<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.5; color: #1a1a1a; max-width: 560px; margin: 0 auto; padding: 24px;">
<p>Hi {{ recipient_first_name }},</p>

<p><strong>{{ requesting_tenant_name }}</strong> has requested calendar full-details consent for the {{ relationship_type }} relationship between <strong>{{ requesting_tenant_name }}</strong> and <strong>{{ partner_tenant_name }}</strong>.</p>

<p>If you accept, both tenants will see full meeting details (subjects, locations, attendee counts) on cross-tenant calendar events. If you decline or take no action, calendar events between the two tenants continue to surface as free/busy windows only.</p>

<p>Either tenant can revoke this consent at any time.</p>

<p><a href="{{ consent_upgrade_url }}" style="display: inline-block; padding: 12px 20px; background-color: #1E40AF; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 500;">Review consent request</a></p>

<p style="color: #525252; font-size: 14px;">{% if expires_in_copy %}This request {{ expires_in_copy }}.{% endif %} You can review pending consent requests at any time from <em>Settings &rarr; Calendar &rarr; Free/busy consent</em>.</p>

<p style="color: #737373; font-size: 12px; margin-top: 32px;">— Bridgeable on behalf of {{ requesting_tenant_name }}</p>
</body>
</html>
"""


_VARIABLE_SCHEMA: dict = {
    "requesting_tenant_name": {"type": "string", "required": True},
    "partner_tenant_name": {"type": "string", "required": True},
    "recipient_first_name": {"type": "string", "required": True},
    "consent_upgrade_url": {"type": "string", "required": True},
    "relationship_type": {"type": "string", "required": True},
    "expires_in_copy": {"type": "string", "required": False},
}


_DESCRIPTION = (
    "Phase W-4b Calendar Step 5.1 — cross-tenant calendar consent "
    "upgrade request email. Sent to partner tenant admins when "
    "ptr_consent_service.request_upgrade(send_email=True) fires "
    "(opt-in per Q1 confirmed pre-build). Per-recipient DocumentDelivery "
    "row per admin per Q2. Best-effort discipline: send failure NEVER "
    "blocks consent state mutation OR in-app notify per Step 4.1 contract."
)


_CHANGELOG_V1 = (
    "Phase W-4b Calendar Step 5.1 seed — initial template for cross-"
    "tenant calendar consent upgrade request emails."
)


_CHANGELOG_PLATFORM_UPDATE = (
    "Platform update — Calendar Step 5.1 template body refreshed."
)


# ── Idempotent seed ─────────────────────────────────────────────────


def _seed_template(db: Session) -> dict[str, int]:
    """Apply the Phase 6 + 8b + 8d.1 idempotent seed state machine.

    Returns a counters dict so callers (CI, deploy hooks, manual
    invocation) can surface what changed. Counter keys: ``created``,
    ``noop_matched``, ``platform_update``, ``skipped_customized``.
    """
    counters = {
        "created": 0,
        "noop_matched": 0,
        "platform_update": 0,
        "skipped_customized": 0,
    }
    now = datetime.now(timezone.utc)

    # Resolve existing platform-scope template (company_id IS NULL).
    template = (
        db.query(DocumentTemplate)
        .filter(
            DocumentTemplate.company_id.is_(None),
            DocumentTemplate.template_key == _TEMPLATE_KEY,
            DocumentTemplate.deleted_at.is_(None),
        )
        .first()
    )

    if template is None:
        # Fresh install — create template + v1 active.
        template = DocumentTemplate(
            company_id=None,
            template_key=_TEMPLATE_KEY,
            document_type="email",
            output_format="html",
            description=_DESCRIPTION,
            is_active=True,
        )
        db.add(template)
        db.flush()
        version = DocumentTemplateVersion(
            template_id=template.id,
            version_number=1,
            status="active",
            body_template=_BODY_TEMPLATE,
            subject_template=_SUBJECT_TEMPLATE,
            variable_schema=_VARIABLE_SCHEMA,
            changelog=_CHANGELOG_V1,
            activated_at=now,
        )
        db.add(version)
        db.flush()
        template.current_version_id = version.id
        db.commit()
        counters["created"] += 1
        return counters

    # Template exists — check version count.
    versions = (
        db.query(DocumentTemplateVersion)
        .filter(DocumentTemplateVersion.template_id == template.id)
        .all()
    )

    if len(versions) > 1:
        # Admin has customized — skip with warning.
        _log.warning(
            "Tenant has custom version of %s (%d versions exist); "
            "skipping platform update. Reconcile manually via the "
            "document templates admin UI.",
            _TEMPLATE_KEY,
            len(versions),
        )
        counters["skipped_customized"] += 1
        return counters

    if len(versions) == 1:
        v1 = versions[0]
        if (
            v1.body_template == _BODY_TEMPLATE
            and v1.subject_template == _SUBJECT_TEMPLATE
        ):
            counters["noop_matched"] += 1
            return counters
        # Platform update: deactivate v1, create v2 active.
        v1.status = "retired"
        new_version = DocumentTemplateVersion(
            template_id=template.id,
            version_number=v1.version_number + 1,
            status="active",
            body_template=_BODY_TEMPLATE,
            subject_template=_SUBJECT_TEMPLATE,
            variable_schema=_VARIABLE_SCHEMA,
            changelog=_CHANGELOG_PLATFORM_UPDATE,
            activated_at=now,
        )
        db.add(new_version)
        db.flush()
        template.current_version_id = new_version.id
        db.commit()
        counters["platform_update"] += 1
        return counters

    # len == 0 (template exists with no versions — defensive recovery).
    new_version = DocumentTemplateVersion(
        template_id=template.id,
        version_number=1,
        status="active",
        body_template=_BODY_TEMPLATE,
        subject_template=_SUBJECT_TEMPLATE,
        variable_schema=_VARIABLE_SCHEMA,
        changelog=_CHANGELOG_V1,
        activated_at=now,
    )
    db.add(new_version)
    db.flush()
    template.current_version_id = new_version.id
    db.commit()
    counters["created"] += 1
    return counters


def main() -> None:
    db = SessionLocal()
    try:
        counters = _seed_template(db)
        print(
            f"[seed-calendar-step51-email-template] "
            f"created={counters['created']} "
            f"noop_matched={counters['noop_matched']} "
            f"platform_update={counters['platform_update']} "
            f"skipped_customized={counters['skipped_customized']}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
