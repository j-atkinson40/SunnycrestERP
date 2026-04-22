"""Spaces CRUD — Phase 3.

Stores per-user spaces in `User.preferences.spaces` (JSONB array).
Server-side resolves pin targets to ResolvedSpace/ResolvedPin so
the client never does a second round-trip to fetch saved-view
titles or resolve seed keys.

Contract:
  - All functions take a `User` ORM instance.
  - Every mutation flips `flag_modified(user, "preferences")` and
    commits. Optimistic-update clients can re-fetch if the server
    rejects.
  - Raises `SpaceError` subclasses for every non-happy path; the
    API layer translates to HTTP via `http_status`.
  - `MAX_SPACES_PER_USER` enforced here, not in the API.

Pin resolution:
  - saved_view pins with a `target_id` that matches a VaultItem
    with item_type="saved_view" the user can see → resolved.
  - saved_view pins with a `target_seed_key` → seed_key looked up
    against VaultItem.source_entity_id filtered to the user's
    company + created_by; if the saved view is missing (user was
    never Phase-2-seeded for that role), the pin resolves as
    unavailable.
  - nav_item pins → label/icon looked up in
    `registry.NAV_LABEL_TABLE`. Availability is trusted; runtime
    frontend filters still apply.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.user import User
from app.models.vault_item import VaultItem
from app.services.spaces import registry as reg
from app.services.spaces.types import (
    MAX_PINS_PER_SPACE,
    MAX_SPACES_PER_USER,
    PinConfig,
    PinNotFound,
    ResolvedPin,
    ResolvedSpace,
    SpaceConfig,
    SpaceError,
    SpaceLimitExceeded,
    SpaceNotFound,
    now_iso,
)

logger = logging.getLogger(__name__)


# ── Internal preferences helpers ─────────────────────────────────────


def _prefs(user: User) -> dict[str, Any]:
    """Snapshot of user preferences as a mutable dict. Call
    `_save_prefs` after mutations to persist."""
    return dict(user.preferences or {})


def _save_prefs(db: Session, user: User, prefs: dict[str, Any]) -> None:
    user.preferences = prefs
    flag_modified(user, "preferences")
    db.commit()
    db.refresh(user)


def _load_spaces(user: User) -> list[SpaceConfig]:
    prefs = user.preferences or {}
    raw = prefs.get("spaces") or []
    spaces: list[SpaceConfig] = []
    for item in raw:
        try:
            spaces.append(SpaceConfig.from_dict(item))
        except Exception:
            # Malformed rows are skipped (defensive); log once so
            # we can spot drift but don't crash the request.
            logger.exception("Malformed space row in user %s preferences", user.id)
    # Always return in display_order.
    spaces.sort(key=lambda s: s.display_order)
    return spaces


def _persist_spaces(db: Session, user: User, spaces: list[SpaceConfig]) -> None:
    """Write the ordered list back into preferences. Preserves any
    unrelated preference keys (saved_views_*, future phases)."""
    prefs = _prefs(user)
    # Reassign display_order to match list position, so reorder
    # operations stay authoritative.
    for idx, sp in enumerate(spaces):
        sp.display_order = idx
    prefs["spaces"] = [s.to_dict() for s in spaces]
    _save_prefs(db, user, prefs)


def _find_space(
    spaces: list[SpaceConfig], space_id: str
) -> tuple[int, SpaceConfig] | None:
    for i, sp in enumerate(spaces):
        if sp.space_id == space_id:
            return i, sp
    return None


# ── Resolution (server-side) ─────────────────────────────────────────


def _resolve_saved_view_seed_key_to_id(
    db: Session, user: User, seed_key: str
) -> tuple[str, str] | None:
    """Look up `seed_key` against VaultItem.source_entity_id under
    the user's company + created_by. Returns (view_id, title) on
    hit, None on miss."""
    hit = (
        db.query(VaultItem.id, VaultItem.title)
        .filter(
            VaultItem.company_id == user.company_id,
            VaultItem.created_by == user.id,
            VaultItem.item_type == "saved_view",
            VaultItem.source_entity_id == seed_key,
            VaultItem.is_active.is_(True),
        )
        .first()
    )
    if hit is None:
        return None
    return (hit[0], hit[1])


def _resolve_saved_view_id_to_title(
    db: Session, user: User, view_id: str
) -> str | None:
    """Look up a saved-view UUID for the user. Returns title or None
    if the view is missing / inaccessible."""
    hit = (
        db.query(VaultItem.title)
        .filter(
            VaultItem.company_id == user.company_id,
            VaultItem.id == view_id,
            VaultItem.item_type == "saved_view",
            VaultItem.is_active.is_(True),
        )
        .first()
    )
    # NB: this doesn't enforce the 4-level saved-view visibility —
    # a shared view would resolve here without a visibility check.
    # Phase 3 ships this permissive for two reasons:
    #   (a) users pinning only their own views is the common case;
    #   (b) cross-user pins will be checked at render time via the
    #       standard saved-views visibility path when the pin's
    #       click navigates to /saved-views/{id} (which runs
    #       crud._can_user_see).
    # Upgrading to full visibility check here is a short-effort
    # follow-on once shared-view pinning lands.
    return hit[0] if hit else None


def _resolve_pin(
    db: Session,
    user: User,
    pin: PinConfig,
    *,
    accessible_queue_ids: set[str] | None = None,
) -> ResolvedPin:
    """Build the API-facing ResolvedPin from a stored PinConfig.

    `accessible_queue_ids` is an optional pre-computed set used to
    batch the triage-queue permission check across all pins of a
    space (avoids per-pin `list_queues_for_user` traversal). Callers
    that know a space has multiple pins should compute it once via
    `_accessible_queue_ids_for_user(db, user)` and pass it down.
    """
    if pin.pin_type == "nav_item":
        label, icon = reg.get_nav_label(pin.target_id) or (pin.target_id, "Link")
        if pin.label_override:
            label = pin.label_override
        return ResolvedPin(
            pin_id=pin.pin_id,
            pin_type="nav_item",
            target_id=pin.target_id,
            display_order=pin.display_order,
            label=label,
            icon=icon,
            href=pin.target_id,
            unavailable=False,
        )

    # triage_queue pin — resolve via Phase 5 registry + count
    if pin.pin_type == "triage_queue":
        queue_id = pin.target_id
        # Use batched access set when caller provided it; otherwise
        # fall back to a single-pin lookup.
        if accessible_queue_ids is None:
            accessible_queue_ids = _accessible_queue_ids_for_user(db, user)
        if queue_id not in accessible_queue_ids:
            return ResolvedPin(
                pin_id=pin.pin_id,
                pin_type="triage_queue",
                target_id=queue_id,
                display_order=pin.display_order,
                label=pin.label_override or queue_id.replace("_", " ").title(),
                icon="ListChecks",
                href=None,
                unavailable=True,
                queue_item_count=None,
            )
        # Resolve display fields from the queue config + count.
        from app.services.triage import (
            engine as _triage_engine,
            registry as _triage_registry,
        )
        try:
            config = _triage_registry.get_config(
                db, company_id=user.company_id, queue_id=queue_id
            )
        except Exception:
            return ResolvedPin(
                pin_id=pin.pin_id,
                pin_type="triage_queue",
                target_id=queue_id,
                display_order=pin.display_order,
                label=pin.label_override or queue_id.replace("_", " ").title(),
                icon="ListChecks",
                href=None,
                unavailable=True,
                queue_item_count=None,
            )
        # queue_count enforces access internally; our outer check above
        # guarantees it won't raise, but be defensive.
        try:
            count = _triage_engine.queue_count(
                db, user=user, queue_id=queue_id
            )
        except Exception:
            count = None
        return ResolvedPin(
            pin_id=pin.pin_id,
            pin_type="triage_queue",
            target_id=queue_id,
            display_order=pin.display_order,
            label=pin.label_override or config.queue_name,
            icon=config.icon,
            href=f"/triage/{queue_id}",
            unavailable=False,
            queue_item_count=count,
        )

    # saved_view pin — two resolution paths
    if pin.target_seed_key:
        result = _resolve_saved_view_seed_key_to_id(db, user, pin.target_seed_key)
        if result is None:
            # Seeded template pointed at a saved-view that wasn't
            # seeded for this user (or was since deleted). Mark
            # unavailable with a readable fallback label.
            label = pin.label_override or pin.target_seed_key.split(":")[-1].replace("_", " ").title()
            return ResolvedPin(
                pin_id=pin.pin_id,
                pin_type="saved_view",
                target_id=pin.target_id or pin.target_seed_key,
                display_order=pin.display_order,
                label=label,
                icon="Layers",
                href=None,
                unavailable=True,
            )
        view_id, title = result
        return ResolvedPin(
            pin_id=pin.pin_id,
            pin_type="saved_view",
            target_id=view_id,
            display_order=pin.display_order,
            label=pin.label_override or title,
            icon="Layers",
            href=f"/saved-views/{view_id}",
            saved_view_id=view_id,
            saved_view_title=title,
            unavailable=False,
        )

    # Plain view_id (user-created pin, not from template)
    title = _resolve_saved_view_id_to_title(db, user, pin.target_id)
    if title is None:
        return ResolvedPin(
            pin_id=pin.pin_id,
            pin_type="saved_view",
            target_id=pin.target_id,
            display_order=pin.display_order,
            label=pin.label_override or "Unavailable view",
            icon="Layers",
            href=None,
            unavailable=True,
        )
    return ResolvedPin(
        pin_id=pin.pin_id,
        pin_type="saved_view",
        target_id=pin.target_id,
        display_order=pin.display_order,
        label=pin.label_override or title,
        icon="Layers",
        href=f"/saved-views/{pin.target_id}",
        saved_view_id=pin.target_id,
        saved_view_title=title,
        unavailable=False,
    )


def _accessible_queue_ids_for_user(db: Session, user: User) -> set[str]:
    """Queue_ids the user can currently access, computed once per
    `_resolve_space` call. Protects against the N+1 pattern that
    would otherwise run `list_queues_for_user` per pin."""
    try:
        from app.services.triage import list_queues_for_user as _list_queues

        return {cfg.queue_id for cfg in _list_queues(db, user=user)}
    except Exception:
        # Triage package import failure or mid-migration state —
        # fail closed so triage pins render as unavailable rather
        # than crashing the whole /spaces response.
        return set()


def _resolve_space(db: Session, user: User, sp: SpaceConfig) -> ResolvedSpace:
    # Phase 3 follow-up 1 — batch the triage-queue access check
    # ONCE per space resolution (instead of per-pin) so a space with
    # many triage pins doesn't pay N× permission checks.
    has_triage_pin = any(p.pin_type == "triage_queue" for p in sp.pins)
    accessible_queue_ids = (
        _accessible_queue_ids_for_user(db, user) if has_triage_pin else None
    )
    resolved_pins = [
        _resolve_pin(db, user, p, accessible_queue_ids=accessible_queue_ids)
        for p in sp.pins
    ]
    resolved_pins.sort(key=lambda p: p.display_order)
    return ResolvedSpace(
        space_id=sp.space_id,
        name=sp.name,
        icon=sp.icon,
        accent=sp.accent,
        display_order=sp.display_order,
        is_default=sp.is_default,
        density=sp.density,
        is_system=sp.is_system,
        default_home_route=sp.default_home_route,
        # Phase 8e.2 — portal modifier fields round-trip.
        access_mode=sp.access_mode,
        tenant_branding=sp.tenant_branding,
        write_mode=sp.write_mode,
        session_timeout_minutes=sp.session_timeout_minutes,
        pins=resolved_pins,
        created_at=sp.created_at,
        updated_at=sp.updated_at,
    )


# ── Queries ──────────────────────────────────────────────────────────


def get_spaces_for_user(db: Session, *, user: User) -> list[ResolvedSpace]:
    """Primary read path used by the /api/v1/spaces endpoint."""
    raw_spaces = _load_spaces(user)
    return [_resolve_space(db, user, sp) for sp in raw_spaces]


def get_space(db: Session, *, user: User, space_id: str) -> ResolvedSpace:
    raw_spaces = _load_spaces(user)
    hit = _find_space(raw_spaces, space_id)
    if hit is None:
        raise SpaceNotFound(f"Space {space_id} not found")
    _, sp = hit
    return _resolve_space(db, user, sp)


def get_active_space_id(user: User) -> str | None:
    prefs = user.preferences or {}
    return prefs.get("active_space_id")


# ── Mutations ────────────────────────────────────────────────────────


def create_space(
    db: Session,
    *,
    user: User,
    name: str,
    icon: str = "",
    accent: str = "neutral",
    is_default: bool = False,
    density: str = "comfortable",
    default_home_route: str | None = None,
) -> ResolvedSpace:
    """Create a new space. Enforces the per-user cap.

    Phase 8e.2.3 — default `icon=""` (was `"layers"`). DotNav's
    ICON_MAP doesn't match the empty string, so user-created spaces
    fall through to the colored-dot fallback. Template spaces (from
    SEED_TEMPLATES) already carry explicit Lucide icon names so
    they continue rendering as icons. This aligns rendering with the
    component name (DotNav = dots for user spaces, icons for
    platform-owned template + system spaces).

    NOT retroactive: existing spaces in the DB with `icon="layers"`
    keep their value. Only NEW user-created spaces get the flipped
    default. Users can still edit via `/settings/spaces` to pick an
    icon. Per approved spec item #4 (2026-04-22): "only flip the
    default for new creates. User can edit manually if they want to
    change."
    """
    if not name or not name.strip():
        raise SpaceError("Space name is required")

    spaces = _load_spaces(user)
    if len(spaces) >= MAX_SPACES_PER_USER:
        raise SpaceLimitExceeded(
            f"You can have up to {MAX_SPACES_PER_USER} spaces. "
            "Delete one first or edit existing spaces."
        )

    # If first space and no is_default flag, force default=True so
    # the user never ends up with zero defaults.
    if not spaces:
        is_default = True

    # If is_default=True, clear other defaults.
    if is_default:
        for s in spaces:
            s.is_default = False

    new_space = SpaceConfig(
        space_id=SpaceConfig.new_id(),
        name=name.strip(),
        icon=icon,
        accent=accent,  # type: ignore[arg-type]
        display_order=len(spaces),
        is_default=is_default,
        pins=[],
        density=density,  # type: ignore[arg-type]
        default_home_route=default_home_route,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    spaces.append(new_space)
    _persist_spaces(db, user, spaces)
    return _resolve_space(db, user, new_space)


_UNSET = object()


def update_space(
    db: Session,
    *,
    user: User,
    space_id: str,
    name: str | None = None,
    icon: str | None = None,
    accent: str | None = None,
    is_default: bool | None = None,
    density: str | None = None,
    default_home_route: Any = _UNSET,
) -> ResolvedSpace:
    """Update a space. `default_home_route` uses a sentinel so callers
    can explicitly clear the route (pass None) vs. omit-no-change
    (sentinel = _UNSET)."""
    spaces = _load_spaces(user)
    hit = _find_space(spaces, space_id)
    if hit is None:
        raise SpaceNotFound(f"Space {space_id} not found")
    _, sp = hit

    if name is not None:
        if not name.strip():
            raise SpaceError("Space name is required")
        sp.name = name.strip()
    if icon is not None:
        sp.icon = icon
    if accent is not None:
        sp.accent = accent  # type: ignore[assignment]
    if density is not None:
        sp.density = density  # type: ignore[assignment]
    if default_home_route is not _UNSET:
        # Empty string → None (treated as "clear"). Leading slash
        # enforcement is light-touch: API layer validates the format
        # before reaching here.
        route = default_home_route
        sp.default_home_route = route if route else None
    if is_default is True:
        # Flipping to default — clear others.
        for s in spaces:
            s.is_default = s.space_id == sp.space_id
    elif is_default is False:
        # Can't remove the last default. If this is the current
        # default, reject; caller must promote another first.
        if sp.is_default:
            other_defaults = [s for s in spaces if s.is_default and s.space_id != sp.space_id]
            if not other_defaults:
                raise SpaceError(
                    "Cannot unset default on your only default space. "
                    "Mark another space as default first."
                )
            sp.is_default = False

    sp.updated_at = now_iso()
    _persist_spaces(db, user, spaces)
    return _resolve_space(db, user, sp)


def delete_space(db: Session, *, user: User, space_id: str) -> None:
    spaces = _load_spaces(user)
    hit = _find_space(spaces, space_id)
    if hit is None:
        raise SpaceNotFound(f"Space {space_id} not found")
    idx, sp = hit

    # Workflow Arc Phase 8a — system spaces are platform-owned and
    # non-deletable. Users can rename + recolor + reorder pins, but
    # delete raises SpaceError so the UI can render a clear message.
    # Matches the audit-approved "can be hidden but not deleted"
    # affordance without requiring separate hide infrastructure in
    # this phase (hide is effectively "move to end + collapse pins";
    # Phase 8e's default-views work may formalize it).
    if sp.is_system:
        raise SpaceError(
            "System spaces can be hidden but not deleted. "
            "Rename, recolor, or reorder pins to customize it."
        )

    was_default = sp.is_default

    # If active_space_id points here, clear it.
    prefs = _prefs(user)
    if prefs.get("active_space_id") == space_id:
        prefs["active_space_id"] = None

    spaces.pop(idx)
    # If we removed the default, promote the first remaining.
    if was_default and spaces:
        spaces[0].is_default = True

    # Persist both prefs (active_space_id clear) AND the spaces list.
    # Inline the save to avoid two commits.
    prefs["spaces"] = [s.to_dict() for s in spaces]
    for i, s in enumerate(spaces):
        s.display_order = i
        prefs["spaces"][i]["display_order"] = i
    _save_prefs(db, user, prefs)

    # Phase 8e.1 — cascade affinity rows for the deleted space.
    # Best-effort: if the affinity delete fails (e.g. migration
    # gap) we log + continue; the space delete already committed.
    try:
        from app.services.spaces.affinity import (
            delete_affinity_for_space,
        )

        delete_affinity_for_space(
            db, user_id=user.id, space_id=space_id
        )
    except Exception:  # pragma: no cover — best-effort
        logger.exception(
            "Failed to cascade affinity rows for deleted space %s",
            space_id,
        )


def set_active_space(
    db: Session, *, user: User, space_id: str
) -> ResolvedSpace:
    """Update `preferences.active_space_id`. 404 if the target
    doesn't belong to this user."""
    spaces = _load_spaces(user)
    hit = _find_space(spaces, space_id)
    if hit is None:
        raise SpaceNotFound(f"Space {space_id} not found")
    _, sp = hit

    prefs = _prefs(user)
    prefs["active_space_id"] = space_id
    _save_prefs(db, user, prefs)
    return _resolve_space(db, user, sp)


