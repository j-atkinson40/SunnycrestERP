"""Workflow Engine API — list, command-bar, start, advance, runs, settings, enrollment."""

import json
import uuid
from typing import Any

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
    WorkflowStepParam,
)
from app.services import workflow_engine, workflow_run_logger


router = APIRouter()


class StartRunRequest(BaseModel):
    """Phase R-6.0a — ``trigger_context`` accepts canonical payload
    shapes that ``workflow_engine.resolve_variables`` knows how to
    walk via prefix-matched references:

      * ``incoming_email``         — {subject, body, from_email, attachments, ...}
      * ``incoming_transcription`` — {text, call_id, participants, ...}
      * ``vault_item``             — {id, item_type, metadata_json, ...}
      * ``record``                 — entity record for ``{current_record.X}``

    Pre-R-6.0 callers using arbitrary trigger_context shapes continue
    to work — the canonical keys above are simply the ones the
    engine's resolver dispatches on by prefix.
    """

    trigger_context: dict | None = None
    initial_inputs: dict | None = None


class AdvanceRunRequest(BaseModel):
    step_input: dict


class EnrollmentPatch(BaseModel):
    is_active: bool


def _serialize_workflow(
    w: Workflow, step_count: int = 0, used_by_count: int | None = None
) -> dict:
    return {
        "id": w.id,
        "name": w.name,
        "description": w.description,
        "keywords": w.keywords or [],
        "tier": w.tier,
        # Workflow Arc Phase 8a — scope + fork + agent metadata
        "scope": w.scope,
        "forked_from_workflow_id": w.forked_from_workflow_id,
        "forked_at": w.forked_at.isoformat() if w.forked_at else None,
        "agent_registry_key": w.agent_registry_key,
        "company_id": w.company_id,
        "vertical": w.vertical,
        "trigger_type": w.trigger_type,
        "trigger_config": w.trigger_config,
        "is_active": w.is_active,
        "is_system": w.is_system,
        "is_coming_soon": getattr(w, "is_coming_soon", False),
        "icon": w.icon,
        "command_bar_priority": w.command_bar_priority,
        "step_count": step_count,
        # used_by_count only populated for core/vertical rows when
        # the caller asks for it (see /workflows?scope=core query).
        "used_by_count": used_by_count,
    }


def _tenant_verticals(db: Session, company_id: str) -> list[str]:
    """Active verticals for the tenant. Currently derived from company.vertical.
    Future: also check active extensions that unlock additional verticals."""
    c = db.query(Company).filter(Company.id == company_id).first()
    if not c or not c.vertical:
        return []
    return [c.vertical]


def _load_step_params(db: Session, workflow_id: str, company_id: str) -> list[dict]:
    """Return merged platform defaults + tenant overrides for a workflow's params."""
    defaults = (
        db.query(WorkflowStepParam)
        .filter(
            WorkflowStepParam.workflow_id == workflow_id,
            WorkflowStepParam.company_id.is_(None),
        )
        .all()
    )
    overrides = {
        (p.step_key, p.param_key): p
        for p in db.query(WorkflowStepParam)
        .filter(
            WorkflowStepParam.workflow_id == workflow_id,
            WorkflowStepParam.company_id == company_id,
        )
        .all()
    }
    out = []
    for p in defaults:
        override = overrides.get((p.step_key, p.param_key))
        out.append({
            "step_key": p.step_key,
            "param_key": p.param_key,
            "label": p.label,
            "description": p.description,
            "param_type": p.param_type,
            "default_value": p.default_value,
            "current_value": override.current_value if override else None,
            "effective_value": (
                override.current_value if override and override.current_value is not None
                else p.default_value
            ),
            "is_configurable": p.is_configurable,
            "validation": p.validation,
        })
    return out


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

