"""Typed order capture — the endpoints the Opas pane talks to.

⚠️ THE FIRST ENDPOINTS THAT RETURN `CaptureState`. Before this, nothing under
`app/api/routes/` referenced the capture engine at all — it was reachable only from
`call_extraction_service`, driven by the RingCentral webhook.

⚠️ FIVE ENDPOINTS. The fifth, `PUT .../text`, is the one the typed pane actually drives:
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
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.capture import session_service

router = APIRouter()


class StartRequest(BaseModel):
    #: ⚠️ OPTIONAL, AND FED THROUGH EXTRACTION WHEN PRESENT. The prototype starts a
    #: capture and immediately feeds the same line, which is what lets "start an order
    #: for Hopkins" capture the funeral home on the opening keystroke.
    opening_line: str | None = Field(default=None, max_length=2000)


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


class ChooseRequest(BaseModel):
    field_id: str = Field(min_length=1, max_length=64)
    #: 1-based, matching the prototype's digit-key handler.
    index: int = Field(ge=1, le=9)


def _state(db: Session, session_id: str, user: User) -> dict:
    try:
        return session_service.read_state(
            db, session_id, company_id=user.company_id, user_id=user.id
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
    try:
        session_service.set_text(
            db, session_id,
            company_id=current_user.company_id, user_id=current_user.id,
            text=body.text,
        )
    except session_service.SessionNotFound:
        raise HTTPException(status_code=404, detail="capture session not found")
    db.commit()
    state = _state(db, session_id, current_user)
    # ⚠️ ECHOED, NOT ACTED ON. See `TextRequest.seq` — the client drops stale
    # responses because the client is the only party that knows what is in the bar.
    state["seq"] = body.seq
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


@router.get("/sessions/{session_id}")
def read_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The session's current state. ⚠️ The pane re-reads this after a tuck."""
    return _state(db, session_id, current_user)
