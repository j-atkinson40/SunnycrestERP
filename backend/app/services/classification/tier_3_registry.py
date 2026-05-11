"""Phase R-6.1a — Tier 3 AI workflow registry selection (last resort).

Triggered when Tier 1 + Tier 2 both fail to dispatch. Assembles the
tenant's enrolled workflow registry, calls the
``intake.classify_into_registry`` managed prompt (Haiku, force_json,
parameterized by ``adapter_type`` per R-6.2a), and validates the
returned ``workflow_id`` against the live registry before dispatch.

R-6.2a — prompt key renamed from ``email.classify_into_registry``
to ``intake.classify_into_registry`` with an ``adapter_type``
variable. See tier_2_taxonomy.py for the seed migration discipline.

Registry assembly:
  ``workflows`` WHERE
    ``company_id IN (NULL, tenant_id)``
    AND ``vertical IN (NULL, tenant_vertical)``
    AND ``tier3_enrolled = true``
    AND ``is_active = true``

Tier 3 enrollment is opt-in per workflow at authoring time. Default
off. Prevents accidental fan-out as the workflow library grows.

Returns a tuple of:
  - matched ``Workflow`` row (or None)
  - confidence (or None on failure)
  - error string (or None on success / silent fallthrough)
  - reasoning string (or None)
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.email_primitive import EmailMessage
from app.models.workflow import Workflow
from app.services.intelligence import intelligence_service

logger = logging.getLogger(__name__)


_BODY_EXCERPT_LIMIT = 2048


def assemble_registry(
    db: Session, tenant_id: str
) -> list[Workflow]:
    """Return the list of workflows the Tier 3 classifier will pick
    from for this tenant. Empty list = no Tier 3 candidates → caller
    skips the LLM call."""
    tenant = (
        db.query(Company).filter(Company.id == tenant_id).first()
    )
    tenant_vertical = tenant.vertical if tenant else None

    q = db.query(Workflow).filter(
        Workflow.tier3_enrolled.is_(True),
        Workflow.is_active.is_(True),
        or_(
            Workflow.company_id.is_(None),
            Workflow.company_id == tenant_id,
        ),
        or_(
            Workflow.vertical.is_(None),
            Workflow.vertical == tenant_vertical,
        ),
    )
    return q.all()


def _serialize_registry(workflows: list[Workflow]) -> list[dict[str, Any]]:
    return [
        {
            "workflow_id": wf.id,
            "name": wf.name or "",
            "description": (wf.description or "").strip(),
        }
        for wf in workflows
    ]


def _build_excerpt(body_text: str | None) -> str:
    if not body_text:
        return ""
    return body_text[:_BODY_EXCERPT_LIMIT]


def classify(
    db: Session,
    *,
    message: EmailMessage,
    registry: list[Workflow],
    confidence_floor: float,
) -> tuple[Workflow | None, float | None, str | None, str | None]:
    """Run Tier 3 selection.

    Returns ``(matched_workflow, confidence, error_message, reasoning)``.
    """
    if not registry:
        return (None, None, None, None)

    variables = {
        "adapter_type": "email",
        "subject": (message.subject or "").strip(),
        "sender_email": message.sender_email or "",
        "sender_name": message.sender_name or "",
        "body_excerpt": _build_excerpt(message.body_text),
        "registry_json": _serialize_registry(registry),
    }

    try:
        result = intelligence_service.execute(
            db,
            prompt_key="intake.classify_into_registry",
            variables=variables,
            company_id=message.tenant_id,
            caller_module="intake_classification.tier_3",
            caller_entity_type="email_message",
            caller_entity_id=message.id,
        )
    except Exception as exc:
        logger.exception(
            "Tier 3 LLM call raised for message %s", message.id
        )
        return (None, None, f"tier_3_exception: {exc}", None)

    if result.status != "success":
        return (
            None,
            None,
            f"tier_3_status: {result.status} ({result.error_message or 'no_detail'})",
            None,
        )

    parsed = result.response_parsed or {}
    if not isinstance(parsed, dict):
        return (None, None, "tier_3_parse: not_object", None)

    workflow_id_raw = parsed.get("workflow_id")
    confidence_raw = parsed.get("confidence")
    reasoning = parsed.get("reasoning")
    if not isinstance(reasoning, str):
        reasoning = None

    if workflow_id_raw is None:
        return (None, None, None, reasoning)

    if not isinstance(workflow_id_raw, str):
        return (
            None,
            None,
            "tier_3_parse: workflow_id_not_string",
            reasoning,
        )

    try:
        confidence = float(confidence_raw) if confidence_raw is not None else 0.0
    except (TypeError, ValueError):
        confidence = 0.0

    if confidence < confidence_floor:
        return (None, confidence, None, reasoning)

    by_id = {wf.id: wf for wf in registry}
    workflow = by_id.get(workflow_id_raw)
    if workflow is None:
        logger.warning(
            "Tier 3 returned unknown workflow_id=%s for tenant %s; "
            "treating as fallthrough.",
            workflow_id_raw,
            message.tenant_id,
        )
        return (None, confidence, None, reasoning)

    return (workflow, confidence, None, reasoning)


# ── R-6.2a — Generic Tier 3 dispatch for form + file sources ────────


def _classify_against_registry(
    db: Session,
    *,
    tenant_id: str,
    registry: list[Workflow],
    variables: dict,
    confidence_floor: float,
    caller_entity_type: str,
    caller_entity_id: str,
) -> tuple[Workflow | None, float | None, str | None, str | None]:
    """Adapter-agnostic Tier 3 classifier."""
    if not registry:
        return (None, None, None, None)

    try:
        result = intelligence_service.execute(
            db,
            prompt_key="intake.classify_into_registry",
            variables=variables,
            company_id=tenant_id,
            caller_module="intake_classification.tier_3",
            caller_entity_type=caller_entity_type,
            caller_entity_id=caller_entity_id,
        )
    except Exception as exc:
        logger.exception(
            "Tier 3 LLM call raised for tenant %s caller_id=%s",
            tenant_id,
            caller_entity_id,
        )
        return (None, None, f"tier_3_exception: {exc}", None)

    if result.status != "success":
        return (
            None,
            None,
            f"tier_3_status: {result.status} ({result.error_message or 'no_detail'})",
            None,
        )

    parsed = result.response_parsed or {}
    if not isinstance(parsed, dict):
        return (None, None, "tier_3_parse: not_object", None)

    workflow_id_raw = parsed.get("workflow_id")
    confidence_raw = parsed.get("confidence")
    reasoning = parsed.get("reasoning")
    if not isinstance(reasoning, str):
        reasoning = None

    if workflow_id_raw is None:
        return (None, None, None, reasoning)
    if not isinstance(workflow_id_raw, str):
        return (None, None, "tier_3_parse: workflow_id_not_string", reasoning)

    try:
        confidence = float(confidence_raw) if confidence_raw is not None else 0.0
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence < confidence_floor:
        return (None, confidence, None, reasoning)

    by_id = {wf.id: wf for wf in registry}
    workflow = by_id.get(workflow_id_raw)
    if workflow is None:
        logger.warning(
            "Tier 3 returned unknown workflow_id=%s for tenant %s",
            workflow_id_raw,
            tenant_id,
        )
        return (None, confidence, None, reasoning)
    return (workflow, confidence, None, reasoning)


def classify_form(
    db: Session,
    *,
    submission_id: str,
    tenant_id: str,
    form_slug: str,
    submitted_data: dict,
    registry: list[Workflow],
    confidence_floor: float,
):
    """Run Tier 3 selection against a form submission."""
    from app.services.classification.tier_2_taxonomy import _form_excerpt

    variables = {
        "adapter_type": "form",
        "subject": form_slug,
        "sender_email": (submitted_data or {}).get("family_contact_email", ""),
        "sender_name": (submitted_data or {}).get("family_contact_name", ""),
        "body_excerpt": _form_excerpt(submitted_data),
        "registry_json": _serialize_registry(registry),
    }
    return _classify_against_registry(
        db,
        tenant_id=tenant_id,
        registry=registry,
        variables=variables,
        confidence_floor=confidence_floor,
        caller_entity_type="intake_form_submission",
        caller_entity_id=submission_id,
    )


def classify_file(
    db: Session,
    *,
    upload_id: str,
    tenant_id: str,
    file_slug: str,
    original_filename: str,
    content_type: str,
    uploader_metadata: dict,
    registry: list[Workflow],
    confidence_floor: float,
):
    """Run Tier 3 selection against a file upload."""
    excerpt = (
        f"filename: {original_filename}\n"
        f"content_type: {content_type}\n"
        f"uploader_metadata: {uploader_metadata}"
    )
    variables = {
        "adapter_type": "file",
        "subject": file_slug,
        "sender_email": (uploader_metadata or {}).get("uploader_email", ""),
        "sender_name": (uploader_metadata or {}).get("uploader_name", ""),
        "body_excerpt": excerpt[:_BODY_EXCERPT_LIMIT],
        "registry_json": _serialize_registry(registry),
    }
    return _classify_against_registry(
        db,
        tenant_id=tenant_id,
        registry=registry,
        variables=variables,
        confidence_floor=confidence_floor,
        caller_entity_type="intake_file_upload",
        caller_entity_id=upload_id,
    )
