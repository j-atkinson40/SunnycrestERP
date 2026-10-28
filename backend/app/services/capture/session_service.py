"""The typed-capture session: start it, feed it lines, read its state.

⚠️ THE ONE PLACE A TYPED SESSION IS MUTATED. The route layer does auth and shape; every
state change goes through here, so there is one answer to "what does a line do to a
session" rather than one per endpoint.

⚠️ EVERY READ AND WRITE IS SCOPED TO (company_id, user_id), NOT company_id ALONE. Two
users in one tenant must not see each other's half-typed orders — a session is a
sentence someone is in the middle of saying. `_load` takes both and returns None rather
than raising, so the route turns a cross-user id into a 404 and the caller cannot tell a
wrong id from someone else's id.

⚠️ CORRECTED 2026-10-16 — THIS SAID THE OPPOSITE OF WHAT THE FILE DOES. It read: "NO
ORDER IS WRITTEN. E5 ends this slice at `review`. There is no approve function here,
deliberately — a stub would read as an intention the slice does not carry out." True of
slice E5; `approve` landed on 2026-10-13 and has written every Opas order since. The
sentence survived three dispatches that changed what `approve` does, which is the §11
shape: a file's own account of itself is tested by nobody and read by everybody.

⚠️ `approve` WRITES A SALES ORDER AND IT IS NOW `confirmed` (James's step 3, 2026-10-16,
superseding D1). What that means for the end-of-day batch, and what still creates drafts,
is in that function's docstring.
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import asdict
from datetime import date, datetime, timezone
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
from app.services.capture.approval import describe_approve_effect
from app.services.capture.typed_extraction import (
    EXTRACTOR,
    evaluate_typed,
    extract_text,
    segments,
)
from app.services.capture import why
from app.services.capture.schema import CREMATION_EQUIPMENT_ROW_LABEL

logger = logging.getLogger(__name__)

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


#: The status Opas Approve gives a new order, superseding D1 of 2026-10-13.
#:
#: ⚠️ IT IS ASSERTED AGAINST THE BATCH'S OWN LIST RATHER THAN SPELLED OUT TWICE. The
#: whole point of step 3 is that this value is now INSIDE
#: `draft_invoice_service.INVOICEABLE_STATUSES` — the order is meant to be billable once
#: its service date arrives. A literal here plus a literal there is two places for the
#: spine to drift; `test_approve_confirms.py` pins the membership.
CONFIRMED_ON_APPROVE = "confirmed"


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
    db: Session,
    *,
    company_id: str,
    user_id: str,
    opening_line: str | None = None,
    prefill: dict[str, object] | None = None,
) -> CaptureSession:
    """Create a session, feeding the opening line through extraction if one was given.

    ⚠️ `prefill` IS WHAT A PANE CHOSE, AND IT IS STORED RATHER THAN APPLIED ONCE. Writing
    it into `values` here is what the bug was: `start` left `full_text` as None, the
    client's next debounced `set_text` arrived with whatever was in the BAR — nothing, on
    a fresh bar — and `values` was rebuilt from an empty string. Reproduced 2026-10-24:
    `start(opening_line="order Johnson Funeral Home ")` gives
    `funeral_home='Johnson Funeral Home'`, and the very next `set_text("")` gives None.

    ⚠️ AND THE CLIENT GUARD COULD NOT HAVE SAVED IT. `CapturePane` skips the re-extract
    when `state.full_text === text`, but `start` goes through `add_line`, which leaves
    `full_text` NULL — so `null === ""` is false and the wipe always fired.
    """
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
    if prefill:
        row.prefill = dict(prefill)
    db.add(row)
    db.flush()
    if opening_line and opening_line.strip():
        add_line(db, row.id, company_id=company_id, user_id=user_id, line=opening_line)
        db.refresh(row)
        # ⚠️ RE-APPLIED AFTER `add_line`, because `add_line` rebuilds `values` from the
        # line and does not know about prefills. Harmless when the line names the same
        # home — it is the same value — and necessary when it does not.
        if prefill:
            values = dict(row.values or {})
            for field_id, value in prefill.items():
                values.setdefault(field_id, value)
            row.values = values
            db.flush()
    # ⚠️ A PREFILL IS ONE OF THE SOURCES JAMES NAMES ("from extraction, prefill, a
    # default such as burial vs urn, or a derived value"), so a funeral home the
    # Customer Pane filled and the person then changed IS a change worth asking about.
    if row.values:
        why.remember(row, dict(row.values),
                     source=why.SOURCE_PREFILL if prefill else why.SOURCE_EXTRACTION)
        db.flush()
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

    ex = extract_text(db, tenant_id=company_id, text=body, resolutions=resolutions,
                      prefill=row.prefill)

    # ⚠️ WHAT OPAS PROPOSED IS REMEMBERED HERE, BEFORE `full_text` IS OVERWRITTEN, and
    # the order matters: `is_continuation` needs the text as it WAS. Refreshed while the
    # person is still typing, frozen the moment they go back and change a word — which
    # is the only way to know later that Opas had read Monticello. See `capture/why.py`.
    why.remember(
        row, ex.values,
        continuing=why.is_continuation(row.full_text, text),
        switch_fields=frozenset(sw.field_id for sw in ex.switches),
    )

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


def load_for_user(
    db: Session, session_id: str, *, company_id: str, user_id: str
) -> CaptureSession:
    """The session, for its own owner. Public because the routes need the ROW.

    ⚠️ IT IS `_load` UNDER A PUBLIC NAME, NOT A SECOND LOOKUP. The "why?" endpoint needs
    `decision_id` and `opas_proposed` off the row, and a route reaching into `_load`
    would be reaching past the underscore that says this module owns the query. One
    query, one tenant-and-user filter, one place that raises `SessionNotFound`.
    """
    return _load(db, session_id, company_id=company_id, user_id=user_id)


def attach_decision(
    db: Session, session_id: str, *, company_id: str, user_id: str, decision_id: str,
) -> None:
    """Link the session to the decision row its opening sentence wrote.

    ⚠️ ONCE, AND NEVER OVERWRITTEN. `record_capture_open` fires on the FIRST text a
    session receives, so this should run once — but a retry or a second tab must not
    repoint an answered question at a different row.

    ⚠️ AND IT SWALLOWS A MISSING SESSION. The caller is already past the write it cared
    about; failing the request because the LOG could not be linked would invert the
    rule that the log must not break what it observes.
    """
    try:
        row = _load(db, session_id, company_id=company_id, user_id=user_id)
    except SessionNotFound:
        return
    if row.decision_id is None:
        row.decision_id = decision_id
        db.flush()


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
            db, tenant_id=company_id, text=row.full_text, resolutions=resolutions,
            prefill=row.prefill,
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
            db, tenant_id=company_id, text=row.full_text, resolutions=resolutions,
            prefill=row.prefill,
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


def answer(
    db: Session, session_id: str, *, company_id: str, user_id: str,
    field_id: str, value: str,
) -> tuple[CaptureSession, str | None]:
    """Record a picked answer, and clear whatever it just made wrong.

    Returns the session and the one-line note, or None when nothing was cleared.

    ⚠️ A PILL PICK IS A RESOLUTION, THE SAME AS A NUMBERED PICK. James, 2026-10-27:
    "A pick is a durable answer like today's click-made picks." So this writes to
    `resolutions` for exactly the reason `choose` does — under whole-text
    re-extraction a value written into `values` is erased by the next keystroke,
    because the next read rebuilds `values` from the text.

    ⚠️ AND IT IS A SEPARATE ENTRY POINT FROM `choose` RATHER THAN A WIDENING OF IT.
    `choose` settles a PENDING PICK: it validates the index against options the
    extractor produced, and a pill is not one of those — it is an answer to a question
    about a field that is simply MISSING, with no ambiguity to settle. Folding them
    together would mean `choose` accepting an index with no pick to index into, which
    is the path that would silently accept anything.

    ⚠️ THE FIELD MUST BE ONE THE SCHEMA ASKS FOR. An unknown field_id is refused
    rather than stored: `resolutions` is read by `extract_text` on every re-read, and a
    key nothing consumes would sit there permanently, invisible and inert.
    """
    row = _load(db, session_id, company_id=company_id, user_id=user_id)

    known = {f.field_id for f in capture.template_for(capture.SALES_ORDER)}
    if field_id not in known:
        raise ValueError(f"{field_id} is not a field this capture asks for")

    resolutions = dict(row.resolutions or {})
    resolutions[field_id] = value

    # ⚠️ CLEARED BEFORE THE RE-EXTRACTION, not after, so the extraction runs against
    # the resolutions the order actually has. Clearing afterwards would re-extract with
    # the stale answer in force, and the response would carry values the note says
    # were removed.
    from app.services.capture.clears import clear_what_no_longer_fits

    before = set(resolutions)
    resolutions, note = clear_what_no_longer_fits(
        db, company_id=company_id, resolutions=resolutions, changed_field=field_id,
    )
    # ⚠️ WHICH KEYS WENT, CAPTURED BEFORE `row.resolutions` IS REASSIGNED. My first
    # version computed this from `row.resolutions` AFTER the assignment below, which is
    # a symmetric difference of a dict with itself — always empty, so the line path
    # silently cleared nothing while the note said it had. Found by re-reading rather
    # than by a test, because no test exercises the line path's clearing.
    cleared_keys = before - set(resolutions)
    row.resolutions = resolutions

    # ⚠️ ANSWERING A FIELD RETIRES ITS SWITCH, the same as `choose`. An offer surviving
    # its own resolution would invite the director to undo the click they just made.
    row.switches = [
        sw for sw in (row.switches or []) if sw.get("field_id") != field_id
    ]

    if row.full_text is not None:
        # ⚠️ RE-EXTRACTED THROUGH THE SAME CALL THE NEXT PAUSE WILL MAKE, exactly as
        # `choose` does, so the response cannot disagree with what the pane is about
        # to be sent.
        ex = extract_text(
            db, tenant_id=company_id, text=row.full_text, resolutions=resolutions,
            prefill=row.prefill,
        )
        row.values = dict(ex.values)
        row.unrecognized = list(ex.unrecognized)
        row.pending_picks = [asdict(pk) for pk in ex.picks]
    else:
        # ⚠️ THE LINE PATH, which has no whole text to re-extract from — a session
        # captured line by line. E6 says that path does not change, so this writes the
        # value directly and removes exactly the keys the clearing removed.
        values = dict(row.values or {})
        values[field_id] = value
        for cleared in cleared_keys:
            values.pop(cleared, None)
        row.values = values

    db.flush()
    return row, note


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
    asking: str | None = None,
) -> dict:
    """The session plus its evaluated capture state and rendered rows.

    ⚠️ `asking` IS THE OFFICE CLICKING A ROW, AND IT EXISTS BECAUSE THE FIRST VERSION
    ONLY MOVED THE OUTLINE. "Clicking a row asks that question again" (James,
    2026-10-27) — and a client-side focus changed which row was outlined while Opas
    went on asking the previous question. The sentence and the pills are composed HERE,
    so the field has to reach here.

    ⚠️ IT IS A PARAMETER, NOT STATE. Nothing about the ORDER changes when somebody
    clicks a row, so there is nothing to store — and a column would mean a focus
    surviving a reload and holding the pane on a question the office had moved past.
    The client sends it while the row is focused and stops when it is answered.

    ⚠️ AND IT IS IGNORED UNLESS IT IS A FIELD STILL BEING ASKED. See `_guided`.

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
        surface, resolved, rendered_answers, done_signal=said_done,
        conflicted_field_ids=frozenset(conflicted),
    )

    # ⚠️ RESOLVED ONCE AND SHARED WITH `_guided`, because two callers asking the same
    # question of the catalogue can disagree. The row label and the chip must either
    # both say cremation or both not — a pane reading "Equipment" with a Cremation chip
    # above it is the self-contradicting response this file already records twice.
    #
    # ⚠️ AND IT IS FIVE TABLE READS, so doing it twice on every keystroke is the cost
    # the `FormResolver` was added to avoid in the first place.
    vault_is_cremation = _is_cremation(db, company_id, row)

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
        # ⚠️ WHAT APPROVE WILL DO, SAID BEFORE IT IS PRESSED (James's step 3, item 3).
        # Approve now creates a CONFIRMED order, so the press is the moment an order
        # enters the end-of-day batch's net — the Review is the last place anyone sees
        # it first. Derived from the same `appraisal` the button is gated on, so the
        # promise and the press cannot disagree; None when the order is not approvable.
        "approve_effect": (
            describe_approve_effect(db, company_id, answers, appraisal)
            if appraisal
            else None
        ),
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
            # ⚠️ THE SUBJECT WAS COMPUTED AND THROWN AWAY HERE, AND THAT IS WHY THE
            # REVIEW HAD NO DECEASED NAME. The summary surface puts the decedent in a
            # `SubjectSlot` — "Smith" over "1948 — 2026" above the grid, from the
            # prototype — and this serializer only ever sent `rows`. So the pane could
            # not render it however it tried: the value never crossed the wire.
            # Measured 2026-10-14 from James's Review screenshot.
            "subject_primary": rendered.subject_primary,
            "subject_secondary": rendered.subject_secondary,
            "rows": [
                {
                    "row_id": r.row_id,
                    # ⚠️ THE EQUIPMENT ROW IS RELABELLED ON A CREMATION, and it has
                    # to happen here rather than on the Row: `Row.label` is static and
                    # the surface layer cannot see the vault's form. The prototype does
                    # the same flip — `f==='equip'&&k==='urn'?'Cremation setup':LABEL[f]`
                    # — and it matters because "Equipment" over three cremation setups
                    # reads as the same question with options missing.
                    "label": (
                        CREMATION_EQUIPMENT_ROW_LABEL
                        if (vault_is_cremation and r.row_id == "cemetery_equipment")
                        else r.label
                    ),
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
                    # ⚠️ EVERY FIELD THE ROW SOURCES, for the row -> span link. The
                    # pointer cannot reach a span (the textarea owns it), so the pane
                    # row is the handle and it needs its own field ids to be one.
                    "field_ids": list(r.field_ids),
                    # ⚠️ SENT 2026-10-27 SO A CLICK CAN ASK AGAIN. It was computed by
                    # `resolve_surface` and dropped by this serializer — the same shape
                    # as `subject_primary`, which was also computed and never sent and
                    # is why the Review had no deceased name. A row the office is told
                    # to click needs to carry what the click means.
                    "edit_target": r.edit_target,
                }
                for r in rendered.rows
            ],
        },
        # ⚠️ THE LABELS FOR THE BAR'S OWN SENTENCE. "Still need: service date" is
        # built from the same missing set the rows colour from, so the bar cannot
        # name something the pane is not highlighting.
        "missing_labels": list(_missing_labels(state)),
        # ⚠️ ONE QUESTION, AND IT REPLACES "Still need: ..." IN THE BAR (James,
        # 2026-10-15). `missing_labels` stays because the Approve BLOCKERS still name
        # every gap at once — that is a report and should be — but the line above the
        # bar is a conversation and asks for one thing. Both read the same `missing`
        # set, so the bar cannot ask for something the pane is not highlighting.
        "next_question": _next_question(state.missing),
        # ⚠️ EVERYTHING GUIDED CAPTURE NEEDS, COMPOSED IN ONE PLACE AND READ ONCE.
        # The question's FIELD, its one-line hint, the answers to offer, and whether
        # the vault has made this a cremation. James, 2026-10-27: "THE NEXT QUESTION
        # comes from the engine (server-side, the capture schema), not the client".
        #
        # ⚠️ ONE CALL, NOT FOUR, because all four readings must describe the SAME
        # field. Composed separately they could disagree — a sentence about the
        # cemetery over pills for the vault — and nothing would be obviously wrong
        # on either side.
        **_guided(db, company_id, row, state, vault_is_cremation, asking),
        # ⚠️ THE SPANS, IN WHOLE-TEXT COORDINATES, WITH THEIR SEQUENCE. James: "Spans
        # apply only to the exact text they were computed for (sequence number).
        # While typing, stale spans are hidden, never misplaced." The sequence is the
        # TEXT ITSELF rather than a counter: a client that has moved on by one
        # keystroke can compare what it sent against `spans_for_text` and drop the
        # lot, with no shared counter to get out of step.
        "spans": _spans_payload(db, row, company_id, conflicts),
        "spans_for_text": _session_text(row),
        # ⚠️ TRANSIENT AND FALSE ON A PLAIN READ. It is the answer to "did somebody
        # just try to finish this order", which is what turns the rows amber — not a
        # property of the order. A typed completion phrase is detected on the SERVER,
        # so the client cannot know about that attempt unless the response says so.
        "completion_attempt": bool(completion_attempt),
        # ⚠️ THE ONE QUESTION OPAS ASKS AFTER AN APPROVE, OR ABSENT. "once, right after
        # you approve, and only if you changed something Opas had filled in. It never
        # asks while you're typing" (James, 2026-10-26) — so this is None until
        # `sales_order_id` is set, which is what "after you approve" means in data.
        #
        # ⚠️ AND IT IS COMPUTED ON EVERY READ RATHER THAN STORED, so a reload after an
        # approve still shows the question — and `already_answered` is what stops it
        # coming back once the person has answered or skipped. The alternative, a flag
        # on the session, would be a second place saying whether a record exists.
        **(
            {"ask_why": asked}
            if (asked := (
                None if why.already_answered(db, row) else why.ask_payload(row)
            )) is not None
            else {}
        ),
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


