"""Seed Phase 1E managed email templates for Personalization Studio.

Phase W-4d Personalization Studio Phase 1E — seeds two managed email
templates against the canonical D-2 DocumentTemplate registry:

  1. ``email.personalization_studio_family_approval_request``
     — sent at ``request_family_approval`` flow (Phase 1E send pathway).
     Magic-link CTA routes to the family portal Space rendering at
     ``/portal/{tenant-slug}/personalization-studio/family-approval/{token}``
     per §3.26.11.9 + Path B substrate consumption.

  2. ``email.personalization_studio_share_granted``
     — Phase 1E ships substrate; Phase 1F consumes via canonical
     DocumentShare grant fired at ``approve`` outcome commit handler.
     Body notifies partner Mfg tenant admins that the FH-side approved
     memorial vault canvas has been shared for fulfillment.

Idempotent seed canonical (Phase 6 + Phase 8b + Phase 8d.1 +
Calendar Step 5.1 pattern):

  - Fresh install (no row matching template_key)        → create v1 active
  - Exactly 1 version + body+subject MATCHES seed       → no-op
  - Exactly 1 version + body or subject DIFFERS         → deactivate v1,
                                                          create v2 active
                                                          (platform update)
  - Multiple versions exist (admin has customized)      → skip with
                                                          warning log;
                                                          manual reconcile

Run:
    cd backend && source .venv/bin/activate
    DATABASE_URL=<url> python scripts/seed_personalization_studio_phase1e_email_templates.py
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
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


# ─────────────────────────────────────────────────────────────────────
# Template 1 — family_approval_request (send pathway shipping Phase 1E)
# ─────────────────────────────────────────────────────────────────────


_FAMILY_APPROVAL_REQUEST_KEY = "email.personalization_studio_family_approval_request"

_FAMILY_APPROVAL_REQUEST_SUBJECT = (
    "Please review the memorial vault for {{ decedent_name }}"
)

# Inline-styled HTML — email clients strip <style> tags inconsistently.
# Tenant-branded surface lives at the magic-link landing page; this email
# stays simple + warm + low-noise, matching the family-facing tone per
# §3.26.11.12.19 + §14.10.5 magic-link contextual surface canon.
_FAMILY_APPROVAL_REQUEST_BODY = """\
<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #1a1a1a; max-width: 560px; margin: 0 auto; padding: 24px;">
<p>Hello,</p>

<p>{{ fh_director_name }} at {{ tenant_name }} has prepared a memorial vault for <strong>{{ decedent_name }}</strong> and would like your approval before the order is placed.</p>

<p>Please take a moment to review the design — including the vault, finishes, and any personalized text — and let us know your decision.</p>

<p style="margin: 32px 0;"><a href="{{ approval_url }}" style="display: inline-block; padding: 14px 28px; background-color: #1E40AF; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 500;">Review the memorial design</a></p>

<p style="color: #525252; font-size: 14px;">If you have questions or would like to discuss any of the details, please reply to this email or call {{ tenant_name }} directly.</p>

<p style="color: #737373; font-size: 13px; margin-top: 32px;">{% if expires_in_copy %}This review link {{ expires_in_copy }}.{% endif %} Thank you for trusting {{ tenant_name }} during this time.</p>

