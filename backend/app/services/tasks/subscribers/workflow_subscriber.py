"""Workflow integration subscriber.

v1 task substrate B3: when a task with `provenance_kind='workflow_step'`
transitions to a terminal state (`done` or `cancelled`), resume the
parent workflow run that was paused on a `wait_for_task_completion`
step.

Provenance contract for workflow-step-created tasks:
  • `provenance_kind == 'workflow_step'`
  • `provenance_ref_type == 'workflow_run'`
  • `provenance_ref_id == <WorkflowRun.id>`
  • event_kind carries the originating step_key (informational only).

Resume semantics:
  • Look up the WorkflowRun by id.
  • If the run is `awaiting_approval` AND the current step is a
    `wait_for_task_completion` node, pass the task outcome into
    `workflow_engine.advance_run` so `_drive_run` advances to the next
    step. The advance_run call honors invoke_review_focus-style
    completion semantics (don't re-enter; mark step done; move next).
  • If the run isn't paused (already running / completed), skip.

Event types: task_completed, task_cancelled.

State doc §5.7; build prompt §7.4 / B3.B.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.task_details import TaskDetails
from app.services.tasks.subscribers.registry import register_subscriber


logger = logging.getLogger(__name__)


def _handle(db: Session, payload: dict[str, Any]) -> None:
    """Resume parent workflow when a workflow-step task terminates."""
    td_id = payload.get("task_details_id")
    if td_id is None:
        return

    td = (
        db.query(TaskDetails)
        .filter(TaskDetails.id == td_id)
        .first()
    )
    if td is None:
        return

    # Only workflow-step-provenance tasks resume a workflow.
    if td.provenance_kind != "workflow_step":
        return
    if td.provenance_ref_type != "workflow_run":
        return
    run_id = td.provenance_ref_id
    if not run_id:
        return

    # Load the run; skip if not paused on a wait_for_task_completion
    # step. We don't unilaterally advance every workflow with a
    # workflow_step task — only those that were paused waiting for it.
    try:
        from app.models.workflow import WorkflowRun, WorkflowStep
    except ImportError:
        return

    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if run is None:
        logger.debug(
            "workflow_resumer: run %s not found (td=%s) — skipping",
            run_id, td_id,
        )
        return
    if run.status != "awaiting_approval":
        logger.debug(
            "workflow_resumer: run %s status=%s (not paused) — skipping",
            run_id, run.status,
        )
        return

    # Verify the current step is a wait_for_task_completion node before
    # calling advance_run — this prevents accidentally resuming runs
    # paused for a different reason (Playwright approval gate,
    # invoke_review_focus, etc.).
    if run.current_step_id:
        current_step = (
            db.query(WorkflowStep)
            .filter(WorkflowStep.id == run.current_step_id)
            .first()
        )
        cfg = (current_step.config or {}) if current_step else {}
        action_type = cfg.get("action_type") if isinstance(cfg, dict) else None
        if action_type != "wait_for_task_completion":
            logger.debug(
                "workflow_resumer: run %s current step action_type=%s — "
                "not wait_for_task_completion; skipping",
                run_id, action_type,
            )
            return

    # Resume via the canonical advance_run path. Pass the task outcome
    # so the run's `input_data` carries the completion signal.
    try:
        from app.services.workflow_engine import advance_run

        advance_run(
            db,
            run_id,
            {
                "task_completed": {
                    "task_details_id": td.id,
                    "current_state": td.current_state,
                    "resolution_outcome": td.resolution_outcome,
                }
            },
        )
        logger.debug(
            "workflow_resumer: resumed run %s after task %s → %s",
            run_id, td_id, td.current_state,
        )
    except Exception:
        logger.exception(
            "workflow_resumer: advance_run failed (run=%s td=%s)",
            run_id, td_id,
        )


register_subscriber(
    "workflow_resumer",
    _handle,
    event_types=("task_completed", "task_cancelled"),
)
