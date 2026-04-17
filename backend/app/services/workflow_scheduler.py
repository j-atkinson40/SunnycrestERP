"""Workflow scheduler — time_of_day + time_after_event trigger support.

Phase W-1 implements a single APScheduler job that runs every 15 minutes
and checks two classes of workflows:

  time_of_day:       fires when current time matches config.time + days
  time_after_event:  fires for records where record_date + offset_days == today

Manual workflows are triggered on demand via the API and are not touched here.
APScheduler's dynamic per-workflow registration (Phase W-2) will replace the
polling approach with proper cron jobs per active workflow.
"""

from datetime import date, datetime, time, timezone, timedelta

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.company import Company
from app.models.workflow import Workflow, WorkflowEnrollment, WorkflowRun
from app.services import workflow_engine


DAY_ABBREV = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}


def _matches_time_of_day(trigger_config: dict, now: datetime) -> bool:
    """Check if now matches time_of_day config.

    Configs are coarse (15-min scheduler interval). A workflow with time "18:00"
    fires when now is in [18:00, 18:15). Days are 3-letter abbreviations.
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
    Returns a summary: {"time_of_day_fired": int, "time_after_fired": int}.
    """
    db = SessionLocal()
    fired_tod = 0
    fired_tae = 0
    now = datetime.now(timezone.utc)
    try:
        # Load all active time-based workflows
        workflows = (
            db.query(Workflow)
            .filter(
                Workflow.is_active == True,  # noqa: E712
                Workflow.trigger_type.in_(["time_of_day", "time_after_event"]),
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
    finally:
        db.close()
    return {"time_of_day_fired": fired_tod, "time_after_fired": fired_tae}
