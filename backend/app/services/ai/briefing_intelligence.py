"""Briefing intelligence — narrative generation, prep notes, weekly summary."""

import json
import logging
from datetime import date, datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import ai_settings_service

logger = logging.getLogger(__name__)


def _call_claude(prompt: str, max_tokens: int = 300) -> str | None:
    try:
        from app.services.ai_service import call_anthropic
        return call_anthropic(prompt, max_tokens=max_tokens)
    except Exception:
        logger.exception("Claude API call failed")
        return None


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

    # Get user name
    from app.models.user import User
    user = db.query(User).filter(User.id == user_id).first()
    user_name = user.first_name if user else "there"

    # Get tenant name
    from app.models.company import Company
    company = db.query(Company).filter(Company.id == tenant_id).first()
    company_name = company.name if company else "your company"

    today_str = date.today().strftime("%A, %B %d")

    # Extract counts from briefing data
    orders_count = briefing_data.get("today_count", 0)
    legacy_count = briefing_data.get("legacy_proofs_pending_review", 0)
    followup_count = briefing_data.get("crm_today_followups", 0)
    overdue_count = briefing_data.get("crm_overdue_followups", 0)
    at_risk_count = len(briefing_data.get("crm_at_risk_accounts", []))

    tone_instruction = "2-3 sentences max." if tone == "concise" else "4-6 sentences, more detail."

    prompt = f"""You are writing a morning briefing narrative for {user_name}, who manages {company_name}, a precast concrete manufacturer.

Write in second person. Be direct and specific. Prioritize urgent items. Sound like a knowledgeable assistant, not a robot.
Tone: {tone_instruction}

Today is {today_str}.

Data:
- Services/deliveries today: {orders_count}
- Legacy proofs pending review: {legacy_count}
- Follow-ups due today: {followup_count}
- Overdue follow-ups: {overdue_count}
- At-risk accounts: {at_risk_count}

Write the narrative. Include what looks good AND what needs attention. Do not list everything — focus on what matters most."""

    return _call_claude(prompt, max_tokens=200)


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

    # Recent orders
    try:
        if customer:
            orders = db.execute(text("""
                SELECT number, total, created_at FROM sales_orders
                WHERE customer_id = :cid ORDER BY created_at DESC LIMIT 3
            """), {"cid": customer.id}).fetchall()
            if orders:
                order_lines = [f"#{o.number}: ${float(o.total):,.2f} ({o.created_at.strftime('%b %d')})" for o in orders]
                context_parts.append(f"Recent orders: {', '.join(order_lines)}")
    except Exception:
        pass

    # Health
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

    prompt = f"""Generate a brief pre-call prep note for a call with {entity.name}.

{f"Last interaction context: {activity_context}" if activity_context else ""}

Current data:
{context}

Provide:
1. Quick situation summary (1 sentence)
2. Key things to address (2-3 bullets)
3. Any issues to watch (1-2 bullets if relevant)

Be specific. Use actual data."""

    return _call_claude(prompt, max_tokens=200)


def generate_weekly_summary(db: Session, tenant_id: str) -> dict | None:
    """Generate weekly business summary."""
    if not ai_settings_service.is_enabled(db, tenant_id, "weekly_summary"):
        return None

    try:
        # This week vs last week
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

        prompt = f"""Write a weekly business summary for a precast concrete manufacturer. Be specific with numbers. Note trends (up/down). Under 100 words.

This week: {this_week.orders} orders, ${float(this_week.revenue):,.0f} revenue
Last week: {last_week.orders if last_week else 0} orders, ${float(last_week.revenue if last_week else 0):,.0f} revenue

Summarize performance and note any trends."""

        summary_text = _call_claude(prompt, max_tokens=150)
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