<p style="color: #737373; font-size: 12px; margin-top: 24px;">— Sent on behalf of {{ tenant_name }}</p>
</body>
</html>
"""

_FAMILY_APPROVAL_REQUEST_SCHEMA: dict = {
    "decedent_name": {"type": "string", "required": True},
    "fh_director_name": {"type": "string", "required": True},
    "tenant_name": {"type": "string", "required": True},
    "approval_url": {"type": "string", "required": True},
    "expires_in_copy": {"type": "string", "required": False},
}

_FAMILY_APPROVAL_REQUEST_DESCRIPTION = (
    "Phase 1E Personalization Studio — family approval request email. "
    "Sent at family_approval.request_family_approval(); magic-link CTA "
    "routes to the family portal Space rendering at "
    "/portal/{tenant-slug}/personalization-studio/family-approval/{token} "
    "per §3.26.11.9 + Path B substrate."
)

_FAMILY_APPROVAL_REQUEST_CHANGELOG_V1 = (
    "Phase 1E Personalization Studio seed — initial template for "
    "family-approval-request emails sent to non-Bridgeable family "
    "recipients of the magic-link contextual surface."
)


# ─────────────────────────────────────────────────────────────────────
# Template 2 — share_granted (substrate; Phase 1F consumes)
# ─────────────────────────────────────────────────────────────────────


_SHARE_GRANTED_KEY = "email.personalization_studio_share_granted"

_SHARE_GRANTED_SUBJECT = (
    "{{ owner_tenant_name }} shared a memorial design for fulfillment"
)

_SHARE_GRANTED_BODY = """\
<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.5; color: #1a1a1a; max-width: 560px; margin: 0 auto; padding: 24px;">
<p>Hi {{ recipient_first_name }},</p>

<p><strong>{{ owner_tenant_name }}</strong> has approved a memorial vault design with the family for <strong>{{ decedent_name }}</strong> and shared it with <strong>{{ partner_tenant_name }}</strong> for fulfillment.</p>

<p>You can view the approved design — including the vault product, personalization details, and any production notes — from the shared canvas in your platform.</p>

<p><a href="{{ canvas_url }}" style="display: inline-block; padding: 12px 20px; background-color: #1E40AF; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 500;">View shared canvas</a></p>

<p style="color: #525252; font-size: 14px;">The canvas is read-only — production updates flow back to {{ owner_tenant_name }} per the canonical cross-tenant share contract.</p>

