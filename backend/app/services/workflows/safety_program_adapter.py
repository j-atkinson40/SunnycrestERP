"""Safety Program Generation — parity adapter (Workflow Arc Phase 8d.1).

Thin bridge between the `wf_sys_safety_program_gen` workflow + the
`safety_program_triage` queue and the existing
`safety_program_generation_service`. The service already owns the
full pipeline — OSHA scrape, Claude generation, WeasyPrint PDF,
approve/reject mechanics. The adapter's only jobs are:

  1. Pipeline entry (workflow-step surface) — wraps
     `run_monthly_generation` for each tenant when the workflow
     scheduler fires on the 1st-of-month cron tick.
  2. Triage action helpers — approve / reject / request_review that
     delegate to the service verbatim.

This is the first migration exercising **AI-generation-with-approval
shape**. Unlike 8b (rule-based matching), 8c (analysis + period lock,
email drafts, AI-assisted classification), or 8d (scheduled follow-ups,
external-data staging), the safety program flow:

  - generates a complete document via Claude (non-deterministic AI
    output — approval acts on opaque bytes, not testable content)
  - stages the generation + PDF for staff review
  - on approve, promotes the generation to the tenant's canonical
    `SafetyProgram` row (version++ on existing, insert on new) — OSHA
    compliance's legal "what's our written program" answer

**Parity discipline — AI-generation-content-invariant (Template v2.2 §5.5.5):**
The adapter does NOT try to assert AI output reproducibility. Parity
is asserted on APPROVAL MECHANICS — given the same seeded
pending_review generation, both legacy `svc.approve_generation` and
triage `approve_generation` produce byte-identical field writes on
`SafetyProgramGeneration` + `SafetyProgram`. Content survives the
approval transition unchanged; it's never re-generated, re-rendered,
or re-uploaded.

**No AgentJob wrapper.** Unlike 8b/8c accounting migrations that
create AgentJob as a container for anomalies, safety_program uses
`SafetyProgramGeneration` as both the domain entity AND the review
unit. Creating a parallel AgentJob row would be double-bookkeeping
with no operational value. The triage queue reads directly from
`SafetyProgramGeneration WHERE status='pending_review'`.

**Cardinality: per-generation-run** (Template v2.2 §10). Distinct
from per-job (AgentJob-backed) and per-staging-row (catalog_fetch's
UrnCatalogSyncLog-backed) because the state machine
(`draft/pending_review/approved/rejected`) predates the arc and
lives on the domain entity itself.

**Zero-duplication:** approval + rejection write paths delegate
straight to `svc.approve_generation` + `svc.reject_generation`.

Public functions:

  run_generation_pipeline(db, *, company_id, triggered_by_user_id,
                          dry_run, trigger_source) -> dict
      Workflow-step surface. Wraps svc.run_monthly_generation for
      this tenant; returns a structured summary dict.

  approve_generation(db, *, user, generation_id, notes=None) -> dict
      Triage approve. Delegates to svc.approve_generation. Promotes
      the generation to the canonical SafetyProgram (insert new or
      version++ existing on matching osha_standard_code).

  reject_generation(db, *, user, generation_id, reason) -> dict
      Triage reject. Delegates to svc.reject_generation. Rejects on
      empty reason (matches legacy 400 behavior).

  request_review(db, *, user, generation_id, note) -> dict
      Triage request-review. Appends a timestamped note to
      review_notes without changing status — item stays in-queue for
      a teammate (e.g., compliance officer) to pick up.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.safety_program_generation import SafetyProgramGeneration
from app.models.user import User

logger = logging.getLogger(__name__)


# ── Pipeline entry (workflow-step surface) ───────────────────────────


def run_generation_pipeline(
    db: Session,
    *,
    company_id: str,
    triggered_by_user_id: str | None,
    dry_run: bool = False,
    trigger_source: str = "workflow",
) -> dict[str, Any]:
    """Run the monthly safety program generation pipeline for one tenant.

    Called by `wf_sys_safety_program_gen` via `call_service_method` on
    the 1st-of-month workflow scheduler tick (tenant-local 6am). The
    pipeline is idempotent-within-a-month: if a SafetyProgramGeneration
    already exists for (tenant, year, month), the service returns
    status="skipped" rather than creating a duplicate.

    No AgentJob row is created — SafetyProgramGeneration is the only
    tracking entity.

    `dry_run=True` is accepted for forward-compat but the legacy
    service doesn't support a dry-run path; we surface that by
    returning a "skipped: dry_run_unsupported" status. The workflow
    config doesn't pass dry_run in practice.
    """
    from app.services.safety_program_generation_service import (
        run_monthly_generation,
    )

    if dry_run:
        return {
            "status": "skipped",
            "reason": "dry_run_unsupported",
            "note": (
                "The safety program generation pipeline does not have "
                "a dry-run mode. Invoke with dry_run=False or through "
                "the ad-hoc /safety/programs/generate-for-topic "
                "endpoint to preview a specific topic."
            ),
            "dry_run": True,
            "trigger_source": trigger_source,
        }

    # Delegate to the legacy service — zero logic duplication. The
    # service handles schedule lookup, existence check, generation
    # row creation, OSHA scrape, Claude generation, and PDF render.
    try:
        result = run_monthly_generation(db, company_id)
    except Exception as exc:  # noqa: BLE001 — surface to workflow step
        logger.exception(
            "Safety program pipeline failed for tenant %s: %s",
            company_id,
            exc,
        )
        return {
            "status": "errored",
            "error": str(exc)[:500],
            "trigger_source": trigger_source,
            "triggered_by_user_id": triggered_by_user_id,
        }

    return {
        "status": result.get("status", "unknown"),
        "generation_id": result.get("generation_id"),
        "topic": result.get("topic"),
        "osha_scrape_status": result.get("osha_scrape_status"),
        "reason": result.get("reason"),
        "trigger_source": trigger_source,
        "triggered_by_user_id": triggered_by_user_id,
    }


# ── Triage action helpers ────────────────────────────────────────────


def _load_generation_scoped(
    db: Session, *, generation_id: str, company_id: str
) -> SafetyProgramGeneration:
    """Fetch a SafetyProgramGeneration scoped to a tenant. Defense-
    in-depth — the triage API already gates by user.company_id, but
    callers (including workflow steps) may pass attacker-controlled
    generation_id through the adapter's public surface."""
    row = (
        db.query(SafetyProgramGeneration)
        .filter(
            SafetyProgramGeneration.id == generation_id,
            SafetyProgramGeneration.tenant_id == company_id,
        )
        .first()
    )
    if row is None:
        raise ValueError(
            f"Safety program generation {generation_id} not found "
            "for this tenant"
        )
    return row


