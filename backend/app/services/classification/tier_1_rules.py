"""Phase R-6.1a — Tier 1 deterministic rule evaluation.

Per-tenant rule list, ordered by ``priority`` ascending; first match
wins. ``match_conditions`` is a JSONB dict of operators; all operators
within a rule are AND, all values within an operator are OR.

Operators (case-insensitive substring match for *_contains_any):
  - sender_email_in: list[str] — exact email match
  - sender_domain_in: list[str] — exact domain match against email's
    domain part (after @)
  - subject_contains_any: list[str] — case-insensitive substring on subject
  - body_contains_any: list[str] — case-insensitive substring on first
    4KB of body_text
  - thread_label_in: list[str] — provider label list intersect; reads
    from ``message_payload.labels`` (Gmail labels) or
    ``message_payload.categories`` (MS Graph). Empty list passed by
    callers means "don't filter on labels".

Empty operator key (key absent from match_conditions OR value list
empty) means "don't constrain on this dimension".

A rule with empty match_conditions ``{}`` matches every message — used
in tests + as a catch-all suppression rule.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.email_classification import TenantWorkflowEmailRule
from app.models.email_primitive import EmailMessage

logger = logging.getLogger(__name__)


# Bound body inspection — operators run against first 4KB of body_text.
_BODY_INSPECTION_LIMIT = 4096


def list_active_rules(
    db: Session, tenant_id: str
) -> list[TenantWorkflowEmailRule]:
    """Return tenant's active rules ordered by priority ascending."""
    return (
        db.query(TenantWorkflowEmailRule)
        .filter(
            TenantWorkflowEmailRule.tenant_id == tenant_id,
            TenantWorkflowEmailRule.is_active.is_(True),
        )
        .order_by(TenantWorkflowEmailRule.priority.asc())
        .all()
    )


def match(
    rule_match: dict[str, Any], message: EmailMessage
) -> bool:
    """Return True iff the message matches every operator in
    ``rule_match``. Empty dict matches every message."""
    if not isinstance(rule_match, dict):
        return False

    sender_email = (message.sender_email or "").lower()
    sender_domain = sender_email.split("@", 1)[1] if "@" in sender_email else ""
    subject = (message.subject or "").lower()
    body_text = (message.body_text or "")[:_BODY_INSPECTION_LIMIT].lower()
    payload = message.message_payload or {}
    # Gmail labels list at message_payload.labels; MS Graph categories at
    # message_payload.categories. Either may be present; union.
    labels: set[str] = set()
    for key in ("labels", "categories"):
        v = payload.get(key)
        if isinstance(v, list):
            labels.update(str(x) for x in v if isinstance(x, str))

    # sender_email_in
    sender_emails = rule_match.get("sender_email_in")
    if isinstance(sender_emails, list) and sender_emails:
        normalized = {str(e).lower() for e in sender_emails}
        if sender_email not in normalized:
            return False

    # sender_domain_in
    sender_domains = rule_match.get("sender_domain_in")
    if isinstance(sender_domains, list) and sender_domains:
        normalized = {str(d).lower().lstrip("@") for d in sender_domains}
        if sender_domain not in normalized:
            return False

    # subject_contains_any
    subject_terms = rule_match.get("subject_contains_any")
    if isinstance(subject_terms, list) and subject_terms:
        normalized = [str(t).lower() for t in subject_terms]
        if not any(t in subject for t in normalized):
            return False

    # body_contains_any
    body_terms = rule_match.get("body_contains_any")
    if isinstance(body_terms, list) and body_terms:
        normalized = [str(t).lower() for t in body_terms]
        if not any(t in body_text for t in normalized):
            return False

    # thread_label_in
    label_terms = rule_match.get("thread_label_in")
    if isinstance(label_terms, list) and label_terms:
        normalized = {str(l) for l in label_terms}
        if not labels & normalized:
            return False

    return True


def evaluate(
    db: Session, message: EmailMessage
) -> TenantWorkflowEmailRule | None:
    """Return the first-priority active rule matching ``message``, or
    None if no rule matches."""
    for rule in list_active_rules(db, message.tenant_id):
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
