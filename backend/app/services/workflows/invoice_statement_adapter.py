"""Invoice & Statement Run workflow adapter (demo artifacts 3c).

Thin wrappers exposing the EXISTING (backend-health-corrected) invoice +
statement services to the workflow engine via `call_service_method`. Each wraps
a real service function and returns a JSON-able summary (the engine stores step
output as JSON). No new business logic — composition only, per
moc_demo_artifacts_investigation.md.

  - run_invoice_generation → draft_invoice_service.generate_draft_invoices
    (the P0-corrected service: nullable actor, not the FK-violating "system").
  - run_statement_run      → statement_generation_service.generate_statement_run.

Registered in workflow_engine._SERVICE_METHOD_REGISTRY. Auto-injected kwargs
(db, company_id, triggered_by_user_id) per the registry contract.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.invoice import Invoice


def _as_date(v: Any) -> date | None:
    if v is None or isinstance(v, date):
        return v
    return datetime.fromisoformat(str(v)).date()


def run_invoice_generation(
    db: Session,
    *,
    company_id: str,
    triggered_by_user_id: str | None = None,
    **_ignored: Any,
) -> dict[str, Any]:
    """Generate draft invoices for the tenant's eligible orders → a summary."""
    from app.services import draft_invoice_service

    before = (
        db.query(Invoice).filter(Invoice.company_id == company_id).count()
    )
    draft_invoice_service.generate_draft_invoices(db, company_id)
    after = db.query(Invoice).filter(Invoice.company_id == company_id).count()
    return {"invoices_generated": after - before, "total_invoices": after}


def run_statement_run(
    db: Session,
    *,
    company_id: str,
    triggered_by_user_id: str | None = None,
    period_start: Any = None,
    period_end: Any = None,
    **_ignored: Any,
) -> dict[str, Any]:
    """Generate a statement run for the period (default: current month) → a
    summary. period_start/period_end may arrive as ISO strings from workflow
    config — parsed here."""
    from app.services import statement_generation_service

    today = date.today()
    ps = _as_date(period_start) or today.replace(day=1)
    pe = _as_date(period_end) or today
    run = statement_generation_service.generate_statement_run(
        db, company_id, triggered_by_user_id, ps, pe
    )
    return {
        "statement_run_id": run.id,
        "total_customers": run.total_customers,
        # BSS-1: surfaced so the approval gate can ask about what it SAYS it
        # asks about. The gate's prompt is "Review flagged statements", and the
        # step output carried only `total_customers` — so any `park_when` would
        # have had to gate on the wrong number, parking on a clean run of forty
        # unflagged statements. NOTHING IS COMPUTED HERE: statement_generation_
        # service already counts these (`:339-424`) and already uses the count
        # to set `run.status` ("in_review" when > 0, else "draft").
        "flagged_count": run.flagged_count,
        "run_status": run.status,
        "period_start": ps.isoformat(),
        "period_end": pe.isoformat(),
    }


def run_statement_dispatch(
    db: Session,
    *,
    company_id: str,
    triggered_by_user_id: str | None = None,
    statement_run_id: Any = None,
    **_ignored: Any,
) -> dict[str, Any]:
    """Dispatch an approved statement run → a summary. BSS-2 D-4.

    Thin wrapper over `statement_service.send_all_digital`, which was already a
    real per-item fan-out with per-item ledger writes and simply had no workflow
    entry point. The `_deliberately_broken` note this replaces claimed bulk
    dispatch did not exist; it did, and was unreachable from here.

    ⚠️ RAISES on hard failures, by design. D-3 classifies a render failure or an
    unanswered send as HARD: per-item state is committed inside the loop first,
    then one terminal raise. So a failed run here means "some items did not
    dispatch and the ledger records exactly which" — NOT "the run did nothing".
    Soft outcomes (no address → `skipped`, provider rejection → `failed`) are
    recorded and do not raise.
    """
    from app.services import statement_service

    if not statement_run_id:
        # The producer emits `statement_run_id`; a missing one means the step is
        # wired to the wrong output key, which is a configuration error rather
        # than an empty run — say so instead of silently dispatching nothing.
        raise ValueError(
            "run_statement_dispatch requires statement_run_id "
            "(bind it to {output.generate_statements.statement_run_id})"
        )

    result = statement_service.send_all_digital(db, str(statement_run_id), company_id)
    return {
        "statement_run_id": str(statement_run_id),
        "sent": result.get("sent", 0),
        "failed": result.get("failed", 0),
        # Soft outcome, surfaced separately so a caller can tell a
        # paper-statement cohort from a broken one.
        "skipped": result.get("skipped", 0),
    }
