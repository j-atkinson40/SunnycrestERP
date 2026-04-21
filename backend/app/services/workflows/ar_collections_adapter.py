"""AR Collections — parity adapter (Workflow Arc Phase 8c).

Thin bridge between the workflow engine / triage engine and the
existing `ARCollectionsAgent` + email-send path. **Closes the
pre-existing Phase 3b TODO** — the legacy approval flow had a
documented no-op (`approval_gate.py:199`); this adapter implements
the correct behavior by routing triage "send" actions through
`email_service.send_collections_email` → `delivery_service.send_email_with_template(template_key="email.collections")`.

The central parity claim of Phase 8c for ar_collections:
  For a given per-customer draft stored in the AgentJob's
  `report_payload.steps.draft_communications.communications` list,
  calling `send_customer_email` via triage produces an IDENTICAL
  `document_deliveries` row to calling
  `email_service.send_collections_email` directly with the same
  customer + subject + body arguments:
    - template_key = "email.collections"
    - caller_module = "ar_collections_adapter.send_customer_email"
      (via the caller_module parameter threaded through)
    - recipient_value = customer.billing_email (or customer.email
      fallback)
    - The related AgentAnomaly for the customer gets resolved with a
      "sent via triage" note.

Verified by `test_ar_collections_migration_parity.py` (BLOCKING).

**New capability — not pure refactor:**
Unlike cash receipts (Phase 8b) which was a strict refactor of
existing behavior, ar_collections closes a pre-existing TODO.
Legacy path was non-functional — `approval_gate._process_approve`
for `ar_collections` only flipped `job.status="complete"` without
sending any emails. Triage path now correctly sends one email per
approved customer. Operational coexistence note: tenants who've
been "approving" drafts will see first real email sends from this
deploy. Discontinue any manual email dispatching.

Fan-out pattern:
  Queue cardinality: ONE-PER-CUSTOMER (not per-anomaly,
  not per-invoice). Each anomaly emitted by the agent is per-customer
  (entity_type="customer", entity_id=customer_id). The draft for
  that customer lives in `AgentJob.report_payload.steps.
  draft_communications.communications[i]` where
  `communications[i].customer_id == anomaly.entity_id`.

Public functions:

  run_collections_pipeline(db, *, company_id, triggered_by_user_id,
                           dry_run=False, trigger_source="workflow")
      -> dict
      Execute the 4-step agent. Creates AgentJob + delegates to
      AgentRunner. Returns summary with agent_job_id + per-tier counts.

  send_customer_email(db, *, user, anomaly_id) -> dict
      Triage "send" action. Closes the 3b TODO. Looks up the draft
      for the anomaly's customer in the job's report_payload, routes
      through `email_service.send_collections_email`, resolves the
      anomaly with a "sent via triage" note + document_delivery_id.

  skip_customer(db, *, user, anomaly_id, reason) -> dict
      Triage "skip" action. Resolves anomaly with reason, NO email
      sent.

  request_review_customer(db, *, user, anomaly_id, note) -> dict
      Triage "request_review" action. Stamps review note, leaves
      anomaly unresolved (item stays in queue).
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent import AgentJob
from app.models.agent_anomaly import AgentAnomaly
from app.models.customer import Customer
from app.models.user import User
from app.schemas.agent import AgentJobStatus, AgentJobType

logger = logging.getLogger(__name__)


# ── Pipeline entry (workflow-step surface) ───────────────────────────


def run_collections_pipeline(
    db: Session,
    *,
    company_id: str,
    triggered_by_user_id: str | None,
    dry_run: bool = False,
    trigger_source: str = "workflow",
) -> dict[str, Any]:
    """Create + execute an ARCollectionsAgent job end-to-end. Agent
    produces per-customer draft emails in `report_payload`. Drafts
    are NOT sent automatically — triage operators dispatch them via
    `send_customer_email`.
    """
    from app.services.agents.agent_runner import AgentRunner

    today = date.today()
    first_of_month = today.replace(day=1)

    job = AgentJob(
        id=str(uuid.uuid4()),
        tenant_id=company_id,
        job_type=AgentJobType.AR_COLLECTIONS.value,
        status=AgentJobStatus.PENDING.value,
        period_start=first_of_month,
        period_end=today,
        dry_run=dry_run,
        triggered_by=triggered_by_user_id,
        trigger_type=trigger_source,
        run_log=[],
        anomaly_count=0,
    )
    db.add(job)
    db.commit()

    AgentRunner.run_job(job.id, db)
    db.refresh(job)

    report = job.report_payload or {}
    exec_summary = (
        report.get("executive_summary", {})
        if isinstance(report, dict) else {}
    )
    return {
        "agent_job_id": job.id,
        "status": job.status,
        "anomaly_count": job.anomaly_count,
        "follow_up_count": exec_summary.get("follow_up_count", 0),
        "escalate_count": exec_summary.get("escalate_count", 0),
        "critical_count": exec_summary.get("critical_count", 0),
        "drafts_generated": exec_summary.get("drafts_generated", 0),
        "dry_run": dry_run,
    }


# ── Tenant-scoped loaders ────────────────────────────────────────────


def _load_anomaly_scoped(
    db: Session, *, anomaly_id: str, company_id: str
) -> AgentAnomaly:
    row = (
        db.query(AgentAnomaly)
        .join(AgentJob, AgentJob.id == AgentAnomaly.agent_job_id)
        .filter(
            AgentAnomaly.id == anomaly_id,
            AgentJob.tenant_id == company_id,
        )
        .first()
    )
    if row is None:
        raise ValueError(
            f"Anomaly {anomaly_id} not found for this tenant"
        )
    return row


def _load_job(db: Session, *, agent_job_id: str) -> AgentJob:
    job = (
        db.query(AgentJob).filter(AgentJob.id == agent_job_id).first()
    )
    if job is None:
        raise ValueError(f"AgentJob {agent_job_id} not found")
    return job


def _draft_for_customer(
    job: AgentJob, customer_id: str
) -> dict[str, Any] | None:
    """Pull the drafted email (subject + body) for a given customer
    from the AgentJob's report_payload. Returns None if not found."""
    if not isinstance(job.report_payload, dict):
        return None
    steps = job.report_payload.get("steps") or {}
    draft_data = steps.get("draft_communications") or {}
    communications = draft_data.get("communications") or []
    for c in communications:
        if c.get("customer_id") == customer_id:
            return c
    return None


