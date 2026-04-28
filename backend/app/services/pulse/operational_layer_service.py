"""Operational layer composition — work in user's operational scope.

Per BRIDGEABLE_MASTER §3.26.2.3 + §3.26.3.1, Operational Layer
composes from existing widget data sources, gated by the user's
selected `work_areas`. The layer dominates the primary work-surface
area per §3.26.2.4.

**Work-area → widget mapping (Phase W-4a Commit 2 — surfaced for
confirmation before Commit 3 composition engine consumes it):**

| Work area               | Widgets                                  | Notes                                                       |
|-------------------------|------------------------------------------|-------------------------------------------------------------|
| Production Scheduling   | vault_schedule (Detail), line_status     | Manufacturing core. Vault schedule dominates primary surface |
| Delivery Scheduling     | vault_schedule (Detail), scheduling.ancillary-pool, today | Dispatcher demo composition                            |
| Inventory Management    | urn_catalog_status (if extension), line_status | line_status surfaces inventory dimension via metrics  |
| Inside Sales            | (none today — sales pipeline widget post-September) | STUB for September                                  |
| Customer Service        | recent_activity (V-1c)                   | Customer comms via recent_activity feed                     |
| Family Communications   | (FH cases widget post-W-3c)              | DEFERRED for September manufacturing focus                  |
| Cross-tenant Coordination | (cross-tenant orders widget post-W-4b) | DEFERRED — depends on cross-tenant communications          |
| Accounting              | anomalies, ar_summary (existing dashboard widget) | Phase 1 accounting agent infrastructure                |
| HR                      | (HR widget post-September)               | STUB for September                                          |

**Vertical-default fallback (D4):** users without `work_areas` set
fall back to a vertical-default composition. For September:
  • manufacturing: Sunnycrest-equivalent dispatcher composition
    (vault_schedule + line_status + scheduling.ancillary-pool +
    today + urn_catalog_status if extension active)
  • funeral_home / cemetery / crematory: sparse defaults pointing to
    primary work surface for that vertical (recent_activity +
    today as universal cross-vertical fallback)

**Tenant + extension awareness:**
  • urn_catalog_status only surfaces if `urn_sales` extension is
    activated AND the urn_sales product line is enabled.
  • vault_schedule + line_status only surface for manufacturing
    tenants with the vault product line enabled.
  • The 5-axis filter at widget_service.get_available_widgets is the
    canonical gate; this layer service applies a conservative
    pre-filter so we never surface a widget the tenant can't access.

**Tenant isolation:** the layer service emits `LayerItem`s with
`component_key`s pointing at widgets. Each widget self-fetches via
its tenant-scoped endpoint (canonical Phase W-3 pattern), so cross-
tenant leakage is prevented at the widget data source. This service
does NOT pre-fetch widget data inline.
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.user import User
from app.services.pulse.types import LayerContent, LayerItem


# ── Work-area → widget mapping ──────────────────────────────────────


# Each entry is a list of (widget_id, variant_id, cols, rows, priority)
# tuples. Priority is layer-internal — higher = surfaces first / larger.
# Composition engine (Commit 3) may further adjust sizing.
WORK_AREA_WIDGET_MAPPING: dict[str, list[tuple[str, str, int, int, int]]] = {
    "Production Scheduling": [
        # vault_schedule Detail (2x2) is the primary work surface for
        # production-scheduling per §3.26.2.4 "Operational layer
        # dominates primary work-surface area" + the demo composition
        # confirmation D5.
        ("vault_schedule", "detail", 2, 2, 90),
        ("line_status", "brief", 2, 1, 70),
    ],
    "Delivery Scheduling": [
        ("vault_schedule", "detail", 2, 2, 90),
        ("scheduling.ancillary-pool", "brief", 2, 1, 80),
        ("today", "glance", 1, 1, 50),
    ],
    "Inventory Management": [
        # urn_catalog_status only surfaces if urn_sales extension
        # active. Pre-filter logic below filters this out for tenants
        # without the extension. line_status ALSO carries inventory
        # signal in its metrics dict.
        ("urn_catalog_status", "glance", 1, 1, 60),
        ("line_status", "brief", 2, 1, 70),
    ],
    "Customer Service": [
        # V-1c recent activity feed surfaces customer-side events
        # (orders, deliveries, communications when comms ship).
        ("recent_activity", "brief", 2, 1, 65),
    ],
    "Accounting": [
        # Phase 1+ accounting agent anomalies + Phase W-3a anomalies
        # widget surfaces unresolved issues. ar_summary is a legacy
        # dashboard widget covering AR aging.
        ("anomalies", "brief", 2, 1, 75),
        ("ar_summary", "brief", 2, 1, 60),
    ],
    # ── Stubs for W-4b primitives ───────────────────────────────────
    # Inside Sales, Family Communications, Cross-tenant Coordination,
    # HR map to no widgets in W-4a. Empty list = no operational
    # content from that work area, but the area's selection is still
    # signal-collected for Tier 2 algorithms.
    "Inside Sales": [],
    "Family Communications": [],
    "Cross-tenant Coordination": [],
    "HR": [],
}


# ── Vertical-default fallback compositions (D4 resolution) ──────────


VERTICAL_DEFAULT_COMPOSITIONS: dict[
    str, list[tuple[str, str, int, int, int]]
] = {
    "manufacturing": [
        # Sunnycrest-equivalent dispatcher composition — confirmed in
        # D5. Detail vault_schedule dominates primary surface;
        # line_status + ancillary_pool + today fill in.
        ("vault_schedule", "detail", 2, 2, 90),
        ("line_status", "brief", 2, 1, 70),
        ("scheduling.ancillary-pool", "brief", 2, 1, 80),
        ("today", "glance", 1, 1, 50),
        # urn_catalog_status only if extension active (filtered below).
        ("urn_catalog_status", "glance", 1, 1, 60),
    ],
    "funeral_home": [
        # Sparse but meaningful — `today` for cross-vertical relevance
        # + recent_activity for case-comms feed once W-3c lands the
        # FH-specific widgets, this fallback gets richer.
        ("today", "glance", 1, 1, 60),
        ("recent_activity", "brief", 2, 1, 50),
    ],
    "cemetery": [
        ("today", "glance", 1, 1, 60),
        ("recent_activity", "brief", 2, 1, 50),
    ],
    "crematory": [
        ("today", "glance", 1, 1, 60),
        ("recent_activity", "brief", 2, 1, 50),
    ],
}


# ── Helpers ─────────────────────────────────────────────────────────


def _enabled_widget_ids_for_user(
    db: Session, *, user: User
) -> set[str]:
    """Return the set of widget_ids visible to this user per the
    canonical 5-axis filter at widget_service.get_available_widgets.

    We pre-filter at the operational layer so widgets that fail the
    extension/product-line/vertical/permission gates don't surface
    even when listed in the work-area mapping. The downstream widget
    data endpoint also filters as defense-in-depth — this is the
    layer-level pre-filter.
    """
    try:
        from app.services.widgets.widget_service import get_available_widgets

        # Use "pulse" page context — the canonical Pulse surface.
        widgets = get_available_widgets(
            db, user.company_id, user, "pulse"
        )
    except Exception:
        # Defensive: a widget service failure must not blank the
        # operational layer. Return empty set → fallback to no
        # widgets, layer renders empty advisory.
        return set()
    return {
        w["widget_id"]
        for w in widgets
        if w.get("is_available") is True
    }


def _resolve_tenant_vertical(db: Session, tenant_id: str) -> str | None:
    company = (
        db.query(Company).filter(Company.id == tenant_id).first()
    )
    return getattr(company, "vertical", None) if company else None


def _build_items_from_mapping(
    mapping_entries: Iterable[tuple[str, str, int, int, int]],
    *,
    enabled_widget_ids: set[str],
    seen_widget_ids: set[str],
) -> list[LayerItem]:
    """Translate (widget_id, variant_id, cols, rows, priority) tuples
    into LayerItems, skipping widgets the tenant can't access AND
    widgets already added (de-dupe across overlapping work areas)."""
    out: list[LayerItem] = []
    for widget_id, variant_id, cols, rows, priority in mapping_entries:
        if widget_id in seen_widget_ids:
            continue
        if widget_id not in enabled_widget_ids:
            # Widget not available to this tenant (extension/product-
            # line/vertical filter). Silently skip; layer still
            # renders other items.
            continue
        out.append(
            LayerItem(
                item_id=f"widget:{widget_id}",
                kind="widget",
                component_key=widget_id,
                variant_id=variant_id,  # type: ignore[arg-type]
                cols=cols,
                rows=rows,
                priority=priority,
            )
        )
        seen_widget_ids.add(widget_id)
    return out


# ── Public API ──────────────────────────────────────────────────────


def compose_for_user(
    db: Session,
    *,
    user: User,
) -> LayerContent:
    """Build the Operational layer for a given user.

    Composition logic:
      1. If user has work_areas set: union of widgets across all
         selected areas, de-duped, filtered by widget availability.
      2. If user has no work_areas: vertical-default fallback per
         D4 resolution.
      3. Items sorted by priority desc within the layer.

    Empty-state contract: returns `LayerContent(items=[], advisory=...)`
    with a friendly hint pointing the user at onboarding when no
    items surface (no work_areas + no vertical default + no enabled
    widgets in the mapping).
    """
    enabled_widget_ids = _enabled_widget_ids_for_user(db, user=user)
    work_areas = user.work_areas or []

    items: list[LayerItem] = []
    seen: set[str] = set()

    if work_areas:
        # Build from work-area mapping — union across selected areas.
        for area in work_areas:
            entries = WORK_AREA_WIDGET_MAPPING.get(area, [])
            items.extend(
                _build_items_from_mapping(
                    entries,
                    enabled_widget_ids=enabled_widget_ids,
                    seen_widget_ids=seen,
                )
            )
        advisory: str | None = None
        if not items:
            # Selected work_areas but no widgets enabled (e.g., user
            # selected "Inside Sales" only; no widgets shipped yet).
            advisory = (
                "Nothing surfacing for your selected work areas yet — "
                "more widgets ship as platform extensions activate."
            )
    else:
        # Vertical-default fallback (D4).
        vertical = _resolve_tenant_vertical(db, user.company_id)
        default_entries = (
            VERTICAL_DEFAULT_COMPOSITIONS.get(vertical or "", [])
            if vertical
            else []
        )
        items = _build_items_from_mapping(
            default_entries,
            enabled_widget_ids=enabled_widget_ids,
            seen_widget_ids=seen,
        )
        advisory = (
            "Showing the default view. Personalize what you see by "
            "setting your work areas in your profile."
            if items
            else "No work surfaces available yet."
        )

    # Sort within layer by priority desc; stable sort preserves
    # mapping-order ties (so "Production Scheduling" widgets stay
    # together even when priorities tie).
    items.sort(key=lambda it: (-it.priority, it.component_key))

    return LayerContent(layer="operational", items=items, advisory=advisory)
