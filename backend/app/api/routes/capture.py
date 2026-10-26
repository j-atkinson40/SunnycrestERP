"""Typed order capture — the endpoints the Opas pane talks to.

⚠️ THE FIRST ENDPOINTS THAT RETURN `CaptureState`. Before this, nothing under
`app/api/routes/` referenced the capture engine at all — it was reachable only from
`call_extraction_service`, driven by the RingCentral webhook.

⚠️ SEVEN ENDPOINTS. The fifth, `PUT .../text`, is the one the typed pane actually drives:
it re-reads the WHOLE text on every pause rather than appending a line. `POST .../lines`
is kept and unchanged — it is the path every existing session was captured through, and
appending is right for a source that arrives one utterance at a time.

⚠️ `PUT`, NOT `POST`, AND THAT IS THE CONTRACT NOT A PREFERENCE. The request sets the
text to a value; sending the same text twice must leave the session identical. A `POST`
would read as "add this", which is what the line endpoint does and what this must not do.

`GET` exists because a session must survive a tuck — the pane is re-rendered from the
server rather than from client memory, so tucking and reopening cannot lose a half-typed
order.

⚠️ NO APPROVE ENDPOINT, BY RULING (E5). The slice ends at a read-only summary. A stub
that returned 501 would read as an intention this slice does not carry out, and the next
reader would take its presence as evidence the write path exists.

⚠️ TENANT AND USER SCOPING IS IN THE SERVICE, NOT HERE. Every handler passes
`current_user.company_id` and `current_user.id` down; the service filters on both and
raises `SessionNotFound` for a wrong id and for another user's id alike, so a 404 cannot
be used to prove a session exists.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.capture import session_service
from app.services.capture import rule_draft, why
from app.services.order_list import decision_log, rulebook

router = APIRouter()


#: Fields a pane may seed. One entry, deliberately — widen it when a pane needs to.
#:
#: ⚠️ A SEEDED VALUE IS NOT VALIDATED AGAINST THE TENANT'S VOCABULARY HERE, because the
#: extractor is what knows the tenant's names and it re-reads the whole text on the next
#: pause anyway. What this list stops is the SHAPE of the attack: seeding `total`, or
#: `service_date`, or anything the office would read as measured.
PREFILLABLE_FIELDS = frozenset({"funeral_home"})


class StartRequest(BaseModel):
    #: ⚠️ OPTIONAL, AND FED THROUGH EXTRACTION WHEN PRESENT. The prototype starts a
    #: capture and immediately feeds the same line, which is what lets "start an order
    #: for Hopkins" capture the funeral home on the opening keystroke.
    opening_line: str | None = Field(default=None, max_length=2000)

    #: What a PANE chose before any text existed — today only `funeral_home`, from the
    #: Customer Pane's "New order".
    #:
    #: ⚠️ WHITELISTED RATHER THAN PASSED THROUGH, AND THAT IS THE POINT. A client able to
    #: seed any field could write a value no extractor produced and no director typed,
    #: which is the thing the whole-text model exists to prevent. Unknown keys are
    #: dropped, not refused: an older bundle sending nothing still works, and a newer one
    #: sending a field this release does not know about must not break the capture.
    prefill: dict[str, str] | None = None

    @field_validator("prefill")
    @classmethod
    def _only_known_fields(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if not v:
            return None
        kept = {
            k: val for k, val in v.items()
            if k in PREFILLABLE_FIELDS and isinstance(val, str) and val.strip()
        }
        return kept or None


#: The scopes the bar can send. 'skipped' is a scope, not an absence — "Esc, or typing
#: something that's clearly a new request, skips it silently (logged as skipped)".
WHY_SCOPES = ("today", "always", "skipped")


class WhyRequest(BaseModel):
    """The answer to "why?", in one or two calls.

    ⚠️ REASON AND SCOPE TRAVEL TOGETHER, which is a shape the CHECK constraint enforces
    (`reason IS NULL OR reason_scope IS NOT NULL`). The bar collects the reason, then
    the scope, and sends both — so a row holding a reason with no scope, which would
    read as a deliberate record of a half-answered question, cannot exist.

    ⚠️ AND `rule_text` IS THE SECOND CALL, not a third field on the first. Sending
    `scope="always"` with no `rule_text` asks for a DRAFT; sending it with one CONFIRMS
    that sentence. One endpoint, two steps, and the person has seen the words either way.
    """

    reason: str | None = Field(default=None, max_length=2000)
    scope: str = Field(min_length=1, max_length=8)
    rule_text: str | None = Field(default=None, max_length=400)

    @field_validator("scope")
    @classmethod
    def _known_scope(cls, v: str) -> str:
        if v not in WHY_SCOPES:
            raise ValueError(f"scope must be one of {WHY_SCOPES}")
        return v


class LineRequest(BaseModel):
    line: str = Field(min_length=1, max_length=2000)


class TextRequest(BaseModel):
    #: ⚠️ EMPTY IS LEGAL. The director clearing the bar is a real edit and must
    #: un-capture everything, so this has no `min_length`. The line endpoint has
    #: `min_length=1` because an empty line is not an utterance.
    text: str = Field(max_length=8000)
    #: ⚠️ THE CLIENT'S SEQUENCE NUMBER, ECHOED BACK UNINTERPRETED. The server does
    #: NOT order by it and does not reject a low one: requests can overtake each
    #: other on the wire, and a server that dropped the "stale" one would be
    #: deciding which of the director's keystrokes counted. The CLIENT holds the
    #: latest number it issued and ignores any response whose `seq` is lower — it
    #: is the only party that knows what the bar currently contains.
    seq: int = Field(default=0, ge=0)


class SwitchRequest(BaseModel):
    field_id: str = Field(min_length=1, max_length=64)
    #: ⚠️ VALIDATED AGAINST THE SERVER'S OWN OFFER in `take_switch`, not accepted on
    #: trust. Without that this is a write path with no vocabulary.
    to_value: str = Field(min_length=1, max_length=200)


class ChooseRequest(BaseModel):
    field_id: str = Field(min_length=1, max_length=64)
    #: 1-based, matching the prototype's digit-key handler.
    index: int = Field(ge=1, le=9)


def _state(
    db: Session, session_id: str, user: User, *, completion_attempt: bool = False
) -> dict:
    try:
        return session_service.read_state(
            db, session_id, company_id=user.company_id, user_id=user.id,
            completion_attempt=completion_attempt,
        )
    except session_service.SessionNotFound:
        raise HTTPException(status_code=404, detail="capture session not found")


@router.post("/sessions")
def start_session(
    body: StartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a typed capture."""
    row = session_service.start(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        opening_line=body.opening_line,
        prefill=body.prefill,
    )
    db.commit()
    return _state(db, row.id, current_user)