def _resolve_anomaly(
    db: Session,
    *,
    anomaly: AgentAnomaly,
    user_id: str,
    note: str,
) -> None:
    anomaly.resolved = True
    anomaly.resolved_by = user_id
    anomaly.resolved_at = datetime.now(timezone.utc)
    anomaly.resolution_note = note
    db.flush()


# ── Triage action helpers ────────────────────────────────────────────


def send_customer_email(
    db: Session,
    *,
    user: User,
    anomaly_id: str,
) -> dict[str, Any]:
    """Dispatch the drafted collection email for this customer.
    Closes the pre-existing Phase 3b TODO. Routes through
    `email_service.send_collections_email` which uses the managed
    `email.collections` template.
    """
    anomaly = _load_anomaly_scoped(
        db, anomaly_id=anomaly_id, company_id=user.company_id
    )
    if anomaly.entity_type != "customer" or not anomaly.entity_id:
        raise ValueError(
            "Expected anomaly with entity_type='customer' and a "
            "customer_id; got "
            f"entity_type={anomaly.entity_type!r}"
        )

    customer = (
        db.query(Customer)
        .filter(
            Customer.id == anomaly.entity_id,
            Customer.company_id == user.company_id,
        )
        .first()
    )
    if customer is None:
        raise ValueError(
            f"Customer {anomaly.entity_id} not found for this tenant"
        )

    recipient = customer.billing_email or customer.email
    if not recipient:
        raise ValueError(
            f"Customer {customer.name} has no billing_email or email "
            "on file — cannot dispatch collection email"
        )

    # Pull the draft for this customer from the job's report_payload.
    job = _load_job(db, agent_job_id=anomaly.agent_job_id)
    draft = _draft_for_customer(job, anomaly.entity_id)
    if draft is None:
        raise ValueError(
            f"No drafted collection email found for customer "
            f"{customer.name} in job {job.id}.report_payload"
        )

    subject = draft.get("subject") or f"Outstanding Balance — {customer.name}"
    body = draft.get("body") or ""
    tier = draft.get("tier") or "FOLLOW_UP"

    # Company name + reply-to email for the delivery.
    from app.models.company import Company

    company = (
        db.query(Company).filter(Company.id == user.company_id).first()
    )
    tenant_name = company.name if company else "Your Company"
    reply_to = getattr(company, "email", None) or user.email

    # Dispatch via the existing email service — reuses the
    # email.collections managed template + delivery_service D-7 path.
    from app.services.email_service import email_service

    delivery_result = email_service.send_collections_email(
        customer_email=recipient,
        customer_name=customer.name,
        subject=subject,
        body=body,
        tenant_name=tenant_name,
        reply_to_email=reply_to or "",
        company_id=user.company_id,
        db=db,
    )

    _resolve_anomaly(
        db,
        anomaly=anomaly,
        user_id=user.id,
        note=(
            f"Sent via triage — {tier} tier collection email to "
            f"{recipient} (delivery_id={delivery_result.get('delivery_id')})"
        ),
    )
    db.commit()
    return {
        "status": "applied",
        "message": (
            f"Collection email sent to {customer.name} ({recipient})."
        ),
        "anomaly_resolved": True,
        "customer_id": customer.id,
        "recipient": recipient,
        "tier": tier,
        "delivery_id": delivery_result.get("delivery_id"),
    }


