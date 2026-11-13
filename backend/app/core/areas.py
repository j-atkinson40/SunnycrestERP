"""Areas — the vocabulary an area-limited role is limited to.

An **area** is a named slice of the tenant app. A role may declare
`limited_to_areas`; a user on such a role is refused every tenant endpoint that
is not tagged with one of those areas, plus the common set below.

⚠️ **DEFAULT DENY, AND THAT IS THE WHOLE POINT.** An endpoint with no `area:` tag
is refused to a limited user. This is deliberately the opposite of the
platform's historical posture: measured 2026-11-03, 1063 of 1920 tenant
endpoints had no per-user gate, and a per-endpoint fix would have been 886 edits
that could each be forgotten. Default-deny closes all of them for a limited role
in one place, and a NEW untagged endpoint is closed the day it is written rather
than the day someone remembers to gate it.

⚠️ **NULL `limited_to_areas` MEANS NOT LIMITED, AND THAT IS NOT THE SAME AS
EMPTY.** NULL is "no area restriction was ever established for this role" —
today's behaviour, byte for byte, for every existing role. `[]` is "limited to
nothing", which refuses everything except the common set. The distinction is
load-bearing and is why the column is nullable with no backfill (CLAUDE.md §5).

### How an endpoint declares its area

A FastAPI tag of the form `area:<key>`, applied at `include_router()` — the
router registration layer:

    v1_router.include_router(
        payroll_reports.router,
        prefix="/payroll-reports",
        tags=["Payroll Reports", "area:payroll"],
    )

Native tags were chosen over a parallel path→area table because the tag sits at
the registration site, cannot drift from the route it describes, and is readable
in the OpenAPI schema. The cost is one extra tag group in `/docs`, which is
cosmetic and considered paid.
"""
from __future__ import annotations

AREA_TAG_PREFIX = "area:"

#: Every area key that exists. A role may only be limited to keys in here, and
#: an `area:` tag naming something absent from this set is a typo that would
#: silently make a router unreachable — so both directions are test-enforced.
#: ⚠️ **PHASE A, 2026-11-06. TAGGING ONLY — NOTHING IS ENFORCED BY THIS.**
#: Every area below is inert until a role's `limited_to_areas` names it, and
#: only `payroll` does today. Phase B turns the rest on role by role.
#:
#: Derived from the ROUTER LIST (158 routers, 1,932 method+path pairs), not
#: from the menu — the menu was the thing that disagreed with the server.
AREA_DESCRIPTIONS: dict[str, str] = {
    "payroll":        "Weekly hours, union dues, remittance, vacation pay.",
    "accounting":     "The books: GL, AR, AP, statements, reconciliation, tax, the accounting agents.",
    "pricing":        "What things cost: price lists, markups, discounts, charge library, inter-licensee rates.",
    "orders":         "Taking and tracking an order through to invoicing.",
    "catalog":        "What is for sale: products, lines, BOM, the product catalogue.",
    "inventory":      "Stock on hand, transfers between licensees.",
    "production":     "Making it: production log, QC, moulds, equipment, work orders.",
    "scheduling":     "Getting it there: delivery, dispatch, drivers, the calendar, union rotations.",
    "customers":      "Who we sell to: CRM, funeral homes, cemeteries, suppliers, carriers.",
    "cases":          "Funeral-home case work: cases, disinterments, SS certificates.",
    "personalization":"Designing the product: personalization studio, Legacies, programs.",
    "resale":         "The urn resale line, end to end.",
    "safety":         "OSHA compliance, training, incidents, toolbox talks.",
    "documents":      "Document templates, rendering, e-signature, email and intake.",
    "settings":       "Administering the tenant: users, roles, locations, modules, imports.",
    "people":         "HR: employee profiles and performance notes. Split out of `settings` "
                      "by James's ruling of 2026-11-06 — performance notes should not sit "
                      "beside locations and modules.",
}

KNOWN_AREAS: frozenset[str] = frozenset({
    *AREA_DESCRIPTIONS,
    "payroll",
    #: Two-step enrolment (Payroll 2). ⚠️ NOT AN AREA A ROLE IS EVER LIMITED TO
    #: BY AN ADMIN — it is the area a user is TEMPORARILY confined to by the
    #: guard when they require two-step and their token has not passed it. The
    #: distinction matters: `limited_to_areas` is a standing property of a role,
    #: this is a property of a token, and both are enforced by the one guard
    #: rather than by two.
    "mfa_enroll",
})


