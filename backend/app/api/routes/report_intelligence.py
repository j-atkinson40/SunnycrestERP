"""Report intelligence API routes — commentary, trends, forecasts, preflight."""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.report_intelligence_service import (
    generate_forecasts,
    get_commentary,
    get_forecasts,
    get_preflight_result,
    get_trend_data,
    override_preflight,
    run_preflight,
    start_commentary_generation,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Commentary ──


@router.get("/commentary/{commentary_id}")
def poll_commentary(
    commentary_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Poll for commentary generation status."""
    result = get_commentary(db, commentary_id)
    if not result:
        raise HTTPException(status_code=404)
    return result


class CommentaryRequest(BaseModel):
    report_type: str
    period_start: str
    period_end: str
    key_metrics: dict
    report_run_id: str | None = None


@router.post("/commentary/generate")
def trigger_commentary(
    body: CommentaryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start commentary generation for a report. Returns ID for polling."""
    cid = start_commentary_generation(
        db=db,
        tenant_id=current_user.company_id,
        report_type=body.report_type,
        period_start=date.fromisoformat(body.period_start),
        period_end=date.fromisoformat(body.period_end),
        key_metrics=body.key_metrics,
        report_run_id=body.report_run_id,
    )
    return {"commentary_id": cid}


# ── Trends ──


@router.get("/trends")
def get_trends(
    report_type: str = Query(...),
    periods: int = Query(6),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get snapshot history for trend display / sparklines."""
    return get_trend_data(db, current_user.company_id, report_type, periods)


# ── Forecasts ──


@router.get("/forecasts")
def list_forecasts(
    forecast_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_forecasts(db, current_user.company_id, forecast_type)


@router.post("/forecasts/generate")
def trigger_forecast_generation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger forecast generation."""
    result = generate_forecasts(db, current_user.company_id)
    return result


# ── Audit Pre-flight ──


class PreflightRequest(BaseModel):
    audit_package_id: str | None = None
    period_start: str | None = None
    period_end: str | None = None


@router.post("/preflight/run")
def trigger_preflight(
    body: PreflightRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run audit pre-flight checks."""
    ps = date.fromisoformat(body.period_start) if body.period_start else None
    pe = date.fromisoformat(body.period_end) if body.period_end else None
    return run_preflight(db, current_user.company_id, body.audit_package_id, ps, pe)


@router.get("/preflight/{result_id}")
def get_preflight(
    result_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = get_preflight_result(db, result_id)
    if not result:
        raise HTTPException(status_code=404)
    return result


class OverrideRequest(BaseModel):
    reason: str


@router.post("/preflight/{result_id}/override")
def override_preflight_check(
    result_id: str,
    body: OverrideRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not override_preflight(db, result_id, current_user.id, body.reason):
        raise HTTPException(status_code=400, detail="Cannot override — not in blocked status")
    return {"status": "overridden"}
