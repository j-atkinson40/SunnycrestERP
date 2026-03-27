"""Training content generation service.

Generates procedure documents and curriculum tracks via Claude API.
Content is saved with tenant_id = NULL (shared across all manufacturing tenants).
"""

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Generator

import anthropic

from app.config import settings
from app.models.training import TrainingCurriculumTrack, TrainingProcedure
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

AI_MODEL = "claude-sonnet-4-20250514"

# ---------------------------------------------------------------------------
# Procedure definitions — 24 procedures for manufacturing vertical
# ---------------------------------------------------------------------------

PROCEDURE_DEFINITIONS = [
    # Standard accounting & operations procedures
    {"key": "month_end_close", "title": "Month-End Close Process", "roles": ["accounting", "manager"], "category": "accounting", "sort_order": 10},
    {"key": "new_funeral_home_setup", "title": "Setting Up a New Funeral Home Charge Account", "roles": ["accounting", "inside_sales"], "category": "sales", "sort_order": 20},
    {"key": "payment_application", "title": "Applying Customer Payments", "roles": ["accounting"], "category": "accounting", "sort_order": 30},
    {"key": "vendor_invoice_discrepancy", "title": "Handling a Vendor Invoice Discrepancy", "roles": ["accounting", "operations"], "category": "accounting", "sort_order": 40},
    {"key": "collections_workflow", "title": "Managing Overdue Accounts", "roles": ["accounting", "manager"], "category": "accounting", "sort_order": 50},
    {"key": "finance_charge_review", "title": "Monthly Finance Charge Review", "roles": ["accounting"], "category": "accounting", "sort_order": 60},
    {"key": "bank_reconciliation", "title": "Monthly Bank Reconciliation", "roles": ["accounting"], "category": "accounting", "sort_order": 70},
    {"key": "new_funeral_order", "title": "Processing a New Funeral Order", "roles": ["inside_sales", "operations"], "category": "operations", "sort_order": 80},
    {"key": "out_of_area_transfer", "title": "Handling an Out-of-Area Funeral Transfer", "roles": ["inside_sales", "operations", "accounting"], "category": "operations", "sort_order": 90},
    {"key": "po_to_receiving", "title": "Purchase Order to Receiving Workflow", "roles": ["operations", "accounting"], "category": "operations", "sort_order": 100},
    {"key": "early_payment_discount", "title": "Processing Early Payment Discounts", "roles": ["accounting"], "category": "accounting", "sort_order": 110},
    {"key": "customer_credit_hold", "title": "Placing and Releasing a Customer Credit Hold", "roles": ["accounting", "manager"], "category": "accounting", "sort_order": 120},
    {"key": "audit_package_generation", "title": "Generating an Audit Package", "roles": ["accounting", "manager"], "category": "accounting", "sort_order": 130},
    {"key": "new_vendor_setup", "title": "Setting Up a New Vendor", "roles": ["accounting", "operations"], "category": "accounting", "sort_order": 140},
    {"key": "statement_generation", "title": "Running Month-End Statements", "roles": ["accounting"], "category": "accounting", "sort_order": 150},
    # AI workflow procedures
    {"key": "reviewing_collections_draft", "title": "How to Review and Send a Collections Email Draft", "roles": ["accounting", "manager"], "category": "ai_workflows", "sort_order": 200},
    {"key": "resolving_payment_match", "title": "Resolving an Unmatched Payment Suggestion", "roles": ["accounting"], "category": "ai_workflows", "sort_order": 210},
    {"key": "handling_po_discrepancy", "title": "Investigating a PO Match Discrepancy", "roles": ["accounting", "operations"], "category": "ai_workflows", "sort_order": 220},
    {"key": "approving_transfer_pricing", "title": "Reviewing and Approving Transfer Pricing", "roles": ["inside_sales", "manager"], "category": "ai_workflows", "sort_order": 230},
    {"key": "acting_on_delivery_conflict", "title": "What to Do When a Delivery Conflict is Flagged", "roles": ["operations", "manager"], "category": "ai_workflows", "sort_order": 240},
    {"key": "reading_financial_health", "title": "How to Read and Act on Your Financial Health Score", "roles": ["accounting", "manager", "owner"], "category": "ai_workflows", "sort_order": 250},
    {"key": "using_insights_page", "title": "Working with Behavioral Insights", "roles": ["accounting", "manager", "owner"], "category": "ai_workflows", "sort_order": 260},
    {"key": "overriding_agent_suggestion", "title": "When and How to Override an Agent Suggestion", "roles": ["accounting", "inside_sales", "operations", "manager"], "category": "ai_workflows", "sort_order": 270},
    {"key": "dismissing_vs_acting", "title": "Dismissing an Alert vs Taking Action", "roles": ["accounting", "inside_sales", "operations"], "category": "ai_workflows", "sort_order": 280},
]

