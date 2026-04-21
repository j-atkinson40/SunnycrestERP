"""Command Bar retrieval orchestrator — Phase 1.

OWNS the public result-shape contract returned by
`/api/v1/command-bar/query`. Frontend callers + any future SDK
clients depend on this shape; bumping it is a coordinated change.

Orchestrates the platform layer:

    1. Classify intent         → intent.classify()
    2. Query the registry      → registry.match_actions() + list_actions()
    3. Resolve vault entities  → resolver.resolve()
    4. Merge + rank            → this module
    5. Permission filter       → this module (via user context)
    6. Shape the response      → ResultItem / QueryResponse

Extending this module for later phases:

  - Phase 2: saved_view results come in as registry entries with
    `action_type="saved_view"`. No orchestrator change required.
  - Phase 3: space-scoped ranking adds a weight multiplier here.
  - Phase 5: workflow registry expands; `_rank_registry_hits`
    handles any `action_type`, so no code change in Phase 5.
  - Phase 6: briefings plug in as a new result type; adds a fifth
    result source and bumps the `ResultItem.type` union.

Do NOT replace this module when later phases add features. Extend.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.command_bar import registry as registry_mod
from app.services.command_bar import resolver as resolver_mod
from app.services.command_bar.intent import (
    Intent,
    classify,
    is_create_entity_query,
    should_search_entities,
)

logger = logging.getLogger(__name__)


# ── Public types — PROTECTED API ─────────────────────────────────────
# Frontend + SDK clients depend on this shape. Changes here are
# coordinated schema changes, not internal refactors.


ResultType = Literal[
    "navigate",
    "create",
    "search_result",
    "action",
    "saved_view",  # Phase 2 — frontend adapter maps to TYPE_RANK='VIEW'
]


@dataclass
class ResultItem:
    """One result tile rendered in the command bar modal.

    Every result has a stable `id`, a `type`, and enough info for the
    frontend to render + activate the tile without a second round-trip.

    Fields are Optional where a given type doesn't use them; frontend
    code branches on `type` and reads the appropriate subset.
    """

    id: str                     # stable client-side key
    type: ResultType
    primary_label: str
    secondary_context: str | None
    icon: str

    # Populated for type="navigate" and search results that navigate.
    url: str | None = None
    # Populated for type="create".
    entity_type: str | None = None
    action_id: str | None = None
    # For search results — what entity type this hit is.
    result_entity_type: str | None = None

    score: float = 0.0


@dataclass
class QueryResponse:
    """The response body for POST /api/v1/command-bar/query."""

    intent: Intent
    results: list[ResultItem] = field(default_factory=list)
    total: int = 0


@dataclass
class QueryContext:
    """Optional contextual hints from the client. Phase 1 uses these
    sparingly; Phase 3 (Spaces) adds `active_space_id` — results
    pinned to the active space get a ranking boost, and a space-
    switch navigate result is synthesized when the query matches
    another space's name."""

    current_page: str | None = None
    current_entity_type: str | None = None
    current_entity_id: str | None = None
    # Phase 3 — current active space id (pn_...). Used to (a) boost
    # pinned targets in the ranking pass, (b) suppress the current
    # space from the space-switch synthesize step.
    active_space_id: str | None = None


# ── Ranking weights ──────────────────────────────────────────────────
# Applied to each source's score before the final merge. Intent-aware
# so that "new sales order" surfaces the create action at the top,
# while "SMITH" surfaces the resolver hit first.

_WEIGHT_CREATE_ON_CREATE_INTENT: float = 1.5    # create action when user typed "new X"
_WEIGHT_NAVIGATE_ON_NAV_INTENT: float = 1.3     # navigate action when query is a page name
_WEIGHT_REGISTRY_DEFAULT: float = 1.0           # registry hit on other intents
_WEIGHT_RESOLVER_DEFAULT: float = 1.0           # entity result baseline

# Phase 3 — multiplier applied to any result whose target matches a
# pin in the user's active space. Additive on top of the base score
# so an already-high-relevance pinned hit floats higher. 1.25 is
# subtle — enough to reorder close scores, not enough to let a
# pinned but poor-match result jump a genuinely better hit.
_WEIGHT_ACTIVE_SPACE_PIN_BOOST: float = 1.25

