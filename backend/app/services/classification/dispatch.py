"""Phase R-6.1a — Email classification cascade orchestrator.

Wires Tier 1 + Tier 2 + Tier 3 + audit writer + workflow_engine.start_run
into a single synchronous entry point ``classify_and_fire``. Inbound
email ingestion's Step 12 hook calls this; admin endpoints reuse the
same primitives for replay + manual reroute.

Cascade semantics:
  1. Tier 1 match → write audit row, fire workflow if rule.fire_action
     .workflow_id is set, else mark is_suppressed=True. Return.
  2. Tier 2 match (above floor) → write audit row, fire mapped
     workflow. Return.
  3. Tier 3 match (above floor) → write audit row, fire selected
     workflow. Return.
  4. All tiers fall through → write audit row with tier=None
     selected_workflow_id=None — surfaces in unclassified triage queue.

LLM exceptions in Tier 2 / Tier 3 do NOT block the cascade; the tier
is recorded as failed in tier_reasoning + the cascade continues to
the next tier. Only complete cascade exhaustion returns "unclassified".

Trigger context shape per R-6.0 contract — flat ``incoming_email`` key
with denormalized message fields. Workflow steps reference these via
``incoming_email.<path>`` parameter binding.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.email_classification import (
    TenantWorkflowEmailRule,
    WorkflowEmailClassification,
)
from app.models.email_primitive import EmailMessage
from app.models.user import User
from app.models.workflow import Workflow
from app.services.classification import tier_1_rules, tier_2_taxonomy, tier_3_registry
from app.services.classification.audit import write_classification_audit
from app.services import workflow_engine

logger = logging.getLogger(__name__)


# Module-level confidence floors — per-tenant override via
# Company.settings_json.classification_confidence_floors.{tier_2, tier_3}.
CONFIDENCE_FLOOR_TIER_2 = 0.55
CONFIDENCE_FLOOR_TIER_3 = 0.65


class ClassificationError(Exception):
    """Base for classification cascade exceptions."""

    def __init__(self, message: str, http_status: int = 400):
        super().__init__(message)
        self.http_status = http_status


class ClassificationNotFound(ClassificationError):
    """Cross-tenant id lookup failed — surfaced to API as 404."""

    def __init__(self, message: str = "Classification not found"):
        super().__init__(message, http_status=404)


@dataclass
class ClassificationResult:
    """Public return shape from dispatch.classify_and_fire et al.

    ``classification_id`` always populated (every path writes an
    audit row). ``tier`` is None for unclassified or suppressed.
    ``workflow_run_id`` populated only when a workflow fired.
    """

    classification_id: str
    tier: int | None
    selected_workflow_id: str | None
    workflow_run_id: str | None
    is_suppressed: bool


def _resolve_floors(db: Session, tenant_id: str) -> tuple[float, float]:
    """Return ``(tier_2_floor, tier_3_floor)`` honoring per-tenant
    override via ``Company.settings_json``."""
    tenant = db.query(Company).filter(Company.id == tenant_id).first()
    if tenant is None:
        return (CONFIDENCE_FLOOR_TIER_2, CONFIDENCE_FLOOR_TIER_3)

    settings = tenant.settings or {}
    overrides = settings.get("classification_confidence_floors") or {}
    tier_2 = overrides.get("tier_2")
    tier_3 = overrides.get("tier_3")
    try:
        tier_2_v = float(tier_2) if tier_2 is not None else CONFIDENCE_FLOOR_TIER_2
    except (TypeError, ValueError):
        tier_2_v = CONFIDENCE_FLOOR_TIER_2
    try:
        tier_3_v = float(tier_3) if tier_3 is not None else CONFIDENCE_FLOOR_TIER_3
    except (TypeError, ValueError):
        tier_3_v = CONFIDENCE_FLOOR_TIER_3
    return (tier_2_v, tier_3_v)


def _build_trigger_context(message: EmailMessage) -> dict[str, Any]:
    """R-6.0 contract: ``incoming_email.<path>`` resolves trigger
    context. Flat shape; full body_text (workflow steps may need it)."""
    return {
        "incoming_email": {
            "id": message.id,
            "thread_id": message.thread_id,
            "tenant_id": message.tenant_id,
            "account_id": message.account_id,
            "provider_message_id": message.provider_message_id,
            "from_email": message.sender_email,
            "from_name": message.sender_name,
            "subject": message.subject,
            "body_text": message.body_text,
            "body_html": message.body_html,
            "received_at": (
                message.received_at.isoformat()
                if message.received_at
                else None
            ),
        }
    }


def _fire_workflow(
    db: Session,
    *,
    workflow: Workflow,
    message: EmailMessage,
) -> str | None:
    """Fire a workflow with the message as trigger_context. Returns
    the run_id or None on failure (logged + audit row's error_message
    populated by caller)."""
    try:
        run = workflow_engine.start_run(
            db,
            workflow_id=workflow.id,
            company_id=message.tenant_id,
            triggered_by_user_id=None,
            trigger_source="email_classification",
            trigger_context=_build_trigger_context(message),
            initial_inputs={},
        )
        return run.id
    except Exception:
        logger.exception(
            "Workflow %s start_run failed for message %s",
            workflow.id,
            message.id,
        )
        return None


def classify_and_fire(
    db: Session,
    *,
    email_message: EmailMessage,
    is_replay: bool = False,
    replay_of_classification_id: str | None = None,
) -> ClassificationResult:
    """Run the three-tier cascade synchronously. Always writes one
    audit row. Fires the dispatched workflow when applicable.

    Caller wraps in try/except — never blocks email ingestion.
    """
    started_at = time.monotonic()
    tier_reasoning: dict[str, Any] = {
        "tier1": None,
        "tier2": None,
        "tier3": None,
    }

    tier_2_floor, tier_3_floor = _resolve_floors(
        db, email_message.tenant_id
    )

    # ── Tier 1 ─────────────────────────────────────────────────
    matched_rule: TenantWorkflowEmailRule | None = tier_1_rules.evaluate(
        db, email_message
    )
    if matched_rule is not None:
        fire_action = matched_rule.fire_action or {}
        target_wf_id = fire_action.get("workflow_id")
        tier_reasoning["tier1"] = {
            "matched_rule_id": matched_rule.id,
            "rule_name": matched_rule.name,
            "workflow_id": target_wf_id,
        }

        if target_wf_id is None:
            # Suppression path — drop without firing or routing to triage.
            row = write_classification_audit(
                db,
                tenant_id=email_message.tenant_id,
                email_message_id=email_message.id,
                tier=1,
                tier1_rule_id=matched_rule.id,
                is_suppressed=True,
                latency_ms=int((time.monotonic() - started_at) * 1000),
                tier_reasoning=tier_reasoning,
                is_replay=is_replay,
                replay_of_classification_id=replay_of_classification_id,
            )
            return ClassificationResult(
                classification_id=row.id,
                tier=1,
                selected_workflow_id=None,
                workflow_run_id=None,
                is_suppressed=True,
            )

        # Validate workflow exists + active for tenant.
        workflow = (
            db.query(Workflow)
            .filter(
                Workflow.id == target_wf_id,
                Workflow.is_active.is_(True),
            )
            .first()
        )
        if workflow is None:
            # Stale rule — workflow archived but rule still references
            # it. Falls through to next tier with error noted.
            tier_reasoning["tier1"]["error"] = "workflow_not_active"
            logger.warning(
                "Tier 1 rule %s references inactive/missing workflow %s; "
                "falling through to Tier 2.",
                matched_rule.id,
                target_wf_id,
            )
        else:
            run_id = _fire_workflow(
                db, workflow=workflow, message=email_message
            )
            row = write_classification_audit(
                db,
                tenant_id=email_message.tenant_id,
                email_message_id=email_message.id,
                tier=1,
                tier1_rule_id=matched_rule.id,
                selected_workflow_id=workflow.id,
                workflow_run_id=run_id,
                latency_ms=int((time.monotonic() - started_at) * 1000),
                tier_reasoning=tier_reasoning,
                is_replay=is_replay,
                replay_of_classification_id=replay_of_classification_id,
                error_message=(
                    "workflow_engine.start_run failed" if run_id is None else None
                ),
            )
            return ClassificationResult(
                classification_id=row.id,
                tier=1,
                selected_workflow_id=workflow.id,
                workflow_run_id=run_id,
                is_suppressed=False,
            )

    # ── Tier 2 ─────────────────────────────────────────────────
    taxonomy = tier_2_taxonomy.list_active_taxonomy(
        db, email_message.tenant_id
    )
    matched_category, t2_confidence, t2_error, t2_reasoning = (
        tier_2_taxonomy.classify(
            db,
            message=email_message,
            taxonomy=taxonomy,
            confidence_floor=tier_2_floor,
        )
    )
    tier_reasoning["tier2"] = {
        "category_id": matched_category.id if matched_category else None,
        "confidence": t2_confidence,
        "error": t2_error,
        "reasoning": t2_reasoning,
    }
    if matched_category is not None and matched_category.mapped_workflow_id:
        workflow = (
            db.query(Workflow)
            .filter(Workflow.id == matched_category.mapped_workflow_id)
            .first()
        )
        if workflow is not None:
            run_id = _fire_workflow(
                db, workflow=workflow, message=email_message
            )
            row = write_classification_audit(
                db,
                tenant_id=email_message.tenant_id,
                email_message_id=email_message.id,
                tier=2,
                tier2_category_id=matched_category.id,
                tier2_confidence=t2_confidence,
                selected_workflow_id=workflow.id,
                workflow_run_id=run_id,
                latency_ms=int((time.monotonic() - started_at) * 1000),
                tier_reasoning=tier_reasoning,
                is_replay=is_replay,
                replay_of_classification_id=replay_of_classification_id,
                error_message=(
                    "workflow_engine.start_run failed" if run_id is None else None
                ),
            )
            return ClassificationResult(
                classification_id=row.id,
                tier=2,
                selected_workflow_id=workflow.id,
                workflow_run_id=run_id,
                is_suppressed=False,
            )

    # ── Tier 3 ─────────────────────────────────────────────────
    registry = tier_3_registry.assemble_registry(db, email_message.tenant_id)
    matched_workflow, t3_confidence, t3_error, t3_reasoning = (
        tier_3_registry.classify(
            db,
            message=email_message,
            registry=registry,
            confidence_floor=tier_3_floor,
        )
    )
    tier_reasoning["tier3"] = {
        "workflow_id": matched_workflow.id if matched_workflow else None,
        "confidence": t3_confidence,
        "error": t3_error,
        "reasoning": t3_reasoning,
    }
    if matched_workflow is not None:
        run_id = _fire_workflow(
            db, workflow=matched_workflow, message=email_message
        )
        row = write_classification_audit(
            db,
            tenant_id=email_message.tenant_id,
            email_message_id=email_message.id,
            tier=3,
            tier3_confidence=t3_confidence,
            selected_workflow_id=matched_workflow.id,
            workflow_run_id=run_id,
            latency_ms=int((time.monotonic() - started_at) * 1000),
            tier_reasoning=tier_reasoning,
            is_replay=is_replay,
            replay_of_classification_id=replay_of_classification_id,
            error_message=(
                "workflow_engine.start_run failed" if run_id is None else None
            ),
        )
        return ClassificationResult(
            classification_id=row.id,
            tier=3,
            selected_workflow_id=matched_workflow.id,
            workflow_run_id=run_id,
            is_suppressed=False,
        )

    # ── Unclassified ───────────────────────────────────────────
    row = write_classification_audit(
        db,
        tenant_id=email_message.tenant_id,
        email_message_id=email_message.id,
        tier=None,
        tier2_confidence=t2_confidence,
        tier3_confidence=t3_confidence,
        latency_ms=int((time.monotonic() - started_at) * 1000),
        tier_reasoning=tier_reasoning,
        is_replay=is_replay,
        replay_of_classification_id=replay_of_classification_id,
    )
    return ClassificationResult(
        classification_id=row.id,
        tier=None,
        selected_workflow_id=None,
        workflow_run_id=None,
        is_suppressed=False,
    )


def get_latest_classification_for_message(
    db: Session, *, message_id: str
) -> WorkflowEmailClassification | None:
    """Read the latest classification (by created_at DESC) for a
    message. Used by admin replay endpoint + by triage display
    component to surface current state."""
    return (
        db.query(WorkflowEmailClassification)
        .filter(WorkflowEmailClassification.email_message_id == message_id)
        .order_by(WorkflowEmailClassification.created_at.desc())
        .first()
    )


def classify_only(
    db: Session, *, message_id: str, tenant_id: str
) -> ClassificationResult:
    """Admin replay surface — re-runs cascade against current rules /
    taxonomy / registry. Writes a NEW audit row with is_replay=True.
    Tenant-scoped (cross-tenant message_id raises
    ClassificationNotFound for existence-hiding canon)."""
    message = (
        db.query(EmailMessage)
        .filter(EmailMessage.id == message_id)
        .first()
    )
    if message is None or message.tenant_id != tenant_id:
        raise ClassificationNotFound("Email message not found")

    prior = get_latest_classification_for_message(
        db, message_id=message_id
    )
    return classify_and_fire(
        db,
        email_message=message,
        is_replay=True,
        replay_of_classification_id=prior.id if prior else None,
    )


def list_unclassified(
    db: Session, *, tenant_id: str, limit: int = 50
) -> list[dict[str, Any]]:
    """Feed the email_unclassified_triage direct-query builder.

    Returns rows shaped for the triage item summary — one entry per
    *latest* unclassified-and-not-suppressed classification per message.
    A message that was previously unclassified but later replayed into
    a tier-1/2/3 dispatch will NOT surface here (we read the latest
    classification per message via the unique ``email_message_id``
    index ordering).
    """
    # Subquery for latest classification per message_id within the tenant.
    rows = (
        db.query(WorkflowEmailClassification, EmailMessage)
        .join(
            EmailMessage,
            EmailMessage.id == WorkflowEmailClassification.email_message_id,
        )
        .filter(
            WorkflowEmailClassification.tenant_id == tenant_id,
            WorkflowEmailClassification.tier.is_(None),
            WorkflowEmailClassification.is_suppressed.is_(False),
        )
        .order_by(WorkflowEmailClassification.created_at.asc())
        .limit(limit)
        .all()
    )

    out: list[dict[str, Any]] = []
    for cls_row, msg in rows:
        # De-dup against later classifications: skip if a newer row
        # exists for this message that flipped state.
        latest = get_latest_classification_for_message(
            db, message_id=msg.id
        )
        if latest is None or latest.id != cls_row.id:
            continue
        # If latest is now classified or suppressed, skip.
        if latest.tier is not None or latest.is_suppressed:
            continue
        out.append(
            {
                "id": cls_row.id,
                "classification_id": cls_row.id,
                "email_message_id": msg.id,
                "subject": msg.subject or "",
                "sender_email": msg.sender_email or "",
                "sender_name": msg.sender_name or "",
                "body_excerpt": (msg.body_text or "")[:500],
                "received_at": (
                    msg.received_at.isoformat()
                    if msg.received_at
                    else None
                ),
                "created_at": (
                    cls_row.created_at.isoformat()
                    if cls_row.created_at
                    else None
                ),
                "tier_reasoning": cls_row.tier_reasoning or {},
            }
        )
    return out


# ── R-6.2a — Form + file cascade entry points ───────────────────────


def _build_form_trigger_context(
    submission, config
) -> dict[str, Any]:
    """R-6.2a contract: ``incoming_form_submission.<path>`` resolves
    trigger context. Flat shape parallels ``incoming_email``."""
    return {
        "incoming_form_submission": {
            "id": submission.id,
            "config_id": submission.config_id,
            "config_slug": config.slug,
            "submitted_data": submission.submitted_data or {},
            "submitter_metadata": submission.submitter_metadata or {},
            "received_at": (
                submission.received_at.isoformat()
                if submission.received_at
                else None
            ),
            "tenant_id": submission.tenant_id,
        }
    }


def _build_file_trigger_context(upload, config) -> dict[str, Any]:
    """R-6.2a contract: ``incoming_file.<path>`` resolves trigger
    context. Includes a presigned download URL with 1-hour TTL."""
    presigned_url = None
    try:
        from app.services import legacy_r2_client

        presigned_url = legacy_r2_client.generate_signed_url(
            upload.r2_key, expires_in=3600
        )
    except Exception:
        # Best-effort — workflows that need the URL handle None.
        logger.warning(
            "Failed to generate presigned URL for upload %s; trigger "
            "context will lack presigned_url.",
            upload.id,
        )

    return {
        "incoming_file": {
            "id": upload.id,
            "config_id": upload.config_id,
            "config_slug": config.slug,
            "r2_key": upload.r2_key,
            "presigned_url": presigned_url,
            "original_filename": upload.original_filename,
            "content_type": upload.content_type,
            "size_bytes": upload.size_bytes,
            "uploader_metadata": upload.uploader_metadata or {},
            "received_at": (
                upload.received_at.isoformat()
                if upload.received_at
                else None
            ),
            "tenant_id": upload.tenant_id,
        }
    }


def _fire_workflow_with_context(
    db: Session,
    *,
    workflow: Workflow,
    tenant_id: str,
    trigger_source: str,
    trigger_context: dict,
) -> str | None:
    """Fire a workflow with a pre-built trigger_context. Returns
    run_id or None on failure (logged)."""
    try:
        run = workflow_engine.start_run(
            db,
            workflow_id=workflow.id,
            company_id=tenant_id,
            triggered_by_user_id=None,
            trigger_source=trigger_source,
            trigger_context=trigger_context,
            initial_inputs={},
        )
        return run.id
    except Exception:
        logger.exception(
            "Workflow %s start_run failed (trigger_source=%s)",
            workflow.id,
            trigger_source,
        )
        return None


def classify_and_fire_form(
    db: Session,
    *,
    submission,
    config,
) -> dict[str, Any]:
    """Run the three-tier cascade synchronously against a form
    submission. Updates ``submission.classification_*`` columns with
    the outcome. Best-effort — caller wraps in try/except.

    Cascade structure mirrors ``classify_and_fire`` for emails but
    persists outcome on the submission row directly (no parallel
    audit table — denormalized payload + tier on the submission).
    """
    started_at = time.monotonic()
    tier_reasoning: dict[str, Any] = {
        "tier1": None,
        "tier2": None,
        "tier3": None,
    }

    tier_2_floor, tier_3_floor = _resolve_floors(db, submission.tenant_id)

    # Tier 1 — form-shape rules.
    matched_rule = tier_1_rules.evaluate_form(
        db,
        tenant_id=submission.tenant_id,
        form_slug=config.slug,
        submitted_data=submission.submitted_data or {},
        submitter_metadata=submission.submitter_metadata or {},
    )
    if matched_rule is not None:
        fire_action = matched_rule.fire_action or {}
        target_wf_id = fire_action.get("workflow_id")
        tier_reasoning["tier1"] = {
            "matched_rule_id": matched_rule.id,
            "rule_name": matched_rule.name,
            "workflow_id": target_wf_id,
        }
        if target_wf_id is None:
            submission.classification_tier = 1
            submission.classification_is_suppressed = True
            submission.classification_payload = {
                "tier_reasoning": tier_reasoning,
                "latency_ms": int((time.monotonic() - started_at) * 1000),
            }
            db.flush()
            return {"tier": 1, "is_suppressed": True}

        workflow = (
            db.query(Workflow)
            .filter(
                Workflow.id == target_wf_id, Workflow.is_active.is_(True)
            )
            .first()
        )
        if workflow is not None:
            trigger_ctx = _build_form_trigger_context(submission, config)
            run_id = _fire_workflow_with_context(
                db,
                workflow=workflow,
                tenant_id=submission.tenant_id,
                trigger_source="form_classification",
                trigger_context=trigger_ctx,
            )
            submission.classification_tier = 1
            submission.classification_workflow_id = workflow.id
            submission.classification_workflow_run_id = run_id
            submission.classification_payload = {
                "tier_reasoning": tier_reasoning,
                "latency_ms": int((time.monotonic() - started_at) * 1000),
            }
            db.flush()
            return {
                "tier": 1,
                "selected_workflow_id": workflow.id,
                "workflow_run_id": run_id,
            }
        else:
            tier_reasoning["tier1"]["error"] = "workflow_not_active"

    # Tier 2.
    taxonomy = tier_2_taxonomy.list_active_taxonomy(db, submission.tenant_id)
    matched_category, t2_confidence, t2_error, t2_reasoning = (
        tier_2_taxonomy.classify_form(
            db,
            submission_id=submission.id,
            tenant_id=submission.tenant_id,
            form_slug=config.slug,
            submitted_data=submission.submitted_data or {},
            taxonomy=taxonomy,
            confidence_floor=tier_2_floor,
        )
    )
    tier_reasoning["tier2"] = {
        "category_id": matched_category.id if matched_category else None,
        "confidence": t2_confidence,
        "error": t2_error,
        "reasoning": t2_reasoning,
    }
    if matched_category is not None and matched_category.mapped_workflow_id:
        workflow = (
            db.query(Workflow)
            .filter(Workflow.id == matched_category.mapped_workflow_id)
            .first()
        )
        if workflow is not None:
            trigger_ctx = _build_form_trigger_context(submission, config)
            run_id = _fire_workflow_with_context(
                db,
                workflow=workflow,
                tenant_id=submission.tenant_id,
                trigger_source="form_classification",
                trigger_context=trigger_ctx,
            )
            submission.classification_tier = 2
            submission.classification_workflow_id = workflow.id
            submission.classification_workflow_run_id = run_id
            submission.classification_payload = {
                "tier_reasoning": tier_reasoning,
                "latency_ms": int((time.monotonic() - started_at) * 1000),
            }
            db.flush()
            return {
                "tier": 2,
                "selected_workflow_id": workflow.id,
                "workflow_run_id": run_id,
            }

    # Tier 3.
    registry = tier_3_registry.assemble_registry(db, submission.tenant_id)
    matched_workflow, t3_confidence, t3_error, t3_reasoning = (
        tier_3_registry.classify_form(
            db,
            submission_id=submission.id,
            tenant_id=submission.tenant_id,
            form_slug=config.slug,
            submitted_data=submission.submitted_data or {},
            registry=registry,
            confidence_floor=tier_3_floor,
        )
    )
    tier_reasoning["tier3"] = {
        "workflow_id": matched_workflow.id if matched_workflow else None,
        "confidence": t3_confidence,
        "error": t3_error,
        "reasoning": t3_reasoning,
    }
    if matched_workflow is not None:
        trigger_ctx = _build_form_trigger_context(submission, config)
        run_id = _fire_workflow_with_context(
            db,
            workflow=matched_workflow,
            tenant_id=submission.tenant_id,
            trigger_source="form_classification",
            trigger_context=trigger_ctx,
        )
        submission.classification_tier = 3
        submission.classification_workflow_id = matched_workflow.id
        submission.classification_workflow_run_id = run_id
        submission.classification_payload = {
            "tier_reasoning": tier_reasoning,
            "latency_ms": int((time.monotonic() - started_at) * 1000),
        }
        db.flush()
        return {
            "tier": 3,
            "selected_workflow_id": matched_workflow.id,
            "workflow_run_id": run_id,
        }

    # Unclassified.
    submission.classification_payload = {
        "tier_reasoning": tier_reasoning,
        "latency_ms": int((time.monotonic() - started_at) * 1000),
    }
    db.flush()
    return {"tier": None, "selected_workflow_id": None}


def classify_and_fire_file(
    db: Session,
    *,
    upload,
    config,
) -> dict[str, Any]:
    """Run the three-tier cascade synchronously against a file
    upload. Updates ``upload.classification_*`` columns. Best-effort."""
    started_at = time.monotonic()
    tier_reasoning: dict[str, Any] = {
        "tier1": None,
        "tier2": None,
        "tier3": None,
    }

    tier_2_floor, tier_3_floor = _resolve_floors(db, upload.tenant_id)

    # Tier 1.
    matched_rule = tier_1_rules.evaluate_file(
        db,
        tenant_id=upload.tenant_id,
        file_slug=config.slug,
        content_type=upload.content_type,
        original_filename=upload.original_filename,
        uploader_metadata=upload.uploader_metadata or {},
    )
    if matched_rule is not None:
        fire_action = matched_rule.fire_action or {}
        target_wf_id = fire_action.get("workflow_id")
        tier_reasoning["tier1"] = {
            "matched_rule_id": matched_rule.id,
            "rule_name": matched_rule.name,
            "workflow_id": target_wf_id,
        }
        if target_wf_id is None:
            upload.classification_tier = 1
            upload.classification_is_suppressed = True
            upload.classification_payload = {
                "tier_reasoning": tier_reasoning,
                "latency_ms": int((time.monotonic() - started_at) * 1000),
            }
            db.flush()
            return {"tier": 1, "is_suppressed": True}

        workflow = (
            db.query(Workflow)
            .filter(
                Workflow.id == target_wf_id, Workflow.is_active.is_(True)
            )
            .first()
        )
        if workflow is not None:
            trigger_ctx = _build_file_trigger_context(upload, config)
            run_id = _fire_workflow_with_context(
                db,
                workflow=workflow,
                tenant_id=upload.tenant_id,
                trigger_source="file_classification",
                trigger_context=trigger_ctx,
            )
            upload.classification_tier = 1
            upload.classification_workflow_id = workflow.id
            upload.classification_workflow_run_id = run_id
            upload.classification_payload = {
                "tier_reasoning": tier_reasoning,
                "latency_ms": int((time.monotonic() - started_at) * 1000),
            }
            db.flush()
            return {
                "tier": 1,
                "selected_workflow_id": workflow.id,
                "workflow_run_id": run_id,
            }

    # Tier 2.
    taxonomy = tier_2_taxonomy.list_active_taxonomy(db, upload.tenant_id)
    matched_category, t2_confidence, t2_error, t2_reasoning = (
        tier_2_taxonomy.classify_file(
            db,
            upload_id=upload.id,
            tenant_id=upload.tenant_id,
            file_slug=config.slug,
            original_filename=upload.original_filename,
            content_type=upload.content_type,
            uploader_metadata=upload.uploader_metadata or {},
            taxonomy=taxonomy,
            confidence_floor=tier_2_floor,
        )
    )
    tier_reasoning["tier2"] = {
        "category_id": matched_category.id if matched_category else None,
        "confidence": t2_confidence,
        "error": t2_error,
        "reasoning": t2_reasoning,
    }
    if matched_category is not None and matched_category.mapped_workflow_id:
        workflow = (
            db.query(Workflow)
            .filter(Workflow.id == matched_category.mapped_workflow_id)
            .first()
        )
        if workflow is not None:
            trigger_ctx = _build_file_trigger_context(upload, config)
            run_id = _fire_workflow_with_context(
                db,
                workflow=workflow,
                tenant_id=upload.tenant_id,
                trigger_source="file_classification",
                trigger_context=trigger_ctx,
            )
            upload.classification_tier = 2
            upload.classification_workflow_id = workflow.id
            upload.classification_workflow_run_id = run_id
            upload.classification_payload = {
                "tier_reasoning": tier_reasoning,
                "latency_ms": int((time.monotonic() - started_at) * 1000),
            }
            db.flush()
            return {
                "tier": 2,
                "selected_workflow_id": workflow.id,
                "workflow_run_id": run_id,
            }

    # Tier 3.
    registry = tier_3_registry.assemble_registry(db, upload.tenant_id)
    matched_workflow, t3_confidence, t3_error, t3_reasoning = (
        tier_3_registry.classify_file(
            db,
            upload_id=upload.id,
            tenant_id=upload.tenant_id,
            file_slug=config.slug,
            original_filename=upload.original_filename,
            content_type=upload.content_type,
            uploader_metadata=upload.uploader_metadata or {},
            registry=registry,
            confidence_floor=tier_3_floor,
        )
    )
    tier_reasoning["tier3"] = {
        "workflow_id": matched_workflow.id if matched_workflow else None,
        "confidence": t3_confidence,
        "error": t3_error,
        "reasoning": t3_reasoning,
    }
    if matched_workflow is not None:
        trigger_ctx = _build_file_trigger_context(upload, config)
        run_id = _fire_workflow_with_context(
            db,
            workflow=matched_workflow,
            tenant_id=upload.tenant_id,
            trigger_source="file_classification",
            trigger_context=trigger_ctx,
        )
        upload.classification_tier = 3
        upload.classification_workflow_id = matched_workflow.id
        upload.classification_workflow_run_id = run_id
        upload.classification_payload = {
            "tier_reasoning": tier_reasoning,
            "latency_ms": int((time.monotonic() - started_at) * 1000),
        }
        db.flush()
        return {
            "tier": 3,
            "selected_workflow_id": matched_workflow.id,
            "workflow_run_id": run_id,
        }

    # Unclassified.
    upload.classification_payload = {
        "tier_reasoning": tier_reasoning,
        "latency_ms": int((time.monotonic() - started_at) * 1000),
    }
    db.flush()
    return {"tier": None, "selected_workflow_id": None}


def manual_route_to_workflow(
    db: Session,
    *,
    classification_id: str,
    workflow_id: str,
    user: User,
    decision_notes: str | None = None,
) -> ClassificationResult:
    """Operator-driven reroute from the unclassified triage queue.
    Validates tenant scope, fires the chosen workflow, writes a NEW
    audit row marking is_replay=True + replay_of_classification_id.
    """
    prior = (
        db.query(WorkflowEmailClassification)
        .filter(
            WorkflowEmailClassification.id == classification_id,
            WorkflowEmailClassification.tenant_id == user.company_id,
        )
        .first()
    )
    if prior is None:
        raise ClassificationNotFound("Classification not found")

    workflow = (
        db.query(Workflow)
        .filter(
            Workflow.id == workflow_id,
            Workflow.is_active.is_(True),
        )
        .first()
    )
    if workflow is None:
        raise ClassificationError(
            "Workflow not found or inactive", http_status=400
        )
    # Workflow must be visible to tenant (cross-vertical+platform OR
    # owned by this tenant).
    if workflow.company_id is not None and workflow.company_id != user.company_id:
        raise ClassificationError(
            "Workflow not available for this tenant", http_status=400
        )

    message = (
        db.query(EmailMessage)
        .filter(EmailMessage.id == prior.email_message_id)
        .first()
    )
    if message is None:
        raise ClassificationNotFound("Original email not found")

    started_at = time.monotonic()
    run_id = _fire_workflow(db, workflow=workflow, message=message)
    tier_reasoning = {
        "manual_route": {
            "operator_user_id": user.id,
            "decision_notes": decision_notes,
        }
    }
    row = write_classification_audit(
        db,
        tenant_id=user.company_id,
        email_message_id=message.id,
        tier=None,  # manual reroute is not a tier dispatch
        selected_workflow_id=workflow.id,
        workflow_run_id=run_id,
        latency_ms=int((time.monotonic() - started_at) * 1000),
        tier_reasoning=tier_reasoning,
        is_replay=True,
        replay_of_classification_id=prior.id,
        error_message=(
            "workflow_engine.start_run failed" if run_id is None else None
        ),
    )
    db.commit()
    return ClassificationResult(
        classification_id=row.id,
        tier=None,
        selected_workflow_id=workflow.id,
        workflow_run_id=run_id,
        is_suppressed=False,
    )
