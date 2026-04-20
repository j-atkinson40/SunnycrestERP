"""Spaces API — Phase 3.

Ten endpoints under `/api/v1/spaces/*`. Every endpoint is
user-scoped (no tenant-level cross-user reads). Pin resolution is
server-side (denormalized saved_view_id + title; `unavailable=true`
when the target is gone) — the client never has to do a second
round-trip to render a pin.

Response shapes are thin Pydantic mirrors of the dataclasses in
`app.services.spaces.types`. Bumping the dataclass without bumping
the response model is a bug.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.spaces import (
    PinNotFound,
    ResolvedPin,
    ResolvedSpace,
    SpaceError,
    SpaceLimitExceeded,
    SpaceNotFound,
    add_pin,
    create_space,
    delete_space,
    get_active_space_id,
    get_spaces_for_user,
    remove_pin,
    reorder_pins,
    reorder_spaces,
    set_active_space,
    update_space,
)

router = APIRouter()


# ── Response shapes ──────────────────────────────────────────────────


class _PinResponse(BaseModel):
    pin_id: str
    pin_type: Literal["saved_view", "nav_item", "triage_queue"]
    target_id: str
    display_order: int
    label: str
    icon: str
    href: str | None
    unavailable: bool
    saved_view_id: str | None = None
    saved_view_title: str | None = None
    # Phase 3 follow-up 1 — pending item count for triage_queue pins.
    # None for other pin types or when the queue is unavailable.
    queue_item_count: int | None = None


class _SpaceResponse(BaseModel):
    space_id: str
    name: str
    icon: str
    accent: str
    display_order: int
    is_default: bool
    density: str
    pins: list[_PinResponse]
    created_at: str | None
    updated_at: str | None


class _SpacesListResponse(BaseModel):
    spaces: list[_SpaceResponse]
    active_space_id: str | None


class _CreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    icon: str = "layers"
    accent: str = "neutral"
    is_default: bool = False
    density: str = "comfortable"


class _UpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    icon: str | None = None
    accent: str | None = None
    is_default: bool | None = None
    density: str | None = None


class _ReorderRequest(BaseModel):
    space_ids: list[str]


class _AddPinRequest(BaseModel):
    pin_type: Literal["saved_view", "nav_item", "triage_queue"]
    target_id: str
    label_override: str | None = None
    target_seed_key: str | None = None


class _ReorderPinsRequest(BaseModel):
    pin_ids: list[str]


# ── Helpers ──────────────────────────────────────────────────────────


def _resolved_to_response(sp: ResolvedSpace) -> _SpaceResponse:
    return _SpaceResponse(
        space_id=sp.space_id,
        name=sp.name,
        icon=sp.icon,
        accent=sp.accent,
        display_order=sp.display_order,
        is_default=sp.is_default,
        density=sp.density,
        pins=[_pin_to_response(p) for p in sp.pins],
        created_at=sp.created_at,
        updated_at=sp.updated_at,
    )


def _pin_to_response(p: ResolvedPin) -> _PinResponse:
    return _PinResponse(
        pin_id=p.pin_id,
        pin_type=p.pin_type,
        target_id=p.target_id,
        display_order=p.display_order,
        label=p.label,
        icon=p.icon,
        href=p.href,
        unavailable=p.unavailable,
        saved_view_id=p.saved_view_id,
        saved_view_title=p.saved_view_title,
        queue_item_count=p.queue_item_count,
    )


def _translate(exc: SpaceError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=str(exc))


# ── Routes ───────────────────────────────────────────────────────────


@router.get("", response_model=_SpacesListResponse)
def list_spaces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _SpacesListResponse:
    """My spaces with resolved pins + the currently-active space id.

    Single call serves the initial layout on every page load: the
    sidebar reads `active_space_id` to determine which pins to
    render; the space switcher reads the full list.
    """
    spaces = get_spaces_for_user(db, user=current_user)
    return _SpacesListResponse(
        spaces=[_resolved_to_response(s) for s in spaces],
        active_space_id=get_active_space_id(current_user),
    )


@router.post("", response_model=_SpaceResponse, status_code=201)
def create(
    body: _CreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _SpaceResponse:
    """Create a new space. Max 5 per user."""
    try:
        sp = create_space(
            db,
            user=current_user,
            name=body.name,
            icon=body.icon,
            accent=body.accent,
            is_default=body.is_default,
            density=body.density,
        )
        return _resolved_to_response(sp)
    except SpaceError as exc:
        raise _translate(exc) from exc


@router.get("/{space_id}", response_model=_SpaceResponse)
def get_one(
    space_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _SpaceResponse:
    """Get a single space by id (must belong to caller)."""
    try:
        from app.services.spaces import get_space

        sp = get_space(db, user=current_user, space_id=space_id)
        return _resolved_to_response(sp)
    except SpaceError as exc:
        raise _translate(exc) from exc


@router.patch("/{space_id}", response_model=_SpaceResponse)
def update(
    space_id: str,
    body: _UpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _SpaceResponse:
    """Partial update — name, icon, accent, is_default, density."""
    try:
        sp = update_space(
            db,
            user=current_user,
            space_id=space_id,
            name=body.name,
            icon=body.icon,
            accent=body.accent,
            is_default=body.is_default,
            density=body.density,
        )
        return _resolved_to_response(sp)
    except SpaceError as exc:
        raise _translate(exc) from exc


@router.delete("/{space_id}")
def delete(
    space_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Delete a space. If it was the default, the first remaining
    space is promoted. If it was active, `active_space_id` is
    cleared. Returns `{status: deleted, id: ...}` — 200 with body
    (matches codebase pattern; see Saved Views rationale)."""
    try:
        delete_space(db, user=current_user, space_id=space_id)
        return {"status": "deleted", "id": space_id}
    except SpaceError as exc:
        raise _translate(exc) from exc


