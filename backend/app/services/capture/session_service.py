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
from app.services.capture.typed_extraction import (
    EXTRACTOR,
    evaluate_typed,
    extract_text,
    segments,
)

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

    if is_done_signal(line):
        # ⚠️ RECORDED BEFORE ACTING, AND IT WAS NOT BEFORE. This branch used to return
        # immediately, so the done phrase was never stored and the attempt left NO
        # TRACE on the row — `_signal_done` sets the status back to `capturing` on a
        # refusal and nothing else. That is why `read_state` had nothing to pass as
        # `done_signal` and why `RowState.NEEDED` could not occur in production.
        # The phrase is part of what the director typed, so it belongs in the text.
        row.typed_lines = list(row.typed_lines or []) + [
            {"line": line, "at": datetime.now(timezone.utc).isoformat()}
        ]
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


def set_text(
    db: Session, session_id: str, *, company_id: str, user_id: str, text: str
) -> CaptureSession:
    """Re-read the WHOLE text. The source of truth for the typed pane.

    ⚠️ IT REPLACES, IT DOES NOT ACCUMULATE, AND THAT IS THE POINT OF THE WHOLE
    MODEL. `values`, `unrecognized` and `pending_picks` are rebuilt from this text
    every time. If the director deletes a word, whatever that word captured is
    un-captured and whatever it failed to place stops being reported. `add_line`
    accumulates — correct when each line was a separate event, wrong now that the
    text is editable and on screen.

    ⚠️ `add_line` IS NOT TOUCHED AND IS NOT DEPRECATED (E6). It is the only path the
    call pipeline's shape resembles, it is the path every existing session was
    captured through, and its FIRST_WINS policy is right for a source that arrives
    one utterance at a time. Two sources, two policies, stated per source.

    ⚠️ THE STATUS IS RE-DERIVED FROM THE TEXT, NOT LATCHED. A director who types
    "that's it" and then deletes it is still capturing. Latching would make the
    done signal the one thing on screen that editing could not take back.
    """
    row = _load(db, session_id, company_id=company_id, user_id=user_id)
    resolutions = dict(row.resolutions or {})

    ex = extract_text(db, tenant_id=company_id, text=text, resolutions=resolutions)

    row.full_text = text
    row.values = dict(ex.values)
    row.unrecognized = list(ex.unrecognized)
    row.pending_picks = [asdict(pk) for pk in ex.picks]
    db.flush()

    # ⚠️ ABANDONED IS NOT RE-DERIVED. It is not a statement about the text.
    if row.status in (STATUS_CAPTURING, STATUS_REVIEW):
        if any(is_done_signal(seg) for seg in segments(text)):
            return _signal_done(db, row)
        row.status = STATUS_CAPTURING
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

    chosen = options[index - 1][0]

    # ⚠️ RECORDED DURABLY, NOT JUST APPLIED. Under whole-text re-extraction a value
    # written into `values` is erased by the next keystroke, because the next read
    # rebuilds `values` from the text — and the text is still ambiguous, so the same
    # question comes straight back. The resolution is the director's decision ABOUT
    # that text and has to outlive every re-read of it.
    resolutions = dict(row.resolutions or {})
    resolutions[field_id] = chosen
    row.resolutions = resolutions

    if row.full_text is not None:
        # ⚠️ RE-EXTRACTED THROUGH THE SAME CALL THE NEXT PAUSE WILL MAKE, so the
        # response cannot disagree with what the pane is about to be sent. Writing
        # `values[field_id]` here instead would be a second place that decides what a
        # settled pick means, and it would differ the moment resolutions gained any
        # behaviour beyond overwrite.
        ex = extract_text(
            db, tenant_id=company_id, text=row.full_text, resolutions=resolutions
        )
        row.values = dict(ex.values)
        row.unrecognized = list(ex.unrecognized)
        row.pending_picks = [asdict(pk) for pk in ex.picks]
    else:
        # ⚠️ THE LINE PATH, BYTE-FOR-BYTE AS IT WAS. A session with no whole-text
        # record is one captured line-by-line, and E6 says that path does not change.
        values = dict(row.values or {})
        values[field_id] = chosen
        row.values = values
        row.pending_picks = [p for p in picks if p["field_id"] != field_id]

    db.flush()
    return row


def is_done_signal(line: str) -> bool:
    """Did the director say they were finished?

    ⚠️ ONE PREDICATE, USED BY BOTH THE WRITER AND THE READER. `add_line` decides
    whether to advance; `read_state` decides whether the rows should show their gaps
    as NEEDED. Those were briefly two expressions — `DONE_SIGNAL.match(line.strip())`
    and `DONE_SIGNAL.search(line.lower())` — which is the same question asked two ways
    and free to drift. `match` anchored at the start is the prototype's behaviour
    (`:539`), so that is the one kept.
    """
    return bool(DONE_SIGNAL.match(line.strip()))


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

    # ⚠️ THE RESOLUTION `evaluate` ALREADY DID — NOT A SECOND ONE. This used to call
    # `resolve_schema(..., personalization_config=None)` while `evaluate_typed` passed
    # the real availability, so ONE RESPONSE CONTRADICTED ITSELF: the
    # `personalization` ROW read "Not configured for this licensee" while the SET said
    # `answered`. Measured on a fresh tenant whose availability resolves correctly.
    # Reading it off the state makes passing different arguments impossible.
    resolved = state.resolved_fields
    surface = SUMMARY_SALES_ORDER if row.status == STATUS_REVIEW else CAPTURE_SALES_ORDER

    # ⚠️ `done_signal` WAS NEVER PASSED, SO `RowState.NEEDED` WAS DEAD STATE — found
    # 2026-10-12 while verifying defect 3c, by writing a test that asserted NEEDED
    # fires and watching it fail. The state exists, has a prototype citation, is
    # covered by unit tests that pass `done_signal=True` directly, and COULD NOT
    # OCCUR through the live path: this call omitted the argument and it defaults to
    # False. Complete machinery behind an unprovisioned entrance (CLAUDE.md §11).
    #
    # ⚠️ AND THERE WAS NOTHING PERSISTED TO PASS. `_signal_done` sets the status back
    # to `capturing` on a refusal and records nothing else, so the attempt left no
    # trace on the row. Rather than add a column for it, the signal is DERIVED FROM
    # THE TEXT — which is where the director actually put it, and which survives the
    # move to whole-text re-extraction, where the text is the only source there is.
    # ⚠️ FROM WHICHEVER SOURCE THIS SESSION ACTUALLY HAS. A line-captured session has
    # lines and no text; a typed-pane session has text and no lines. Reading only one
    # would make the done signal work in one pane and silently not in the other.
    said_done = any(
        is_done_signal(ln.get("line") or "") for ln in (row.typed_lines or [])
    ) or any(is_done_signal(seg) for seg in segments(row.full_text or ""))
    rendered = resolve_surface(surface, resolved, answers, done_signal=said_done)

    return {
        "session_id": row.id,
        "status": row.status,
        "object_type": row.object_type,
        "typed_lines": [ln["line"] for ln in (row.typed_lines or [])],
        # ⚠️ BOTH ARE RETURNED SO A RELOAD RESTORES THE PANE EXACTLY. The text goes
        # back in the bar; the resolutions keep the settled picks settled. Returning
        # the text alone would re-raise every question the director already answered.
        # `None`, not `""` — the pane must be able to tell "no whole-text record"
        # from "the bar is empty", and only the first means fall back to the lines.
        "full_text": row.full_text,
        "resolutions": dict(row.resolutions or {}),
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