#: ─────────────────────────────────────────────────────────────── view / change
#:
#: ⚠️ **A GRANT HAS A LEVEL, BECAUSE ALL-OR-NOTHING FORCED OVER-GRANTING.**
#: James's ruling of 2026-11-06: "Production needs to *see* orders without
#: editing them, and drivers need to *see* the schedule." Without levels the
#: only way to let production read an order is to let it rewrite one.
#:
#:     view     admits GET
#:     change   admits everything
#:
#: ⚠️ **A BARE AREA NAME MEANS `change`, WHICH IS WHAT MAKES THIS BACKWARD
#: COMPATIBLE.** `limited_to_areas = ["payroll"]` is live on production today
#: and must keep behaving identically, so a string with no level parses as a
#: full grant. `"orders:view"` is the narrowed form. Nothing about the payroll
#: role changes.
VIEW, CHANGE = "view", "change"
_READ_METHODS = frozenset({"GET"})


def parse_area_grant(grant: str) -> tuple[str, str]:
    """`"orders:view"` -> `("orders", "view")`; `"payroll"` -> `("payroll", "change")`."""
    if ":" in grant:
        area, _, level = grant.partition(":")
        return area.strip(), (level.strip() or CHANGE)
    return grant.strip(), CHANGE


def grant_admits(level: str, method: str, path: str) -> bool:
    """Does a grant at `level` admit this method on this route?

    ⚠️ **THE METHOD IS THE PROXY FOR MEANING, AND IT IS WRONG SOMETIMES — SO THE
    EXCEPTIONS ARE NAMED RATHER THAN INFERRED.** A POST that only searches is a
    read; `READ_ONLY_WRITE_VERBS` lists those by hand. I tried deriving the
    list and the heuristic was worthless: 559 non-GET handlers show no write in
    their own body because most delegate to a service that writes, and
    read-sounding names lie in both directions — `/alerts/{id}/resolve`,
    `/suggestions/{id}/accept` and `/health/recalculate` all change things.
    So the default is unmoved: **a non-GET is a change unless it is on the
    list**, and the list is reviewed per route.
    """
    if level == CHANGE:
        return True
    m = (method or "").upper()
    if m in _READ_METHODS:
        return True
    return (m, strip_mount_prefix(path)) in READ_ONLY_WRITE_VERBS


#: Write verbs that only read. ⚠️ EACH ONE CONFIRMED INDIVIDUALLY, not generated.
#: A route missing from here is treated as a change, which is the safe default.
READ_ONLY_WRITE_VERBS: frozenset[tuple[str, str]] = frozenset({
    ("POST", "/command-bar/query"),            # search
    ("POST", "/command-bar/quote-preview"),    # priced preview, persists nothing
    ("POST", "/command-bar/price-list-reference"),
    ("POST", "/saved-views/preview"),          # runs a view's query unsaved
    ("POST", "/nl-creation/extract"),          # extraction only; /create persists
    ("POST", "/core/command"),                 # legacy intent classification
    ("POST", "/core/command-bar/extract"),
    ("POST", "/core/command-bar/ai"),
    ("POST", "/ai/parse-filters"),
    ("POST", "/ai/parse-ap"),
    ("POST", "/ai/parse-inventory"),
    ("POST", "/discount/calculate"),           # computes, does not apply
    ("POST", "/delivery/check-conflict"),
    ("POST", "/order-station/parse-order"),
    ("POST", "/journal-entries/entries/parse"),
    ("POST", "/migration/parse"),
    ("POST", "/data-import/match-customers"),
    ("POST", "/data-import/match-products"),
    ("POST", "/legacy/generate-preview"),
    ("POST", "/catalog-pane/resolve"),
    ("POST", "/onboarding-flow/territory/resolve"),
    ("POST", "/cases/extract-first-call"),
})


