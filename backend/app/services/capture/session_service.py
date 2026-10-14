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
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.capture_session import (
    STATUS_ABANDONED,
    STATUS_APPROVED,
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
#: ⚠️ THE APPROVE SIGNAL, VERBATIM FROM THE SAME PROTOTYPE LINE
#: (`docs/prototypes/2026-10-01-opas-overlay.html:543`):
#: `/^(approve|create it|send it|yes|go)$/`. Kept whole rather than trimmed to
#: "approve" — the prototype is the authority on what a director types, and "yes"
#: after "Ready for your approval" is the most natural thing to type of the five.
#:
#: ⚠️ IT ONLY MEANS ANYTHING IN REVIEW. "yes" and "go" are ordinary words; in the
#: capturing stage they are order text and must stay that way. The gate is the
#: status check at the call site, not the pattern.
#: Everything a director types to mean "finish this order".
#:
#: ⚠️ ONE SET, ONE ACTION, BY RULING (James, 2026-10-14). "done", "that's it",
#: "that's everything", "approve" and "complete" all do what the Complete order
#: button does, and NONE of them may ever appear under Not Understood. Measured
#: 2026-10-14: "…last name smith approve" put **approve** in the unrecognized list,
#: because the approve phrase was only stripped when the session was already in
#: review — and getting to review needed a separate "that's everything" first.
#:
#: ⚠️ IT IS THE UNION OF THE TWO OLDER PATTERNS PLUS "complete", kept as one object
#: so a phrase cannot be understood by one half of the code and not the other.
COMPLETE_SIGNAL = re.compile(
    r"^(that'?s (it|everything|all)|that should be everything|done|review( it)?"
    r"|looks good|ready|approve|create it|send it|yes|go|complete"
    r"|complete order|finish)$",
    re.I,
)

APPROVE_SIGNAL = re.compile(
    r"^(approve|create it|send it|yes|go)$", re.I
)

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

    # ⚠️ AN APPROVED SESSION IS TERMINAL AND IS RETURNED UNTOUCHED. Found in a real
    # browser: after Approve the pane clears the bar, the bar's debounced extraction
    # sent `setCaptureText(session, "")`, and this function re-extracted — replacing
    # `values` with nothing on a session that had already written a sales order. The
    # order row was safe; the session was gutted and the receipt read $0.00.
    #
    # ⚠️ THE OLD STATUS GUARD WAS NOT ENOUGH, AND THAT IS THE LESSON. It sat at the
    # BOTTOM of this function and protected only `row.status`; every write above it —
    # `values`, `unrecognized`, `pending_picks`, `switches`, `full_text` — ran
    # unconditionally. A guard placed after the damage is not a guard.
    if row.status == STATUS_APPROVED:
        return row

    resolutions = dict(row.resolutions or {})

    # ⚠️ A TRAILING COMPLETION PHRASE IS STRIPPED REGARDLESS OF STATUS, AND THAT IS
    # THE FIX FOR WHAT JAMES SAW. Until 2026-10-14 the approve phrase was only taken
    # off the text when the session was already in `review`, so "…last name smith
    # approve" on a capturing session left "approve" in the ORDER TEXT — where the
    # extractor could place it nowhere and reported it as not understood. A word the
    # engine acts on must never also be a word it fails to read.
    #
    # ⚠️ STRIPPED REPEATEDLY, because a director types one onto the end of another.
    # "…that's everything approve" carries two; leaving the inner one behind would
    # put "that's everything" into the order text.
    completing = False
    body = text
    while True:
        shorter = trailing_signal(body, COMPLETE_SIGNAL)
        if shorter is None:
            break
        completing = True
        body = shorter

    ex = extract_text(db, tenant_id=company_id, text=body, resolutions=resolutions)

    # ⚠️ THE TYPED TEXT IS STORED, NOT THE STRIPPED BODY. `full_text` is the order's
    # own words and ends up in `sales_orders.notes`; editing it here would make the
    # record disagree with what the director saw in the bar.
    row.full_text = text
    row.values = dict(ex.values)
    row.unrecognized = list(ex.unrecognized)
    row.pending_picks = [asdict(pk) for pk in ex.picks]
    # ⚠️ STORED ON THE ROW RATHER THAN RE-DERIVED AT READ TIME, for the same reason
    # `pending_picks` is: `read_state` must not run extraction. It evaluates, which
    # needs only `values` — re-extracting there would double the cost of every read
    # and give two places that decide what the text means.
    row.switches = [asdict(sw) for sw in ex.switches]
    # ⚠️ REMEMBERED ON THE INSTANCE, NOT IN THE DATABASE. "somebody just tried to
    # finish this" is a fact about this request, not about the order — a later plain
    # read must not find the rows amber. The route reads it off the returned row.
    row._completion_attempt = completing  # type: ignore[attr-defined]
    db.flush()

    # ⚠️ ABANDONED IS NOT RE-DERIVED. It is not a statement about the text.
    # ⚠️ NOR IS APPROVED. An approved session has a sales order; re-reading its text
    # must never walk it back to `capturing`, which the branch below would do.
    if row.status in (STATUS_CAPTURING, STATUS_REVIEW):
        if completing or any(
            COMPLETE_SIGNAL.match(seg.strip()) for seg in segments(text)
        ):
            return complete(
                db, row.id, company_id=row.company_id, user_id=row.user_id
            )
        row.status = STATUS_CAPTURING
        db.flush()
    return row


def complete(
    db: Session, session_id: str, *, company_id: str, user_id: str
) -> CaptureSession:
    """Finish the order: show the summary, or say what is still missing.

    ⚠️ ONE ACTION BEHIND THREE ENTRANCES, BY RULING (2026-10-14): the Complete order
    button, ⌘Enter, and a trailing "done"/"that's it"/"approve"/"complete" all arrive
    here. Three code paths for one intention is how "approve" came to work only after
    a separate "that's everything".

    ⚠️ IT DOES NOT APPROVE FROM `capturing`, AND THAT IS DELIBERATE. From a capturing
    session a completion phrase moves to REVIEW so the summary is seen; approving is
    the second press. The office must look at the lines and the total before an order
    exists, and typing one word must not skip that.

    ⚠️ FROM `review` THE SAME PHRASE APPROVES, which is what makes "press Enter or
    Approve" true of the typed path as well as the button.

    ⚠️ A BLOCKED ORDER STAYS WHERE IT IS. It does not advance and does not raise: the
    caller reads `missing_labels` and the rows' own `missing_field_ids` and turns them
    amber. Advancing to a summary that could not be approved would be a screen whose
    only content is a refusal.
    """
    row = _load(db, session_id, company_id=company_id, user_id=user_id)
    if row.status == STATUS_APPROVED:
        return row

    if row.status == STATUS_REVIEW:
        assessment = assess_approval(db, row)
        if assessment.ready:
            return approve(db, row.id, company_id=company_id, user_id=user_id)
        # ⚠️ FALLS BACK TO CAPTURING WHEN REVIEW IS NO LONGER SAFE. A pick reopened
        # or a product deleted between the summary and the press, and the order is
        # not approvable any more; the rows are where the office fixes that.
        row.status = STATUS_CAPTURING
        db.flush()
        return row

    _resolution, state, conflicts = evaluate_typed(
        db, tenant_id=row.company_id, answers=dict(row.values or {})
    )
    blocked = bool(state.missing) or bool(conflicts) or bool(row.pending_picks)
    row.status = STATUS_CAPTURING if blocked else STATUS_REVIEW
    db.flush()
    return row


def abandon(
    db: Session, session_id: str, *, company_id: str, user_id: str
) -> CaptureSession:
    """Closing Opas ends the capture. The row is MARKED, never deleted.

    ⚠️ RULED 2026-10-13, AND THE REASON IS A SHARED OFFICE COMPUTER, not tidiness.
    The next person at that machine must never see someone else's half-typed order.
    So Esc, the veil and the close button end the capture rather than tucking it.

    ⚠️ MARKED, NOT DELETED, WHICH IS THE WHOLE POINT OF THE DISTINCTION. James
    accepted the consequence — an accidental click away loses the order FROM THE
    SCREEN — on the basis that the server keeps a copy, so it can be recovered if
    that ever turns out to matter. Deleting the row would make that promise false,
    and nothing in the UI would reveal it.

    ⚠️ IDEMPOTENT. The veil and Escape can both fire for one gesture, and a second
    call must not be an error — the pane is already gone by then and an error would
    surface as a failed request for an action that succeeded.
    """
    row = _load(db, session_id, company_id=company_id, user_id=user_id)
    if row.status != STATUS_ABANDONED:
        row.status = STATUS_ABANDONED
        db.flush()
    return row


def take_switch(
    db: Session, session_id: str, *, company_id: str, user_id: str,
    field_id: str, to_value: str,
) -> CaptureSession:
    """Take the alternative a switch offered. One click, by ruling.

    ⚠️ THE VALUE IS VALIDATED AGAINST THE OFFER, not accepted on trust. Without that
    this endpoint would set any field to any string — a write path with no vocabulary,
    reachable by anyone who can reach the session. The only acceptable value is the
    `to_value` the server itself put in `switches`.

    ⚠️ IT WRITES A RESOLUTION, NOT A VALUE, which is what makes the click survive the
    next keystroke. `values` is rebuilt from the text on every pause, so a value
    written here would be erased ~350 ms later and the burial vault would come back.
    Resolutions outrank extraction; that is the whole mechanism.
    """
    row = _load(db, session_id, company_id=company_id, user_id=user_id)
    offers = [
        sw for sw in (row.switches or [])
        if sw.get("field_id") == field_id and sw.get("to_value") == to_value
    ]
    if not offers:
        raise ValueError(f"no switch offered for {field_id!r} to {to_value!r}")

    resolutions = dict(row.resolutions or {})
    resolutions[field_id] = to_value
    row.resolutions = resolutions

    if row.full_text is not None:
        ex = extract_text(
            db, tenant_id=company_id, text=row.full_text, resolutions=resolutions
        )
        row.values = dict(ex.values)
        row.unrecognized = list(ex.unrecognized)
        row.pending_picks = [asdict(pk) for pk in ex.picks]
        row.switches = [asdict(sw) for sw in ex.switches]
    else:
        values = dict(row.values or {})
        values[field_id] = to_value
        row.values = values
        row.switches = [
            sw for sw in (row.switches or []) if sw.get("field_id") != field_id
        ]
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
    # ⚠️ SETTLING A FIELD RETIRES ITS SWITCH. An offer surviving its own resolution
    # would invite the director to undo the click they just made.
    row.switches = [
        sw for sw in (row.switches or []) if sw.get("field_id") != field_id
    ]

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


def trailing_signal(text: str, pattern: re.Pattern) -> str | None:
    """The order text with a trailing signal phrase removed, or None if there isn't one.

    ⚠️ THE SIGNAL IS A TRAILING PHRASE, NOT A SEGMENT, AND WITHOUT THIS THE WHOLE
    REVIEW STAGE IS UNREACHABLE FOR THE WAY JAMES TYPES. `segments()` splits on
    commas, and the done signal was tested per segment — so "that's everything" was
    only ever detected after a comma. Measured 2026-10-13:

        "order … nameplate only, that's everything"  -> two segments, signal found
        "order … nameplate only that's everything"   -> ONE segment, signal missed

    He types no commas. The done signal therefore never fired, the session never
    reached `review`, and Approve could not be got to at all. The segment check is
    kept as well — a director who does type a comma is still understood.

    ⚠️ IT RETURNS THE REMAINING TEXT RATHER THAN A BOOLEAN, so the caller extracts
    from the ORDER and not from the order plus a command. Left in, "done" and "go"
    are words the extractor would try to place and then report as not understood.

    ⚠️ IT TRIES THE LAST FOUR WORDS DOWN TO THE LAST ONE, longest first. "that
    should be everything" is four; "go" is one. Matching shortest-first would let
    "everything" alone decide a phrase that says something else.
    """
    stripped = (text or "").rstrip().rstrip(".!?").rstrip()
    words = stripped.split()
    for n in range(4, 0, -1):
        if len(words) < n:
            continue
        tail = " ".join(words[-n:])
        if pattern.match(tail.strip()):
            return " ".join(words[:-n])
    return None


def is_approve_signal(line: str) -> bool:
    return bool(APPROVE_SIGNAL.match(line.strip()))


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
    _, state, _conflicts = evaluate_typed(
        db, tenant_id=row.company_id, answers=dict(row.values or {})
    )
    if state.missing:
        row.status = STATUS_CAPTURING
    else:
        row.status = STATUS_REVIEW
    db.flush()
    return row


def read_state(
    db: Session,
    session_id: str,
    *,
    company_id: str,
    user_id: str,
    completion_attempt: bool = False,
) -> dict:
    """The session plus its evaluated capture state and rendered rows.

    ⚠️ THE ROWS COME FROM THE EXISTING `capture` SURFACE, NOT FROM A NEW LIST. The
    investigation found the row layer already declares 9 rows over the template and is
    reusable as-is; inventing a second row list for the typed pane would be two sources
    of truth about what an order shows.
    """
    row = _load(db, session_id, company_id=company_id, user_id=user_id)
    answers = dict(row.values or {})
    resolution, state, conflicts = evaluate_typed(
        db, tenant_id=company_id, answers=answers
    )

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
    # ⚠️ THE CONFLICTING ANSWERS ARE WITHHELD FROM THE RENDER TOO, AND THAT IS NOT
    # TIDINESS. `evaluate` never saw them, so they are absent from `state.answered` —
    # but `resolve_surface` renders from `answers`, so passing the full dict made the
    # Personalization row read DONE, showing "Nameplate & Life's Reflections® Vinyl",
    # while the same response reported that value as unavailable on this vault.
    # Measured over HTTP on dev. One response contradicting itself is the defect class
    # that produced `not_configured`-vs-`answered` earlier in this arc; the fix then
    # was to read the state's own resolution rather than re-deriving, and the fix here
    # is the same move — render from exactly what was evaluated.
    conflicted = {c.field_id for c in conflicts}
    rendered_answers = {k: v for k, v in answers.items() if k not in conflicted}
    rendered = resolve_surface(
        surface, resolved, rendered_answers, done_signal=said_done
    )

    # ⚠️ THE SUMMARY'S LINES AND BLOCKERS ARE COMPUTED ONLY IN REVIEW. Assessing on
    # every keystroke would run two product lookups and a customer lookup per
    # extraction, and would report "nothing to bill" at the first character — a
    # blocker is an answer to "why can't I approve", which nobody is asking while
    # they are still typing.
    appraisal = None
    if row.status == STATUS_REVIEW:
        appraisal = assess_approval(db, row)

    # ⚠️ ONCE THE ORDER EXISTS, THE ORDER IS THE RECORD — not a fresh assessment.
    # `read_state` used to re-assess for an approved session too, which meant the
    # receipt's total was recomputed from the tenant's products on every read: delete
    # a product afterwards and the office would be shown a different total for an
    # order it had already approved. Blockers are withheld for the same reason — they
    # answered "why can't I approve", and that question is gone.
    order_number = None
    order_total = None
    if row.sales_order_id:
        found = db.execute(
            text("SELECT number, total FROM sales_orders WHERE id = :i"),
            {"i": row.sales_order_id},
        ).first()
        if found:
            order_number, order_total = found.number, found.total

    return {
        "session_id": row.id,
        "status": row.status,
        "object_type": row.object_type,
        # ⚠️ PRESENT ONLY IN REVIEW, AND `null` IS NOT `[]`. An empty list would say
        # "this order has no lines", which is a blocker; `null` says the question has
        # not been asked yet.
        "lines": (
            [
                {
                    "kind": l.kind,
                    "description": l.description,
                    "product_id": l.product_id,
                    "unit_price": str(l.unit_price) if l.unit_price is not None else None,
                    "quantity": str(l.quantity),
                    "line_total": str(l.line_total),
                }
                for l in appraisal.lines
            ]
            if appraisal
            else None
        ),
        "total": (
            str(order_total)
            if order_total is not None
            else (str(appraisal.total) if appraisal else None)
        ),
        "blockers": list(appraisal.blockers) if appraisal else None,
        "can_approve": bool(appraisal.ready) if appraisal else False,
        "sales_order_id": row.sales_order_id,
        "sales_order_number": order_number,
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
        # ⚠️ A SEPARATE LIST FROM `unrecognized`, BY NATURE NOT BY TASTE. The extractor
        # understood these phrases; they contradict each other. Reporting a conflict as
        # "not understood" would send the director back to re-type words that were read
        # correctly. This list is why the pane no longer 500s on
        # "Continental 34 … nameplate and vinyl".
        "conflicts": [
            {
                "field_id": c.field_id,
                "value": c.value,
                "permitted": list(c.permitted),
                "message": c.message,
            }
            for c in conflicts
        ],
        "pending_picks": list(row.pending_picks or []),
        # ⚠️ A SWITCH IS NOT A PICK. The field is CAPTURED; this is the one
        # alternative, one click away. Ruled 2026-10-13: a vault ambiguous only by
        # form takes the burial vault and offers the urn vault, because a pick there
        # asks a question whose answer the office already knows.
        "switches": list(row.switches or []),
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
                    # ⚠️ THE PILL AND THE AMBER BOTH READ THIS, which is what makes
                    # "the pill count equals the number of amber-able rows" true by
                    # construction. The pill used to count missing FIELDS while the
                    # colour belonged to ROWS, and two missing fields can share one
                    # row — so "2 needed" could mean one amber row and the director
                    # had to guess which fields were meant.
                    "missing_field_ids": list(r.missing_field_ids),
                }
                for r in rendered.rows
            ],
        },
        # ⚠️ THE LABELS FOR THE BAR'S OWN SENTENCE. "Still need: service date" is
        # built from the same missing set the rows colour from, so the bar cannot
        # name something the pane is not highlighting.
        "missing_labels": list(_missing_labels(state)),
        # ⚠️ TRANSIENT AND FALSE ON A PLAIN READ. It is the answer to "did somebody
        # just try to finish this order", which is what turns the rows amber — not a
        # property of the order. A typed completion phrase is detected on the SERVER,
        # so the client cannot know about that attempt unless the response says so.
        "completion_attempt": bool(completion_attempt),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Approve — the capture becomes a sales order
