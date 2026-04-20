"""Vault → Accounting admin endpoints — Phase V-1e.

Consolidates platform-admin accounting surfaces under
`/api/v1/vault/accounting/*`:

  - Periods + Locks (with audit trail)
  - GL Classification Queue (admin review of AI suggestions)
  - COA Templates (read-only platform standard category definitions)
  - Pending-close aggregation (months month-end-close agent flagged as
    ready to close)
  - Period-audit feed (history of lock/unlock actions)

Tenant-facing Financials Hub (invoices, bills, JEs, statements, reports)
stays in the vertical nav and its existing routes — not touched by this
phase. Deprecated AccountingConnection / QBO / Sage cleanup is a
separate focused build.

All routes require admin via `require_admin`. Tenant isolation enforced
on every query via `current_user.company_id`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models.accounting_analysis import (
    TenantAccountingAnalysis,
    TenantGLMapping,
)
from app.models.agent import AgentJob
from app.models.audit_log import AuditLog
from app.models.journal_entry import AccountingPeriod
from app.models.user import User
from app.services.accounting_analysis_service import PLATFORM_CATEGORIES

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────


_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _period_display_name(period: AccountingPeriod) -> str:
    return f"{_MONTH_NAMES[period.period_month - 1]} {period.period_year}"


def _write_period_audit(
    db: Session,
    *,
    user: User,
    period: AccountingPeriod,
    action: str,
    previous_status: str,
    new_status: str,
) -> AuditLog:
    """Write a period-lock audit row. Append-only by convention — no
    update/delete paths exist on the AuditLog service."""
    import json

    row = AuditLog(
        company_id=user.company_id,
        user_id=user.id,
        action=action,
        entity_type="accounting_period",
        entity_id=period.id,
        changes=json.dumps(
            {
                "period_month": period.period_month,
                "period_year": period.period_year,
                "previous_status": previous_status,
                "new_status": new_status,
                "display_name": _period_display_name(period),
            }
        ),
    )
    db.add(row)
    db.flush()
    return row


# ── Periods + Locks ───────────────────────────────────────────────────


class _PeriodRow(BaseModel):
    id: str
    period_month: int
    period_year: int
    display_name: str
    status: str
    closed_at: datetime | None = None
    closed_by: str | None = None


class _PeriodListResponse(BaseModel):
    periods: list[_PeriodRow]


@router.get("/periods", response_model=_PeriodListResponse)
def list_periods(
    year: int | None = Query(None, ge=2000, le=2100),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List accounting periods for the tenant, optionally filtered by
    year. If no periods exist for the queried year, seed the 12 months
    as 'open' so the UI can render a full year at a glance."""
    q = db.query(AccountingPeriod).filter(
        AccountingPeriod.tenant_id == current_user.company_id,
    )
    if year is not None:
        q = q.filter(AccountingPeriod.period_year == year)
        existing = {p.period_month for p in q.all()}
        missing = [m for m in range(1, 13) if m not in existing]
        if missing:
            for m in missing:
                db.add(
                    AccountingPeriod(
                        tenant_id=current_user.company_id,
                        period_month=m,
                        period_year=year,
                    )
                )
            db.commit()
            # Re-query after seeding.
            q = db.query(AccountingPeriod).filter(
                AccountingPeriod.tenant_id == current_user.company_id,
                AccountingPeriod.period_year == year,
            )
    rows = q.order_by(
        AccountingPeriod.period_year.desc(),
        AccountingPeriod.period_month.desc(),
    ).limit(60).all()
    return _PeriodListResponse(
        periods=[
            _PeriodRow(
                id=p.id,
                period_month=p.period_month,
                period_year=p.period_year,
                display_name=_period_display_name(p),
                status=p.status,
                closed_at=p.closed_at,
                closed_by=p.closed_by,
            )
            for p in rows
        ]
    )


def _get_owned_period(db: Session, user: User, period_id: str) -> AccountingPeriod:
    period = (
        db.query(AccountingPeriod)
        .filter(
            AccountingPeriod.id == period_id,
            AccountingPeriod.tenant_id == user.company_id,
        )
        .first()
    )
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")
    return period