#: ─────────────────────────────────────────────── the planned role lists
#:
#: ⚠️ **RECORDED, NOT ENFORCED.** Nothing reads this to make a decision. Phase B
#: copies a role's list into `roles.limited_to_areas`, one role at a time, with
#: a before/after reach comparison each time. Until then every role keeps
#: `limited_to_areas = NULL` and reaches what it reaches today.
#:
#: ⚠️ **NOT WRITTEN TO THE DATABASE, AND THAT IS A DEVIATION FROM THE RULING,
#: FLAGGED RATHER THAN TAKEN QUIETLY.** James asked for the lists "stored on the
#: roles, but NOT enforced yet". `roles.limited_to_areas` is the enforced
#: column — writing them there IS Phase B. A separate `planned_limited_to_areas`
#: column would satisfy both halves and needs a migration, and **the dev
#: database is currently stamped at `r228_capture_prefix_offers`, a revision
#: that no longer exists in the repo**, so `alembic upgrade head` fails locally
#: and a new migration cannot be tested. Keeping the lists here is inert,
#: reviewable in the diff, and per-slug — which is what Phase B wants anyway,
#: since every tenant has its own copy of each role and they all take the same
#: list. Raised for James's call.
#:
#: Each grant is marked where the reasoning was a judgement rather than the job.
PLANNED_ROLE_AREAS: dict[str, tuple[str, ...]] = {
    # driver: sees the run and the safety material. Nothing else.
    "driver":        ("scheduling:view", "safety:view"),
    # office: start narrow per James — widen per person when someone real is
    # invited, because widening later costs nothing and narrowing does not.
    "office":        ("orders:change", "customers:change", "documents:change",
                      "scheduling:view"),
    "office_staff":  ("orders:change", "customers:change", "documents:change",
                      "scheduling:view"),
    # production: `orders:view` is the case that forced levels to exist.
    "production":    ("production:change", "inventory:change", "orders:view",
                      "safety:view", "scheduling:view"),
    "dispatcher":    ("scheduling:change", "orders:view", "customers:view"),
    "director":      ("cases:change", "customers:change", "documents:change",
                      "personalization:change", "scheduling:view"),
    "accountant":    ("accounting:change", "pricing:view", "orders:view",
                      "customers:view"),
    # live today, unchanged by Phase A
    "payroll":       ("payroll:change",),
    # ⚠️ **LIMITED TO NOTHING — THE COMMON SET AND NOTHING ELSE.** James's
    # ruling of 2026-11-06. `employee` is the role `POST /auth/register`
    # handed out to anyone who asked, and it carried no permissions AND no
    # area limit, so it reached all 274 "signed in is enough" routes. The
    # endpoint is deleted and no real user holds the role; this closes what it
    # could have reached.
    #
    # ⚠️ `()` MEANS `[]`, NOT `None`. An empty list is "limited to nothing";
    # absence from this dict is "no limit". `_planned_area_limit` decides by
    # MEMBERSHIP for exactly that reason — an empty tuple is falsy and a
    # truthiness check would have made this role unrestricted.
    "employee":      (),
    # ⚠️ `admin` is DELIBERATELY ABSENT. An unlimited admin is a decision, and
    # its absence here is that decision rather than an oversight: `admin` keeps
    # `limited_to_areas = NULL` and the guard early-returns for it.
}


