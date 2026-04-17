"""WorkflowRunLogger — lightweight wrapper for registering Tier 1 platform
processes in the workflow run history without rewriting their code.

Existing services call start/log_step/complete/fail from their normal
execution path. The engine doesn't execute anything — it's pure tracking.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.workflow import WorkflowRun, WorkflowRunStep


def start(
    db: Session,
    *,
    workflow_id: str,
    company_id: str,
    trigger_source: str,
    trigger_context: dict | None = None,
) -> str:
    """Create a workflow_run and return its id."""
    run = WorkflowRun(
        workflow_id=workflow_id,
        company_id=company_id,
        trigger_source=trigger_source,
        trigger_context=trigger_context,
        status="running",
        input_data={},
        output_data={},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run.id


def log_step(
    db: Session,
    *,
    run_id: str,
    step_key: str,
    status: str = "completed",
    output_data: dict | None = None,
    step_id: str | None = None,
) -> None:
    """Record a step execution. step_id can be omitted — we look it up by
    step_key on the associated workflow if needed."""
    # If step_id not given, try to look it up
    if not step_id:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
        if run:
            from app.models.workflow import WorkflowStep
            step = (
                db.query(WorkflowStep)
                .filter(WorkflowStep.workflow_id == run.workflow_id, WorkflowStep.step_key == step_key)
                .first()
            )
            if step:
                step_id = step.id
    if not step_id:
        # No matching step — still record the run step without FK for audit purposes
        step_id = str(uuid.uuid4())

    rs = WorkflowRunStep(
        run_id=run_id,
        step_id=step_id,
        step_key=step_key,
        status=status,
        output_data=output_data,
    )
    try:
        db.add(rs)
        db.commit()
    except Exception:
        db.rollback()


def complete(db: Session, *, run_id: str, output_data: dict | None = None) -> None:
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if not run:
        return
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    if output_data:
        run.output_data = {**(run.output_data or {}), **output_data}
    db.commit()


def fail(db: Session, *, run_id: str, error_message: str) -> None:
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if not run:
        return
    run.status = "failed"
    run.error_message = error_message[:500]
    run.completed_at = datetime.now(timezone.utc)
    db.commit()


def list_recent_runs(
    db: Session,
    *,
    workflow_id: str,
    company_id: str | None = None,
    limit: int = 10,
) -> list[WorkflowRun]:
    q = db.query(WorkflowRun).filter(WorkflowRun.workflow_id == workflow_id)
    if company_id:
        q = q.filter(WorkflowRun.company_id == company_id)
    return q.order_by(WorkflowRun.started_at.desc()).limit(limit).all()
