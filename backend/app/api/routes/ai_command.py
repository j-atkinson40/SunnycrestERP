"""AI Command Bar, Natural Language Filters, and Company Chat endpoints."""

import json
import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import text
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


# ── Voice Memo ───────────────────────────────────────────────────────────────

@router.post("/voice-memo")
async def voice_memo(
    audio: UploadFile = File(...),
    master_company_id: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Process a voice memo: transcribe → extract → create activity."""
    if not ai_settings_service.is_enabled(db, current_user.company_id, "voice_memo", user_id=current_user.id):
        raise HTTPException(status_code=403, detail="Voice memo is disabled")

    audio_bytes = await audio.read()
    if len(audio_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Audio file too large (max 25MB)")

    content_type = audio.content_type or "audio/webm"

    from app.services.ai.voice_memo_service import process_voice_memo
    result = process_voice_memo(
        db, current_user.company_id, current_user.id,
        audio_bytes, master_company_id, content_type,
    )

    if "error" in result:
        return result  # Return 200 with error field (CORS-safe)

    db.commit()
    return result


# ── Voice Command ────────────────────────────────────────────────────────────

@router.post("/voice-command")
async def voice_command(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Process a voice command: transcribe → interpret as command."""
    if not ai_settings_service.is_enabled(db, current_user.company_id, "voice_commands", user_id=current_user.id):
        raise HTTPException(status_code=403, detail="Voice commands are disabled")

    audio_bytes = await audio.read()
    content_type = audio.content_type or "audio/webm"

    from app.services.ai.voice_memo_service import transcribe_audio
    transcript = transcribe_audio(audio_bytes, content_type)
    if not transcript:
        return {"error": True, "detail": "Could not transcribe audio"}

    ai_settings_service.track_usage(db, current_user.company_id, "transcription", 1)

    # Reuse command bar logic with the transcript
    cmd_data = CommandRequest(query=transcript, context={"current_page": "voice"})
    return process_command(cmd_data, current_user, db)


# ── Duplicate Reviews ────────────────────────────────────────────────────────

@router.get("/duplicates")
def list_duplicate_reviews(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List pending duplicate reviews with company details."""
    try:
        rows = db.execute(text("""
            SELECT dr.id, dr.similarity_score, dr.status,
                   a.id as a_id, a.name as a_name, a.city as a_city, a.state as a_state,
                   a.customer_type as a_type, a.is_customer as a_is_cust, a.is_vendor as a_is_vend, a.is_cemetery as a_is_cem,
                   b.id as b_id, b.name as b_name, b.city as b_city, b.state as b_state,
                   b.customer_type as b_type, b.is_customer as b_is_cust, b.is_vendor as b_is_vend, b.is_cemetery as b_is_cem
            FROM duplicate_reviews dr
            JOIN company_entities a ON dr.company_id_a = a.id
            JOIN company_entities b ON dr.company_id_b = b.id
            WHERE dr.tenant_id = :tid AND dr.status = 'pending'
            ORDER BY dr.similarity_score DESC
        """), {"tid": current_user.company_id}).fetchall()

        def _roles(r, prefix):
            roles = []
            if getattr(r, f"{prefix}_is_cust", False): roles.append("Customer")
            if getattr(r, f"{prefix}_is_vend", False): roles.append("Vendor")
            if getattr(r, f"{prefix}_is_cem", False): roles.append("Cemetery")
            return roles

        return [
            {
                "id": r.id,
                "similarity_score": float(r.similarity_score) if r.similarity_score else None,
                "status": r.status,
                "company_a": {"id": r.a_id, "name": r.a_name, "city": r.a_city, "state": r.a_state,
                              "customer_type": r.a_type, "roles": _roles(r, "a")},
                "company_b": {"id": r.b_id, "name": r.b_name, "city": r.b_city, "state": r.b_state,
                              "customer_type": r.b_type, "roles": _roles(r, "b")},
            }
            for r in rows
        ]
    except Exception:
        return []


@router.post("/duplicates/{review_id}/resolve")
def resolve_duplicate(
    review_id: str,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resolve a duplicate review — merge or mark as not duplicate."""
    action = data.get("action", "not_duplicate")
    now = datetime.now(timezone.utc)

    if action == "undo":
        db.execute(text(
            "UPDATE duplicate_reviews SET status = 'pending', resolved_by = NULL, resolved_at = NULL WHERE id = :id"
        ), {"id": review_id})
    elif action == "merge":
        db.execute(text(
            "UPDATE duplicate_reviews SET status = 'merged', resolved_by = :uid, resolved_at = :now WHERE id = :id"
        ), {"id": review_id, "uid": current_user.id, "now": now})
    else:
        db.execute(text(
            "UPDATE duplicate_reviews SET status = 'not_duplicate', resolved_by = :uid, resolved_at = :now WHERE id = :id"
        ), {"id": review_id, "uid": current_user.id, "now": now})

    db.commit()
    return {"resolved": True, "action": action}


# ── Agent Management ─────────────────────────────────────────────────────────

@router.get("/agents/run-nightly")
def run_nightly_agents_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger nightly AI agents for current tenant."""
    from app.services.ai.agent_orchestrator import run_nightly_agents
    try:
        results = run_nightly_agents(db, current_user.company_id)
        return results
    except Exception as e:
        return {"error": True, "detail": str(e)}


@router.get("/agents/runs")
def get_agent_runs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get recent agent run history."""
    try:
        rows = db.execute(text(
            "SELECT agent_name, started_at, completed_at, status, records_processed, results_summary, error_message "
            "FROM ai_agent_runs WHERE tenant_id = :tid ORDER BY started_at DESC LIMIT 20"
        ), {"tid": current_user.company_id}).fetchall()
        return [
            {
                "agent_name": r.agent_name,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "status": r.status,
                "records_processed": r.records_processed,
                "results_summary": r.results_summary,
                "error_message": r.error_message,
            }
            for r in rows
        ]
    except Exception:
        return []


# ── Name Suggestions ─────────────────────────────────────────────────────────

@router.get("/name-suggestions")
def list_name_suggestions(status: str = "pending", page: int = 1, per_page: int = 20, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.ai_name_suggestion import AiNameSuggestion
    from app.models.company_entity import CompanyEntity
    try:
        query = db.query(AiNameSuggestion, CompanyEntity).join(CompanyEntity, AiNameSuggestion.master_company_id == CompanyEntity.id).filter(AiNameSuggestion.tenant_id == current_user.company_id, AiNameSuggestion.status == status).order_by(AiNameSuggestion.confidence.desc())
        total = query.count()
        items = query.offset((page - 1) * per_page).limit(per_page).all()
        def _etype(e):
            ct = getattr(e, "customer_type", None)
            if ct: return ct
            if getattr(e, "is_cemetery", False): return "cemetery"
            if getattr(e, "is_funeral_home", False): return "funeral_home"
            return None
        return {"items": [{"id": s.id, "current_name": s.current_name, "suggested_name": s.suggested_name, "confidence": float(s.confidence) if s.confidence else None, "suggestion_source": s.suggestion_source, "suggested_phone": s.suggested_phone, "suggested_website": s.suggested_website, "suggested_address_line1": s.suggested_address_line1, "company_id": e.id, "customer_type": _etype(e), "city": e.city, "state": e.state} for s, e in items], "total": total, "page": page, "pages": (total + per_page - 1) // per_page}
    except Exception:
        db.rollback()
        return {"items": [], "total": 0, "page": 1, "pages": 0}

@router.get("/name-suggestions/summary")
def name_suggestions_summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        from app.models.ai_name_suggestion import AiNameSuggestion
        return {"pending": db.query(AiNameSuggestion).filter(AiNameSuggestion.tenant_id == current_user.company_id, AiNameSuggestion.status == "pending").count()}
    except Exception:
        db.rollback()
        return {"pending": 0}

@router.post("/name-suggestions/{sid}/apply")
def apply_name_suggestion(sid: str, data: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.ai_name_suggestion import AiNameSuggestion
    from app.models.company_entity import CompanyEntity
    s = db.query(AiNameSuggestion).filter(AiNameSuggestion.id == sid).first()
    if not s: raise HTTPException(status_code=404, detail="Not found")
    entity = db.query(CompanyEntity).filter(CompanyEntity.id == s.master_company_id).first()
    if not entity: raise HTTPException(status_code=404, detail="Company not found")
    new_name = data.get("name", s.suggested_name)
    entity.name = new_name
    if data.get("apply_address") and s.suggested_address_line1: entity.address_line1 = s.suggested_address_line1
    if data.get("apply_phone") and s.suggested_phone and not entity.phone: entity.phone = s.suggested_phone
    if data.get("apply_website") and s.suggested_website and not entity.website: entity.website = s.suggested_website
    s.status = "applied"; s.reviewed_by = current_user.id; s.reviewed_at = datetime.now(timezone.utc); s.applied_name = new_name
    db.commit()
    return {"applied": True, "name": new_name}

@router.post("/name-suggestions/{sid}/reject")
def reject_name_suggestion(sid: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.ai_name_suggestion import AiNameSuggestion
    s = db.query(AiNameSuggestion).filter(AiNameSuggestion.id == sid).first()
    if not s: raise HTTPException(status_code=404, detail="Not found")
    s.status = "rejected"; s.reviewed_by = current_user.id; s.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return {"rejected": True}

@router.post("/name-suggestions/apply-bulk")
def apply_bulk_suggestions(data: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.ai_name_suggestion import AiNameSuggestion
    from app.models.company_entity import CompanyEntity
    applied = 0
    for sid in data.get("suggestion_ids", []):
        s = db.query(AiNameSuggestion).filter(AiNameSuggestion.id == sid, AiNameSuggestion.status == "pending").first()
        if s and s.suggested_name:
            entity = db.query(CompanyEntity).filter(CompanyEntity.id == s.master_company_id).first()
            if entity:
                entity.name = s.suggested_name
                if s.suggested_phone and not entity.phone: entity.phone = s.suggested_phone
                if s.suggested_website and not entity.website: entity.website = s.suggested_website
                s.status = "applied"; s.reviewed_by = current_user.id; s.reviewed_at = datetime.now(timezone.utc); s.applied_name = s.suggested_name
                applied += 1
    db.commit()
    return {"applied": applied}

@router.get("/name-enrichment/run")
def run_name_enrichment_endpoint(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.ai.name_enrichment_agent import run_name_enrichment
    try:
        return run_name_enrichment(db, current_user.company_id)
    except Exception as e:
        db.rollback()
        return {"error": True, "detail": str(e)}
