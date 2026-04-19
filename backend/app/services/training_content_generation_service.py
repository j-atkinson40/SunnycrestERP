"""Training content generation service.

Phase 2c-2 migration: routes through two managed Intelligence prompts —
`training.generate_procedure` (per-procedure) and `training.generate_curriculum_track`
(per-role). Content is saved with tenant_id = NULL (shared across all
manufacturing tenants), so Intelligence calls also use company_id=None.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Generator

from sqlalchemy.orm import Session

from app.config import settings
from app.models.training import TrainingCurriculumTrack, TrainingProcedure

logger = logging.getLogger(__name__)

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
    {"key": "taking_a_funeral_order", "title": "Taking a Funeral Order — Phone to Saved in 30 Seconds", "roles": ["inside_sales", "operations", "manager"], "category": "sales", "sort_order": 85, "user_msg": "Write a procedure for taking a funeral order by phone at a Wilbert burial vault manufacturing company using Bridgeable.\n\nThe procedure should feel like a cheat sheet for someone on the phone with a funeral home director.\n\nCover:\n- Opening the order station\n- Selecting a quick order template vs starting fresh (when to use each)\n- Selecting the funeral home (type first 3 letters)\n- Understanding the cemetery shortlist (why their common cemeteries appear)\n- What happens when a cemetery is selected (equipment auto-fills, county auto-fills)\n- Setting the service date\n- What to do if the vault or equipment is unusual (override the template)\n- Saving the order\n- What NOT to do: don't create an invoice manually, it happens automatically tonight\n- The AI shorthand trick for speed\n\nAlso cover:\n- What to do when the funeral home isn't in the system yet: type their name → select '+ Add [name] as new funeral home' → they are created instantly with a monthly statement charge account → complete their profile from Customers later\n- The platform will alert you weekly about any customers created this way that still need their profiles completed\n\nInclude a 'quick reference' step at the end that summarizes the entire flow in 5 bullet points — something they could tape next to their monitor.\n\nWHY this matters: Every order that gets entered while the funeral home is still on the phone is one that doesn't get lost on a sticky note or forgotten in the afternoon rush."},
    {"key": "out_of_area_transfer", "title": "Handling an Out-of-Area Funeral Transfer", "roles": ["inside_sales", "operations", "accounting"], "category": "operations", "sort_order": 90},
    {"key": "po_to_receiving", "title": "Purchase Order to Receiving Workflow", "roles": ["operations", "accounting"], "category": "operations", "sort_order": 100},
    {"key": "early_payment_discount", "title": "Processing Early Payment Discounts", "roles": ["accounting"], "category": "accounting", "sort_order": 110},
    {"key": "customer_credit_hold", "title": "Placing and Releasing a Customer Credit Hold", "roles": ["accounting", "manager"], "category": "accounting", "sort_order": 120},
    {"key": "audit_package_generation", "title": "Generating an Audit Package", "roles": ["accounting", "manager"], "category": "accounting", "sort_order": 130},
    {"key": "new_vendor_setup", "title": "Setting Up a New Vendor", "roles": ["accounting", "operations"], "category": "accounting", "sort_order": 140},
    {"key": "statement_generation", "title": "Running Month-End Statements", "roles": ["accounting"], "category": "accounting", "sort_order": 150},
    {"key": "morning_invoice_review", "title": "Morning Invoice Review and Approval", "roles": ["accounting", "manager"], "category": "accounting", "sort_order": 160},
    # AI workflow procedures
    {"key": "reviewing_collections_draft", "title": "How to Review and Send a Collections Email Draft", "roles": ["accounting", "manager"], "category": "ai_workflows", "sort_order": 200},
    {"key": "acting_on_draft_invoice_alerts", "title": "Acting on Draft Invoice Alerts from the Morning Briefing", "roles": ["accounting", "manager"], "category": "ai_workflows", "sort_order": 205},
    {"key": "resolving_payment_match", "title": "Resolving an Unmatched Payment Suggestion", "roles": ["accounting"], "category": "ai_workflows", "sort_order": 210},
    {"key": "handling_po_discrepancy", "title": "Investigating a PO Match Discrepancy", "roles": ["accounting", "operations"], "category": "ai_workflows", "sort_order": 220},
    {"key": "approving_transfer_pricing", "title": "Reviewing and Approving Transfer Pricing", "roles": ["inside_sales", "manager"], "category": "ai_workflows", "sort_order": 230},
    {"key": "acting_on_delivery_conflict", "title": "What to Do When a Delivery Conflict is Flagged", "roles": ["operations", "manager"], "category": "ai_workflows", "sort_order": 240},
    {"key": "reading_financial_health", "title": "How to Read and Act on Your Financial Health Score", "roles": ["accounting", "manager", "owner"], "category": "ai_workflows", "sort_order": 250},
    {"key": "using_insights_page", "title": "Working with Behavioral Insights", "roles": ["accounting", "manager", "owner"], "category": "ai_workflows", "sort_order": 260},
    {"key": "overriding_agent_suggestion", "title": "When and How to Override an Agent Suggestion", "roles": ["accounting", "inside_sales", "operations", "manager"], "category": "ai_workflows", "sort_order": 270},
    {"key": "dismissing_vs_acting", "title": "Dismissing an Alert vs Taking Action", "roles": ["accounting", "inside_sales", "operations"], "category": "ai_workflows", "sort_order": 280},
    {
        "key": "managing_cemeteries",
        "title": "Managing Your Cemetery List",
        "roles": ["inside_sales", "operations", "manager"],
        "category": "operations",
        "sort_order": 88,
        "user_msg": (
            "Write a procedure for managing the cemetery list at a Wilbert burial vault manufacturing company using Bridgeable.\n\n"
            "Cover:\n"
            "- Where to find the cemetery list (Customers → Cemeteries tab)\n"
            "- How to add a new cemetery manually from the customer list\n"
            "- How to configure equipment settings on a cemetery record (what each flag means)\n"
            "- What the equipment prefill does on new orders — explain that when a funeral home selects a cemetery "
            "that provides its own lowering device, the lowering device charge is automatically removed from the order\n"
            "- When to update equipment settings: cemetery bought new equipment, policy changed, seasonal variation\n"
            "- How the county field on a cemetery affects which tax rate is applied to the order\n"
            "- What to do when a new cemetery comes up during a call "
            "(you can create it inline from the order form — you don't need to stop the call)\n"
            "- The consequence of NOT keeping cemetery settings updated: you charge a funeral home for equipment "
            "the cemetery provides, the funeral home pushes back, awkward call after the service\n\n"
            "Write for inside sales staff who may be new to the death care industry. "
            "Be specific about navigation paths and explain the real-world impact of each setting."
        ),
    },
]

CURRICULUM_ROLES = ["accounting", "inside_sales", "operations"]

# System prompts + user templates for procedure and curriculum generation now
# live in the managed `training.generate_procedure` and
# `training.generate_curriculum_track` prompts (Phase 2c-2 migration).
# See backend/scripts/seed_intelligence_phase2c.py for the verbatim content.


# ---------------------------------------------------------------------------
# Intelligence-layer callers — return (parsed_dict, error_message)
# ---------------------------------------------------------------------------


def _generate_procedure_via_intel(
    db: Session,
    *,
    title: str,
    roles: list[str],
    category: str,
    custom_instructions: str | None,
) -> tuple[dict | None, str | None]:
    """Route a procedure generation through the managed prompt.

    Returns (parsed_dict, None) on success or (None, error_message) on failure.
    Platform-level content — company_id=None, no caller_entity linkage.
    """
    if not settings.ANTHROPIC_API_KEY:
        return None, "ANTHROPIC_API_KEY not configured"
    try:
        from app.services.intelligence import intelligence_service

        result = intelligence_service.execute(
            db,
            prompt_key="training.generate_procedure",
            variables={
                "title": title,
                "roles": ", ".join(roles),
                "category": category,
                "custom_instructions": custom_instructions or "",
            },
            company_id=None,
            caller_module="training_content_generation_service.generate_procedures",
        )
        if result.status == "success" and isinstance(result.response_parsed, dict):
            return result.response_parsed, None
        return None, f"status={result.status}: {result.error_message or 'no parsed response'}"
    except Exception as e:
        return None, str(e)


def _generate_curriculum_via_intel(
    db: Session, *, role_label: str,
) -> tuple[dict | None, str | None]:
    """Route a curriculum track generation through the managed prompt."""
    if not settings.ANTHROPIC_API_KEY:
        return None, "ANTHROPIC_API_KEY not configured"
    try:
        from app.services.intelligence import intelligence_service

        result = intelligence_service.execute(
            db,
            prompt_key="training.generate_curriculum_track",
            variables={"role_label": role_label},
            company_id=None,
            caller_module="training_content_generation_service.generate_curriculum_tracks",
        )
        if result.status == "success" and isinstance(result.response_parsed, dict):
            return result.response_parsed, None
        return None, f"status={result.status}: {result.error_message or 'no parsed response'}"
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

        result, error = _generate_procedure_via_intel(
            db,
            title=title,
            roles=defn["roles"],
            category=defn["category"],
            custom_instructions=defn.get("user_msg"),
        )

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
        result, error = _generate_curriculum_via_intel(db, role_label=role_labels.get(role, role))

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
# Targeted re-generation — specific procedure keys only
# ---------------------------------------------------------------------------

# Keys that reference the invoice workflow and must be re-generated to reflect it
INVOICE_WORKFLOW_PROCEDURE_KEYS = [
    "statement_generation",
    "reviewing_collections_draft",
    "payment_application",
    "month_end_close",
    "morning_invoice_review",
    "acting_on_draft_invoice_alerts",
]


def regenerate_specific_procedures(db: Session, keys: list[str]) -> Generator[dict, None, None]:
    """Force-regenerate specific procedure keys regardless of whether they exist."""
    definitions_by_key = {d["key"]: d for d in PROCEDURE_DEFINITIONS}
    target_keys = [k for k in keys if k in definitions_by_key]
    total = len(target_keys)
    yield {"type": "section_start", "section": "procedures", "total": total}

    created = 0
    errors = []

    for i, key in enumerate(target_keys, 1):
        defn = definitions_by_key[key]
        title = defn["title"]
        yield {"type": "progress", "section": "procedures", "index": i, "total": total, "item": key, "status": "generating"}

        result, error = _generate_procedure_via_intel(
            db,
            title=title,
            roles=defn["roles"],
            category=defn["category"],
            custom_instructions=defn.get("user_msg"),
        )

        if error or not result:
            errors.append(f"{key}: {error}")
            yield {"type": "progress", "section": "procedures", "index": i, "total": total, "item": key, "status": "error", "error": error}
            continue

        now = datetime.now(timezone.utc)
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
# Curriculum module patch — update accounting track invoice modules
# ---------------------------------------------------------------------------


def patch_accounting_invoice_modules(db: Session) -> dict:
    """Update the accounting curriculum track's invoice-related module guided_task
    to reference the Invoice Review Queue (/ar/invoices/review).

    Returns a summary dict with patched/skipped counts.
    """
    track = db.query(TrainingCurriculumTrack).filter(
        TrainingCurriculumTrack.tenant_id.is_(None),
        TrainingCurriculumTrack.training_role == "accounting",
    ).first()

    if not track:
        return {"status": "no_track", "patched": 0}

    modules: list[dict] = list(track.modules or [])
    patched = 0
    INVOICE_KEYWORDS = ("invoice", "ar review", "draft invoice", "morning review", "billing")

    for module in modules:
        title_lower = (module.get("title") or "").lower()
        key_lower = (module.get("module_key") or "").lower()
        if any(kw in title_lower or kw in key_lower for kw in INVOICE_KEYWORDS):
            guided = module.get("guided_task")
            if isinstance(guided, dict):
                action = guided.get("platform_action", "")
                if "/ar/invoices/review" not in action:
                    guided["platform_action"] = (
                        "AR Command Center → Invoice Review tab → review draft invoices generated overnight → "
                        "approve clean invoices individually or use 'Approve All' for invoices with no exceptions"
                    )
                    module["guided_task"] = guided
                    patched += 1

    if patched:
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(track, "modules")
        track.modules = modules
        db.commit()

    return {"status": "ok", "patched": patched, "track_role": "accounting"}


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
