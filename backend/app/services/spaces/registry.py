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

from app.services.spaces.types import (
    AccentName,
    AccessMode,
    DensityName,
    PinType,
    WriteMode,
)

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
    # Phase 8e — deliberate-activation landing route for the seeded
    # space. See SpaceConfig.default_home_route.
    default_home_route: str | None = None
    # Phase 8e.2 — portal-as-space-with-modifiers. Templates for
    # operational roles (driver, future yard_operator, etc.) declare
    # access_mode="portal_partner" to surface portal UX semantics
    # when the user logs in. Existing office templates keep the
    # "platform" default. See SPACES_ARCHITECTURE.md §10.
    access_mode: AccessMode = "platform"
    tenant_branding: bool = False
    write_mode: WriteMode = "full"
    session_timeout_minutes: int | None = None


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
            default_home_route="/cases",
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
            default_home_route="/financials",
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
            default_home_route="/dashboard",
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
            default_home_route="/cases",
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
            default_home_route="/financials",
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
            default_home_route="/financials",
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
            default_home_route="/scheduling",
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
            default_home_route="/financials",
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
    # Phase 8e enrichment — safety_program_triage pin added alongside
    # task_triage. Production managers see both pending safety program
    # reviews (post-Phase 8d.1) and task-triage items at the top of
    # the Production space.
    ("manufacturing", "production"): [
        SpaceTemplate(
            template_id="production",
            name="Production",
            icon="factory",
            accent="industrial",
            is_default=True,
            default_home_route="/production-hub",
            pins=[
                # Follow-up 1 — production managers have cross-
                # vertical tasks (equipment inspections, training
                # renewals, etc.) flowing through task_triage. Same
                # shortcut as director Arrangement.
                PinSeed(pin_type="triage_queue", target="task_triage"),
                # Phase 8e — safety program approvals (Phase 8d.1) pin.
                PinSeed(pin_type="triage_queue", target="safety_program_triage"),
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
            default_home_route="/scheduling",
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
            default_home_route="/production-hub",
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
            default_home_route="/quoting",
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
            default_home_route="/dashboard",
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

    # ────────────────────────────────────────────────────────────────
    # Phase 8e — new (vertical, role) combinations
    # ────────────────────────────────────────────────────────────────

    # ── Cemetery — admin ──
    # Cemetery operators manage interments + plots + deeds. Admin
    # picks up Operations (primary), Administrative (books), Ownership
    # (KPI lens) — mirrors manufacturing/admin's shape with cemetery-
    # specific pins.
    ("cemetery", "admin"): [
        SpaceTemplate(
            template_id="operations",
            name="Operations",
            icon="map-pin",
            accent="industrial",
            is_default=True,
            default_home_route="/interments",
            pins=[
                PinSeed(pin_type="triage_queue", target="task_triage"),
                PinSeed(pin_type="nav_item", target="/interments"),
                PinSeed(pin_type="nav_item", target="/plots"),
                PinSeed(pin_type="nav_item", target="/deeds"),
                PinSeed(
                    pin_type="saved_view",
                    target="saved_view_seed:admin:recent_cases",
                ),
            ],
        ),
        SpaceTemplate(
            template_id="administrative",
            name="Administrative",
            icon="receipt",
            accent="crisp",
            is_default=False,
            default_home_route="/financials",
            pins=[
                PinSeed(pin_type="nav_item", target="/financials"),
                PinSeed(
                    pin_type="saved_view",
                    target="saved_view_seed:admin:outstanding_invoices",
                ),
            ],
        ),
        SpaceTemplate(
            template_id="ownership",
            name="Ownership",
            icon="trending-up",
            accent="neutral",
            is_default=False,
            default_home_route="/dashboard",
            pins=[
                PinSeed(pin_type="nav_item", target="/financials"),
                PinSeed(pin_type="nav_item", target="/dashboard"),
            ],
        ),
    ],

    # ── Cemetery — office ──
    ("cemetery", "office"): [
        SpaceTemplate(
            template_id="administrative",
            name="Administrative",
            icon="receipt",
            accent="crisp",
            is_default=True,
            default_home_route="/financials",
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
            icon="map-pin",
            accent="forward",
            is_default=False,
            default_home_route="/interments",
            pins=[
                PinSeed(pin_type="nav_item", target="/interments"),
                PinSeed(pin_type="nav_item", target="/plots"),
            ],
        ),
    ],

    # ── Crematory — admin ──
    # Crematory operators run sequential cremation cases with strict
    # chain-of-custody. Operations space (default) + Administrative.
    # No Ownership tier today — add later if demand surfaces.
    ("crematory", "admin"): [
        SpaceTemplate(
            template_id="operations",
            name="Operations",
            icon="factory",
            accent="industrial",
            is_default=True,
            default_home_route="/crematory/schedule",
            pins=[
                PinSeed(pin_type="triage_queue", target="task_triage"),
                PinSeed(pin_type="nav_item", target="/crematory/cases"),
                PinSeed(pin_type="nav_item", target="/crematory/schedule"),
                PinSeed(pin_type="nav_item", target="/crematory/custody"),
                PinSeed(
                    pin_type="saved_view",
                    target="saved_view_seed:admin:recent_cases",
                ),
            ],
        ),
        SpaceTemplate(
            template_id="administrative",
            name="Administrative",
            icon="receipt",
            accent="crisp",
            is_default=False,
            default_home_route="/financials",
            pins=[
                PinSeed(pin_type="nav_item", target="/financials"),
                PinSeed(
                    pin_type="saved_view",
                    target="saved_view_seed:admin:outstanding_invoices",
                ),
            ],
        ),
    ],

    # ── Crematory — office ──
    ("crematory", "office"): [
        SpaceTemplate(
            template_id="operations",
            name="Operations",
            icon="factory",
            accent="industrial",
            is_default=True,
            default_home_route="/crematory/schedule",
            pins=[
                PinSeed(pin_type="nav_item", target="/crematory/cases"),
                PinSeed(pin_type="nav_item", target="/crematory/schedule"),
            ],
        ),
        SpaceTemplate(
            template_id="administrative",
            name="Administrative",
            icon="receipt",
            accent="crisp",
            is_default=False,
            default_home_route="/financials",
            pins=[
                PinSeed(
                    pin_type="saved_view",
                    target="saved_view_seed:office:outstanding_invoices",
                ),
                PinSeed(pin_type="nav_item", target="/financials"),
            ],
        ),
    ],

    # ── Funeral home — accountant ──
    # Books (primary financial work) + Reports (compilation /
    # analysis). Accountants in FH vertical rarely touch cases
    # directly — no Arrangement space seeded.
    ("funeral_home", "accountant"): [
        SpaceTemplate(
            template_id="books",
            name="Books",
            icon="calculator",
            accent="crisp",
            is_default=True,
            default_home_route="/financials",
            pins=[
                PinSeed(pin_type="nav_item", target="/financials"),
                PinSeed(
                    pin_type="saved_view",
                    target="saved_view_seed:accountant:outstanding_invoices",
                ),
            ],
        ),
        SpaceTemplate(
            template_id="reports",
            name="Reports",
            icon="bar-chart-3",
            accent="neutral",
            is_default=False,
            default_home_route="/reports",
            pins=[
                PinSeed(pin_type="nav_item", target="/reports"),
                PinSeed(pin_type="nav_item", target="/financials/board"),
            ],
        ),
    ],

    # ── Manufacturing — accountant ──
    # Like FH accountant but with a Compliance lens because MFG
    # tenants run OSHA + NPCA + training compliance that intersects
    # with the books (training expenses, safety program costs, etc.).
    ("manufacturing", "accountant"): [
        SpaceTemplate(
            template_id="books",
            name="Books",
            icon="calculator",
            accent="crisp",
            is_default=True,
            default_home_route="/financials",
            pins=[
                PinSeed(pin_type="nav_item", target="/financials"),
                PinSeed(
                    pin_type="saved_view",
                    target="saved_view_seed:accountant:outstanding_invoices",
                ),
            ],
        ),
        SpaceTemplate(
            template_id="reports",
            name="Reports",
            icon="bar-chart-3",
            accent="neutral",
            is_default=False,
            default_home_route="/reports",
            pins=[
                PinSeed(pin_type="nav_item", target="/reports"),
                PinSeed(pin_type="nav_item", target="/financials/board"),
            ],
        ),
        SpaceTemplate(
            template_id="compliance",
            name="Compliance",
            icon="shield-check",
            accent="forward",
            is_default=False,
            default_home_route="/compliance",
            pins=[
                PinSeed(pin_type="nav_item", target="/compliance"),
            ],
        ),
    ],

    # ── Manufacturing — safety trainer ──
    # Promoted from FALLBACK in Phase 8e. Safety trainers run the
    # OSHA-300 + training-expiry + incident-reporting workstream.
    # Compliance (primary) carries the safety_program_triage pin
    # from Phase 8d.1; Training holds the calendar + toolbox talks.
    ("manufacturing", "safety_trainer"): [
        SpaceTemplate(
            template_id="compliance",
            name="Compliance",
            icon="shield-check",
            accent="forward",
            is_default=True,
            default_home_route="/safety",
            pins=[
                PinSeed(pin_type="triage_queue", target="safety_program_triage"),
                PinSeed(pin_type="nav_item", target="/safety"),
                PinSeed(pin_type="nav_item", target="/safety/osha-300"),
                PinSeed(pin_type="nav_item", target="/safety/incidents"),
            ],
        ),
        SpaceTemplate(
            template_id="training",
            name="Training",
            icon="graduation-cap",
            accent="neutral",
            is_default=False,
            default_home_route="/safety/training",
            pins=[
                PinSeed(pin_type="nav_item", target="/safety/training"),
                PinSeed(pin_type="nav_item", target="/safety/training/calendar"),
                PinSeed(pin_type="nav_item", target="/safety/toolbox-talks"),
            ],
        ),
    ],

    # ────────────────────────────────────────────────────────────────
    # Phase 8e.2 — first portal template (reconnaissance)
    # ────────────────────────────────────────────────────────────────
    # MFG driver gets a portal-shaped space (access_mode=portal_partner,
    # tenant_branding=True, write_mode=limited). This is the first
    # concrete portal use case validating the portal-as-space-with-
    # modifiers architecture from SPACES_ARCHITECTURE.md §10.
    #
    # Invariant (test-enforced): driver role MUST have access_mode
    # starting with "portal_". Office roles (admin/director/etc.) MUST
    # have access_mode="platform". See
    # `tests/test_spaces_phase8e.py::TestDriverTemplatesUsePortalAccessMode`.
    #
    # Single space, no pins — drivers work one thing at a time. The
    # DotNav, command bar, and settings are hidden by the portal shell.
    # `default_home_route` navigates to the portal-scoped driver home
    # (the slug is resolved at render time by the portal UI shell —
    # the stored route is relative to the portal).
    ("manufacturing", "driver"): [
        SpaceTemplate(
            template_id="driver_portal",
            name="Driver",
            icon="truck",
            accent="industrial",
            is_default=True,
            # The portal URL shape is `/portal/<slug>/driver`. The
            # slug is filled in at render time by PortalLayout; the
            # stored route is the portal-relative suffix.
            default_home_route="/driver",
            density="comfortable",
            access_mode="portal_partner",
            tenant_branding=True,
            write_mode="limited",
            # 12-hour session matches a driver's workday — avoids
            # mid-route logouts.
            session_timeout_minutes=12 * 60,
            pins=[],  # Driver portal: one space, no pin clutter.
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
    default_home_route="/dashboard",
    pins=[
        PinSeed(pin_type="nav_item", target="/dashboard"),
    ],
)


# ── System spaces (Workflow Arc Phase 8a) ──────────────────────────
# Platform-owned spaces gated by permission, not (vertical, role).
# Unlike role-based SEED_TEMPLATES:
#   - Conditionally seeded based on a live user_has_permission check
#   - Set is_system=True on the stored SpaceConfig (blocks delete)
#   - Tracked via preferences.system_spaces_seeded list[str]
#   - DotNav renders them leftmost
#   - User can rename + recolor + reorder pins; cannot delete


@dataclass
class SystemSpaceTemplate:
    """A platform-owned system space. Unlike role-based templates,
    system spaces are conditionally seeded based on a live permission
    check — not a (vertical, role_slug) lookup."""

    template_id: str
    name: str
    icon: str
    accent: AccentName
    pins: list[PinSeed] = field(default_factory=list)
    density: DensityName = "comfortable"
    # Permission required to see this system space. Matches the
    # permission_service vocabulary. None = everyone gets it
    # (reserved for future; not used today).
    required_permission: str | None = None
    # System spaces always sort leftmost — negative display_order
    # keeps them ahead of user-created spaces regardless of the
    # user's reorder history.
    display_order: int = -1000
    # Phase 8e — deliberate-activation landing route (same contract
    # as SpaceTemplate.default_home_route).
    default_home_route: str | None = None


SYSTEM_SPACE_TEMPLATES: list[SystemSpaceTemplate] = [
    # Phase W-4a — Home system space (always-first, contains Pulse).
    # Per BRIDGEABLE_MASTER §3.26.1.1, Home is "always present, always
    # first in navigation" and renders the Pulse — the platform's
    # primary Monitor surface and most distinctive product feature.
    # Seeded for every active user regardless of role/permission;
    # `default_home_route="/home"` so DotNav click navigates straight
    # to PulseSurface. `display_order=-2000` ranks it leftmost of all
    # system spaces (Settings is -1000). Pins are intentionally empty:
    # Pulse is intelligence-composed, not user-curated, so the Home
    # space's pin list is conceptually meaningless. The space exists
    # to give DotNav an always-present leftmost slot that routes to
    # the Pulse.
    SystemSpaceTemplate(
        template_id="home",
        name="Home",
        icon="home",
        accent="warm",
        required_permission=None,
        pins=[],
        display_order=-2000,
        default_home_route="/home",
    ),
    SystemSpaceTemplate(
        template_id="settings",
        name="Settings",
        icon="settings",
        accent="neutral",
        required_permission="admin",
        # Phase 8a ships four pins; existing Settings nav sub-section
        # stays during transition so the full 30+ settings pages
        # remain reachable. Phase 8h+ migrates additional pages.
        pins=[
            PinSeed(
                pin_type="nav_item",
                target="/settings/workflows",
                label_override="Workflows",
            ),
            PinSeed(
                pin_type="nav_item",
                target="/saved-views",
                label_override="Saved views",
            ),
            PinSeed(
                pin_type="nav_item",
                target="/admin/users",
                label_override="Users",
            ),
            PinSeed(
                pin_type="nav_item",
                target="/admin/roles",
                label_override="Roles",
            ),
        ],
        display_order=-1000,
        default_home_route="/settings/workflows",
    ),
]


def get_system_space_templates_for_user(
    db: Any, user: Any
) -> list[SystemSpaceTemplate]:
    """Return system space templates visible to this user based on
    each template's required_permission. Evaluated at seed time AND
    at resolve time so permission revocations hide the space from
    the dot nav without a re-seed."""
    from app.services.permission_service import user_has_permission

    out: list[SystemSpaceTemplate] = []
    for tpl in SYSTEM_SPACE_TEMPLATES:
        perm = tpl.required_permission
        if perm is None or user_has_permission(user, db, perm):
            out.append(tpl)
    return out


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
    # ── Phase 8e additions ──────────────────────────────────────────
    # Cemetery
    "/interments": ("Interments", "MapPin"),
    "/plots": ("Plot Map", "MapPin"),
    "/deeds": ("Deeds", "FileText"),
    # Crematory
    "/crematory/cases": ("Cremation Cases", "FolderOpen"),
    "/crematory/schedule": ("Schedule", "Calendar"),
    "/crematory/custody": ("Chain of Custody", "Link"),
    # Accountant
    "/reports": ("Reports", "BarChart3"),
    "/financials/board": ("Financials Board", "LayoutDashboard"),
    # Compliance + safety
    "/compliance": ("Compliance Hub", "ShieldCheck"),
    "/safety": ("Safety", "ShieldCheck"),
    "/safety/training": ("Safety Training", "BookOpen"),
    "/safety/osha-300": ("OSHA 300", "FileCheck"),
    "/safety/incidents": ("Incidents", "Bell"),
    "/safety/training/calendar": ("Training Calendar", "Calendar"),
    "/safety/toolbox-talks": ("Toolbox Talks", "Bell"),
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
