"""Workflow Engine API — list, command-bar, start, advance, runs, settings, enrollment."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.company import Company
from app.models.user import User
from app.models.workflow import (
    Workflow,
    WorkflowEnrollment,
    WorkflowRun,
    WorkflowRunStep,
    WorkflowStep,
)
from app.services import workflow_engine


router = APIRouter()


class StartRunRequest(BaseModel):
    trigger_context: dict | None = None
    initial_inputs: dict | None = None


class AdvanceRunRequest(BaseModel):
    step_input: dict


class EnrollmentPatch(BaseModel):
    is_active: bool


def _serialize_workflow(w: Workflow, step_count: int = 0) -> dict:
    return {
        "id": w.id,
        "name": w.name,
        "description": w.description,
        "keywords": w.keywords or [],
        "tier": w.tier,
        "vertical": w.vertical,
        "trigger_type": w.trigger_type,
        "trigger_config": w.trigger_config,
        "is_active": w.is_active,
        "is_system": w.is_system,
        "icon": w.icon,
        "command_bar_priority": w.command_bar_priority,
        "step_count": step_count,
    }


def _serialize_run(run: WorkflowRun, steps: list[WorkflowRunStep]) -> dict:
    return {
        "id": run.id,
        "workflow_id": run.workflow_id,
        "status": run.status,
        "trigger_source": run.trigger_source,
        "trigger_context": run.trigger_context,
        "input_data": run.input_data,
        "output_data": run.output_data,
        "current_step_id": run.current_step_id,
        "error_message": run.error_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "steps": [
            {
                "step_key": s.step_key,
                "status": s.status,
                "input_data": s.input_data,
                "output_data": s.output_data,
                "error_message": s.error_message,
            }
            for s in steps
        ],
        # When paused, surface the prompt of the current step for the UI
        "awaiting_prompt": _awaiting_prompt(run, steps),
    }


def _awaiting_prompt(run: WorkflowRun, run_steps: list[WorkflowRunStep]) -> dict | None:
    if run.status != "awaiting_input":
        return None
    pending = next((s for s in run_steps if s.status in ("pending", "running")), None)
    if not pending or not pending.output_data:
        return None
    prompt = (pending.output_data or {}).get("prompt")
    if not prompt:
        return None
    return {"step_key": pending.step_key, **prompt}


def _company_vertical(db: Session, company_id: str) -> str | None:
    c = db.query(Company).filter(Company.id == company_id).first()
    return (c.vertical or None) if c else None


# ─────────────────────────────────────────────────────────────────────
# List + command bar
# ─────────────────────────────────────────────────────────────────────

@router.get("")
def list_workflows(
    trigger_type: str | None = Query(None),
    vertical: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vert = vertical or _company_vertical(db, current_user.company_id)
    workflows = workflow_engine.get_active_workflows_for_tenant(
        db, current_user.company_id, vertical=vert, trigger_type=trigger_type
    )
    out = []
    for w in workflows:
        count = db.query(WorkflowStep).filter(WorkflowStep.workflow_id == w.id).count()
        out.append(_serialize_workflow(w, step_count=count))
    return out


@router.get("/command-bar")
def command_bar_workflows(
    q: str = Query("", description="Search query"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vert = _company_vertical(db, current_user.company_id)
    user_role = getattr(current_user, "role_slug", None)
    return workflow_engine.get_command_bar_workflows(
        db, current_user.company_id, vert, user_role, q
    )


# ─────────────────────────────────────────────────────────────────────
# Run lifecycle
# ─────────────────────────────────────────────────────────────────────

@router.post("/{workflow_id}/start")
def start_run(
    workflow_id: str,
    data: StartRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify the workflow is available to this tenant
    vert = _company_vertical(db, current_user.company_id)
    available = workflow_engine.get_active_workflows_for_tenant(
        db, current_user.company_id, vertical=vert
    )
    if not any(w.id == workflow_id for w in available):
        raise HTTPException(status_code=404, detail="Workflow not available")

    run = workflow_engine.start_run(
        db=db,
        workflow_id=workflow_id,
        company_id=current_user.company_id,
        triggered_by_user_id=current_user.id,
        trigger_source="command_bar",
        trigger_context=data.trigger_context,
        initial_inputs=data.initial_inputs,
    )
    run_steps = db.query(WorkflowRunStep).filter(WorkflowRunStep.run_id == run.id).all()
    return _serialize_run(run, run_steps)


@router.post("/runs/{run_id}/advance")
def advance_run(
    run_id: str,
    data: AdvanceRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = db.query(WorkflowRun).filter(
        WorkflowRun.id == run_id,
        WorkflowRun.company_id == current_user.company_id,
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        run = workflow_engine.advance_run(db, run_id, data.step_input)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    run_steps = db.query(WorkflowRunStep).filter(WorkflowRunStep.run_id == run.id).all()
    return _serialize_run(run, run_steps)


@router.get("/runs/{run_id}")
def get_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = db.query(WorkflowRun).filter(
        WorkflowRun.id == run_id,
        WorkflowRun.company_id == current_user.company_id,
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    run_steps = db.query(WorkflowRunStep).filter(WorkflowRunStep.run_id == run.id).all()
    return _serialize_run(run, run_steps)


@router.get("/runs")
def list_runs(
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    runs = workflow_engine.list_runs(db, current_user.company_id, limit=limit, status=status)
    out = []
    for r in runs:
        wf = db.query(Workflow).filter(Workflow.id == r.workflow_id).first()
        out.append({
            "id": r.id,
            "workflow_id": r.workflow_id,
            "workflow_name": wf.name if wf else None,
            "status": r.status,
            "trigger_source": r.trigger_source,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        })
    return out


# ─────────────────────────────────────────────────────────────────────
# Settings + enrollment
# ─────────────────────────────────────────────────────────────────────

@router.get("/settings")
def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all workflows grouped by tier with the tenant's enrollment status."""
    vert = _company_vertical(db, current_user.company_id)

    workflows = db.query(Workflow).filter(
        Workflow.is_active == True,  # noqa: E712
    ).all()
    # Scope by vertical — platform (NULL) + vertical match + tenant-owned
    relevant = [
        w for w in workflows
        if w.company_id == current_user.company_id
        or (w.company_id is None and (w.vertical is None or w.vertical == vert))
    ]

    enrollments = {
        e.workflow_id: e
        for e in db.query(WorkflowEnrollment).filter(WorkflowEnrollment.company_id == current_user.company_id).all()
    }

    def enriched(w: Workflow) -> dict:
        step_count = db.query(WorkflowStep).filter(WorkflowStep.workflow_id == w.id).count()
        base = _serialize_workflow(w, step_count=step_count)
        enrollment = enrollments.get(w.id)
        if w.tier == 3:
            base["enrolled"] = bool(enrollment and enrollment.is_active)
        else:
            # Tier 2 is on unless explicitly opted-out
            base["enrolled"] = not enrollment or enrollment.is_active
        base["can_disable"] = w.tier != 1
        return base

    return {
        "tier_2_default_on": [enriched(w) for w in relevant if w.tier == 2],
        "tier_3_available": [enriched(w) for w in relevant if w.tier == 3],
        "tier_4_custom": [enriched(w) for w in relevant if w.tier == 4 and w.company_id == current_user.company_id],
    }


@router.patch("/{workflow_id}/enrollment")
def set_enrollment(
    workflow_id: str,
    data: EnrollmentPatch,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin-only: enable/disable a workflow for this tenant."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if workflow.tier == 1:
        raise HTTPException(status_code=400, detail="Platform-locked workflows cannot be disabled")

    enrollment = (
        db.query(WorkflowEnrollment)
        .filter(
            WorkflowEnrollment.workflow_id == workflow_id,
            WorkflowEnrollment.company_id == current_user.company_id,
        )
        .first()
    )
    if enrollment:
        enrollment.is_active = data.is_active
    else:
        enrollment = WorkflowEnrollment(
            workflow_id=workflow_id,
            company_id=current_user.company_id,
            is_active=data.is_active,
        )
        db.add(enrollment)
    db.commit()
    return {"workflow_id": workflow_id, "is_active": data.is_active}
