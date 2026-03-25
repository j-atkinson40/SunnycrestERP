"""Financial health + cross-system insight API routes."""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.financial_health_service import get_health_score, get_score_history, run_daily_score
from app.services.cross_system_insight_service import detect_all_insights, dismiss_insight, get_active_insights

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/score")
def get_score(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get today's financial health score (calculates if needed)."""
    return get_health_score(db, current_user.company_id)


@router.get("/history")
def score_history(
    days: int = Query(30, ge=7, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get score history for chart."""
    return get_score_history(db, current_user.company_id, days)


@router.post("/recalculate")
def recalculate(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Force recalculate today's health score."""
    return run_daily_score(db, current_user.company_id, date.today())


@router.get("/cross-system")
def cross_system_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get active cross-system insights."""
    return get_active_insights(db, current_user.company_id)


@router.post("/cross-system/detect")
def run_detection(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger cross-system insight detection."""
    count = detect_all_insights(db, current_user.company_id)
    return {"active_insights": count}


@router.post("/cross-system/{insight_id}/dismiss")
def dismiss(
    insight_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not dismiss_insight(db, insight_id):
        raise HTTPException(status_code=404)
    return {"status": "dismissed"}
