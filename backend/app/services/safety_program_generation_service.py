"""Safety Program Generation Service.

Generates monthly written safety programs using Claude Sonnet and OSHA regulation text.
Produces canonical Document rows via the Phase D-2 managed template
registry (`pdf.safety_program_base`). Ties into the existing safety
training schedule.
"""

import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models.safety_program import SafetyProgram
from app.models.safety_program_generation import SafetyProgramGeneration
from app.models.safety_training_topic import SafetyTrainingTopic
from app.models.tenant_training_schedule import TenantTrainingSchedule
from app.services.osha_scraper_service import scrape_osha_standard

logger = logging.getLogger(__name__)

GENERATION_MODEL = "claude-sonnet-4-20250514"
GENERATION_MAX_TOKENS = 4096


# ---------------------------------------------------------------------------
# OSHA scrape step
# ---------------------------------------------------------------------------


def scrape_osha_for_generation(
    db: Session, generation_id: str
) -> SafetyProgramGeneration:
    """Scrape OSHA standard text and store on the generation record."""
    gen = db.query(SafetyProgramGeneration).filter(
        SafetyProgramGeneration.id == generation_id
    ).first()
    if not gen:
        raise ValueError(f"Generation {generation_id} not found")

    topic = db.query(SafetyTrainingTopic).filter(
        SafetyTrainingTopic.id == gen.topic_id
    ).first()
    if not topic or not topic.osha_standard:
        gen.osha_scrape_status = "skipped"
        gen.osha_scraped_at = datetime.now(timezone.utc)
        db.commit()
        return gen

    result = scrape_osha_standard(topic.osha_standard)

    gen.osha_standard_code = result["standard_code"]
    gen.osha_scrape_url = result["url"]
    gen.osha_scraped_at = datetime.now(timezone.utc)

    if result["success"]:
        gen.osha_scraped_text = result["text"]
        gen.osha_scrape_status = "success"
    else:
        gen.osha_scrape_status = "failed"
        gen.error_message = f"OSHA scrape: {result['error']}"

    db.commit()
    db.refresh(gen)
    return gen


# ---------------------------------------------------------------------------
# Claude generation step
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = """You are a safety program writer for a precast concrete / burial vault manufacturing company.
You write clear, professional, OSHA-compliant written safety programs.

Your output must be a complete written safety program in HTML format suitable for PDF generation.
Include these sections:
1. Purpose & Scope
2. Responsibilities (management, supervisors, employees)
3. Definitions
4. Procedures / Requirements (this is the main body — be detailed and specific)
5. Training Requirements
6. Recordkeeping
7. Program Review & Updates

Use proper HTML with semantic tags (<h2>, <h3>, <p>, <ul>, <li>, <table> where appropriate).
Do NOT include <html>, <head>, or <body> tags — just the content that goes inside the body.
Use professional language suitable for an official company safety document.
Reference the specific OSHA standard numbers where applicable.
Include practical, industry-specific guidance for precast concrete operations where relevant.
"""


def generate_program_content(
    db: Session, generation_id: str
) -> SafetyProgramGeneration:
    """Generate the written safety program using Claude Sonnet."""
    gen = db.query(SafetyProgramGeneration).filter(
        SafetyProgramGeneration.id == generation_id
    ).first()
    if not gen:
        raise ValueError(f"Generation {generation_id} not found")

    topic = db.query(SafetyTrainingTopic).filter(
        SafetyTrainingTopic.id == gen.topic_id
    ).first()
    if not topic:
        raise ValueError(f"Topic {gen.topic_id} not found")

    # Get company name for the program
    company = db.query(Company).filter(Company.id == gen.tenant_id).first()
    company_name = company.name if company else "Company"

    gen.generation_status = "generating"
    db.commit()

    if not settings.ANTHROPIC_API_KEY:
        gen.generation_status = "failed"
        gen.error_message = "ANTHROPIC_API_KEY not configured"
        db.commit()
        return gen

    try:
        from app.services.intelligence import intelligence_service

        result = intelligence_service.execute(
            db,
            prompt_key="safety.draft_monthly_program",
            variables={
                "topic_title": topic.title,
                "company_name": company_name,
                "osha_standard": topic.osha_standard or "General industry standards apply",
                "osha_standard_label": topic.osha_standard_label or topic.title,
                "topic_description": topic.description or "",
                "key_points": topic.key_points or [],
                "osha_scraped_text": (gen.osha_scraped_text or "")[:12000],
            },
            company_id=gen.tenant_id,
            caller_module="safety_program_generation_service",
            caller_entity_type="safety_program_generation",
            caller_entity_id=gen.id,
        )

        if result.status == "success" and result.response_text:
            gen.generated_content = result.response_text
            gen.generated_html = _wrap_program_html(
                result.response_text,
                topic.title,
                company_name,
                topic.osha_standard,
                db=db,
                company_id=gen.tenant_id,
            )
            gen.generation_status = "complete"
            gen.generation_model = result.model_used or GENERATION_MODEL
            gen.generation_token_usage = {
                "input_tokens": result.input_tokens or 0,
                "output_tokens": result.output_tokens or 0,
            }
            gen.generated_at = datetime.now(timezone.utc)
            gen.status = "pending_review"
        else:
            gen.generation_status = "failed"
            gen.error_message = (
                f"Intelligence execute status={result.status}: "
                f"{result.error_message or 'no response text'}"
            )[:500]

    except Exception as e:
        gen.generation_status = "failed"
        gen.error_message = f"Claude API error: {str(e)[:500]}"
        logger.error(f"Safety program generation failed: {e}", exc_info=True)

    db.commit()
    db.refresh(gen)
    return gen