def _as_datetime_midnight(value: object):
    """The same day `_as_date` would return, as a UTC-midnight timestamp, or None.

    ⚠️ DERIVED FROM `_as_date` RATHER THAN RE-PARSING. `sales_orders.required_date` is a
    `DateTime` and `scheduled_date` is a `Date`, and the two must name the SAME DAY —
    `approve` writes both from one answer. A second parser would be a second set of
    year-vs-date edge cases to keep in step, and the one that matters ("1948" is not a
    date) is already handled once, carefully, up there.

    ⚠️ RETURNS None EXACTLY WHEN `_as_date` DOES, which is the property the batch depends
    on: its `COALESCE(scheduled_date, date(required_date))` must not find a date in one
    column and nothing in the other, or an order with no service date would still be
    selected through the fallback.
    """
    from datetime import datetime as _datetime, time as _time, timezone as _timezone

    d = _as_date(value)
    if d is None:
        return None
    return _datetime.combine(d, _time.min, tzinfo=_timezone.utc)


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


#: What Opas asks when a phrase matched more than one thing.
#:
#: ⚠️ THE PROTOTYPE'S OWN WORDING: `ask:\`Which one did you mean by \u201c${p.text}\u201d?\``.
#: It quotes the phrase back because the director typed something ambiguous and needs
#: to see WHICH word is in question — unlike a miss, where quoting reads as "that is
#: not a thing" and was ruled out on 2026-10-23.
DID_YOU_MEAN_BY = "Which one did you mean by \u201c{phrase}\u201d?"