#: Routers that span several areas and are NOT tagged with one.
#:
#: ⚠️ **THESE BECOME "COMPOSED" SURFACES: each must filter what it returns to
#: the caller's allowed areas.** James's ruling of 2026-11-06. Until a surface
#: does that, a limited role stays refused there — which is today's behaviour,
#: so nothing regresses by waiting. One tag would either over-grant (the note
#: shows everything) or break the surface (the note shows nothing).
#:
#: In the order they matter, which is the order they should be built:
COMPOSED_SURFACES: tuple[tuple[str, str], ...] = (
    ("note",        "The daily note. First thing after sign-in — the payroll "
                    "user's error page IS this surface refusing."),
    ("command-bar", "Opas. The stated primary entrance; Sue's Opas should know "
                    "payroll and nothing else. Must resolve per RESULT."),
    ("core",        "The legacy command/search endpoints Opas still calls."),
    ("briefings",   "Composed from orders, invoices, safety and cases."),
    ("widget-data", "28 pairs, one per widget, each reading a different area. "
                    "Needs per-route tags, not a router tag."),
    ("widgets",     "As widget-data."),
    ("widget-definitions", "As widget-data."),
    ("tasks",       "Task substrate — every area creates tasks."),
    ("vault",       "The cross-cutting hub by definition: documents, CRM, "
                    "intelligence, notifications and accounting under one roof."),
    ("operations-board", "A board composed from production, delivery and orders."),
    ("reports",     "Spans accounting, production and safety."),
    ("report-intelligence", "As reports."),
    ("saved-views", "A saved view's area is its query's area."),
    ("focus",       "The Focus kind decides the area, not the router."),
    ("peek",        "Previews six entity types across areas."),
    ("nl-creation", "Creates entities in several areas from one sentence."),
    ("triage",      "Queues are per-domain; the ROUTER is cross-area."),
    ("intelligence","Cross-system synthesis by definition."),
    ("behavioral",  "Analytics over everyone's activity."),
    ("completeness","Data-quality checks across areas."),
    ("knowledge-base", "Reference content spanning areas."),
    ("announcements", "Tenant-wide messages; not obviously any one area."),
    ("ai",          "Generic AI helpers used by several areas."),
    ("workflows",   "Workflow definitions span areas; the steps decide."),
    ("workflow-authoring", "As workflows."),
    # ⚠️ **THESE FIVE ARE THE COMMON SET'S OWN ROUTERS.** `is_common` matches
    # EXACT routes, so `/auth/me` is common while the `auth` SEGMENT is not —
    # which means the segment needs declaring here or the tagging rule demands
    # an area for a shell router that must not have one. My first version of
    # that rule failed on exactly these five.
    ("auth",        "Identity and session; the common set's own router."),
    ("themes",      "Design tokens; common set."),
    ("edge-panel",  "Shell panel; common set."),
    ("health",      "Liveness; no tenant data."),
    ("operator-profile", "Her own profile."),
    ("two-step",    "Already `area:mfa_enroll` — a token property, not an "
                    "administrable area."),
    ("spaces",      "Her own workspace config; common set."),
    ("notifications", "Her own notifications; common set."),
    ("feature-flags", "`/feature-flags/me` is common; the matrix is admin."),
    ("locations",   "`GET /locations` is common (boot chain); the rest is settings."),
    # ⚠️ `driver` AND `admin` ARE DECLARED, NOT `driver-announcements` — the
    # module name is not a path segment, and my own stale-entry test caught
    # that on its first run. `driver_announcements` mounts with prefix="" and
    # serves BOTH /driver/announcements and /admin/announcements.
    ("admin",       "The other half of the driver_announcements split "
                    "(/admin/announcements), plus assorted admin sub-trees. "
                    "Needs per-route tagging, not a segment tag."),
    ("driver",      "⚠️ ONE ROUTER, TWO AREAS, found by deriving "
                    "segments from where routes LAND rather than from the "
                    "prefix string: it mounts with prefix=\"\" and serves "
                    "/driver/announcements AND /admin/announcements. Split it "
                    "or tag per route; do not pick one."),
)


