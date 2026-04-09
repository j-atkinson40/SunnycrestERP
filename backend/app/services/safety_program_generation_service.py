"""Safety Program Generation Service.

Generates monthly written safety programs using Claude Sonnet and OSHA regulation text.
Produces PDF via WeasyPrint. Ties into the existing safety training schedule.
"""

import logging
import uuid
from datetime import date, datetime, timezone

import anthropic
from sqlalchemy.orm import Session

from app.config import settings
from app.models.company import Company
from app.models.document import Document
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

    # Build user prompt
    user_parts = [
        f"Generate a written safety program for: {topic.title}",
        f"Company: {company_name}",
        f"OSHA Standard: {topic.osha_standard or 'General industry standards apply'}",
        f"Standard Label: {topic.osha_standard_label or topic.title}",
        "",
    ]

    if topic.description:
        user_parts.append(f"Topic description: {topic.description}")
        user_parts.append("")

    if topic.key_points:
        user_parts.append("Key points to cover:")
        for kp in topic.key_points:
            user_parts.append(f"- {kp}")
        user_parts.append("")

    if gen.osha_scraped_text:
        user_parts.append("OSHA REGULATION TEXT (for reference — incorporate requirements into the program):")
        user_parts.append("---")
        # Limit to avoid token overflow
        osha_text = gen.osha_scraped_text[:12000]
        user_parts.append(osha_text)
        user_parts.append("---")
        user_parts.append("")

    user_parts.append(
        "Generate the complete written safety program now. "
        "Output ONLY the HTML content (no markdown, no code fences)."
    )

    user_prompt = "\n".join(user_parts)

    if not settings.ANTHROPIC_API_KEY:
        gen.generation_status = "failed"
        gen.error_message = "ANTHROPIC_API_KEY not configured"
        db.commit()
        return gen

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=GENERATION_MODEL,
            max_tokens=GENERATION_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        content_text = message.content[0].text
        gen.generated_content = content_text
        gen.generated_html = _wrap_program_html(content_text, topic.title, company_name, topic.osha_standard)
        gen.generation_status = "complete"
        gen.generation_model = GENERATION_MODEL
        gen.generation_token_usage = {
            "input_tokens": message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens,
        }
        gen.generated_at = datetime.now(timezone.utc)
        gen.status = "pending_review"

    except Exception as e:
        gen.generation_status = "failed"
        gen.error_message = f"Claude API error: {str(e)[:500]}"
        logger.error(f"Safety program generation failed: {e}", exc_info=True)

    db.commit()
    db.refresh(gen)
    return gen


def _wrap_program_html(
    content: str, title: str, company_name: str, osha_standard: str | None
) -> str:
    """Wrap generated content in a full HTML document for PDF rendering."""
    from app.utils.pdf_generators.social_service_certificate_pdf import _esc

    today_str = date.today().strftime("%B %Y")
    osha_line = f"OSHA Standard: {_esc(osha_standard)}" if osha_standard else ""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: letter portrait;
    margin: 0.75in 0.75in 1in 0.75in;
    @bottom-center {{
      content: "Page " counter(page) " of " counter(pages);
      font-size: 8pt;
      color: #888;
    }}
  }}
  body {{
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    color: #1a1a1a;
    line-height: 1.6;
    margin: 0;
    padding: 0;
  }}
  .cover-header {{
    text-align: center;
    padding: 20px 0 16px;
    border-bottom: 3px solid #1a365d;
    margin-bottom: 24px;
  }}
  .cover-header .company-name {{
    font-size: 14pt;
    font-weight: 700;
    color: #1a365d;
    letter-spacing: 0.5px;
    margin-bottom: 6px;
  }}
  .cover-header .program-title {{
    font-size: 18pt;
    font-weight: 700;
    margin: 12px 0 8px;
  }}
  .cover-header .osha-ref {{
    font-size: 10pt;
    color: #555;
  }}
  .cover-header .date-line {{
    font-size: 10pt;
    color: #555;
    margin-top: 4px;
  }}
  h2 {{
    font-size: 13pt;
    font-weight: 700;
    color: #1a365d;
    border-bottom: 1.5px solid #1a365d;
    padding-bottom: 4px;
    margin-top: 24px;
    margin-bottom: 12px;
    page-break-after: avoid;
  }}
  h3 {{
    font-size: 11pt;
    font-weight: 700;
    color: #2d3748;
    margin-top: 16px;
    margin-bottom: 8px;
    page-break-after: avoid;
  }}
  p {{
    margin: 0 0 8px;
  }}
  ul, ol {{
    margin: 0 0 12px;
    padding-left: 24px;
  }}
  li {{
    margin-bottom: 4px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 10pt;
  }}
  table th, table td {{
    border: 1px solid #ccc;
    padding: 6px 8px;
    text-align: left;
    vertical-align: top;
  }}
  table th {{
    background: #edf2f7;
    font-weight: 600;
  }}
  .disclaimer {{
    margin-top: 30px;
    padding: 12px;
    border: 1px solid #ccc;
    background: #f7fafc;
    font-size: 9pt;
    color: #555;
    line-height: 1.5;
  }}
  .footer-line {{
    margin-top: 24px;
    border-top: 1px solid #ddd;
    padding-top: 8px;
    font-size: 8.5pt;
    color: #888;
    text-align: center;
  }}
