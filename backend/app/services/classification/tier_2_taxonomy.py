"""Phase R-6.1a — Tier 2 AI taxonomy classification.

Triggered when Tier 1 returns no match. Calls the
``email.classify_into_taxonomy`` managed prompt (Haiku, force_json)
with the tenant's taxonomy + message excerpt; the returned
``category_id`` is validated against the live taxonomy + the
mapped workflow's active state before dispatch.

Returns a tuple of:
  - matched ``TenantWorkflowEmailCategory`` row (or None)
  - confidence (or None on failure)
  - error string (or None on success / silent fallthrough)
  - reasoning string (or None)

Hallucination discipline: if the LLM returns a ``category_id`` that
isn't in the live taxonomy, the result is treated as None (cascade
falls through to Tier 3). Same for inactive or unmapped categories.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.email_classification import TenantWorkflowEmailCategory
from app.models.email_primitive import EmailMessage
from app.models.workflow import Workflow
from app.services.intelligence import intelligence_service

logger = logging.getLogger(__name__)


# Body excerpt size for AI classification prompts (sent into LLM
# context). Keep small — Haiku is fast on small inputs.
_BODY_EXCERPT_LIMIT = 2048


def list_active_taxonomy(
    db: Session, tenant_id: str
) -> list[TenantWorkflowEmailCategory]:
    """Return tenant's active taxonomy nodes ordered by parent then
    position."""
    return (
        db.query(TenantWorkflowEmailCategory)
        .filter(
            TenantWorkflowEmailCategory.tenant_id == tenant_id,
            TenantWorkflowEmailCategory.is_active.is_(True),
        )
        .order_by(
            TenantWorkflowEmailCategory.parent_id,
            TenantWorkflowEmailCategory.position,
        )
        .all()
    )


def _serialize_taxonomy(
    nodes: list[TenantWorkflowEmailCategory],
) -> list[dict[str, Any]]:
    """Compact JSON shape for the LLM prompt — id/label/description
    + parent_id for tree shape (depth-1 in v1 but tree-ready)."""
    return [
        {
            "category_id": n.id,
            "label": n.label,
            "description": n.description or "",
            "parent_id": n.parent_id,
        }
        for n in nodes
    ]


def _build_excerpt(body_text: str | None) -> str:
    if not body_text:
        return ""
    return body_text[:_BODY_EXCERPT_LIMIT]


def classify(
    db: Session,
    *,
    message: EmailMessage,
    taxonomy: list[TenantWorkflowEmailCategory],
    confidence_floor: float,
) -> tuple[
    TenantWorkflowEmailCategory | None,
    float | None,
    str | None,
    str | None,
]:
    """Run Tier 2 classification.

    Returns ``(matched_category, confidence, error_message, reasoning)``.
    ``matched_category`` is None when:
      - taxonomy is empty
      - LLM call fails (status != "success") — error_message populated
      - LLM returns ``category_id=None`` or below confidence floor
      - LLM hallucinates an id not in taxonomy (silent fallthrough)
      - Matched category lacks ``mapped_workflow_id``
      - Mapped workflow is inactive
    """
    if not taxonomy:
        return (None, None, None, None)

    serialized_taxonomy = _serialize_taxonomy(taxonomy)
    variables = {
        "subject": (message.subject or "").strip(),
        "sender_email": message.sender_email or "",
        "sender_name": message.sender_name or "",
        "body_excerpt": _build_excerpt(message.body_text),
        "taxonomy_json": serialized_taxonomy,
    }

    try:
        result = intelligence_service.execute(
            db,
            prompt_key="email.classify_into_taxonomy",
            variables=variables,
            company_id=message.tenant_id,
            caller_module="email_classification.tier_2",
            caller_entity_type="email_message",
            caller_entity_id=message.id,
        )
    except Exception as exc:
        logger.exception(
            "Tier 2 LLM call raised for message %s", message.id
        )
        return (None, None, f"tier_2_exception: {exc}", None)

    if result.status != "success":
        return (
            None,
            None,
            f"tier_2_status: {result.status} ({result.error_message or 'no_detail'})",
            None,
        )

    parsed = result.response_parsed or {}
    if not isinstance(parsed, dict):
        return (None, None, "tier_2_parse: not_object", None)

    category_id_raw = parsed.get("category_id")
    confidence_raw = parsed.get("confidence")
    reasoning = parsed.get("reasoning")
    if not isinstance(reasoning, str):
        reasoning = None

    # null category_id is a legitimate "I can't classify" signal from
    # the prompt — fall through to Tier 3 silently.
    if category_id_raw is None:
        return (None, None, None, reasoning)

    if not isinstance(category_id_raw, str):
        return (
            None,
            None,
            "tier_2_parse: category_id_not_string",
            reasoning,
        )

    try:
        confidence = float(confidence_raw) if confidence_raw is not None else 0.0
    except (TypeError, ValueError):
        confidence = 0.0

    if confidence < confidence_floor:
        return (None, confidence, None, reasoning)

    # Lookup against live taxonomy (hallucination guard).
    by_id = {n.id: n for n in taxonomy}
    category = by_id.get(category_id_raw)
    if category is None:
        logger.warning(
            "Tier 2 returned unknown category_id=%s for tenant %s; "
            "treating as fallthrough.",
            category_id_raw,
            message.tenant_id,
        )
        return (None, confidence, None, reasoning)

    if category.mapped_workflow_id is None:
        return (None, confidence, None, reasoning)

    # Workflow must be active for the tenant.
    workflow = (
        db.query(Workflow)
        .filter(
            Workflow.id == category.mapped_workflow_id,
            Workflow.is_active.is_(True),
        )
        .first()
    )
    if workflow is None:
        return (None, confidence, None, reasoning)

    return (category, confidence, None, reasoning)
