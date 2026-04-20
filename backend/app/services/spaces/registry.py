"""Space template registry — Phase 3.

Each (vertical, role_slug) has a list of `SpaceTemplate` defaults
that get seeded on user creation OR role change. Exactly one of
each role's templates has `is_default=True` (the space the user
lands in on first login).

Templates describe pins via two shapes:

  - `PinSeed(pin_type="saved_view", target_seed_key=...)` —
    resolves to the user's actual saved-view UUID at seed-time
    via `crud._resolve_saved_view_seed_key_to_id`. If a seed key
    doesn't resolve for this user (e.g. Phase 2 didn't seed that
    specific template for the role), the pin is omitted — NOT
    stored as unavailable. Idempotency across Phase 2 + Phase 3
    means this rarely matters in practice.

  - `PinSeed(pin_type="nav_item", target_id="/cases")` — pin to
    a nav item by href. Labels come from a static fallback table
    (since templates are declared server-side and navigation is
    client-side). The API's pin-resolver enriches the label at
    read-time from the user's live navigation config.

To add a new template: append a `SpaceTemplate` to
`SEED_TEMPLATES[(vertical, role_slug)]`. Pre-existing users pick
it up on the NEXT role change (or never, if the role already
appears in `preferences.spaces_seeded_for_roles`). Phase 3 accepts
the same trade-off Phase 2 accepts — template additions don't
backfill; bump a role-version or run a one-off script if needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.spaces.types import AccentName, DensityName, PinType

# ── Template shapes ──────────────────────────────────────────────────


@dataclass
class PinSeed:
    """One pin in a space template."""

    pin_type: PinType
    # For saved_view: stable key like "saved_view_seed:director:my_active_cases"
    # For nav_item: href like "/cases"
    target: str
    label_override: str | None = None


@dataclass
class SpaceTemplate:
    """One space template. Per-user instantiation fills in IDs,
    display_order, and timestamps."""

    template_id: str          # stable key within (vertical, role)
    name: str
    icon: str                 # lucide icon name
    accent: AccentName
    is_default: bool
    pins: list[PinSeed] = field(default_factory=list)
    density: DensityName = "comfortable"


# ── Templates by (vertical, role_slug) ──────────────────────────────
# Keys: (vertical, role_slug). Values: ordered list of SpaceTemplate
# (display_order = index in list).
#
# Role slugs match Role.slug. Common slugs: admin, office, director,
# production, driver, accountant. Unknown slugs are silently no-op.


SEED_TEMPLATES: dict[tuple[str, str], list[SpaceTemplate]] = {
    # ── Funeral home director ──
    # Operationalizes the two-hub pattern the master doc describes:
    #   Arrangement = Funeral Direction hub
    #   Administrative = Business Management hub
    #   Ownership = strategic lens
    ("funeral_home", "director"): [
        SpaceTemplate(
            template_id="arrangement",
            name="Arrangement",
            icon="calendar-heart",
            accent="warm",
            is_default=True,
            pins=[
                # Follow-up 1 — directors get their task triage queue
                # pinned at the top of Arrangement so the decision
                # stream is one click from their primary workspace.
                PinSeed(pin_type="triage_queue", target="task_triage"),
                PinSeed(pin_type="nav_item", target="/cases"),
                PinSeed(pin_type="nav_item", target="/cases/new"),
                PinSeed(
                    pin_type="saved_view",
                    target="saved_view_seed:director:my_active_cases",
                ),
                PinSeed(
                    pin_type="saved_view",
                    target="saved_view_seed:director:this_weeks_services",
                ),
            ],
        ),
        SpaceTemplate(
            template_id="administrative",
            name="Administrative",
            icon="receipt",
            accent="crisp",
            is_default=False,
            pins=[
                PinSeed(pin_type="nav_item", target="/financials"),
                PinSeed(pin_type="nav_item", target="/funeral-home/compliance"),
            ],
        ),
        SpaceTemplate(
            template_id="ownership",
            name="Ownership",
            icon="trending-up",
            accent="neutral",
            is_default=False,
            pins=[
                PinSeed(pin_type="nav_item", target="/financials"),
                PinSeed(pin_type="nav_item", target="/dashboard"),
            ],
        ),
    ],

    # ── Funeral home admin (same vertical, broader role) ──
    ("funeral_home", "admin"): [
        SpaceTemplate(
            template_id="arrangement",
            name="Arrangement",
            icon="calendar-heart",
            accent="warm",
            is_default=True,
            pins=[
                PinSeed(pin_type="nav_item", target="/cases"),
                PinSeed(
                    pin_type="saved_view",
                    target="saved_view_seed:admin:my_active_cases",
                ),
            ],
        ),
        SpaceTemplate(
            template_id="administrative",
            name="Administrative",
            icon="receipt",
            accent="crisp",
            is_default=False,
            pins=[
                PinSeed(pin_type="nav_item", target="/financials"),
                PinSeed(pin_type="nav_item", target="/funeral-home/compliance"),
            ],
        ),
    ],

    # ── Manufacturing — office manager / bookkeeper ──
    ("manufacturing", "office"): [
        SpaceTemplate(
            template_id="administrative",
            name="Administrative",
            icon="receipt",
            accent="crisp",
            is_default=True,
            pins=[
                PinSeed(
                    pin_type="saved_view",
                    target="saved_view_seed:office:outstanding_invoices",
                ),
                PinSeed(pin_type="nav_item", target="/financials"),
            ],
        ),
        SpaceTemplate(
            template_id="operational",
            name="Operational",
            icon="truck",
            accent="forward",
            is_default=False,
            pins=[
                PinSeed(pin_type="nav_item", target="/order-station"),
                PinSeed(pin_type="nav_item", target="/scheduling"),
            ],
        ),
    ],

    # ── Funeral home office ──
    ("funeral_home", "office"): [
        SpaceTemplate(
            template_id="administrative",
            name="Administrative",
            icon="receipt",
            accent="crisp",
            is_default=True,
            pins=[
                PinSeed(
                    pin_type="saved_view",
                    target="saved_view_seed:office:outstanding_invoices",
                ),
                PinSeed(pin_type="nav_item", target="/financials"),
            ],
        ),
    ],

    # ── Manufacturing — production ──
    ("manufacturing", "production"): [
        SpaceTemplate(
            template_id="production",
            name="Production",
            icon="factory",
            accent="industrial",
            is_default=True,
            pins=[
                # Follow-up 1 — production managers have cross-
                # vertical tasks (equipment inspections, training
                # renewals, etc.) flowing through task_triage. Same
                # shortcut as director Arrangement.
                PinSeed(pin_type="triage_queue", target="task_triage"),
                PinSeed(
                    pin_type="saved_view",
                    target="saved_view_seed:production:active_pours",
                ),
                PinSeed(pin_type="nav_item", target="/production-hub"),
                PinSeed(pin_type="nav_item", target="/console/operations"),
            ],
        ),
        SpaceTemplate(
            template_id="operations",
            name="Operations",
            icon="kanban",
            accent="crisp",
            is_default=False,
            pins=[
                PinSeed(pin_type="nav_item", target="/scheduling"),
                PinSeed(pin_type="nav_item", target="/order-station"),
            ],
        ),
    ],

    # ── Manufacturing — owner / admin ──
    ("manufacturing", "admin"): [
        SpaceTemplate(
            template_id="production",
            name="Production",
            icon="factory",
            accent="industrial",
            is_default=True,
            pins=[
                PinSeed(pin_type="nav_item", target="/production-hub"),
                PinSeed(pin_type="nav_item", target="/console/operations"),
            ],
        ),
        SpaceTemplate(
            template_id="sales",
            name="Sales",
            icon="store",
            accent="forward",
            is_default=False,
            pins=[
                PinSeed(pin_type="nav_item", target="/quoting"),
                PinSeed(pin_type="nav_item", target="/vault/crm"),
            ],
        ),
        SpaceTemplate(
            template_id="ownership",
            name="Ownership",
            icon="trending-up",
            accent="neutral",
            is_default=False,
            pins=[
                PinSeed(pin_type="nav_item", target="/financials"),
                PinSeed(pin_type="nav_item", target="/dashboard"),
                PinSeed(
                    pin_type="saved_view",
                    target="saved_view_seed:admin:outstanding_invoices",
                ),
            ],
        ),
    ],
}


# ── Fallback template for users without a matched role ──────────────
# Per the spec: "User with no roles: Seed a single 'General' space
# with minimal pins. Don't leave them with zero spaces." Also used
# when (vertical, role_slug) misses — always give the user a floor.


FALLBACK_TEMPLATE: SpaceTemplate = SpaceTemplate(
    template_id="general",
    name="General",
    icon="home",
    accent="neutral",
    is_default=True,
    pins=[
        PinSeed(pin_type="nav_item", target="/dashboard"),
    ],
)


# ── Static label table for nav-item pins ────────────────────────────
# Labels for nav hrefs seen in the templates above. Keeps backend
# self-sufficient without having to ingest navigation-service.ts.
# The API resolver falls back to this map for any nav_item pin
# whose href can't be located in the user's live nav tree (extension
# disabled, module gated off, etc.) so the pin still has a readable
# label before being marked unavailable.


NAV_LABEL_TABLE: dict[str, tuple[str, str]] = {
    # href → (label, icon)
    "/cases": ("Active Cases", "FolderOpen"),
    "/cases/new": ("New Case", "Plus"),
    "/dashboard": ("Home", "Home"),
    "/financials": ("Financials", "BarChart3"),
    "/funeral-home/compliance": ("FTC Compliance", "Scale"),
    "/order-station": ("Order Station", "Zap"),
    "/scheduling": ("Scheduling Board", "Kanban"),
    "/console/operations": ("Operations Board", "LayoutDashboard"),
    "/production-hub": ("Production", "Factory"),
    "/quoting": ("Quoting", "FileText"),
    "/vault/crm": ("CRM", "Building2"),
}


# ── Public helpers ──────────────────────────────────────────────────


def get_templates(vertical: str | None, role_slug: str | None) -> list[SpaceTemplate]:
    """Return templates for the (vertical, role) pair.

    If the pair has no mapped templates, returns `[FALLBACK_TEMPLATE]`
    — the user still gets a workable "General" space.
    """
    if vertical and role_slug:
        templates = SEED_TEMPLATES.get((vertical, role_slug))
        if templates:
            return list(templates)
    return [FALLBACK_TEMPLATE]


def get_nav_label(href: str) -> tuple[str, str] | None:
    """Lookup a (label, icon) for a nav_item pin by href. Returns
    None when the href isn't in the static table — API falls back
    to `(href, 'Link')` for unknown hrefs."""
    return NAV_LABEL_TABLE.get(href)


def all_template_pairs() -> list[tuple[str, str]]:
    """Test + admin helper: every seeded (vertical, role) pair."""
    return list(SEED_TEMPLATES.keys())


# Used by the command bar to recognize saved-view pin targets vs
# arbitrary strings.
def is_seed_key(target: str) -> bool:
    return target.startswith("saved_view_seed:")


# Expose for tests that want to inspect template shape without
# poking into the module-private dict directly.
def get_all_templates() -> dict[tuple[str, str], list[SpaceTemplate]]:
    return dict(SEED_TEMPLATES)


def get_fallback_template() -> SpaceTemplate:
    return FALLBACK_TEMPLATE


__all__ = [
    "PinSeed",
    "SpaceTemplate",
    "SEED_TEMPLATES",
    "FALLBACK_TEMPLATE",
    "NAV_LABEL_TABLE",
    "get_templates",
    "get_nav_label",
    "all_template_pairs",
    "is_seed_key",
    "get_all_templates",
    "get_fallback_template",
]


# ── Type check helper ───────────────────────────────────────────────
# Keep `Any` import usable even when mypy strict — left for future
# typed-dict conversion pass.
_: Any = None
