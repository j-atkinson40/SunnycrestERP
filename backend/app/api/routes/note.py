"""Note surface — session 1 read endpoint.

⚠️ THIS DOES NOT SERVE /home. Pulse still does, until session 5 retires it.
The note lives at its own route so the two can coexist without either
pretending to be the other.
"""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.note_settled_record import NoteSettledRecord
from app.models.user import User
from app.services.fragments.emission import emit_for_user
from app.services.note import get_or_create_note, render_standing_set
from app.services.note.composition import apply_gate, record_renders
from app.services.note.spans import serialise_spans
from app.services.note.deferral import (
    PRESETS,
    DeferralError,
    defer,
    deferral_count,
    until_label,
)

def _spans(fragment) -> list[dict]:
    """Prose and the deferral record, through the one serialiser.

    Settled records use the same function directly — see
    `app/services/note/spans.py` for why there is only one.
    """
    return serialise_spans(fragment.instance.payload.spans)


router = APIRouter()


@router.get("/today")
def get_today_note(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Today's note: identity, the standing set, and the composed prose.

    `prose` stays a list in every case, including the empty one. An absent key
    would let a client treat "not built yet" and "nothing to say today" as the
    same thing, and a quiet day producing an empty prose region is correct
    permanent behaviour rather than a gap to hide.

    ⚠️ THIS GET WRITES, DELIBERATELY. `get_or_create_note` already did; session 2
    adds `record_renders`, because the composition gate's whole mechanism is
    comparing today against what the previous note SAID, and nothing else is in
    a position to record that. Recording is idempotent — the unique constraint
    on (note, fragment, identity) plus an existence check means re-viewing the
    note records once — and only fragments that actually RENDERED are written,
    so a withheld one never refreshes its stored digest.
    """
    note = get_or_create_note(db, current_user)
    standing = render_standing_set(db, current_user)

    # (1) emit -> (2) gate -> (3) record. The gate is a pure read and recording
    # is separate, so evaluating twice does not change the answer.
    emitted = emit_for_user(db, user=current_user)
    decisions = apply_gate(
        db, user_id=current_user.id, note_date=note.note_date, fragments=emitted
    )
    rendering = [d for d in decisions if d.renders]
    record_renders(
        db,
        daily_note_id=note.id,
        company_id=current_user.company_id,
        user_id=current_user.id,
        note_date=note.note_date,
        decisions=decisions,
    )
    db.commit()

    return {
        "note_id": note.id,
        "note_date": note.note_date.isoformat(),
        "subject_id": note.subject_id,
        "settled_at": note.settled_at.isoformat() if note.settled_at else None,
        "standing_set": [
            {
                "entry_id": r.entry.entry_id,
                "label": r.entry.label,
                "target_surface": r.entry.target_surface,
                "target_key": r.entry.target_key,
                # None means "no count", NEVER zero. Zero is a claim.
                "count": r.count,
                # ⚠️ Distinguishes a deliberate blank from a silent failure.
                # Both render without a number, and an operator reviewing the
                # surface must still be able to tell them apart — otherwise
                # three absent counts and three broken ones look identical.
                "count_state": r.state,
                "tier": r.tier,
                # ⚠️ Declared, not wired — and the client must not invent a
                # click for it.
                #
                # A first pass wired this to a PEEK and was reverted
                # (2026-09-09). Operator review of the running surface found
                # the peek opened on cursor travel, pinned itself on pointer
                # entry, and at 360px could not show a day's schedule anyway —
                # so it summarised and the user clicked through regardless.
                # Two steps to reach what one step reaches directly.
                #
                # The ruling: a standing line opens a FOCUS on click,
                # read-only without edit permission. This flag flips when that
                # target exists, and the gate will key on whether the entry's
                # target HAS a Focus — not on `peek_inline`, which was the
                # reverted design's gate.
                "openable": False,
            }
            for r in standing
        ],
        # ⚠️ SPANS, NOT A STRING. The three text states are carried
        # structurally so the renderer never has to find a substring to mark:
        # a label occurring twice would be marked in the wrong place and
        # nothing would look wrong. `text` is the concatenation, sent so a
        # client that ignores spans still reads exactly what the spans say.
        "prose": [
            {
                "fragment_id": d.fragment.declaration.fragment_id,
                "instance_key": d.fragment.instance_key,
                "kind": d.fragment.declaration.kind,
                "title": d.fragment.instance.payload.title,
                "text": d.fragment.instance.payload.synthesized_text,
                "spans": _spans(d.fragment),
                "target_surface": d.fragment.declaration.target_surface,
                "target_key": d.fragment.declaration.target_key,
                # Session 3 wires opening; declared, not wired, exactly as the
                # standing set's targets are.
                "openable": False,
                # Why this is here. Carried so an operator review can ask "why
                # is this not showing?" and get an answer from the surface
                # rather than from the logs.
                "gate": d.verdict,
                # ⚠️ PROMPTS DEFER; NON-PROMPTS DISMISS. Carried explicitly so
                # the client renders one affordance or the other rather than
                # inferring which from `kind` and getting it wrong the day a
                # third kind exists.
                "deferrable": d.fragment.declaration.kind == "prompt",
                # How many times this reader has deferred THIS prompt, ever —
                # including deferrals that lapsed or were woken. Stated
                # plainly. Someone pushing the same thing repeatedly is usually
                # blocked on something else, and that is worth seeing rather
                # than colouring.
                "deferred_count": (
                    deferral_count(
                        db,
                        user_id=current_user.id,
                        fragment_id=d.fragment.declaration.fragment_id,
                        instance_key=d.fragment.instance_key,
                    )
                    if d.fragment.declaration.kind == "prompt"
                    else 0
                ),
            }
            for d in rendering
        ],
        # ⚠️ What the gate WITHHELD, and why. Not rendered as prose — it is the
        # answer to "should there be more here?", which on a quiet day is the
        # question an operator will actually have.
        # ⚠️ THE SETTLED RECORD IS SERVED, OR SETTLING IS INVISIBLE.
        #
        # Session 2 shipped a complete substrate that `GET /note/today` never
        # called, and every test passed while the surface showed nothing. The
        # settled note is the same shape of risk: a job that writes records
        # nobody reads is indistinguishable from a job that does not run.
        #
        # Frozen text and frozen spans are served as stored — NOT re-rendered.
        # Re-serialising the spans would resolve them against today's world,
        # which is a link quietly showing today's data under yesterday's
        # sentence.
        "settled": [
            {
                "fragment_id": r.fragment_id,
                "instance_key": r.instance_key,
                "outcome_key": r.outcome_key,
                "count": r.count,
                "text": r.text,
                "spans": json.loads(r.spans) if r.spans else [],
                # The visible timestamp. The settled note is append-only, so a
                # reader can see a record arrived after the rest of the day.
                "occurred_through": r.occurred_through.isoformat(),
            }
            for r in db.execute(
                select(NoteSettledRecord)
                .where(NoteSettledRecord.daily_note_id == note.id)
                .order_by(NoteSettledRecord.occurred_through)
            ).scalars().all()
        ],
        "withheld": [
            {
                "fragment_id": d.fragment.declaration.fragment_id,
                "instance_key": d.fragment.instance_key,
                "gate": d.verdict,
                # ⚠️ THE RECORD CARRIES ITS SUBJECT.
                #
                # Operator review, 2026-09-09: "Deferred until 2026-09-10" was
                # rendered alone, with no indication of WHAT was deferred. A
                # record of an act with no object is unreadable the next day and
                # worse than nothing on a settled note read next week — and with
                # two fragments rendering as adjacent lines, a floating record
                # also reads as belonging to whichever prompt happens to sit
                # above it.
                #
                # So the deferred fragment keeps its sentence and the record
                # appends to it. The prompt is still WITHHELD — this is not a
                # re-render, it is the note saying what the reader chose to
                # postpone, about whom.
                "title": d.fragment.instance.payload.title,
                "text": d.fragment.instance.payload.synthesized_text,
                "spans": _spans(d.fragment),
                # A deferred prompt says WHEN it comes back. Without this,
                # "withheld:deferred" is indistinguishable from gone.
                "deferred_until": (
                    d.deferral.deferred_until.isoformat()
                    if d.deferral is not None
                    else None
                ),
                # How a person says that date TODAY. Re-derived per read rather
                # than stored, because "next week" stops being true on Thursday.
                "deferred_until_label": (
                    until_label(d.deferral.deferred_until, today=note.note_date)
                    if d.deferral is not None
                    else None
                ),
                "deferred_count": (
                    d.deferral.count if d.deferral is not None else 0
                ),
            }
            for d in decisions
            if not d.renders
        ],
    }


class DeferRequest(BaseModel):
    fragment_id: str
    instance_key: str
    preset: str
    #: Required when `preset == "date"`, ignored otherwise.
    deferred_until: date | None = None


@router.post("/defer")
def defer_prompt(
    body: DeferRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Defer a prompt to a named date. The note surface is its own actor.

    ⚠️ THE FRAGMENT IS RE-EMITTED RATHER THAN TRUSTED FROM THE REQUEST. The
    snapshot has to be of the condition inputs AS THEY ARE, and a client-supplied
    digest would let a stale tab defer against a shape that no longer holds —
    the deferral would then never wake, because it was born already diverged.

    A prompt whose condition no longer holds is not deferrable: there is nothing
    to come back. That is a 409, not a 404 — the fragment type exists, this
    instance of it does not.
    """
    note = get_or_create_note(db, current_user)
    emitted = emit_for_user(db, user=current_user)

    match = next(
        (
            f for f in emitted
            if f.declaration.fragment_id == body.fragment_id
            and f.instance_key == body.instance_key
        ),
        None,
    )
    if match is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{body.fragment_id} / {body.instance_key} is not currently "
                "emitted — its condition no longer holds, so there is nothing "
                "to defer."
            ),
        )

    try:
        row = defer(
            db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            daily_note_id=note.id,
            fragment=match,
            preset=body.preset,
            today=note.note_date,
            explicit_date=body.deferred_until,
        )
    except DeferralError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    return {
        "deferral_id": row.id,
        "fragment_id": row.fragment_id,
        "instance_key": row.instance_key,
        "deferred_until": row.deferred_until.isoformat(),
        "preset": row.preset,
        "deferred_count": deferral_count(
            db,
            user_id=current_user.id,
            fragment_id=row.fragment_id,
            instance_key=row.instance_key,
        ),
        "presets": list(PRESETS),
    }
