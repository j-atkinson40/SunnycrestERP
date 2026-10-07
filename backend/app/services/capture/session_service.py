"""The typed-capture session: start it, feed it lines, read its state.

⚠️ THE ONE PLACE A TYPED SESSION IS MUTATED. The route layer does auth and shape; every
state change goes through here, so there is one answer to "what does a line do to a
session" rather than one per endpoint.

⚠️ EVERY READ AND WRITE IS SCOPED TO (company_id, user_id), NOT company_id ALONE. Two
users in one tenant must not see each other's half-typed orders — a session is a
sentence someone is in the middle of saying. `_load` takes both and returns None rather
than raising, so the route turns a cross-user id into a 404 and the caller cannot tell a
wrong id from someone else's id.

⚠️ NO ORDER IS WRITTEN. E5 ends this slice at `review`. There is no approve function
here, deliberately — a stub would read as an intention the slice does not carry out.
"""
from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.capture_session import (
    STATUS_CAPTURING,
    STATUS_REVIEW,
    CaptureSession,
)
from app.services import capture
from app.services.capture.typed_extraction import EXTRACTOR, evaluate_typed

#: ⚠️ THE DONE-SIGNAL, VERBATIM FROM THE OPAS OVERLAY PROTOTYPE
#: (`docs/prototypes/2026-10-01-opas-overlay.html:539`). Not re-worded: the prototype is
#: the authority on what a director types, and a phrase that works there and not here
#: would be a difference nobody chose.
DONE_SIGNAL = re.compile(
    r"^(that'?s (it|everything|all)|that should be everything|done|review( it)?"
    r"|looks good|ready)$",
    re.I,
)

#: The entrance, also from the prototype (`:296`). ⚠️ The opening line is FED THROUGH
#: EXTRACTION as well as starting the session (`:568` calls `feed` immediately), which
#: is what lets "start an order for Hopkins" capture the funeral home on the same
#: keystroke that creates the pane.
START_SIGNAL = re.compile(
    r"\b(new|create|start|make|enter|put in|take)\b.*\border\b|^order for\b", re.I
)


class SessionNotFound(LookupError):
    """⚠️ RAISED FOR A WRONG ID AND FOR SOMEONE ELSE'S ID ALIKE. The route turns both
    into 404; distinguishing them would tell a caller that a session they may not read
    exists."""


def _load(db: Session, session_id: str, *, company_id: str, user_id: str) -> CaptureSession:
    row = (
        db.query(CaptureSession)
        .filter(
            CaptureSession.id == session_id,
            CaptureSession.company_id == company_id,
            CaptureSession.user_id == user_id,
        )
        .first()
    )
    if row is None:
        raise SessionNotFound(session_id)
    return row


def start(
    db: Session, *, company_id: str, user_id: str, opening_line: str | None = None
) -> CaptureSession:
    """Create a session, feeding the opening line through extraction if one was given."""
    row = CaptureSession(
        company_id=company_id,
        user_id=user_id,
        object_type=capture.SALES_ORDER,
        status=STATUS_CAPTURING,
        typed_lines=[],
        values={},
        unrecognized=[],
        pending_picks=[],
    )
    db.add(row)
    db.flush()
    if opening_line and opening_line.strip():
        add_line(db, row.id, company_id=company_id, user_id=user_id, line=opening_line)
        db.refresh(row)
    return row


def add_line(
    db: Session, session_id: str, *, company_id: str, user_id: str, line: str
) -> CaptureSession:
    """Extract one typed line into the session.

    ⚠️ THE SESSION'S OWN VALUES ARE PASSED IN AS `answers`, so the extractor can tell a
    new answer from a re-statement. Extracting each line in isolation would let a later
    line silently overwrite an earlier one.

    ⚠️ `unrecognized` ACCUMULATES AND IS NOT RESET PER LINE. The director needs to see
    everything the engine failed to place across the whole order, not only in the last
    thing they typed.
    """
    row = _load(db, session_id, company_id=company_id, user_id=user_id)
    values = dict(row.values or {})

    if DONE_SIGNAL.match(line.strip()):
        return _signal_done(db, row)

    ex = EXTRACTOR.extract_line(
        db, tenant_id=company_id, line=line, answers=values
    )
    values.update(ex.values)

    lines = list(row.typed_lines or [])
    lines.append({"line": line, "at": datetime.now(timezone.utc).isoformat()})

    # ⚠️ A PICK FOR A FIELD REPLACES ANY EARLIER PICK FOR THE SAME FIELD. Two pending
    # questions about the same field would render as two numbered lists and the second
    # answer would be ambiguous about which it settled.
    picks = [p for p in (row.pending_picks or []) if p["field_id"] not in
             {pk.field_id for pk in ex.picks}]
    picks.extend(asdict(pk) for pk in ex.picks)

    row.typed_lines = lines
    row.values = values
    row.unrecognized = list(row.unrecognized or []) + list(ex.unrecognized)
    row.pending_picks = picks
    db.flush()
    return row


