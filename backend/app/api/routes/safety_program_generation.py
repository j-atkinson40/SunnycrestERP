"""Safety Program Generation API routes."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.database import get_db
from app.models.user import User
from app.services import safety_program_generation_service as svc

router = APIRouter()


@router.get("/generations")
def list_generations(
    year: int | None = None,
    limit: int = Query(20, le=100),
    current_user: User = Depends(require_permission("safety.trainer.view")),
    db: Session = Depends(get_db),
):
    """List safety program generations for the current tenant."""
    return svc.list_generations(db, current_user.company_id, year=year, limit=limit)


@router.get("/generations/{generation_id}")
def get_generation_detail(
    generation_id: str,
    current_user: User = Depends(require_permission("safety.trainer.view")),
    db: Session = Depends(get_db),
):
    """Get full detail for a safety program generation."""
    result = svc.get_generation_detail(db, generation_id, current_user.company_id)
    if not result:
        raise HTTPException(status_code=404, detail="Generation not found")
    return result


@router.post("/generate")
def trigger_generation(
    background_tasks: BackgroundTasks,
    year: int | None = None,
    month: int | None = None,
    current_user: User = Depends(require_permission("safety.trainer.generate")),
    db: Session = Depends(get_db),
):
    """Manually trigger safety program generation for a specific month.

    If year/month not specified, generates for the current month.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    target_year = year or now.year
    target_month = month or now.month

    if target_month < 1 or target_month > 12:
        raise HTTPException(status_code=400, detail="Month must be 1-12")

    # Run the pipeline
    result = svc.run_monthly_generation(db, current_user.company_id)
    return result


@router.post("/generate-for-topic/{topic_id}")
def generate_for_topic(
    topic_id: str,
    current_user: User = Depends(require_permission("safety.trainer.generate")),
    db: Session = Depends(get_db),
):
    """Generate a safety program for a specific topic (ad-hoc)."""
    import uuid
    from datetime import datetime, timezone

    from app.models.safety_program_generation import SafetyProgramGeneration
    from app.models.safety_training_topic import SafetyTrainingTopic

    topic = db.query(SafetyTrainingTopic).filter(
        SafetyTrainingTopic.id == topic_id
    ).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    now = datetime.now(timezone.utc)

    gen = SafetyProgramGeneration(
        id=str(uuid.uuid4()),
        tenant_id=current_user.company_id,
        topic_id=topic.id,
        year=now.year,
        month_number=topic.month_number,
        osha_standard_code=topic.osha_standard,
    )
    db.add(gen)
    db.commit()

    # Run pipeline steps
    try:
        svc.scrape_osha_for_generation(db, gen.id)
    except Exception:
        pass

    try:
        svc.generate_program_content(db, gen.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)[:200]}")

    try:
        svc.generate_pdf(db, gen.id)
    except Exception:
        pass  # PDF is non-fatal

    return svc.get_generation_detail(db, gen.id, current_user.company_id)


@router.post("/generations/{generation_id}/regenerate-pdf")
def regenerate_pdf(
    generation_id: str,
    current_user: User = Depends(require_permission("safety.trainer.generate")),
    db: Session = Depends(get_db),
):
    """Re-generate the PDF for an existing generation."""
    from app.models.safety_program_generation import SafetyProgramGeneration

    gen = db.query(SafetyProgramGeneration).filter(
        SafetyProgramGeneration.id == generation_id,
        SafetyProgramGeneration.tenant_id == current_user.company_id,
    ).first()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found")
    if not gen.generated_html:
        raise HTTPException(status_code=400, detail="No HTML content to render")

    svc.generate_pdf(db, gen.id)
    return svc.get_generation_detail(db, gen.id, current_user.company_id)


@router.post("/generations/{generation_id}/approve")
def approve_generation(
    generation_id: str,
    notes: str | None = None,
    current_user: User = Depends(require_permission("safety.trainer.approve")),
    db: Session = Depends(get_db),
):
    """Approve a generated safety program."""
    try:
        svc.approve_generation(db, generation_id, current_user.id, notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return svc.get_generation_detail(db, generation_id, current_user.company_id)


@router.post("/generations/{generation_id}/reject")
def reject_generation(
    generation_id: str,
    notes: str = "",
    current_user: User = Depends(require_permission("safety.trainer.approve")),
    db: Session = Depends(get_db),
):
    """Reject a generated safety program with notes."""
    if not notes:
        raise HTTPException(status_code=400, detail="Rejection notes are required")
    try:
        svc.reject_generation(db, generation_id, current_user.id, notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return svc.get_generation_detail(db, generation_id, current_user.company_id)