#: ─────────────────────────────────────────────────────────────────────────────
#: THE COMMON SET — reachable by every signed-in user regardless of area.
#:
#: ⚠️ **EXACT (METHOD, PATH) PAIRS, NOT PREFIXES, AND THAT CHANGE HAS A CAUSE.**
#: James's ruling of 2026-11-06, after a probe found `GET /locations/users`
#: reachable by a payroll-limited user on production. It returned another user's
#: location-access row — `access_level='admin'` — and it was admitted by the
#: `/locations` entry, whose own stated reason reads "the tenant's facility list
#: — organisational configuration, not business records". That reason describes
#: `GET /locations`. It says nothing about the per-user access table.
#:
#: ⚠️ **THE DEFECT WAS PREFIX BREADTH, NOT SLOPPY MATCHING.** `is_common` already
#: respected segment boundaries, and a test pinned that. The hole was that a
#: prefix admits every SIBLING route somebody adds under it later — including
#: routes that did not exist when the reason was written, and including writes.
#: Measured before the change: **7 prefixes admitted 39 method+path pairs**, of
#: which 17 were writes nobody had reviewed against any stated reason. The
#: listing below is 21 pairs, each one named by the reason beside it.
#:
#: Adding a route here is now a per-route decision that shows up in a diff. A
#: new sibling endpoint is denied by default, which is the direction the
#: asymmetry should point: forgetting to add something costs a 403 and a bug
#: report, where forgetting to remove something costs a disclosure nobody sees.
#:
#: Entries were DERIVED, not guessed: `TenantProviders.tsx` declares the boot
#: provider chain and each provider's fetch was traced to its path.
#:
#: Three tests hold this: `test_common_routes_are_real_routes` (no stale entry
#: granting nothing), `test_common_set_admits_only_what_it_lists` (no sibling
#: creeps back), and `test_locations_users_is_not_reachable` (the specific
#: disclosure, pinned by name).
#:
#: Matched EXACTLY against the route's method and PATH TEMPLATE, after the
#: /api/v1 (or /api) mount prefix is stripped.
COMMON_ROUTES: tuple[tuple[str, str, str], ...] = (
    # ── identity and session ──────────────────────────────────────────────
    (
        "GET", "/auth/me",
        "Supplies the user, permissions, modules and — since 2026-11-06 — the "
        "allowed AREAS the shell is built from. Without it nothing renders at "
        "all. This is also the single source of truth the frontend nav reads, "
        "so that the menu is filtered by the same rule the server enforces "
        "rather than by a second list that drifts.",
    ),
    (
        "POST", "/auth/refresh",
        "Called by the api-client interceptor. Without it she is signed out "
        "the moment her access token expires.",
    ),
    (
        "POST", "/auth/change-password",
        "She must be able to rotate her own password.",
    ),
    (
        "POST", "/auth/login",
        "⚠️ KEPT DELIBERATELY, AND THE PREVIOUS REASON DID NOT NAME IT. An "
        "AUTHENTICATION endpoint must never be refused by an AUTHORIZATION "
        "guard. The guard returns early when there is no authenticated tenant "
        "user, so in the ordinary flow login never reaches it — but a browser "
        "holding a stale-yet-decodable token that posts to login would get a "
        "403 on the one request that could fix its state, and a lockout whose "
        "cause is invisible from the sign-in page. Carries no tenant data.",
    ),
    # ⚠️ `POST /auth/register` IS DELIBERATELY ABSENT. It was admitted by the
    # old `/auth` prefix and named by nothing. It creates a user and is gated
    # by `get_current_company` alone — which is its own question, raised
    # separately and NOT fixed here, because a guard entry is the wrong place
    # to fix an endpoint's own authorization.

    # ── shell boot chain ──────────────────────────────────────────────────
    (
        "GET", "/feature-flags/me",
        "`FeatureFlagProvider` is the second provider in the boot chain and "
        "fetches this on mount. Scoped to the caller. Deliberately NOT the "
        "whole `/feature-flags` router — the matrix and audit-log endpoints "
        "are admin surfaces and stay denied.",
    ),
    (
        "GET", "/themes/resolve",
        "`PresetThemeProvider` resolves the tenant's design tokens. Read-only "
        "presentation values; an unstyled app is not a usable one.",
    ),
    (
        "GET", "/edge-panel/preferences",
        "`EdgePanelProvider` mounts at the app root, outside the route tree, "
        "so a refusal here throws above every page rather than degrading one. "
        "Per-user.",
    ),
    (
        "PATCH", "/edge-panel/preferences",
        "Her own panel preferences. Per-user, and named by the original "
        "reason's phrase `preferences is per-user`.",
    ),
    (
        "GET", "/edge-panel/resolve",
        "Shell configuration for the edge panel. Read-only.",
    ),
    (
        "GET", "/capture/preferences",
        "⚠️ **A MIS-TAG FOUND BY A TEST THAT IS NOT ABOUT AREAS.** `pick_modifier` "
        "is which modifier key picks an item — a per-user UI preference read "
        "from `current_user.preferences`. The router-level `area:orders` tag "
        "swept it up with order capture, and `test_pick_modifier` went red for a "
        "reason it knows nothing about. Its own docstring names the precedent: "
        "\"edge_panel's preferences pair, which is the precedent this follows\" "
        "— and that pair is two entries above. So it belongs here, beside the "
        "thing it was modelled on.",
    ),
    (
        "PATCH", "/capture/preferences",
        "The write half of the pair above. Per-user.",
    ),
    (
        "GET", "/edge-panel/tenant-config",
        "Shell configuration for the edge panel. Read-only.",
    ),
    (
        "GET", "/locations",
        "`LocationProvider` is in the boot chain above the route tree. Returns "
        "the tenant's facility list — organisational configuration, not "
        "business records.\n"
        "⚠️ THIS IS THE ONLY `/locations` ROUTE ADMITTED. The nine siblings the "
        "old prefix also granted are denied: `GET /locations/users` "
        "(company-wide user access-level rows — the disclosure that prompted "
        "this change), `GET /locations/overview`, `GET /locations/{id}`, "
        "`GET /locations/{id}/summary`, and the five writes. The four writes "
        "remain gated by `require_admin` at the endpoint, unchanged; they now "
        "also no longer reach it, which is defence in depth rather than a "
        "replacement for it.",
    ),
    # ── the notification bell, mounted for every user by app-layout.tsx ───
    (
        "GET", "/notifications",
        "The notification bell in the header. Her own notifications.\n"
        "⚠️ This entry read `/vault/notifications` in the first draft, taken "
        "from that string in `notification-dropdown.tsx` — which is a "
        "client-side `navigate()` target, NOT an API path. It matched no route, "
        "so it granted nothing while reading as protection.",
    ),
    (
        "GET", "/notifications/unread-count",
        "The unread badge on the bell. Her own count.",
    ),
    (
        "PATCH", "/notifications/{notification_id}/read",
        "Marking her own notification read.",
    ),
    (
        "PATCH", "/notifications/read-all",
        "Marking all of her own notifications read.",
    ),
    # ── spaces: the sidebar's DotNav and the affinity signal ──────────────
    #
    # ⚠️ READ AND ACTIVATE ONLY. Every `spaces` row is per-user and scoped by
    # `user_id`, so the old prefix disclosed nothing — but it admitted nine
    # writes (create, rename, delete, reorder, reapply-defaults, and four pin
    # mutations) that the stated reason never named. An area-limited user's
    # pin and space-editing controls are hidden by the same area rule as the
    # nav itself, so those endpoints are not something her shell calls.
    (
        "GET", "/spaces",
        "`SpaceProvider` plus the DotNav at the bottom of the sidebar. "
        "Per-user rows, scoped by `user_id`.",
    ),
    (
        "GET", "/spaces/{space_id}",
        "One of her own spaces, read by the DotNav.",
    ),
    (
        "POST", "/spaces/{space_id}/activate",
        "Switching between her own spaces — the DotNav's only write.",
    ),
    (
        "GET", "/spaces/affinity/count",
        "The 'N tracked signals' counter. Her own count.",
    ),
    (
        "POST", "/spaces/affinity/visit",
        "The affinity write, named explicitly by the original reason. "
        "Per-user, fire-and-forget.",
    ),
    (
        "DELETE", "/spaces/affinity",
        "'Clear my learning history' — a privacy action over her own rows.",
    ),
)