def reorder_spaces(
    db: Session, *, user: User, space_ids_in_order: list[str]
) -> list[ResolvedSpace]:
    spaces = _load_spaces(user)
    existing_ids = {s.space_id for s in spaces}
    if set(space_ids_in_order) != existing_ids:
        raise SpaceError(
            "reorder_spaces input must contain exactly the user's space IDs."
        )
    id_to_space = {s.space_id: s for s in spaces}
    reordered = [id_to_space[sid] for sid in space_ids_in_order]
    _persist_spaces(db, user, reordered)
    return [_resolve_space(db, user, sp) for sp in reordered]


# ── Pin ops ──────────────────────────────────────────────────────────


def add_pin(
    db: Session,
    *,
    user: User,
    space_id: str,
    pin_type: str,
    target_id: str,
    label_override: str | None = None,
    target_seed_key: str | None = None,
) -> ResolvedPin:
    spaces = _load_spaces(user)
    hit = _find_space(spaces, space_id)
    if hit is None:
        raise SpaceNotFound(f"Space {space_id} not found")
    _, sp = hit

    if len(sp.pins) >= MAX_PINS_PER_SPACE:
        raise SpaceError(f"Space has the maximum {MAX_PINS_PER_SPACE} pins")

    if pin_type not in ("saved_view", "nav_item", "triage_queue"):
        raise SpaceError(f"Unknown pin_type {pin_type!r}")

    # De-dupe: skip if a pin of the same (type, target) already
    # exists. Callers (star toggle) rely on idempotency.
    for existing in sp.pins:
        same_target = (
            existing.pin_type == pin_type
            and existing.target_id == target_id
            and (existing.target_seed_key or None) == (target_seed_key or None)
        )
        if same_target:
            # Treat as no-op; return the existing resolved pin.
            return _resolve_pin(db, user, existing)

    new_pin = PinConfig(
        pin_id=PinConfig.new_id(),
        pin_type=pin_type,  # type: ignore[arg-type]
        target_id=target_id,
        display_order=len(sp.pins),
        label_override=label_override,
        target_seed_key=target_seed_key,
    )
    sp.pins.append(new_pin)
    sp.updated_at = now_iso()
    _persist_spaces(db, user, spaces)
    return _resolve_pin(db, user, new_pin)


