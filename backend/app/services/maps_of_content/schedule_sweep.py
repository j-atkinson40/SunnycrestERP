"""MoC schedule sweep (Canvas↔Runtime Bridge T-2.1a/b) — the first live caller.

A PARALLEL sweep (its own iteration over `moc_task_trigger` schedule rows — a
different entity than the workflow scheduler's loop) that fires DUE MoC schedule-
triggers through the T-2.0b dry-run-safe engine. It REUSES the scheduler's matcher
helpers (`_resolve_tenant_tz`, `_matches_time_of_day`, `_intended_scheduled_fire`)
and mirrors its idempotency pattern (re-keyed on the TRIGGER, since compiled
workflows are ephemeral).

THE SAFETY INVARIANT: `go_live` has ONE source — `_resolve_go_live(trig, template)`
(T-2.1b; was the constant False in T-2.1a). Live requires BOTH, both explicit:
the trigger is PROMOTED (`is_live`, default FALSE — a deliberate per-trigger act)
AND its task resolves to a COMPILED (single-owner) workflow. A MIRROR task NEVER
fires live (§6 double-fire hazard vs its independently-scheduled source) — it
fires DRY-RUN even when is_live=True. So the DEFAULT is dry-run (unpromoted or
mirror), and a real effect requires the deliberate promotion of a compiled task.
No scattered convenience True; a promoted trigger cannot fire live through any
other path. The engine (T-2.0b) suppresses every real effect in dry-run.

Correctness (inherited + one fix):
- IDEMPOTENCY: a due trigger fires ONCE per intended-fire tick, deduped on
  (moc_task_trigger_id, intended_fire, company) via WorkflowRun.trigger_context —
  no new table.
- TIMEZONE: `time_of_day` is evaluated TENANT-LOCAL (the fix for the scheduler's
  UTC bug — we pass a tenant-local `now` to the reused matcher). `cron` is already
  tenant-tz-aware.
- CATCH-UP: the 15-min match window means a backlog (a schedule due while the
  system was down beyond the window) is naturally SKIPPED — no backlog storm.
- time_after_event is deferred (funeral_case-only upstream) — cron + time_of_day
  this phase.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.company import Company
from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.moc_task_trigger import MoCTaskTrigger
from app.models.workflow import WorkflowRun, WorkflowRunStep
from app.models.workflow_template import WorkflowTemplate
from app.services.workflow_scheduler import (
    _intended_scheduled_fire,
    _matches_time_of_day,
    _resolve_tenant_tz,
)
from app.services.workflows.canvas_compiler import CanvasCompileError
from app.services.workflows.execution_bridge import ExecutionBridgeError, execute_template

logger = logging.getLogger(__name__)


def _resolve_go_live(
    trig: MoCTaskTrigger, template: WorkflowTemplate | None
) -> bool:
    """THE ONE SOURCE of go_live (T-2.1b — the safety-critical derivation). Live
    requires BOTH, both explicit:
      1. the trigger is PROMOTED (`is_live`) — a deliberate per-trigger act; AND
      2. its task resolves to a COMPILED (single-owner) workflow.

    A MIRROR task (§6 double-fire hazard: re-point runs the runtime source, which
    is independently scheduled) NEVER fires live — it fires DRY-RUN with a logged
    reason, even when is_live=True. Mirror live-scheduling is deferred to its own
    arc. This is the SOLE place go_live is derived — never a scattered convenience
    True; a promoted trigger cannot fire live through any other path."""
    if not trig.is_live:
        return False
    if template is not None and template.mirrored_from_workflow_id is not None:
        logger.info(
            "MoC trigger %s is is_live but its task is a MIRROR — firing DRY-RUN "
            "(mirror live-scheduling deferred, §6 double-fire hazard).",
            trig.id,
        )
        return False
    return True

_TRIGGER_SOURCE = "moc_task_schedule"


def _fanout_companies(task: MoCTaskCatalog, companies: list[Company]) -> list[Company]:
    """Which tenants a task's schedule-trigger fires for — the vertical fan-out
    precedent (mirrors how a vertical workflow fires per-company-in-vertical)."""
    if task.scope == "platform_default":
        return companies
    if task.scope == "vertical_default":
        tv = (task.vertical or "").lower()
        return [c for c in companies if (c.vertical or "").lower() == tv]
    if task.scope == "tenant_override":
        return [c for c in companies if c.id == task.tenant_id]
    return []


def _due_intended_fire(
    trig: MoCTaskTrigger, company: Company, now: datetime
) -> datetime | None:
    """The intended-fire datetime if the trigger is due THIS tick, else None. The
    intended-fire time doubles as the idempotency key (unique per window)."""
    cfg = trig.config or {}
    spec = cfg.get("spec_kind")
    tz = _resolve_tenant_tz(company.timezone)

    if spec == "time_of_day":
        now_local = now.astimezone(tz)  # THE tz FIX — tenant-local, not UTC
        if not _matches_time_of_day(cfg, now_local):
            return None
        try:
            hh, mm = str(cfg.get("time")).split(":", 1)
            return now_local.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
        except Exception:
            return None

    if spec == "cron":
        cron = cfg.get("cron")
        if not cron:
            return None
        try:
            return _intended_scheduled_fire(cron, tz, now)  # tz-aware, window-based, or None
        except ValueError:
            logger.warning("MoC schedule trigger %s: invalid cron %r — skipped", trig.id, cron)
            return None

    # time_after_event (funeral_case-only upstream) is deferred to a later phase.
    return None


def _already_fired(
    db: Session, *, trigger_id: str, company_id: str, intended_fire: datetime
) -> bool:
    """Deduped on the TRIGGER (not the ephemeral compiled workflow) + intended
    fire — a 6pm task fires once across the N sweep-ticks in its window."""
    intended_iso = intended_fire.isoformat()
    intended_utc_iso = intended_fire.astimezone(timezone.utc).isoformat()
    existing = (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.company_id == company_id,
            WorkflowRun.trigger_source == _TRIGGER_SOURCE,
            WorkflowRun.trigger_context["moc_task_trigger_id"].astext == trigger_id,
            WorkflowRun.trigger_context["intended_fire"].astext.in_(
                [intended_iso, intended_utc_iso]
            ),
        )
        .first()
    )
    return existing is not None


def _fire(
    db: Session, *, trig: MoCTaskTrigger, task: MoCTaskCatalog,
    company: Company, intended_fire: datetime,
) -> WorkflowRun:
    """Fire the task's workflow through the T-2.0b engine. go_live comes ONLY from
    `_resolve_go_live` (is_live AND compiled) — never a convenience True. Loads
    the template so the compiled-vs-mirror discriminator is available to the
    guard (the SAME `mirrored_from_workflow_id` the resolver uses)."""
    template = db.get(WorkflowTemplate, task.workflow_template_id)
    go_live = _resolve_go_live(trig, template)
    return execute_template(
        db,
        template_id=task.workflow_template_id,
        company_id=company.id,
        trigger_source=_TRIGGER_SOURCE,
        trigger_context={
            "moc_task_trigger_id": trig.id,
            "intended_fire": intended_fire.isoformat(),
            "task_name": task.name,
        },
        triggered_by_user_id=None,
        allow_run=True,
        go_live=go_live,  # ← ONE source: _resolve_go_live(is_live AND compiled)
    )


def check_moc_task_schedules(now: datetime | None = None) -> dict:
    """The sweep — runs on the 15-min APScheduler cadence. Fires every DUE MoC
    schedule-trigger DRY-RUN. Fresh DB session (scheduler jobs must not share
    sessions). Per-fire try/except: one bad trigger never blocks the sweep."""
    db = SessionLocal()
    now = now or datetime.now(timezone.utc)
    fired = 0
    errors = 0
    try:
        triggers = (
            db.query(MoCTaskTrigger)
            .filter(
                MoCTaskTrigger.kind == "schedule",
                MoCTaskTrigger.is_active.is_(True),
            )
            .all()
        )
        if not triggers:
            return {"fired_dry_run": 0, "errors": 0}
        companies = db.query(Company).filter(Company.is_active.is_(True)).all()

        for trig in triggers:
            task = db.get(MoCTaskCatalog, trig.task_catalog_id)
            if task is None or not task.is_active or not task.workflow_template_id:
                continue  # nothing runnable to fire
            for company in _fanout_companies(task, companies):
                try:
                    intended = _due_intended_fire(trig, company, now)
                    if intended is None:
                        continue  # not due this tick (or backlog outside the window → skipped)
                    if _already_fired(db, trigger_id=trig.id, company_id=company.id, intended_fire=intended):
                        continue  # idempotent — already fired this window
                    _fire(db, trig=trig, task=task, company=company, intended_fire=intended)
                    fired += 1
                except (ExecutionBridgeError, CanvasCompileError) as exc:
                    logger.error(
                        "MoC schedule fire failed (trigger %s / company %s): %s",
                        trig.id, company.id, exc,
                    )
                    errors += 1
                    db.rollback()
        return {"fired_dry_run": fired, "errors": errors}
    finally:
        db.close()


# ── Observability — the dry-run run-log (see what fired) ───────────────


def list_schedule_runs(
    db: Session, *, limit: int = 50, trigger_id: str | None = None
) -> list[dict]:
    """Recent MoC fires — SCHEDULE and EVENT (T-2.2b) — + their "would do X"
    records, so an operator SEES what fired dry-run and what it would have done.
    One unified log: schedule fires (trigger_source=moc_task_schedule) and
    event fires (moc_task_event) with a `source` discriminator; event rows
    carry their provenance (event_key + event_id — WHAT fired them, the new
    bit vs schedule). `trigger_id` (T-2.1c) scopes to ONE trigger — the go-live
    confirm's latest-preview fetch — and works identically for event triggers.
    FIDELITY CAVEAT (canon): a dry-run fire whose branching depends on a
    suppressed effect-step's output takes a synthetic branch — a preview may not
    perfectly predict live for such tasks."""
    q = db.query(WorkflowRun).filter(
        WorkflowRun.trigger_source.in_((_TRIGGER_SOURCE, "moc_task_event"))
    )
    if trigger_id is not None:
        q = q.filter(
            WorkflowRun.trigger_context["moc_task_trigger_id"].astext == trigger_id
        )
    runs = q.order_by(WorkflowRun.started_at.desc()).limit(limit).all()
    out: list[dict] = []
    for r in runs:
        steps = (
            db.query(WorkflowRunStep)
            .filter(WorkflowRunStep.run_id == r.id)
            .order_by(WorkflowRunStep.executed_at)
            .all()
        )
        would_do = [
            (s.output_data or {}).get("would")
            for s in steps
            if s.output_data and (s.output_data or {}).get("would")
        ]
        ctx = r.trigger_context or {}
        out.append({
            "run_id": r.id,
            "task_name": ctx.get("task_name"),
            "moc_task_trigger_id": ctx.get("moc_task_trigger_id"),
            "company_id": r.company_id,
            "status": r.status,
            "is_dry_run": bool((r.output_data or {}).get("__dry_run__")),
            "intended_fire": ctx.get("intended_fire"),
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "would_do": would_do,
            # T-2.2b — the source discriminator + event provenance ("event
            # order.created matched trigger X" — null for schedule fires).
            "source": "event" if r.trigger_source == "moc_task_event" else "schedule",
            "event_key": ctx.get("event_key"),
            "event_id": ctx.get("event_id"),
        })
    return out