#: ⚠️ Kept as an alias so a stale import fails LOUDLY at the name rather than
#: silently iterating two-tuples as three-tuples. Remove once nothing imports
#: it.
COMMON_PREFIXES = None  # noqa: N816 — intentionally un-iterable; see above


EXCLUDED_FROM_COMMON: tuple[str, ...] = ("/focus", "/companies/settings")


def area_for_tags(tags) -> str | None:
    """The area a route declares, or None if it declares none."""
    for tag in tags or ():
        if isinstance(tag, str) and tag.startswith(AREA_TAG_PREFIX):
            return tag[len(AREA_TAG_PREFIX):]
    return None


def strip_mount_prefix(path: str) -> str:
    """Normalise `/api/v1/foo` and `/api/foo` to `/foo`.

    The v1 router is mounted twice — at `/api/v1` and at the deprecated `/api`
    alias — so the guard must see the same path either way or the alias becomes
    a way around it.
    """
    for mount in ("/api/v1", "/api"):
        if path.startswith(mount + "/"):
            return path[len(mount):]
        if path == mount:
            return "/"
    return path


def is_common(method: str, path: str) -> bool:
    """Is this exact (method, route template) in the common set?

    ⚠️ **EXACT, NOT PREFIX.** The signature changed on 2026-11-06 and the method
    parameter is not optional, deliberately: a caller that still passes one
    argument fails with a TypeError rather than silently treating a path as a
    method and admitting nothing — or worse, admitting everything. The old
    prefix form admitted 39 method+path pairs across 7 entries; this admits the
    21 that are named.
    """
    rel = strip_mount_prefix(path)
    m = (method or "").upper()
    return any(m == cm and rel == cp for cm, cp, _reason in COMMON_ROUTES)
