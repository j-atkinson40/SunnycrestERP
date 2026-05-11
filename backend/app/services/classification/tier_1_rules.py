"""Phase R-6.1a — Tier 1 deterministic rule evaluation.

Per-tenant rule list, ordered by ``priority`` ascending; first match
wins. ``match_conditions`` is a JSONB dict of operators; all operators
within a rule are AND, all values within an operator are OR.

R-6.2a — ``adapter_type`` discriminator on the rule selects which
source type the rule applies to. "email" (default — preserves R-6.1
backward compat for rules persisted before R-6.2a), "form", "file".

Email operators (case-insensitive substring match for *_contains_any):
  - sender_email_in: list[str]
  - sender_domain_in: list[str]
  - subject_contains_any: list[str]
  - body_contains_any: list[str] (first 4KB of body_text)
  - thread_label_in: list[str] (Gmail labels / MS Graph categories)

Form operators (R-6.2a):
  - form_slug_equals: str — match adapter config slug
  - field_value_equals: dict[field_id -> str] — exact match per field
  - field_value_contains: dict[field_id -> str] — substring per field
  - submitter_email_in: list[str]
  - submitter_domain_in: list[str]

File operators (R-6.2a):
  - file_adapter_slug_equals: str
  - content_type_in: list[str]
  - filename_contains_any: list[str] (case-insensitive)
  - uploader_email_in: list[str]
  - uploader_domain_in: list[str]

Empty operator key (key absent OR value list empty) means "don't
constrain on this dimension".

A rule with empty match_conditions ``{}`` matches every message of
its adapter_type.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.email_classification import TenantWorkflowEmailRule
from app.models.email_primitive import EmailMessage

logger = logging.getLogger(__name__)


_BODY_INSPECTION_LIMIT = 4096


def list_active_rules(
    db: Session,
    tenant_id: str,
    *,
    adapter_type: str = "email",
) -> list[TenantWorkflowEmailRule]:
    """Return tenant's active rules ordered by priority ascending.

    Filters by ``adapter_type`` (default "email" for R-6.1 backward
    compat). Pre-R-6.2a rules carry no adapter_type column and
    backfill to "email" via server_default in r94.
    """
    return (
        db.query(TenantWorkflowEmailRule)
        .filter(
            TenantWorkflowEmailRule.tenant_id == tenant_id,
            TenantWorkflowEmailRule.is_active.is_(True),
            TenantWorkflowEmailRule.adapter_type == adapter_type,
        )
        .order_by(TenantWorkflowEmailRule.priority.asc())
        .all()
    )


# ── Email matching ──────────────────────────────────────────────────


def match(
    rule_match: dict[str, Any], message: EmailMessage
) -> bool:
    """Return True iff ``message`` matches every email operator.
    Empty dict matches every message of email adapter_type."""
    if not isinstance(rule_match, dict):
        return False

    sender_email = (message.sender_email or "").lower()
    sender_domain = sender_email.split("@", 1)[1] if "@" in sender_email else ""
    subject = (message.subject or "").lower()
    body_text = (message.body_text or "")[:_BODY_INSPECTION_LIMIT].lower()
    payload = message.message_payload or {}
    labels: set[str] = set()
    for key in ("labels", "categories"):
        v = payload.get(key)
        if isinstance(v, list):
            labels.update(str(x) for x in v if isinstance(x, str))

    sender_emails = rule_match.get("sender_email_in")
    if isinstance(sender_emails, list) and sender_emails:
        normalized = {str(e).lower() for e in sender_emails}
        if sender_email not in normalized:
            return False

    sender_domains = rule_match.get("sender_domain_in")
    if isinstance(sender_domains, list) and sender_domains:
        normalized = {str(d).lower().lstrip("@") for d in sender_domains}
        if sender_domain not in normalized:
            return False

    subject_terms = rule_match.get("subject_contains_any")
    if isinstance(subject_terms, list) and subject_terms:
        normalized = [str(t).lower() for t in subject_terms]
        if not any(t in subject for t in normalized):
            return False

    body_terms = rule_match.get("body_contains_any")
    if isinstance(body_terms, list) and body_terms:
        normalized = [str(t).lower() for t in body_terms]
        if not any(t in body_text for t in normalized):
            return False

    label_terms = rule_match.get("thread_label_in")
    if isinstance(label_terms, list) and label_terms:
        normalized = {str(l) for l in label_terms}
        if not labels & normalized:
            return False

    return True


def evaluate(
    db: Session, message: EmailMessage
) -> TenantWorkflowEmailRule | None:
    """Return the first-priority active email rule matching
    ``message``, or None if no rule matches."""
    for rule in list_active_rules(db, message.tenant_id, adapter_type="email"):
        try:
            if match(rule.match_conditions or {}, message):
                return rule
        except Exception:
            logger.exception(
                "Tier 1 rule %s evaluation raised; treating as no-match",
                rule.id,
            )
            continue
    return None


# ── Form matching (R-6.2a) ──────────────────────────────────────────


def match_form(
    rule_match: dict[str, Any],
    *,
    form_slug: str,
    submitted_data: dict[str, Any],
    submitter_metadata: dict[str, Any],
) -> bool:
    """Return True iff form-shaped source matches every form operator."""
    if not isinstance(rule_match, dict):
        return False

    submitter_email = ""
    if isinstance(submitted_data, dict):
        # Canonical field id for the family contact email per the seeded
        # personalization-request schema. Fall back to common alternates.
        for key in ("family_contact_email", "submitter_email", "email"):
            v = submitted_data.get(key)
            if isinstance(v, str) and v:
                submitter_email = v.lower()
                break
    if not submitter_email and isinstance(submitter_metadata, dict):
        v = submitter_metadata.get("submitter_email")
        if isinstance(v, str):
            submitter_email = v.lower()
    submitter_domain = (
        submitter_email.split("@", 1)[1] if "@" in submitter_email else ""
    )

    slug_eq = rule_match.get("form_slug_equals")
    if isinstance(slug_eq, str) and slug_eq:
        if form_slug != slug_eq:
            return False

    field_eq = rule_match.get("field_value_equals")
    if isinstance(field_eq, dict) and field_eq:
        for field_id, expected in field_eq.items():
            if not isinstance(field_id, str):
                continue
            raw = (submitted_data or {}).get(field_id)
            if raw != expected:
                return False

    field_contains = rule_match.get("field_value_contains")
    if isinstance(field_contains, dict) and field_contains:
        for field_id, needle in field_contains.items():
            if not isinstance(field_id, str) or not isinstance(needle, str):
                continue
            raw = (submitted_data or {}).get(field_id)
            if not isinstance(raw, str):
                return False
            if needle.lower() not in raw.lower():
                return False

    submitter_emails = rule_match.get("submitter_email_in")
    if isinstance(submitter_emails, list) and submitter_emails:
        normalized = {str(e).lower() for e in submitter_emails}
        if submitter_email not in normalized:
            return False

    submitter_domains = rule_match.get("submitter_domain_in")
    if isinstance(submitter_domains, list) and submitter_domains:
        normalized = {str(d).lower().lstrip("@") for d in submitter_domains}
        if submitter_domain not in normalized:
            return False

    return True


def evaluate_form(
    db: Session,
    *,
    tenant_id: str,
    form_slug: str,
    submitted_data: dict[str, Any],
    submitter_metadata: dict[str, Any],
) -> TenantWorkflowEmailRule | None:
    """Return the first-priority active form rule matching the
    submission, or None if no rule matches."""
    for rule in list_active_rules(db, tenant_id, adapter_type="form"):
        try:
            if match_form(
                rule.match_conditions or {},
                form_slug=form_slug,
                submitted_data=submitted_data,
                submitter_metadata=submitter_metadata,
            ):
                return rule
        except Exception:
            logger.exception(
                "Tier 1 form rule %s evaluation raised; treating as "
                "no-match",
                rule.id,
            )
            continue
    return None


# ── File matching (R-6.2a) ──────────────────────────────────────────


def match_file(
    rule_match: dict[str, Any],
    *,
    file_slug: str,
    content_type: str,
    original_filename: str,
    uploader_metadata: dict[str, Any],
) -> bool:
    """Return True iff file-shaped source matches every file operator."""
    if not isinstance(rule_match, dict):
        return False

    uploader_email = ""
    if isinstance(uploader_metadata, dict):
        for key in ("uploader_email", "submitter_email", "email"):
            v = uploader_metadata.get(key)
            if isinstance(v, str) and v:
                uploader_email = v.lower()
                break
    uploader_domain = (
        uploader_email.split("@", 1)[1] if "@" in uploader_email else ""
    )

    slug_eq = rule_match.get("file_adapter_slug_equals")
    if isinstance(slug_eq, str) and slug_eq:
        if file_slug != slug_eq:
            return False

    types = rule_match.get("content_type_in")
    if isinstance(types, list) and types:
        normalized = {str(t).lower() for t in types}
        if (content_type or "").lower() not in normalized:
            return False

    filename_contains = rule_match.get("filename_contains_any")
    if isinstance(filename_contains, list) and filename_contains:
        normalized = [str(t).lower() for t in filename_contains]
        lower_filename = (original_filename or "").lower()
        if not any(t in lower_filename for t in normalized):
            return False

    uploader_emails = rule_match.get("uploader_email_in")
    if isinstance(uploader_emails, list) and uploader_emails:
        normalized = {str(e).lower() for e in uploader_emails}
        if uploader_email not in normalized:
            return False

    uploader_domains = rule_match.get("uploader_domain_in")
    if isinstance(uploader_domains, list) and uploader_domains:
        normalized = {str(d).lower().lstrip("@") for d in uploader_domains}
        if uploader_domain not in normalized:
            return False

    return True


def evaluate_file(
    db: Session,
    *,
    tenant_id: str,
    file_slug: str,
    content_type: str,
    original_filename: str,
    uploader_metadata: dict[str, Any],
) -> TenantWorkflowEmailRule | None:
    """Return the first-priority active file rule matching the upload,
    or None if no rule matches."""
    for rule in list_active_rules(db, tenant_id, adapter_type="file"):
        try:
            if match_file(
                rule.match_conditions or {},
                file_slug=file_slug,
                content_type=content_type,
                original_filename=original_filename,
                uploader_metadata=uploader_metadata,
            ):
                return rule
        except Exception:
            logger.exception(
                "Tier 1 file rule %s evaluation raised; treating as "
                "no-match",
                rule.id,
            )
            continue
    return None