CURRICULUM_ROLES = ["accounting", "inside_sales", "operations"]

# ---------------------------------------------------------------------------
# System prompt for procedure generation
# ---------------------------------------------------------------------------

PROCEDURE_SYSTEM_PROMPT = """You are generating training content for employees at a Wilbert burial vault manufacturing company using the Bridgeable business management platform.

The company manufactures concrete burial vaults and sells them to funeral homes on charge accounts. Funeral homes order throughout the month and receive a consolidated monthly statement. The company also handles cross-licensee transfers (shipping vaults to other Wilbert licensees in other territories).

Bridgeable platform navigation conventions:
- Financials Board → [zone name] (e.g., Financials Board → AR Zone)
- AR Command Center → [tab name] (e.g., AR Command Center → Aging tab)
- AP Command Center → [tab name]
- Operations Board → [zone name]
- Settings → [section name]

Generate a detailed procedure document. Write for new employees who are unfamiliar with the business. Explain WHY each step matters, not just what to do. Be specific about platform navigation paths.

Return JSON only — no markdown, no preamble:
{
  "overview": "string (2-3 paragraphs: business context, why this procedure exists, what goes wrong without it)",
  "steps": [
    {
      "step_number": 1,
      "title": "string (action-oriented title)",
      "instruction": "string (clear, specific instruction)",
      "platform_path": "string (exact navigation path, e.g. 'AR Command Center → Aging tab → Customer row → Apply Payment')",
      "why_this_matters": "string (consequence of skipping or doing wrong)",
      "common_mistakes": ["string", "string"]
    }
  ],
  "related_procedure_keys": ["string"]
}"""

CURRICULUM_SYSTEM_PROMPT = """You are generating a 4-week onboarding curriculum for a new employee at a Wilbert burial vault manufacturing company using the Bridgeable platform.

The platform has these core modules: AR management, AP and purchasing, monthly statement billing, finance charges, bank reconciliation, journal entries, financial reports, funeral order management, cross-licensee transfers, and driver/delivery management.

The company sells burial vaults to funeral homes on charge accounts with monthly statement billing. Net 30 payment terms. Finance charges apply to overdue accounts. Cross-licensee transfers happen when a funeral home in another territory needs a vault.

Bridgeable has an AI assistant that proactively flags issues (overdue accounts, payment mismatches, PO discrepancies). Employees review AI suggestions before anything is sent or posted.

Create 12-16 modules across 4 weeks. Each module teaches one specific business process. Write for someone with basic computer skills but no prior industry experience. The first module must be ai_orientation about working with the AI assistant.

Return JSON only:
{
  "track_name": "string",
  "description": "string (2-3 sentences)",
  "estimated_weeks": 4,
  "modules": [
    {
      "week": 1,
      "module_key": "string (snake_case, unique within track)",
      "title": "string",
      "description": "string (one sentence)",
      "concept_explanation": "string (2-3 paragraphs explaining the business concept and why it matters)",
      "guided_task": {
        "instruction": "string",
        "platform_action": "string (specific navigation path and action)",
        "success_criteria": "string (how employee knows they did it right)"
      },
      "comprehension_check": {
        "question": "string",
        "options": ["string", "string", "string", "string"],
        "correct_index": 0,
        "explanation": "string (why that answer is correct)"
      },
      "estimated_minutes": 20
    }
  ]
}"""

# ---------------------------------------------------------------------------
# Claude caller — direct, no HTTPException, returns (result, error)
# ---------------------------------------------------------------------------