#: ⚠️ THE SECOND HALF IS THE PART THAT MATTERS AND IT IS THE PROTOTYPE'S: "the rest of
#: what you typed stays put". A director who sees a choice list mid-sentence has to know
#: that answering it will not discard the rest of the order.
PICK_HINT = "More than one matches. Pick one, and the rest of what you typed stays put."


def _is_cremation(db, company_id: str, row) -> bool:
    """Has the chosen vault made this order a cremation?

    ⚠️ FAILS CLOSED TO `False`, AND "NO VAULT YET" IS ALSO False. An order whose vault
    cannot be placed is not thereby a cremation; `vault_form.form_of` already makes
    that distinction and this only has to not undo it.
    """
    try:
        from app.services.capture.vault_form import form_of

        return form_of(
            db, tenant_id=company_id, vault=(row.values or {}).get("vault")
        ).is_cremation
    except Exception:  # pragma: no cover - the pane renders without the chip
        logger.warning("could not resolve the vault's form", exc_info=True)
        return False


def _guided(
    db, company_id: str, row, state, cremation: bool, asking: str | None = None,
) -> dict:
    """The question's field, its hint, its pills, and the cremation chip.

    ⚠️ IT DOES NOT READ THE ORDER HISTORY ITSELF, AND MY FIRST VERSION DID. `pills_for`
    needs that history to rank the answers for four fields and needs nothing for the
    rest — `deceased_name`, the dates, `grave_location` can never carry a pill. This is
    called from `read_state` on a ~350ms debounce while the director types, and
    `load_facts` is a full pass over the tenant's sales orders with a correlated
    subquery per row, so an eager read here charged every keystroke for a question that
    could not use it. `pills_for` decides and returns early.

    ⚠️ FAILS OPEN, AND THAT IS A DELIBERATE CHOICE RATHER THAN DEFENSIVENESS. These
    four keys are an ADDITION to a response the pane already renders without them —
    `next_question` and the five sets are what the pane needs to work. A pill query
    that raises must not take the capture pane down with it, so the question still
    goes out and the pills are simply absent. The 2026-10-12 blank-pane defect was the
    other arrangement: one key an older server omitted, and nothing rendered.

    ⚠️ IT LOGS. An exception swallowed silently here would make missing pills
    indistinguishable from a question that has no pills — which is a real state for
    `deceased_name` — so the two must be told apart in the log if nowhere else.
    """
    from app.services.capture.schema import guided_field, question_for, hint_for
    from app.services.capture.schema import (
        CREMATION_CHIP,
        DONE_HINT,
        DONE_QUESTION,
        NEW_ORDER_ACTION,
        NEW_ORDER_PILL_LABEL,
        NEW_ORDER_PILL_SUB,
        REVIEW_ACTION,
        REVIEW_PILL_LABEL,
        REVIEW_PILL_SUB,
    )

    # ⚠️ THE DONE STATE IS FIRST, BEFORE ANY QUESTION IS COMPUTED. James's dispatch of
    # 2026-10-28, clause 2: once the order is approved the pane says "Order confirmed."
    # with a pill that starts another. An approved session has no next question — every
    # field is answered — so `guided_field` would return None and the pane would show
    # the ready state ("That's everything.") on an order that is already an order.
    #
    # ⚠️ AND IT IS SERVED RATHER THAN DECIDED BY THE CLIENT, because the session is
    # still there to be read: `approve` leaves `status == "approved"` and the pane
    # renders `capture-approved` from it. The IDLE state is the opposite case — no
    # session exists — so that one cannot come from here and does not.
    #
    # ⚠️ NO QUOTE BRANCH, PER CLAUSE 3, AND IT IS MEASURED NOT ASSUMED — see the
    # comment on `DONE_QUESTION` in `schema.py`. `object_type` has one writer and it
    # is hard-coded to `sales_order`.
    if getattr(row, "status", None) == "approved":
        return {
            "question_field_id": None,
            "question": DONE_QUESTION,
            "question_hint": DONE_HINT,
            "pills": [{
                "act": NEW_ORDER_ACTION,
                "value": NEW_ORDER_ACTION,
                "label": NEW_ORDER_PILL_LABEL,
                "sub": NEW_ORDER_PILL_SUB,
            }],
            "cremation": CREMATION_CHIP if cremation else None,
        }

    # ⚠️ `guided_field`, NOT `next_field(state.missing)`, AND THE DIFFERENCE IS FOUR
    # QUESTIONS. `missing` is required-and-unanswered, so the four fields that are
    # never required — equipment, the Legacy series, the Legacy print and the Life's
    # Reflections symbol — were never asked at all. See `guided_field`.
    field_id = guided_field(state)

    # ⚠️ THE CLICKED ROW WINS, AND ONLY WHILE IT IS STILL BEING ASKED. That is the
    # prototype's own rule — `if(S.focus&&applicable(S.focus)&&!S.f[S.focus])return
    # S.focus` — so a click on an ANSWERED row re-asks it (the office wants to change
    # it) and a click on a field the schema does not ask for is ignored.
    #
    # ⚠️ VALIDATED AGAINST THE SETS RATHER THAN TRUSTED. `asking` arrives from a query
    # string; accepting it unchecked would let a stale or hand-typed value put the pane
    # on a question this order does not have — "Which Legacy print?" on an order with
    # no personalization. The three sets below are every field the schema asks about.
    if asking is not None:
        askable = (
            set(state.missing)
            | set(state.unanswered_optional)
            | set(state.answered)
        )
        if asking in askable:
            field_id = asking

    # ⚠️ AN AMBIGUITY OUTRANKS A GAP, AND THE PILLS ARE THE SAME PILLS. James,
    # 2026-10-27: "The ambiguity choice list becomes these same pills." A pending pick
    # is the one thing that needs the director's hand — the same ordering
    # `captureVoice` already uses, where the pick comes before everything else.
    #
    # ⚠️ AND ITS OPTIONS ARE THE SERVER'S OWN, NOT RANKED. A pick's options are the
    # candidates the extractor found for a phrase the director actually typed; ranking
    # them by what this home usually orders would reorder an answer to "which of these
    # two did you mean" by popularity, which is a different question.
    picks = list(row.pending_picks or [])
    if picks:
        pick = picks[0]
        return {
            "question_field_id": pick["field_id"],
            "question": DID_YOU_MEAN_BY.format(phrase=pick.get("phrase") or ""),
            "question_hint": PICK_HINT,
            "pills": [
                {"value": value, "label": label}
                for value, label in pick.get("options", [])
            ],
        }

    out: dict = {"question_field_id": field_id}
    try:
        from app.services.capture.pills import pills_for

        values = dict(row.values or {})
        if cremation:
            # ⚠️ THE CHIP IS A SENTENCE FROM THE SERVER like every other label, and
            # `via` travels with it because the five ways of establishing a cremation
            # are not equally strong — on sunnycrest today it is the product's own
            # name. A reader who needs to know can; the pane just shows the chip.
            from app.services.capture.vault_form import form_of

            out["cremation"] = {
                "label": CREMATION_CHIP,
                "via": form_of(
                    db, tenant_id=company_id, vault=values.get("vault")
                ).via,
            }
        out["question"] = question_for(field_id, cremation=cremation)
        hint = hint_for(field_id, cremation=cremation)
        if hint:
            out["question_hint"] = hint
        if field_id is not None:
            # ⚠️ `facts` IS NOT PASSED, DELIBERATELY, AND THAT IS A CHANGE FROM MY FIRST
            # VERSION. It read `load_facts(db, company_id)` here and handed it down —
            # correct for a caller asking about SEVERAL fields, and this one asks about
            # exactly one. So the eager read made every keystroke pay for a full pass
            # over the tenant's sales orders even when the question was `deceased_name`,
            # which can never have a pill. `pills_for` now decides, and returns early
            # for the fields that cannot use history.
            out["pills"] = [
                pill.as_dict()
                for pill in pills_for(
                    db,
                    tenant_id=company_id,
                    field_id=field_id,
                    values=values,
                    resolved_fields=state.resolved_fields,
                    today=date.today(),
                )
            ]

        # ── the Review action ───────────────────────────────────────────────────────
        #
        # ⚠️ ITS CONDITION IS "EVERYTHING NEEDED IS ANSWERED", WHICH IS HIS WORDING AND
        # NOT "nothing left to ask". James, 2026-10-27: "When everything needed is
        # answered, Opas says 'That's everything.' with a Review pill (⌥1) and Enter."
        # `missing` empty is "everything needed"; optional questions can still remain,
        # and `guided_field` still asks them.
        #
        # ⚠️ SO IT CAN SIT BESIDE ANSWER PILLS, and that combination is the point: once
        # the order is reviewable the office must be able to finish from the question
        # they are on, without answering about chairs first. In the prototype the two
        # conditions coincide because its model has no optional fields; ours does, and
        # collapsing them would either trap the office on an optional question or stop
        # equipment ever being asked.
        #
        # ⚠️ AN ACTION, NOT AN ANSWER — it carries `act`, and the client must route it
        # to what Enter does. Through `/answer` it would try to store "review" into a
        # field.
        #
        # ⚠️ AND IT GOES LAST so the ⌥ numbers of the real answers do not shift as the
        # order becomes reviewable. A pill whose key changes under the director's hand
        # is worse than one further along the row.
        if state.is_complete:
            out["pills"] = [*out.get("pills", []), {
                "act": REVIEW_ACTION,
                "value": REVIEW_ACTION,
                "label": REVIEW_PILL_LABEL,
                "sub": REVIEW_PILL_SUB,
            }]
    except Exception:
        logger.warning("guided capture extras unavailable for field %r", field_id,
                       exc_info=True)
    return out


