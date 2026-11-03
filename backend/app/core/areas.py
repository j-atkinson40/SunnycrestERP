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
})


#: ─────────────────────────────────────────────────────────────────────────────
#: THE COMMON SET — reachable by every signed-in user regardless of area.
#:
#: ⚠️ EVERY ENTRY IS HERE BECAUSE THE SHELL CANNOT RENDER WITHOUT IT, and the
#: list was DERIVED rather than guessed: `TenantProviders.tsx` declares the boot
#: provider chain, and each provider's fetch was traced to its path. Nothing is
#: on this list because it seemed harmless.
#:
#: The test `test_common_prefixes_are_real_routes` fails if an entry matches no
#: route, so a stale entry cannot sit here granting nothing.
#:
#: Matched as a prefix of the route's PATH TEMPLATE, after the /api/v1 (or /api)
#: mount prefix is stripped.
COMMON_PREFIXES: tuple[tuple[str, str], ...] = (
    (
        "/auth",
        "Identity and session. `/auth/me` supplies the user, permissions and "
        "modules the shell is built from — without it nothing renders at all — "
        "and `/auth/refresh` is called by the api-client interceptor, without "
        "which she is signed out when the access token expires. Also carries "
        "`/auth/change-password`, which she must be able to reach to rotate her "
        "own password.",
    ),
    (
        "/feature-flags/me",
        "`FeatureFlagProvider` is the second provider in the boot chain and "
        "fetches this on mount. Scoped to the caller. Deliberately NOT the "
        "whole `/feature-flags` router — the matrix and audit-log endpoints are "
        "admin surfaces and stay denied.",
    ),
    (
        "/spaces",
        "`SpaceProvider` plus the DotNav at the bottom of the sidebar. Every row "
        "is per-user and already scoped by `user_id`, including the affinity "
        "writes, so this grants her only her own workspace configuration.",
    ),
    (
        "/themes/resolve",
        "`PresetThemeProvider` resolves the tenant's design tokens. Read-only "
        "presentation values; an unstyled app is not a usable one.",
    ),
    (
        "/edge-panel",
        "`EdgePanelProvider` and `EdgePanelHost` mount at the app root, outside "
        "the route tree, so a refusal here throws above every page rather than "
        "degrading one. `preferences` is per-user; `resolve` and `tenant-config` "
        "are shell configuration.",
    ),
    (
        "/locations",
        "`LocationProvider` is in the boot chain above the route tree. Returns "
        "the tenant's facility list — organisational configuration, not business "
        "records.",
    ),
    (
        "/notifications",
        "The notification bell in the header, mounted for every user by "
        "`app-layout.tsx`: `/notifications` and `/notifications/unread-count`, "
        "plus the read/read-all marks. Her own notifications.\n"
        "⚠️ This entry read `/vault/notifications` in the first draft, taken from "
        "that string in `notification-dropdown.tsx` — which is a client-side "
        "`navigate()` target, NOT an API path. It matched no route, so it granted "
        "nothing while reading as protection. Caught by "
        "`test_common_prefixes_are_real_routes`, which exists for exactly this.",
    ),
)

#: ⚠️ DELIBERATELY NOT IN THE COMMON SET, recorded so the omission reads as a
#: decision rather than an oversight:
#:
#:   /focus, /focus/recent — `FocusProvider` is in the boot chain, but
#:       `/focus/recent` returns recently-opened ENTITIES, which is exactly the
#:       cross-area leak this guard exists to prevent. A 403 there costs a
#:       recents list; it does not block sign-in. Revisit when Focus grows a
#:       per-area scope.
#:
#:   /companies/settings — already gated on `company.view`
#:       (`app/api/routes/companies.py:35`) and called only by two non-shell
#:       pages, so it was never a boot dependency.
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


def is_common(path: str) -> bool:
    """Is this route in the common set every signed-in user may reach?"""
    rel = strip_mount_prefix(path)
    # ⚠️ EXACT OR SEGMENT-BOUNDED ONLY. A bare `rel.startswith(p)` would let
    # `/authorization-anything` through on the `/auth` entry — a prefix match
    # that ignores segment boundaries is how an allowlist grows holes nobody
    # typed. Pinned by `test_common_match_respects_segment_boundaries`.
    return any(rel == p or rel.startswith(p + "/") for p, _reason in COMMON_PREFIXES)