def _call_claude(system_prompt: str, user_message: str, max_tokens: int = 3000) -> tuple[dict | None, str | None]:
    """Call Claude API directly. Returns (parsed_dict, None) or (None, error_message)."""
    if not settings.ANTHROPIC_API_KEY:
        return None, "ANTHROPIC_API_KEY not configured"
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=AI_MODEL,
            max_tokens=max_tokens,
            system=system_prompt + "\n\nIMPORTANT: Respond with valid JSON only. No markdown, no code fences.",
            messages=[{"role": "user", "content": user_message}],
        )
        text = message.content[0].text.strip()
        # Strip code fences if Claude adds them anyway
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, f"JSON parse error: {e}"
    except Exception as e:
        return None, str(e)


# ---------------------------------------------------------------------------
# Procedure generation
# ---------------------------------------------------------------------------


def _shared_procedure_exists(db: Session, procedure_key: str) -> bool:
    return db.query(TrainingProcedure).filter(
        TrainingProcedure.tenant_id.is_(None),
        TrainingProcedure.procedure_key == procedure_key,
    ).first() is not None


def generate_procedures(db: Session, force: bool = False) -> Generator[dict, None, None]:
    """Generate all procedures and yield progress events."""
    total = len(PROCEDURE_DEFINITIONS)
    yield {"type": "section_start", "section": "procedures", "total": total}

    created = 0
    errors = []

    for i, defn in enumerate(PROCEDURE_DEFINITIONS, 1):
        key = defn["key"]
        title = defn["title"]

        if not force and _shared_procedure_exists(db, key):
            yield {"type": "progress", "section": "procedures", "index": i, "total": total, "item": key, "status": "skipped"}
            continue

        yield {"type": "progress", "section": "procedures", "index": i, "total": total, "item": key, "status": "generating"}

        user_msg = f"Generate a complete procedure document for: {title}\nRoles: {', '.join(defn['roles'])}\nCategory: {defn['category']}"
        result, error = _call_claude(PROCEDURE_SYSTEM_PROMPT, user_msg, max_tokens=3000)

        if error or not result:
            errors.append(f"{key}: {error}")
            yield {"type": "progress", "section": "procedures", "index": i, "total": total, "item": key, "status": "error", "error": error}
            continue

        now = datetime.now(timezone.utc)

        # Upsert
        existing = db.query(TrainingProcedure).filter(
            TrainingProcedure.tenant_id.is_(None),
            TrainingProcedure.procedure_key == key,
        ).first()

        if existing:
            existing.title = title
            existing.applicable_roles = defn["roles"]
            existing.category = defn["category"]
            existing.overview = result.get("overview", "")
            existing.steps = result.get("steps", [])
            existing.related_procedure_keys = result.get("related_procedure_keys", [])
            existing.content_generated = True
            existing.content_generated_at = now
            existing.sort_order = defn["sort_order"]
        else:
            proc = TrainingProcedure(
                id=str(uuid.uuid4()),
                tenant_id=None,
                procedure_key=key,
                title=title,
                applicable_roles=defn["roles"],
                category=defn["category"],
                overview=result.get("overview", ""),
                steps=result.get("steps", []),
                related_procedure_keys=result.get("related_procedure_keys", []),
                content_generated=True,
                content_generated_at=now,
                sort_order=defn["sort_order"],
            )
            db.add(proc)

        db.commit()
        created += 1
        yield {"type": "progress", "section": "procedures", "index": i, "total": total, "item": key, "status": "done"}

    yield {"type": "section_complete", "section": "procedures", "created": created, "errors": errors}


# ---------------------------------------------------------------------------
# Curriculum track generation
# ---------------------------------------------------------------------------


def _shared_track_exists(db: Session, role: str) -> bool:
    return db.query(TrainingCurriculumTrack).filter(
        TrainingCurriculumTrack.tenant_id.is_(None),
        TrainingCurriculumTrack.training_role == role,
    ).first() is not None


