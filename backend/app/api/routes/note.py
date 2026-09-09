"""Note surface — session 1 read endpoint.

⚠️ THIS DOES NOT SERVE /home. Pulse still does, until session 5 retires it.
The note lives at its own route so the two can coexist without either
pretending to be the other.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.fragments.emission import emit_for_user
from app.services.note import get_or_create_note, render_standing_set
from app.services.note.composition import apply_gate, record_renders

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
                # Session 3 wires opening. Declared, not wired, and the client
                # must not invent a click for it.
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
                "spans": [
                    {
                        "text": sp.text,
                        "state": sp.kind,
                        "href": sp.reference.href if sp.reference else None,
                        "entity_id": sp.reference.entity_id if sp.reference else None,
                    }
                    for sp in d.fragment.instance.payload.spans
                ],
                "target_surface": d.fragment.declaration.target_surface,
                "target_key": d.fragment.declaration.target_key,
                # Session 3 wires opening; declared, not wired, exactly as the
                # standing set's targets are.
                "openable": False,
                # Why this is here. Carried so an operator review can ask "why
                # is this not showing?" and get an answer from the surface
                # rather than from the logs.
                "gate": d.verdict,
            }
            for d in rendering
        ],
        # ⚠️ What the gate WITHHELD, and why. Not rendered as prose — it is the
        # answer to "should there be more here?", which on a quiet day is the
        # question an operator will actually have.
        "withheld": [
            {
                "fragment_id": d.fragment.declaration.fragment_id,
                "instance_key": d.fragment.instance_key,
                "gate": d.verdict,
            }
            for d in decisions
            if not d.renders
        ],
    }