@router.get("/step-types")
def list_step_types(
    current_user: User = Depends(get_current_user),
):
    """Phase 3d — discovery endpoint for the workflow designer.

    Returns the catalog of step types the engine supports + a short
    description for each. Keep in sync with the cascade in
    workflow_engine._execute_step.
    """
    return {
        "step_types": [
            {
                "key": "input",
                "label": "Input",
                "description": "Ask the user for a value and pause the run.",
            },
            {
                "key": "action",
                "label": "Action",
                "description": "Perform a side-effecting operation (create record, send email, etc).",
            },
            {
                "key": "condition",
                "label": "Condition",
                "description": "Branch based on an expression.",
            },
            {
                "key": "output",
                "label": "Output",
                "description": "Show a final result to the user.",
            },
            {
                "key": "ai_prompt",
                "label": "AI Prompt",
                "description": "Invoke a managed Intelligence prompt and expose its response to downstream steps.",
            },
            {
                "key": "playwright_action",
                "label": "Playwright Automation",
                "description": "Execute a registered Playwright script with optional human approval.",
            },
        ],
    }


@router.get("")
def list_workflows(
    trigger_type: str | None = Query(None),
    vertical: str | None = Query(None),
    scope: str | None = Query(
        None,
        description="Filter by workflow scope. Valid values: core, vertical, tenant.",
        pattern="^(core|vertical|tenant)$",
    ),
    include_used_by: bool = Query(
        False,
        description=(
            "Populate used_by_count on core/vertical rows. Costs an extra "
            "aggregate query per workflow — only request when rendering "
            "the three-tab builder."
        ),
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List workflows visible to the caller.

    Default behavior unchanged — no scope filter returns the full
    tenant-visible list via workflow_engine. Scope filter narrows:

      - scope=core: all workflows with scope='core' (platform-global,
        visible to every tenant)
      - scope=vertical: workflows with scope='vertical' matching the
        tenant's vertical (and any vertical explicitly passed)
      - scope=tenant: workflows owned by the caller's tenant
        (company_id == caller's company) — includes forks + custom

    `include_used_by` returns per-row tenant-enrollment counts on
    core/vertical rows for the "Used by N tenants" column. Not
    computed for tenant-scope because each tenant sees only their
    own, so the count is always 1.
    """
    vert = vertical or _company_vertical(db, current_user.company_id)

    if scope is not None:
        # Three-tab filtering path.
        q = db.query(Workflow)
        if scope == "core":
            q = q.filter(Workflow.scope == "core")
        elif scope == "vertical":
            q = q.filter(Workflow.scope == "vertical")
            # Restrict to vertical matching caller's tenant.
            if vert:
                q = q.filter(Workflow.vertical == vert)
        elif scope == "tenant":
            q = q.filter(
                Workflow.scope == "tenant",
                Workflow.company_id == current_user.company_id,
            )
        q = q.filter(Workflow.is_active.is_(True))
        q = q.order_by(Workflow.tier.asc(), Workflow.name.asc())
        workflows = q.all()
    else:
        # Legacy path — unfiltered tenant-visible list via engine.
        workflows = workflow_engine.get_active_workflows_for_tenant(
            db,
            current_user.company_id,
            vertical=vert,
            trigger_type=trigger_type,
        )

    out = []
    for w in workflows:
        count = (
            db.query(WorkflowStep)
            .filter(WorkflowStep.workflow_id == w.id)
            .count()
        )
        used_by: int | None = None
        if include_used_by and w.scope in ("core", "vertical"):
            from app.services.workflow_fork import count_tenants_using_workflow

            used_by = count_tenants_using_workflow(db, workflow_id=w.id)
        out.append(
            _serialize_workflow(w, step_count=count, used_by_count=used_by)
        )
    return out


# ── Workflow Arc Phase 8a — fork mechanism (Option A) ───────────────


class _ForkRequest(BaseModel):
    new_name: str | None = None


@router.post("/{workflow_id}/fork")
def fork_workflow(
    workflow_id: str,
    body: _ForkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fork a core or vertical workflow into a tenant-owned copy.

    Option A — independent copies. Platform updates to the source
    workflow do NOT propagate to the fork. The fork is the tenant's
    to edit, rename, activate/deactivate, and ultimately delete.

    For soft customization (parameter overrides while staying enrolled
    in the platform workflow), use PATCH /workflows/{id}/enrollment
    instead. The two paths are documented in CLAUDE.md § Workflows
    under the dual-path rationale.

    409 if the tenant already has an active fork of this source.
    """
    from app.services.workflow_fork import (
        WorkflowForkError,
        fork_workflow_to_tenant,
    )

    try:
        fork = fork_workflow_to_tenant(
            db,
            user=current_user,
            source_workflow_id=workflow_id,
            new_name=body.new_name,
        )
    except WorkflowForkError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc

    step_count = (
        db.query(WorkflowStep).filter(WorkflowStep.workflow_id == fork.id).count()
    )
    return _serialize_workflow(fork, step_count=step_count)


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


# ─────────────────────────────────────────────────────────────────────
# AI-assisted generation + custom workflow CRUD (Phase W-2)
# ─────────────────────────────────────────────────────────────────────

class GenerateWorkflowRequest(BaseModel):
    description: str


class SaveWorkflowRequest(BaseModel):
    id: str | None = None
    name: str
    description: str | None = None
    keywords: list[str] | None = None
    vertical: str | None = None
    trigger_type: str = "manual"
    trigger_config: dict | None = None
    icon: str | None = None
    command_bar_priority: int = 50
    is_active: bool = False  # draft by default
    steps: list[dict]


_WORKFLOW_SYSTEM_PROMPT = """You are a workflow designer for an ERP platform. Convert a natural-language description of a business process into a structured workflow JSON object.

Output schema:
{
  "name": "Short imperative name (e.g. 'Schedule Delivery')",
  "description": "One-sentence description.",
  "keywords": ["phrase", "another phrase"],
  "trigger_type": "manual" | "scheduled" | "event",
  "trigger_config": {} | null,
  "icon": "lucide-icon-name",
  "steps": [
    {
      "step_order": 1,
      "step_key": "snake_case_key",
      "step_type": "input" | "action" | "condition" | "output",
      "config": { ... }
    }
  ]
}

Input step config: { "prompt": "...", "input_type": "text|number|select|date_picker|datetime_picker|crm_search|record_search|user_search", "required": bool, "options": [...] (for select), "record_type": "..." (for record_search) }
Action step config: { "action_type": "create_record|send_email|send_notification|log_vault_item|generate_document|open_slide_over|show_confirmation", plus action-specific fields }
Condition step config: { "expression": "...", "true_next": "step_key", "false_next": "step_key" }
Output step config: { "action_type": "open_slide_over|show_confirmation", "message": "..." }

Use {input.step_key.field} and {output.step_key.field} to reference prior step outputs.

Respond with the JSON object only."""


@router.post("/generate")
def generate_workflow(
    data: GenerateWorkflowRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """AI-assisted workflow draft generation from a natural-language description."""
    if not data.description or len(data.description.strip()) < 10:
        raise HTTPException(status_code=400, detail="Description too short (min 10 chars)")

    vert = _company_vertical(db, current_user.company_id)
    try:
        # Phase 2c-4 migration — workflow.generate_from_description
        from app.services.intelligence import intelligence_service

        intel = intelligence_service.execute(
            db,
            prompt_key="workflow.generate_from_description",
            variables={"description": data.description, "company_vertical": vert or ""},
            company_id=current_user.company_id,
            caller_module="workflows.generate_workflow",
            caller_entity_type="workflow_draft",
        )
        if intel.status == "success" and isinstance(intel.response_parsed, dict):
            result = intel.response_parsed
        else:
            raise HTTPException(
                status_code=502,
                detail=f"AI generation failed: {intel.error_message or intel.status}",
            )
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover — defensive
        raise HTTPException(status_code=502, detail=f"AI generation failed: {e}")

    # Normalize
    result.setdefault("trigger_type", "manual")
    result.setdefault("steps", [])
    result["vertical"] = vert
    result["is_active"] = False  # draft
    return result


@router.get("/{workflow_id}")
def get_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single workflow with its steps. Read-only if Tier 1 or not owned."""
    w = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Workflow not found")
    # Visibility: platform workflows (company_id NULL) or owned
    if w.company_id and w.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    steps = (
        db.query(WorkflowStep)
        .filter(WorkflowStep.workflow_id == w.id)
        .order_by(WorkflowStep.step_order)
        .all()
    )
    base = _serialize_workflow(w, step_count=len(steps))
    base["steps"] = [
        {
            "id": s.id,
            "step_order": s.step_order,
            "step_key": s.step_key,
            "step_type": s.step_type,
            "config": s.config,
            "is_core": getattr(s, "is_core", False),
            "display_name": s.display_name,
            "next_step_id": s.next_step_id,
            "condition_true_step_id": s.condition_true_step_id,
            "condition_false_step_id": s.condition_false_step_id,
        }
        for s in steps
    ]
    base["params"] = _load_step_params(db, w.id, current_user.company_id)
    # Enrollment-level added_steps (tenant-owned extensions of Tier 1 flows)
    enrollment = (
        db.query(WorkflowEnrollment)
        .filter(
            WorkflowEnrollment.workflow_id == w.id,
            WorkflowEnrollment.company_id == current_user.company_id,
        )
        .first()
    )
    base["added_steps"] = (enrollment.added_steps if enrollment else None) or []
    base["editable"] = (
        w.tier != 1
        and w.company_id == current_user.company_id
        and not w.is_system
    )
    base["configurable"] = w.tier == 1 and len(base["params"]) > 0
    # Recent runs (visibility for Tier 1 and custom)
    runs = workflow_run_logger.list_recent_runs(
        db, workflow_id=w.id, company_id=current_user.company_id, limit=10
    )
    base["recent_runs"] = [
        {
            "id": r.id,
            "status": r.status,
            "trigger_source": r.trigger_source,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "error_message": r.error_message,
        }
        for r in runs
    ]
    return base


def _apply_steps(db: Session, workflow_id: str, steps: list[dict]) -> None:
    """Replace all steps on a workflow."""
    db.query(WorkflowStep).filter(WorkflowStep.workflow_id == workflow_id).delete()
    for s in steps:
        db.add(
            WorkflowStep(
                id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                step_order=s.get("step_order", 0),
                step_key=s.get("step_key", ""),
                step_type=s.get("step_type", "action"),
                config=s.get("config", {}),
                is_core=s.get("is_core", False),
                display_name=s.get("display_name") or None,
            )
        )


def _validate_ai_prompt_steps_or_400(
    db: Session, company_id: str | None, steps: list[dict]
) -> None:
    """Phase 3d — fail-fast on misconfigured ai_prompt steps.

    Raises HTTPException(400) with a `detail.errors` list so the frontend
    can point at specific step keys. Other step types are unchanged.
    """
    from app.services.workflow_engine import validate_ai_prompt_steps

    errs = validate_ai_prompt_steps(db, company_id, steps)
    if errs:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Workflow contains invalid ai_prompt steps",
                "errors": errs,
            },
        )


@router.post("")
def create_workflow(
    data: SaveWorkflowRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new custom (Tier 4) workflow."""
    _validate_ai_prompt_steps_or_400(db, current_user.company_id, data.steps)
    vert = data.vertical or _company_vertical(db, current_user.company_id)
    wf = Workflow(
        id=data.id or str(uuid.uuid4()),
        company_id=current_user.company_id,
        name=data.name,
        description=data.description,
        keywords=data.keywords or [],
        tier=4,
        vertical=vert,
        trigger_type=data.trigger_type,
        trigger_config=data.trigger_config,
        is_active=data.is_active,
        is_system=False,
        icon=data.icon,
        command_bar_priority=data.command_bar_priority,
        created_by_user_id=current_user.id,
    )
    db.add(wf)
    db.flush()
    _apply_steps(db, wf.id, data.steps)
    db.commit()
    db.refresh(wf)
    return _serialize_workflow(wf, step_count=len(data.steps))


@router.patch("/{workflow_id}")
def update_workflow(
    workflow_id: str,
    data: SaveWorkflowRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a custom workflow. Tier 1 + system + non-owned are forbidden."""
    wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if wf.tier == 1 or wf.is_system:
        raise HTTPException(status_code=400, detail="Platform-locked workflows cannot be edited")
    if wf.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    _validate_ai_prompt_steps_or_400(db, current_user.company_id, data.steps)

    wf.name = data.name
    wf.description = data.description
    wf.keywords = data.keywords or []
    wf.vertical = data.vertical or wf.vertical
    wf.trigger_type = data.trigger_type
    wf.trigger_config = data.trigger_config
    wf.icon = data.icon
    wf.command_bar_priority = data.command_bar_priority
    wf.is_active = data.is_active
    _apply_steps(db, wf.id, data.steps)
    db.commit()
    db.refresh(wf)
    return _serialize_workflow(wf, step_count=len(data.steps))


@router.delete("/{workflow_id}")
def delete_workflow(
    workflow_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if wf.tier == 1 or wf.is_system or wf.company_id != current_user.company_id:
        raise HTTPException(status_code=400, detail="Workflow cannot be deleted")
    db.query(WorkflowStep).filter(WorkflowStep.workflow_id == wf.id).delete()
    db.delete(wf)
    db.commit()
    return {"deleted": True}


# ─────────────────────────────────────────────────────────────────────
# Individual step PATCH / DELETE
# ─────────────────────────────────────────────────────────────────────

class StepPatchRequest(BaseModel):
    display_name: str | None = None
    config: dict | None = None


@router.patch("/{workflow_id}/steps/{step_id}")
def patch_step(
    workflow_id: str,
    step_id: str,
    data: StepPatchRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Partially update a step's display_name and/or config.
    Works for both custom and platform workflows — only updates the fields
    explicitly provided. Core steps can be edited (core means can't delete, not frozen)."""
    wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if wf.company_id and wf.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    step = db.query(WorkflowStep).filter(
        WorkflowStep.id == step_id,
        WorkflowStep.workflow_id == workflow_id,
    ).first()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    if data.display_name is not None:
        step.display_name = data.display_name if data.display_name.strip() else None
    if data.config is not None:
        step.config = data.config
    db.commit()
    return {
        "id": step.id,
        "display_name": step.display_name,
        "config": step.config,
    }


@router.delete("/{workflow_id}/steps/{step_id}")
def delete_step(
    workflow_id: str,
    step_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Remove a step from a custom workflow. Core steps cannot be removed."""
    wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if wf.tier == 1 or wf.is_system:
        raise HTTPException(status_code=400, detail="Platform-locked workflow steps cannot be removed")
    if wf.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    step = db.query(WorkflowStep).filter(
        WorkflowStep.id == step_id,
        WorkflowStep.workflow_id == workflow_id,
    ).first()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    if step.is_core:
        raise HTTPException(status_code=400, detail="Core steps cannot be removed from the workflow")

    db.delete(step)
    db.commit()
    return None  # 204


# ─────────────────────────────────────────────────────────────────────
# Library view — 3 tabs: mine / platform / templates
# ─────────────────────────────────────────────────────────────────────

@router.get("/library/all")
def library_all(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all workflows visible to the tenant, split into 3 tabs.

    Vertical filtering: platform workflows (company_id NULL) are included if
    their vertical is NULL (cross-vertical) or matches one of the tenant's
    active verticals.
    """
    tenant_verts = _tenant_verticals(db, current_user.company_id)
    all_wfs = db.query(Workflow).all()

    # Precompute params count per workflow for "configurable" badge
    param_counts = {}
    for row in db.query(WorkflowStepParam.workflow_id).filter(
        WorkflowStepParam.company_id.is_(None)
    ).all():
        param_counts[row[0]] = param_counts.get(row[0], 0) + 1

    def visible(w: Workflow) -> bool:
        if w.company_id == current_user.company_id:
            return True
        if w.company_id is None:
            if w.vertical is None:
                return True
            if tenant_verts and w.vertical in tenant_verts:
                return True
        return False

    wfs = [w for w in all_wfs if visible(w)]

    def enrich(w: Workflow) -> dict:
        step_count = db.query(WorkflowStep).filter(WorkflowStep.workflow_id == w.id).count()
        base = _serialize_workflow(w, step_count=step_count)
        base["editable"] = (
            w.tier != 1
            and w.company_id == current_user.company_id
            and not w.is_system
        )
        base["configurable"] = w.tier == 1 and param_counts.get(w.id, 0) > 0
        return base

    mine = [enrich(w) for w in wfs if w.company_id == current_user.company_id]
    platform = [enrich(w) for w in wfs if w.tier == 1]
    templates = [enrich(w) for w in wfs if w.tier in (2, 3) and w.company_id is None]

    return {
        "mine": mine,
        "platform": platform,
        "templates": templates,
        "tenant_verticals": tenant_verts,
    }


class ParamOverrideRequest(BaseModel):
    current_value: Any


@router.put("/{workflow_id}/params/{step_key}/{param_key}")
def set_param_override(
    workflow_id: str,
    step_key: str,
    param_key: str,
    data: ParamOverrideRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Save a tenant-specific override for a workflow step param."""
    # Verify the platform default exists (only configurable ones can be overridden)
    default = (
        db.query(WorkflowStepParam)
        .filter(
            WorkflowStepParam.workflow_id == workflow_id,
            WorkflowStepParam.step_key == step_key,
            WorkflowStepParam.param_key == param_key,
            WorkflowStepParam.company_id.is_(None),
        )
        .first()
    )
    if not default:
        raise HTTPException(status_code=404, detail="Param not found")
    if not default.is_configurable:
        raise HTTPException(status_code=400, detail="Param is not configurable")

    override = (
        db.query(WorkflowStepParam)
        .filter(
            WorkflowStepParam.workflow_id == workflow_id,
            WorkflowStepParam.step_key == step_key,
            WorkflowStepParam.param_key == param_key,
            WorkflowStepParam.company_id == current_user.company_id,
        )
        .first()
    )
    if override:
        override.current_value = data.current_value
    else:
        db.add(
            WorkflowStepParam(
                id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                company_id=current_user.company_id,
                step_key=step_key,
                param_key=param_key,
                label=default.label,
                description=default.description,
                param_type=default.param_type,
                default_value=default.default_value,
                current_value=data.current_value,
                is_configurable=default.is_configurable,
                validation=default.validation,
            )
        )
    db.commit()
    return {"saved": True}


class AddedStepsRequest(BaseModel):
    added_steps: list[dict]


@router.put("/{workflow_id}/added-steps")
def set_added_steps(
    workflow_id: str,
    data: AddedStepsRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Save tenant-owned additional steps on a Tier 1 workflow enrollment."""
    wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    enrollment = (
        db.query(WorkflowEnrollment)
        .filter(
            WorkflowEnrollment.workflow_id == workflow_id,
            WorkflowEnrollment.company_id == current_user.company_id,
        )
        .first()
    )
    if enrollment:
        enrollment.added_steps = data.added_steps
    else:
        db.add(
            WorkflowEnrollment(
                id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                company_id=current_user.company_id,
                is_active=True,
                added_steps=data.added_steps,
            )
        )
    db.commit()
    return {"saved": True}


class ComingSoonNotifyRequest(BaseModel):
    workflow_id: str


@router.post("/notify-when-available")
def notify_when_available(
    data: ComingSoonNotifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Subscribe the tenant to a 'coming soon' workflow launch notification.

    Stored as an inactive enrollment row — when the workflow flips off
    is_coming_soon, a launch job can iterate these enrollments and email.
    """
    wf = db.query(Workflow).filter(Workflow.id == data.workflow_id).first()
    if not wf or not wf.is_coming_soon:
        raise HTTPException(status_code=400, detail="Workflow not awaiting launch")
    existing = (
        db.query(WorkflowEnrollment)
        .filter(
            WorkflowEnrollment.workflow_id == data.workflow_id,
            WorkflowEnrollment.company_id == current_user.company_id,
        )
        .first()
    )
    if not existing:
        db.add(
            WorkflowEnrollment(
                id=str(uuid.uuid4()),
                workflow_id=data.workflow_id,
                company_id=current_user.company_id,
                is_active=False,  # will flip on at launch
            )
        )
        db.commit()
    return {"subscribed": True}
