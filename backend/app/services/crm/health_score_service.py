"""Health score service — calculate account health for funeral home customers."""

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.company_entity import CompanyEntity
from app.models.crm_settings import CrmSettings
from app.models.customer import Customer
from app.models.manufacturer_company_profile import ManufacturerCompanyProfile

logger = logging.getLogger(__name__)


def _get_or_create_settings(db: Session, tenant_id: str) -> CrmSettings:
    import uuid as _uuid
    settings = db.query(CrmSettings).filter(CrmSettings.company_id == tenant_id).first()
    if not settings:
        settings = CrmSettings(id=str(_uuid.uuid4()), company_id=tenant_id)
        db.add(settings)
        db.flush()
    return settings


def calculate_health_score(db: Session, master_company_id: str, tenant_id: str) -> str:
    """Calculate and update health score for one company. Returns the score."""
    profile = (
        db.query(ManufacturerCompanyProfile)
        .filter(ManufacturerCompanyProfile.master_company_id == master_company_id)
        .first()
    )
    if not profile:
        return "unknown"

    # Find linked customer
    entity = db.query(CompanyEntity).filter(CompanyEntity.id == master_company_id).first()
    if not entity:
        return "unknown"
    customer = db.query(Customer).filter(Customer.master_company_id == master_company_id).first()
    if not customer:
        profile.health_score = "unknown"
        profile.health_reasons = []
        profile.health_last_calculated = datetime.now(timezone.utc)
        return "unknown"

    customer_id = customer.id
    settings = _get_or_create_settings(db, tenant_id)
    reasons = []

    # ── Signal 1: Order recency ──────────────────────────────────────────
    try:
        from app.models.sales_order import SalesOrder

        # Order stats
        twelve_months_ago = text("now() - interval '12 months'")
        order_count_12mo = (
            db.query(func.count(SalesOrder.id))
            .filter(SalesOrder.customer_id == customer_id, SalesOrder.status != "cancelled", SalesOrder.created_at >= twelve_months_ago)
            .scalar() or 0
        )
        total_revenue_12mo = (
            db.query(func.sum(SalesOrder.total))
            .filter(SalesOrder.customer_id == customer_id, SalesOrder.status != "cancelled", SalesOrder.created_at >= twelve_months_ago)
            .scalar() or Decimal("0")
        )
        last_order_row = (
            db.query(func.max(SalesOrder.created_at))
            .filter(SalesOrder.customer_id == customer_id, SalesOrder.status != "cancelled")
            .scalar()
        )

        profile.order_count_12mo = order_count_12mo
        profile.total_revenue_12mo = total_revenue_12mo
        profile.last_order_date = last_order_row.date() if last_order_row else None

        # Average gap between orders
        avg_gap = None
        days_since_last = None
        if last_order_row:
            days_since_last = (datetime.now(timezone.utc) - last_order_row).days if last_order_row.tzinfo else None

        if order_count_12mo >= 3:
            gap_result = db.execute(text("""
                WITH order_gaps AS (
                    SELECT EXTRACT(DAY FROM created_at - LAG(created_at) OVER (ORDER BY created_at)) as gap_days
                    FROM sales_orders
                    WHERE customer_id = :cid AND status != 'cancelled'
                    AND created_at >= now() - interval '12 months'
                )
                SELECT AVG(gap_days) FROM order_gaps WHERE gap_days IS NOT NULL
            """), {"cid": customer_id}).scalar()
            avg_gap = float(gap_result) if gap_result else None

        profile.avg_days_between_orders = Decimal(str(round(avg_gap, 2))) if avg_gap else None

        multiplier = float(settings.at_risk_days_multiplier or 2.0)
        if avg_gap and avg_gap < 30 and days_since_last and days_since_last > avg_gap * multiplier:
            reasons.append(f"No order in {days_since_last} days (avg: every {avg_gap:.0f} days)")

    except Exception:
        logger.exception("Error computing order recency for %s", master_company_id)

    # ── Signal 2: Payment trend ──────────────────────────────────────────
    try:
        from app.models.invoice import Invoice

        recent_avg = db.execute(text("""
            SELECT AVG(EXTRACT(DAY FROM paid_at - invoice_date))
            FROM invoices WHERE customer_id = :cid AND paid_at IS NOT NULL
            AND invoice_date >= now() - interval '90 days'
        """), {"cid": customer_id}).scalar()

        prior_avg = db.execute(text("""
            SELECT AVG(EXTRACT(DAY FROM paid_at - invoice_date))
            FROM invoices WHERE customer_id = :cid AND paid_at IS NOT NULL
            AND invoice_date BETWEEN now() - interval '180 days' AND now() - interval '90 days'
        """), {"cid": customer_id}).scalar()

        profile.avg_days_to_pay_recent = Decimal(str(round(float(recent_avg), 2))) if recent_avg else None
        profile.avg_days_to_pay_prior = Decimal(str(round(float(prior_avg), 2))) if prior_avg else None

        trend_threshold = int(settings.at_risk_payment_trend_days or 7)
        payment_threshold = int(settings.at_risk_payment_threshold_days or 30)

        if recent_avg and prior_avg:
            r, p = float(recent_avg), float(prior_avg)
            if r > p + trend_threshold and r > payment_threshold:
                reasons.append(f"Payment time trending longer: now {r:.0f} days (was {p:.0f} days)")

    except Exception:
        logger.exception("Error computing payment trend for %s", master_company_id)

    # ── Determine score ──────────────────────────────────────────────────
    if profile.order_count_12mo == 0 and not profile.last_order_date:
        score = "unknown"
        reasons = []
    elif len(reasons) == 0:
        score = "healthy"
    elif len(reasons) == 1:
        score = "watch"
    else:
        score = "at_risk"

    profile.health_score = score
    profile.health_reasons = reasons
    profile.health_last_calculated = datetime.now(timezone.utc)

    return score


def recalculate_all(db: Session, tenant_id: str) -> int:
    """Recalculate health scores for all customer companies in a tenant."""
    settings = _get_or_create_settings(db, tenant_id)
    if not settings.health_scoring_enabled:
        return 0

    profiles = (
        db.query(ManufacturerCompanyProfile)
        .filter(ManufacturerCompanyProfile.company_id == tenant_id)
        .all()
    )
    count = 0
    for profile in profiles:
        try:
            calculate_health_score(db, profile.master_company_id, tenant_id)
            count += 1
        except Exception:
            logger.exception("Failed to calculate score for %s", profile.master_company_id)

    db.commit()
    logger.info("Health scores recalculated for %d companies in tenant %s", count, tenant_id)
    return count


def get_health_summary(db: Session, tenant_id: str) -> dict:
    """Return counts by health score for a tenant."""
    rows = (
        db.query(ManufacturerCompanyProfile.health_score, func.count(ManufacturerCompanyProfile.id))
        .filter(ManufacturerCompanyProfile.company_id == tenant_id)
        .group_by(ManufacturerCompanyProfile.health_score)
        .all()
    )
    summary = {"healthy": 0, "watch": 0, "at_risk": 0, "unknown": 0}
    for score, count in rows:
        if score in summary:
            summary[score] = count
    summary["total"] = sum(summary.values())
    return summary