# ─────────────────────────────────────────────────────────────────────────────


def _as_date(value: object):
    """An ISO date, or None if the answer is not a full date.

    ⚠️ YEARS ARE THE COMMON CASE AND THEY ARE NOT DATES. Measured 2026-10-13: the
    capture stores `date_of_birth` as `'1948'` — a year, because that is what a
    director says and what the nameplate prints. A year cannot be a `Date`, and
    guessing January 1st would invent a birthday that then appears on an invoice.

    ⚠️ NOTHING IS LOST WHEN THIS RETURNS None. The order carries
    `capture_sessions.sales_order_id` in the other direction, so the raw answers
    stay reachable from the order through the session that produced it, and the
    personalization task keeps the inscription text verbatim.
    """
    from datetime import date as _date

    if isinstance(value, _date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return _date.fromisoformat(value.strip())
    except ValueError:
        return None


def assess_approval(db: Session, row: CaptureSession):
    """The blockers and prospective lines for a session, without writing anything."""
    from app.services.capture.approval import assess

    answers = dict(row.values or {})
    _resolution, state, conflicts = evaluate_typed(
        db, tenant_id=row.company_id, answers=answers
    )
    labels = _missing_labels(state)
    picks = tuple(
        p.get("field_id", "") for p in (row.pending_picks or []) if p.get("field_id")
    )
    return assess(
        db,
        tenant_id=row.company_id,
        answers=answers,
        missing_labels=labels,
        open_picks=picks,
        # ⚠️ THE CONFLICTS WERE DISCARDED HERE UNTIL 2026-10-13 (`_conflicts`), so an
        # answer the vault cannot take did not stop the order being approved.
        conflicts=tuple(c.message for c in conflicts),
    )


def _missing_labels(state) -> tuple[str, ...]:
    """Field labels for the missing set, so a blocker reads in the office's words.

    ⚠️ FROM `PLATFORM_DEFAULT_FIELDS`, NOT `resolve_schema`. Labels are platform-level
    — the tenant resolution decides which fields APPLY, not what they are called —
    and `resolve_schema` needs a resolved vault and a personalization config it has
    no business asking for just to spell "Deceased name".
    """
    from app.services.capture.schema import PLATFORM_DEFAULT_FIELDS

    labels = {f.field_id: f.label for f in PLATFORM_DEFAULT_FIELDS}
    return tuple(
        labels.get(fid) or fid.replace("_", " ") for fid in state.missing
    )


def approve(
    db: Session, session_id: str, *, company_id: str, user_id: str
) -> CaptureSession:
    """Create the sales order this capture describes. One transaction, idempotent.

    ⚠️ STATUS `draft`, BY JAMES'S DECISION D1 (2026-10-13), AND IT IS A SAFETY
    MECHANISM RATHER THAN A DEFAULT. Measured on production: the 18:00 end-of-day
    batch selects `status IN ('confirmed','processing','shipped','delivered',
    'completed')` (`draft_invoice_service.py:226-228`) and, in the auto-confirm mode
    every production tenant runs, it SETS THE ORDER TO `delivered` and drafts an
    invoice against it. 12 invoices and 5 rewritten orders on production prove it is
    live. `draft` is outside that net, and `create_invoice_from_order` refuses a
    draft outright besides.

    ⚠️ `order_type='funeral'` IS NOT A SECOND GUARD, THOUGH I WROTE THAT HERE FIRST
    AND A BREAK TEST CAUGHT IT. The batch's filter is
    `order_type == 'funeral' OR order_type IS NULL`
    (`draft_invoice_service.py:240`) — BOTH are inside the net, so setting it to
    'funeral' protects nothing. It is set because it is TRUE: these are funeral
    orders, and the column is what the end-of-day batch and the scheduling board
    read to know that.

    ⚠️ SO THE PROTECTION IS `status='draft'` ALONE, and it should be read that way
    rather than as defence in depth. The only other value that would exclude the
    order is a false one.

    ⚠️ IT DOES NOT CALL `sales_service.create_sales_order`, DELIBERATELY. That path
    runs `apply_placer_to_order_lines` — which ADDS LINES from funeral-home placer
    preferences — and `recalculate_order_line_prices` over them, both inside
    try/except that only logs (`sales_service.py:582-599`). The order the office
    approved would not be the order that got stored, and a failure would be a log
    line. The numbering allocator IS reused, because that is the part which must
    stay consistent with every other order.

    ⚠️ IDEMPOTENT BY READING THE LINK, NOT BY A CONSTRAINT. A session already
    carrying `sales_order_id` returns unchanged, so a double click, a retried
    request and a second typed "approve" all produce one order.
    """
    from app.models.sales_order import SalesOrder, SalesOrderLine

    row = _load(db, session_id, company_id=company_id, user_id=user_id)

    if row.sales_order_id:
        return row

    assessment = assess_approval(db, row)
    if not assessment.ready:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "This order cannot be approved yet.",
                "blockers": list(assessment.blockers),
            },
        )

    answers = dict(row.values or {})
    subtotal = assessment.total

    from app.services.sales_service import _next_number

    number = _next_number(db, company_id, SalesOrder, "SO")

    order = SalesOrder(
        id=str(uuid.uuid4()),
        company_id=company_id,
        number=number,
        customer_id=assessment.customer_id,
        status="draft",
        order_type="funeral",
        order_date=datetime.now(timezone.utc),
        # ⚠️ THE SERVICE DATE, BY DISPATCH. It is also the field the 18:00 batch
        # compares against `today`, which is why `status` and `order_type` carry
        # the protection rather than this.
        scheduled_date=_as_date(answers.get("service_date")),
        # ⚠️ DERIVED FROM THE SERVICE DATE, NOT FROM THE CAPTURED ANSWER. Ruled
        # 2026-10-13: the burial is always the service day, so Opas stopped asking —
        # `burial_date` is no longer required and is normally absent from `answers`.
        # Reading the answer here would store NULL on every order that did not
        # volunteer one, which is most of them.
        #
        # ⚠️ AND IT IS NOT READ EVEN WHEN PRESENT. A typed burial date that disagrees
        # with the service date is a CONFLICT and blocks approval, so by the time this
        # line runs the two either agree or the order was refused. Taking the typed
        # value would make the stored date depend on which of two agreeing sources
        # happened to be consulted.
        burial_date=_as_date(answers.get("service_date")),
        date_of_birth=_as_date(answers.get("date_of_birth")),
        date_of_death=_as_date(answers.get("date_of_death")),
        grave_location=(answers.get("grave_location") or None),
        deceased_name=(answers.get("deceased_name") or None),
        cemetery_id=_cemetery_id(db, company_id, answers.get("cemetery")),
        service_location=(answers.get("service_location") or None),
        service_location_other=(answers.get("service_location_other") or None),
        service_time=_as_time(answers.get("service_time")),
        eta=_as_time(answers.get("eta")),
        # ⚠️ THE ORDER'S OWN WORDS, KEPT. The sentence the director typed is the
        # most faithful record of what was asked for, and it is what the office
        # would want to read when something looks wrong.
        notes=(row.full_text or None),
        subtotal=subtotal,
        tax_rate=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total=subtotal,
        created_by=user_id,
    )
    db.add(order)
    db.flush()

    for idx, line in enumerate(assessment.lines):
        db.add(
            SalesOrderLine(
                id=str(uuid.uuid4()),
                sales_order_id=order.id,
                product_id=line.product_id,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                line_total=line.line_total,
                sort_order=idx,
            )
        )

    _write_personalization_tasks(db, order, answers, company_id)

    row.status = STATUS_APPROVED
    row.sales_order_id = order.id

    from app.services import audit_service

    audit_service.log_action(
        db,
        company_id,
        "created",
        "sales_order",
        order.id,
        user_id=user_id,
        changes={
            "number": order.number,
            "total": str(order.total),
            "source": "opas_capture",
            "capture_session_id": row.id,
        },
    )
    db.commit()
    db.refresh(row)
    return row


