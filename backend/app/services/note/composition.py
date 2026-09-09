"""The composition gate — truth is not sufficient for rendering.

A fragment can be true and still not worth saying. Per the session-2 dispatch:

  PROMPTS render whenever their condition holds. A prompt has a bounded
  decision and a declared end transition; a pending decision is always worth
  saying, and saying it again tomorrow is not repetition, it is the decision
  still being open.

  NON-PROMPTS render only on CHANGE against the previous note's state for that
  IDENTITY. Something crossed a line, appeared, or diverged. If the same true
  thing was said yesterday and nothing about it moved, it is not said again.

⚠️ NO PRIORITY SCORE AND NO TUNABLE THRESHOLD, DELIBERATELY. Every author sets
their own fragment's priority high — that is not cynicism, it is what it means
to have written the fragment. A threshold nobody can tune is the same erosion
one layer up, and a threshold everybody can tune is no threshold. The gate is a
predicate on the world, not a ranking of opinions.

⚠️ A QUIET DAY PRODUCES AN EMPTY PROSE REGION, PERMANENTLY. That is the
behaviour, not a degraded mode to be improved later. A surface that always has
something to say teaches people it is never worth reading.

──────────────────────────────────────────────────────────────────────────
WHY THIS IS ONLY IMPLEMENTABLE NOW

The change test is "the same IDENTITY, unchanged." Both halves are load-bearing:

  IDENTITY — `EmittedFragment.instance_key`, derived from the declared subject.
  If the key came from the evaluation, every day would produce a new identity,
  nothing would ever match yesterday, and the gate would pass everything while
  appearing to work. That failure is silent and looks like a busy world.

  UNCHANGED — a digest of the CONDITION INPUTS, never of the prose. Wording must
  be stable across refreshes; digesting the prose would make the gate depend on
  the synthesiser and re-render everything the day a prompt template changed.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.note_fragment_render import NoteFragmentRender
from app.services.fragments.emission import EmittedFragment

logger = logging.getLogger(__name__)

#: Why a fragment did or did not render. Carried out of the gate so an operator
#: review can ask "why is this not here?" and get an answer, and so the
#: positive controls can assert the REASON rather than only the absence.
GateVerdict = str
RENDER_PROMPT: GateVerdict = "render:prompt"
RENDER_FIRST_SIGHTING: GateVerdict = "render:first_sighting"
RENDER_CHANGED: GateVerdict = "render:changed"
WITHHELD_UNCHANGED: GateVerdict = "withheld:unchanged"


@dataclass(frozen=True)
class GateDecision:
    fragment: EmittedFragment
    verdict: GateVerdict
    change_digest: str
    #: The prior digest this was compared against, if there was one.
    prior_digest: str | None = None

    @property
    def renders(self) -> bool:
        return self.verdict.startswith("render:")


def change_digest(fragment: EmittedFragment) -> str:
    """A stable digest of what the change test compares.

    ⚠️ COMPUTED FROM `condition_inputs`, NOT FROM THE PROSE. The contract
    already requires conditions to declare enumerable, snapshottable inputs —
    declaration (2) — precisely so that "did anything move?" is answerable
    without re-reading a sentence. Digesting the prose would couple the gate to
    the synthesiser: a reworded template would read as the whole world changing.

    `sort_keys` because dict ordering is not part of the world's state, and a
    digest that changed when a key order changed would make the gate report
    movement that did not happen.
    """
    payload = json.dumps(
        dict(fragment.instance.condition_inputs), sort_keys=True, default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _prior_render(
    db: Session, *, user_id: str, fragment_id: str, instance_key: str,
    before: date,
) -> NoteFragmentRender | None:
    """The most recent render of this identity STRICTLY BEFORE today.

    ⚠️ STRICTLY BEFORE, and that bound is the whole correctness of a refresh.
    The note is re-composed on every view. If today's own record counted as
    "the previous note", the first view would record it and the second view
    would find it unchanged and withhold — a fragment that appears once and
    vanishes on reload, which reads as a bug and is worse than never showing it.
    """
    return db.execute(
        select(NoteFragmentRender)
        .where(
            NoteFragmentRender.user_id == user_id,
            NoteFragmentRender.fragment_id == fragment_id,
            NoteFragmentRender.instance_key == instance_key,
            NoteFragmentRender.note_date < datetime.combine(
                before, datetime.min.time(), tzinfo=timezone.utc
            ),
        )
        .order_by(NoteFragmentRender.note_date.desc())
        .limit(1)
    ).scalars().first()


def apply_gate(
    db: Session,
    *,
    user_id: str,
    note_date: date,
    fragments: Sequence[EmittedFragment],
) -> list[GateDecision]:
    """Decide which emitted fragments are worth saying today.

    Pure read. Recording what rendered is `record_renders`, called by the note
    service once the note is actually composed — separated so that evaluating
    the gate twice (a test, a diagnostic) does not itself change the answer.
    """
    out: list[GateDecision] = []
    for f in fragments:
        digest = change_digest(f)

        if f.declaration.kind == "prompt":
            out.append(GateDecision(f, RENDER_PROMPT, digest))
            continue

        prior = _prior_render(
            db, user_id=user_id, fragment_id=f.declaration.fragment_id,
            instance_key=f.instance_key, before=note_date,
        )
        if prior is None:
            out.append(GateDecision(f, RENDER_FIRST_SIGHTING, digest))
        elif prior.change_digest != digest:
            out.append(GateDecision(f, RENDER_CHANGED, digest, prior.change_digest))
        else:
            out.append(GateDecision(f, WITHHELD_UNCHANGED, digest, prior.change_digest))
    return out


def record_renders(
    db: Session,
    *,
    daily_note_id: str,
    company_id: str,
    user_id: str,
    note_date: date,
    decisions: Iterable[GateDecision],
) -> int:
    """Record what the note said, so tomorrow's gate has something to compare.

    ⚠️ ONLY WHAT RENDERED IS RECORDED. A withheld fragment must not refresh the
    stored digest: if it did, a value that drifted a little each day would never
    accumulate into a change, and the gate would go permanently quiet on exactly
    the slow movement it exists to notice.

    Idempotent against the unique constraint: re-composing the same note twice
    records once.
    """
    stamp = datetime.combine(note_date, datetime.min.time(), tzinfo=timezone.utc)
    written = 0
    for d in decisions:
        if not d.renders:
            continue
        existing = db.execute(
            select(NoteFragmentRender).where(
                NoteFragmentRender.daily_note_id == daily_note_id,
                NoteFragmentRender.fragment_id == d.fragment.declaration.fragment_id,
                NoteFragmentRender.instance_key == d.fragment.instance_key,
            )
        ).scalars().first()
        if existing is not None:
            continue
        db.add(NoteFragmentRender(
            daily_note_id=daily_note_id,
            company_id=company_id,
            user_id=user_id,
            note_date=stamp,
            fragment_id=d.fragment.declaration.fragment_id,
            instance_key=d.fragment.instance_key,
            kind=d.fragment.declaration.kind,
            change_digest=d.change_digest,
            change_inputs=json.dumps(
                dict(d.fragment.instance.condition_inputs), sort_keys=True, default=str
            )[:8000],
        ))
        written += 1
    db.flush()
    return written