<p style="color: #737373; font-size: 12px; margin-top: 32px;">— Bridgeable on behalf of {{ owner_tenant_name }}</p>
</body>
</html>
"""

_SHARE_GRANTED_SCHEMA: dict = {
    "owner_tenant_name": {"type": "string", "required": True},
    "partner_tenant_name": {"type": "string", "required": True},
    "recipient_first_name": {"type": "string", "required": True},
    "decedent_name": {"type": "string", "required": True},
    "canvas_url": {"type": "string", "required": True},
}

_SHARE_GRANTED_DESCRIPTION = (
    "Phase 1E Personalization Studio — DocumentShare-grant notification "
    "email substrate. Phase 1F wires DocumentShare grant fire at "
    "approve outcome commit handler; this template renders the partner-"
    "tenant admin notification with magic-link to the shared canvas."
)

_SHARE_GRANTED_CHANGELOG_V1 = (
    "Phase 1E Personalization Studio seed — substrate template for "
    "Phase 1F DocumentShare-grant notification email."
)


_PLATFORM_UPDATE_CHANGELOG = (
    "Platform update — Phase 1E Personalization Studio template refreshed."
)


# ─────────────────────────────────────────────────────────────────────
# Idempotent seed state machine (Phase 6 + 8b + 8d.1 + Step 5.1 pattern)
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _TemplateSpec:
    """Canonical template-seed input bundle."""

    key: str
    subject: str
    body: str
    schema: dict
    description: str
    changelog_v1: str


_TEMPLATES: tuple[_TemplateSpec, ...] = (
    _TemplateSpec(
        key=_FAMILY_APPROVAL_REQUEST_KEY,
        subject=_FAMILY_APPROVAL_REQUEST_SUBJECT,
        body=_FAMILY_APPROVAL_REQUEST_BODY,
        schema=_FAMILY_APPROVAL_REQUEST_SCHEMA,
        description=_FAMILY_APPROVAL_REQUEST_DESCRIPTION,
        changelog_v1=_FAMILY_APPROVAL_REQUEST_CHANGELOG_V1,
    ),
    _TemplateSpec(
        key=_SHARE_GRANTED_KEY,
        subject=_SHARE_GRANTED_SUBJECT,
        body=_SHARE_GRANTED_BODY,
        schema=_SHARE_GRANTED_SCHEMA,
        description=_SHARE_GRANTED_DESCRIPTION,
        changelog_v1=_SHARE_GRANTED_CHANGELOG_V1,
    ),
)


def _seed_template(db: Session, spec: _TemplateSpec) -> dict[str, int]:
    """Apply the Phase 6 + 8b + 8d.1 + Step 5.1 idempotent state machine.

    Returns counters dict scoped to one template.
    """
    counters = {
        "created": 0,
        "noop_matched": 0,
        "platform_update": 0,
        "skipped_customized": 0,
    }
    now = datetime.now(timezone.utc)

    template = (
        db.query(DocumentTemplate)
        .filter(
            DocumentTemplate.company_id.is_(None),
            DocumentTemplate.template_key == spec.key,
            DocumentTemplate.deleted_at.is_(None),
        )
        .first()
    )

    if template is None:
        template = DocumentTemplate(
            company_id=None,
            template_key=spec.key,
            document_type="email",
            output_format="html",
            description=spec.description,
            is_active=True,
        )
        db.add(template)
        db.flush()
        version = DocumentTemplateVersion(
            template_id=template.id,
            version_number=1,
            status="active",
            body_template=spec.body,
            subject_template=spec.subject,
            variable_schema=spec.schema,
            changelog=spec.changelog_v1,
            activated_at=now,
        )
        db.add(version)
        db.flush()
        template.current_version_id = version.id
        db.commit()
        counters["created"] += 1
        return counters

    versions = (
        db.query(DocumentTemplateVersion)
        .filter(DocumentTemplateVersion.template_id == template.id)
        .all()
    )

    if len(versions) > 1:
        _log.warning(
            "Tenant has custom version of %s (%d versions exist); "
            "skipping platform update. Reconcile manually via the "
            "document templates admin UI.",
            spec.key,
            len(versions),
        )
        counters["skipped_customized"] += 1
        return counters

    if len(versions) == 1:
        v1 = versions[0]
        if (
            v1.body_template == spec.body
            and v1.subject_template == spec.subject
        ):
            counters["noop_matched"] += 1
            return counters
        v1.status = "retired"
        new_version = DocumentTemplateVersion(
            template_id=template.id,
            version_number=v1.version_number + 1,
            status="active",
            body_template=spec.body,
            subject_template=spec.subject,
            variable_schema=spec.schema,
            changelog=_PLATFORM_UPDATE_CHANGELOG,
            activated_at=now,
        )
        db.add(new_version)
        db.flush()
        template.current_version_id = new_version.id
        db.commit()
        counters["platform_update"] += 1
        return counters

    # Defensive recovery — template row exists with zero versions.
    new_version = DocumentTemplateVersion(
        template_id=template.id,
        version_number=1,
        status="active",
        body_template=spec.body,
        subject_template=spec.subject,
        variable_schema=spec.schema,
        changelog=spec.changelog_v1,
        activated_at=now,
    )
    db.add(new_version)
    db.flush()
    template.current_version_id = new_version.id
    db.commit()
    counters["created"] += 1
    return counters


def seed_phase1e_email_templates(db: Session) -> dict[str, dict[str, int]]:
    """Seed both Phase 1E templates idempotently. Returns per-key counters.

    Importable for tests + CI hooks. CLI wraps in main().
    """
    return {spec.key: _seed_template(db, spec) for spec in _TEMPLATES}


def main() -> None:
    db = SessionLocal()
    try:
        all_counters = seed_phase1e_email_templates(db)
        for key, counters in all_counters.items():
            print(
                f"[seed-personalization-studio-phase1e] {key}: "
                f"created={counters['created']} "
                f"noop_matched={counters['noop_matched']} "
                f"platform_update={counters['platform_update']} "
                f"skipped_customized={counters['skipped_customized']}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