# Phase 8e.1 — starter-template target boost. Smaller than the
# pin boost (1.25): "this is the kind of thing this space is about,
# even if you unpinned it" is a weaker signal than "you pinned it."
# Compound max with pin + affinity (1.25 * 1.10 * 1.40 = 1.925)
# stays below the generic create-intent ceiling.
_WEIGHT_STARTER_TEMPLATE_BOOST: float = 1.10

# Phase 3 — score for synthesized space-switch results. Sits
# between a create action hit (1.5) and a registry default (1.0) so
# typing "arrangement" in a funeral director tenant surfaces the
# space switch near the top but doesn't shadow a literal
# "Arrangement" entity hit if one exists.
_WEIGHT_SPACE_SWITCH_EXACT: float = 1.4
_WEIGHT_SPACE_SWITCH_PREFIX: float = 1.1


# ── Permission filtering ─────────────────────────────────────────────


def _user_can_see(user: User, entry: registry_mod.ActionRegistryEntry) -> bool:
    """Check the three gates on a registry entry against a user.

    Mirrors `vault.hub_registry` filtering:
      - super_admin: bypass all gates
      - required_permission="admin": pass if role.slug=="admin" (via
        user_has_permission short-circuit)
      - required_permission=<other>: user must have that permission
      - required_module: tenant must have the module enabled
      - required_extension: tenant extension must be active
    """
    if getattr(user, "is_super_admin", False):
        return True

    # Permission gate
    if entry.required_permission:
        from app.services.permission_service import user_has_permission

        # We need a DB session to check permissions. Callers pass one
        # in via `query()`; propagate it here when available. For this
        # helper we accept either a pre-fetched perm set OR defer to
        # the service. The simple path: the caller filters before
        # calling `_user_can_see` OR we accept a `perms` arg. For
        # Phase 1 we check permission inline in `query()` where the
        # db session is in scope; this function is a placeholder for
        # the pure-flag cases (module, extension).
        pass

    # Module / extension gates are checked in `query()` where we have
    # access to the DB session + tenant context.
    return True


# ── Main entry point ─────────────────────────────────────────────────


