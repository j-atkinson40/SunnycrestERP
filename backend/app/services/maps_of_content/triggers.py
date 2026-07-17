"""MoC task trigger service (MoC Triggers T-1a) — the descriptive trigger CRUD.

A task carries 0..N heterogeneous triggers (schedule | event | manual), a
collection mirroring the focus join. DESCRIPTIVE only — triggers are legible/
editable metadata that does NOT fire; execution is the deferred T-2 canvas↔
runtime bridge.

The validator checks SHAPE, not fireability (the descriptive layer):
- kind ∈ {schedule, event, manual};
- schedule config matches its spec_kind's shape (the three real workflow_scheduler
  shapes, so the future bridge is a wiring job);
- event config: the event resolves in the curated catalog; `conditions` is a LIST
  (a flat string is REJECTED — the structured-for-expansion guard); each
  condition's field is exposed by the event's filterable_fields (referential);
  operator ∈ the operator set + value present;
- manual takes no config.
A bad trigger is rejected LOUDLY (TriggerValidationError → HTTP 400), never a
swallowed no-op.

Also exposes `humanize_schedule(config)` — the non-destructive Frequency
derivation (a schedule trigger's human summary), landed as a helper this phase;
the 2a Frequency field is untouched.
"""
from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy.orm import Session

from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.moc_task_trigger import MoCTaskTrigger
from app.services.maps_of_content import trigger_events

_UNSET: Any = object()

KINDS = ("schedule", "event", "manual")
SCHEDULE_SPEC_KINDS = ("time_of_day", "cron", "time_after_event", "ordinal_weekday")
# Tenant Ponder-Editor P1 — the ordinal-weekday rider ("the first Monday of
# every month"). Standard cron can't express it (dom/dow OR-semantics), so
# it's a first-class spec_kind the sweep evaluates tenant-local.
ORDINALS = (1, 2, 3, 4, "last")
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
# Condition operators (filtered now; the list-of-conditions grows to rich later).
OPERATORS = ("==", "!=", "in", ">", "<", ">=", "<=", "contains")


class TriggerValidationError(ValueError):
    """A rejected trigger write (bad kind/config/condition) — HTTP 400 (404 on
    'not found')."""


# ── Validation (structural — the descriptive layer validates shape) ─────────


def _validate_schedule(config: dict) -> None:
    spec = config.get("spec_kind")
    if spec not in SCHEDULE_SPEC_KINDS:
        raise TriggerValidationError(
            f"schedule spec_kind must be one of {SCHEDULE_SPEC_KINDS} (got {spec!r})"
        )
    if spec == "time_of_day":
        if not config.get("time"):
            raise TriggerValidationError("time_of_day schedule requires 'time' (HH:MM)")
        days = config.get("days")
        if days is not None and not isinstance(days, list):
            raise TriggerValidationError("time_of_day 'days' must be a list")
    elif spec == "cron":
        if not config.get("cron"):
            raise TriggerValidationError("cron schedule requires a 'cron' expression")
    elif spec == "time_after_event":
        for f in ("record_type", "field"):
            if not config.get(f):
                raise TriggerValidationError(f"time_after_event schedule requires {f!r}")
        offset = config.get("offset_days", 0)
        if not isinstance(offset, int):
            raise TriggerValidationError("time_after_event 'offset_days' must be an int")
    elif spec == "ordinal_weekday":
        ordinal = config.get("ordinal")
        if ordinal not in ORDINALS:
            raise TriggerValidationError(
                f"ordinal_weekday 'ordinal' must be one of {ORDINALS} (got {ordinal!r})"
            )
        weekday = config.get("weekday")
        if weekday not in WEEKDAYS:
            raise TriggerValidationError(
                f"ordinal_weekday 'weekday' must be one of {WEEKDAYS} (got {weekday!r})"
            )
        time_str = config.get("time")
        try:
            hh, mm = str(time_str).split(":", 1)
            if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
                raise ValueError
        except (ValueError, AttributeError):
            raise TriggerValidationError(
                f"ordinal_weekday requires 'time' as HH:MM (got {time_str!r})"
            )


