"""Vault Schedule widget — mode-aware vault production scheduling.

Phase W-3d cluster widget — first **workspace-core widget**
(DESIGN_LANGUAGE.md §12.6) renders the SAME data the scheduling Focus
kanban core consumes, with a **deliberately abridged interactive
surface**. Bounded edits per §12.6a (mark hole-dug, drag delivery
between drivers, attach/detach ancillary, update single ETA);
finalize / day-switch / bulk reassignment remain Focus-only.

Mode-aware rendering per BRIDGEABLE_MASTER §5.2.2:
  • Production mode — vault is poured in-house. Reads Delivery rows
    where `delivery_type = "funeral_vault"` (or scheduling_type kanban
    convention) for the target date. Renders driver lanes + delivery
    cards.
  • Purchase mode — vault arrives from a supplier licensee via
    LicenseeTransfer. Reads incoming transfer rows where
    `area_tenant_id == this_tenant`. Renders calendar of expected
    receipts.
  • Hybrid mode — composes both (production lanes + purchase
    receipts stacked).

Tenant isolation: explicit `Company.id == user.company_id` filter at
every entry point. Cancelled deliveries excluded. Per Phase W-3a
canonical tenant-isolation discipline.

**Why Delivery is the canonical scheduling entity (not SalesOrder):**
Per the SalesOrder vs Delivery architectural investigation
(2026-04-27), ancillary items (urns, cremation trays, flowers) are
INDEPENDENT SalesOrders sold separately to the funeral home customer.
A funeral home ordering "1 vault + 1 urn + 1 tray" creates THREE
SalesOrders → THREE Deliveries. Driver assignment + scheduling lives
on Delivery because driver is a logistics concept, not a commercial
concept. The widget therefore consumes Delivery rows; the kanban card
enriches each row with SalesOrder context (deceased name, line items,
service location) at render time. See PLATFORM_ARCHITECTURE.md §9 +
BRIDGEABLE_MASTER §5.2 for the canonical entity distinction.

Per-instance config:
  • `target_date`: which date's schedule to show (default: tenant-
    local today). Future widget pinning of "next Tuesday's load"
    style configs lands here without service changes.

Empty state: returns mode + primary_navigation_target + empty arrays.
Frontend renders thoughtful empty-state copy with CTA to the
appropriate Focus.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.delivery import Delivery
from app.models.sales_order import SalesOrder
from app.models.user import User


# ── Mode resolution ─────────────────────────────────────────────────


VALID_MODES = ("production", "purchase", "hybrid")


def _resolve_operating_mode(db: Session, tenant_id: str) -> str | None:
    """Read `TenantProductLine(line_key="vault").config["operating_mode"]`.

    Returns one of "production" / "purchase" / "hybrid", or None when
    vault product line isn't enabled for the tenant. Defensive against
    legacy config shapes — falls back to "production" if config exists
    but `operating_mode` key is missing (matches the r60 backfill
    semantics where a present row without operating_mode means vault
    was activated but never explicitly mode-tagged).
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
    # Defensive: vault row exists but mode tag missing — treat as
    # production (the Sunnycrest demo default; matches r60 backfill).
    return "production"


def _local_today_for_tenant(db: Session, tenant_id: str) -> date:
    """Resolve "today" in the tenant's timezone — same logic the
    today widget uses. Tenant TZ resolution is the canonical pattern.
    """
    company = db.query(Company).filter(Company.id == tenant_id).first()
    tz_name = (
        getattr(company, "timezone", None) or "America/New_York"
        if company
        else "America/New_York"
    )
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("America/New_York")
    return datetime.now(tz).date()


# ── Production-mode reader ──────────────────────────────────────────