def _cemetery_id(db: Session, tenant_id: str, name: object) -> str | None:
    if not name or not isinstance(name, str):
        return None
    return db.execute(
        text(
            "SELECT id FROM cemeteries WHERE company_id = :t "
            "AND lower(btrim(name)) = lower(btrim(:n)) LIMIT 1"
        ),
        {"t": tenant_id, "n": name},
    ).scalar()


def _as_time(value: object):
    from datetime import time as _time

    if isinstance(value, _time):
        return value
    if not isinstance(value, str):
        return None
    try:
        return _time.fromisoformat(value.strip())
    except ValueError:
        return None


def _write_personalization_tasks(
    db: Session, order, answers: dict, company_id: str
) -> None:
    """One `order_personalization_tasks` row per personalization substrate chosen.

    ⚠️ THIS TABLE, NOT `sales_order_lines.personalization_data` — Q3 from the
    investigation, answered. Both exist; this one is FK'd to the order
    (`order_personalization_task.py:17`), already carries `print_name`, `symbol` and
    `is_custom_legacy`, and is what the personalization flow reads. Writing the JSONB
    column instead would store the fact somewhere nothing looks.

    ⚠️ `case_merchandise` IS NOT AN OPTION, though the investigation's dispatch
    suggested it: it is keyed by `case_id` and has no path to a sales order.
    """
    from app.models.order_personalization_task import OrderPersonalizationTask

    chosen = answers.get("personalization")
    if not chosen:
        return
    substrates = chosen if isinstance(chosen, (list, tuple)) else [chosen]

    for substrate in substrates:
        if not substrate or substrate == "none":
            continue
        db.add(
            OrderPersonalizationTask(
                id=str(uuid.uuid4()),
                company_id=company_id,
                order_id=order.id,
                task_type=str(substrate),
                inscription_name=(answers.get("deceased_name") or None),
                # ⚠️ THE CAPTURED DATES VERBATIM, because they are usually YEARS
                # ("1948"), which no date column can hold and which is exactly what
                # the nameplate prints.
                inscription_dates=_inscription_dates(answers),
                nameplate_date_format=(answers.get("nameplate_date_format") or None),
                print_name=(answers.get("legacy_print_name") or None),
                symbol=(answers.get("lifes_reflections_symbol") or None),
                is_custom_legacy=(answers.get("legacy_series") == "custom"),
            )
        )


def _inscription_dates(answers: dict) -> str | None:
    dob = (answers.get("date_of_birth") or "").strip()
    dod = (answers.get("date_of_death") or "").strip()
    if dob and dod:
        return f"{dob} - {dod}"
    return dob or dod or None
