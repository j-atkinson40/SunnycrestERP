"""Network intelligence API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.services.network_intelligence_service import (
    accept_suggestion,
    build_platform_health_snapshot,
    dismiss_suggestion,
    get_connection_suggestions,
    get_latest_snapshot,
    get_onboarding_warnings,
    get_snapshot_history,
    get_top_gaps,
    predict_onboarding_timeline,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Tenant-facing network endpoints ──


@router.get("/suggestions")
def list_suggestions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_connection_suggestions(db, current_user.company_id)


@router.post("/suggestions/{suggestion_id}/accept")
def accept(
    suggestion_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not accept_suggestion(db, suggestion_id):
        raise HTTPException(status_code=404)
    return {"status": "connected"}


@router.post("/suggestions/{suggestion_id}/dismiss")
def dismiss(
    suggestion_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not dismiss_suggestion(db, suggestion_id):
        raise HTTPException(status_code=404)
    return {"status": "dismissed"}


# ── Onboarding intelligence ──


@router.get("/onboarding/predictions")
def onboarding_predictions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.company import Company
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    tenant_type = company.preset if company else "manufacturing"
    return predict_onboarding_timeline(db, current_user.company_id, tenant_type)


@router.get("/onboarding/warnings")
def onboarding_warnings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.company import Company
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    tenant_type = company.preset if company else "manufacturing"
    return get_onboarding_warnings(db, current_user.company_id, tenant_type)


# ── Super admin network endpoints ──


@router.get("/admin/health")
def admin_health(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_latest_snapshot(db, "platform_health") or {"message": "No data yet"}


@router.get("/admin/geographic")
def admin_geographic(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_latest_snapshot(db, "geographic_demand") or {"message": "No data yet"}


@router.get("/admin/gaps")
def admin_gaps(
    state: str | None = Query(None),
    limit: int = Query(20),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_top_gaps(db, limit, state)


@router.get("/admin/trends")
def admin_trends(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_latest_snapshot(db, "product_trends") or {"message": "No data yet"}


@router.get("/admin/benchmarks")
def admin_benchmarks(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_latest_snapshot(db, "ar_benchmarks") or {"message": "No data yet"}


@router.get("/admin/transfers")
def admin_transfers(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_latest_snapshot(db, "transfer_patterns") or {"message": "No data yet"}


@router.get("/admin/growth")
def admin_growth(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_snapshot_history(db, "platform_health", 12)


@router.post("/admin/build-snapshot")
def admin_build_snapshot(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manually trigger platform health snapshot (admin only)."""
    result = build_platform_health_snapshot(db)
    if not result:
        return {"status": "skipped", "reason": "insufficient_tenants"}
    return {"status": "built", "data": result}
