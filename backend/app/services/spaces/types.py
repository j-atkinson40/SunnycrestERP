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
#
# Widget Library Phase W-2 (April 2026) added `widget` per Decision
# 2 of the Widget Library Architecture spec — Spaces sidebar absorbs
# widget pins so users have one mental model: pin to dashboard OR
# pin to sidebar (Glance variant). DESIGN_LANGUAGE.md §12.5
# documents the composition; sidebar widget pins always use Glance
# variant (the only valid sidebar variant per §12.2 compatibility
# matrix).
PinType = Literal["saved_view", "nav_item", "triage_queue", "widget"]

# ── Phase 8e.2 — portal-as-space-with-modifiers types ──────────────
#
# Three modifier fields on SpaceConfig distinguish platform spaces
# from portal spaces without introducing a separate primitive. Per
# SPACES_ARCHITECTURE.md §10:
#
#   - access_mode = "platform": office UX (DotNav, command bar,
#     customization). Existing pre-8e.2 behavior.
#   - access_mode = "portal_partner": internal-but-restricted
#     operational role (driver, yard operator, removal staff).
#     Portal UI shell; no DotNav / command bar / settings.
#   - access_mode = "portal_external": external-user portal (family,
#     supplier, customer, partner). Same restricted UI shell as
#     portal_partner; audit + security semantics may differ.
#
# tenant_branding: when True, portal UI shell applies tenant
# branding (logo, brand color) on the highest-attention surfaces
# (header, primary CTA, active tab indicator). Brand color is a
# wash, not a reskin — status colors, typography, surface tokens
# stay platform per DESIGN_LANGUAGE.
#
# write_mode: narrows the set of actions permitted on data reachable
# from this space.
#   - "full": same as any tenant user.
#   - "limited": can update specific fields (e.g., driver updates
#     delivery status, proof-of-delivery) but not edit underlying
#     orders.
#   - "read_only": cannot mutate any data.
AccessMode = Literal["platform", "portal_partner", "portal_external"]
WriteMode = Literal["full", "limited", "read_only"]


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

    For `pin_type="triage_queue"`:
      - `target_id` is the queue id (e.g. `task_triage`).
      - `target_seed_key` is None.

    Widget Library Phase W-2 — for `pin_type="widget"`:
      - `target_id` is the widget_id (e.g. `scheduling.ancillary-pool`).
      - `target_seed_key` is None.
      - `variant_id` defaults to "glance" at resolve time (the only
        valid sidebar variant per DESIGN_LANGUAGE.md §12.2).
      - `config` carries per-instance widget configuration if the
        widget declares a config_schema (e.g. a saved_view widget
        pin uses config={"view_id": "..."}). None for widgets without
        per-instance config.
    """

    pin_id: str
    pin_type: PinType
    target_id: str
    display_order: int
    label_override: str | None = None
    target_seed_key: str | None = None
    # Widget Library Phase W-2 — variant-aware pin storage.
    # variant_id is None for non-widget pins; widget pins default to
    # "glance" at resolve time when stored as None.
    variant_id: str | None = None
    # Widget Library Phase W-2 — per-instance widget config (e.g.
    # saved_view widget gets config={"view_id": "..."}). None for
    # non-widget pins or widgets without per-instance config.
    config: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pin_id": self.pin_id,
            "pin_type": self.pin_type,
            "target_id": self.target_id,
            "display_order": self.display_order,
            "label_override": self.label_override,
            "target_seed_key": self.target_seed_key,
            "variant_id": self.variant_id,
            "config": self.config,
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
            variant_id=data.get("variant_id"),
            config=data.get("config"),
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
    # Workflow Arc Phase 8a — platform-owned system spaces (Settings
    # being the first) set is_system=True. Users can rename, recolor,
    # reorder pins, and hide them via display_order tricks, but
    # CANNOT delete them. The delete-space service raises SpaceError
    # with a helpful message. System spaces also re-seed if missing
    # from preferences.spaces on next load — defense in depth against
    # manual JSONB edits.
    is_system: bool = False
    # Phase 8e — deliberate-activation landing route.
    # When the user switches INTO this space via a deliberate action
    # (DotNav click, dropdown click, Switch-to-X command-bar result),
    # the frontend navigates here. None = no navigation (stay on
    # whatever route they were on). Keyboard shortcuts (Cmd+[/Cmd+])
    # deliberately do NOT trigger the landing-route navigation —
    # rapid-switching across spaces shouldn't fling the user between
    # routes. See SPACES_ARCHITECTURE.md for the "deliberate vs.
    # keyboard" distinction.
    default_home_route: str | None = None
    # Phase 8e.2 — portal-as-space-with-modifiers.
    # See SPACES_ARCHITECTURE.md §10. For legacy rows (pre-8e.2),
    # `from_dict` defaults these to platform/False/full, preserving
    # existing behavior.
    access_mode: AccessMode = "platform"
    tenant_branding: bool = False
    write_mode: WriteMode = "full"
    # Optional per-space JWT TTL override (minutes). None → the
    # portal realm default (12h for portal_partner, likely 1h for
    # portal_external per type). Future portal types declare their
    # preferred TTL here.
    session_timeout_minutes: int | None = None
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
            "is_system": self.is_system,
            "default_home_route": self.default_home_route,
            "access_mode": self.access_mode,
            "tenant_branding": self.tenant_branding,
            "write_mode": self.write_mode,
            "session_timeout_minutes": self.session_timeout_minutes,
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
            is_system=bool(data.get("is_system", False)),
            default_home_route=data.get("default_home_route"),
            # Phase 8e.2 — legacy rows (pre-8e.2) default to platform
            # semantics; unchanged behavior.
            access_mode=data.get("access_mode", "platform"),
            tenant_branding=bool(data.get("tenant_branding", False)),
            write_mode=data.get("write_mode", "full"),
            session_timeout_minutes=data.get("session_timeout_minutes"),
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
    # Widget Library Phase W-2 — present only for widget pins.
    # widget_id is the catalog reference (e.g. `scheduling.ancillary-
    # pool`); variant_id is the resolved variant ("glance" default
    # for sidebar). config is per-instance widget config (None for
    # widgets without per-instance config). The frontend
    # PinnedSection passes these through to `getWidgetRenderer()`.
    widget_id: str | None = None
    variant_id: str | None = None
    config: dict[str, Any] | None = None

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
            "widget_id": self.widget_id,
            "variant_id": self.variant_id,
            "config": self.config,
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
    is_system: bool = False
    default_home_route: str | None = None
    # Phase 8e.2 — see SpaceConfig.
    access_mode: AccessMode = "platform"
    tenant_branding: bool = False
    write_mode: WriteMode = "full"
    session_timeout_minutes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "space_id": self.space_id,
            "name": self.name,
            "icon": self.icon,
            "accent": self.accent,
            "display_order": self.display_order,
            "is_default": self.is_default,
            "density": self.density,
            "is_system": self.is_system,
            "default_home_route": self.default_home_route,
            "access_mode": self.access_mode,
            "tenant_branding": self.tenant_branding,
            "write_mode": self.write_mode,
            "session_timeout_minutes": self.session_timeout_minutes,
            "pins": [p.to_dict() for p in self.pins],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ── Constants ────────────────────────────────────────────────────────

# Max number of spaces per user. Phase 8e bumped 5 → 7 to accommodate
# users who pick up the Settings system space (Phase 8a) plus multiple
# role-seeded spaces plus custom user-created spaces. DotNav horizontal
# layout verified to accommodate 7 dots at default sidebar widths.
# Still bounded for psychological clarity — 10+ creates UI noise.
MAX_SPACES_PER_USER = 7

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