def _validate_event(db: Session, *, config: dict, vertical: str | None) -> None:
    event_key = config.get("event")
    if not event_key:
        raise TriggerValidationError("event trigger requires an 'event'")
    ev = trigger_events.get_event(db, event_key=event_key, vertical=vertical)
    if ev is None:
        raise TriggerValidationError(
            f"event {event_key!r} is not in the catalog for vertical {vertical!r}"
        )
    conditions = config.get("conditions")
    # THE LOAD-BEARING GUARD: conditions is a LIST holding {field,operator,value}
    # objects — a flat string is rejected so filtered→rich is appending, never a
    # migration.
    if not isinstance(conditions, list):
        raise TriggerValidationError(
            "event 'conditions' must be a list of {field, operator, value} objects "
            f"(got {type(conditions).__name__}) — the structured-for-expansion shape"
        )
    allowed = {f.get("field") for f in (ev.filterable_fields or [])}
    for cond in conditions:
        if not isinstance(cond, dict):
            raise TriggerValidationError("each condition must be a {field, operator, value} object")
        field = cond.get("field")
        operator = cond.get("operator")
        if field not in allowed:
            raise TriggerValidationError(
                f"condition field {field!r} is not exposed by event {event_key!r} "
                f"(allowed: {sorted(f for f in allowed if f)})"
            )
        if operator not in OPERATORS:
            raise TriggerValidationError(
                f"condition operator {operator!r} invalid (allowed: {OPERATORS})"
            )
        if "value" not in cond:
            raise TriggerValidationError("each condition requires a 'value'")


def validate_trigger(
    db: Session, *, kind: str, config: dict, vertical: str | None
) -> None:
    """Structural validation for a (kind, config). Raises TriggerValidationError."""
    if kind not in KINDS:
        raise TriggerValidationError(f"kind must be one of {KINDS} (got {kind!r})")
    config = config or {}
    if kind == "manual":
        if config:
            raise TriggerValidationError("manual triggers take no config")
    elif kind == "schedule":
        _validate_schedule(config)
    elif kind == "event":
        _validate_event(db, config=config, vertical=vertical)


# ── CRUD ────────────────────────────────────────────────────────────────────


def _require_task(db: Session, task_catalog_id: str) -> MoCTaskCatalog:
    task = db.get(MoCTaskCatalog, task_catalog_id)
    if task is None or not task.is_active:
        raise TriggerValidationError(f"task {task_catalog_id!r} not found")
    return task


def list_triggers(db: Session, *, task_catalog_id: str) -> list[MoCTaskTrigger]:
    return (
        db.query(MoCTaskTrigger)
        .filter(MoCTaskTrigger.task_catalog_id == task_catalog_id)
        .order_by(MoCTaskTrigger.display_order, MoCTaskTrigger.created_at)
        .all()
    )


def add_trigger(
    db: Session,
    *,
    task_catalog_id: str,
    kind: str,
    config: dict | None = None,
    label: str | None = None,
    display_order: int = 0,
    actor_id: str | None = None,
) -> MoCTaskTrigger:
    """Validate + attach a trigger to a task. 400 on a bad shape. Caller commits."""
    task = _require_task(db, task_catalog_id)
    config = config or {}
    validate_trigger(db, kind=kind, config=config, vertical=task.vertical)
    trig = MoCTaskTrigger(
        task_catalog_id=task_catalog_id, kind=kind, config=config, label=label,
        display_order=display_order, created_by=actor_id, updated_by=actor_id,
    )
    db.add(trig)
    db.flush()
    return trig


def patch_trigger(
    db: Session,
    *,
    trigger_id: str,
    kind: Any = _UNSET,
    config: Any = _UNSET,
    label: Any = _UNSET,
    display_order: Any = _UNSET,
    is_active: Any = _UNSET,
    is_live: Any = _UNSET,
    actor_id: str | None = None,
) -> MoCTaskTrigger:
    """Partial update. _UNSET = leave alone. Re-validates the RESULTING (kind,
    config). `is_live` is the T-2.1b live-promotion (default FALSE; the sweep only
    fires live when is_live AND the task is compiled — the mirror guard is in the
    sweep, not here). Caller commits."""
    trig = db.get(MoCTaskTrigger, trigger_id)
    if trig is None:
        raise TriggerValidationError(f"trigger {trigger_id!r} not found")
    task = db.get(MoCTaskCatalog, trig.task_catalog_id)
    vertical = task.vertical if task else None

    new_kind = trig.kind if kind is _UNSET else kind
    new_config = trig.config if config is _UNSET else (config or {})
    # Re-validate ONLY when the (kind, config) shape is actually being changed.
    # Validating an UNCHANGED config against the live catalog means catalog
    # drift bricks unrelated patches — an event removed from the catalog would
    # make its triggers impossible to deactivate or promote/de-promote
    # (T-2.2c surfaced this via the synthetic witness event key). Shape
    # validation gates writes TO the shape, not writes near it.
    if kind is not _UNSET or config is not _UNSET:
        validate_trigger(db, kind=new_kind, config=new_config, vertical=vertical)

    if kind is not _UNSET:
        trig.kind = kind
    if config is not _UNSET:
        trig.config = new_config
    if label is not _UNSET:
        trig.label = label
    if display_order is not _UNSET:
        trig.display_order = display_order
    if is_active is not _UNSET:
        trig.is_active = is_active
    if is_live is not _UNSET:
        trig.is_live = is_live
    trig.updated_by = actor_id
    db.flush()
    return trig


