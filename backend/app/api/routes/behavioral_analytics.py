"""Behavioral analytics API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.behavioral_analytics_service import (
    add_feedback,
    dismiss_insight,
    get_insight_count,
    get_insights,
    get_profile,
    mark_insight_seen,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class DismissRequest(BaseModel):
    reason: str | None = None
    suppress_days: int = 90


class FeedbackRequest(BaseModel):
    feedback_type: str
    note: str | None = None


@router.get("/insights")
def list_insights(
    status: str | None = Query(None),
    scope: str | None = Query(None),
    entity_id: str | None = Query(None),
    limit: int = Query(50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_insights(db, current_user.company_id, status, scope, entity_id, limit)


@router.get("/insights/count")
def insight_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"count": get_insight_count(db, current_user.company_id)}


@router.patch("/insights/{insight_id}/seen")
def mark_seen(
    insight_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mark_insight_seen(db, insight_id)
    return {"status": "ok"}


@router.post("/insights/{insight_id}/dismiss")
def dismiss(
    insight_id: str,
    body: DismissRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not dismiss_insight(db, insight_id, current_user.id, body.reason, body.suppress_days):
        raise HTTPException(status_code=404)
    return {"status": "dismissed"}


@router.post("/insights/{insight_id}/feedback")
def submit_feedback(
    insight_id: str,
    body: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    add_feedback(db, current_user.company_id, insight_id, current_user.id, body.feedback_type, body.note)
    return {"status": "ok"}


@router.get("/profiles/{entity_type}/{entity_id}")
def get_entity_profile(
    entity_type: str,
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_profile(db, current_user.company_id, entity_type, entity_id)
    if not profile:
        return {"profile": None}
    return {"profile": profile}