def _next_question(missing) -> str:
    """⚠️ IMPORTED AT CALL TIME, matching `_missing_labels` just below, which imports
    `PLATFORM_DEFAULT_FIELDS` the same way. `schema` is a heavy module and this file
    is on the session hot path."""
    from app.services.capture.schema import next_question

    return next_question(missing)


def _session_text(row) -> str:
    """The text this session actually has.

    ⚠️ A TYPED-PANE SESSION HAS `full_text`; A LINE-CAPTURED ONE HAS LINES AND NONE.
    The done-signal derivation a few lines up reads both for exactly this reason, and
    spans must agree with it — reporting spans against `full_text` for a session that
    has none would quietly return an empty list on the older pane rather than saying
    there is nothing to mark.
    """
    return row.full_text or ""


def _spans_payload(db, row, company_id: str, conflicts) -> list[dict]:
    """The claimed spans for this session's text, with conflicts marked.

    ⚠️ CONFLICT STATE IS APPLIED HERE, NOT IN `extract_text`, because conflicts are
    not a property of the TEXT — they come from evaluating the answers against the
    vault's availability, which the extractor deliberately does not do. A span whose
    field is in conflict is re-stated rather than re-computed, so the amber and the
    blocker always name the same field.
    """
    text_value = _session_text(row)
    if not text_value:
        return []
    from app.services.capture.typed_extraction import extract_text

    ex = extract_text(db, tenant_id=company_id, text=text_value)
    conflicted = {c.field_id for c in (conflicts or ())}
    out = []
    for sp in ex.spans:
        state = sp.state
        if state == "captured" and any(f in conflicted for f in sp.field_ids):
            state = "conflict"
        out.append({
            "start": sp.start, "end": sp.end, "state": state,
            "field_ids": list(sp.field_ids),
        })
    return out


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

    ⚠️ STATUS `confirmed`, BY JAMES'S STEP-3 DISPATCH (2026-10-16). **THIS SUPERSEDES
    DECISION D1 OF 2026-10-13**, which made it `draft`, and the supersession is
    recorded in DECISIONS rather than only here.

    D1's reason was specific and it is gone. The end-of-day batch used to select on
    `scheduled_date <= today` with no regard for whether the service had happened, so
    an order that was merely CONFIRMED could be marked delivered and invoiced on the
    afternoon of its service date — or, before the clock fix, at 2 PM Eastern, ahead
    of an afternoon service. `draft` was the only thing standing outside that net.
    Step 2 moved the gate: the batch now acts only once the service date has arrived
    in the TENANT'S local time, and the three-status spine plus
    `sales_order_transitions` means nothing skips ahead. With the hazard removed, the
    draft was costing a step rather than buying safety.

    ⚠️ WHAT STILL CREATES A DRAFT, because "drafts remain only for a capture saved
    partway" is a claim about this file and is only true of Opas:

        capture saved partway   `capture_sessions` in `capturing` / `review`. ⚠️ NOT A
                                SALES ORDER AT ALL — no `sales_orders` row exists until
                                this function runs, and abandoning leaves an
                                `abandoned` session and no order.
        Undo confirm            `confirmed -> draft` via the PATCH path, refused once
                                the order is delivered or invoiced
                                (`sales_order_transitions.undo_confirm_blocker`).
        every non-Opas creator  `sales_service.create_sales_order` and the quote
                                conversion still create drafts, unchanged. This
                                dispatch moved OPAS APPROVE, not the order model's
                                default, and the office's own New Order form is
                                untouched.

    ⚠️ "APPROVE SETS OFF NOTHING DOWNSTREAM" IS RETIRED (James, 2026-10-16). It was a
    true and useful rule for as long as Approve produced a `draft` — a row nothing acted
    on. Once Approve confirms, it is not available as a property: confirming IS what
    sets the order in motion. The replacement rule is parity — an order confirmed from
    Opas behaves exactly like one confirmed any other way — which is why the delivery
    hook is fired at the bottom of this function and why
    `test_the_two_confirm_paths_do_not_diverge` exists.

    ⚠️ `required_date` IS WRITTEN FOR BOTH CONSUMERS: the batch's
    `COALESCE(scheduled_date, date(required_date))`, and the hook, which dates the
    delivery from it. See the field comments below.

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
        # ⚠️ `confirmed`, SUPERSEDING D1 — see the docstring. Imported from the batch
        # rather than written as a literal so the two cannot drift: this value must be
        # IN `draft_invoice_service.INVOICEABLE_STATUSES`, and the test asserts that
        # rather than restating the word.
        status=CONFIRMED_ON_APPROVE,
        order_type="funeral",
        order_date=datetime.now(timezone.utc),
        # ⚠️ THE SERVICE DATE, BY DISPATCH, AND NOW THE ONLY THING KEEPING THIS ORDER
        # OUT OF TONIGHT'S BATCH. While the order was born `draft` the status was the
        # protection; now that it is born `confirmed`, the batch's
        # `SERVICE_DATE <= tenant_today` is. An order approved for next Tuesday is
        # untouched until Tuesday evening *because of this field* — which is why
        # `assess_approval` refuses to approve without it (James's step 3, item 4).
        scheduled_date=_as_date(answers.get("service_date")),
        # ⚠️ THE SAME DAY, WRITTEN TWICE ON PURPOSE, AND THIS IS THE FIELD THE DELIVERY
        # HOOK READS (James's step 2, item 3). The two columns are not redundant — they
        # have different types and different consumers:
        #
        #   scheduled_date  Date       the service date. First branch of the batch's
        #                              COALESCE; what the scheduling surfaces read.
        #   required_date   DateTime   what `order_integration_service.on_order_confirmed`
        #                              dates the auto-created delivery from
        #                              (`requested_date = order.required_date.date()`),
        #                              and the batch's COALESCE fallback for pre-Opas
        #                              orders that carry only this one.
        #
        # ⚠️ LEAVING IT NULL WAS A LATENT BUG, not a saving. Measured 2026-10-16: with
        # `auto_create_delivery_from_order` enabled, a captured order would have produced
        # a delivery with `requested_date = NULL` — a stop on nobody's day. The flag is
        # OFF for Sunnycrest today, so nothing had surfaced it; turning the flag on
        # without this would have.
        #
        # ⚠️ CORRECTED 2026-10-16 — THIS COMMENT ASSERTED SOMETHING FALSE AND THE
        # DIVERGENCE TEST CAUGHT IT. It read: "Midnight in the TENANT's zone would be
        # more precise, but this column is consumed only as `.date()`, and a date-only
        # value with a UTC midnight stamp round-trips to the same day for every zone
        # from UTC-11 to UTC+13."
        #
        # It does not. Midnight UTC is the PREVIOUS EVENING in every negative offset —
        # most of the Americas — so `.date()` read on an Eastern session returns the day
        # BEFORE the service. Measured: a service on 2026-10-23 produced a delivery
        # requested for 2026-10-22.
        #
        # The value is left as midnight UTC because the fix belongs at the consumer:
        # `order_integration_service` now reads `scheduled_date`, a plain `Date` that
        # has no zone and cannot shift, and falls back to this column only for orders
        # that carry nothing else. Changing what is stored here would fix one consumer
        # and leave the next one to rediscover the same trap.
        required_date=_as_datetime_midnight(answers.get("service_date")),
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

    # ⚠️ THE DELIVERY HOOK, BY JAMES'S RULING OF 2026-10-16: "an order confirmed from
    # Opas behaves exactly like one confirmed any other way. When
    # auto_create_delivery_from_order is turned on for any tenant, both paths must
    # create the delivery."
    #
    # This is the same call `sales_service.update_sales_order` makes when a status
    # becomes `confirmed` (`sales_service.py:660-667`), so `confirmed` means one thing
    # however the order got there.
    #
    # ⚠️ IT WAS ADDED, BACKED OUT, AND RE-ADDED, AND THE MIDDLE STEP IS WORTH KNOWING.
    # It came out because `tests/test_approve_triggers_nothing.py` carried an explicit
    # rule that Approve must not set off anything downstream — a rule that belonged to
    # the DRAFT era, when Approve produced a row nothing acted on. James has now retired
    # it: once Approve confirms, "sets nothing in motion" is no longer available as a
    # property, because confirming IS the thing that sets the order in motion.
    #
    # ⚠️ AFTER `db.flush()` AND THE LINES, DELIBERATELY. The hook reads `order.id`,
    # `order.required_date` and `order.ship_to_*`, and it COMMITS when it creates a
    # delivery. Firing it before the lines existed would commit a priced order with no
    # lines on it.
    #
    # ⚠️ SWALLOWED TO A LOG LINE, EXACTLY AS THE PATCH PATH DOES. An integration failure
    # must not lose the order the office just approved. The parity is the point: if this
    # ever stops matching `update_sales_order`'s handling,
    # `test_the_two_confirm_paths_do_not_diverge` is what fails.
    try:
        from app.services import order_integration_service

        order_integration_service.on_order_confirmed(db, order)
    except Exception as exc:
        logger.error(
            "Order integration hook failed for approved order %s: %s", order.id, exc
        )

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
