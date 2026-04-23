"""Dispatch schedule state machine.

Phase B Session 1. Owns the `delivery_schedules` aggregate table's
state machine:

  draft ←─── revert (on post-finalize delivery edit)
    │
    finalize (explicit OR auto at 1pm local)
    ↓
  finalized

**Lazy creation.** Rows only exist for dates a dispatcher has actually
touched (via Focus open, Monitor edit, or the auto-finalize sweep).
`get_schedule_state` returns None for untouched dates. `ensure_schedule`
creates a draft row if needed.

**Revert contract.** When `delivery_service.update_delivery` commits
changes to a delivery whose `requested_date` matches a finalized
schedule's date, the service calls `maybe_revert_on_delivery_edit`
which flips the schedule back to draft + stamps `last_reverted_at`
+ `last_revert_reason`. `finalized_at` + `finalized_by_user_id` are
preserved for audit — they narrate "finalized on X by Y, then
reverted on Z."

**Auto-finalize semantics.** The 1pm scheduler sweep targets
**tomorrow's schedule** (`schedule_date = local_today + 1 day`)
ONLY. Operational reality: by 1pm today, the dispatcher locks
tomorrow's work so drivers can plan their morning. Today's schedule
is already live at 1pm and never auto-finalized. Past-date drafts
are anomalies (dispatcher forgot to finalize a past day) and stay
draft — they surface via the Pulse composition's
`overdue_draft_schedules` anomaly widget, not silently auto-resolved.

Focus-open deferral: if any user has an active focus_session whose
focus_type is dispatch-flavored and whose layout_state references
**tomorrow's date**, the sweep skips (up to 15-min grace). Hard
cutoff 13:15 local — force-finalize regardless. All auto-finalizes
stamp `auto_finalized=True` + `finalized_by_user_id=NULL` so audit
can distinguish from user-driven finalizes.

**Cross-tenant isolation.** Every function filters by `company_id`.
Writes that span tenants raise on principle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.delivery import Delivery
from app.models.delivery_schedule import DeliverySchedule

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo  # noqa: F401 — used via getattr in tz resolution


logger = logging.getLogger(__name__)


# ── Constants ─────────────────────────────────────────────────────────

AUTO_FINALIZE_HOUR = 13  # 1 pm tenant-local
AUTO_FINALIZE_DEFERRED_HARD_CUTOFF_MINUTE = 15  # 1:15 pm hard-stop

VALID_STATES = ("draft", "finalized")
VALID_HOLE_DUG = (None, "unknown", "yes", "no")


# ── Errors ─────────────────────────────────────────────────────────────


class ScheduleStateError(Exception):
    """Invalid state transition or guard violation."""


class UnknownScheduleError(ScheduleStateError):
    """Attempted to mutate a schedule that doesn't exist."""


# ── Read path ──────────────────────────────────────────────────────────


def get_schedule_state(
    db: Session,
    company_id: str,
    schedule_date: date,
) -> DeliverySchedule | None:
    """Return the schedule row for (company_id, schedule_date) or None
    if no row has been created. Lazy — never creates."""
    return (
        db.query(DeliverySchedule)
        .filter(
            DeliverySchedule.company_id == company_id,
            DeliverySchedule.schedule_date == schedule_date,
        )
        .first()
    )


def get_schedules_for_range(
    db: Session,
    company_id: str,
    start_date: date,
    end_date: date,
) -> list[DeliverySchedule]:
    """Return all existing schedule rows for dates in [start_date,
    end_date] inclusive. Sorted ascending by schedule_date. Doesn't
    create rows for dates that haven't been touched."""
    if start_date > end_date:
        return []
    return (
        db.query(DeliverySchedule)
        .filter(
            DeliverySchedule.company_id == company_id,
            DeliverySchedule.schedule_date >= start_date,
            DeliverySchedule.schedule_date <= end_date,
        )
        .order_by(DeliverySchedule.schedule_date.asc())
        .all()
    )


# ── Mutations — state machine ──────────────────────────────────────────


