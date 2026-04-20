"""Phase 7 — server-side first-run onboarding touch dismissals.

Stored in `User.preferences.onboarding_touches_shown: list[str]`.
Cross-device: a tooltip dismissed on desktop stays dismissed on
mobile. This is deliberately separate from the existing
`HelpTooltip` localStorage dismissal (device-local, keyed by
`help_tooltips_dismissed`) — different persistence layers for
different use cases.

Three endpoints:
  GET  /api/v1/onboarding-touches            — return shown list
  POST /api/v1/onboarding-touches/{key}      — record dismissal (idempotent)
  DELETE /api/v1/onboarding-touches/{key}    — undo dismissal (dev/testing)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User

router = APIRouter()


_KEY = "onboarding_touches_shown"


class _TouchesOut(BaseModel):
    shown: list[str]


def _get_shown(user: User) -> list[str]:
    prefs = user.preferences or {}
    val = prefs.get(_KEY)
    return list(val) if isinstance(val, list) else []


@router.get("", response_model=_TouchesOut)
def list_touches(
    current_user: User = Depends(get_current_user),
) -> _TouchesOut:
    return _TouchesOut(shown=_get_shown(current_user))


@router.post("/{touch_key}", response_model=_TouchesOut)
def record_touch(
    touch_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _TouchesOut:
    """Record that the user dismissed (or saw + interacted with) a
    first-run tooltip. Idempotent — calling twice is a no-op."""
    shown = _get_shown(current_user)
    if touch_key not in shown:
        shown.append(touch_key)
        prefs = current_user.preferences or {}
        prefs[_KEY] = shown
        current_user.preferences = prefs
        flag_modified(current_user, "preferences")
        db.commit()
        db.refresh(current_user)
    return _TouchesOut(shown=shown)


@router.delete("/{touch_key}", response_model=_TouchesOut)
def undo_touch(
    touch_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _TouchesOut:
    """Undo a dismissal. Primarily for testing + admin reset."""
    shown = _get_shown(current_user)
    if touch_key in shown:
        shown = [k for k in shown if k != touch_key]
        prefs = current_user.preferences or {}
        prefs[_KEY] = shown
        current_user.preferences = prefs
        flag_modified(current_user, "preferences")
        db.commit()
        db.refresh(current_user)
    return _TouchesOut(shown=shown)
