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
KNOWN_AREAS: frozenset[str] = frozenset({
    "payroll",
    #: Two-step enrolment (Payroll 2). ⚠️ NOT AN AREA A ROLE IS EVER LIMITED TO
    #: BY AN ADMIN — it is the area a user is TEMPORARILY confined to by the
    #: guard when they require two-step and their token has not passed it. The
    #: distinction matters: `limited_to_areas` is a standing property of a role,
    #: this is a property of a token, and both are enforced by the one guard
    #: rather than by two.
    "mfa_enroll",
})


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
