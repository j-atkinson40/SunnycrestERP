"""Pattern recognition agent — detects unusual order/payment patterns."""

import logging
import uuid as _uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.ai_pattern_alert import AiPatternAlert
from app.services import ai_settings_service

logger = logging.getLogger(__name__)

SENSITIVITY_THRESHOLDS = {
    "conservative": Decimal("0.85"),
    "moderate": Decimal("0.70"),
    "aggressive": Decimal("0.55"),
}


def detect_patterns(db: Session, tenant_id: str) -> list[dict]:
    """Detect unusual patterns in order/payment data. Returns new alerts."""
    if not ai_settings_service.is_enabled(db, tenant_id, "pattern_alerts"):
        return []

    settings = ai_settings_service.get_settings(db, tenant_id)
    sensitivity = getattr(settings, "pattern_alerts_sensitivity", "moderate")
    threshold = SENSITIVITY_THRESHOLDS.get(sensitivity, Decimal("0.70"))

    alerts: list[dict] = []

    try:
        alerts.extend(_detect_missed_orders(db, tenant_id, threshold))
    except Exception:
        logger.exception("Error detecting missed orders")

    try:
        alerts.extend(_detect_unusual_order_size(db, tenant_id, threshold))
    except Exception:
        logger.exception("Error detecting unusual order sizes")

    try:
        alerts.extend(_detect_volume_trends(db, tenant_id, threshold))
    except Exception:
        logger.exception("Error detecting volume trends")

    # Persist new alerts
    for alert in alerts:
        if alert.get("confidence", 0) >= float(threshold):
            existing = db.query(AiPatternAlert).filter(
                AiPatternAlert.tenant_id == tenant_id,
                AiPatternAlert.pattern_type == alert["pattern_type"],
                AiPatternAlert.master_company_id == alert.get("master_company_id"),
                AiPatternAlert.dismissed == False,
                AiPatternAlert.surfaced_in_briefing == False,
            ).first()
            if not existing:
                db.add(AiPatternAlert(
                    id=str(_uuid.uuid4()),
                    tenant_id=tenant_id,
                    pattern_type=alert["pattern_type"],
                    master_company_id=alert.get("master_company_id"),
                    description=alert["description"],
                    confidence=Decimal(str(alert.get("confidence", 0.7))),
                ))

    db.flush()
    return alerts


def get_unsurfaced_alerts(db: Session, tenant_id: str) -> list[AiPatternAlert]:
    """Get pattern alerts not yet shown in briefing."""
    return (
        db.query(AiPatternAlert)
        .filter(
            AiPatternAlert.tenant_id == tenant_id,
            AiPatternAlert.surfaced_in_briefing == False,
            AiPatternAlert.dismissed == False,
        )
        .order_by(AiPatternAlert.confidence.desc())
        .limit(5)
        .all()
    )


def mark_surfaced(db: Session, alert_ids: list[str]) -> None:
    """Mark alerts as surfaced in briefing."""
    now = datetime.now(timezone.utc)
    for aid in alert_ids:
        db.query(AiPatternAlert).filter(AiPatternAlert.id == aid).update({
            "surfaced_in_briefing": True, "surfaced_at": now,
        })


def dismiss_alert(db: Session, alert_id: str, user_id: str) -> None:
    """Dismiss a pattern alert."""
    db.query(AiPatternAlert).filter(AiPatternAlert.id == alert_id).update({
        "dismissed": True,
        "dismissed_by": user_id,
        "dismissed_at": datetime.now(timezone.utc),
    })


# ── Pattern detectors ────────────────────────────────────────────────────────