def query(
    db: Session,
    *,
    query_text: str,
    user: User,
    max_results: int = 10,
    context: QueryContext | None = None,
) -> QueryResponse:
    """Run a full command-bar query.

    This function is the contract surface for the /command-bar/query
    endpoint. Frontend callers depend on the shape of the returned
    `QueryResponse`.

    Args:
        db:          Active DB session.
        query_text:  User's raw input.
        user:        Authenticated user (for tenant + permission).
        max_results: Cap on total results returned. Default 10.
        context:     Optional contextual hints.

    Returns a `QueryResponse` with `intent` + `results` + `total`.

    Behavior:
      - empty query → empty response with intent="empty"
      - navigate/action intents → registry hits first, resolver after
      - create intent → create action prioritized, optional create
                        variants also included
      - search intent → resolver hits first, registry hits second
    """
    qc = context or QueryContext()
    q = (query_text or "").strip()

    intent: Intent = classify(q)
    if intent == "empty":
        return QueryResponse(intent=intent, results=[], total=0)

    company_id = user.company_id

    # ── Resolve permissions once up front ────────────────────────────
    # For Phase 1 we check (a) module enablement, (b) extension,
    # (c) permission strings against user_has_permission. Super-
    # admins bypass.
    from app.services.permission_service import user_has_permission
    from app.services.module_service import is_module_enabled

    is_super = bool(getattr(user, "is_super_admin", False))

    def _registry_entry_visible(entry: registry_mod.ActionRegistryEntry) -> bool:
        if is_super:
            return True
        if entry.required_permission and not user_has_permission(
            user, db, entry.required_permission
        ):
            return False
        if entry.required_module and not is_module_enabled(
            db, company_id, entry.required_module
        ):
            return False
        if entry.required_extension:
            # Extension gate — check TenantExtension presence.
            from app.models.tenant_extension import TenantExtension

            exists = (
                db.query(TenantExtension.id)
                .filter(
                    TenantExtension.tenant_id == company_id,
                    TenantExtension.extension_key == entry.required_extension,
                )
                .first()
            )
            if exists is None:
                return False
        # Dynamic permission check callable
        if entry.permission_check is not None:
            try:
                if not entry.permission_check(user):
                    return False
            except Exception:
                logger.warning(
                    "permission_check raised for action %s — treating as deny",
                    entry.action_id,
                )
                return False
        return True

    # ── Gather results from sources ──────────────────────────────────
    results: list[tuple[ResultItem, float]] = []

    # 1. Registry matches (navigate + create actions)
    registry_hits = registry_mod.match_actions(q, max_results=max_results * 2)
    create_entity = is_create_entity_query(q)

    for entry, base_score in registry_hits:
        if not _registry_entry_visible(entry):
            continue
        weight = _WEIGHT_REGISTRY_DEFAULT
        if intent == "create" and entry.action_type == "create":
            weight = _WEIGHT_CREATE_ON_CREATE_INTENT
            # If the user typed "new X" and entry exactly matches X,
            # give it an additional nudge.
            if create_entity and entry.entity_type == create_entity:
                weight *= 1.15
        elif intent == "navigate" and entry.action_type == "navigate":
            weight = _WEIGHT_NAVIGATE_ON_NAV_INTENT

        result = _registry_entry_to_result(entry, score=base_score * weight)
        results.append((result, result.score))

    # 2. Entity resolver hits
    if should_search_entities(intent):
        try:
            hits = resolver_mod.resolve(
                db,
                query_text=q,
                company_id=company_id,
                limit=max_results * 2,
            )
        except Exception:
            logger.exception("resolver failed (query=%r)", q[:80])
            hits = []

        for h in hits:
            item = ResultItem(
                id=f"entity:{h.entity_type}:{h.entity_id}",
                type="search_result",
                primary_label=h.primary_label or "(untitled)",
                secondary_context=h.secondary_context,
                icon=_icon_for_entity(h.entity_type),
                url=h.url,
                result_entity_type=h.entity_type,
                score=h.score * _WEIGHT_RESOLVER_DEFAULT,
            )
            results.append((item, item.score))

    # 3. Saved-views resolver hits (Phase 2).
    # PARALLEL to the entity resolver — do NOT fold into its UNION ALL.
    # Saved views live in `vault_items` with title fuzzy-match; the
    # entity resolver's query plan stays unchanged, protecting its
    # p99 budget. Merge via the existing dedupe-by-id logic below.
    if should_search_entities(intent):
        try:
            from app.services.command_bar import saved_views_resolver as sv_res

            view_hits = sv_res.resolve(
                db,
                query_text=q,
                user=user,
                limit=max_results,
            )
        except Exception:
            logger.exception("saved_views_resolver failed (query=%r)", q[:80])
            view_hits = []

        for vh in view_hits:
            item = ResultItem(
                id=f"saved_view:{vh.view_id}",
                type="saved_view",
                primary_label=vh.title,
                secondary_context=vh.description or f"Saved view — {vh.entity_type}",
                icon="LayoutDashboard",
                url=f"/saved-views/{vh.view_id}",
                action_id=f"saved_view:{vh.view_id}",
                # Weight equal to resolver default; VIEW rank is in the
                # frontend TYPE_RANK (slot 5), between RECORD (3) and
                # NAV (6). Adapter maps backend type="saved_view" →
                # frontend CommandAction.type="VIEW" via a 1-line
                # branch in commandBarQueryAdapter.ts.
                score=vh.score * _WEIGHT_RESOLVER_DEFAULT,
            )
            results.append((item, item.score))

    # 4. Synthesized space-switch results (Phase 3).
    # NOT registered in the module-level action registry — that
    # singleton is shared across tenants and per-user state would
    # leak. Synthesize at query time from the user's preferences.
    # Parallel source pattern, same as saved-views.
    for item, score in _synthesize_space_switch_results(
        user=user,
        query=q,
        active_space_id=qc.active_space_id,
    ):
        results.append((item, score))

    # 5. Active-space pin boost (Phase 3).
    # Additive multiplier applied to any result whose target appears
    # in the active space's pin set. Same scoring pass as everything
    # else; identity of the pinned target is resolved via the user's
    # preferences (already loaded in step 4) and matched against
    # item.url + item.id.
    # NB: `ResultItem` is a mutable dataclass; update `item.score`
    # in place so the serialized response reflects the boost. The
    # (item, score) tuple score stays in sync for the merge+sort
    # step below.
    pinned_targets = _active_space_pin_targets(
        user=user, active_space_id=qc.active_space_id,
    )
    if pinned_targets:
        boosted: list[tuple[ResultItem, float]] = []
        for item, score in results:
            if _result_matches_pin_target(item, pinned_targets):
                new_score = score * _WEIGHT_ACTIVE_SPACE_PIN_BOOST
                item.score = new_score
                boosted.append((item, new_score))
            else:
                boosted.append((item, score))
        results = boosted

    # 6. Starter-template target boost (Phase 8e.1).
    # Applied when the active space was seeded from a role template
    # AND the result's target appears in that template's pin set —
    # even if the user has since unpinned it. "This is the kind of
    # thing this space is for" is a weaker signal than "you pinned
    # this," so the weight (1.10) is smaller than the pin boost
    # (1.25). Max-stacking with pin boost: a result that is BOTH
    # pinned AND in the starter template gets pin-boost only —
    # these are not additive.
    starter_targets = _active_space_starter_template_targets(
        user=user, active_space_id=qc.active_space_id,
    )
    if starter_targets:
        boosted = []
        for item, score in results:
            # Skip if already pinned (pin boost already applied above).
            if pinned_targets and _result_matches_pin_target(
                item, pinned_targets
            ):
                boosted.append((item, score))
                continue
            if _result_matches_pin_target(item, starter_targets):
                new_score = score * _WEIGHT_STARTER_TEMPLATE_BOOST
                item.score = new_score
                boosted.append((item, new_score))
            else:
                boosted.append((item, score))
        results = boosted

    # 7. Topical affinity boost (Phase 8e.1).
    # Single prefetch query → in-memory dict → O(1) lookup per
    # result. Composes multiplicatively with starter-template and
    # pin boost: "I work on this AND I pinned it AND it's in the
    # template" stacks up to ~1.925x for the ideal hit.
    #
    # Identifying which target a result refers to:
    #   - navigate actions: url matches nav_item affinity
    #   - create actions: not affinity-boosted (no target identity)
    #   - search_result entity hits: result_entity_type + entity_id
    #     embedded in item.id ("entity:<type>:<id>")
    #   - saved_view: item.id ("saved_view:<view_id>")
    #
    # If prefetch_for_user_space fails (migration gap), returns
    # empty dict — no boost, no crash.
    if qc.active_space_id:
        from app.services.spaces.affinity import (
            boost_for_target,
            prefetch_for_user_space,
        )

        affinity = prefetch_for_user_space(
            db, user=user, space_id=qc.active_space_id
        )
        if affinity:
            boosted = []
            for item, score in results:
                factor = _affinity_factor_for_result(
                    item, affinity, boost_for_target
                )
                if factor > 1.0:
                    new_score = score * factor
                    item.score = new_score
                    boosted.append((item, new_score))
                else:
                    boosted.append((item, score))
            results = boosted

    # ── Merge + rank ──────────────────────────────────────────────────
    # Deduplicate by `id` — a registry hit + resolver hit for the same
    # record won't collide because one is "action:nav.foo" and the
    # other is "entity:sales_order:abc", but belt-and-suspenders.
    seen_ids: set[str] = set()
    deduped: list[tuple[ResultItem, float]] = []
    for item, score in results:
        if item.id in seen_ids:
            continue
        seen_ids.add(item.id)
        deduped.append((item, score))

    # Sort by score desc
    deduped.sort(key=lambda pair: (-pair[1], pair[0].primary_label.lower()))
    final = [pair[0] for pair in deduped[:max_results]]

    return QueryResponse(
        intent=intent,
        results=final,
        total=len(final),
    )


