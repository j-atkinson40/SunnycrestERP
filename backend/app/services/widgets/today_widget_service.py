"""Today widget — vertical + product-line-aware "what's on today" summary.

Phase W-3a foundation widget. Cross-vertical + cross-line catalog
visibility (every tenant sees the widget); per-vertical-and-line
content rendering.

Per [DESIGN_LANGUAGE.md §12.10](../../../DESIGN_LANGUAGE.md) reference:
  • Glance variant: total count + date
  • Brief variant: 3-5 row breakdown by category, each row clickable

Canonical breakdown shapes per active tenant configuration:

  manufacturing + vault product line (Sunnycrest demo case)
    → "N vault deliveries today"
    → "N ancillary pool items waiting"
    → "N unscheduled" (deliveries without assignee)
  manufacturing + redi_rock / wastewater (future W-3d)
    → analogous shapes; this service stays line-aware so when
      additional lines activate, the breakdown grows naturally.
  funeral_home, cemetery, crematory (future W-3c+)
    → empty for W-3a Phase 1; per-vertical content lands when
      those verticals get widget builds.

Data sources (all tenant-scoped, idempotent reads — no writes):
  • Delivery (manufacturing+vault rows where requested_date = today)
  • Future: FHCase services, cemetery interment events, crematory
    case events.

Empty state contract: returns total_count=0 + empty categories list +
canonical date. Frontend renders thoughtful empty-state copy with a
helpful next-action affordance ("Nothing scheduled today" + link to
relevant primary work surface, e.g. /dispatch).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.delivery import Delivery
from app.models.user import User


# ── Today resolution ─────────────────────────────────────────────────


def _local_today_for_tenant(db: Session, tenant_id: str) -> date:
    """Resolve "today" in the tenant's timezone.

    Pre-canon some endpoints used UTC for "today" which gave wrong
    answers for tenants in non-UTC zones. This service reads
    `Company.timezone` (default `America/New_York` for Sunnycrest +
    most production tenants).
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


# ── Category builders (per vertical + product line) ──────────────────


def _build_manufacturing_vault_categories(
    db: Session, tenant_id: str, today: date
) -> tuple[int, list[dict]]:
    """Manufacturing tenant with vault product line activated.

    Returns (total_count, categories[]). Categories are surfaced in
    the Brief variant breakdown; total_count drives the Glance variant.

    Vault deliveries are tracked in the Delivery table (per the
    existing dispatch service). The widget treats kanban deliveries
    with `requested_date = today` as "today's vault deliveries" and
    ancillary deliveries in the unassigned pool as "ancillary pool
    items waiting" (the pool isn't strictly today-bounded, but the
    operator's mental model is "what's on my plate now").
    """
    # Kanban deliveries scheduled today.
    # scheduling_type IS NULL is treated as kanban per the model
    # convention — see Delivery.scheduling_type docstring.
    kanban_count = (
        db.query(func.count(Delivery.id))
        .filter(
            Delivery.company_id == tenant_id,
            Delivery.requested_date == today,
            or_(
                Delivery.scheduling_type.is_(None),
                Delivery.scheduling_type == "kanban",
            ),
            Delivery.status != "cancelled",
        )
        .scalar()
        or 0
    )

    # Ancillary pool items waiting (date-less + unassigned).
    # Per Delivery model docstring: pool = attached_to_delivery_id NULL
    # + primary_assignee_id NULL + requested_date NULL.
    ancillary_count = (
        db.query(func.count(Delivery.id))
        .filter(
            Delivery.company_id == tenant_id,
            Delivery.scheduling_type == "ancillary",
            Delivery.attached_to_delivery_id.is_(None),
            Delivery.primary_assignee_id.is_(None),
            Delivery.requested_date.is_(None),
            Delivery.status != "cancelled",
        )
        .scalar()
        or 0
    )

    # Unscheduled deliveries today — deliveries on the calendar but
    # without a primary assignee. This is the "needs attention" row;
    # surfaces missed scheduling work.
    unscheduled_count = (
        db.query(func.count(Delivery.id))
        .filter(
            Delivery.company_id == tenant_id,
            Delivery.requested_date == today,
            Delivery.primary_assignee_id.is_(None),
            or_(
                Delivery.scheduling_type.is_(None),
                Delivery.scheduling_type == "kanban",
            ),
            Delivery.status != "cancelled",
        )
        .scalar()
        or 0
    )

    categories: list[dict] = []
    if kanban_count > 0:
        categories.append(
            {
                "key": "vault_deliveries",
                "label": (
                    f"{kanban_count} vault delivery"
                    if kanban_count == 1
                    else f"{kanban_count} vault deliveries"
                ),
                "count": kanban_count,
                "navigation_target": "/dispatch",
            }
        )
    if ancillary_count > 0:
        categories.append(
            {
                "key": "ancillary_pool",
                "label": (
                    f"{ancillary_count} ancillary item waiting"
                    if ancillary_count == 1
                    else f"{ancillary_count} ancillary items waiting"
                ),
                "count": ancillary_count,
                "navigation_target": "/dispatch",
            }
        )
    if unscheduled_count > 0:
        categories.append(
            {
                "key": "unscheduled",
                "label": (
                    f"{unscheduled_count} unscheduled"
                    if unscheduled_count == 1
                    else f"{unscheduled_count} unscheduled"
                ),
                "count": unscheduled_count,
                "navigation_target": "/dispatch",
            }
        )

    # Glance total = primary work surface count (kanban + ancillary).
    # "Unscheduled" is a subset overlap with kanban; don't double-count.
    total_count = kanban_count + ancillary_count
    return total_count, categories


