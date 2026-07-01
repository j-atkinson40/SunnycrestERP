"""Execution bridge (Canvas↔Runtime Bridge T-2.0, the SPINE).

The shared path both future fire-mechanisms (T-2.1 schedule, T-2.2 event) block
on: turn an inert `workflow_template` (canvas) into a runnable runtime workflow +
execute it via the existing engine. TWO mechanisms:

  MECHANISM 1 — RE-POINT (mirrors): a mirror template carries
    `mirrored_from_workflow_id` → its runtime source workflow (which the engine
    already runs). Executing a mirror = resolve that id → run the SOURCE. No
    compile. This retires the deliberate backfill debt exactly as the provenance
    column was designed for.

  MECHANISM 2 — COMPILE (drafts): a draft/authored template has no runtime
    source → compile its canvas → runtime steps (LINEAR subset only, see
    `canvas_compiler`).

SAFETY (T-2.0, per the operator split):
  - EXECUTION IS GATED OFF. The engine has no dry-run mode yet (that's T-2.0b);
    executing hits REAL side-effects. `execute_template` therefore requires an
    explicit `allow_live_execution=True` — test-only until T-2.0b threads the
    engine dry-run + a real trigger. No production caller wires this yet.
  - FAILURE IS LOUD. Resolve failures (bad template / dangling mirror / an
    out-of-subset canvas) RAISE. A run that fails mid-execution is recorded
    loudly by the engine on WorkflowRun.status="failed" + error_message (the
    auto-escalation hook is T-2.1; the loud RECORD is inherited now).
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.workflow import WorkflowRun, WorkflowRunStep
from app.models.workflow_template import WorkflowTemplate
from app.services.workflow_engine import start_run
from app.services.workflows.canvas_compiler import compile_canvas_to_workflow

logger = logging.getLogger(__name__)


class ExecutionBridgeError(RuntimeError):
    """A bridge-layer failure resolving/executing a template — raised loudly."""


class RepointError(ExecutionBridgeError):
    """A mirror can't be re-pointed (not a mirror / dangling source)."""


class ExecutionGatedError(ExecutionBridgeError):
    """Live execution attempted without the explicit gate — T-2.0 has no engine
    dry-run yet, so a canvas run hits real side-effects; only tests may opt in."""


def repoint_mirror(db: Session, template: WorkflowTemplate) -> str:
    """A mirror template → its runnable runtime source workflow id. Raises
    RepointError if the template isn't a mirror or its source is gone (dangling)."""
    source_id = template.mirrored_from_workflow_id
    if not source_id:
        raise RepointError(
            f"template {template.id!r} is not a mirror (no mirrored_from_workflow_id) "
            f"— cannot re-point"
        )
    # Import here to avoid a model import cycle at module load.
    from app.models.workflow import Workflow

    source = db.get(Workflow, source_id)
    if source is None:
        raise RepointError(
            f"mirror {template.id!r} points at workflow {source_id!r}, which no "
            f"longer exists (dangling source) — cannot re-point"
        )
    return source_id


def resolve_executable_workflow(
    db: Session, *, template_id: str, company_id: str, actor_user_id: str | None = None
) -> str:
    """A workflow_template → a runnable runtime workflow id. Mirrors RE-POINT to
    their source; drafts COMPILE (linear subset). Raises loudly on a missing
    template, a dangling mirror, or an out-of-subset canvas. Caller commits."""
    template = db.get(WorkflowTemplate, template_id)
    if template is None:
        raise ExecutionBridgeError(f"workflow_template {template_id!r} not found")

    if template.mirrored_from_workflow_id:
        return repoint_mirror(db, template)

    wf = compile_canvas_to_workflow(
        db,
        canvas_state=template.canvas_state or {},
        company_id=company_id,
        name=template.display_name or f"Compiled {template.workflow_type}",
        source_template_id=template.id,
        actor_user_id=actor_user_id,
    )
    return wf.id


def execute_template(
    db: Session,
    *,
    template_id: str,
    company_id: str,
    trigger_source: str = "manual",
    trigger_context: dict[str, Any] | None = None,
    triggered_by_user_id: str | None = None,
    allow_live_execution: bool = False,
) -> WorkflowRun:
    """THE SPINE: resolve a template → a runnable workflow (re-point OR compile)
    → execute it via the engine → a WorkflowRun.

    GATED: `allow_live_execution` must be True. T-2.0 has NO engine dry-run
    (T-2.0b), so this runs with REAL side-effects — only tests opt in until the
    dry-run gate + a real trigger land. Loud failure: resolve errors raise; a
    failed run comes back with status="failed" + error_message (not swallowed).
    Caller commits (start_run commits internally)."""
    if not allow_live_execution:
        raise ExecutionGatedError(
            "canvas execution is gated until T-2.0b (engine dry-run) lands — no "
            "production trigger may fire this yet. Pass allow_live_execution=True "
            "only from tests."
        )
    workflow_id = resolve_executable_workflow(
        db, template_id=template_id, company_id=company_id,
        actor_user_id=triggered_by_user_id,
    )
    run = start_run(
        db,
        workflow_id=workflow_id,
        company_id=company_id,
        triggered_by_user_id=triggered_by_user_id,
        trigger_source=trigger_source,
        trigger_context=trigger_context,
    )
    _surface_run_failures(db, run)
    return run


def _surface_run_failures(db: Session, run: WorkflowRun) -> None:
    """Make a step failure LOUD at the RUN level (the safety surface).

    ENGINE LIMITATION (flagged, T-2.1): `_drive_run` does NOT stop on a step
    failure — `_execute_step` records the failed step (WorkflowRunStep.status=
    'failed' + error_message) but the loop continues and `_complete_run`
    overwrites the run back to 'completed'. So run-level failure is swallowed by
    the engine today. Until the engine's run-level failure handling is fixed
    (T-2.1, alongside the escalation hook), the bridge compensates: if ANY step
    failed, mark the run 'failed' with the step's reason + log loudly. A trigger
    that fires and fails must never read as 'completed'."""
    if run.status == "failed":
        return
    failed = (
        db.query(WorkflowRunStep)
        .filter(WorkflowRunStep.run_id == run.id, WorkflowRunStep.status == "failed")
        .all()
    )
    if not failed:
        return
    reasons = "; ".join(f"{s.step_key}: {s.error_message}" for s in failed[:3])
    run.status = "failed"
    run.error_message = (run.error_message or "") + (
        f" [bridge] {len(failed)} step(s) failed: {reasons}"
    )
    db.commit()
    logger.error(
        "Canvas execution run %s had %d failed step(s) but the engine left it "
        "'%s' — surfaced as failed by the bridge. Reasons: %s",
        run.id, len(failed), "completed", reasons,
    )