def _build_production_schedule(
    db: Session, tenant_id: str, target_date: date
) -> dict:
    """Read kanban Delivery rows for the target date and shape them
    into widget-consumption form.

    Each delivery is enriched with SalesOrder context (deceased,
    customer, service info) lazily — the kanban renders rich cards.
    Per §12.6 workspace-core canon, the widget reads identical data
    to the scheduling Focus core; the kanban is the source of truth.
    """
    # Active kanban + funeral_vault deliveries on target date.
    # scheduling_type IS NULL is treated as kanban per the model convention.
    deliveries: list[Delivery] = (
        db.query(Delivery)
        .filter(
            Delivery.company_id == tenant_id,
            Delivery.requested_date == target_date,
            or_(
                Delivery.scheduling_type.is_(None),
                Delivery.scheduling_type == "kanban",
            ),
            Delivery.status != "cancelled",
        )
        .order_by(
            Delivery.primary_assignee_id.asc().nullsfirst(),
            Delivery.driver_start_time.asc().nullslast(),
        )
        .all()
    )

    # Bulk-fetch SalesOrders for context (deceased, customer, etc.).
    order_ids = [d.order_id for d in deliveries if d.order_id]
    orders_by_id: dict[str, SalesOrder] = {}
    if order_ids:
        for o in (
            db.query(SalesOrder)
            .filter(
                SalesOrder.id.in_(order_ids),
                SalesOrder.company_id == tenant_id,  # defense-in-depth
            )
            .all()
        ):
            orders_by_id[o.id] = o

    # Bulk-fetch attached ancillaries (the "ride-along" relationship —
    # ancillary Delivery rows attached to a parent vault Delivery for
    # logistics, NOT commercially nested).
    parent_ids = [d.id for d in deliveries]
    attached_by_parent: dict[str, list[Delivery]] = {}
    if parent_ids:
        attached: list[Delivery] = (
            db.query(Delivery)
            .filter(
                Delivery.company_id == tenant_id,
                Delivery.attached_to_delivery_id.in_(parent_ids),
                Delivery.status != "cancelled",
            )
            .all()
        )
        for a in attached:
            attached_by_parent.setdefault(a.attached_to_delivery_id, []).append(a)

    rows: list[dict] = []
    for d in deliveries:
        order = orders_by_id.get(d.order_id) if d.order_id else None
        attached_count = len(attached_by_parent.get(d.id, []))
        rows.append(
            {
                "delivery_id": d.id,
                "order_id": d.order_id,
                "deceased_name": (
                    getattr(order, "deceased_name", None) if order else None
                ),
                "customer_id": d.customer_id,
                "primary_assignee_id": d.primary_assignee_id,
                "helper_user_id": d.helper_user_id,
                "status": d.status,
                "driver_start_time": (
                    d.driver_start_time.isoformat()
                    if d.driver_start_time
                    else None
                ),
                "service_time": (
                    getattr(order, "service_time", None).isoformat()
                    if order and getattr(order, "service_time", None)
                    else None
                ),
                "service_location": (
                    getattr(order, "service_location", None) if order else None
                ),
                "eta": (
                    getattr(order, "eta", None).isoformat()
                    if order and getattr(order, "eta", None)
                    else None
                ),
                "hole_dug_status": d.hole_dug_status,
                "delivery_address": d.delivery_address,
                "attached_ancillary_count": attached_count,
                "priority": d.priority,
            }
        )

    # Driver lane summary — per-driver counts for Brief variant.
    by_driver: dict[str | None, int] = {}
    for r in rows:
        key = r["primary_assignee_id"]
        by_driver[key] = by_driver.get(key, 0) + 1

    unassigned_count = by_driver.get(None, 0)
    assigned_count = sum(v for k, v in by_driver.items() if k is not None)
    driver_count = len([k for k in by_driver if k is not None])

    return {
        "deliveries": rows,
        "total_count": len(rows),
        "unassigned_count": unassigned_count,
        "assigned_count": assigned_count,
        "driver_count": driver_count,
    }


# ── Purchase-mode reader ────────────────────────────────────────────