def approve_generation(
    db: Session,
    *,
    user: User,
    generation_id: str,
    notes: str | None = None,
) -> dict[str, Any]:
    """Approve a pending_review safety program generation.

    Delegates to `svc.approve_generation` — zero duplication. The
    service handles status transition (`pending_review → approved`),
    reviewer field stamping, and the SafetyProgram upsert (insert
    new on no match OR version++ on existing match keyed by
    `(company_id, osha_standard_code)`).

    Parity claim: this path produces byte-identical field writes on
    SafetyProgramGeneration + SafetyProgram as the legacy
    `POST /safety/programs/generations/{id}/approve` route.
    """
    from app.services.safety_program_generation_service import (
        approve_generation as svc_approve,
    )

    # Scope-check first (legacy route does this via router dependency;
    # we do it inline for defense-in-depth).
    _load_generation_scoped(
        db, generation_id=generation_id, company_id=user.company_id
    )

    try:
        gen = svc_approve(db, generation_id, user.id, notes)
    except ValueError as exc:
        # Legacy service raises ValueError for wrong-status approval
        # ("Cannot approve generation in status 'approved'"); surface
        # identically so legacy HTTP 400 behavior is preserved when
        # the route layer maps ValueError → 400.
        raise ValueError(str(exc)) from exc

    return {
        "status": "applied",
        "message": (
            f"Safety program approved and promoted to "
            f"SafetyProgram {gen.safety_program_id}"
        ),
        "generation_id": gen.id,
        "safety_program_id": gen.safety_program_id,
        "generation_status": gen.status,
        "reviewed_by": gen.reviewed_by,
        "reviewed_at": (
            gen.reviewed_at.isoformat() if gen.reviewed_at else None
        ),
        "posted_at": (
            gen.posted_at.isoformat() if gen.posted_at else None
        ),
    }


def reject_generation(
    db: Session,
    *,
    user: User,
    generation_id: str,
    reason: str,
) -> dict[str, Any]:
    """Reject a pending_review safety program generation.

    Mirrors the legacy route's reject behavior: the service requires
    notes (we enforce empty-reason rejection here to match legacy
    400), delegates to svc.reject_generation which transitions
    status → 'rejected' and stamps reviewer fields. No SafetyProgram
    write on reject (negative-assertion parity test category).
    """
    from app.services.safety_program_generation_service import (
        reject_generation as svc_reject,
    )

    if not reason or not reason.strip():
        # Matches legacy route's 400 "Rejection notes are required".
        raise ValueError("Rejection notes are required")

    _load_generation_scoped(
        db, generation_id=generation_id, company_id=user.company_id
    )

    try:
        gen = svc_reject(db, generation_id, user.id, reason)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    return {
        "status": "applied",
        "message": "Safety program generation rejected.",
        "generation_id": gen.id,
        "generation_status": gen.status,
        "reviewed_by": gen.reviewed_by,
        "reviewed_at": (
            gen.reviewed_at.isoformat() if gen.reviewed_at else None
        ),
    }


def request_review(
    db: Session,
    *,
    user: User,
    generation_id: str,
    note: str,
) -> dict[str, Any]:
    """Request a second opinion without resolving.

    Appends a timestamped note to `review_notes` in the format:

        [Request-review YYYY-MM-DDTHH:MM:SS by user@email.com]: <note>

    Separated from any existing content by a newline. Status stays
    `pending_review` — item remains in-queue for a teammate (e.g.,
    compliance officer for the second-opinion case).

    No schema change: uses the existing review_notes Text column.
    """
    if not note or not note.strip():
        raise ValueError("A note is required when requesting review")

    gen = _load_generation_scoped(
        db, generation_id=generation_id, company_id=user.company_id
    )

    stamp = (
        f"[Request-review "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')} "
        f"by {user.email}]: {note.strip()}"
    )
    existing = gen.review_notes or ""
    gen.review_notes = f"{existing}\n{stamp}" if existing else stamp
    db.commit()
    db.refresh(gen)

    return {
        "status": "applied",
        "message": "Review requested — generation stays in queue.",
        "generation_id": gen.id,
        "generation_status": gen.status,
        "review_notes": gen.review_notes,
    }


__all__ = [
    "run_generation_pipeline",
    "approve_generation",
    "reject_generation",
    "request_review",
]
