"""The note shell — day identity, and the standing-set cascade.

    code role template  ->  tenant override  ->  user override

First match wins at the WHOLE-SET level, not per entry. A standing set is a
positional arrangement, and merging two arrangements produces a third that
neither author designed — the same reason `focus_compositions` resolves
first-match-wins rather than overlaying.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.daily_note import DailyNote
from app.models.standing_set_config import StandingSetConfig
from app.models.user import User
from app.services.note.counts import resolve_count
from app.services.note.registry import template_for, validate_entries
from app.services.note.types import (
    ResolvedStandingEntry,
    StandingEntry,
)

logger = logging.getLogger(__name__)

_DEFAULT_TZ = "America/New_York"


def tenant_today(db: Session, company_id: str) -> date:
    """The tenant's local calendar day.

    ⚠️ TENANT-LOCAL, NOT UTC. The same trap `time_of_day` workflow dispatch
    still has (CLAUDE.md §8b.5: "fires at UTC wall-clock, not tenant-local"),
    and the note's whole identity is the day, so getting it wrong here would
    mint the wrong note rather than merely fire something late.
    """
    from app.models.company import Company

    co = db.query(Company).filter(Company.id == company_id).first()
    tz = getattr(co, "timezone", None) or _DEFAULT_TZ
    try:
        return datetime.now(ZoneInfo(tz)).date()
    except Exception:
        logger.warning("unknown tenant timezone %r — falling back to %s", tz, _DEFAULT_TZ)
        return datetime.now(ZoneInfo(_DEFAULT_TZ)).date()


def get_or_create_note(db: Session, user: User, on_date: date | None = None) -> DailyNote:
    """One note per user per day. Idempotent.

    The unique constraint is the real guard — this runs on every page load and
    two tabs would otherwise race. On conflict we re-read rather than raise.
    """
    d = on_date or tenant_today(db, user.company_id)
    existing = (
        db.query(DailyNote)
        .filter(DailyNote.user_id == user.id, DailyNote.note_date == d)
        .first()
    )
    if existing:
        return existing

    now = datetime.now(timezone.utc)
    note = DailyNote(
        company_id=user.company_id,
        user_id=user.id,
        note_date=d,
        created_at=now,
        updated_at=now,
    )
    db.add(note)
    try:
        db.commit()
    except Exception:
        # Lost the race. The constraint did its job; read the winner.
        db.rollback()
        note = (
            db.query(DailyNote)
            .filter(DailyNote.user_id == user.id, DailyNote.note_date == d)
            .first()
        )
        if note is None:
            raise
    return note


# ── The cascade ──────────────────────────────────────────────────────


def _override_for(db: Session, company_id: str, user_id: str | None):
    q = db.query(StandingSetConfig).filter(StandingSetConfig.company_id == company_id)
    q = (
        q.filter(StandingSetConfig.user_id == user_id)
        if user_id
        else q.filter(StandingSetConfig.user_id.is_(None))
    )
    return q.first()


def resolve_standing_set(
    db: Session, user: User
) -> tuple[tuple[StandingEntry, ...], str]:
    """Resolve the standing set for this user. Returns (entries, tier).

    First match wins over the WHOLE set:

      1. user override   — a row with this user_id
      2. tenant override — a row with user_id NULL
      3. role template   — code, keyed (vertical, role_slug)

    ⚠️ AN ABSENT ROW AND AN EMPTY `entries` ARE DIFFERENT. No row means inherit
    the tier beneath. A row with `entries == []` means "show no standing set",
    and it wins — because a user who cleared their set meant to clear it, and
    silently restoring the role template would be the platform overriding a
    decision the user made.
    """
    row = _override_for(db, user.company_id, user.id)
    if row is not None:
        return tuple(StandingEntry.from_dict(e) for e in (row.entries or [])), "user"

    row = _override_for(db, user.company_id, None)
    if row is not None:
        return tuple(StandingEntry.from_dict(e) for e in (row.entries or [])), "tenant"

    from app.models.company import Company
    from app.models.role import Role

    co = db.query(Company).filter(Company.id == user.company_id).first()
    role = db.query(Role).filter(Role.id == user.role_id).first()
    vertical = getattr(co, "vertical", None) or getattr(co, "vertical_preset", None)
    return template_for(vertical, getattr(role, "slug", None)), "role"


def render_standing_set(db: Session, user: User) -> list[ResolvedStandingEntry]:
    """The standing set with counts resolved, in declared order.

    Order is the declaration's order and is never re-sorted. Entries do not
    reorder, do not appear and do not disappear — that positional stability is
    the register's entire value.
    """
    entries, tier = resolve_standing_set(db, user)
    return [
        ResolvedStandingEntry(
            entry=e,
            count=resolve_count(db, user, e.count_source),
            tier=tier,
        )
        for e in entries
    ]


def set_override(
    db: Session,
    *,
    company_id: str,
    entries: list[StandingEntry],
    user_id: str | None = None,
) -> StandingSetConfig:
    """Write a tenant or user override. Validates BEFORE writing.

    ⚠️ THE CAP IS ENFORCED HERE, AT CONFIGURATION TIME. Not at render, where a
    reader would silently see seven of eight and never know. `validate_entries`
    raises `StandingSetError` with a message naming the cap and why it exists.
    """
    validate_entries(entries)

    now = datetime.now(timezone.utc)
    row = _override_for(db, company_id, user_id)
    payload = [e.to_dict() for e in entries]
    if row is None:
        row = StandingSetConfig(
            company_id=company_id,
            user_id=user_id,
            entries=payload,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.entries = payload
        row.updated_at = now
    db.commit()
    return row