def _wrap_program_html(
    content: str,
    title: str,
    company_name: str,
    osha_standard: str | None,
    *,
    db: Session | None = None,
    company_id: str | None = None,
) -> str:
    """Render the Claude-generated content inside the managed
    `pdf.safety_program_base` wrapper. D-2: structural HTML moved to the
    template registry; tenants override this wrapper to re-brand without
    touching the AI-generated content.

    `content` is Claude's HTML. We pass it through the wrapper via the
    `ai_generated_html` context variable — the template uses `|safe` to
    render it un-escaped (trust is established at Claude-call time by the
    managed `safety.draft_monthly_program` prompt).

    When `db` + `company_id` are provided, the renderer resolves a
    tenant override first; omit them to force the platform template.
    """
    from app.services.documents import document_renderer

    today_str = date.today().strftime("%B %Y")
    context = {
        "company_name": company_name,
        "program_title": title,
        "osha_standard": osha_standard,
        "date_line": today_str,
        "ai_generated_html": content,
    }
    result = document_renderer.render_html(
        db,
        template_key="pdf.safety_program_base",
        context=context,
        company_id=company_id,
    )
    return result.rendered_content  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# PDF generation step
# ---------------------------------------------------------------------------


def generate_pdf(
    db: Session, generation_id: str
) -> SafetyProgramGeneration:
    """Generate a PDF from the generated HTML content — produces a
    canonical Document row via the managed template registry.

    D-2 rewrite: routes through document_renderer.render() with
    `pdf.safety_program_base`. The Claude-generated content from
    `gen.generated_content` is embedded via the `ai_generated_html`
    context variable. Any tenant-scoped override of the base template
    wins over the platform default.
    """
    gen = db.query(SafetyProgramGeneration).filter(
        SafetyProgramGeneration.id == generation_id
    ).first()
    if not gen:
        raise ValueError("Generation not found")
    content = gen.generated_content or gen.generated_html
    if not content:
        raise ValueError("No content to render")

    topic = db.query(SafetyTrainingTopic).filter(
        SafetyTrainingTopic.id == gen.topic_id
    ).first()
    topic_title = topic.title if topic else "Safety Program"

    from app.models.company import Company
    company = db.query(Company).filter(Company.id == gen.tenant_id).first()
    company_name = company.name if company else "Company"

    today_str = date.today().strftime("%B %Y")
    context = {
        "company_name": company_name,
        "program_title": topic_title,
        "osha_standard": topic.osha_standard if topic else None,
        "date_line": today_str,
        "ai_generated_html": content,
    }

    from app.services.documents import document_renderer

    try:
        doc = document_renderer.render(
            db,
            template_key="pdf.safety_program_base",
            context=context,
            document_type="safety_program",
            title=(
                f"Safety Program \u2014 {topic_title} \u2014 "
                f"{gen.year}-{gen.month_number:02d}"
            ),
            company_id=gen.tenant_id,
            entity_type="safety_program_generation",
            entity_id=gen.id,
            safety_program_generation_id=gen.id,
            caller_module="safety_program_generation_service.generate_pdf",
        )

        gen.pdf_document_id = doc.id
        gen.pdf_generated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(gen)
        return gen

    except Exception as e:
        gen.error_message = f"PDF generation failed: {str(e)[:500]}"
        db.commit()
        raise


# ---------------------------------------------------------------------------
# Approval workflow
# ---------------------------------------------------------------------------