@router.post("/periods/{period_id}/lock")
def lock_period(
    period_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Lock a period. Writes a `period_locked` AuditLog row. Idempotent
    on an already-locked period — returns 409 instead of re-writing
    (prevents double-audit noise)."""
    period = _get_owned_period(db, current_user, period_id)
    if period.status == "closed":
        raise HTTPException(
            status_code=409, detail="Period is already closed"
        )
    previous_status = period.status
    period.status = "closed"
    period.closed_by = current_user.id
    period.closed_at = datetime.now(timezone.utc)
    _write_period_audit(
        db,
        user=current_user,
        period=period,
        action="period_locked",
        previous_status=previous_status,
        new_status="closed",
    )
    db.commit()
    return {
        "status": "closed",
        "period_id": period.id,
        "closed_at": period.closed_at.isoformat(),
    }


@router.post("/periods/{period_id}/unlock")
def unlock_period(
    period_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Unlock a previously-closed period. Writes a `period_unlocked`
    audit row. Idempotent on an already-open period — returns 409."""
    period = _get_owned_period(db, current_user, period_id)
    if period.status != "closed":
        raise HTTPException(
            status_code=409, detail="Period is not closed"
        )
    previous_status = period.status
    period.status = "open"
    period.closed_by = None
    period.closed_at = None
    _write_period_audit(
        db,
        user=current_user,
        period=period,
        action="period_unlocked",
        previous_status=previous_status,
        new_status="open",
    )
    db.commit()
    return {"status": "open", "period_id": period.id}


class _PeriodAuditRow(BaseModel):
    id: str
    action: str
    entity_id: str | None
    user_id: str | None
    created_at: datetime
    changes: dict[str, Any] | None


class _PeriodAuditResponse(BaseModel):
    events: list[_PeriodAuditRow]


@router.get("/period-audit", response_model=_PeriodAuditResponse)
def list_period_audit(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Recent period-lock / unlock activity for the current tenant.

    Returns the last N `period_locked` + `period_unlocked` AuditLog
    rows, newest first. Used by the Periods & Locks tab's "Recent
    Activity" section.
    """
    import json

    rows = (
        db.query(AuditLog)
        .filter(
            AuditLog.company_id == current_user.company_id,
            AuditLog.entity_type == "accounting_period",
            AuditLog.action.in_(["period_locked", "period_unlocked"]),
        )
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
        .all()
    )
    out = []
    for r in rows:
        changes_json: dict[str, Any] | None = None
        if r.changes:
            try:
                changes_json = json.loads(r.changes)
            except ValueError:
                changes_json = None
        out.append(
            _PeriodAuditRow(
                id=r.id,
                action=r.action,
                entity_id=r.entity_id,
                user_id=r.user_id,
                created_at=r.created_at,
                changes=changes_json,
            )
        )
    return _PeriodAuditResponse(events=out)


# ── Pending-close aggregation ─────────────────────────────────────────


class _PendingCloseRow(BaseModel):
    job_id: str
    period_month: int
    period_year: int
    display_name: str
    completed_at: datetime | None
    anomaly_count: int


class _PendingCloseResponse(BaseModel):
    pending: list[_PendingCloseRow]


@router.get("/pending-close", response_model=_PendingCloseResponse)
def list_pending_close(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Months flagged by the month-end-close agent as ready to close.

    Criterion: most recent `month_end_close` agent job per
    (period_year, period_month) whose status is
    `awaiting_approval` or `completed`, AND whose matching
    AccountingPeriod is still `open`. Returns one row per such
    candidate, newest completed_at first.

    This is a derived view — no new persisted state. Re-runs are
    cheap (indexed on tenant_id + job_type).
    """
    # Fetch the agent job tail for this tenant, job_type=month_end_close.
    jobs = (
        db.query(AgentJob)
        .filter(
            AgentJob.tenant_id == current_user.company_id,
            AgentJob.job_type == "month_end_close",
            AgentJob.status.in_(["awaiting_approval", "complete"]),
            AgentJob.period_start.isnot(None),
        )
        .order_by(desc(AgentJob.completed_at))
        .limit(60)
        .all()
    )
    # Collapse to one-per-period (newest wins).
    seen: set[tuple[int, int]] = set()
    out: list[_PendingCloseRow] = []
    for job in jobs:
        if not job.period_start:
            continue
        year = job.period_start.year
        month = job.period_start.month
        key = (year, month)
        if key in seen:
            continue
        # Is the matching AccountingPeriod still open?
        period = (
            db.query(AccountingPeriod)
            .filter(
                AccountingPeriod.tenant_id == current_user.company_id,
                AccountingPeriod.period_year == year,
                AccountingPeriod.period_month == month,
            )
            .first()
        )
        if period is not None and period.status == "closed":
            seen.add(key)
            continue
        seen.add(key)
        out.append(
            _PendingCloseRow(
                job_id=job.id,
                period_month=month,
                period_year=year,
                display_name=f"{_MONTH_NAMES[month - 1]} {year}",
                completed_at=job.completed_at,
                anomaly_count=job.anomaly_count or 0,
            )
        )
    return _PendingCloseResponse(pending=out)


# ── GL Classification Queue ───────────────────────────────────────────


class _ClassificationRow(BaseModel):
    id: str
    mapping_type: str
    source_id: str | None
    source_name: str
    platform_category: str | None
    confidence: float | None
    reasoning: str | None
    alternative: str | None
    status: str
    is_stale: bool
    created_at: datetime


class _ClassificationPendingResponse(BaseModel):
    pending: list[_ClassificationRow]


@router.get(
    "/classification/pending", response_model=_ClassificationPendingResponse
)
def list_pending_classifications(
    limit: int = Query(50, ge=1, le=200),
    mapping_type: str | None = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Pending TenantAccountingAnalysis rows awaiting admin review.

    Filters:
      - status == 'pending'
      - optional `mapping_type` (gl_account / customer / vendor / product)

    Returns newest-confidence first so admin triages high-confidence
    bulk-confirms at the top.
    """
    q = db.query(TenantAccountingAnalysis).filter(
        TenantAccountingAnalysis.tenant_id == current_user.company_id,
        TenantAccountingAnalysis.status == "pending",
    )
    if mapping_type:
        q = q.filter(TenantAccountingAnalysis.mapping_type == mapping_type)
    rows = (
        q.order_by(desc(TenantAccountingAnalysis.confidence))
        .limit(limit)
        .all()
    )
    return _ClassificationPendingResponse(
        pending=[
            _ClassificationRow(
                id=r.id,
                mapping_type=r.mapping_type,
                source_id=r.source_id,
                source_name=r.source_name,
                platform_category=r.platform_category,
                confidence=float(r.confidence) if r.confidence else None,
                reasoning=r.reasoning,
                alternative=r.alternative,
                status=r.status,
                is_stale=r.is_stale,
                created_at=r.created_at,
            )
            for r in rows
        ]
    )


class _ClassificationConfirmBody(BaseModel):
    # Optional override — if None, use the AI's suggestion.
    platform_category: str | None = None


@router.post("/classification/{analysis_id}/confirm")
def confirm_classification(
    analysis_id: str,
    body: _ClassificationConfirmBody | None = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Confirm an AI classification suggestion.

    For `gl_account` rows this also writes a `TenantGLMapping` row so
    downstream agents can resolve the mapping. Returns 404 if the
    analysis row doesn't exist or isn't in the caller's tenant.
    """
    row = (
        db.query(TenantAccountingAnalysis)
        .filter(
            TenantAccountingAnalysis.id == analysis_id,
            TenantAccountingAnalysis.tenant_id == current_user.company_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis row not found")
    if row.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Analysis row is already {row.status!r}",
        )
    chosen = (body.platform_category if body else None) or row.platform_category
    if not chosen:
        raise HTTPException(
            status_code=400,
            detail=(
                "No platform_category — AI did not suggest one and "
                "no override was provided"
            ),
        )
    row.platform_category = chosen
    row.status = "confirmed"
    row.confirmed_at = datetime.now(timezone.utc)
    row.confirmed_by = current_user.id

    # For gl_account rows, create/update the TenantGLMapping so the
    # expense categorization + other agents resolve the mapping at
    # runtime. For other mapping_types (customer/vendor/product),
    # the analysis row itself is the source of truth.
    if row.mapping_type == "gl_account":
        existing = (
            db.query(TenantGLMapping)
            .filter(
                TenantGLMapping.tenant_id == current_user.company_id,
                TenantGLMapping.platform_category == chosen,
                TenantGLMapping.account_name == row.source_name,
            )
            .first()
        )
        if existing is None:
            db.add(
                TenantGLMapping(
                    tenant_id=current_user.company_id,
                    platform_category=chosen,
                    account_name=row.source_name,
                    provider_account_id=row.source_id,
                )
            )
    db.commit()
    return {"status": "confirmed", "id": row.id, "platform_category": chosen}


@router.post("/classification/{analysis_id}/reject")
def reject_classification(
    analysis_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Reject an AI classification suggestion. Removes from the queue
    (status='rejected'). Does NOT create a TenantGLMapping."""
    row = (
        db.query(TenantAccountingAnalysis)
        .filter(
            TenantAccountingAnalysis.id == analysis_id,
            TenantAccountingAnalysis.tenant_id == current_user.company_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis row not found")
    if row.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Analysis row is already {row.status!r}",
        )
    row.status = "rejected"
    row.confirmed_at = datetime.now(timezone.utc)
    row.confirmed_by = current_user.id
    db.commit()
    return {"status": "rejected", "id": row.id}


# ── COA Templates (platform standard category list) ──────────────────


class _CoaTemplateRow(BaseModel):
    category_type: str  # revenue / ar / cogs / ap / expenses
    platform_category: str  # e.g. "vault_sales", "accounts_payable"


class _CoaTemplateResponse(BaseModel):
    templates: list[_CoaTemplateRow]


@router.get("/coa-templates", response_model=_CoaTemplateResponse)
def list_coa_templates(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Platform standard GL category definitions — READ-ONLY.

    The source is `PLATFORM_CATEGORIES` in
    `app.services.accounting_analysis_service`. Tenants can't modify
    these directly; tenant-specific overrides go through the
    Classification tab → TenantGLMapping.
    """
    out: list[_CoaTemplateRow] = []
    for category_type, categories in PLATFORM_CATEGORIES.items():
        for cat in categories:
            out.append(
                _CoaTemplateRow(
                    category_type=category_type,
                    platform_category=cat,
                )
            )
    return _CoaTemplateResponse(templates=out)