def choose(
    db: Session, session_id: str, *, company_id: str, user_id: str,
    field_id: str, index: int,
) -> CaptureSession:
    """Settle a numbered pick. `index` is 1-based, as the director types it.

    ⚠️ ONE-BASED BECAUSE THE PROTOTYPE'S KEYBOARD HANDLER IS
    (`2026-10-01-opas-overlay.html:622`: `/^[1-9]$/` then `choose(+e.key-1)`). Taking
    zero-based here would make the API disagree with the only interface that drives it.
    """
    row = _load(db, session_id, company_id=company_id, user_id=user_id)
    picks = list(row.pending_picks or [])
    pick = next((p for p in picks if p["field_id"] == field_id), None)
    if pick is None:
        raise SessionNotFound(f"{session_id}:{field_id}")
    options = pick["options"]
    if not (1 <= index <= len(options)):
        raise ValueError(f"pick {index} is outside 1..{len(options)}")

    values = dict(row.values or {})
    values[field_id] = options[index - 1][0]
    row.values = values
    row.pending_picks = [p for p in picks if p["field_id"] != field_id]
    db.flush()
    return row


def _signal_done(db: Session, row: CaptureSession) -> CaptureSession:
    """Move to review if nothing is missing; otherwise stay and let the gaps show.

    ⚠️ THE PROTOTYPE'S TWO OUTCOMES, KEPT (`:540-542`): with required gaps it does NOT
    advance and names them; otherwise it goes to review. The difference here is that
    the gaps come from `capture.evaluate` rather than from a seven-field list.
    """
    _, state = evaluate_typed(db, tenant_id=row.company_id, answers=dict(row.values or {}))
    if state.missing:
        row.status = STATUS_CAPTURING
    else:
        row.status = STATUS_REVIEW
    db.flush()
    return row


def read_state(db: Session, session_id: str, *, company_id: str, user_id: str) -> dict:
    """The session plus its evaluated capture state and rendered rows.

    ⚠️ THE ROWS COME FROM THE EXISTING `capture` SURFACE, NOT FROM A NEW LIST. The
    investigation found the row layer already declares 9 rows over the template and is
    reusable as-is; inventing a second row list for the typed pane would be two sources
    of truth about what an order shows.
    """
    row = _load(db, session_id, company_id=company_id, user_id=user_id)
    answers = dict(row.values or {})
    resolution, state = evaluate_typed(db, tenant_id=company_id, answers=answers)

    from app.services.capture.rows import resolve_surface
    from app.services.capture.surfaces import (
        CAPTURE_SALES_ORDER,
        SUMMARY_SALES_ORDER,
    )

    resolved = capture.resolve_schema(
        vault_product_id=resolution.variant_template_id,
        personalization_config=None,
        platform_fields=capture.template_for(capture.SALES_ORDER),
    )
    surface = SUMMARY_SALES_ORDER if row.status == STATUS_REVIEW else CAPTURE_SALES_ORDER
    rendered = resolve_surface(surface, resolved, answers)

    return {
        "session_id": row.id,
        "status": row.status,
        "object_type": row.object_type,
        "typed_lines": [ln["line"] for ln in (row.typed_lines or [])],
        "values": answers,
        # ⚠️ ALL FIVE SETS, NOT JUST `missing`. The pane renders a row per state and
        # `not_applicable` vs `indeterminate` is the distinction the amber dashed row
        # exists for.
        "answered": list(state.answered),
        "missing": list(state.missing),
        "unanswered_optional": list(state.unanswered_optional),
        "not_applicable": list(state.not_applicable),
        "indeterminate": list(state.indeterminate),
        "is_complete": state.is_complete,
        "unrecognized": list(row.unrecognized or []),
        "pending_picks": list(row.pending_picks or []),
        "vault_resolution": {
            "resolved": bool(resolution.variant_template_id),
            "candidates": [c.sku for c in resolution.candidates],
            "discriminators": [d.value for d in resolution.discriminators],
        },
        "surface": {
            "id": rendered.surface_id,
            "rows": [
                {
                    "row_id": r.row_id,
                    "label": r.label,
                    "state": r.state.value,
                    "value": r.value,
                    "secondary_value": r.secondary_value,
                }
                for r in rendered.rows
            ],
        },
    }