def approve_generation(
    db: Session, generation_id: str, user_id: str, notes: str | None = None
) -> SafetyProgramGeneration:
    """Approve a generated program and create/update the SafetyProgram record."""
    gen = db.query(SafetyProgramGeneration).filter(
        SafetyProgramGeneration.id == generation_id
    ).first()
    if not gen:
        raise ValueError("Generation not found")
    if gen.status not in ("pending_review", "draft"):
        raise ValueError(f"Cannot approve generation in status '{gen.status}'")

    topic = db.query(SafetyTrainingTopic).filter(
        SafetyTrainingTopic.id == gen.topic_id
    ).first()

    gen.status = "approved"
    gen.reviewed_by = user_id
    gen.reviewed_at = datetime.now(timezone.utc)
    gen.review_notes = notes

    # Create or update SafetyProgram
    program = (
        db.query(SafetyProgram)
        .filter(
            SafetyProgram.company_id == gen.tenant_id,
            SafetyProgram.osha_standard_code == (topic.osha_standard if topic else None),
        )
        .first()
    )

    if program:
        program.content = gen.generated_content
        program.version = (program.version or 0) + 1
        program.last_reviewed_at = datetime.now(timezone.utc)
        program.reviewed_by = user_id
        program.status = "active"
        program.updated_at = datetime.now(timezone.utc)
    else:
        program = SafetyProgram(
            id=str(uuid.uuid4()),
            company_id=gen.tenant_id,
            program_name=topic.title if topic else "Safety Program",
            osha_standard=topic.osha_standard_label if topic else None,
            osha_standard_code=topic.osha_standard if topic else None,
            description=topic.description if topic else None,
            content=gen.generated_content,
            version=1,
            status="active",
            last_reviewed_at=datetime.now(timezone.utc),
            reviewed_by=user_id,
        )
        db.add(program)
        db.flush()

    gen.safety_program_id = program.id
    gen.posted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(gen)
    return gen


def reject_generation(
    db: Session, generation_id: str, user_id: str, notes: str
) -> SafetyProgramGeneration:
    """Reject a generated program with notes."""
    gen = db.query(SafetyProgramGeneration).filter(
        SafetyProgramGeneration.id == generation_id
    ).first()
    if not gen:
        raise ValueError("Generation not found")

    gen.status = "rejected"
    gen.reviewed_by = user_id
    gen.reviewed_at = datetime.now(timezone.utc)
    gen.review_notes = notes
    db.commit()
    db.refresh(gen)
    return gen


# ---------------------------------------------------------------------------
# Full pipeline (for scheduler)
# ---------------------------------------------------------------------------


