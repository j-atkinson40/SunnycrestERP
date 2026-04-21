"""FH Aftercare 7-Day Follow-up — parity adapter (Workflow Arc Phase 8d).

Thin bridge between the `wf_fh_aftercare_7day` workflow + the
aftercare_triage queue and the outbound email + vault-log writes.

Why an adapter if there's no legacy agent to parity-test against?

The pre-8d seed referenced `template="aftercare_7day"` — a template
key that didn't exist in the D-2 template registry. If the workflow's
scheduler ever fired (`time_after_event` 7 days after service_date),
the `send_email` step would silently produce no email. Phase 8d
formalizes the path:

  1. scheduler fire → `run_pipeline` stages items in FhAftercareQueue
     (one per case whose service_date + 7 falls in the window)
  2. each staged item materialises as an AgentJob + anomaly so the
     triage queue can pull it via `_dq_aftercare_triage`
  3. triage `approve` → `approve_send` renders the managed
     `email.fh_aftercare_7day` template, sends via D-7
     delivery_service, logs a VaultItem, resolves the anomaly
  4. triage `skip` → resolves the anomaly without sending

One-item-per-case matrix. The adapter uses AgentJob even though
there is no "agent" in the accounting sense — the job is the
container anomalies hang off, matching the Phase 8b/c pattern so
the triage engine can reuse its anomaly-backed queue infrastructure.

Public functions:

  run_pipeline(db, *, company_id, triggered_by_user_id, dry_run,
               trigger_source) -> dict
      Fires from `wf_fh_aftercare_7day` via `call_service_method`.
      Finds FuneralCase rows whose service_date + 7 days is the run
      date, creates one AgentJob + one anomaly per case. Returns a
      summary dict with counts + job_id.

  approve_send(db, *, user, anomaly_id) -> dict
      Triage approve action. Renders the managed email template +
      sends via delivery_service + logs a VaultItem + resolves the
      anomaly. Returns result dict with delivery_id.

  skip_case(db, *, user, anomaly_id, reason) -> dict
      Triage skip action. Resolves the anomaly with a reason; no
      email sent.

  request_review(db, *, user, anomaly_id, note) -> dict
      Escalation — stamps a review note without resolving. The
      anomaly stays in-queue.

Zero-duplication discipline:
  - Email rendering + delivery goes through the managed D-2 +
    D-7 pipeline (`email.fh_aftercare_7day` managed template +
    `delivery_service.send_email_with_template`). Do not re-render
    inline; every change to the email body flows through the
    template editor.
  - VaultItem creation matches the pre-8d seed's `log_vault_item`
    step intent (event_type="aftercare_message", related
    funeral_case linkage).
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent import AgentJob
from app.models.agent_anomaly import AgentAnomaly
from app.models.funeral_case import (
    CaseDeceased,
    CaseInformant,
    CaseService,
    FuneralCase,
)
from app.models.user import User
from app.schemas.agent import AgentJobStatus, AnomalySeverity

logger = logging.getLogger(__name__)


# Anomaly type for aftercare items. Narrowly scoped — the triage
# engine's `_dq_aftercare_triage` filters on this type to pick up
# aftercare items without accidentally pulling future per-case
# anomaly types that may share the same job_type.
ANOMALY_TYPE = "fh_aftercare_pending"


# Not in the accounting-agent AgentJobType enum; define a string
# constant so the triage engine can filter without enum coupling.
AFTERCARE_JOB_TYPE = "fh_aftercare"


# ── Pipeline entry (workflow-step surface) ───────────────────────────


def run_pipeline(
    db: Session,
    *,
    company_id: str,
    triggered_by_user_id: str | None,
    dry_run: bool = False,
    trigger_source: str = "workflow",
) -> dict[str, Any]:
    """Stage aftercare items for cases whose service_date was 7 days
    ago (inclusive of the run date's day-of boundary).

    Called by `wf_fh_aftercare_7day` via `call_service_method`.
    Idempotent-within-a-day: if a job for this tenant + today's
    staging date already exists, we reuse it rather than
    double-staging (the triage engine would otherwise show
    duplicate items for the same case).
    """
    today = date.today()
    target_service_date = today - timedelta(days=7)

    # Find cases with service_date = today - 7.
    cases = (
        db.query(FuneralCase, CaseService)
        .join(CaseService, CaseService.case_id == FuneralCase.id)
        .filter(
            FuneralCase.company_id == company_id,
            CaseService.service_date == target_service_date,
        )
        .all()
    )

    if not cases:
        return {
            "status": "applied",
            "agent_job_id": None,
            "cases_staged": 0,
            "dry_run": dry_run,
            "target_service_date": target_service_date.isoformat(),
        }

    # Idempotency: look for an existing job scoped to today so a
    # re-run doesn't double-enqueue. We identify by period_start +
    # period_end both == today for the aftercare job_type.
    existing = (
        db.query(AgentJob)
        .filter(
            AgentJob.tenant_id == company_id,
            AgentJob.job_type == AFTERCARE_JOB_TYPE,
            AgentJob.period_start == today,
            AgentJob.period_end == today,
        )
        .order_by(AgentJob.created_at.desc())
        .first()
    )
    if existing is not None and not dry_run:
        return {
            "status": "applied",
            "agent_job_id": existing.id,
            "cases_staged": existing.anomaly_count or 0,
            "dry_run": dry_run,
            "target_service_date": target_service_date.isoformat(),
            "idempotent_reuse": True,
        }

    job = AgentJob(
        id=str(uuid.uuid4()),
        tenant_id=company_id,
        job_type=AFTERCARE_JOB_TYPE,
        status=AgentJobStatus.COMPLETE.value,
        period_start=today,
        period_end=today,
        dry_run=dry_run,
        triggered_by=triggered_by_user_id,
        trigger_type=trigger_source,
        run_log=[],
        anomaly_count=0,
        report_payload={
            "target_service_date": target_service_date.isoformat(),
            "pipeline": "fh_aftercare_7day",
        },
    )
    db.add(job)
    db.flush()

    staged = 0
    for fc, service in cases:
        anomaly = AgentAnomaly(
            id=str(uuid.uuid4()),
            agent_job_id=job.id,
            severity=AnomalySeverity.INFO.value,
            anomaly_type=ANOMALY_TYPE,
            entity_type="funeral_case",
            entity_id=fc.id,
            description=(
                f"Aftercare 7-day follow-up due for case {fc.case_number}"
            ),
            resolved=False,
        )
        db.add(anomaly)
        staged += 1

    job.anomaly_count = staged
    if dry_run:
        db.rollback()
    else:
        db.commit()

    return {
        "status": "applied",
        "agent_job_id": job.id if not dry_run else None,
        "cases_staged": staged,
        "dry_run": dry_run,
        "target_service_date": target_service_date.isoformat(),
    }


# ── Triage helpers ───────────────────────────────────────────────────


def _load_case_context(
    db: Session, *, case_id: str, company_id: str
) -> dict[str, Any]:
    """Pull everything an aftercare email + vault-log needs from a
    single case. Denormalized so the triage row display + email
    render share one fetch."""
    fc = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.company_id == company_id,
        )
        .first()
    )
    if fc is None:
        raise ValueError(f"Case {case_id} not found for this tenant")
    deceased = (
        db.query(CaseDeceased)
        .filter(CaseDeceased.case_id == case_id)
        .first()
    )
    informant = (
        db.query(CaseInformant)
        .filter(
            CaseInformant.case_id == case_id,
            CaseInformant.is_primary.is_(True),
        )
        .first()
    )
    # Fall back to any informant if no is_primary row exists.
    if informant is None:
        informant = (
            db.query(CaseInformant)
            .filter(CaseInformant.case_id == case_id)
            .order_by(CaseInformant.created_at.asc())
            .first()
        )
    service = (
        db.query(CaseService)
        .filter(CaseService.case_id == case_id)
        .first()
    )
    family_surname = (
        (deceased.last_name if deceased else None)
        or (fc.case_number or "").split("-")[0]
        or "the"
    )
    return {
        "case": fc,
        "deceased": deceased,
        "informant": informant,
        "service": service,
        "family_surname": family_surname,
        "primary_email": informant.email if informant else None,
        "primary_name": informant.name if informant else None,
    }


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
        raise ValueError(f"Anomaly {anomaly_id} not found for this tenant")
    return row


def _resolve_anomaly(
    db: Session, *, anomaly: AgentAnomaly, user_id: str, note: str
) -> None:
    anomaly.resolved = True
    anomaly.resolved_by = user_id
    anomaly.resolved_at = datetime.now(timezone.utc)
    anomaly.resolution_note = note
    db.flush()


# ── Triage action surface ────────────────────────────────────────────


def approve_send(
    db: Session, *, user: User, anomaly_id: str
) -> dict[str, Any]:
    """Send the aftercare email for the case backing this anomaly.

    Renders the managed `email.fh_aftercare_7day` template via
    delivery_service, logs a VaultItem, resolves the anomaly.
    Returns delivery metadata so the triage UI can show "sent to
    mary@family.com".
    """
    anomaly = _load_anomaly_scoped(
        db, anomaly_id=anomaly_id, company_id=user.company_id
    )
    if anomaly.entity_type != "funeral_case" or not anomaly.entity_id:
        raise ValueError("Anomaly is not linked to a funeral_case")

    ctx = _load_case_context(
        db, case_id=anomaly.entity_id, company_id=user.company_id
    )
    recipient_email = ctx["primary_email"]
    if not recipient_email:
        raise ValueError(
            "Primary contact has no email address — cannot send aftercare follow-up"
        )

    # FH display name for the template sign-off. Falls back to
    # "Your funeral home team" via the template's Jinja default.
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == user.company_id).first()
    funeral_home_name = (company.name if company is not None else None)

    # Send via D-7 managed-template path. The adapter does NOT
    # construct HTML inline — every byte of email body comes from
    # the `email.fh_aftercare_7day` template registered via r40.
    from app.services.delivery.delivery_service import (
        send_email_with_template,
    )

    delivery_id = None
    try:
        delivery_row = send_email_with_template(
            db,
            company_id=user.company_id,
            to_email=recipient_email,
            to_name=ctx["primary_name"],
            template_key="email.fh_aftercare_7day",
            template_context={
                "family_surname": ctx["family_surname"],
                "funeral_home_name": funeral_home_name,
            },
            caller_module="aftercare_adapter",
        )
        delivery_id = getattr(delivery_row, "id", None)
    except Exception as exc:  # noqa: BLE001 — surface as step error
        logger.exception("Aftercare email send failed: %s", exc)
        raise

    # Log the vault item (matches pre-8d seed's step 2 intent).
    try:
        from app.services.vault_service import create_vault_item

        create_vault_item(
            db,
            company_id=user.company_id,
            item_type="communication",
            event_type="aftercare_message",
            title="7-day aftercare message sent",
            related_entity_type="funeral_case",
            related_entity_id=anomaly.entity_id,
            metadata_json={
                "family_surname": ctx["family_surname"],
                "recipient_email": recipient_email,
                "delivery_id": delivery_id,
            },
        )
    except Exception:  # noqa: BLE001
        # Vault write is audit-flavor; don't fail the user's approve
        # click if it breaks. Log + continue.
        logger.exception(
            "Aftercare vault-item creation failed (email already sent)"
        )

    _resolve_anomaly(
        db,
        anomaly=anomaly,
        user_id=user.id,
        note=(
            f"Aftercare email sent to {recipient_email} "
            f"(delivery_id={delivery_id})"
        ),
    )
    db.commit()
    return {
        "status": "applied",
        "message": f"Aftercare email sent to {recipient_email}",
        "case_id": anomaly.entity_id,
        "anomaly_id": anomaly_id,
        "delivery_id": delivery_id,
        "recipient_email": recipient_email,
    }


def skip_case(
    db: Session, *, user: User, anomaly_id: str, reason: str
) -> dict[str, Any]:
    """Skip the aftercare send for this case. Resolves the anomaly
    with a reason; no email leaves the system. The case stays
    eligible for manual follow-up; no auto re-queue."""
    if not reason:
        raise ValueError("Reason is required to skip an aftercare send")
    anomaly = _load_anomaly_scoped(
        db, anomaly_id=anomaly_id, company_id=user.company_id
    )
    _resolve_anomaly(
        db,
        anomaly=anomaly,
        user_id=user.id,
        note=f"Skipped aftercare send — {reason}",
    )
    db.commit()
    return {
        "status": "applied",
        "message": "Aftercare send skipped.",
        "case_id": anomaly.entity_id,
        "anomaly_id": anomaly_id,
    }


def request_review(
    db: Session, *, user: User, anomaly_id: str, note: str
) -> dict[str, Any]:
    """Escalate to a teammate — stamps a review note without
    resolving. Item stays in-queue."""
    if not note:
        raise ValueError("A note is required when requesting review")
    anomaly = _load_anomaly_scoped(
        db, anomaly_id=anomaly_id, company_id=user.company_id
    )
    existing = anomaly.resolution_note or ""
    stamp = (
        f"[review-requested by {user.id} at "
        f"{datetime.now(timezone.utc).isoformat()}] {note}"
    )
    anomaly.resolution_note = f"{existing}\n{stamp}" if existing else stamp
    db.flush()
    db.commit()
    return {
        "status": "applied",
        "message": "Review requested — case stays in queue.",
        "case_id": anomaly.entity_id,
        "anomaly_id": anomaly_id,
    }


__all__ = [
    "run_pipeline",
    "approve_send",
    "skip_case",
    "request_review",
    "ANOMALY_TYPE",
    "AFTERCARE_JOB_TYPE",
]