def delete_trigger(db: Session, *, trigger_id: str) -> bool:
    """Hard-delete a trigger. Returns False if it didn't exist. Caller commits."""
    trig = db.get(MoCTaskTrigger, trigger_id)
    if trig is None:
        return False
    db.delete(trig)
    db.flush()
    return True


# ── Frequency derivation (non-destructive; coexist-first) ────────────────────
#
# The schedule trigger is the source of truth for "when"; Frequency (the 2a
# field) becomes a derived summary. THIS phase lands the helper only — the 2a
# Frequency field is untouched (still editable, still the fallback). Wiring the
# derived label into the surface is T-1b.

_DAY_ORDER = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _fmt_time(hhmm: str) -> str:
    """'18:00' → '6:00 PM'. Falls back to the raw string on a bad value."""
    try:
        hh, mm = hhmm.split(":", 1)
        h, m = int(hh), int(mm)
        suffix = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h12}:{m:02d} {suffix}"
    except Exception:
        return hhmm


def _humanize_cron(cron: str) -> str:
    """Best-effort readable label for common cron shapes; raw cron as fallback."""
    parts = cron.split()
    if len(parts) != 5:
        return cron
    minute, hour, dom, month, dow = parts
    # Sub-daily interval shapes (T-1: the adopted expense-cat cron surfaced
    # "*/15 * * * *" reading as "Daily" — misleading on the authority chip).
    if minute.startswith("*/") and hour == "*" and dom == "*" and dow == "*":
        return f"Every {minute[2:]} minutes"
    if hour.startswith("*/") and dom == "*" and dow == "*":
        return f"Every {hour[2:]} hours"
    try:
        at = _fmt_time(f"{int(hour):02d}:{int(minute):02d}") if hour != "*" and minute != "*" else ""
    except ValueError:
        at = ""
    if dom != "*" and dow == "*":
        # Monthly on a day-of-month ('last' = APScheduler end-of-month).
        if dom == "last":
            return "Monthly · last day" + (f", {at}" if at else "")
        suffix = {"1": "1st", "2": "2nd", "3": "3rd"}.get(dom, f"{dom}th")
        return f"Monthly · {suffix}" + (f", {at}" if at else "")
    if dow != "*" and dom == "*":
        # Standard cron dow: 0=Sun, 1=Mon … 6=Sat; _DAY_ORDER starts at Mon.
        # (T-2 walk fix: "0 8 * * 1" chipped as "Tue" while firing Monday.)
        day = _DAY_ORDER[(int(dow) - 1) % 7].capitalize() if dow.isdigit() else dow
        return f"Weekly · {day}" + (f", {at}" if at else "")
    if dom == "*" and dow == "*":
        return "Daily" + (f" · {at}" if at else "")
    return cron


def summarize_trigger(kind: str, config: dict) -> str:
    """A one-line chip summary for a trigger — the display label the cell/panel
    render. Schedule reuses humanize_schedule (no frontend drift); event reads
    the key + first condition; manual is fixed. Non-firing; purely for display."""
    config = config or {}
    if kind == "schedule":
        return humanize_schedule(config)
    if kind == "event":
        event = config.get("event", "")
        conditions = config.get("conditions") or []
        if conditions and isinstance(conditions[0], dict):
            c = conditions[0]
            return f"{event}: {c.get('value')}"
        return event or "Event"
    return "Manual"


def humanize_schedule(config: dict) -> str:
    """A schedule config → a human summary label (the Frequency derivation).
    Non-firing; purely for display."""
    config = config or {}
    spec = config.get("spec_kind")
    if spec == "time_of_day":
        days = config.get("days") or []
        at = _fmt_time(config.get("time", ""))
        if not days or len(days) >= 7:
            day_part = "Daily"
        else:
            ordered = [d for d in _DAY_ORDER if d in days]
            day_part = ", ".join(d.capitalize() for d in ordered)
        return f"{day_part} · {at}" if at else day_part
    if spec == "cron":
        return _humanize_cron(config.get("cron", ""))
    if spec == "ordinal_weekday":
        ordinal = config.get("ordinal")
        ord_label = "Last" if ordinal == "last" else {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}.get(ordinal, str(ordinal))
        day = str(config.get("weekday", "")).capitalize()
        at = _fmt_time(config.get("time", ""))
        return f"Monthly · {ord_label} {day}" + (f", {at}" if at else "")
    if spec == "time_after_event":
        n = config.get("offset_days", 0)
        return f"{n} day{'s' if n != 1 else ''} after {config.get('field', 'event')}"
    return "Scheduled"