def generate_curriculum_tracks(db: Session, force: bool = False) -> Generator[dict, None, None]:
    """Generate curriculum tracks for all 3 roles and yield progress events."""
    total = len(CURRICULUM_ROLES)
    yield {"type": "section_start", "section": "curriculum_tracks", "total": total}

    created = 0
    errors = []

    for i, role in enumerate(CURRICULUM_ROLES, 1):
        if not force and _shared_track_exists(db, role):
            yield {"type": "progress", "section": "curriculum_tracks", "index": i, "total": total, "item": role, "status": "skipped"}
            continue

        yield {"type": "progress", "section": "curriculum_tracks", "index": i, "total": total, "item": role, "status": "generating"}

        role_labels = {"accounting": "Accounting", "inside_sales": "Inside Sales / Customer Service", "operations": "Operations / Production"}
        user_msg = f"Generate a complete 4-week onboarding curriculum for a new {role_labels.get(role, role)} employee. The first module must be ai_orientation covering: what the AI assistant does, the difference between agent alerts and human decisions, confidence scores, and why human judgment always overrides agent suggestions."

        result, error = _call_claude(CURRICULUM_SYSTEM_PROMPT, user_msg, max_tokens=5000)

        if error or not result:
            errors.append(f"{role}: {error}")
            yield {"type": "progress", "section": "curriculum_tracks", "index": i, "total": total, "item": role, "status": "error", "error": error}
            continue

        now = datetime.now(timezone.utc)
        modules = result.get("modules", [])
        total_modules = len(modules)

        existing = db.query(TrainingCurriculumTrack).filter(
            TrainingCurriculumTrack.tenant_id.is_(None),
            TrainingCurriculumTrack.training_role == role,
        ).first()

        if existing:
            existing.track_name = result.get("track_name", f"{role_labels.get(role, role)} Onboarding")
            existing.description = result.get("description", "")
            existing.modules = modules
            existing.total_modules = total_modules
            existing.estimated_weeks = result.get("estimated_weeks", 4)
            existing.content_generated = True
            existing.content_generated_at = now
        else:
            track = TrainingCurriculumTrack(
                id=str(uuid.uuid4()),
                tenant_id=None,
                training_role=role,
                track_name=result.get("track_name", f"{role_labels.get(role, role)} Onboarding"),
                description=result.get("description", ""),
                modules=modules,
                total_modules=total_modules,
                estimated_weeks=result.get("estimated_weeks", 4),
                content_generated=True,
                content_generated_at=now,
            )
            db.add(track)

        db.commit()
        created += 1
        yield {"type": "progress", "section": "curriculum_tracks", "index": i, "total": total, "item": role, "status": "done"}

    yield {"type": "section_complete", "section": "curriculum_tracks", "created": created, "errors": errors}


# ---------------------------------------------------------------------------
# Top-level: generate all content
# ---------------------------------------------------------------------------


def generate_all_content(db: Session, force: bool = False) -> Generator[dict, None, None]:
    """Generate procedures and curriculum tracks. Yields newline-delimited JSON progress events."""
    yield {"type": "start", "procedures_total": len(PROCEDURE_DEFINITIONS), "tracks_total": len(CURRICULUM_ROLES)}

    proc_errors: list[str] = []
    proc_created = 0
    track_errors: list[str] = []
    track_created = 0

    for event in generate_procedures(db, force=force):
        if event.get("type") == "section_complete":
            proc_created = event.get("created", 0)
            proc_errors = event.get("errors", [])
        yield event

    for event in generate_curriculum_tracks(db, force=force):
        if event.get("type") == "section_complete":
            track_created = event.get("created", 0)
            track_errors = event.get("errors", [])
        yield event

    yield {
        "type": "complete",
        "procedures_created": proc_created,
        "tracks_created": track_created,
        "errors": proc_errors + track_errors,
    }


# ---------------------------------------------------------------------------
# Status check
# ---------------------------------------------------------------------------


def get_content_status(db: Session) -> dict:
    from sqlalchemy import func
    procedures = db.query(func.count(TrainingProcedure.id)).filter(TrainingProcedure.tenant_id.is_(None)).scalar() or 0
    tracks = db.query(func.count(TrainingCurriculumTrack.id)).filter(TrainingCurriculumTrack.tenant_id.is_(None)).scalar() or 0
    return {
        "shared_procedures": procedures,
        "shared_curriculum_tracks": tracks,
        "has_shared_content": procedures > 0,
        "procedures_expected": len(PROCEDURE_DEFINITIONS),
        "tracks_expected": len(CURRICULUM_ROLES),
    }