@router.post("/sessions/{session_id}/lines")
def add_line(
    session_id: str,
    body: LineRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Type one line into the session."""
    try:
        session_service.add_line(
            db, session_id,
            company_id=current_user.company_id, user_id=current_user.id,
            line=body.line,
        )
    except session_service.SessionNotFound:
        raise HTTPException(status_code=404, detail="capture session not found")
    db.commit()
    return _state(db, session_id, current_user)


@router.put("/sessions/{session_id}/text")
def set_text(
    session_id: str,
    body: TextRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-read the whole typed text. The hot path — one call per pause."""
    # ⚠️ READ BEFORE THE WRITE, because "was this the session's first text" is only
    # answerable beforehand. One row per capture opening, not one per pause.
    #
    # ⚠️ A DIRECT SCOPED QUERY, BECAUSE `session_service.read` DOES NOT EXIST — my first
    # version called it, the AttributeError landed in the `except` below, `first_text`
    # stayed False forever and capture logging SILENTLY NEVER FIRED. Caught by checking
    # the service's exports rather than by any test: a feature that logs nothing and a
    # feature that is switched off look identical from here.
    first_text = False
    try:
        from app.models.capture_session import CaptureSession

        existing = (
            db.query(CaptureSession)
            .filter(
                CaptureSession.id == session_id,
                CaptureSession.company_id == current_user.company_id,
            )
            .first()
        )
        first_text = existing is not None and not (existing.full_text or "").strip()
    except Exception:
        # ⚠️ NOT FATAL AND NOT ASSUMED TRUE. If the pre-read fails we log nothing rather
        # than guess it was the first — a duplicate opening row is worse than a missing
        # one, because it would double-count the phrase in any set built from this table.
        first_text = False
    try:
        row = session_service.set_text(
            db, session_id,
            company_id=current_user.company_id, user_id=current_user.id,
            text=body.text,
        )
    except session_service.SessionNotFound:
        raise HTTPException(status_code=404, detail="capture session not found")
    # ⚠️ READ OFF THE ROW BEFORE THE COMMIT CLEARS THE INSTANCE. A trailing
    # completion phrase is detected on the SERVER, so this flag is the only way the
    # client learns that an attempt happened and the rows should turn amber.
    attempted = bool(getattr(row, "_completion_attempt", False))
    db.commit()
    state = _state(db, session_id, current_user, completion_attempt=attempted)
    # ⚠️ ECHOED, NOT ACTED ON. See `TextRequest.seq` — the client drops stale
    # responses because the client is the only party that knows what is in the bar.
    state["seq"] = body.seq
    if first_text:
        # ⚠️ THE RETURNED ID IS KEPT NOW, AND IT WAS BEING THROWN AWAY. The dispatch of
        # 2026-10-26 says "the decision-log row for that capture gets the reason", and a
        # session had no way back to its own row — `record_capture_open` has always
        # returned the id and nothing read it.
        #
        # ⚠️ BEST-EFFORT, LIKE THE LOG ITSELF. `record_capture_open` returns None when
        # the write failed, and the capture carries on without a link rather than
        # failing: a log that can break the thing it observes is worse than no log.
        decision_id = decision_log.record_capture_open(
            db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            phrase=body.text,
        )
        if decision_id is not None:
            session_service.attach_decision(
                db, session_id,
                company_id=current_user.company_id, user_id=current_user.id,
                decision_id=decision_id,
            )
    return state


@router.post("/sessions/{session_id}/choose")
def choose(
    session_id: str,
    body: ChooseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Settle a numbered pick."""
    try:
        session_service.choose(
            db, session_id,
            company_id=current_user.company_id, user_id=current_user.id,
            field_id=body.field_id, index=body.index,
        )
    except session_service.SessionNotFound:
        raise HTTPException(status_code=404, detail="capture session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return _state(db, session_id, current_user)


@router.post("/sessions/{session_id}/switch")
def take_switch(
    session_id: str,
    body: SwitchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Take the one alternative a switch offered."""
    try:
        session_service.take_switch(
            db, session_id,
            company_id=current_user.company_id, user_id=current_user.id,
            field_id=body.field_id, to_value=body.to_value,
        )
    except session_service.SessionNotFound:
        raise HTTPException(status_code=404, detail="capture session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return _state(db, session_id, current_user)


@router.post("/sessions/{session_id}/abandon")
def abandon(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Closing Opas ends the capture. ⚠️ MARKED abandoned, never deleted — the row
    is the recovery path James accepted the screen-level loss against."""
    try:
        session_service.abandon(
            db, session_id,
            company_id=current_user.company_id, user_id=current_user.id,
        )
    except session_service.SessionNotFound:
        raise HTTPException(status_code=404, detail="capture session not found")
    db.commit()
    return {"session_id": session_id, "status": "abandoned"}


@router.post("/sessions/{session_id}/complete")
def complete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Finish the order: the summary, or what is still missing.

    ⚠️ THE SAME SERVICE CALL THE TYPED PHRASES REACH, so the Complete order button,
    ⌘Enter and "done"/"approve"/"complete" cannot drift apart.

    ⚠️ IT RETURNS 200 WITH THE MISSING SET, NOT AN ERROR. "You have not finished yet"
    is the pane's normal business — the rows go amber and the bar names them — and a
    4xx would make the client decide between an error path and a state path for one
    outcome.
    """
    try:
        session_service.complete(
            db, session_id,
            company_id=current_user.company_id, user_id=current_user.id,
        )
    except session_service.SessionNotFound:
        raise HTTPException(status_code=404, detail="capture session not found")
    db.commit()
    return _state(db, session_id, current_user, completion_attempt=True)


@router.post("/sessions/{session_id}/approve")
def approve_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create the sales order this capture describes. Status `draft`, by ruling D1.

    ⚠️ IDEMPOTENT. A double click, a retried request and a second typed "approve"
    all return the same order — `session_service.approve` reads the session's
    `sales_order_id` first and returns unchanged when it is already set.

    ⚠️ 409 WITH THE BLOCKERS, NOT 400 WITH A STRING. The pane shows the office what
    is stopping the order, so the reasons have to survive the trip as a list.
    """
    try:
        session_service.approve(
            db, session_id,
            company_id=current_user.company_id, user_id=current_user.id,
        )
    except session_service.SessionNotFound:
        raise HTTPException(status_code=404, detail="capture session not found")
    return _state(db, session_id, current_user)


@router.post("/sessions/{session_id}/why")
def answer_why(
    session_id: str,
    body: WhyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Answer Opas's one question about a change. Two steps, one endpoint.

        scope="skipped"                     logged as skipped, nothing else
        scope="today"                       the reason is stored and that is all
        scope="always", no rule_text        the reason is stored AND a rule is drafted
        scope="always", with rule_text      that sentence becomes a rule

    ⚠️ ONLY THE PERSON WHO APPROVED CAN ANSWER, and it is `_load`'s own filter that makes
    that true rather than a check here: a capture session is scoped by `user_id`, so
    another user's session is a 404 and always has been. "Only the person who approved
    is asked."

    ⚠️ AND IT REFUSES A SECOND ANSWER. `record_answer` returns False when the row already
    carries a scope — a retry, a second tab, or a double ⌘1 must not replace the first
    answer. "never asks twice for one order" is enforced at the record, not only in the
    drawing.
    """
    row = _session_or_404(db, session_id, current_user)
    if row.decision_id is None:
        # ⚠️ NOT AN ERROR. The link is best-effort by design — the decision log swallows
        # its own failures — so a capture whose log row never landed simply has nowhere
        # to record a reason. Saying so is better than inventing a row to hang it on.
        return {"stored": False, "why": "no decision row for this capture"}

    change = why.ask_payload(row)
    if change is None and body.scope != "skipped":
        # The question is gone (answered already, or the change no longer stands).
        return {"stored": False, "why": "nothing to explain"}

    # ── confirming a drafted rule ────────────────────────────────────────────
    if body.scope == "always" and body.rule_text:
        rule_id = rulebook.add_rule(
            db, company_id=current_user.company_id, user_id=current_user.id,
            rule_text=body.rule_text, source_decision_id=row.decision_id,
        )
        # ⚠️ THE SCOPE IS WRITTEN IN THE SAME TRANSACTION AS THE RULE. A crash between
        # them would leave a rule nobody can trace, or a question that looks unanswered
        # with a rule already in the book.
        rulebook.record_answer(
            db, decision_id=row.decision_id, company_id=current_user.company_id,
            reason=body.reason, scope="always", change=change,
        )
        db.commit()
        return {"stored": True, "scope": "always", "rule_id": rule_id,
                "rule_text": body.rule_text}

    stored = rulebook.record_answer(
        db, decision_id=row.decision_id, company_id=current_user.company_id,
        reason=body.reason, scope=body.scope, change=change,
    )
    if not stored:
        db.rollback()
        return {"stored": False, "why": "already answered"}

    draft: str | None = None
    if body.scope == "always":
        # ⚠️ DRAFTED AFTER THE REASON IS STORED, so a model timeout cannot lose the
        # person's own words. And the fallback is their words verbatim — "If the model
        # is down, your own words become the draft" (James).
        draft = rule_draft.draft(
            db, company_id=current_user.company_id,
            field_label=change["label"] if change else "",
            was=change["was"] if change else "",
            now=change["now"] if change else "",
            reason=body.reason or "",
        ) or (body.reason or None)
    db.commit()
    out: dict = {"stored": True, "scope": body.scope}
    if draft:
        out["draft"] = draft
    return out


def _session_or_404(db: Session, session_id: str, user: User):
    try:
        return session_service.load_for_user(
            db, session_id, company_id=user.company_id, user_id=user.id,
        )
    except session_service.SessionNotFound:
        raise HTTPException(status_code=404, detail="capture session not found")


@router.get("/sessions/{session_id}")
def read_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The session's current state. ⚠️ The pane re-reads this after a tuck."""
    return _state(db, session_id, current_user)


@router.get("/vocabulary")
def read_vocabulary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Everything the bar may complete, for THIS tenant. Fetched once per capture.

    ⚠️ A WHOLE-LIST ENDPOINT RATHER THAN A PER-KEYSTROKE SEARCH, BY RULING (James,
    2026-10-16): "Matching is client-side only... keystroke latency must not depend on
    the network." A search endpoint would be the obvious shape and the wrong one — the
    bar is where a director is mid-sentence, and a completion that stutters on a slow
    connection is worse than none.

    ⚠️ IT IS SMALL BECAUSE IT IS TENANT-SCOPED. Measured 2026-10-16: 101 terms on
    sunnycrest, 115 on testco. If a tenant's catalog ever made this large enough to
    matter, the fix is to narrow what is sent, not to move matching back to the wire.
    """
    from app.services.capture.vocabulary import build_vocabulary

    terms = build_vocabulary(db, current_user.company_id)
    return {
        "terms": [
            {
                "text": t.text,
                "kind": t.kind,
                "carried": t.carried,
                "note": t.note,
                "form": t.form,
            }
            for t in terms
        ],
    }