# ── Helpers ──────────────────────────────────────────────────────────


def _registry_entry_to_result(
    entry: registry_mod.ActionRegistryEntry,
    *,
    score: float,
) -> ResultItem:
    """Map a registry entry to a `ResultItem`. The client branches on
    `type` to render + activate — see ResultItem docstring."""

    if entry.action_type == "navigate":
        return ResultItem(
            id=f"action:{entry.action_id}",
            type="navigate",
            primary_label=entry.label,
            secondary_context=None,
            icon=entry.icon,
            url=entry.target_url,
            action_id=entry.action_id,
            score=score,
        )
    if entry.action_type == "create":
        return ResultItem(
            id=f"action:{entry.action_id}",
            type="create",
            primary_label=entry.label,
            secondary_context=None,
            icon=entry.icon,
            url=entry.target_url,
            entity_type=entry.entity_type,
            action_id=entry.action_id,
            score=score,
        )
    # workflow / saved_view — map to "action" generic type for now
    return ResultItem(
        id=f"action:{entry.action_id}",
        type="action",
        primary_label=entry.label,
        secondary_context=None,
        icon=entry.icon,
        url=entry.target_url,
        action_id=entry.action_id,
        score=score,
    )


_ENTITY_ICON_MAP: dict[str, str] = {
    "fh_case": "Folder",
    "sales_order": "ShoppingCart",
    "invoice": "Receipt",
    "contact": "User",
    "product": "Package",
    "document": "FileText",
}


