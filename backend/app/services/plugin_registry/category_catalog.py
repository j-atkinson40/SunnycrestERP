"""Plugin Registry — category-key → introspection callable catalog.

24 entries mirroring PLUGIN_CONTRACTS.md sections. Each entry either
provides a live-introspection callable (Tier R1/R2 registries) OR
declares the category non-introspectable with a `reason` + expected
count (Tier R3/R4 categories awaiting registry promotion).

The catalog is the single point of substrate-change for R-8.y.d.
Future migrations promote a category from non-introspectable to
introspectable by adding/swapping the callable. The browser UI
flips the `registry_introspectable` flag automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ─── Introspection callable contract ─────────────────────────────────
#
# Each introspection callable returns a tuple:
#   (registrations: list[dict], registry_size: int)
#
# Each registration is a dict with at minimum:
#   {"key": str, "metadata": dict}
#
# Metadata shape varies per category but stays JSON-serializable.


@dataclass(frozen=True)
class CategoryIntrospection:
    """Catalog entry for one plugin category.

    Either `callable_fn` is set (introspectable category — call it to
    enumerate live registry state) OR `reason` is set (category is
    documented in PLUGIN_CONTRACTS.md but the runtime registry doesn't
    enumerate today; the reason explains why + flags the promotion
    arc when known).
    """

    category_key: str
    callable_fn: Optional[Callable[[], tuple[list[dict], int]]] = None
    reason: str = ""
    expected_implementations_count: int = 0
    tier_hint: str = ""

    @property
    def introspectable(self) -> bool:
        return self.callable_fn is not None


# ─── Per-category introspection callables ────────────────────────────


def _intro_email_providers() -> tuple[list[dict], int]:
    from app.services.email.providers import PROVIDER_REGISTRY

    registrations = [
        {
            "key": key,
            "metadata": {
                "class_name": cls.__name__,
                "module": cls.__module__,
            },
        }
        for key, cls in sorted(PROVIDER_REGISTRY.items())
    ]
    return registrations, len(registrations)


def _intro_calendar_providers() -> tuple[list[dict], int]:
    from app.services.calendar.providers import PROVIDER_REGISTRY

    registrations = [
        {
            "key": key,
            "metadata": {
                "class_name": cls.__name__,
                "module": cls.__module__,
            },
        }
        for key, cls in sorted(PROVIDER_REGISTRY.items())
    ]
    return registrations, len(registrations)


def _intro_notification_categories() -> tuple[list[dict], int]:
    from app.services.notifications.category_types import (
        NOTIFICATION_CATEGORY_REGISTRY,
    )

    registrations = [
        {"key": key, "metadata": dict(meta)}
        for key, meta in sorted(NOTIFICATION_CATEGORY_REGISTRY.items())
    ]
    return registrations, len(registrations)


def _intro_activity_log_types() -> tuple[list[dict], int]:
    from app.services.crm.activity_log_types import ACTIVITY_TYPE_REGISTRY

    registrations = [
        {"key": key, "metadata": dict(meta)}
        for key, meta in sorted(ACTIVITY_TYPE_REGISTRY.items())
    ]
    return registrations, len(registrations)


def _intro_composition_action_types() -> tuple[list[dict], int]:
    # Side-effect imports populate the registry. Email + Calendar
    # action service modules register their action types at import
    # time; ensure they're loaded before reading _REGISTRY.
    from app.services import email  # noqa: F401
    try:
        from app.services.calendar import calendar_action_service  # noqa: F401
    except ImportError:
        pass
    from app.services.platform.action_registry import _REGISTRY

    registrations = []
    for key in sorted(_REGISTRY.keys()):
        descriptor = _REGISTRY[key]
        meta: dict[str, Any] = {"action_type": key}
        # ActionTypeDescriptor — surface canonical attrs without
        # depending on import-time class layout.
        for attr in (
            "primitive",
            "linked_entity_type",
            "display_name",
            "description",
        ):
            val = getattr(descriptor, attr, None)
            if val is not None:
                meta[attr] = val
        registrations.append({"key": key, "metadata": meta})
    return registrations, len(registrations)


def _intro_document_blocks() -> tuple[list[dict], int]:
    from app.services.documents.block_registry import list_block_kinds

    registrations = []
    for block in list_block_kinds():
        meta = {
            "kind": getattr(block, "kind", None),
            "display_name": getattr(block, "display_name", None),
            "description": getattr(block, "description", None),
            "accepts_children": getattr(block, "accepts_children", False),
        }
        registrations.append(
            {
                "key": meta["kind"] or "<unknown>",
                "metadata": {k: v for k, v in meta.items() if v is not None},
            }
        )
    registrations.sort(key=lambda r: r["key"])
    return registrations, len(registrations)


def _intro_workshop_template_types() -> tuple[list[dict], int]:
    from app.services.workshop.registry import list_template_types

    registrations = []
    for descriptor in list_template_types():
        meta = {}
        for attr in (
            "template_type",
            "display_name",
            "description",
            "applicable_verticals",
            "applicable_authoring_contexts",
            "tune_mode_dimensions",
            "sort_order",
        ):
            val = getattr(descriptor, attr, None)
            if val is not None:
                meta[attr] = val
        registrations.append(
            {
                "key": meta.get("template_type", "<unknown>"),
                "metadata": meta,
            }
        )
    registrations.sort(key=lambda r: r["key"])
    return registrations, len(registrations)


def _intro_widget_kinds() -> tuple[list[dict], int]:
    from app.services.widgets.widget_registry import WIDGET_DEFINITIONS

    registrations = []
    for w in WIDGET_DEFINITIONS:
        meta = {
            "title": w.get("title"),
            "category": w.get("category"),
            "default_size": w.get("default_size"),
            "supported_surfaces": w.get("supported_surfaces"),
            "required_vertical": w.get("required_vertical"),
            "required_product_line": w.get("required_product_line"),
            "default_enabled": w.get("default_enabled"),
        }
        registrations.append(
            {
                "key": w.get("widget_id", "<unknown>"),
                "metadata": {k: v for k, v in meta.items() if v is not None},
            }
        )
    registrations.sort(key=lambda r: r["key"])
    return registrations, len(registrations)


def _intro_focus_composition_kinds() -> tuple[list[dict], int]:
    # Per PLUGIN_CONTRACTS.md §2, the canonical kinds today are
    # the two enumerated CHECK values on focus_compositions.kind.
    # Surface them as the introspection payload — operators reading
    # the browser need the same two values regardless of DB state.
    registrations = [
        {
            "key": "focus",
            "metadata": {
                "description": "Standalone Focus primitive — scheduling, arrangement_scribe, triage_decision Focuses.",
                "pages_field": False,
                "rows_field": True,
            },
        },
        {
            "key": "edge_panel",
            "metadata": {
                "description": "Multi-page tenant edge panel substrate (R-5.0). Pages array non-empty; top-level rows empty.",
                "pages_field": True,
                "rows_field": False,
            },
        },
    ]
    return registrations, len(registrations)


def _intro_theme_tokens() -> tuple[list[dict], int]:
    # Theme tokens are the canonical CSS token catalog read from
    # frontend/src/styles/tokens.css. Backend doesn't enumerate them
    # — the frontend token catalog at `lib/visual-editor/themes/`
    # is the canonical surface. Mark as introspectable-via-frontend
    # rather than ship a Python mirror; the browser already imports
    # the snapshot for content, and tokens.css is read by the
    # editor's PreviewCanvas. Returning empty + size=0 here signals
    # "see frontend token catalog" — the snapshot's Current
    # Implementations subsection links there.
    return [], 0


def _intro_accounting_providers() -> tuple[list[dict], int]:
    # Accounting providers per PLUGIN_CONTRACTS.md §8 enumerated via
    # the provider abstraction. The current canonical set is fixed
    # in `accounting/providers/`. Listing module-level providers:
    try:
        from app.services.accounting.providers import sage_csv_provider  # noqa: F401
    except ImportError:
        sage_csv_provider = None
    try:
        from app.services.accounting.providers import qbo_provider  # noqa: F401
    except ImportError:
        qbo_provider = None

    registrations = []
    if sage_csv_provider is not None:
        registrations.append(
            {
                "key": "sage_csv",
                "metadata": {
                    "module": "app.services.accounting.providers.sage_csv_provider",
                    "description": "Sage 100 CSV export provider.",
                },
            }
        )
    if qbo_provider is not None:
        registrations.append(
            {
                "key": "qbo",
                "metadata": {
                    "module": "app.services.accounting.providers.qbo_provider",
                    "description": "QuickBooks Online OAuth API provider.",
                },
            }
        )
    return registrations, len(registrations)


def _intro_playwright_scripts() -> tuple[list[dict], int]:
    # Per PLUGIN_CONTRACTS.md §10 — Playwright scripts are registered
    # in `app/services/playwright/script_registry.py` if it exists.
    try:
        from app.services.playwright.script_registry import (
            list_playwright_scripts,
        )
    except ImportError:
        return [], 0

    try:
        scripts = list_playwright_scripts()
    except Exception:
        return [], 0

    registrations = []
    for s in scripts:
        meta = {}
        for attr in ("name", "description", "credential_required"):
            val = getattr(s, attr, None)
            if val is not None:
                meta[attr] = val
        registrations.append(
            {"key": meta.get("name", "<unknown>"), "metadata": meta}
        )
    registrations.sort(key=lambda r: r["key"])
    return registrations, len(registrations)


# ─── Catalog: 24 entries mirroring PLUGIN_CONTRACTS.md §1-§24 ────────


CATEGORY_CATALOG: dict[str, CategoryIntrospection] = {
    # §1 ✓ canonical
    "intake_adapters": CategoryIntrospection(
        category_key="intake_adapters",
        reason="Tier R3 — 3 canonical adapters (email/form/file) enforced via CHECK constraint on tenant_workflow_email_rules.adapter_type. No register_adapter API today; extension is substrate edit.",
        expected_implementations_count=3,
        tier_hint="R3",
    ),
    # §2 ✓ canonical
    "focus_composition_kinds": CategoryIntrospection(
        category_key="focus_composition_kinds",
        callable_fn=_intro_focus_composition_kinds,
        tier_hint="R3",
    ),
    # §3 ✓ canonical
    "widget_kinds": CategoryIntrospection(
        category_key="widget_kinds",
        callable_fn=_intro_widget_kinds,
        tier_hint="R2",
    ),
    # §4 ✓ canonical
    "document_blocks": CategoryIntrospection(
        category_key="document_blocks",
        callable_fn=_intro_document_blocks,
        tier_hint="R1",
    ),
    # §5 ✓ canonical
    "theme_tokens": CategoryIntrospection(
        category_key="theme_tokens",
        reason="Theme tokens live in frontend/src/styles/tokens.css + lib/visual-editor/themes/ — canonical surface is the frontend token catalog, not a backend registry. Browser deep-links to the Themes editor for the live token list.",
        expected_implementations_count=80,
        tier_hint="R2",
    ),
    # §6 ✓ canonical
    "workshop_template_types": CategoryIntrospection(
        category_key="workshop_template_types",
        callable_fn=_intro_workshop_template_types,
        tier_hint="R1",
    ),
    # §7 ✓ canonical
    "composition_action_types": CategoryIntrospection(
        category_key="composition_action_types",
        callable_fn=_intro_composition_action_types,
        tier_hint="R1",
    ),
    # §8 ✓ canonical
    "accounting_providers": CategoryIntrospection(
        category_key="accounting_providers",
        callable_fn=_intro_accounting_providers,
        tier_hint="R3",
    ),
    # §9 ✓ canonical
    "email_providers": CategoryIntrospection(
        category_key="email_providers",
        callable_fn=_intro_email_providers,
        tier_hint="R2",
    ),
    # §10 ✓ canonical
    "playwright_scripts": CategoryIntrospection(
        category_key="playwright_scripts",
        callable_fn=_intro_playwright_scripts,
        tier_hint="R1",
    ),
    # §11 ✓ canonical (reclassified)
    "calendar_providers": CategoryIntrospection(
        category_key="calendar_providers",
        callable_fn=_intro_calendar_providers,
        tier_hint="R2",
    ),
    # §12 ~ partial — Tier R4 dispatch chain
    "workflow_node_types": CategoryIntrospection(
        category_key="workflow_node_types",
        reason="Tier R4 — if/elif dispatch chain in workflow_engine._execute_action. Promotion to a Tier R1 registry is the R-9 workflow node registry migration candidate per R-8 audit Tier 2.",
        expected_implementations_count=13,
        tier_hint="R4",
    ),
    # §13 ~ partial
    "intelligence_providers": CategoryIntrospection(
        category_key="intelligence_providers",
        reason="Partial — Anthropic SDK is the sole canonical provider. Provider abstraction is implicit; multi-provider support deferred. See PLUGIN_CONTRACTS.md §13 Current Divergences.",
        expected_implementations_count=1,
        tier_hint="R3",
    ),
    # §14 ~ partial
    "delivery_channels": CategoryIntrospection(
        category_key="delivery_channels",
        reason="Partial — protocol-based channel interface at delivery/channels/. Channels register via module-level imports; no canonical register_channel API. Email + SMS stub channels in production.",
        expected_implementations_count=2,
        tier_hint="R3",
    ),
    # §15 ~ partial — triage queue configs (DB-resident, can't list without session)
    "triage_queue_configs": CategoryIntrospection(
        category_key="triage_queue_configs",
        reason="Triage queue configs combine in-code platform defaults (app/services/triage/platform_defaults.py) + per-tenant vault_items overrides. Browser introspection without a DB session and tenant scope is not meaningful. Per-tenant configuration browser arc (R-8.y+1) will surface these in context.",
        expected_implementations_count=2,
        tier_hint="R3",
    ),
    # §16 ~ partial
    "agent_kinds": CategoryIntrospection(
        category_key="agent_kinds",
        reason="Partial — AgentRunner.AGENT_REGISTRY (Python dict) registers 13 accounting agents via class-level constant. Not a register_agent API; canonical extension is module edit. R-9 agent registry promotion is a future candidate.",
        expected_implementations_count=13,
        tier_hint="R2",
    ),
    # §17 ~ partial
    "button_kinds": CategoryIntrospection(
        category_key="button_kinds",
        reason="Partial — R-4 ButtonRegistry + per-button registration shims. Frontend-resident registry (not Python-side). Browser shares the Component Registry's reach but doesn't enumerate buttons through a backend endpoint.",
        expected_implementations_count=3,
        tier_hint="R1",
    ),
    # §18 ~ implicit
    "intake_match_condition_operators": CategoryIntrospection(
        category_key="intake_match_condition_operators",
        reason="Tier R3 partial — closed-vocabulary operator catalogs per adapter (5 email + 5 form + 5 file). No register_operator API; vocabulary frozen in tier_1_rules.py + frontend mirror.",
        expected_implementations_count=15,
        tier_hint="R3",
    ),
    # §19 ✓ canonical (reclassified)
    "notification_categories": CategoryIntrospection(
        category_key="notification_categories",
        callable_fn=_intro_notification_categories,
        tier_hint="R2",
    ),
    # §20 ✓ canonical (reclassified)
    "activity_log_event_types": CategoryIntrospection(
        category_key="activity_log_event_types",
        callable_fn=_intro_activity_log_types,
        tier_hint="R2",
    ),
    # §21 ~ implicit
    "pdf_generator_callers": CategoryIntrospection(
        category_key="pdf_generator_callers",
        reason="Implicit pattern — each PDF generator (invoice/statement/quote/etc.) is its own service module routing through document_renderer.render(). No central registry; canonical pattern is documented in CLAUDE.md §4 Documents arc.",
        expected_implementations_count=8,
        tier_hint="R4",
    ),
    # §22 ~ implicit
    "page_contexts": CategoryIntrospection(
        category_key="page_contexts",
        reason="Implicit pattern — page_contexts strings live in widget_definitions[*].page_contexts + frontend route constants. No central enumeration today.",
        expected_implementations_count=6,
        tier_hint="R3",
    ),
    # §23 ~ implicit
    "customer_classification_rules": CategoryIntrospection(
        category_key="customer_classification_rules",
        reason="Implicit pattern — classification rules embedded in crm_visibility_service. R-classify migration candidate per R-8 audit Tier 2 surfaces this as a canonical registry.",
        expected_implementations_count=4,
        tier_hint="R4",
    ),
    # §24 ~ implicit
    "intent_classifiers": CategoryIntrospection(
        category_key="intent_classifiers",
        reason="Implicit pattern — command bar intent classifier is rule-based (intent.py). Multi-classifier abstraction deferred until concrete second classifier emerges.",
        expected_implementations_count=1,
        tier_hint="R4",
    ),
}


def get_category_introspection(
    category_key: str,
) -> Optional[CategoryIntrospection]:
    return CATEGORY_CATALOG.get(category_key)


def list_category_keys() -> list[str]:
    return sorted(CATEGORY_CATALOG.keys())
