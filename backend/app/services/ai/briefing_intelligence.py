"""Briefing intelligence — narrative generation, prep notes, weekly summary.

Phase 2c-4 migration: each function calls the Intelligence layer directly
with a dedicated managed prompt_key. The shared _call_claude helper was
deleted as part of this migration.
"""

import logging
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import ai_settings_service

logger = logging.getLogger(__name__)


def generate_narrative(
    db: Session,
    tenant_id: str,
    user_id: str,
    briefing_data: dict,
) -> str | None:
    """Generate AI-written morning briefing narrative."""
    if not ai_settings_service.is_enabled(db, tenant_id, "briefing_narrative", user_id=user_id):
        return None

    settings = ai_settings_service.get_effective_settings(db, tenant_id, user_id)
    tone = settings.get("briefing_narrative_tone", "concise")

    from app.models.user import User
    user = db.query(User).filter(User.id == user_id).first()
    user_name = user.first_name if user else "there"

    from app.models.company import Company
    company = db.query(Company).filter(Company.id == tenant_id).first()
    company_name = company.name if company else "your company"

    today_str = date.today().strftime("%A, %B %d")
    orders_count = briefing_data.get("today_count", 0)
    legacy_count = briefing_data.get("legacy_proofs_pending_review", 0)
    followup_count = briefing_data.get("crm_today_followups", 0)
    overdue_count = briefing_data.get("crm_overdue_followups", 0)
    at_risk_count = len(briefing_data.get("crm_at_risk_accounts", []))
    tone_instruction = "2-3 sentences max." if tone == "concise" else "4-6 sentences, more detail."

    try:
        from app.services.intelligence import intelligence_service

        result = intelligence_service.execute(
            db,
            prompt_key="briefing.generate_narrative",
            variables={
                "user_name": user_name,
                "company_name": company_name,
                "tone_instruction": tone_instruction,
                "today_str": today_str,
                "orders_count": orders_count,
                "legacy_count": legacy_count,
                "followup_count": followup_count,
                "overdue_count": overdue_count,
                "at_risk_count": at_risk_count,
            },
            company_id=tenant_id,
            caller_module="briefing_intelligence.generate_narrative",
            caller_entity_type="user",
            caller_entity_id=user_id,
        )
        if result.status == "success":
            return result.response_text
    except Exception:
        logger.exception("Narrative generation failed")
    return None


def generate_prep_note(
    db: Session,
    tenant_id: str,
    master_company_id: str,
    activity_context: str | None = None,
) -> str | None:
    """Generate pre-call prep note for a scheduled follow-up."""
    if not ai_settings_service.is_enabled(db, tenant_id, "prep_notes"):
        return None

    from app.models.company_entity import CompanyEntity
    from app.models.customer import Customer

    entity = db.query(CompanyEntity).filter(CompanyEntity.id == master_company_id).first()
    if not entity:
        return None

    context_parts = [f"Company: {entity.name}"]
    if entity.city:
        context_parts.append(f"Location: {entity.city}, {entity.state}")

    customer = db.query(Customer).filter(Customer.master_company_id == master_company_id).first()
    if customer:
        context_parts.append(f"Balance: ${float(customer.current_balance or 0):,.2f}")
        context_parts.append(f"Payment terms: {customer.payment_terms}")

    try:
        if customer:
            orders = db.execute(text("""
                SELECT number, total, created_at FROM sales_orders
                WHERE customer_id = :cid ORDER BY created_at DESC LIMIT 3
            """), {"cid": customer.id}).fetchall()
            if orders:
                order_lines = [
                    f"#{o.number}: ${float(o.total):,.2f} ({o.created_at.strftime('%b %d')})"
                    for o in orders
                ]
                context_parts.append(f"Recent orders: {', '.join(order_lines)}")
    except Exception:
        pass

    try:
        from app.models.manufacturer_company_profile import ManufacturerCompanyProfile
        profile = db.query(ManufacturerCompanyProfile).filter(
            ManufacturerCompanyProfile.master_company_id == master_company_id
        ).first()
        if profile:
            context_parts.append(f"Health: {profile.health_score}")
            if profile.avg_days_to_pay_recent:
                context_parts.append(f"Avg payment: {float(profile.avg_days_to_pay_recent):.0f} days")
    except Exception:
        pass

    context = "\n".join(context_parts)
    activity_context_block = (
        f"Last interaction context: {activity_context}" if activity_context else ""
    )

    try:
        from app.services.intelligence import intelligence_service

        result = intelligence_service.execute(
            db,
            prompt_key="briefing.generate_prep_note",
            variables={
                "entity_name": entity.name,
                "activity_context_block": activity_context_block,
                "context": context,
            },
            company_id=tenant_id,
            caller_module="briefing_intelligence.generate_prep_note",
            caller_entity_type="company_entity",
            caller_entity_id=master_company_id,
        )
        if result.status == "success":
            return result.response_text
    except Exception:
        logger.exception("Prep note generation failed")
    return None


def generate_weekly_summary(db: Session, tenant_id: str, user_id: str | None = None) -> dict | None:
    """Generate weekly business summary."""
    if not ai_settings_service.is_enabled(db, tenant_id, "weekly_summary"):
        return None

    try:
        this_week = db.execute(text("""
            SELECT COUNT(*) as orders, COALESCE(SUM(total), 0) as revenue
            FROM sales_orders
            WHERE company_id = :tid AND status != 'cancelled'
            AND created_at >= now() - interval '7 days'
        """), {"tid": tenant_id}).fetchone()

        last_week = db.execute(text("""
            SELECT COUNT(*) as orders, COALESCE(SUM(total), 0) as revenue
            FROM sales_orders
            WHERE company_id = :tid AND status != 'cancelled'
            AND created_at BETWEEN now() - interval '14 days' AND now() - interval '7 days'
        """), {"tid": tenant_id}).fetchone()

        if not this_week:
            return None

        from app.services.intelligence import intelligence_service

        result = intelligence_service.execute(
            db,
            prompt_key="briefing.generate_weekly_summary",
            variables={
                "this_week_orders": this_week.orders,
                "this_week_revenue": f"{float(this_week.revenue):,.0f}",
                "last_week_orders": last_week.orders if last_week else 0,
                "last_week_revenue": f"{float(last_week.revenue if last_week else 0):,.0f}",
            },
            company_id=tenant_id,
            caller_module="briefing_intelligence.generate_weekly_summary",
            caller_entity_type="user" if user_id else None,
            caller_entity_id=user_id,
        )
        summary_text = result.response_text if result.status == "success" else None
        if not summary_text:
            return None

        return {
            "type": "weekly_summary",
            "priority": "info",
            "title": "Last week summary",
            "content": summary_text,
            "data": {
                "revenue": float(this_week.revenue),
                "orders": this_week.orders,
                "revenue_prior": float(last_week.revenue) if last_week else 0,
                "orders_prior": last_week.orders if last_week else 0,
            },
        }
    except Exception:
        logger.exception("Weekly summary generation failed")
        return None
