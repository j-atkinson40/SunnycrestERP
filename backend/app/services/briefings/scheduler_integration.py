"""Phase 6 — per-user briefing sweep.

First per-user scheduled pattern on the platform. The global
`job_briefing_sweep()` wrapper in `scheduler.py` runs this every 15
minutes. For each (user, briefing_type) where the preference time
falls in [now - window, now] AND no briefing exists for today, the
sweep generates + delivers one.

Key design decisions:
  - Idempotency via DB: checks the `briefings` table's
    `(user_id, briefing_type, DATE(generated_at))` unique index. If a
    row exists for today → skip. No in-memory per-sweep dedup state.
  - Timezone: honors `Company.timezone` per tenant; falls back to
    `America/New_York` (same default as scheduler.py). This matters
    because a Pacific tenant's 7am is a different wall-clock than an
    Eastern tenant's.
  - Defensive: a single user's failure logs + continues. The sweep
    never dies mid-run; users still receive briefings the next sweep
    if transient failure.

The sweep is read-heavy — queries `users × briefing_type` per tenant
— but the window check is cheap (string comparison on HH:MM).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover — Python < 3.9 unsupported
    from backports.zoneinfo import ZoneInfo  # type: ignore

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.briefing import Briefing
from app.models.company import Company
from app.models.user import User
from app.services.briefings.data_sources import (
    collect_data_for_evening_briefing,
    collect_data_for_morning_briefing,
)
from app.services.briefings.delivery import deliver_briefing
from app.services.briefings.generator import (
    generate_evening_briefing,
    generate_morning_briefing,
)
from app.services.briefings.preferences import get_preferences
from app.services.briefings.types import BriefingType

logger = logging.getLogger(__name__)


DEFAULT_TZ = "America/New_York"
SWEEP_WINDOW_MINUTES = 15  # matches CronTrigger(minute="*/15")


# ── Public entry ────────────────────────────────────────────────────


def sweep_briefings_to_generate(db: Session) -> dict[str, Any]:
    """Run one sweep pass.

    Called by `scheduler.py::job_briefing_sweep` every 15 minutes.
    Returns a summary dict for `job_runs` auditing.
    """
    stats = {
        "users_scanned": 0,
        "briefings_generated": 0,
        "skipped_already_generated": 0,
        "skipped_outside_window": 0,
        "skipped_disabled": 0,
        "errors": 0,
    }

    now_utc = datetime.now(timezone.utc)

    # Fetch active users + their tenant's timezone in one pass.
    user_rows = (
        db.query(User, Company.timezone)
        .join(Company, User.company_id == Company.id)
        .filter(
            User.is_active.is_(True),
            Company.is_active.is_(True),
        )
        .all()
    )

    for user, tz_name in user_rows:
        stats["users_scanned"] += 1
        tz = _resolve_tz(tz_name)
        local_now = now_utc.astimezone(tz)

        # Briefings enabled tenant-wide?
        company = (
            db.query(Company).filter(Company.id == user.company_id).first()
        )
        if company and company.get_setting("briefings_enabled_tenant_wide", True) is False:
            stats["skipped_disabled"] += 1
            continue

        try:
            prefs = get_preferences(user)
        except Exception as e:
            logger.warning("prefs read failed for user %s: %s", user.id, e)
            stats["errors"] += 1
            continue

        for btype, enabled, target_time in (
            ("morning", prefs.morning_enabled, prefs.morning_delivery_time),
            ("evening", prefs.evening_enabled, prefs.evening_delivery_time),
        ):
            if not enabled:
                stats["skipped_disabled"] += 1
                continue

            if not _window_fired(local_now, target_time, SWEEP_WINDOW_MINUTES):
                stats["skipped_outside_window"] += 1
                continue

            if _already_generated_today(db, user.id, btype, local_now.date()):
                stats["skipped_already_generated"] += 1
                continue

            try:
                _generate_and_deliver(db, user, btype, prefs=prefs)
                stats["briefings_generated"] += 1
            except Exception as e:
                logger.exception(
                    "Sweep: briefing generation failed for user %s %s: %s",
                    user.id,
                    btype,
                    e,
                )
                stats["errors"] += 1

    logger.info("briefing sweep: %s", stats)
    return stats


# ── Helpers ─────────────────────────────────────────────────────────


def _resolve_tz(name: str | None):
    try:
        return ZoneInfo(name or DEFAULT_TZ)
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


def _window_fired(
    local_now: datetime, target_time: str, window_minutes: int
) -> bool:
    """True if `target_time` (HH:MM) fell in the trailing window.

    The test is on the local clock — a tenant's 7am is 7am wherever they
    are. Running every 15 min means the window length matches, so each
    scheduled moment fires exactly once per day.
    """
    try:
        hh, mm = target_time.split(":", 1)
        target_h = int(hh)
        target_m = int(mm)
    except Exception:
        return False
    today_local = local_now.date()
    target_dt = datetime(
        today_local.year,
        today_local.month,
        today_local.day,
        target_h,
        target_m,
        tzinfo=local_now.tzinfo,
    )
    window_start = local_now - timedelta(minutes=window_minutes)
    return window_start < target_dt <= local_now


def _already_generated_today(
    db: Session, user_id: str, briefing_type: BriefingType, local_date: date
) -> bool:
    """Check the daily-unique index defensively.

    We don't rely solely on the unique constraint — we pre-check so
    the sweep short-circuits cheaply (avoiding a failed insert +
    rollback for the overwhelming common case of idempotent re-runs).
    """
    row = (
        db.query(Briefing.id)
        .filter(
            Briefing.user_id == user_id,
            Briefing.briefing_type == briefing_type,
            func.date(Briefing.generated_at) == local_date,
        )
        .first()
    )
    return row is not None


def _generate_and_deliver(
    db: Session,
    user: User,
    briefing_type: BriefingType,
    *,
    prefs,
) -> Briefing:
    """Generate + persist + deliver one briefing."""
    if briefing_type == "morning":
        ctx = collect_data_for_morning_briefing(
            db, user, requested_sections=prefs.morning_sections
        )
        result = generate_morning_briefing(db, user, ctx)
        channels = prefs.morning_channels
    else:
        ctx = collect_data_for_evening_briefing(
            db, user, requested_sections=prefs.evening_sections
        )
        result = generate_evening_briefing(db, user, ctx)
        channels = prefs.evening_channels

    briefing = Briefing(
        company_id=user.company_id,
        user_id=user.id,
        briefing_type=briefing_type,
        generated_at=datetime.now(timezone.utc),
        delivery_channels=[],
        narrative_text=result.narrative_text,
        structured_sections=result.structured_sections.model_dump(),
        active_space_id=result.active_space_id,
        active_space_name=result.active_space_name,
        role_slug=result.role_slug,
        generation_context=result.generation_context,
        generation_duration_ms=result.generation_duration_ms,
        intelligence_cost_usd=result.intelligence_cost_usd,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )
    db.add(briefing)
    db.commit()
    db.refresh(briefing)

    # Dispatch per preferences. Failure logs + doesn't raise; the user
    # still has the briefing available in-app.
    try:
        deliver_briefing(db, briefing, channels=channels or ["in_app"])
    except Exception as e:
        logger.warning("deliver failed for briefing %s: %s", briefing.id, e)

    return briefing


__all__ = [
    "sweep_briefings_to_generate",
]
