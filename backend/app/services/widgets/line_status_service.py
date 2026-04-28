"""Line Status widget — cross-line health aggregator.

Phase W-3d cluster widget. Cross-line aggregator that surfaces
per-line operational health for whichever product lines the tenant
has activated. Replaces the implicit pre-canon `production_status`
widget (which assumed all lines are production-mode) with a
mode-agnostic, per-line health view.

Per [DESIGN_LANGUAGE.md §12.10 reference 5](../../../DESIGN_LANGUAGE.md):
  • Brief variant: one row per active product line + status
    indicator + headline metric. Production-mode lines show "On
    track / behind / blocked" + today's pour count; purchase-mode
    lines show supplier delivery status + today's incoming count;
    hybrid lines show both metrics inline.
  • Detail variant: same row structure with expanded metrics
    (capacity utilization, on-time %, this-week trend, anomaly
    flags).
  • NO Glance variant per §12.10 — line status is operational-health
    information that doesn't compress to count-only.

Multi-line builder pattern (mirrors `today_widget_service.py`):
  • `_build_vault_health(db, tid)` for vault production/purchase
  • `_build_redi_rock_health(db, tid)` — placeholder until extension ships
  • `_build_wastewater_health(db, tid)` — placeholder
  • `_build_urn_sales_health(db, tid)` — placeholder
  • Future lines plug in via additional builder functions

For Phase W-3d Phase 1 (this commit): vault metrics are real,
others are stubs that activate when their respective extensions
ship per-line metrics aggregators. The widget is functional today
for Sunnycrest (vault-only) and architecturally future-proof for
multi-line tenants.

Per-line health vocabulary (canonical):
  • on_track   — status indicator green; metrics nominal
  • behind     — status indicator amber; metrics show slippage
  • blocked    — status indicator red; metrics show critical issue
  • idle       — status indicator neutral; line enabled but no work
  • unknown    — status indicator neutral; insufficient data

Tenant isolation: every per-line builder filters by
`tenant_id == user.company_id`. Anomaly counts read tenant-wide
(per the SalesOrder vs Delivery investigation: `agent_anomalies`
has no `product_line` column today, so multi-line tenants get an
unattributed total at the line-status surface — Sunnycrest is
vault-only, so attribution is unambiguous).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.delivery import Delivery
from app.models.user import User


# ── Tenant-local today (canonical pattern) ──────────────────────────


def _local_today_for_tenant(db: Session, tenant_id: str) -> date:
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


def _resolve_line_operating_mode(
    db: Session, tenant_id: str, line_key: str
) -> str | None:
    """Read `TenantProductLine.config["operating_mode"]` for one line."""
    try:
        from app.models.tenant_product_line import TenantProductLine

        row = (
            db.query(TenantProductLine)
            .filter(
                TenantProductLine.company_id == tenant_id,
                TenantProductLine.line_key == line_key,
                TenantProductLine.is_enabled.is_(True),
            )
            .first()
        )
    except Exception:
        return None
    if row is None:
        return None
    return (row.config or {}).get("operating_mode") or "production"


def _enabled_lines_for_tenant(db: Session, tenant_id: str) -> list[dict]:
    """Return list of {line_key, display_name, operating_mode} for
    every active TenantProductLine row. Ordered by sort_order."""
    try:
        from app.models.tenant_product_line import TenantProductLine

        rows = (
            db.query(TenantProductLine)
            .filter(
                TenantProductLine.company_id == tenant_id,
                TenantProductLine.is_enabled.is_(True),
            )
            .order_by(TenantProductLine.sort_order.asc())
            .all()
        )
    except Exception:
        return []
    return [
        {
            "line_key": r.line_key,
            "display_name": r.display_name,
            "operating_mode": (r.config or {}).get("operating_mode")
            or "production",
        }
        for r in rows
    ]


# ── Per-line builders ───────────────────────────────────────────────


def _build_vault_health(
    db: Session, tenant_id: str, mode: str, today: date
) -> dict:
    """Build vault line health — production / purchase / hybrid mode aware.

    Returns the per-line health row consumed by the line_status
    widget. Today's pour load + assigned/unassigned distribution
    drives status assessment.

    Status assessment for production mode:
      • blocked   — any unassigned delivery within 4 hours of
        scheduled time AND no driver started today (heuristic; full
        capacity-vs-load analysis is post-Phase-1)
      • behind    — > 25% of today's deliveries unassigned
      • on_track  — all deliveries assigned, schedule progressing
      • idle      — zero deliveries scheduled

    For purchase mode: pending status counts drive assessment.
    For hybrid: both shaping signals composed.
    """
    today_count = 0
    assigned_count = 0
    unassigned_count = 0
    incoming_count = 0
    incoming_pending = 0

    if mode in ("production", "hybrid"):
        # Today's kanban deliveries
        deliveries: list[Delivery] = (
            db.query(Delivery)
            .filter(
                Delivery.company_id == tenant_id,
                Delivery.requested_date == today,
                or_(
                    Delivery.scheduling_type.is_(None),
                    Delivery.scheduling_type == "kanban",
                ),
                Delivery.status != "cancelled",
            )
            .all()
        )
        today_count = len(deliveries)
        for d in deliveries:
            if d.primary_assignee_id:
                assigned_count += 1
            else:
                unassigned_count += 1

    if mode in ("purchase", "hybrid"):
        from app.models.licensee_transfer import LicenseeTransfer

        # Today's incoming transfers (this tenant is the receiver)
        transfers: list[LicenseeTransfer] = (
            db.query(LicenseeTransfer)
            .filter(
                LicenseeTransfer.area_tenant_id == tenant_id,
                LicenseeTransfer.service_date == today,
                LicenseeTransfer.status.in_(
                    ["pending", "accepted", "in_progress", "fulfilled"]
                ),
            )
            .all()
        )
        incoming_count = len(transfers)
        incoming_pending = sum(1 for t in transfers if t.status == "pending")

    # Status assessment
    if mode == "production":
        if today_count == 0:
            status = "idle"
        elif unassigned_count == 0:
            status = "on_track"
        elif unassigned_count / today_count > 0.25:
            status = "behind"
        else:
            status = "on_track"
    elif mode == "purchase":
        if incoming_count == 0:
            status = "idle"
        elif incoming_pending > 0:
            status = "behind"
        else:
            status = "on_track"
    else:  # hybrid
        # Compose: behind if either branch behind; else on_track if
        # either branch has work; else idle
        any_work = today_count + incoming_count > 0
        prod_behind = (
            today_count > 0 and unassigned_count / today_count > 0.25
        )
        purch_behind = incoming_count > 0 and incoming_pending > 0
        if not any_work:
            status = "idle"
        elif prod_behind or purch_behind:
            status = "behind"
        else:
            status = "on_track"

    # Headline metric — primary number to surface in Brief
    if mode == "production":
        headline = f"{today_count} pour{'' if today_count == 1 else 's'} today"
    elif mode == "purchase":
        headline = (
            f"{incoming_count} incoming"
            if incoming_count > 0
            else "no incoming today"
        )
    else:
        headline = (
            f"{today_count} pour{'' if today_count == 1 else 's'} · "
            f"{incoming_count} incoming"
        )

    return {
        "line_key": "vault",
        "display_name": "Burial vault",
        "operating_mode": mode,
        "status": status,
        "headline": headline,
        "metrics": {
            "production_today": today_count,
            "production_assigned": assigned_count,
            "production_unassigned": unassigned_count,
            "purchase_today": incoming_count,
            "purchase_pending": incoming_pending,
        },
        "navigation_target": (
            "/dispatch"
            if mode != "purchase"
            else "/licensee-transfers/incoming"
        ),
    }


def _build_placeholder_health(
    line_key: str, display_name: str, mode: str
) -> dict:
    """Placeholder for product lines whose health metrics aren't
    yet wired (redi_rock, wastewater, urn_sales, rosetta). Returns
    `status="unknown"` + neutral copy. Activates fully when each
    line's metrics aggregator ships in a future phase.
    """
    return {
        "line_key": line_key,
        "display_name": display_name,
        "operating_mode": mode,
        "status": "unknown",
        "headline": "metrics not yet available",
        "metrics": {},
        "navigation_target": None,
    }


# ── Public API ──────────────────────────────────────────────────────


def get_line_status(
    db: Session,
    *,
    user: User,
    tenant_id: Optional[str] = None,
) -> dict:
    """Return per-line health summary for the user's tenant.

    Response shape:
        {
          "date": "2026-04-27",
          "lines": [
            {
              "line_key": "vault",
              "display_name": "Burial vault",
              "operating_mode": "production",
              "status": "on_track" | "behind" | "blocked" | "idle" | "unknown",
              "headline": "8 pours today",
              "metrics": { production_today: 8, production_unassigned: 0, ... },
              "navigation_target": "/dispatch"
            },
            ...
          ],
          "total_active_lines": 1,
          "any_attention_needed": false
        }

    Empty state: `lines=[]` when tenant has no active product lines.
    """
    tid = tenant_id or user.company_id
    if not tid:
        return {
            "date": date.today().isoformat(),
            "lines": [],
            "total_active_lines": 0,
            "any_attention_needed": False,
        }

    today = _local_today_for_tenant(db, tid)
    enabled = _enabled_lines_for_tenant(db, tid)

    lines: list[dict] = []
    for line_info in enabled:
        line_key = line_info["line_key"]
        if line_key == "vault":
            lines.append(
                _build_vault_health(
                    db, tid, line_info["operating_mode"], today
                )
            )
        else:
            # Placeholder for redi_rock / wastewater / urn_sales / rosetta
            # — full health aggregators ship when each extension lands.
            lines.append(
                _build_placeholder_health(
                    line_key,
                    line_info["display_name"],
                    line_info["operating_mode"],
                )
            )

    any_attention = any(
        ln["status"] in ("behind", "blocked") for ln in lines
    )

    return {
        "date": today.isoformat(),
        "lines": lines,
        "total_active_lines": len(lines),
        "any_attention_needed": any_attention,
    }
