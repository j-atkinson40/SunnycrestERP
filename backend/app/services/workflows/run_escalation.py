"""H1 — the escalation hook: failed runs → Decision Triage + the outbox.

Per ponder_investigation.md H1 (the flagship ponder beat made TRUE): the back
half already existed — WorkflowReviewItem (r92) is consumed by the
workflow_review_triage queue (the queue the Decision Triage Focus binds to),
and the morning briefing's _collect_queue_summaries already carries per-queue
pending counts. This module is the missing FRONT half: at the failure-record
chokepoint, route the failure into that machinery.

CALLED INSIDE the failure-recording transaction, BEFORE its commit — from
`workflow_engine._fail_run` (the single live chokepoint; every
run.status="failed" writer routes through it) and `workflow_run_logger.fail`
(a dormant zero-caller path, instrumented for safety).

THE ATOMICITY TRADE, resolved eyes-open: recording the failure is the PRIMARY
duty; routing is secondary. Routing runs inside a SAVEPOINT
(db.begin_nested()) — a routing bug (bad FK, constraint, anything) rolls back
to the savepoint, the failure record itself survives and commits, and the
routing failure logs at ERROR with full context. This is a deliberate,
narrow, LOUD exception to the never-swallow discipline (and to emit_event's
own no-swallow docstring): the alternative — a routing bug silently erasing
the failure record — is strictly worse. The pin test proves both properties.

THE NOISE SEMANTICS (the fan-out-cap lesson applied to triage): a broken
schedule-triggered workflow fails EVERY tick. ONE OPEN item per
(company, workflow, trigger_source): a repeat failure while an open item
exists UPDATES it (occurrence_count += 1, last_seen, latest error, run_id
re-pointed to the newest failed run so the deep-link stays fresh) — never a
duplicate. A decided (resolved/dismissed) item allows a fresh one: a new
breakage after a fix is new news.

The run.failed OUTBOX EVENT rides in the same savepoint (T-2.2a
same-transaction pattern). The free capability: run.failed is a MATCHABLE
domain event — operators can author event-triggers on it ("when a run fails,
do X") with zero further work.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.workflow import Workflow, WorkflowRun
from app.models.workflow_review_item import WorkflowReviewItem
from app.services.maps_of_content.domain_events import emit_event

logger = logging.getLogger(__name__)

# The kind discriminator. review_focus_id is a String(64) key (not an FK), so
# escalation items declare themselves with this sentinel; input_data.kind
# carries the same value for display-layer convenience. No migration needed.
RUN_FAILURE_FOCUS_ID = "run_failure"


def route_failed_run(db: Session, run: WorkflowRun, message: str) -> None:
    """Route a just-failed run into Decision Triage + the outbox.

    Same-transaction (caller commits), savepoint-isolated (see module
    docstring). Never raises — a routing failure is logged at ERROR and the
    caller's failure record proceeds untouched.
    """
    if not run.company_id:
        # Platform-scoped/companyless runs have no triage tenant to land in;
        # the loud record (status+error) still stands.
        return
    try:
        with db.begin_nested():
            _route(db, run, message)
    except Exception:
        logger.error(
            "run_escalation: routing FAILED for run=%s workflow=%s company=%s "
            "— the failure record itself is preserved; the escalation item/"
            "event were rolled back. Fix the routing path.",
            run.id, run.workflow_id, run.company_id,
            exc_info=True,
        )


def _route(db: Session, run: WorkflowRun, message: str) -> None:
    now = datetime.now(timezone.utc)
    workflow = db.query(Workflow).filter(Workflow.id == run.workflow_id).first()
    workflow_name = workflow.name if workflow else (run.workflow_id or "unknown")
    task_name = None
    if isinstance(run.trigger_context, dict):
        task_name = run.trigger_context.get("task_name")
    error_text = (message or "")[:500]
    trigger_source = run.trigger_source or "unknown"

    # Dedup: one OPEN failure item per (company, workflow, trigger_source).
    open_item = (
        db.query(WorkflowReviewItem)
        .filter(
            WorkflowReviewItem.company_id == run.company_id,
            WorkflowReviewItem.review_focus_id == RUN_FAILURE_FOCUS_ID,
            WorkflowReviewItem.decision.is_(None),
            WorkflowReviewItem.input_data["workflow_id"].astext == (run.workflow_id or ""),
            WorkflowReviewItem.input_data["trigger_source"].astext == trigger_source,
        )
        .first()
    )

    if open_item is not None:
        data = dict(open_item.input_data or {})
        data["occurrence_count"] = int(data.get("occurrence_count") or 1) + 1
        data["last_seen"] = now.isoformat()
        data["error"] = error_text
        open_item.input_data = data  # reassign — JSONB change detection
        open_item.run_id = run.id  # deep-link points at the NEWEST failure
        db.flush()
    else:
        db.add(WorkflowReviewItem(
            run_id=run.id,
            company_id=run.company_id,
            review_focus_id=RUN_FAILURE_FOCUS_ID,
            input_data={
                "kind": RUN_FAILURE_FOCUS_ID,
                "workflow_id": run.workflow_id,
                "workflow_name": workflow_name,
                "task_name": task_name,
                "trigger_source": trigger_source,
                "error": error_text,
                "occurrence_count": 1,
                "first_seen": now.isoformat(),
                "last_seen": now.isoformat(),
            },
        ))
        db.flush()

    emit_event(
        db,
        company_id=run.company_id,
        event_key="run.failed",
        entity_type="workflow_run",
        entity_id=run.id,
        payload={
            "workflow_id": run.workflow_id,
            "workflow_name": workflow_name,
            "trigger_source": trigger_source,
            "error": error_text[:200],
        },
    )
