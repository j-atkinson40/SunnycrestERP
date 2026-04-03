"""AI Command Bar, Natural Language Filters, and Company Chat endpoints."""

import json
import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services import ai_settings_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class CommandRequest(BaseModel):
    query: str
    context: dict | None = None


class CommandExecuteRequest(BaseModel):
    action_type: str
    parameters: dict


class FilterParseRequest(BaseModel):
    query: str
    entity_type: str


class BriefingEnhanceRequest(BaseModel):
    briefing_data: dict


class CompanyChatRequest(BaseModel):
    master_company_id: str
    message: str
    conversation_history: list[dict] | None = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _call_claude(prompt: str, max_tokens: int = 300) -> str | None:
    """Call Claude API and return the text response."""
    try:
        from app.services.ai_service import call_anthropic
        return call_anthropic(prompt, max_tokens=max_tokens)
    except Exception:
        logger.exception("Claude API call failed")
        return None


# ── Command Bar ──────────────────────────────────────────────────────────────

@router.post("/command")
def process_command(
    data: CommandRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Process a command bar query using Claude AI."""
    if not ai_settings_service.is_enabled(db, current_user.company_id, "command_bar"):
        raise HTTPException(status_code=403, detail="Command bar is disabled")

    settings = ai_settings_service.get_effective_settings(db, current_user.company_id, current_user.id)
    action_tier = settings.get("command_bar_action_tier", "review")

    # Quick local routing for simple navigation
    nav_map = {
        "orders": "/ar/orders", "order station": "/order-station",
        "companies": "/crm/companies", "funeral homes": "/crm/funeral-homes",
        "contractors": "/crm/contractors", "legacy library": "/legacy/library",
        "legacy": "/legacy/library", "generator": "/legacy/generator",
        "invoices": "/ar/invoices/review", "scheduling": "/scheduling",
        "schedule": "/scheduling", "announcements": "/announcements",
        "settings": "/admin/settings", "users": "/admin/users",
        "employees": "/admin/users", "dashboard": "/dashboard",
        "inventory": "/inventory", "production": "/production-log",
        "safety": "/safety", "pipeline": "/crm/pipeline",
        "classification": "/admin/company-classification",
    }

    query_lower = data.query.strip().lower()

    # Direct navigation shortcuts
    for keyword, url in nav_map.items():
        if query_lower in (keyword, f"go to {keyword}", f"open {keyword}", f"show {keyword}"):
            return {
                "intent": "navigate",
                "display_text": f"Go to {keyword.title()}",
                "navigation_url": url,
                "results": None, "answer": None, "action": None,
            }

    # Quick search — if query is short and looks like a name
    if len(query_lower) >= 2 and not any(w in query_lower for w in ["log", "create", "when", "what", "how", "mark", "complete"]):
        from app.models.company_entity import CompanyEntity
        try:
            matches = (
                db.query(CompanyEntity)
                .filter(
                    CompanyEntity.company_id == current_user.company_id,
                    CompanyEntity.is_active == True,
                    CompanyEntity.name.ilike(f"%{data.query.strip()}%"),
                )
                .order_by(CompanyEntity.name)
                .limit(8)
                .all()
            )
            if matches:
                return {
                    "intent": "search",
                    "display_text": f"Found {len(matches)} companies",
                    "results": [
                        {"id": m.id, "name": m.name, "type": "company",
                         "url": f"/crm/companies/{m.id}",
                         "subtitle": f"{m.city}, {m.state}" if m.city else None}
                        for m in matches
                    ],
                    "navigation_url": None, "answer": None, "action": None,
                }
        except Exception:
            pass

    # For complex queries, use Claude
    prompt = f"""You are a command interpreter for a vault manufacturer's business platform called Bridgeable.

Classify this query and return JSON only:
{{
  "intent": "navigate"|"search"|"action"|"question",
  "display_text": "plain English description of what will happen",
  "navigation_url": "/path" or null,
  "action_type": "log_activity"|"complete_followup"|"create_order"|"navigate" or null,
  "parameters": {{}},
  "entity_name": "company name mentioned" or null
}}

Available pages: /ar/orders, /crm/companies, /crm/funeral-homes, /legacy/library, /scheduling, /announcements, /settings, /admin/users, /inventory, /production-log, /safety

User query: {data.query}
Current page: {(data.context or {}).get('current_page', 'unknown')}"""

    response = _call_claude(prompt, max_tokens=200)
    if not response:
        return {
            "intent": "search",
            "display_text": "Searching...",
            "results": [], "navigation_url": None, "answer": None, "action": None,
        }

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        return {
            "intent": "search", "display_text": response,
            "results": [], "navigation_url": None, "answer": None, "action": None,
        }

    intent = parsed.get("intent", "search")
    action = None

    if intent == "action":
        if action_tier == "view_only":
            return {
                "intent": "action",
                "display_text": "Action commands are disabled. Enable in AI Settings.",
                "results": None, "answer": None, "action": None, "navigation_url": None,
            }
        action = {
            "type": parsed.get("action_type"),
            "parameters": parsed.get("parameters", {}),
            "confirmation_required": action_tier == "review",
            "confirmation_text": parsed.get("display_text", ""),
        }
        if parsed.get("entity_name"):
            action["parameters"]["entity_name"] = parsed["entity_name"]

    return {
        "intent": intent,
        "display_text": parsed.get("display_text", ""),
        "navigation_url": parsed.get("navigation_url"),
        "results": None,
        "answer": parsed.get("answer") if intent == "question" else None,
        "action": action,
    }


@router.post("/command/execute")
def execute_command(
    data: CommandExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute a confirmed command bar action."""
    if not ai_settings_service.is_enabled(db, current_user.company_id, "command_bar"):
        raise HTTPException(status_code=403, detail="Command bar is disabled")

    if data.action_type == "log_activity":
        from app.services.crm.activity_log_service import log_manual_activity
        entity_name = data.parameters.get("entity_name", "")
        # Find company by name
        from app.models.company_entity import CompanyEntity
        company = db.query(CompanyEntity).filter(
            CompanyEntity.company_id == current_user.company_id,
            CompanyEntity.name.ilike(f"%{entity_name}%"),
        ).first()
        if company:
            entry = log_manual_activity(
                db, current_user.company_id, company.id,
                activity_type=data.parameters.get("activity_type", "call"),
                title=data.parameters.get("title", f"Call with {company.name}"),
                logged_by=current_user.id,
                body=data.parameters.get("notes"),
            )
            db.commit()
            return {"success": True, "message": f"Activity logged for {company.name}"}
        return {"success": False, "message": f"Could not find company: {entity_name}"}

    elif data.action_type == "complete_followup":
        from app.services.crm.activity_log_service import complete_followup
        activity_id = data.parameters.get("activity_id")
        if activity_id:
            complete_followup(db, activity_id, current_user.id)
            db.commit()
            return {"success": True, "message": "Follow-up completed"}
        return {"success": False, "message": "No activity ID provided"}

    return {"success": False, "message": f"Unknown action type: {data.action_type}"}


# ── Natural Language Filters ─────────────────────────────────────────────────

@router.post("/parse-filters")
def parse_filters(
    data: FilterParseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Parse natural language filter query into structured filters."""
    if not ai_settings_service.is_enabled(db, current_user.company_id, "natural_language_filters"):
        raise HTTPException(status_code=403, detail="Natural language filters are disabled")

    today = date.today().isoformat()
    prompt = f"""Parse this filter query for a {data.entity_type} list in a business platform.
Today is {today}.

Return JSON only with these fields (all optional, null if not specified):
{{
  "date_from": "YYYY-MM-DD" or null,
  "date_to": "YYYY-MM-DD" or null,
  "status": "string" or null,
  "customer_type": "funeral_home"|"contractor"|"cemetery"|etc or null,
  "amount_min": number or null,
  "amount_max": number or null,
  "search_text": "string" or null,
  "chips": ["human-readable label for each filter"]
}}

Examples:
"last month" → date_from: first of last month, date_to: last of last month
"over $2000" → amount_min: 2000
"funeral homes" → customer_type: "funeral_home"
"unpaid" → status: "unpaid"
"overdue" → status: "overdue"

Query: {data.query}"""

    response = _call_claude(prompt, max_tokens=200)
    if not response:
        return {"filters": {}, "chips": [], "error": "Could not parse filters"}

    try:
        parsed = json.loads(response)
        return {"filters": parsed, "chips": parsed.get("chips", [])}
    except json.JSONDecodeError:
        return {"filters": {}, "chips": [], "error": "Could not parse response"}


# ── Conversational Company Lookup ────────────────────────────────────────────

@router.post("/company-chat")
def company_chat(
    data: CompanyChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Answer questions about a specific company using its data."""
    if not ai_settings_service.is_enabled(db, current_user.company_id, "conversational_lookup"):
        raise HTTPException(status_code=403, detail="Conversational lookup is disabled")

    from app.models.company_entity import CompanyEntity
    from app.models.customer import Customer
    from app.models.contact import Contact

    entity = db.query(CompanyEntity).filter(CompanyEntity.id == data.master_company_id).first()
    if not entity:
        return {"answer": "Company not found.", "sources": []}

    # Build context from company data
    context_parts = [f"Company: {entity.name}"]
    if getattr(entity, "customer_type", None):
        context_parts.append(f"Type: {entity.customer_type}")
    if entity.city and entity.state:
        context_parts.append(f"Location: {entity.city}, {entity.state}")
    if entity.phone:
        context_parts.append(f"Phone: {entity.phone}")

    # Get customer stats
    customer = db.query(Customer).filter(Customer.master_company_id == data.master_company_id).first()
    if customer:
        context_parts.append(f"Account status: {customer.account_status}")
        context_parts.append(f"Current balance: ${float(customer.current_balance or 0):,.2f}")
        context_parts.append(f"Payment terms: {customer.payment_terms}")

        # Recent orders
        try:
            from sqlalchemy import text
            orders = db.execute(text("""
                SELECT number, total, created_at, status
                FROM sales_orders WHERE customer_id = :cid
                ORDER BY created_at DESC LIMIT 5
            """), {"cid": customer.id}).fetchall()
            if orders:
                order_lines = [f"Order #{o.number}: ${float(o.total):,.2f} ({o.status}, {o.created_at.strftime('%b %d')})" for o in orders]
                context_parts.append(f"Recent orders:\n" + "\n".join(order_lines))
        except Exception:
            pass

    # Get contacts
    contacts = db.query(Contact).filter(
        Contact.master_company_id == data.master_company_id,
        Contact.is_active == True,
    ).limit(5).all()
    if contacts:
        contact_lines = [f"{c.name} ({c.title or c.role or 'contact'}){' - PRIMARY' if c.is_primary else ''}" for c in contacts]
        context_parts.append(f"Contacts: {', '.join(contact_lines)}")

    # Get health data
    try:
        from app.models.manufacturer_company_profile import ManufacturerCompanyProfile
        profile = db.query(ManufacturerCompanyProfile).filter(
            ManufacturerCompanyProfile.master_company_id == data.master_company_id
        ).first()
        if profile:
            context_parts.append(f"Health score: {profile.health_score}")
            context_parts.append(f"Orders (12mo): {profile.order_count_12mo}")
            context_parts.append(f"Revenue (12mo): ${float(profile.total_revenue_12mo or 0):,.2f}")
            if profile.most_ordered_vault_name:
                context_parts.append(f"Most ordered: {profile.most_ordered_vault_name}")
            if profile.avg_days_to_pay_recent:
                context_parts.append(f"Avg payment time: {float(profile.avg_days_to_pay_recent):.0f} days")
    except Exception:
        pass

    context = "\n".join(context_parts)

    # Build conversation
    history = data.conversation_history or []
    history_text = ""
    for msg in history[-4:]:
        role = msg.get("role", "user")
        history_text += f"\n{role}: {msg.get('content', '')}"

    prompt = f"""You are answering questions about a specific company in a business CRM for a vault manufacturer.

Company data:
{context}

{f"Conversation so far:{history_text}" if history_text else ""}

Answer the user's question using only the data provided. Be concise — 1-3 sentences. If the data doesn't contain the answer, say so clearly.

User: {data.message}"""

    answer = _call_claude(prompt, max_tokens=200)
    if not answer:
        return {"answer": "Sorry, I couldn't process that question right now.", "sources": []}

    return {"answer": answer, "sources": []}


# ── Briefing Intelligence ────────────────────────────────────────────────────

@router.post("/briefing/enhance")
def enhance_briefing(
    data: BriefingEnhanceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate AI-enhanced briefing items: narrative, patterns, prep notes."""
    items = []
    tid = current_user.company_id

    # 1. Narrative
    try:
        from app.services.ai.briefing_intelligence import generate_narrative
        narrative = generate_narrative(db, tid, current_user.id, data.briefing_data)
        if narrative:
            items.append({
                "type": "ai_narrative",
                "priority": "info",
                "content": narrative,
            })
    except Exception:
        logger.exception("Narrative generation failed")

    # 2. Pattern alerts
    try:
        from app.services.ai.pattern_agent import get_unsurfaced_alerts, mark_surfaced
        alerts = get_unsurfaced_alerts(db, tid)
        alert_ids = []
        for alert in alerts:
            items.append({
                "type": "pattern_alert",
                "priority": "info",
                "title": "Something I noticed",
                "message": alert.description,
                "company_id": alert.master_company_id,
                "alert_id": alert.id,
                "action_url": f"/crm/companies/{alert.master_company_id}" if alert.master_company_id else None,
            })
            alert_ids.append(alert.id)
        if alert_ids:
            mark_surfaced(db, alert_ids)
    except Exception:
        logger.exception("Pattern alerts failed")

    # 3. Prep notes for today's follow-ups
    try:
        from app.services.ai.briefing_intelligence import generate_prep_note
        from app.models.activity_log import ActivityLog
        from datetime import date as _date

        followups = (
            db.query(ActivityLog)
            .filter(
                ActivityLog.tenant_id == tid,
                ActivityLog.follow_up_date == _date.today(),
                ActivityLog.follow_up_completed == False,
            )
            .limit(5)
            .all()
        )
        for fu in followups:
            if fu.master_company_id:
                note = generate_prep_note(db, tid, fu.master_company_id, fu.body)
                if note:
                    items.append({
                        "type": "prep_note",
                        "priority": "info",
                        "title": f"Prep: {fu.title or 'Follow-up'}",
                        "content": note,
                        "company_id": fu.master_company_id,
                    })
    except Exception:
        logger.exception("Prep notes failed")

    db.commit()
    return {"items": items}


@router.post("/pattern-alerts/{alert_id}/dismiss")
def dismiss_pattern_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dismiss a pattern alert so it doesn't appear again."""
    from app.services.ai.pattern_agent import dismiss_alert
    dismiss_alert(db, alert_id, current_user.id)
    db.commit()
    return {"dismissed": True}