</style>
</head>
<body>

<div class="cover-header">
  <div class="company-name">{_esc(company_name)}</div>
  <div class="program-title">{_esc(title)}</div>
  <div class="program-title" style="font-size: 12pt; font-weight: 400;">Written Safety Program</div>
  <div class="osha-ref">{osha_line}</div>
  <div class="date-line">{today_str}</div>
</div>

{content}

<div class="disclaimer">
  This written safety program is generated as a starting point and should be reviewed
  and customized by the designated safety trainer or safety manager before implementation.
  It does not constitute legal advice. Consult with qualified safety professionals and
  legal counsel to ensure full compliance with all applicable OSHA regulations and
  state-specific requirements.
</div>

<div class="footer-line">
  {_esc(company_name)} &mdash; Written Safety Program &mdash; {today_str}
</div>

</body>
</html>"""


# ---------------------------------------------------------------------------
# PDF generation step
# ---------------------------------------------------------------------------


def generate_pdf(
    db: Session, generation_id: str
) -> SafetyProgramGeneration:
    """Generate a PDF from the HTML content and store as a Document."""
    gen = db.query(SafetyProgramGeneration).filter(
        SafetyProgramGeneration.id == generation_id
    ).first()
    if not gen or not gen.generated_html:
        raise ValueError("No HTML content to render")

    try:
        from weasyprint import HTML

        pdf_bytes = HTML(string=gen.generated_html).write_pdf()

        topic = db.query(SafetyTrainingTopic).filter(
            SafetyTrainingTopic.id == gen.topic_id
        ).first()
        topic_title = topic.title if topic else "Safety Program"

        # Create a Document record and upload to R2
        filename = f"safety-program-{gen.year}-{gen.month_number:02d}-{topic_title.lower().replace(' ', '-')[:40]}.pdf"
        r2_key = f"tenants/{gen.tenant_id}/safety_programs/{gen.id}/{filename}"

        # Try R2 upload
        try:
            from app.services.legacy_r2_client import upload_bytes as r2_upload
            r2_upload(pdf_bytes, r2_key, content_type="application/pdf")
        except Exception as e:
            logger.warning(f"R2 upload failed, storing locally: {e}")
            import os
            upload_dir = os.path.join("static", "safety-programs", gen.tenant_id)
            os.makedirs(upload_dir, exist_ok=True)
            filepath = os.path.join(upload_dir, filename)
            with open(filepath, "wb") as f:
                f.write(pdf_bytes)
            r2_key = filepath

        doc = Document(
            id=str(uuid.uuid4()),
            company_id=gen.tenant_id,
            entity_type="safety_program_generation",
            entity_id=gen.id,
            file_name=filename,
            file_path=r2_key,
            r2_key=r2_key if r2_key.startswith("tenants/") else None,
            file_size=len(pdf_bytes),
            mime_type="application/pdf",
        )
        db.add(doc)

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
