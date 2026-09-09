"""Deferral — a prompt's only exit besides its end transition occurring.

Per DECISIONS 2026-09-04 ("Prompts leave the note by resolution or dated
deferral, never silently"). A prompt has NO dismiss. Non-prompts keep theirs,
and that path is not touched here.

──────────────────────────────────────────────────────────────────────────
THE FOUR THINGS THIS OWES

  1. A NAMED DATE. Presets plus a picker, no finer granularity — enforced by
     `deferred_until` being a DATE column rather than by validating a timestamp.

  2. A RECORD ON THE LIVE NOTE. The row carries `daily_note_id`, so the note the
     deferral was made from holds it. The live surface consumes it ("deferred
     three times"); settling reads the same rows when it exists. Storage with a
     live consumer, not substrate waiting for one.

  3. A SNAPSHOT. `condition_digest` over the same `condition_inputs` the
     composition gate digests, taken at the moment of deferral.

  4. A WAKE ON DIVERGENCE. The reader deferred a decision with a KNOWN SHAPE. If
     the shape changes, the deferral was made about a different question and the
     prompt comes back regardless of its date.

──────────────────────────────────────────────────────────────────────────
⚠️ THE DIGEST IS NOT RE-IMPLEMENTED HERE

`composition.change_digest` computes it. Two digests over the same inputs must
be the same value or the wake is nonsense — a second implementation that sorted
keys differently, or stringified a date differently, would wake every deferral
on every view and look exactly like a world that keeps moving.

⚠️ RE-DEFERRAL IS COUNTED, NOT ESCALATED

`deferral_count` returns a number and nothing here decides what it means.
Someone pushing the same thing repeatedly is usually blocked on something else,
and colouring it red states a judgement the surface has not earned.
"""

from __future__ import annotations

import calendar
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.note_fragment_deferral import NoteFragmentDeferral
from app.services.fragments.emission import EmittedFragment
from app.services.note.composition import change_digest

logger = logging.getLogger(__name__)


class DeferralError(ValueError):
    """A deferral was refused. Raised at the boundary, surfaced as 4xx."""


#: The affordances. `date` is the picker; the rest resolve to a date from today.
#: ⚠️ A CLOSED SET, and `custom` is not among them — every deferral names a date
#: that one of these produced, so "what did people choose" is answerable without
#: inferring intent from the dates themselves.
PRESETS: tuple[str, ...] = ("tomorrow", "next_week", "next_month", "date")


def _add_months(d: date, months: int) -> date:
    """Calendar month, clamped to the last valid day.

    ⚠️ NOT `+30 days`. "Next month" on the 31st means the last day of a 30-day
    month, not the 30th of a 31-day one, and a reader who picked "next month"
    and got a date in the same month would be right to distrust the control.
    """
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def resolve_preset(preset: str, *, today: date, explicit: date | None = None) -> date:
    """Turn an affordance into the date it names."""
    if preset not in PRESETS:
        raise DeferralError(
            f"unknown preset {preset!r}; expected one of {list(PRESETS)}"
        )
    if preset == "date":
        if explicit is None:
            raise DeferralError("preset 'date' requires an explicit date")
        return explicit
    if preset == "tomorrow":
        return date.fromordinal(today.toordinal() + 1)
    if preset == "next_week":
        return date.fromordinal(today.toordinal() + 7)
    return _add_months(today, 1)


@dataclass(frozen=True)
class ActiveDeferral:
    """The deferral currently suppressing an identity, if any."""

    row: NoteFragmentDeferral
    #: How many times this identity has been deferred, including this one.
    count: int

    @property
    def deferred_until(self) -> date:
        return self.row.deferred_until

    def diverged(self, fragment: EmittedFragment) -> bool:
        """Has the question changed shape since it was deferred?"""
        return change_digest(fragment) != self.row.condition_digest


def deferral_count(
    db: Session, *, user_id: str, fragment_id: str, instance_key: str
) -> int:
    """How many times this identity has been deferred. All acts, ever.

    ⚠️ INCLUDES WOKEN AND EXPIRED ONES. "Deferred three times" is a fact about
    the reader's history with this prompt, not about which deferral is live —
    and a count that reset whenever one lapsed would hide exactly the pattern
    the count exists to reveal.
    """
    return int(
        db.execute(
            select(func.count())
            .select_from(NoteFragmentDeferral)
            .where(
                NoteFragmentDeferral.user_id == user_id,
                NoteFragmentDeferral.fragment_id == fragment_id,
                NoteFragmentDeferral.instance_key == instance_key,
            )
        ).scalar_one()
    )


def active_deferral(
    db: Session,
    *,
    user_id: str,
    fragment_id: str,
    instance_key: str,
    today: date,
) -> ActiveDeferral | None:
    """The deferral suppressing this identity today, or None.

    Live means: the most recent act, not yet woken, whose named date has not
    arrived. `deferred_until` is the day the prompt comes BACK, so a deferral
    to tomorrow suppresses today and not tomorrow.
    """
    row = db.execute(
        select(NoteFragmentDeferral)
        .where(
            NoteFragmentDeferral.user_id == user_id,
            NoteFragmentDeferral.fragment_id == fragment_id,
            NoteFragmentDeferral.instance_key == instance_key,
        )
        .order_by(NoteFragmentDeferral.deferred_at.desc())
        .limit(1)
    ).scalars().first()

    if row is None:
        return None
    if row.woken_at is not None:
        return None
    if row.deferred_until <= today:
        return None

    return ActiveDeferral(
        row=row,
        count=deferral_count(
            db, user_id=user_id, fragment_id=fragment_id,
            instance_key=instance_key,
        ),
    )


def defer(
    db: Session,
    *,
    company_id: str,
    user_id: str,
    daily_note_id: str,
    fragment: EmittedFragment,
    preset: str,
    today: date,
    explicit_date: date | None = None,
) -> NoteFragmentDeferral:
    """Record one act of deferring a prompt. Caller commits.

    ⚠️ PROMPTS ONLY. A non-prompt exits by dismiss, which is a different path
    and not this one. Deferring a non-prompt is refused rather than silently
    accepted, because a fragment with no end transition has nothing to come
    back FOR.
    """
    if fragment.declaration.kind != "prompt":
        raise DeferralError(
            f"{fragment.declaration.fragment_id} is a "
            f"{fragment.declaration.kind}; only prompts defer. Non-prompts "
            "exit by dismiss."
        )

    until = resolve_preset(preset, today=today, explicit=explicit_date)
    if until <= today:
        raise DeferralError(
            f"deferred_until {until.isoformat()} is not after {today.isoformat()} "
            "— a deferral that has already arrived suppresses nothing"
        )

    row = NoteFragmentDeferral(
        company_id=company_id,
        user_id=user_id,
        fragment_id=fragment.declaration.fragment_id,
        instance_key=fragment.instance_key,
        daily_note_id=daily_note_id,
        deferred_until=until,
        preset=preset,
        condition_digest=change_digest(fragment),
        condition_inputs=json.dumps(
            dict(fragment.instance.condition_inputs), sort_keys=True, default=str
        ),
    )
    db.add(row)
    return row


def mark_woken(db: Session, row: NoteFragmentDeferral) -> None:
    """Spend a deferral that divergence woke. Caller commits.

    The row stays as the record that the deferral happened; `woken_at` stops it
    suppressing. Deleting it would erase an act from the history that
    `deferral_count` reads.
    """
    if row.woken_at is None:
        row.woken_at = datetime.now(timezone.utc)