# ── Public API ───────────────────────────────────────────────────────


def get_today_summary(
    db: Session, *, user: User, tenant_id: Optional[str] = None
) -> dict:
    """Return today's work summary for the user's tenant.

    Response shape (matches frontend `TodayWidgetData`):
        {
          "date": "2026-04-27",
          "total_count": 8,
          "categories": [
            {
              "key": "vault_deliveries",
              "label": "5 vault deliveries",
              "count": 5,
              "navigation_target": "/dispatch"
            },
            ...
          ],
          "primary_navigation_target": "/dispatch"
        }

    Empty state: total_count=0, categories=[], primary_navigation_target
    points at the relevant primary work surface for the tenant's
    vertical (so the empty-state CTA "Nothing scheduled today, open
    Schedule →" lands somewhere useful).

    Per Phase W-3a Phase 1 scope: only manufacturing+vault tenants
    get a populated breakdown. Other verticals get the empty shape
    until W-3c/W-3d build their per-vertical content. This is a
    deliberate scope decision — the widget contract is line-aware,
    so future lines plug in via category-builder functions analogous
    to `_build_manufacturing_vault_categories`.
    """
    tid = tenant_id or user.company_id
    if not tid:
        return {
            "date": date.today().isoformat(),
            "total_count": 0,
            "categories": [],
            "primary_navigation_target": None,
        }

    today = _local_today_for_tenant(db, tid)

    # Resolve tenant context — vertical + active product lines.
    company = db.query(Company).filter(Company.id == tid).first()
    vertical = getattr(company, "vertical", None) if company else None

    # Active product lines (lazy import to avoid circular deps with
    # widget_service which already imports product_line stuff).
    try:
        from app.models.tenant_product_line import TenantProductLine

        enabled_lines = {
            row[0]
            for row in (
                db.query(TenantProductLine.line_key)
                .filter(
                    TenantProductLine.company_id == tid,
                    TenantProductLine.is_enabled.is_(True),
                )
                .all()
            )
        }
    except Exception:
        enabled_lines = set()

    total_count = 0
    categories: list[dict] = []
    primary_target = None

    if vertical == "manufacturing" and "vault" in enabled_lines:
        total_count, categories = _build_manufacturing_vault_categories(
            db, tid, today
        )
        primary_target = "/dispatch"
    elif vertical == "manufacturing":
        # Manufacturing tenant without vault — primary surface still
        # dispatch (other lines may be active in future W-3d).
        primary_target = "/dispatch"
    elif vertical == "funeral_home":
        # FH tenants land on /cases or /scheduling depending on role.
        # Dispatch still exists; /cases is the canonical primary.
        primary_target = "/cases"
    elif vertical == "cemetery":
        primary_target = "/interments"
    elif vertical == "crematory":
        primary_target = "/crematory/schedule"
    else:
        primary_target = "/dashboard"

    return {
        "date": today.isoformat(),
        "total_count": total_count,
        "categories": categories,
        "primary_navigation_target": primary_target,
    }
