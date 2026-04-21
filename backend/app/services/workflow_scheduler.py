"""Workflow scheduler — time_of_day + time_after_event + scheduled trigger support.

Phase W-1 shipped `time_of_day` + `time_after_event` dispatch. Workflow
Arc Phase 8b.5 adds `scheduled` (cron-based) dispatch to fix the
latent bug where 8 Tier-1 `wf_sys_*` workflows declared
`trigger_type="scheduled"` + `trigger_config.cron` but were NOT
being queried or fired by this sweep.

A single APScheduler job runs every 15 minutes (registered in
`backend/app/scheduler.py` as `workflow_time_based_check`) and checks
three classes of workflows:

  time_of_day:       fires when current UTC wall-clock matches
                     config.time + days. (Latent TZ bug: doesn't
                     respect tenant TZ. Flagged for follow-on cleanup
                     — see Phase 8b.5 session log.)
  time_after_event:  fires for records where record_date + offset_days
                     == today.
  scheduled:         (Phase 8b.5) fires when the cron expression in
                     `trigger_config.cron` would have fired anywhere
                     in the last 15 minutes, per tenant. Uses
                     `CronTrigger.from_crontab(cron, timezone=tenant_tz)`
                     via APScheduler — no new dependency. Tenant TZ
                     resolved via `Company.timezone` with
                     `America/New_York` fallback (mirrors briefings
                     precedent).

Idempotency for cron-fired workflows is enforced by
`_already_fired_scheduled` — query for any `WorkflowRun` with
`trigger_source="schedule"` whose `started_at >= intended_fire_time`.
Self-healing across system restarts; no schema change needed.

Manual + event-triggered workflows are dispatched elsewhere.
APScheduler's dynamic per-workflow registration (Phase W-2) will
eventually replace this polling approach.
"""

import logging
from datetime import date, datetime, time, timezone, timedelta

try:  # py3.9+
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.company import Company
from app.models.workflow import Workflow, WorkflowEnrollment, WorkflowRun
from app.services import workflow_engine


logger = logging.getLogger(__name__)

DAY_ABBREV = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}

# Matches the briefings scheduler precedent.
_DEFAULT_TENANT_TZ = "America/New_York"
# Sweep cadence — `backend/app/scheduler.py` registers the sweep at
# a 15-minute interval. Cron dispatch uses this as the window.
_SWEEP_WINDOW_MINUTES = 15


def _resolve_tenant_tz(tz_name: str | None) -> ZoneInfo:
    """Resolve a tenant's timezone with graceful fallback. Mirrors
    `app.services.briefings.scheduler_integration._resolve_tz`."""
    try:
        return ZoneInfo(tz_name or _DEFAULT_TENANT_TZ)
    except Exception:
        return ZoneInfo(_DEFAULT_TENANT_TZ)


def _matches_time_of_day(trigger_config: dict, now: datetime) -> bool:
    """Check if now matches time_of_day config.

    Configs are coarse (15-min scheduler interval). A workflow with time "18:00"
    fires when now is in [18:00, 18:15). Days are 3-letter abbreviations.

    Note: `now` is UTC today — this does NOT apply tenant TZ. That's a
    latent bug tracked for follow-on cleanup (Phase 8b.5 session log).
    """
    time_str = (trigger_config or {}).get("time")
    days = (trigger_config or {}).get("days") or []
    if not time_str:
        return False
    try:
        hh, mm = time_str.split(":", 1)
        target = time(int(hh), int(mm))
    except Exception:
        return False

    # Within 15 minutes of target, same day
    now_t = now.time().replace(second=0, microsecond=0)
    target_minutes = target.hour * 60 + target.minute
    now_minutes = now_t.hour * 60 + now_t.minute
    if not (0 <= now_minutes - target_minutes < 15):
        return False

    if days:
        weekday = DAY_ABBREV.get(now.weekday())
        if weekday not in days:
            return False
    return True


