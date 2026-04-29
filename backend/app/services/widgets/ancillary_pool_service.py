"""Ancillary Pool widget — mode-aware pool of pending ancillaries.

Phase W-4a Cleanup Session B.2 — surface-fetched data source for the
**pulse_grid surface** rendering of `scheduling.ancillary-pool`. Closes
the Path 3 deferral surfaced in Phase W-4a Step 5: AncillaryPoolPin
strict `useSchedulingFocus()` hook prevented pulse_grid mounting; this
service powers the read-only fallback path so the widget renders in
home Pulse without the SchedulingFocusDataProvider context.

**Surface-fetched data discipline (per DESIGN_LANGUAGE §12.6 +
§12.6a)**: workspace-core widgets read from the SAME source the Focus
core consumes when interactive (FH Focus subtree → context provider).
When mounted outside the Focus subtree (pulse_grid surface), the widget
falls back to a parallel read-only endpoint — that's this service.
The data shape is identical to `/dispatch/pool-ancillaries` for the
items list; the surface-endpoint additionally exposes
`operating_mode` + `mode_note` + `total_count` + `is_vault_enabled`
so the Brief variant can render workspace-shape advisories per
§13.3.2.1 (preserve workspace shape across surfaces).

Mode-aware rendering per BRIDGEABLE_MASTER §5.2.2:
  • Production / hybrid mode → returns full pool (active in-house
    operations)
  • Purchase mode → returns empty `items` + `mode_note=
    "no_pool_in_purchase_mode"`. The Brief variant renders the
    advisory + preserves the "Open in scheduling Focus" CTA per
    §13.3.2.1 workspace-shape preservation discipline.
  • Vault not enabled → returns `is_vault_enabled=False` + empty
    items. Frontend renders empty state with a CTA to enable the
    product line in settings.

Tenant isolation: explicit `Company.id == user.company_id` filter.
Per Phase W-3a canonical tenant-isolation discipline (vault_schedule_
service is the established pattern; this service mirrors it).

**Why a dedicated endpoint vs reusing `/dispatch/pool-ancillaries`**:
  1. Mode dispatch — `/dispatch/pool-ancillaries` doesn't read
     `TenantProductLine.config["operating_mode"]`; surface-fetched
     widget rendering needs the dispatch.
  2. Widget-shaped response — Brief variant needs `total_count` +
     `mode_note` + `primary_navigation_target` so the rendering can
     compose advisory + CTA without secondary fetches.
  3. Caller surface separation — `/dispatch/pool-ancillaries` is the
     FH Focus interactive surface (returns rich `MonitorDeliveryDTO`
     with all drag-source fields); `/widget-data/ancillary-pool` is
     the Pulse-surface read-only view (returns the slim items shape
     the Brief variant renders).

Pool definition (matches `/dispatch/pool-ancillaries` filter exactly):
  scheduling_type == "ancillary"
  AND attached_to_delivery_id IS NULL
  AND primary_assignee_id IS NULL
  AND ancillary_is_floating IS TRUE
  AND status != "cancelled"
  AND (ancillary_fulfillment_status != "completed" OR NULL)
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.delivery import Delivery
from app.models.user import User


# ── Mode resolution (mirrors vault_schedule_service for consistency) ──


VALID_MODES = ("production", "purchase", "hybrid")


def _resolve_operating_mode(db: Session, tenant_id: str) -> str | None:
    """Read `TenantProductLine(line_key="vault").config["operating_mode"]`.

    Returns "production" / "purchase" / "hybrid", or None when the
    vault product line isn't enabled. Defensive against legacy config
    shapes — falls back to "production" when the row exists without
    an explicit `operating_mode` key (matches the r60 backfill
    semantics + vault_schedule_service convention).
    """
    try:
        from app.models.tenant_product_line import TenantProductLine

        row = (
            db.query(TenantProductLine)
            .filter(
                TenantProductLine.company_id == tenant_id,
                TenantProductLine.line_key == "vault",
                TenantProductLine.is_enabled.is_(True),
            )
            .first()
        )
    except Exception:
        return None
    if row is None:
        return None
    cfg = row.config or {}
    mode = cfg.get("operating_mode")
    if mode in VALID_MODES:
        return mode
    # Defensive fallback — vault row exists but mode tag missing →
    # treat as production (mirrors vault_schedule_service).
    return "production"


# ── Pool item shape ─────────────────────────────────────────────────


def _serialize_pool_item(d: Delivery) -> dict:
    """Slim widget-consumption shape — fields the Brief variant
    renders (label, subhead, navigation context). Mirrors the
    `resolvePoolItemLabel` / `resolvePoolItemSubhead` fallback chain
    in AncillaryPoolPin.tsx so the frontend's same display logic
    works against the surface-fetched payload.

    Items remain sortable by ancillary_soft_target_date (oldest
    first → most-pending-attention surfaces first) per the existing
    /dispatch/pool-ancillaries ordering.
    """
    type_config = d.type_config or {}
    return {
        "id": d.id,
        "delivery_type": d.delivery_type,
        "type_config": type_config,
        "ancillary_soft_target_date": (
            d.ancillary_soft_target_date.isoformat()
            if d.ancillary_soft_target_date
            else None
        ),
        "created_at": (
            d.created_at.isoformat() if d.created_at else None
        ),
    }


# ── Public API ──────────────────────────────────────────────────────


def get_ancillary_pool(
    db: Session,
    *,
    user: User,
    tenant_id: Optional[str] = None,
) -> dict:
    """Return the ancillary pool for the user's tenant.

    Mode-aware: production / hybrid → full pool list; purchase →
    empty + mode_note advisory; vault disabled → is_vault_enabled
    false + empty.

    Response shape:
        {
          "operating_mode": "production" | "purchase" | "hybrid" | null,
          "is_vault_enabled": bool,
          "items": [ { id, delivery_type, type_config, ... }, ... ],
          "total_count": int,
          "mode_note": str | null,    # "no_pool_in_purchase_mode" or null
          "primary_navigation_target": "/dispatch" | null,
        }

    Tenant scoping: `Company.id == user.company_id` enforced server-
    side. `tenant_id` parameter is for testing only — defaults to
    `user.company_id`.

    Performance: single SELECT with no joins (items are slim shape;
    type_config is a JSONB column already on Delivery). Sub-100ms on
    Sunnycrest dev (pool typically <20 rows).
    """
    tid = tenant_id or user.company_id
    if not tid:
        return {
            "operating_mode": None,
            "is_vault_enabled": False,
            "items": [],
            "total_count": 0,
            "mode_note": None,
            "primary_navigation_target": None,
        }

    mode = _resolve_operating_mode(db, tid)

    # Vault not enabled → empty payload + is_vault_enabled=False.
    if mode is None:
        return {
            "operating_mode": None,
            "is_vault_enabled": False,
            "items": [],
            "total_count": 0,
            "mode_note": None,
            "primary_navigation_target": None,
        }

    # Purchase mode → no pool concept (vault arrives via licensee
    # transfers, not poured in-house). Return empty items + advisory
    # mode_note. Workspace-shape preservation per §13.3.2.1 — the
    # Brief variant renders advisory + CTA, not a generic empty state.
    if mode == "purchase":
        return {
            "operating_mode": "purchase",
            "is_vault_enabled": True,
            "items": [],
            "total_count": 0,
            "mode_note": "no_pool_in_purchase_mode",
            "primary_navigation_target": "/dispatch",
        }

    # Production / hybrid → real pool.
    rows: list[Delivery] = (
        db.query(Delivery)
        .filter(
            Delivery.company_id == tid,
            Delivery.scheduling_type == "ancillary",
            Delivery.attached_to_delivery_id.is_(None),
            Delivery.primary_assignee_id.is_(None),
            Delivery.ancillary_is_floating.is_(True),
            Delivery.status != "cancelled",
        )
        .filter(
            # Match /dispatch/pool-ancillaries exactly: exclude
            # completed; null fulfillment_status allowed (legacy data).
            or_(
                Delivery.ancillary_fulfillment_status != "completed",
                Delivery.ancillary_fulfillment_status.is_(None),
            )
        )
        .order_by(
            Delivery.ancillary_soft_target_date.asc().nullslast(),
            Delivery.created_at.asc(),
        )
        .all()
    )

    items = [_serialize_pool_item(d) for d in rows]

    return {
        "operating_mode": mode,
        "is_vault_enabled": True,
        "items": items,
        "total_count": len(items),
        "mode_note": None,
        "primary_navigation_target": "/dispatch",
    }
