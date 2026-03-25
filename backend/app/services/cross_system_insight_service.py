"""Cross-system insight engine — detects patterns across modules."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.cross_system_intelligence import CrossSystemInsight

logger = logging.getLogger(__name__)


def _upsert_insight(db: Session, tenant_id: str, insight_key: str, entity_id: str | None, data: dict) -> CrossSystemInsight:
    """Upsert a cross-system insight — update if exists, create if not."""
    existing = (
        db.query(CrossSystemInsight)
        .filter(
            CrossSystemInsight.tenant_id == tenant_id,
            CrossSystemInsight.insight_key == insight_key,
            CrossSystemInsight.primary_entity_id == entity_id,
            CrossSystemInsight.status == "active",
        )
        .first()
    )
    if existing:
        existing.last_confirmed_at = datetime.now(timezone.utc)
        existing.headline = data.get("headline", existing.headline)
        existing.narrative = data.get("narrative", existing.narrative)
        db.commit()
        return existing

    insight = CrossSystemInsight(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        insight_key=insight_key,
        primary_entity_type=data.get("entity_type"),
        primary_entity_id=entity_id,
        connected_systems=data.get("connected_systems", []),
        headline=data["headline"],
        narrative=data["narrative"],
        severity=data.get("severity", "info"),
        primary_action_label=data.get("action_label"),
        primary_action_url=data.get("action_url"),
        secondary_action_label=data.get("secondary_action_label"),
        secondary_action_url=data.get("secondary_action_url"),
    )
    db.add(insight)
    db.commit()
    return insight


def detect_month_end_stack(db: Session, tenant_id: str) -> None:
    """Detect overlapping month-end obligations within 5 days of month end."""
    from datetime import date
    today = date.today()
    days_left = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1) - today).days if today.month < 12 else (today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1) - today).days

    if days_left > 5:
        # Not near month end — resolve if active
        existing = (
            db.query(CrossSystemInsight)
            .filter(
                CrossSystemInsight.tenant_id == tenant_id,
                CrossSystemInsight.insight_key == "month_end_stack",
                CrossSystemInsight.status == "active",
            )
            .first()
        )
        if existing:
            existing.status = "resolved"
            existing.auto_resolved = True
            existing.resolved_at = datetime.now(timezone.utc)
            db.commit()
        return

    pending = []
    # Check for pending month-end tasks (simplified checks)
    # In production these would query actual module status
    pending.append("Review month-end reconciliation")
    pending.append("Check accounting period status")

    if len(pending) >= 2:
        _upsert_insight(db, tenant_id, "month_end_stack", None, {
            "connected_systems": ["reconciliation", "periods", "statements"],
            "severity": "warning",
            "headline": f"{len(pending)} month-end tasks need attention in the next {days_left} days",
            "narrative": f"Month end is in {days_left} days. Pending: {', '.join(pending)}. Complete these before generating statements.",
            "action_label": "View financial board",
            "action_url": "/financials",
        })


def detect_all_insights(db: Session, tenant_id: str) -> int:
    """Run all cross-system insight detectors. Returns count of active insights."""
    detect_month_end_stack(db, tenant_id)
    # Additional detectors would be called here:
    # detect_overdue_customer_new_order(db, tenant_id)
    # detect_cost_pressure_vendor_signals(db, tenant_id)
    # detect_nsf_risk_with_pending_payment(db, tenant_id)
    # detect_transfer_pricing_stalled(db, tenant_id)
    # detect_relationship_declining_with_open_ar(db, tenant_id)
    # detect_vendor_concentration_risk(db, tenant_id)

    count = (
        db.query(CrossSystemInsight)
        .filter(CrossSystemInsight.tenant_id == tenant_id, CrossSystemInsight.status == "active")
        .count()
    )
    return count


def get_active_insights(db: Session, tenant_id: str) -> list[dict]:
    """Get all active cross-system insights for a tenant."""
    insights = (
        db.query(CrossSystemInsight)
        .filter(CrossSystemInsight.tenant_id == tenant_id, CrossSystemInsight.status == "active")
        .order_by(
            # critical first, then warning, then info
            desc(CrossSystemInsight.severity == "critical"),
            desc(CrossSystemInsight.severity == "warning"),
            desc(CrossSystemInsight.first_detected_at),
        )
        .all()
    )
    return [
        {
            "id": i.id,
            "insight_key": i.insight_key,
            "headline": i.headline,
            "narrative": i.narrative,
            "severity": i.severity,
            "connected_systems": i.connected_systems,
            "primary_action_label": i.primary_action_label,
            "primary_action_url": i.primary_action_url,
            "secondary_action_label": i.secondary_action_label,
            "secondary_action_url": i.secondary_action_url,
            "first_detected_at": i.first_detected_at.isoformat() if i.first_detected_at else None,
            "days_active": (datetime.now(timezone.utc) - i.first_detected_at).days if i.first_detected_at else 0,
        }
        for i in insights
    ]


def dismiss_insight(db: Session, insight_id: str) -> bool:
    i = db.query(CrossSystemInsight).filter(CrossSystemInsight.id == insight_id).first()
    if not i:
        return False
    i.status = "dismissed"
    i.resolved_at = datetime.now(timezone.utc)
    db.commit()
    return True
