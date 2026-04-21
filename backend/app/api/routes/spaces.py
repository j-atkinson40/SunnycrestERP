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
    SpaceNotOwnedError,
    add_pin,
    clear_affinity_for_user,
    count_for_user,
    create_space,
    delete_space,
    get_active_space_id,
    get_spaces_for_user,
    record_visit,
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
    # Workflow Arc Phase 8a — platform-owned system spaces (Settings)
    # are non-deletable. Frontend DotNav uses this to disable the
    # delete option on the space editor.
    is_system: bool = False
    # Phase 8e — deliberate-activation landing route. Null when the
    # space should not trigger navigation on activation.
    default_home_route: str | None = None
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
    # Phase 8e — optional landing route at create time.
    default_home_route: str | None = Field(default=None, max_length=256)


class _UpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    icon: str | None = None
    accent: str | None = None
    is_default: bool | None = None
    density: str | None = None
    # Phase 8e — Pydantic-nullable: omitted in JSON → field absent
    # → service treats as "no change"; explicit null → clear route.
    # Using Field with `exclude_unset=True` on the model would be
    # cleaner but Pydantic v2 loses the distinction through
    # model_dump(). We rely on `.model_fields_set` inside the route
    # handler to detect "was this field supplied".
    default_home_route: str | None = Field(default=None, max_length=256)


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
        is_system=sp.is_system,
        default_home_route=sp.default_home_route,
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
    """Create a new space. Per-user cap enforced server-side
    (MAX_SPACES_PER_USER = 7 as of Phase 8e)."""
    try:
        sp = create_space(
            db,
            user=current_user,
            name=body.name,
            icon=body.icon,
            accent=body.accent,
            is_default=body.is_default,
            density=body.density,
            default_home_route=body.default_home_route,
        )
        return _resolved_to_response(sp)
    except SpaceError as exc:
        raise _translate(exc) from exc


# ── Phase 8e.1 — affinity request/response shapes ────────────────────


class _AffinityVisitRequest(BaseModel):
    """Body of POST /spaces/affinity/visit. Client fires fire-and-
    forget; the server upserts the (user, space, target) row."""

    space_id: str = Field(..., min_length=1, max_length=36)
    target_type: Literal[
        "nav_item", "saved_view", "entity_record", "triage_queue"
    ]
    target_id: str = Field(..., min_length=1, max_length=255)


class _AffinityVisitResponse(BaseModel):
    """Minimal ack shape. `recorded=False` when the server-side
    throttle suppressed the write; clients don't need to distinguish
    but expose the field for observability + tests."""

    recorded: bool


class _AffinityCountResponse(BaseModel):
    count: int


class _AffinityClearResponse(BaseModel):
    cleared: int


# ── Phase 8e.1 — affinity routes ─────────────────────────────────────
# IMPORTANT: these routes MUST be declared BEFORE the `/{space_id}`
# routes below. FastAPI matches paths in declaration order; otherwise
# `DELETE /spaces/affinity` would match `DELETE /spaces/{space_id}`
# with `space_id="affinity"` and fail with 404 SpaceNotFound.


@router.post(
    "/affinity/visit",
    response_model=_AffinityVisitResponse,
    status_code=200,
)
def record_affinity_visit(
    body: _AffinityVisitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _AffinityVisitResponse:
    """Phase 8e.1 — record a topical-affinity visit.

    Called fire-and-forget from the client on deliberate-intent
    signals: pin click, PinStar toggle to pinned, command-bar
    navigate with an active space, pinned-nav direct page visit.
    Server-side upsert increments visit_count + refreshes
    last_visited_at. 60-second in-memory throttle per (user,
    target_type, target_id) prevents write storms — throttled
    requests return `recorded=false` with 200.

    400 on invalid target_type (Pydantic enforces before handler).
    404 when space_id doesn't belong to the caller (defense-in-
    depth — Space IDs are opaque UUIDs but we validate anyway).
    """
    try:
        recorded = record_visit(
            db,
            user=current_user,
            space_id=body.space_id,
            target_type=body.target_type,
            target_id=body.target_id,
        )
    except SpaceNotOwnedError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _AffinityVisitResponse(recorded=recorded)


@router.get(
    "/affinity/count",
    response_model=_AffinityCountResponse,
)
def get_affinity_count(
    space_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _AffinityCountResponse:
    """Phase 8e.1 — count of active affinity rows for the caller.

    Powers the "N tracked signals" counter on /settings/spaces.
    Optional `space_id` query param narrows to a single space.
    """
    return _AffinityCountResponse(
        count=count_for_user(
            db, user=current_user, space_id=space_id
        )
    )


@router.delete(
    "/affinity",
    response_model=_AffinityClearResponse,
)
def clear_affinity(
    space_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _AffinityClearResponse:
    """Phase 8e.1 — privacy "clear command bar learning history"
    action. Deletes all affinity rows for the caller; optional
    `space_id` query param narrows to a single space. Returns
    count deleted. Idempotent (calling twice is fine; second call
    returns 0)."""
    deleted = clear_affinity_for_user(
        db, user=current_user, space_id=space_id
    )
    return _AffinityClearResponse(cleared=deleted)


# ── Space read/mutation routes (parameterized — after /affinity/*) ───


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
    """Partial update — name, icon, accent, is_default, density,
    default_home_route. Pass `default_home_route: null` explicitly to
    clear; omit the key to leave unchanged."""
    try:
        from app.services.spaces.crud import _UNSET

        # Detect field-supplied-vs-omitted via model_fields_set;
        # defaults to _UNSET (no change) when the client omitted it.
        route_update: Any = (
            body.default_home_route
            if "default_home_route" in body.model_fields_set
            else _UNSET
        )
        sp = update_space(
            db,
            user=current_user,
            space_id=space_id,
            name=body.name,
            icon=body.icon,
            accent=body.accent,
            is_default=body.is_default,
            density=body.density,
            default_home_route=route_update,
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


class _ReapplyDefaultsResponse(BaseModel):
    """Shape of POST /spaces/reapply-defaults. Mirrors the dict
    returned by `user_service.reapply_role_defaults_for_user`."""

    saved_views: int
    spaces: int
    briefings: int


@router.post("/reapply-defaults", response_model=_ReapplyDefaultsResponse)
def reapply_defaults(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _ReapplyDefaultsResponse:
    """Phase 8e — opt-in re-run of Phase 2 (saved_views) +
    Phase 3 (spaces) + Phase 6 (briefings) role-based seeding for
    the caller. The underlying seed functions are idempotent per
    their own `preferences.*_seeded_for_roles` arrays, so calling
    this when nothing new needs to seed is a no-op returning all
    zeros. Exposed because `ROLE_CHANGE_RESEED_ENABLED=False`
    gates the saved_views auto-reseed on role change (opinionated-
    but-configurable discipline); this endpoint is the user-driven
    escape hatch that future customization UI wires into.

    Returns per-subsystem counts of new rows created.
    """
    from app.services.user_service import reapply_role_defaults_for_user

    counts = reapply_role_defaults_for_user(db, current_user)
    # Defensive — ensure all three keys present even if the helper
    # shape drifts in a future arc.
    return _ReapplyDefaultsResponse(
        saved_views=int(counts.get("saved_views", 0)),
        spaces=int(counts.get("spaces", 0)),
        briefings=int(counts.get("briefings", 0)),
    )


# Explicitly silence unused-import warnings from the defensive
# re-exports above (typecheckers sometimes flag these).
_USED = (SpaceNotFound, SpaceLimitExceeded, PinNotFound)
