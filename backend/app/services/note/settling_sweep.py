"""The settling sweep — one global cron, per-tenant local timing.

⚠️ THIS IS THE NOTE SURFACE'S FIRST SCHEDULED WRITER. Every other job this arc
added reads. A job that writes daily to every user's note has a different risk
profile from one that reads, and the deploy that registers it should be a deploy
someone chose.

──────────────────────────────────────────────────────────────────────────
WHY ONE CRON AND NOT ONE JOB PER TENANT

The briefings precedent (Phase 6): APScheduler registers ONE
`CronTrigger(minute="*/15")`, and per-tenant timing runs in application code
against `Company.timezone`. A trigger per tenant scales with tenant count and
puts scheduling state somewhere nobody looks.

⚠️ THE CONSEQUENCE IS THAT THE WINDOW IS EVALUATED ~96 TIMES A DAY PER TENANT,
and settling must happen once per user per day. That is not enforced by the
sweep being careful — it is enforced by `settle_note` being idempotent on
(note, fragment, instance, outcome), which is the anomaly arc's rule. The sweep
being wrong about the window costs a redundant call, not a duplicated summary.

──────────────────────────────────────────────────────────────────────────
TWO PASSES, AND THE SECOND ONE IS WHY THE NOTE IS APPEND-ONLY

  1. SETTLE — at the tenant's settling hour, settle the day that just ended.
  2. CATCH UP — on every firing, re-run settling for notes settled within the
     last 24 hours.

The second pass exists because the settled note is append-only rather than
immutable: an action that occurs after settling has run still belongs to the day
it occurred in. Re-running is safe precisely because settling is idempotent, and
a new event produces a NEW record rather than rewriting an old one.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.daily_note import DailyNote
from app.models.user import User
from app.services.note.settling import settle_note

logger = logging.getLogger(__name__)

DEFAULT_TZ = "America/New_York"
SWEEP_WINDOW_MINUTES = 15  # matches CronTrigger(minute="*/15")
#: Tenant setting, hour 0-23 in tenant-local time. Midnight by default.
SETTLING_HOUR_SETTING = "note_settling_hour"
DEFAULT_SETTLING_HOUR = 0
#: How far back the catch-up pass reaches for late events.
CATCH_UP_HOURS = 24


def _tz_for(company: Company) -> ZoneInfo:
    try:
        return ZoneInfo(company.timezone or DEFAULT_TZ)
    except Exception:
        logger.warning(
            "unknown timezone %r on company %s; falling back",
            company.timezone, company.id,
        )
        return ZoneInfo(DEFAULT_TZ)


def _settling_hour_for(company: Company) -> int:
    raw = None
    try:
        raw = company.settings.get(SETTLING_HOUR_SETTING)
    except Exception:
        raw = None
    try:
        hour = int(raw) if raw is not None else DEFAULT_SETTLING_HOUR
    except (TypeError, ValueError):
        logger.warning(
            "non-integer %s=%r on company %s; using default",
            SETTLING_HOUR_SETTING, raw, company.id,
        )
        return DEFAULT_SETTLING_HOUR
    return hour if 0 <= hour <= 23 else DEFAULT_SETTLING_HOUR


def hour_fell_in_window(
    local_now: datetime, *, hour: int, window_minutes: int = SWEEP_WINDOW_MINUTES
) -> bool:
    """Did the settling hour occur in the trailing window?

    ⚠️ A TRAILING WINDOW, NOT AN EQUALITY CHECK ON THE HOUR. A sweep that fires
    at :00, :15, :30, :45 and asks `local_now.hour == hour` would settle FOUR
    times an hour, and would miss the hour entirely if a firing were skipped.
    """
    target = local_now.replace(hour=hour, minute=0, second=0, microsecond=0)
    delta = (local_now - target).total_seconds()
    return 0 <= delta < window_minutes * 60


def sweep_notes_to_settle(db: Session) -> dict[str, Any]:
    """One sweep pass. Called every 15 minutes. Returns a summary for auditing."""
    stats: dict[str, Any] = {
        "tenants_scanned": 0,
        "tenants_in_window": 0,
        "notes_settled": 0,
        "records_written": 0,
        "records_already_present": 0,
        "catch_up_notes": 0,
        "unsettleable": 0,
        "errors": 0,
    }

    # ⚠️ ONLY TENANTS THAT HAVE NOTES. A tenant with no daily_notes has nothing
    # to settle, and scanning it costs two queries per firing — ~96 firings a
    # day, times every tenant that ever existed. Measured on the dev database:
    # scanning all active companies took 55s per sweep against 2,363 rows.
    # Scoping to tenants with notes is not an optimisation of the settling
    # logic; it is declining to ask a question whose answer is always "none".
    companies = db.execute(
        select(Company)
        .where(
            Company.is_active.is_(True),
            select(DailyNote.id)
            .where(DailyNote.company_id == Company.id)
            .exists(),
        )
    ).scalars().all()

    for company in companies:
        stats["tenants_scanned"] += 1
        try:
            tz = _tz_for(company)
            local_now = datetime.now(timezone.utc).astimezone(tz)
            hour = _settling_hour_for(company)

            notes: list[DailyNote] = []

            if hour_fell_in_window(local_now, hour=hour):
                stats["tenants_in_window"] += 1
                # The day that just ended in this tenant's local time.
                ended: date = (local_now - timedelta(days=1)).date()
                notes.extend(db.execute(
                    select(DailyNote).where(
                        DailyNote.company_id == company.id,
                        DailyNote.note_date == ended,
                    )
                ).scalars().all())

            # Catch-up: late events belong to the day they occurred in.
            cutoff = datetime.now(timezone.utc) - timedelta(hours=CATCH_UP_HOURS)
            recent = db.execute(
                select(DailyNote).where(
                    DailyNote.company_id == company.id,
                    DailyNote.settled_at.is_not(None),
                    DailyNote.settled_at >= cutoff,
                )
            ).scalars().all()
            seen = {n.id for n in notes}
            for n in recent:
                if n.id not in seen:
                    notes.append(n)
                    stats["catch_up_notes"] += 1

            for note in notes:
                user = db.execute(
                    select(User).where(User.id == note.user_id)
                ).scalars().first()
                if user is None:
                    continue
                res = settle_note(db, user=user, note=note)
                stats["notes_settled"] += 1
                stats["records_written"] += res.written
                stats["records_already_present"] += res.already_present
                stats["unsettleable"] += len(res.unsettleable)
                if res.unsettleable:
                    # ⚠️ LOGGED, NOT SWALLOWED. A resolution that happened and
                    # could not be written down is the one thing this job knows
                    # and nobody else does.
                    logger.warning(
                        "settling: %d unsettleable on note %s: %s",
                        len(res.unsettleable), note.id,
                        [u.reason for u in res.unsettleable],
                    )
            db.commit()
        except Exception:
            stats["errors"] += 1
            db.rollback()
            logger.exception("settling sweep failed for company %s", company.id)

    return stats
