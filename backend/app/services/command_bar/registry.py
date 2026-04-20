"""Command Bar action registry — Phase 1.

Singleton registry of all invokable actions. Features register at
app startup; the registry is queryable by intent type, entity type,
or free-text match.

This module OWNS the `ActionRegistryEntry` type. Phase 2+ (saved
views), Phase 5 (workflows), and Phase 6 (briefings) extend the
registry with new action types — they do NOT redefine the schema.

Lifecycle mirrors `app.services.vault.hub_registry`: a module-level
dict populated by a lazy `_ensure_seeded()` on first `get_registry()`
call, plus a `reset_registry()` escape hatch for tests.

Registration happens two ways today:

  1. At-startup seed in `_seed_default_actions()` — navigate actions
     for every top-level page, create actions for every creatable
     entity type. Think of this as "platform-owned actions".

  2. External call to `register_action()` — for extensions or later
     phases that add actions dynamically (saved views loaded from DB,
     per-tenant workflows, etc.).

Permission, module, and extension gates mirror the navigation-service
contract. The resolver + retrieval layers apply these gates at query
time; the registry stores them as opaque strings / callables.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

logger = logging.getLogger(__name__)


# ── Types ─────────────────────────────────────────────────────────────


ActionType = Literal[
    # Take the user to a page or record. `target_url` required.
    "navigate",
    # Create a new entity. `entity_type` required (maps to the
    # Compose-style handler).
    "create",
    # Invoke a Workflow Engine workflow. `workflow_id` required.
    # (Phase 5 extends this.)
    "workflow",
    # Render a saved view. `saved_view_id` required. (Phase 2.)
    "saved_view",
    # Never invokable — only surfaces as a result tile. (Reserved.)
    "search_only",
]


@dataclass
class ActionRegistryEntry:
    """Schema for one registered action.

    OWNED BY THIS MODULE. Callers in later phases must not redefine
    this — they extend it with `metadata` for action-type-specific
    data that the registry itself doesn't care about.
    """

    action_id: str
    action_type: ActionType
    label: str
    icon: str
    aliases: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    # Gates — mirror navigation-service.ts semantics.
    # `required_permission` — e.g. "customers.view", or the magic
    # string "admin" which short-circuits via role.slug==admin.
    required_permission: str | None = None
    required_module: str | None = None
    required_extension: str | None = None

    # Action-type-specific wiring.
    target_url: str | None = None       # for "navigate"
    entity_type: str | None = None      # for "create"
    workflow_id: str | None = None      # for "workflow"
    saved_view_id: str | None = None    # for "saved_view" (Phase 2)

    # Optional callable invoked server-side when the action is
    # selected. Most actions are client-side routed (target_url), so
    # this is typically None. Left as a hook for future phases.
    handler: Callable | None = None

    # Optional late-bound permission check. Takes a user context and
    # returns bool. Runs AFTER the three gate strings — a belt-and-
    # suspenders check for actions with dynamic visibility (e.g.
    # "only show if this tenant has >0 quotes"). Typically None.
    permission_check: Callable[[Any], bool] | None = None

    # Catch-all for action-type-specific data that doesn't justify a
    # top-level field. Examples: "which Compose variant to open",
    # briefing-template ID, saved-view query params, etc.
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Internal state ────────────────────────────────────────────────────


_registry: dict[str, ActionRegistryEntry] = {}
_seeded: bool = False


# ── Public API ────────────────────────────────────────────────────────


def register_action(entry: ActionRegistryEntry) -> None:
    """Register (or replace) an action by `action_id`.

    Replacement is intentional: extensions can override platform
    actions by registering with the same id. The registry logs a
    debug line on replacement so accidental overrides show up in
    startup logs.
    """
    if entry.action_id in _registry:
        logger.debug(
            "command_bar.registry: replacing action %s (was %s, now %s)",
            entry.action_id,
            _registry[entry.action_id].action_type,
            entry.action_type,
        )
    _registry[entry.action_id] = entry


def get_registry() -> dict[str, ActionRegistryEntry]:
    """Return the full registry dict. Read-only view — do NOT mutate.

    Callers that want to iterate + filter should use the convenience
    helpers below (`list_actions`, `find_by_alias`, etc.).
    """
    _ensure_seeded()
    return _registry


def list_actions(
    *,
    action_type: ActionType | None = None,
    entity_type: str | None = None,
) -> list[ActionRegistryEntry]:
    """List actions, optionally filtered by action_type or entity_type."""
    _ensure_seeded()
    out = list(_registry.values())
    if action_type is not None:
        out = [a for a in out if a.action_type == action_type]
    if entity_type is not None:
        out = [a for a in out if a.entity_type == entity_type]
    return out


def find_by_alias(alias: str) -> ActionRegistryEntry | None:
    """Exact-match lookup by alias, case-insensitive. Returns the
    first hit — alias uniqueness is advisory, not enforced.

    This is used by the intent classifier for the ACTION intent ("type
    exactly the alias and we surface the action at the top"). Fuzzy
    matches go through `match_actions()` instead.
    """
    _ensure_seeded()
    needle = alias.strip().lower()
    if not needle:
        return None
    for entry in _registry.values():
        if entry.label.lower() == needle:
            return entry
        for a in entry.aliases:
            if a.lower() == needle:
                return entry
    return None


def match_actions(
    query: str, *, max_results: int = 10
) -> list[tuple[ActionRegistryEntry, float]]:
    """Substring + token-overlap fuzzy match against label + aliases
    + keywords. Returns (entry, score) tuples, highest score first.

    Score shape:
      - 1.0   exact match of label or alias
      - 0.9   label starts with query (prefix match)
      - 0.8   alias starts with query
      - 0.6   keyword contains query (substring)
      - 0.4   query contains keyword (reverse substring)
      - 0.3   token-overlap ratio >= 0.5

    AI classification is Phase 4+; for Phase 1 we want the registry
    matcher to be zero-AI, deterministic, and fast.
    """
    _ensure_seeded()
    q = query.strip().lower()
    if not q:
        return []

    q_tokens = set(q.split())
    scored: list[tuple[ActionRegistryEntry, float]] = []

    for entry in _registry.values():
        best = 0.0
        label_l = entry.label.lower()

        if label_l == q:
            best = 1.0
        else:
            if any(a.lower() == q for a in entry.aliases):
                best = 1.0
            elif label_l.startswith(q):
                best = max(best, 0.9)
            elif any(a.lower().startswith(q) for a in entry.aliases):
                best = max(best, 0.8)
            else:
                for kw in entry.keywords:
                    kwl = kw.lower()
                    if q in kwl:
                        best = max(best, 0.6)
                    elif kwl in q:
                        best = max(best, 0.4)
                # Token overlap on label + aliases
                bag = set(label_l.split())
                for a in entry.aliases:
                    bag.update(a.lower().split())
                if q_tokens and bag:
                    overlap = len(q_tokens & bag) / len(q_tokens)
                    if overlap >= 0.5:
                        best = max(best, 0.3 + 0.2 * overlap)

        if best > 0:
            scored.append((entry, best))

    scored.sort(key=lambda t: (-t[1], t[0].label.lower()))
    return scored[:max_results]


def reset_registry() -> None:
    """Test-only — clear the registry and mark it unseeded so the next
    `get_registry()` call triggers `_seed_default_actions()`. Mirrors
    `app.services.vault.hub_registry.reset_registry`."""
    global _seeded
    _registry.clear()
    _seeded = False


# ── Seed ──────────────────────────────────────────────────────────────


def _ensure_seeded() -> None:
    global _seeded
    if _seeded:
        return
    _seed_default_actions()
    _seeded = True


def _seed_default_actions() -> None:
    """Seed platform-owned actions at first registry access.

    Navigate actions — one per top-level page + hub. Aliases cover
    shorthand ("AR" → AR Aging, "P&L" → Profit and Loss).
    Permission gates mirror the navigation-service entries they
    represent.

    Create actions — one per currently-creatable entity type. Aliases
    cover synonyms ("order", "SO" for sales_order; "estimate", "bid"
    for quote; etc.).

    Later phases add:
      - V-1 saved views as `saved_view` entries (Phase 2)
      - Workflow Engine workflows as `workflow` entries (Phase 5)
      - Briefings as their own action type (Phase 6)
    """
    # ── Navigate actions ──────────────────────────────────────────────
    # Top-level pages a user might type the name of. Ordered by
    # discoverability priority — hubs first, then high-traffic admin
    # surfaces, then long-tail pages. Aliases are opinionated picks.
    _seed_navigate(
        action_id="nav.dashboard",
        label="Dashboard",
        aliases=["home", "main", "overview"],
        icon="LayoutDashboard",
        url="/dashboard",
    )
    _seed_navigate(
        action_id="nav.operations_board",
        label="Operations Board",
        aliases=["ops", "ops board", "operations", "production board"],
        icon="Factory",
        url="/operations",
    )
    _seed_navigate(
        action_id="nav.financials",
        label="Financials",
        aliases=["financials board", "finances", "money"],
        icon="DollarSign",
        url="/financials",
    )
    _seed_navigate(
        action_id="nav.ar_aging",
        label="AR Aging",
        aliases=["accounts receivable", "receivables", "ar", "aging"],
        icon="Receipt",
        url="/financials/ar-aging",
    )
    _seed_navigate(
        action_id="nav.ap_aging",
        label="AP Aging",
        aliases=["accounts payable", "payables", "ap"],
        icon="CreditCard",
        url="/financials/ap-aging",
    )
    _seed_navigate(
        action_id="nav.pnl",
        label="Profit and Loss",
        aliases=["P&L", "pnl", "income statement"],
        icon="TrendingUp",
        url="/financials/profit-loss",
    )
    _seed_navigate(
        action_id="nav.invoices",
        label="Invoices",
        aliases=["invoice list", "all invoices", "billing"],
        icon="FileText",
        url="/ar/invoices",
    )
    _seed_navigate(
        action_id="nav.sales_orders",
        label="Sales Orders",
        aliases=["orders", "order list", "SO", "SOs"],
        icon="ShoppingCart",
        url="/orders",
    )
    _seed_navigate(
        action_id="nav.quoting",
        label="Quoting Hub",
        aliases=["quotes", "estimates", "bids"],
        icon="FileQuestion",
        url="/quoting",
    )
    _seed_navigate(
        action_id="nav.compliance",
        label="Compliance",
        aliases=["compliance hub", "safety", "OSHA"],
        icon="ShieldCheck",
        url="/compliance",
    )
    _seed_navigate(
        action_id="nav.pricing",
        label="Price List",
        aliases=["pricing", "prices"],
        icon="Tag",
        url="/pricing",
    )
    _seed_navigate(
        action_id="nav.knowledge_base",
        label="Knowledge Base",
        aliases=["KB", "docs", "knowledge"],
        icon="BookOpen",
        url="/knowledge-base",
    )
    _seed_navigate(
        action_id="nav.vault",
        label="Bridgeable Vault",
        aliases=["vault", "vault hub", "platform"],
        icon="Vault",
        url="/vault",
        required_permission="admin",
    )
    _seed_navigate(
        action_id="nav.vault_documents",
        label="Vault Documents",
        aliases=["documents", "document log", "templates"],
        icon="FileText",
        url="/vault/documents",
        required_permission="admin",
    )
    _seed_navigate(
        action_id="nav.vault_intelligence",
        label="Intelligence",
        aliases=["prompts", "ai prompts", "intelligence log"],
        icon="Sparkles",
        url="/vault/intelligence",
        required_permission="admin",
    )
    _seed_navigate(
        action_id="nav.vault_crm",
        label="CRM",
        aliases=["crm", "companies", "customers", "contacts hub"],
        icon="Building2",
        url="/vault/crm",
        required_permission="customers.view",
    )
    _seed_navigate(
        action_id="nav.vault_notifications",
        label="Notifications",
        aliases=["inbox", "alerts", "my notifications"],
        icon="Bell",
        url="/vault/notifications",
    )
    _seed_navigate(
        action_id="nav.vault_accounting",
        label="Accounting Admin",
        aliases=["accounting", "periods", "gl classification"],
        icon="Calculator",
        url="/vault/accounting",
        required_permission="admin",
    )

    # ── Create actions ────────────────────────────────────────────────
    # One per currently-creatable entity type. The audit confirmed the
    # old `wf_compose` umbrella workflow doesn't exist in code — only
    # `wf_create_order` does. We register one create action per
    # entity with that entity's canonical creation route.
    #
    # For sales_order specifically, `wf_create_order` is the workflow
    # backbone. The create action routes to the workflow runner; the
    # workflow already handles the universal order lifecycle (including
    # disinterment and urn variants via context).
    _seed_create(
        action_id="create.sales_order",
        label="New sales order",
        # "SO" / "sales order" alone resolves to the navigate action
        # (list view). "new SO" / "new sales order" takes create-
        # verb prefix → create intent via the classifier.
        aliases=["new order", "create order", "new SO", "new sales order"],
        icon="ShoppingCart",
        entity_type="sales_order",
        url="/orders/new",
        metadata={"workflow_id": "wf_create_order"},
    )
    _seed_create(
        action_id="create.quote",
        label="New quote",
        aliases=["new quote", "create quote", "estimate", "bid", "new estimate"],
        icon="FileQuestion",
        entity_type="quote",
        url="/quoting/new",
    )
    _seed_create(
        action_id="create.case",
        label="New case",
        aliases=["new case", "new arrangement", "arrangement", "file", "new file"],
        icon="Folder",
        entity_type="fh_case",
        url="/cases/new",
        required_module="funeral_home",
    )
    _seed_create(
        action_id="create.invoice",
        label="New invoice",
        aliases=["new invoice", "create invoice", "bill", "new bill"],
        icon="Receipt",
        entity_type="invoice",
        url="/ar/invoices/new",
    )
    _seed_create(
        action_id="create.contact",
        label="New contact",
        aliases=["new contact", "add contact", "new person"],
        icon="UserPlus",
        entity_type="contact",
        url="/vault/crm/contacts/new",
        required_permission="customers.view",
    )
    _seed_create(
        action_id="create.product",
        label="New product",
        aliases=["new product", "add product", "new SKU"],
        icon="Package",
        entity_type="product",
        url="/products/new",
    )
    # Phase 4 — event creation via NL overlay (vault_item.type=event).
    _seed_create(
        action_id="create.event",
        label="New event",
        aliases=[
            "new event", "add event", "schedule event",
            "new meeting", "schedule meeting", "new calendar event",
        ],
        icon="Calendar",
        entity_type="event",
        url="/vault/calendar",
    )
    # Phase 5 — task creation via NL overlay (deferred from Phase 4).
    _seed_create(
        action_id="create.task",
        label="New task",
        aliases=[
            "new task", "add task", "create task", "todo", "new todo",
        ],
        icon="CheckSquare",
        entity_type="task",
        url="/tasks/new",
    )


def _seed_navigate(
    *,
    action_id: str,
    label: str,
    icon: str,
    url: str,
    aliases: list[str] | None = None,
    required_permission: str | None = None,
    required_module: str | None = None,
    required_extension: str | None = None,
) -> None:
    """Internal helper — one call per navigate action."""
    register_action(
        ActionRegistryEntry(
            action_id=action_id,
            action_type="navigate",
            label=label,
            icon=icon,
            aliases=aliases or [],
            keywords=[label.lower()] + [a.lower() for a in (aliases or [])],
            target_url=url,
            required_permission=required_permission,
            required_module=required_module,
            required_extension=required_extension,
        )
    )


def _seed_create(
    *,
    action_id: str,
    label: str,
    icon: str,
    entity_type: str,
    url: str,
    aliases: list[str] | None = None,
    required_permission: str | None = None,
    required_module: str | None = None,
    required_extension: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Internal helper — one call per create action."""
    register_action(
        ActionRegistryEntry(
            action_id=action_id,
            action_type="create",
            label=label,
            icon=icon,
            aliases=aliases or [],
            keywords=[label.lower()] + [a.lower() for a in (aliases or [])],
            entity_type=entity_type,
            target_url=url,
            required_permission=required_permission,
            required_module=required_module,
            required_extension=required_extension,
            metadata=metadata or {},
        )
    )