def _matches_time_after_event(
    db: Session, workflow: Workflow, company_id: str, now: datetime
) -> list[str]:
    """Return list of record_ids to fire for a time_after_event workflow today."""
    cfg = workflow.trigger_config or {}
    record_type = cfg.get("record_type")
    field = cfg.get("field")
    offset = int(cfg.get("offset_days") or 0)
    if not record_type or not field:
        return []

    table_map = {
        "funeral_case": ("funeral_cases", "case_service", "service_date"),
    }
    if record_type not in table_map:
        # Phase W-1 supports funeral_case only; easy to extend via the map
        return []

    main_table, joined_table, joined_field = table_map[record_type]
    target_date = (now.date() - timedelta(days=offset)).isoformat()

    try:
        # funeral_cases lives at `funeral_cases` and service_date is on case_service
        if joined_table and joined_field == field:
            rows = db.execute(
                sql_text(
                    f"SELECT fc.id FROM {main_table} fc "
                    f"JOIN {joined_table} cs ON cs.case_id = fc.id "
                    f"WHERE fc.company_id = :cid AND cs.{field} = :dt"
                ),
                {"cid": company_id, "dt": target_date},
            ).fetchall()
        else:
            rows = db.execute(
                sql_text(
                    f"SELECT id FROM {main_table} "
                    f"WHERE company_id = :cid AND {field} = :dt"
                ),
                {"cid": company_id, "dt": target_date},
            ).fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []


# ── Phase 8b.5 — scheduled (cron) trigger support ────────────────────


def _intended_scheduled_fire(
    cron_expr: str, tenant_tz: ZoneInfo, now: datetime
) -> datetime | None:
    """Return the cron fire time that falls in the trailing 15-min
    window, or None if the cron didn't want to fire in this window.

    Uses APScheduler's `CronTrigger.from_crontab` — same parser the
    platform already uses for every APScheduler job in
    `backend/app/scheduler.py`.

    Returns an aware datetime in `tenant_tz`.

    Raises `ValueError` on malformed cron strings — caller catches.
    """
    trigger = CronTrigger.from_crontab(cron_expr, timezone=tenant_tz)
    # Walk back by the sweep window and ask: what's the next fire time
    # at or after (now - window)? If it's <= now, the cron wanted to
    # fire in this window.
    window_start = now - timedelta(minutes=_SWEEP_WINDOW_MINUTES)
    # get_next_fire_time(previous_fire_time, now_arg) returns the next
    # fire at or after `now_arg`. Passing window_start as `now_arg`
    # finds the earliest fire at or after the window start.
    intended = trigger.get_next_fire_time(None, window_start)
    if intended is None:
        return None
    # Normalize `intended` to an aware datetime for comparison. APScheduler
    # returns tz-aware dts when a timezone is supplied.
    if intended <= now:
        return intended
    return None


def _already_fired_scheduled(
    db: Session,
    *,
    workflow_id: str,
    company_id: str,
    intended_fire: datetime,
) -> bool:
    """True if any scheduled WorkflowRun for this (workflow, company)
    pair has already recorded this exact intended_fire tick in its
    trigger_context.

    Guards against the same cron tick firing twice across adjacent
    15-min sweeps (or within a single tick if the sweep is re-invoked).
    Self-healing: the check is against the canonical audit trail
    (`trigger_context.intended_fire`) rather than the wall-clock
    `started_at`, so the result is correct regardless of how long
    start_run took to execute or whether the system restarted
    between ticks.
    """
    # trigger_context is JSONB; compare via the ISO-formatted string
    # stored there. Normalizing to UTC iso ensures matches even when
    # the cron is interpreted in a tenant-local TZ.
    intended_iso = intended_fire.isoformat()
    intended_utc_iso = intended_fire.astimezone(timezone.utc).isoformat()
    existing = (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.workflow_id == workflow_id,
            WorkflowRun.company_id == company_id,
            WorkflowRun.trigger_source == "schedule",
            WorkflowRun.trigger_context["intended_fire"].astext.in_(
                [intended_iso, intended_utc_iso]
            ),
        )
        .first()
    )
    return existing is not None


def _already_ran_for_record(db: Session, workflow_id: str, record_id: str) -> bool:
    """Avoid duplicate triggers for the same record."""
    existing = (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.workflow_id == workflow_id,
            WorkflowRun.trigger_source == "schedule",
        )
        .all()
    )
    for r in existing:
        ctx = (r.trigger_context or {}).get("record", {})
        if ctx.get("id") == record_id:
            return True
    return False


