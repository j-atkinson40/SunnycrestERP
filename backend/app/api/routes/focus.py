"""Focus primitive API — Phase A Session 4.

Endpoints:

  GET    /api/v1/focus/{focus_type}/layout
    → Return the resolved layout for this user + focus_type via
      the 3-tier cascade. Response shape:
        { "layout_state": {...} | null, "source": "active" | "recent"
                                                  | "default" | null }

  POST   /api/v1/focus/{focus_type}/open
    → Create or resume an active session. Returns the session + the
      resolved initial layout (so the frontend can set up in one
      round-trip).

  PATCH  /api/v1/focus/sessions/{session_id}/layout
    → Write layout_state. Ownership enforced — caller must own the
      session.

  POST   /api/v1/focus/sessions/{session_id}/close
    → Close session. Ownership enforced. Idempotent.

  GET    /api/v1/focus/recent
    → List recently-closed sessions across all focus_types.

All endpoints require authenticated user; tenant scoping comes from
`user.company_id` on lookups. Cross-tenant access is prevented by
construction (every query filters on user_id).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.focus_session import FocusSession
from app.models.user import User
from app.services.focus import focus_session_service as fss


router = APIRouter()


# ── Schemas ─────────────────────────────────────────────────────────


class FocusSessionOut(BaseModel):
    id: str
    focus_type: str
    layout_state: dict
    is_active: bool
    opened_at: str
    closed_at: str | None
    last_interacted_at: str

    @classmethod
    def from_model(cls, s: FocusSession) -> "FocusSessionOut":
        return cls(
            id=s.id,
            focus_type=s.focus_type,
            layout_state=dict(s.layout_state or {}),
            is_active=s.is_active,
            opened_at=s.opened_at.isoformat() if s.opened_at else "",
            closed_at=s.closed_at.isoformat() if s.closed_at else None,
            last_interacted_at=(
                s.last_interacted_at.isoformat()
                if s.last_interacted_at
                else ""
            ),
        )


class FocusLayoutResponse(BaseModel):
    """Response for GET /focus/{type}/layout — 3-tier resolved."""

    layout_state: dict | None
    source: str | None = Field(
        default=None,
        description=(
            "Which tier answered: 'active' | 'recent' | 'default' | null."
        ),
    )


class FocusOpenResponse(BaseModel):
    session: FocusSessionOut
    # Same 3-tier resolved layout the GET endpoint returns — frontend
    # uses this to swap from its optimistic registry default on open.
    layout_state: dict | None
    source: str | None = None


class FocusLayoutUpdateRequest(BaseModel):
    layout_state: dict


# ── Resolver helper ─────────────────────────────────────────────────


def _resolve_with_source(
    db: Session, user: User, focus_type: str
) -> tuple[dict | None, str | None]:
    """Mirror fss.resolve_layout_state but also report the source tier.

    The route-level response exposes `source` for debugging + future
    UI affordances ("using your saved layout" vs "using team default").
    """
    active = fss.get_active_session(db, user, focus_type)
    if active is not None and active.layout_state:
        return active.layout_state, "active"
    recent = fss.get_recent_closed_session(db, user, focus_type)
    if recent is not None and recent.layout_state:
        return recent.layout_state, "recent"
    default = fss.get_layout_default(db, user.company_id, focus_type)
    if default is not None and default.layout_state:
        return default.layout_state, "default"
    return None, None


def _get_owned_session(
    db: Session, session_id: str, user: User
) -> FocusSession:
    """Fetch a session owned by the caller, or raise 404.

    We return 404 (not 403) on cross-user access so the endpoint
    doesn't leak the existence of sessions belonging to other users.
    """
    session = (
        db.query(FocusSession)
        .filter(FocusSession.id == session_id, FocusSession.user_id == user.id)
        .first()
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Focus session not found",
        )
    return session


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("/{focus_type}/layout", response_model=FocusLayoutResponse)
def get_layout(
    focus_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FocusLayoutResponse:
    """Resolve the layout for this user + focus_type (3-tier cascade)."""
    layout, source = _resolve_with_source(db, current_user, focus_type)
    return FocusLayoutResponse(layout_state=layout, source=source)


@router.post("/{focus_type}/open", response_model=FocusOpenResponse)
def open_session(
    focus_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FocusOpenResponse:
    """Create or resume an active session. Returns session + resolved
    initial layout in one round-trip."""
    # Resolve layout FIRST (before create_or_resume may write an empty
    # active row), so we get the tenant-default / recent-closed value
    # if the user has no active state.
    layout, source = _resolve_with_source(db, current_user, focus_type)
    session = fss.create_or_resume_session(db, current_user, focus_type)
    # If the newly-created session has its own layout (seeded from
    # tenant default in service), expose that as the authoritative
    # initial state.
    if session.layout_state:
        layout = session.layout_state
        source = source or "active"
    db.commit()
    return FocusOpenResponse(
        session=FocusSessionOut.from_model(session),
        layout_state=layout,
        source=source,
    )


@router.patch(
    "/sessions/{session_id}/layout", response_model=FocusSessionOut
)
def update_layout(
    session_id: str,
    body: FocusLayoutUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FocusSessionOut:
    """Write layout_state to an owned session."""
    session = _get_owned_session(db, session_id, current_user)
    updated = fss.update_layout_state(db, session, body.layout_state)
    db.commit()
    return FocusSessionOut.from_model(updated)


@router.post("/sessions/{session_id}/close", response_model=FocusSessionOut)
def close_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FocusSessionOut:
    """Close an owned session. Idempotent."""
    session = _get_owned_session(db, session_id, current_user)
    closed = fss.close_session(db, session)
    db.commit()
    return FocusSessionOut.from_model(closed)


@router.get("/recent", response_model=list[FocusSessionOut])
def list_recent(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FocusSessionOut]:
    """List recently-closed sessions across all focus_types."""
    limit = max(1, min(50, limit))
    rows = fss.list_recent_closed_sessions(db, current_user, limit=limit)
    return [FocusSessionOut.from_model(r) for r in rows]