def _build_purchase_schedule(
    db: Session, tenant_id: str, target_date: date
) -> dict:
    """Read incoming LicenseeTransfer rows where this tenant is the
    receiver (`area_tenant_id`). Purchase mode means vault is supplied
    from a partner licensee, not poured in-house.

    Shows transfers with a service_date in the target week (incoming
    POs typically span days, not single-date kanban). The widget's
    Brief variant shows the next 5 incoming; Detail shows the full
    week.
    """
    from datetime import timedelta

    from app.models.licensee_transfer import LicenseeTransfer

    # Window: target_date through +6 days. Transfers without
    # service_date are excluded (they're not yet scheduled).
    end_date = target_date + timedelta(days=7)

    transfers: list[LicenseeTransfer] = (
        db.query(LicenseeTransfer)
        .filter(
            LicenseeTransfer.area_tenant_id == tenant_id,
            LicenseeTransfer.service_date >= target_date,
            LicenseeTransfer.service_date < end_date,
            LicenseeTransfer.status.in_(
                ["pending", "accepted", "in_progress", "fulfilled"]
            ),
        )
        .order_by(LicenseeTransfer.service_date.asc())
        .all()
    )

    rows: list[dict] = []
    for t in transfers:
        rows.append(
            {
                "transfer_id": t.id,
                "transfer_number": t.transfer_number,
                "status": t.status,
                "service_date": (
                    t.service_date.isoformat() if t.service_date else None
                ),
                "deceased_name": t.deceased_name,
                "funeral_home_name": t.funeral_home_name,
                "cemetery_name": t.cemetery_name,
                "cemetery_city": t.cemetery_city,
                "cemetery_state": t.cemetery_state,
                "transfer_items": t.transfer_items,
                "home_tenant_id": t.home_tenant_id,  # supplier
            }
        )

    # By-status summary for Brief variant.
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    return {
        "transfers": rows,
        "total_count": len(rows),
        "by_status": by_status,
    }


# ── Public API ──────────────────────────────────────────────────────


def get_vault_schedule(
    db: Session,
    *,
    user: User,
    target_date: Optional[date] = None,
    tenant_id: Optional[str] = None,
) -> dict:
    """Return today's vault schedule for the user's tenant.

    Mode-aware: dispatches to production / purchase / hybrid based on
    `TenantProductLine(line_key="vault").config["operating_mode"]`.

    Response shape:
        {
          "date": "2026-04-27",
          "operating_mode": "production" | "purchase" | "hybrid" | null,
          "production": { deliveries: [...], total_count, unassigned_count, ... } | null,
          "purchase": { transfers: [...], total_count, ... } | null,
          "primary_navigation_target": "/dispatch" | "/dispatch/incoming" | null,
          "is_vault_enabled": bool
        }

    Empty states:
      • Tenant has no vault line enabled: `is_vault_enabled=false`,
        both branches null. Frontend renders empty state with CTA to
        product line settings.
      • Vault enabled but mode in production with zero deliveries:
        `production.total_count=0`, frontend shows "Nothing scheduled".
      • Hybrid mode: both branches populated (or both empty).
    """
    tid = tenant_id or user.company_id
    if not tid:
        return {
            "date": (target_date or date.today()).isoformat(),
            "operating_mode": None,
            "production": None,
            "purchase": None,
            "primary_navigation_target": None,
            "is_vault_enabled": False,
        }

    today = target_date or _local_today_for_tenant(db, tid)
    mode = _resolve_operating_mode(db, tid)

    if mode is None:
        return {
            "date": today.isoformat(),
            "operating_mode": None,
            "production": None,
            "purchase": None,
            "primary_navigation_target": None,
            "is_vault_enabled": False,
        }

    production_data: dict | None = None
    purchase_data: dict | None = None

    if mode in ("production", "hybrid"):
        production_data = _build_production_schedule(db, tid, today)
    if mode in ("purchase", "hybrid"):
        purchase_data = _build_purchase_schedule(db, tid, today)

    # Primary navigation target — production-mode tenants land on the
    # main dispatch board (kanban); purchase-mode tenants land on
    # incoming POs view. Hybrid defaults to dispatch (production
    # primary surface) — the widget itself surfaces both modes.
    if mode == "purchase":
        primary_target = "/licensee-transfers/incoming"
    else:
        primary_target = "/dispatch"

    return {
        "date": today.isoformat(),
        "operating_mode": mode,
        "production": production_data,
        "purchase": purchase_data,
        "primary_navigation_target": primary_target,
        "is_vault_enabled": True,
    }
