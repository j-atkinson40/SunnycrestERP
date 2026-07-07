"""MoC event-matcher sweep (Canvas↔Runtime Bridge T-2.2b) — the outbox consumer.

Reads UNPROCESSED `moc_domain_event` rows (the r119 partial-index work queue),
matches each against kind="event" `moc_task_trigger` rows (event_key + the
structured conditions evaluated against the event's emit-time payload), and
fires matches DRY-RUN through the T-2.0b engine. Mirrors the T-2.1a schedule
sweep exactly, one layer over the emission substrate.

THE SAFETY INVARIANT (T-2.2c — the T-2.1b conversion, replayed for events):
`go_live` comes ONLY from `_resolve_go_live(trig, template)` — the SAME single
source the schedule path uses. Live requires BOTH, both explicit: the trigger
PROMOTED (`is_live` — the kind-agnostic r117 column, shared with schedule
triggers) AND the task COMPILED (§6: a mirror-task event-trigger fires DRY-RUN
even when promoted). The default is dry-run; a real event-driven effect
requires the deliberate promotion of a compiled task's trigger.

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
from app.models.workflow_template import WorkflowTemplate
from app.services.maps_of_content.schedule_sweep import _resolve_go_live
from app.services.workflows.canvas_compiler import CanvasCompileError
from app.services.workflows.execution_bridge import ExecutionBridgeError, execute_template

logger = logging.getLogger(__name__)

# T-2.2c: go_live comes from `_resolve_go_live` — THE SAME single source the
# schedule path uses (T-2.1b): live requires the trigger PROMOTED (`is_live`,
# the kind-agnostic r117 column event-triggers share) AND the task COMPILED
# (the §6 mirror guard — a mirror-task event-trigger fires DRY-RUN even
# promoted). The T-2.2b constant `_MATCH_GO_LIVE = False` is gone; no other
# derivation exists on the event path.

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
    """Fire via T-2.1's spine. go_live comes ONLY from `_resolve_go_live`
    (is_live AND compiled — shared with the schedule path; §6 forces a mirror
    to dry-run). Loads the template so the discriminator is available."""
    template = db.get(WorkflowTemplate, task.workflow_template_id)
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
        go_live=_resolve_go_live(trig, template),  # ← ONE source, shared with schedule
    )


# ── The sweep ──────────────────────────────────────────────────────────


# SWEEP HARDENING (task_0daaafd0): the per-tick FIRE cap (distinct from the
# events-read `cap`) — a runaway bound. Capped work DEFERS cleanly on the
# event path: an event not fully handled keeps processed_at NULL and re-sweeps
# next tick; the (trigger, event) pair-dedup makes re-processing exact-once.
_EVENT_FIRE_CAP = 500


def check_moc_domain_events(cap: int = 500, fire_cap: int = _EVENT_FIRE_CAP) -> dict:
    """The matcher sweep — runs on its own APScheduler cadence. Reads up to
    `cap` unprocessed outbox events, fires every (trigger, event) match,
    marks events processed. Fresh DB session; per-event try/except
    (one bad event never blocks the sweep).

    THE FIRE CAP: at most `fire_cap` fires per tick. CRITICAL partial-handling
    contract — `processed_at` is set ONLY when an event's match pass ran to
    COMPLETION: an event capped mid-matches stays unprocessed and re-sweeps
    next tick (already-fired pairs dedup-skip; the remainder fires — nothing
    lost, nothing doubled). Errors still mark processed (the poison-event
    protection — only CAP deferral skips the marking). Tripping is LOUD."""
    db = SessionLocal()
    fired = 0
    processed = 0
    errors = 0
    cap_tripped = False
    deferred_events = 0
    try:
        events = (
            db.query(MoCDomainEvent)
            .filter(MoCDomainEvent.processed_at.is_(None))
            .order_by(MoCDomainEvent.emitted_at)
            .limit(cap)
            .all()
        )
        if not events:
            return {"processed": 0, "fired_dry_run": 0, "errors": 0,
                    "cap_tripped": False, "deferred_events": 0}
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
            if fired >= fire_cap:
                # THE CAP — stop starting new events; everything from here
                # stays UNPROCESSED and defers to the next tick (natural
                # backpressure: processed_at NULL = still in the work queue).
                cap_tripped = True
                deferred_events = len(events) - processed
                break
            completed = True  # processed_at is set ONLY when this stays True
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
                    if fired >= fire_cap:
                        # Capped MID-event: the remaining matches must NOT be
                        # lost — leave the event unprocessed; next tick the
                        # already-fired pairs dedup-skip and the rest fire.
                        completed = False
                        cap_tripped = True
                        break
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
                # completed stays True: errors MARK processed (poison-event
                # protection) — only CAP deferral skips the marking.
            finally:
                if completed:
                    event.processed_at = datetime.now(timezone.utc)
                    db.commit()
                    processed += 1
                else:
                    db.commit()  # keep the fired runs; the event re-sweeps
                    deferred_events += 1
        if cap_tripped:
            logger.warning(
                "MoC event matcher FIRE CAP tripped at %s fires this tick — "
                "%s event(s) deferred unprocessed to the next tick (the pair-"
                "dedup makes re-processing exact-once). A trip is a runaway "
                "signal: inspect the matching triggers' breadth.",
                fire_cap, deferred_events,
            )
        return {"processed": processed, "fired_dry_run": fired, "errors": errors,
                "cap_tripped": cap_tripped, "deferred_events": deferred_events}
    finally:
        db.close()