def _detect_missed_orders(db: Session, tenant_id: str, threshold: Decimal) -> list[dict]:
    """Detect customers who missed their usual ordering day."""
    alerts = []
    try:
        # Find customers with consistent ordering patterns (3+ orders on same DOW)
        rows = db.execute(text("""
            WITH customer_patterns AS (
                SELECT
                    so.customer_id,
                    c.master_company_id,
                    ce.name as company_name,
                    EXTRACT(DOW FROM so.created_at) as order_dow,
                    COUNT(*) as freq
                FROM sales_orders so
                JOIN customers c ON so.customer_id = c.id
                JOIN company_entities ce ON c.master_company_id = ce.id
                WHERE so.company_id = :tid
                AND so.status != 'cancelled'
                AND so.created_at >= now() - interval '3 months'
                AND c.master_company_id IS NOT NULL
                GROUP BY so.customer_id, c.master_company_id, ce.name, EXTRACT(DOW FROM so.created_at)
                HAVING COUNT(*) >= 3
            ),
            last_orders AS (
                SELECT customer_id, MAX(created_at) as last_order
                FROM sales_orders WHERE company_id = :tid AND status != 'cancelled'
                GROUP BY customer_id
            )
            SELECT cp.company_name, cp.master_company_id, cp.order_dow, cp.freq,
                   EXTRACT(DAY FROM now() - lo.last_order) as days_since
            FROM customer_patterns cp
            JOIN last_orders lo ON cp.customer_id = lo.customer_id
            WHERE EXTRACT(DAY FROM now() - lo.last_order) > 7
            ORDER BY cp.freq DESC
            LIMIT 5
        """), {"tid": tenant_id}).fetchall()

        dow_names = {0: "Sunday", 1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday"}

        for row in rows:
            day_name = dow_names.get(int(row.order_dow), "their usual day")
            alerts.append({
                "pattern_type": "missed_usual_order",
                "master_company_id": row.master_company_id,
                "description": f"{row.company_name} usually orders on {day_name}s ({int(row.freq)} times in 3 months). No order in {int(row.days_since)} days.",
                "confidence": min(0.9, 0.6 + (row.freq * 0.05)),
            })
    except Exception:
        logger.exception("Missed order pattern detection failed")

    return alerts


def _detect_unusual_order_size(db: Session, tenant_id: str, threshold: Decimal) -> list[dict]:
    """Detect orders significantly larger or smaller than customer's average."""
    alerts = []
    try:
        rows = db.execute(text("""
            WITH customer_avgs AS (
                SELECT customer_id, AVG(total) as avg_total, COUNT(*) as order_count
                FROM sales_orders
                WHERE company_id = :tid AND status != 'cancelled'
                AND created_at >= now() - interval '6 months'
                GROUP BY customer_id HAVING COUNT(*) >= 5
            ),
            recent AS (
                SELECT so.customer_id, so.total, so.number, so.created_at,
                       c.master_company_id, ce.name as company_name
                FROM sales_orders so
                JOIN customers c ON so.customer_id = c.id
                JOIN company_entities ce ON c.master_company_id = ce.id
                WHERE so.company_id = :tid AND so.status != 'cancelled'
                AND so.created_at >= now() - interval '7 days'
                AND c.master_company_id IS NOT NULL
            )
            SELECT r.company_name, r.master_company_id, r.total, r.number,
                   ca.avg_total, r.total / ca.avg_total as ratio
            FROM recent r
            JOIN customer_avgs ca ON r.customer_id = ca.customer_id
            WHERE r.total > ca.avg_total * 2 OR r.total < ca.avg_total * 0.3
            LIMIT 5
        """), {"tid": tenant_id}).fetchall()

        for row in rows:
            ratio = float(row.ratio)
            if ratio > 2:
                alerts.append({
                    "pattern_type": "large_order",
                    "master_company_id": row.master_company_id,
                    "description": f"{row.company_name} placed an unusually large order (${float(row.total):,.0f} vs avg ${float(row.avg_total):,.0f}). May indicate a big project.",
                    "confidence": 0.75,
                })
            elif ratio < 0.3:
                alerts.append({
                    "pattern_type": "small_order",
                    "master_company_id": row.master_company_id,
                    "description": f"{row.company_name} placed a much smaller order than usual (${float(row.total):,.0f} vs avg ${float(row.avg_total):,.0f}). Worth checking in.",
                    "confidence": 0.65,
                })
    except Exception:
        logger.exception("Unusual order size detection failed")

    return alerts


def _detect_volume_trends(db: Session, tenant_id: str, threshold: Decimal) -> list[dict]:
    """Detect significant volume changes vs same period last year."""
    alerts = []
    try:
        rows = db.execute(text("""
            WITH this_month AS (
                SELECT so.customer_id, c.master_company_id, ce.name as company_name,
                       COUNT(*) as orders
                FROM sales_orders so
                JOIN customers c ON so.customer_id = c.id
                JOIN company_entities ce ON c.master_company_id = ce.id
                WHERE so.company_id = :tid AND so.status != 'cancelled'
                AND so.created_at >= now() - interval '30 days'
                AND c.master_company_id IS NOT NULL
                GROUP BY so.customer_id, c.master_company_id, ce.name
                HAVING COUNT(*) >= 2
            ),
            last_year AS (
                SELECT customer_id, COUNT(*) as orders
                FROM sales_orders
                WHERE company_id = :tid AND status != 'cancelled'
                AND created_at BETWEEN now() - interval '395 days' AND now() - interval '365 days'
                GROUP BY customer_id
            )
            SELECT tm.company_name, tm.master_company_id, tm.orders as current_orders,
                   COALESCE(ly.orders, 0) as prior_orders
            FROM this_month tm
            LEFT JOIN last_year ly ON tm.customer_id = ly.customer_id
            WHERE ly.orders IS NOT NULL AND ly.orders > 0
            AND (tm.orders::float / ly.orders < 0.75 OR tm.orders::float / ly.orders > 1.5)
            LIMIT 5
        """), {"tid": tenant_id}).fetchall()

        for row in rows:
            if row.prior_orders > 0:
                pct = ((row.current_orders - row.prior_orders) / row.prior_orders) * 100
                if pct < -25:
                    alerts.append({
                        "pattern_type": "volume_down",
                        "master_company_id": row.master_company_id,
                        "description": f"{row.company_name}'s orders are down {abs(pct):.0f}% vs this time last year ({row.current_orders} vs {row.prior_orders}).",
                        "confidence": 0.70,
                    })
                elif pct > 50:
                    alerts.append({
                        "pattern_type": "volume_up",
                        "master_company_id": row.master_company_id,
                        "description": f"{row.company_name}'s orders are up {pct:.0f}% vs last year — possible growth opportunity.",
                        "confidence": 0.75,
                    })
    except Exception:
        logger.exception("Volume trend detection failed")

    return alerts