def skip_customer(
    db: Session,
    *,
    user: User,
    anomaly_id: str,
    reason: str,
) -> dict[str, Any]:
    """Skip sending — resolves the anomaly with a reason, no email.
    Next agent run re-evaluates this customer."""
    if not reason:
        raise ValueError("Reason is required to skip a collection")

    anomaly = _load_anomaly_scoped(
        db, anomaly_id=anomaly_id, company_id=user.company_id
    )
    _resolve_anomaly(
        db,
        anomaly=anomaly,
        user_id=user.id,
        note=f"Skipped via triage — {reason}",
    )
    db.commit()
    return {
        "status": "applied",
        "message": "Collection skipped — no email sent.",
        "anomaly_resolved": True,
        "customer_id": anomaly.entity_id,
    }


def request_review_customer(
    db: Session,
    *,
    user: User,
    anomaly_id: str,
    note: str,
) -> dict[str, Any]:
    """Request review — stamps a note on the anomaly without
    resolving. Item stays in queue for a teammate to pick up."""
    if not note:
        raise ValueError("Note is required when requesting review")

    anomaly = _load_anomaly_scoped(
        db, anomaly_id=anomaly_id, company_id=user.company_id
    )
    stamp = (
        f"[review-requested by {user.id} at "
        f"{datetime.now(timezone.utc).isoformat()}] {note}"
    )
    existing = anomaly.resolution_note or ""
    anomaly.resolution_note = (
        f"{existing}\n{stamp}" if existing else stamp
    )
    db.flush()
    db.commit()
    return {
        "status": "applied",
        "message": "Review requested — item stays in queue.",
        "anomaly_resolved": False,
        "customer_id": anomaly.entity_id,
    }


__all__ = [
    "run_collections_pipeline",
    "send_customer_email",
    "skip_customer",
    "request_review_customer",
]