def check_time_based_workflows() -> dict:
    """APScheduler job — runs every 15 minutes.

    Creates fresh DB session (scheduler jobs must not share sessions).
    Returns a summary: {"time_of_day_fired": int, "time_after_fired": int,
    "scheduled_fired": int, "scheduled_skipped_invalid_cron": int}.
    """
    db = SessionLocal()
    fired_tod = 0
    fired_tae = 0
    fired_sched = 0
    skipped_invalid_cron = 0
    now = datetime.now(timezone.utc)
    try:
        # Load all active time-based workflows (Phase 8b.5 adds "scheduled").
        workflows = (
            db.query(Workflow)
            .filter(
                Workflow.is_active == True,  # noqa: E712
                Workflow.trigger_type.in_(
                    ["time_of_day", "time_after_event", "scheduled"]
                ),
            )
            .all()
        )
        companies = db.query(Company).filter(Company.is_active == True).all()  # noqa: E712

        for w in workflows:
            for company in companies:
                # Scope by vertical
                if w.vertical and company.vertical and w.vertical != (company.vertical or "").lower():
                    continue
                if w.company_id and w.company_id != company.id:
                    continue
                # Tier 3 requires active enrollment
                if w.tier == 3:
                    enrollment = (
                        db.query(WorkflowEnrollment)
                        .filter(
                            WorkflowEnrollment.workflow_id == w.id,
                            WorkflowEnrollment.company_id == company.id,
                        )
                        .first()
                    )
                    if not enrollment or not enrollment.is_active:
                        continue

                if w.trigger_type == "time_of_day":
                    if _matches_time_of_day(w.trigger_config or {}, now):
                        workflow_engine.start_run(
                            db=db,
                            workflow_id=w.id,
                            company_id=company.id,
                            triggered_by_user_id=None,
                            trigger_source="schedule",
                            trigger_context={"fired_at": now.isoformat()},
                        )
                        fired_tod += 1
                elif w.trigger_type == "time_after_event":
                    record_ids = _matches_time_after_event(db, w, company.id, now)
                    for rid in record_ids:
                        if _already_ran_for_record(db, w.id, rid):
                            continue
                        workflow_engine.start_run(
                            db=db,
                            workflow_id=w.id,
                            company_id=company.id,
                            triggered_by_user_id=None,
                            trigger_source="schedule",
                            trigger_context={"record": {"id": rid, "type": "funeral_case"}},
                        )
                        fired_tae += 1
                elif w.trigger_type == "scheduled":
                    # Phase 8b.5 — cron-based dispatch per tenant.
                    cron_expr = (w.trigger_config or {}).get("cron")
                    if not cron_expr:
                        # No cron defined — skip silently.
                        continue
                    tenant_tz = _resolve_tenant_tz(company.timezone)
                    try:
                        intended = _intended_scheduled_fire(
                            cron_expr, tenant_tz, now
                        )
                    except ValueError as exc:
                        # Malformed cron — log and skip this workflow
                        # (one bad cron doesn't stop the sweep).
                        logger.warning(
                            "Invalid cron expression for workflow %s "
                            "(tenant %s): %r — %s",
                            w.id, company.id, cron_expr, exc,
                        )
                        skipped_invalid_cron += 1
                        continue
                    if intended is None:
                        continue
                    if _already_fired_scheduled(
                        db,
                        workflow_id=w.id,
                        company_id=company.id,
                        intended_fire=intended,
                    ):
                        continue
                    workflow_engine.start_run(
                        db=db,
                        workflow_id=w.id,
                        company_id=company.id,
                        triggered_by_user_id=None,
                        trigger_source="schedule",
                        trigger_context={
                            "fired_at": now.isoformat(),
                            "intended_fire": intended.isoformat(),
                            "cron": cron_expr,
                        },
                    )
                    fired_sched += 1
    finally:
        db.close()
    return {
        "time_of_day_fired": fired_tod,
        "time_after_fired": fired_tae,
        "scheduled_fired": fired_sched,
        "scheduled_skipped_invalid_cron": skipped_invalid_cron,
    }