def run_monthly_generation(db: Session, tenant_id: str) -> dict:
    """Run the full monthly safety program generation pipeline for a tenant.

    Called by the scheduler on the 1st of each month.
    Returns summary dict.
    """
    now = datetime.now(timezone.utc)
    current_month = now.month
    current_year = now.year

    # Get this month's training schedule
    schedule = (
        db.query(TenantTrainingSchedule)
        .filter(
            TenantTrainingSchedule.tenant_id == tenant_id,
            TenantTrainingSchedule.year == current_year,
            TenantTrainingSchedule.month_number == current_month,
        )
        .first()
    )

    if not schedule:
        logger.info(f"No training schedule for {tenant_id} {current_year}-{current_month}")
        return {"status": "skipped", "reason": "no_schedule"}

    topic = db.query(SafetyTrainingTopic).filter(
        SafetyTrainingTopic.id == schedule.topic_id
    ).first()
    if not topic:
        return {"status": "skipped", "reason": "no_topic"}

    # Check if already generated this month
    existing = (
        db.query(SafetyProgramGeneration)
        .filter(
            SafetyProgramGeneration.tenant_id == tenant_id,
            SafetyProgramGeneration.year == current_year,
            SafetyProgramGeneration.month_number == current_month,
        )
        .first()
    )
    if existing:
        return {"status": "skipped", "reason": "already_generated", "generation_id": existing.id}

    # Create generation record
    gen = SafetyProgramGeneration(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        topic_id=topic.id,
        schedule_id=schedule.id,
        year=current_year,
        month_number=current_month,
        osha_standard_code=topic.osha_standard,
    )
    db.add(gen)
    db.commit()

    # Step 1: Scrape OSHA
    try:
        scrape_osha_for_generation(db, gen.id)
    except Exception as e:
        logger.warning(f"OSHA scrape step failed for {gen.id}: {e}")

    # Step 2: Generate content
    try:
        generate_program_content(db, gen.id)
    except Exception as e:
        logger.error(f"Content generation failed for {gen.id}: {e}")
        return {"status": "failed", "generation_id": gen.id, "error": str(e)}

    # Step 3: Generate PDF
    try:
        generate_pdf(db, gen.id)
    except Exception as e:
        logger.warning(f"PDF generation failed for {gen.id}: {e}")
        # Non-fatal — content is still available

    db.refresh(gen)
    return {
        "status": gen.generation_status,
        "generation_id": gen.id,
        "topic": topic.title,
        "osha_scrape_status": gen.osha_scrape_status,
    }


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def list_generations(
    db: Session, tenant_id: str, year: int | None = None, limit: int = 20
) -> list[dict]:
    """List safety program generations for a tenant."""
    query = (
        db.query(SafetyProgramGeneration)
        .filter(SafetyProgramGeneration.tenant_id == tenant_id)
    )
    if year:
        query = query.filter(SafetyProgramGeneration.year == year)

    gens = query.order_by(
        SafetyProgramGeneration.year.desc(),
        SafetyProgramGeneration.month_number.desc(),
    ).limit(limit).all()

    topic_ids = list({g.topic_id for g in gens})
    topics = {
        t.id: t
        for t in db.query(SafetyTrainingTopic)
        .filter(SafetyTrainingTopic.id.in_(topic_ids))
        .all()
    } if topic_ids else {}

    results = []
    for g in gens:
        topic = topics.get(g.topic_id)
        results.append({
            "id": g.id,
            "year": g.year,
            "month_number": g.month_number,
            "topic_title": topic.title if topic else None,
            "osha_standard": topic.osha_standard if topic else None,
            "osha_scrape_status": g.osha_scrape_status,
            "generation_status": g.generation_status,
            "status": g.status,
            "pdf_document_id": g.pdf_document_id,
            "safety_program_id": g.safety_program_id,
            "generated_at": g.generated_at.isoformat() if g.generated_at else None,
            "reviewed_at": g.reviewed_at.isoformat() if g.reviewed_at else None,
            "created_at": g.created_at.isoformat() if g.created_at else None,
            "error_message": g.error_message,
        })
    return results


def get_generation_detail(
    db: Session, generation_id: str, tenant_id: str
) -> dict | None:
    """Get full detail for a single generation."""
    gen = (
        db.query(SafetyProgramGeneration)
        .filter(
            SafetyProgramGeneration.id == generation_id,
            SafetyProgramGeneration.tenant_id == tenant_id,
        )
        .first()
    )
    if not gen:
        return None

    topic = db.query(SafetyTrainingTopic).filter(
        SafetyTrainingTopic.id == gen.topic_id
    ).first()

    from app.models.user import User
    reviewer = None
    if gen.reviewed_by:
        r = db.query(User).filter(User.id == gen.reviewed_by).first()
        if r:
            reviewer = f"{r.first_name} {r.last_name}"

    return {
        "id": gen.id,
        "tenant_id": gen.tenant_id,
        "year": gen.year,
        "month_number": gen.month_number,
        "topic_id": gen.topic_id,
        "topic_title": topic.title if topic else None,
        "osha_standard": topic.osha_standard if topic else None,
        "osha_standard_label": topic.osha_standard_label if topic else None,
        "osha_standard_code": gen.osha_standard_code,
        "osha_scrape_status": gen.osha_scrape_status,
        "osha_scrape_url": gen.osha_scrape_url,
        "osha_scraped_at": gen.osha_scraped_at.isoformat() if gen.osha_scraped_at else None,
        "generated_content": gen.generated_content,
        "generated_html": gen.generated_html,
        "generation_status": gen.generation_status,
        "generation_model": gen.generation_model,
        "generation_token_usage": gen.generation_token_usage,
        "generated_at": gen.generated_at.isoformat() if gen.generated_at else None,
        "pdf_document_id": gen.pdf_document_id,
        "pdf_generated_at": gen.pdf_generated_at.isoformat() if gen.pdf_generated_at else None,
        "status": gen.status,
        "reviewed_by_name": reviewer,
        "reviewed_at": gen.reviewed_at.isoformat() if gen.reviewed_at else None,
        "review_notes": gen.review_notes,
        "safety_program_id": gen.safety_program_id,
        "posted_at": gen.posted_at.isoformat() if gen.posted_at else None,
        "error_message": gen.error_message,
        "created_at": gen.created_at.isoformat() if gen.created_at else None,
    }
