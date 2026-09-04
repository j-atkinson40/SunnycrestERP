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
from app.services.note import get_or_create_note, render_standing_set

router = APIRouter()


@router.get("/today")
def get_today_note(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Today's note: identity, the standing set, and an empty prose region.

    `prose` is deliberately an empty list rather than absent. Prose composition
    is session 2, and an absent key would let a client treat "not built yet" and
    "nothing to say today" as the same thing — when canon says a three-line note
    on a quiet day is correct behaviour, so the empty case is a real state the
    client must render rather than a gap it should hide.
    """
    note = get_or_create_note(db, current_user)
    standing = render_standing_set(db, current_user)

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
        "prose": [],
    }