def _icon_for_entity(entity_type: str) -> str:
    return _ENTITY_ICON_MAP.get(entity_type, "Search")


# ── Phase 3 — Spaces integration ─────────────────────────────────────
# The two helpers below read `user.preferences` directly (synchronous,
# no DB round-trip) — spaces live in JSONB on the User row and are
# already hydrated when the request arrives. No new query per call.


def _synthesize_space_switch_results(
    *,
    user: User,
    query: str,
    active_space_id: str | None,
) -> list[tuple[ResultItem, float]]:
    """Scan the user's spaces for a name match. Emits
    `type="navigate"` results with `url="/?__switch_space=<id>"` so
    the frontend can intercept the route and activate the space
    without a real navigation. The URL is deliberately query-param
    shaped — legacy clients that fall through to a regular navigate
    still land on `/` (the dashboard) rather than 404.

    Matching rules (intentionally forgiving so short queries work):
      - exact name match (case-insensitive)  → high weight
      - name starts with query (>=2 chars)   → moderate weight
      - no match                             → nothing emitted
    The user's current active space is excluded (no self-switch).
    """
    prefs = user.preferences or {}
    raw_spaces = prefs.get("spaces") or []
    if not raw_spaces:
        return []

    q = (query or "").strip().lower()
    if len(q) == 0:
        return []

    out: list[tuple[ResultItem, float]] = []
    for space in raw_spaces:
        space_id = space.get("space_id")
        if not space_id or space_id == active_space_id:
            continue
        name = (space.get("name") or "").strip()
        if not name:
            continue
        name_lower = name.lower()

        if name_lower == q:
            weight = _WEIGHT_SPACE_SWITCH_EXACT
        elif len(q) >= 2 and name_lower.startswith(q):
            weight = _WEIGHT_SPACE_SWITCH_PREFIX
        else:
            continue

        icon = space.get("icon") or "Layers"
        item = ResultItem(
            id=f"space_switch:{space_id}",
            type="navigate",
            primary_label=f"Switch to {name}",
            secondary_context="Space",
            icon=icon,
            url=f"/?__switch_space={space_id}",
            action_id=f"space_switch:{space_id}",
            # Expose the space id to the frontend for interception
            # without a round-trip. Reusing `result_entity_type` as a
            # lightweight annotation channel.
            result_entity_type=None,
            score=weight,
        )
        out.append((item, weight))
    return out


def _active_space_pin_targets(
    *, user: User, active_space_id: str | None,
) -> set[str]:
    """Return the set of pin target identifiers in the user's active
    space. Used to decide which results get the pin boost.

    Identifiers are the raw strings the result URLs/ids are built
    from:
      - nav_item pin: the href (e.g. "/financials")
      - saved_view pin: the saved-view id (e.g. "abc-123-def"), so
        the matcher can hit both `/saved-views/abc-123-def` URLs
        and `saved_view:abc-123-def` ids.
    """
    if not active_space_id:
        return set()
    prefs = user.preferences or {}
    for space in prefs.get("spaces") or []:
        if space.get("space_id") != active_space_id:
            continue
        out: set[str] = set()
        for pin in space.get("pins") or []:
            tid = pin.get("target_id")
            if tid:
                out.add(tid)
        return out
    return set()