@router.post("/{space_id}/activate", response_model=_SpaceResponse)
def activate(
    space_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _SpaceResponse:
    """Set as the user's active space (updates
    `preferences.active_space_id`)."""
    try:
        sp = set_active_space(db, user=current_user, space_id=space_id)
        return _resolved_to_response(sp)
    except SpaceError as exc:
        raise _translate(exc) from exc


@router.post("/reorder", response_model=_SpacesListResponse)
def reorder(
    body: _ReorderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _SpacesListResponse:
    """Reorder spaces. `space_ids` must contain every space id
    the user currently owns (server validates set equality)."""
    try:
        spaces = reorder_spaces(
            db, user=current_user, space_ids_in_order=body.space_ids
        )
        return _SpacesListResponse(
            spaces=[_resolved_to_response(s) for s in spaces],
            active_space_id=get_active_space_id(current_user),
        )
    except SpaceError as exc:
        raise _translate(exc) from exc


@router.post("/{space_id}/pins", response_model=_PinResponse, status_code=201)
def create_pin(
    space_id: str,
    body: _AddPinRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _PinResponse:
    """Add a pin. Idempotent — same-(type, target, seed_key) on an
    existing pin is treated as no-op + returns the existing pin.
    Max 20 pins per space."""
    try:
        pin = add_pin(
            db,
            user=current_user,
            space_id=space_id,
            pin_type=body.pin_type,
            target_id=body.target_id,
            label_override=body.label_override,
            target_seed_key=body.target_seed_key,
        )
        return _pin_to_response(pin)
    except SpaceError as exc:
        raise _translate(exc) from exc


@router.delete("/{space_id}/pins/{pin_id}")
def delete_pin(
    space_id: str,
    pin_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Remove a pin. 404 if the pin isn't in that space."""
    try:
        remove_pin(db, user=current_user, space_id=space_id, pin_id=pin_id)
        return {"status": "deleted", "id": pin_id}
    except SpaceError as exc:
        raise _translate(exc) from exc


@router.post(
    "/{space_id}/pins/reorder",
    response_model=_SpaceResponse,
)
def reorder_pins_route(
    space_id: str,
    body: _ReorderPinsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _SpaceResponse:
    """Reorder pins within a space. `pin_ids` must contain every
    pin id in the space."""
    try:
        reorder_pins(
            db,
            user=current_user,
            space_id=space_id,
            pin_ids_in_order=body.pin_ids,
        )
        # Re-fetch to return the full space shape with reordered
        # pins and fresh resolution.
        from app.services.spaces import get_space

        sp = get_space(db, user=current_user, space_id=space_id)
        return _resolved_to_response(sp)
    except SpaceError as exc:
        raise _translate(exc) from exc


# Explicitly silence unused-import warnings from the defensive
# re-exports above (typecheckers sometimes flag these).
_USED = (SpaceNotFound, SpaceLimitExceeded, PinNotFound)
