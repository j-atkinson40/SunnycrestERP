"""Employee training API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.services.training_service import (
    complete_flow,
    complete_module,
    create_learning_profile,
    get_all_employees_learning,
    get_explanation,
    get_learning_profile,
    get_procedure,
    get_procedures,
    get_track_progress,
    should_offer_flow,
    start_flow,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateProfileRequest(BaseModel):
    training_role: str


class CompleteModuleRequest(BaseModel):
    module_key: str
    comprehension_passed: bool


class StartFlowRequest(BaseModel):
    total_steps: int


# ── Learning Profile ──


@router.get("/profile")
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_learning_profile(db, current_user.company_id, current_user.id)
    if not profile:
        return {"exists": False}
    return {**profile, "exists": True}


@router.post("/profile")
def create_profile(
    body: CreateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.training_role not in ("accounting", "inside_sales", "operations", "manager", "owner"):
        raise HTTPException(status_code=400, detail="Invalid training role")
    create_learning_profile(db, current_user.company_id, current_user.id, body.training_role)
    return {"status": "created"}


# ── Track Progress ──


@router.get("/track/progress")
def track_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    progress = get_track_progress(db, current_user.company_id, current_user.id)
    if not progress:
        return {"exists": False}
    return {**progress, "exists": True}


@router.post("/track/complete-module")
def complete_mod(
    body: CompleteModuleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = complete_module(db, current_user.company_id, current_user.id, body.module_key, body.comprehension_passed)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Procedures ──


@router.get("/procedures")
def list_procedures(
    category: str | None = Query(None),
    role: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_procedures(db, current_user.company_id, category, role)


@router.get("/procedures/{key}")
def get_proc(
    key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    proc = get_procedure(db, current_user.company_id, key)
    if not proc:
        raise HTTPException(status_code=404)
    return proc


# ── Contextual Explanations ──


@router.get("/explanations/{key}")
def get_expl(
    key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expl = get_explanation(db, current_user.company_id, key)
    if not expl:
        # Auto-seed explanations on first request if none exist for this tenant
        from app.models.training import ContextualExplanation
        count = db.query(ContextualExplanation).filter(ContextualExplanation.tenant_id == current_user.company_id).count()
        if count == 0:
            try:
                from app.services.training_content_seed import seed_explanations
                seed_explanations(db, current_user.company_id)
                expl = get_explanation(db, current_user.company_id, key)
                if expl:
                    return {**expl, "exists": True}
            except Exception as e:
                logger.error(f"Failed to seed explanations: {e}")
        return {"exists": False}
    return {**expl, "exists": True}


@router.post("/content/seed-explanations")
def seed_expl(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manually seed all contextual explanations for this tenant."""
    from app.services.training_content_seed import seed_explanations
    count = seed_explanations(db, current_user.company_id)
    return {"seeded": count}


# ── Guided Flows ──


@router.get("/guided-flows/should-offer/{flow_key}")
def check_offer(
    flow_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"should_offer": should_offer_flow(db, current_user.company_id, current_user.id, flow_key)}


@router.post("/guided-flows/{flow_key}/start")
def start_guided(
    flow_key: str,
    body: StartFlowRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return start_flow(db, current_user.company_id, current_user.id, flow_key, body.total_steps)


@router.post("/guided-flows/{flow_key}/complete")
def complete_guided(
    flow_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return complete_flow(db, current_user.company_id, current_user.id, flow_key)


# ── Manager View ──


@router.get("/employees")
def list_employees(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_all_employees_learning(db, current_user.company_id)