def ensure_schedule(
    db: Session,
    company_id: str,
    schedule_date: date,
    *,
    commit: bool = True,
) -> DeliverySchedule:
    """Get the schedule row for (company_id, date), creating a fresh
    draft row if it doesn't exist. Idempotent."""
    existing = get_schedule_state(db, company_id, schedule_date)
    if existing:
        return existing

    row = DeliverySchedule(
        company_id=company_id,
        schedule_date=schedule_date,
        state="draft",
        auto_finalized=False,
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row


def finalize_schedule(
    db: Session,
    company_id: str,
    schedule_date: date,
    *,
    user_id: str | None,
    auto: bool = False,
    commit: bool = True,
) -> DeliverySchedule:
    """Transition to finalized state.

    `user_id` may be None iff `auto=True` (the 1pm job's caller
    context). Explicit user finalizes must pass a non-null `user_id`.
    Idempotent — calling on an already-finalized row is a no-op but
    does NOT raise (enables "stamp over stale state" semantics the
    scheduler needs).
    """
    if not auto and user_id is None:
        raise ScheduleStateError(
            "Explicit finalize requires a user_id. Pass auto=True for scheduler calls."
        )

    row = ensure_schedule(db, company_id, schedule_date, commit=False)

    # Idempotent: already finalized is a no-op.
    if row.state == "finalized":
        if commit:
            db.commit()
            db.refresh(row)
        return row

    row.state = "finalized"
    row.finalized_at = datetime.now(timezone.utc)
    row.finalized_by_user_id = user_id
    row.auto_finalized = bool(auto)
    row.updated_at = datetime.now(timezone.utc)

    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()

    logger.info(
        "delivery_schedule.finalize company_id=%s schedule_date=%s user_id=%s auto=%s",
        company_id,
        schedule_date,
        user_id,
        auto,
    )
    return row


def revert_to_draft(
    db: Session,
    company_id: str,
    schedule_date: date,
    *,
    reason: str | None = None,
    commit: bool = True,
) -> DeliverySchedule | None:
    """Transition finalized → draft. Preserves `finalized_at` +
    `finalized_by_user_id` for audit.

    Returns None if no schedule row exists (nothing to revert).
    Returns the row unchanged if already draft (idempotent).
    """
    row = get_schedule_state(db, company_id, schedule_date)
    if row is None:
        return None

    if row.state == "draft":
        return row

    row.state = "draft"
    row.last_reverted_at = datetime.now(timezone.utc)
    row.last_revert_reason = (reason[:200] if reason else None)
    # NOT clearing finalized_at / finalized_by_user_id — audit trail.
    row.updated_at = datetime.now(timezone.utc)

    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()

    logger.info(
        "delivery_schedule.revert company_id=%s schedule_date=%s reason=%r",
        company_id,
        schedule_date,
        reason,
    )
    return row


def maybe_revert_on_delivery_edit(
    db: Session,
    delivery: Delivery,
    *,
    reason: str | None = None,
    commit: bool = True,
) -> DeliverySchedule | None:
    """Called by `delivery_service.update_delivery` after a delivery
    mutation commits. If the delivery has a `requested_date` and the
    matching schedule row is finalized, revert it.

    Returns the reverted schedule row, the unchanged row if it was
    already draft, or None if no schedule row exists.
    """
    if delivery.requested_date is None:
        return None
    row = get_schedule_state(db, delivery.company_id, delivery.requested_date)
    if row is None or row.state == "draft":
        return row
    effective_reason = reason or f"Delivery {delivery.id[:8]} edited after finalize"
    return revert_to_draft(
        db,
        delivery.company_id,
        delivery.requested_date,
        reason=effective_reason,
        commit=commit,
    )


# ── Hole-dug quick-edit ────────────────────────────────────────────────


def set_hole_dug_status(
    db: Session,
    delivery: Delivery,
    status: str | None,
    *,
    revert_schedule: bool = True,
    commit: bool = True,
) -> Delivery:
    """Update `Delivery.hole_dug_status`. Validates the enum + triggers
    schedule revert if the delivery's requested_date is on a finalized
    schedule.

    `status` values: `None` (clear — back to initial state), or one
    of `"unknown"`, `"yes"`, `"no"`.
    """
    if status not in VALID_HOLE_DUG:
        raise ValueError(f"Invalid hole_dug_status: {status!r}. Valid: {VALID_HOLE_DUG}")

    delivery.hole_dug_status = status
    delivery.modified_at = datetime.now(timezone.utc)

    if revert_schedule and delivery.requested_date is not None:
        row = get_schedule_state(db, delivery.company_id, delivery.requested_date)
        if row is not None and row.state == "finalized":
            revert_to_draft(
                db,
                delivery.company_id,
                delivery.requested_date,
                reason=f"Hole-dug status changed on delivery {delivery.id[:8]}",
                commit=False,
            )

    if commit:
        db.commit()
        db.refresh(delivery)
    else:
        db.flush()
    return delivery


# ── Auto-finalize sweep ────────────────────────────────────────────────


@dataclass
class AutoFinalizeResult:
    """Summary of one company's auto-finalize pass."""
    company_id: str
    tenant_local_now: datetime
    considered_dates: list[date]
    finalized_dates: list[date]
    deferred_dates: list[date]
    skipped_dates: list[date]


def _get_tenant_timezone(company: Company):
    """Resolve a tenant's IANA timezone; fall back to America/New_York.

    Matches the precedent set in briefings scheduler_integration — see
    CLAUDE.md §10 "Per-user Scheduled Jobs."
    """
    from zoneinfo import ZoneInfo
    tz_name = getattr(company, "timezone", None) or "America/New_York"
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("America/New_York")


def _has_active_focus_for_date(
    db: Session,
    company_id: str,
    schedule_date: date,
) -> bool:
    """Check if any user in the company has an active scheduling Focus
    session whose layout_state references `schedule_date`.

    Focus-open deferral per brief: the auto-finalize caller passes
    TOMORROW's date (since that's what the 1pm sweep targets). If a
    dispatcher has the Scheduling Focus open composing tomorrow's
    schedule at the 1pm fire time, defer finalization up to 15
    minutes so they can finalize explicitly. Hard cutoff at 1:15pm —
    the caller enforces that bound via `in_grace_window`.

    Returns False if focus_sessions table or infrastructure isn't
    available (degrade gracefully — never block auto-finalize on a
    read-path error).
    """
    try:
        from app.models.focus_session import FocusSession
    except Exception:
        return False

    # Focus type convention: scheduling Focus carries a focus_type
    # that contains "schedul" (e.g. "scheduling", "scheduling_focus").
    # Loose match to avoid hardcoding a specific focus_id.
    iso_date = schedule_date.isoformat()
    q = (
        db.query(FocusSession)
        .filter(
            FocusSession.company_id == company_id,
            FocusSession.is_active.is_(True),
            FocusSession.focus_type.ilike("%schedul%"),
        )
    )
    try:
        rows = q.all()
    except Exception:
        return False

    for row in rows:
        layout = getattr(row, "layout_state", None) or {}
        # Accept a few shapes the Scheduling Focus might store the
        # target date in. Conservative match — if ANY session has
        # today's date in its layout_state, defer.
        candidates = [
            layout.get("schedule_date"),
            layout.get("day_being_scheduled"),
            (layout.get("core_layout") or {}).get("schedule_date"),
        ]
        for c in candidates:
            if c == iso_date:
                return True
    return False


def auto_finalize_pending_schedules(
    db: Session,
    *,
    now_utc: datetime | None = None,
    company_ids: list[str] | None = None,
) -> list[AutoFinalizeResult]:
    """Sweep tenants; finalize TOMORROW's draft schedule when tenant-
    local time has reached the 1pm auto-finalize window.

    Called by the scheduler every 15 min starting at 13:00 tenant-
    local (the cron in `app/scheduler.py` runs in the scheduler's
    timezone = America/New_York by default; per-tenant tz resolution
    still happens here for multi-tz tenants).

    Per-tenant logic:
      1. Resolve tenant tz + current tenant-local datetime.
      2. If tenant-local time is before 13:00 → skip this tenant
         this tick.
      3. Find exactly ONE candidate: the draft schedule row for
         `local_today + 1 day` (tomorrow). Past-date drafts are
         NEVER auto-finalized — they stay draft and surface via the
         `overdue_draft_schedules` anomaly widget. Today's schedule
         is NEVER auto-finalized — it's already live work.
      4. For the tomorrow candidate:
         - If tenant-local time is between 13:00 and 13:14:59 AND
           a user has Focus open for tomorrow's date → defer.
         - Else → finalize with auto=True, user_id=None.
      5. Collect results for logging / observability.

    `company_ids`: optional scoping for testing — if provided, only
    those tenants are considered. Production caller (the scheduler
    job) passes None to sweep every active tenant.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    results: list[AutoFinalizeResult] = []
    company_query = db.query(Company).filter(Company.is_active.is_(True))
    if company_ids is not None:
        company_query = company_query.filter(Company.id.in_(company_ids))
    companies = company_query.all()

    for company in companies:
        tz = _get_tenant_timezone(company)
        local_now = now_utc.astimezone(tz)

        # Only consider tenants whose local time has reached 13:00.
        if local_now.hour < AUTO_FINALIZE_HOUR:
            continue

        local_today = local_now.date()
        local_tomorrow = local_today + timedelta(days=1)

        # Exactly one candidate per tenant per tick: tomorrow's draft
        # schedule row. No past-slippage sweep — past drafts are
        # dispatcher-anomaly surface, not auto-resolved.
        draft_row = (
            db.query(DeliverySchedule)
            .filter(
                DeliverySchedule.company_id == company.id,
                DeliverySchedule.state == "draft",
                DeliverySchedule.schedule_date == local_tomorrow,
            )
            .first()
        )

        considered: list[date] = [draft_row.schedule_date] if draft_row else []
        finalized: list[date] = []
        deferred: list[date] = []
        skipped: list[date] = []

        # Hard-cutoff window: between 13:00 and 13:14:59 inclusive, we
        # allow deferral. At 13:15+ local, never defer — just finalize.
        in_grace_window = (
            local_now.hour == AUTO_FINALIZE_HOUR
            and local_now.minute < AUTO_FINALIZE_DEFERRED_HARD_CUTOFF_MINUTE
        )

        if draft_row is not None:
            # Focus-open deferral: if a dispatcher has the Scheduling
            # Focus open with TOMORROW's date in layout_state, defer
            # finalization within the 13:00-13:14:59 grace window.
            if (
                in_grace_window
                and _has_active_focus_for_date(db, company.id, local_tomorrow)
            ):
                deferred.append(draft_row.schedule_date)
            else:
                try:
                    finalize_schedule(
                        db,
                        company.id,
                        draft_row.schedule_date,
                        user_id=None,
                        auto=True,
                        commit=False,
                    )
                    finalized.append(draft_row.schedule_date)
                except Exception as exc:
                    logger.exception(
                        "auto_finalize failed company_id=%s date=%s: %s",
                        company.id,
                        draft_row.schedule_date,
                        exc,
                    )
                    skipped.append(draft_row.schedule_date)

        # One commit per tenant — keep the transaction scoped.
        try:
            db.commit()
        except Exception:
            logger.exception(
                "auto_finalize commit failed company_id=%s", company.id
            )
            db.rollback()

        results.append(AutoFinalizeResult(
            company_id=company.id,
            tenant_local_now=local_now,
            considered_dates=considered,
            finalized_dates=finalized,
            deferred_dates=deferred,
            skipped_dates=skipped,
        ))

    return results


# ── Summary helper for API responses ───────────────────────────────────


def schedule_to_dict(row: DeliverySchedule) -> dict:
    """Serialize a DeliverySchedule for API responses. Stable shape."""
    return {
        "id": row.id,
        "company_id": row.company_id,
        "schedule_date": row.schedule_date.isoformat(),
        "state": row.state,
        "finalized_at": row.finalized_at.isoformat() if row.finalized_at else None,
        "finalized_by_user_id": row.finalized_by_user_id,
        "auto_finalized": row.auto_finalized,
        "last_reverted_at": (
            row.last_reverted_at.isoformat() if row.last_reverted_at else None
        ),
        "last_revert_reason": row.last_revert_reason,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }
