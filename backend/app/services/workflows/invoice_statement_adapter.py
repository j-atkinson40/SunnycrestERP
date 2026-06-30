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
        "period_start": ps.isoformat(),
        "period_end": pe.isoformat(),
    }