def remove_pin(
    db: Session, *, user: User, space_id: str, pin_id: str
) -> None:
    spaces = _load_spaces(user)
    hit = _find_space(spaces, space_id)
    if hit is None:
        raise SpaceNotFound(f"Space {space_id} not found")
    _, sp = hit
    before = len(sp.pins)
    sp.pins = [p for p in sp.pins if p.pin_id != pin_id]
    if len(sp.pins) == before:
        raise PinNotFound(f"Pin {pin_id} not found in space {space_id}")
    # Compact display_order after removal.
    for i, p in enumerate(sp.pins):
        p.display_order = i
    sp.updated_at = now_iso()
    _persist_spaces(db, user, spaces)


def reorder_pins(
    db: Session,
    *,
    user: User,
    space_id: str,
    pin_ids_in_order: list[str],
) -> list[ResolvedPin]:
    spaces = _load_spaces(user)
    hit = _find_space(spaces, space_id)
    if hit is None:
        raise SpaceNotFound(f"Space {space_id} not found")
    _, sp = hit

    existing_ids = {p.pin_id for p in sp.pins}
    if set(pin_ids_in_order) != existing_ids:
        raise SpaceError(
            "reorder_pins input must contain exactly the space's pin IDs."
        )
    id_to_pin = {p.pin_id: p for p in sp.pins}
    reordered = [id_to_pin[pid] for pid in pin_ids_in_order]
    for i, p in enumerate(reordered):
        p.display_order = i
    sp.pins = reordered
    sp.updated_at = now_iso()
    _persist_spaces(db, user, spaces)
    return [_resolve_pin(db, user, p) for p in reordered]


__all__ = [
    "get_spaces_for_user",
    "get_space",
    "get_active_space_id",
    "create_space",
    "update_space",
    "delete_space",
    "set_active_space",
    "reorder_spaces",
    "add_pin",
    "remove_pin",
    "reorder_pins",
    # Re-export for convenience in API layer
    "SpaceError",
    "SpaceNotFound",
    "SpaceLimitExceeded",
    "PinNotFound",
]
