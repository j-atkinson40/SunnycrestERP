"""Spaces — typed data model.

Phase 3 of the UI/UX arc. A Space is a per-user workspace context —
name + icon + accent + pinned items — that overlays the existing
vertical navigation. Spaces are stored in
`User.preferences.spaces` (a JSONB array). No new table.

Every dataclass has `to_dict`/`from_dict` for round-trip through
the JSONB column. Mirrors the Phase 2 Saved Views convention so
evolution is predictable.

NB: the API layer uses Pydantic models for request/response
validation; these dataclasses are the canonical in-memory shape
used by crud/seed/registry. Pydantic schemas in the API route are
thin mirrors that convert to/from these via `to_dict`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

# ── Enums ────────────────────────────────────────────────────────────

# Six curated accents ship in Phase 3. Custom accent picker is a
# Phase 7 polish item — don't expand this set without updating the
# frontend `ACCENT_VARS` map in `types/spaces.ts`.
AccentName = Literal[
    "warm",        # soft amber, serif-y — Arrangement mode
    "crisp",       # neutral gray + blue — Administrative mode
    "industrial",  # high-contrast gray + orange — Production mode
    "forward",     # bright blue + purple — Sales / Operational
    "neutral",     # muted gray + minimal color — Ownership / default
    "muted",       # even more reserved — low-stimulus contexts
]

DensityName = Literal["comfortable", "compact"]

# Pin target types. Extending this union = extend `_resolve_pin`
# (crud.py), `_build_pins_from_seeds` (seed.py), the API pin
# request/response Pydantic models, the frontend `PinType` literal,
# and PinStar's prop union. All must stay in lockstep.
PinType = Literal["saved_view", "nav_item", "triage_queue"]


# ── Pin ──────────────────────────────────────────────────────────────


@dataclass
class PinConfig:
    """One pinned item in a space's sidebar section.

    For `pin_type="saved_view"`:
      - `target_id` is a Saved View UUID (if the pin was created from
        a user's existing view)
      - `target_seed_key` is an optional seed key (e.g.
        `saved_view_seed:director:my_active_cases`) used by TEMPLATE
        pins — resolved to the user's actual saved-view id at load
        time in `crud.get_spaces_for_user`.

    For `pin_type="nav_item"`:
      - `target_id` is the nav `href` (e.g. `/cases`, `/financials`).
      - `target_seed_key` is None.
    """

    pin_id: str
    pin_type: PinType
    target_id: str
    display_order: int
    label_override: str | None = None
    target_seed_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pin_id": self.pin_id,
            "pin_type": self.pin_type,
            "target_id": self.target_id,
            "display_order": self.display_order,
            "label_override": self.label_override,
            "target_seed_key": self.target_seed_key,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PinConfig":
        return cls(
            pin_id=data["pin_id"],
            pin_type=data["pin_type"],
            target_id=data["target_id"],
            display_order=int(data.get("display_order", 0)),
            label_override=data.get("label_override"),
            target_seed_key=data.get("target_seed_key"),
        )

    @staticmethod
    def new_id() -> str:
        return f"pn_{uuid.uuid4().hex[:12]}"


# ── Space ────────────────────────────────────────────────────────────


@dataclass
class SpaceConfig:
    """A single Space."""

    space_id: str
    name: str
    icon: str
    accent: AccentName
    display_order: int
    is_default: bool
    pins: list[PinConfig] = field(default_factory=list)
    density: DensityName = "comfortable"
    created_at: str | None = None  # ISO-8601
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "space_id": self.space_id,
            "name": self.name,
            "icon": self.icon,
            "accent": self.accent,
            "display_order": self.display_order,
            "is_default": self.is_default,
            "density": self.density,
            "pins": [p.to_dict() for p in self.pins],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpaceConfig":
        return cls(
            space_id=data["space_id"],
            name=data["name"],
            icon=data["icon"],
            accent=data.get("accent", "neutral"),
            display_order=int(data.get("display_order", 0)),
            is_default=bool(data.get("is_default", False)),
            pins=[PinConfig.from_dict(p) for p in data.get("pins", [])],
            density=data.get("density", "comfortable"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    @staticmethod
    def new_id() -> str:
        return f"sp_{uuid.uuid4().hex[:12]}"


# ── Resolved pin (returned by API, not stored) ───────────────────────


@dataclass
class ResolvedPin:
    """Pin enriched with server-side-resolved display data.

    `GET /api/v1/spaces` returns this shape so the client never has
    to resolve a seed_key to a saved-view-id or fetch a saved-view
    title via a second round trip. If the pin target is unavailable
    (deleted, access revoked), `unavailable=True`.
    """

    pin_id: str
    pin_type: PinType
    target_id: str
    display_order: int
    label: str
    icon: str
    href: str | None  # resolved navigate URL (same for saved views + nav items)
    unavailable: bool = False
    # Present only for saved_view pins when resolved successfully.
    saved_view_id: str | None = None
    saved_view_title: str | None = None
    # Present only for triage_queue pins. Pending item count the user
    # would see if they opened this queue right now — used as a sidebar
    # badge. Excludes snoozed items (see triage.engine.queue_count).
    # None for non-triage pin types + for unavailable triage pins.
    queue_item_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pin_id": self.pin_id,
            "pin_type": self.pin_type,
            "target_id": self.target_id,
            "display_order": self.display_order,
            "label": self.label,
            "icon": self.icon,
            "href": self.href,
            "unavailable": self.unavailable,
            "saved_view_id": self.saved_view_id,
            "saved_view_title": self.saved_view_title,
            "queue_item_count": self.queue_item_count,
        }


@dataclass
class ResolvedSpace:
    """Space with pins resolved for the API response."""

    space_id: str
    name: str
    icon: str
    accent: AccentName
    display_order: int
    is_default: bool
    density: DensityName
    pins: list[ResolvedPin]
    created_at: str | None
    updated_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "space_id": self.space_id,
            "name": self.name,
            "icon": self.icon,
            "accent": self.accent,
            "display_order": self.display_order,
            "is_default": self.is_default,
            "density": self.density,
            "pins": [p.to_dict() for p in self.pins],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ── Constants ────────────────────────────────────────────────────────

# Max number of spaces per user. Psychological clarity threshold per
# the UX arc architecture doc. Enforced at the API layer.
MAX_SPACES_PER_USER = 5

# Max pins per space. Not a hard-coded contract today — clients
# render more if present — but the API soft-caps creation to keep
# sidebar sane. Match the spec's "~20 pins each" upper bound.
MAX_PINS_PER_SPACE = 20


# ── Error types ──────────────────────────────────────────────────────


class SpaceError(Exception):
    """Base error for spaces service. `http_status` lets the API
    route translate cleanly to HTTPException."""

    http_status = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)


class SpaceNotFound(SpaceError):
    http_status = 404


class SpacePermissionDenied(SpaceError):
    http_status = 403


class SpaceLimitExceeded(SpaceError):
    http_status = 400


class PinNotFound(SpaceError):
    http_status = 404


# ── Helpers ──────────────────────────────────────────────────────────


def now_iso() -> str:
    """UTC ISO-8601 string — stored in space/pin timestamps."""
    return datetime.now(timezone.utc).isoformat()