def _result_matches_pin_target(
    item: ResultItem, pin_targets: set[str]
) -> bool:
    """Soft matcher. Checks item.url (for nav + saved view routes)
    and item.id (for `saved_view:<id>` ids). Kept forgiving —
    pinning a nav item boosts both the registry-hit result AND any
    adjacent resolver hit on the same URL."""
    if item.url and item.url in pin_targets:
        return True
    # saved_view:<id> id shape — extract the trailing segment.
    if item.id.startswith("saved_view:"):
        view_id = item.id.split(":", 1)[1]
        if view_id in pin_targets:
            return True
    # URL like /saved-views/<id>
    if item.url and item.url.startswith("/saved-views/"):
        view_id = item.url.rsplit("/", 1)[-1]
        if view_id in pin_targets:
            return True
    return False


# ── Phase 8e.1 — starter-template + affinity helpers ─────────────────


def _active_space_starter_template_targets(
    *, user: User, active_space_id: str | None,
) -> set[str]:
    """Return the set of target_ids from the role-template that
    seeded the user's active space.

    Resolution:
      1. Find the active space in user.preferences.spaces.
      2. Look up the tenant's vertical (company.vertical).
      3. Walk `spaces/registry.py::SEED_TEMPLATES[(vertical, role)]`
         for a template whose name matches the active space's name.
      4. Return the pin.target values.

    Returns an empty set when:
      - No active space is set.
      - The space is user-created (not matching any template name).
      - The tenant vertical can't be resolved.

    This function is intentionally defensive (silent-empty on any
    mismatch) because it sits on the command-bar hot path.
    """
    if not active_space_id:
        return set()

    prefs = user.preferences or {}
    raw_spaces = prefs.get("spaces") or []
    active = next(
        (s for s in raw_spaces if s.get("space_id") == active_space_id),
        None,
    )
    if active is None:
        return set()
    active_name = (active.get("name") or "").strip().lower()
    if not active_name:
        return set()

    from app.services.spaces import registry as space_reg

    # Identify the user's role_slug via preferences.spaces_seeded_for_roles
    # — the most reliable signal of which (vertical, role) seeded this
    # user. Falls back to any role whose template matches the space
    # name; either approach avoids a DB round-trip.
    seeded_roles = prefs.get("spaces_seeded_for_roles") or []

    # Scan templates across all seeded roles for a name match.
    for (vertical, role_slug), templates in space_reg.SEED_TEMPLATES.items():
        if seeded_roles and role_slug not in seeded_roles:
            continue
        for tpl in templates:
            if tpl.name.lower() == active_name:
                return {p.target for p in tpl.pins}
    return set()


def _affinity_factor_for_result(
    item: ResultItem,
    affinity: dict[tuple[str, str], object],
    boost_for_target,
) -> float:
    """Map a ResultItem to its affinity boost factor via the prefetch
    dict. Inspects item.type + item.url + item.id + result_entity_type
    to identify the (target_type, target_id) key.

    Returns 1.0 (no boost) when no matching affinity row exists.
    """
    # Entity-record hits — item.id has shape "entity:<type>:<id>";
    # we use the entity_id portion as target_id.
    if item.type == "search_result" and item.id.startswith("entity:"):
        parts = item.id.split(":", 2)
        if len(parts) == 3:
            return float(boost_for_target(affinity, "entity_record", parts[2]))
        return 1.0

    # Saved-view hits — item.id has shape "saved_view:<id>".
    if item.type == "saved_view" and item.id.startswith("saved_view:"):
        view_id = item.id.split(":", 1)[1]
        return float(boost_for_target(affinity, "saved_view", view_id))

    # Navigate actions with a URL — check for nav_item affinity.
    # Match exactly on URL (the affinity write path records the same
    # href as the nav pin's target_id).
    if item.type == "navigate" and item.url:
        # Triage queue nav URLs: /triage/<queue_id>
        if item.url.startswith("/triage/"):
            queue_id = item.url.rsplit("/", 1)[-1]
            return float(boost_for_target(affinity, "triage_queue", queue_id))
        return float(boost_for_target(affinity, "nav_item", item.url))

    return 1.0
