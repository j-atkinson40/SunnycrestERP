"""MoC event-matcher sweep (Canvas↔Runtime Bridge T-2.2b) — the outbox consumer.

Reads UNPROCESSED `moc_domain_event` rows (the r119 partial-index work queue),
matches each against kind="event" `moc_task_trigger` rows (event_key + the
structured conditions evaluated against the event's emit-time payload), and
fires matches DRY-RUN through the T-2.0b engine. Mirrors the T-2.1a schedule
sweep exactly, one layer over the emission substrate.

THE SAFETY INVARIANT (the T-2.1a choreography, replayed): `go_live` is the
constant `_MATCH_GO_LIVE = False` — EVERY event-fire is dry-run this phase,
regardless of any trigger's is_live (which the schedule path honors but the
event path deliberately does not yet). T-2.2c converts this constant to
`_resolve_go_live` (the T-2.1b move). Dry-run makes the §6 mirror hazard moot.

CONDITION MATCHING (fail-closed — the blast-radius guard):
- conditions is the structured list of {field, operator, value}; ALL elements
  must match (AND — list-of-one today, rich-ready).
- A field ABSENT from the payload → no match (clean fail, not an error).
- A malformed condition (not a list, non-dict element, unknown operator) →
  matches NOTHING (a broken condition fires nothing, never everything).
- An EMPTY conditions list → matches on event_key alone (an unconditional
  trigger on the event — valid per the T-1a validator).

IDEMPOTENCY (the event-scale re-key of T-2.1a's): dedup on the
(moc_task_trigger_id, event_id) PAIR via WorkflowRun.trigger_context. One event
matching N triggers → N distinct fires; one trigger matching N events → N
fires; the SAME pair never fires twice, across sweep ticks and re-runs.

PROCESSED MARKING: an event is marked processed after its match pass, EVEN IF a
fire errored — poison-event protection (a bad event must not block the queue
forever). A failed fire is loud (failed WorkflowRun / logged error), and the
pair-dedup means a re-run would not double-fire the successes anyway.

TENANT SCOPING: the event's company must be IN the trigger's task fan-out set
(the inverse of the schedule sweep's `_fanout_companies` membership):
platform_default → any; vertical_default → company.vertical matches;
tenant_override → task.tenant_id == event.company_id.

Per-sweep cap (default 500): a runaway emitter backlogs VISIBLY (logged) rather
than firing unboundedly in one tick.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.company import Company
from app.models.moc_domain_event import MoCDomainEvent
from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.moc_task_trigger import MoCTaskTrigger
from app.models.workflow import WorkflowRun
from app.services.workflows.canvas_compiler import CanvasCompileError
from app.services.workflows.execution_bridge import ExecutionBridgeError, execute_template

logger = logging.getLogger(__name__)

# THE ONE SOURCE of go_live for event fires this phase (T-2.1a's pattern):
# every fire is DRY-RUN. T-2.2c replaces this constant with _resolve_go_live
# (is_live AND compiled — the §6 guard), exactly as T-2.1b did for schedules.
_MATCH_GO_LIVE = False

_TRIGGER_SOURCE = "moc_task_event"

# Mirrors triggers.OPERATORS — the authoring validator's vocabulary.
_OPERATORS = ("==", "!=", "in", ">", "<", ">=", "<=", "contains")


# ── Condition evaluation (pure, fail-closed) ───────────────────────────


def _numeric(value: Any) -> float | None:
    """Coerce to float for ordering comparisons; None = not coercible
    (→ the condition fails closed, never a wrong-typed comparison)."""
    if isinstance(value, bool):  # bool is int in Python — never order-compare
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _condition_matches(cond: Any, payload: dict) -> bool:
    """One {field, operator, value} against the payload. Fail-closed on any
    malformed shape, absent field, unknown operator, or type mismatch."""
    if not isinstance(cond, dict):
        return False
    field = cond.get("field")
    operator = cond.get("operator")
    if not field or operator not in _OPERATORS or "value" not in cond:
        return False
    if field not in payload:
        return False  # absent field = clean no-match (never an error)
    actual = payload[field]
    expected = cond["value"]

    if operator == "==":
        return actual == expected
    if operator == "!=":
        return actual != expected
    if operator == "in":
        return isinstance(expected, (list, tuple)) and actual in expected
    if operator == "contains":
        try:
            return expected in actual  # string substring or list membership
        except TypeError:
            return False
    # ordering operators — numeric only, fail-closed on non-coercible
    a, e = _numeric(actual), _numeric(expected)
    if a is None or e is None:
        return False
    if operator == ">":
        return a > e
    if operator == "<":
        return a < e
    if operator == ">=":
        return a >= e
    if operator == "<=":
        return a <= e
    return False


def conditions_match(conditions: Any, payload: dict | None) -> bool:
    """The trigger's structured condition list against the event payload.
    ALL elements must match (AND). Empty list → match (event_key alone).
    Anything malformed → False (fail-closed)."""
    if conditions is None:
        conditions = []
    if not isinstance(conditions, list):
        return False  # a flat string / object is malformed → fires NOTHING
    payload = payload or {}
    return all(_condition_matches(c, payload) for c in conditions)


# ── Tenant scoping (fan-out membership — the inverse of _fanout_companies) ─


def _fanout_includes(task: MoCTaskCatalog, company: Company | None) -> bool:
    """Would the schedule sweep's fan-out include this company for this task?
    The event fires the trigger only if the event's tenant is in the task's
    audience."""
    if company is None:
        return False
    if task.scope == "platform_default":
        return True
    if task.scope == "vertical_default":
        return (task.vertical or "").lower() == (company.vertical or "").lower()
    if task.scope == "tenant_override":
        return task.tenant_id == company.id
    return False


# ── Idempotency (the (trigger, event) pair — T-2.1a re-keyed) ──────────


def _already_fired(db: Session, *, trigger_id: str, event_id: str) -> bool:
    existing = (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.trigger_source == _TRIGGER_SOURCE,
            WorkflowRun.trigger_context["moc_task_trigger_id"].astext == trigger_id,
            WorkflowRun.trigger_context["event_id"].astext == event_id,
        )
        .first()
    )
    return existing is not None


# ── The fire (T-2.1's spine, event provenance in the context) ──────────


def _fire(
    db: Session, *, trig: MoCTaskTrigger, task: MoCTaskCatalog,
    event: MoCDomainEvent,
) -> WorkflowRun:
    return execute_template(
        db,
        template_id=task.workflow_template_id,
        company_id=event.company_id,
        trigger_source=_TRIGGER_SOURCE,
        trigger_context={
            "moc_task_trigger_id": trig.id,
            "event_id": event.id,
            "event_key": event.event_key,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "task_name": task.name,
        },
        triggered_by_user_id=None,
        allow_run=True,
        go_live=_MATCH_GO_LIVE,  # ← constant False this phase (T-2.2c converts)
    )


# ── The sweep ──────────────────────────────────────────────────────────


def check_moc_domain_events(cap: int = 500) -> dict:
    """The matcher sweep — runs on its own APScheduler cadence. Reads up to
    `cap` unprocessed outbox events, fires every (trigger, event) match
    DRY-RUN, marks events processed. Fresh DB session; per-event try/except
    (one bad event never blocks the sweep)."""
    db = SessionLocal()
    fired = 0
    processed = 0
    errors = 0
    try:
        events = (
            db.query(MoCDomainEvent)
            .filter(MoCDomainEvent.processed_at.is_(None))
            .order_by(MoCDomainEvent.emitted_at)
            .limit(cap)
            .all()
        )
        if not events:
            return {"processed": 0, "fired_dry_run": 0, "errors": 0}
        backlog_note = (
            db.query(MoCDomainEvent).filter(MoCDomainEvent.processed_at.is_(None)).count()
            if len(events) == cap
            else None
        )
        if backlog_note and backlog_note > cap:
            logger.warning(
                "MoC event matcher: backlog %s exceeds the per-sweep cap %s — "
                "processing the oldest %s this tick.", backlog_note, cap, cap,
            )

        for event in events:
            try:
                company = db.get(Company, event.company_id)
                triggers = (
                    db.query(MoCTaskTrigger)
                    .filter(
                        MoCTaskTrigger.kind == "event",
                        MoCTaskTrigger.is_active.is_(True),
                        MoCTaskTrigger.config["event"].astext == event.event_key,
                    )
                    .all()
                )
                for trig in triggers:
                    task = db.get(MoCTaskCatalog, trig.task_catalog_id)
                    if task is None or not task.is_active or not task.workflow_template_id:
                        continue
                    if not _fanout_includes(task, company):
                        continue
                    if not conditions_match((trig.config or {}).get("conditions"), event.payload):
                        continue
                    if _already_fired(db, trigger_id=trig.id, event_id=event.id):
                        continue  # the (trigger, event) pair already fired
                    try:
                        _fire(db, trig=trig, task=task, event=event)
                        fired += 1
                    except (ExecutionBridgeError, CanvasCompileError) as exc:
                        logger.error(
                            "MoC event fire failed (trigger %s / event %s): %s",
                            trig.id, event.id, exc,
                        )
                        errors += 1
                        db.rollback()
            except Exception as exc:  # noqa: BLE001 — one bad event never blocks the sweep
                logger.error("MoC event matching failed (event %s): %s", event.id, exc)
                errors += 1
                db.rollback()
            finally:
                # POISON-EVENT PROTECTION: processed even when a fire errored —
                # a bad event must not wedge the queue; the pair-dedup keeps a
                # re-run from double-firing the successes.
                event.processed_at = datetime.now(timezone.utc)
                db.commit()
                processed += 1
        return {"processed": processed, "fired_dry_run": fired, "errors": errors}
    finally:
        db.close()
