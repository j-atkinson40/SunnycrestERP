"""Legacy Series print API — template listing, background caching, and generation."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


class BackgroundRequest(BaseModel):
    print_name: str
    is_urn: bool = False


class GenerateRequest(BaseModel):
    order_id: str
    print_name: str | None = None
    is_urn: bool = False
    is_custom: bool = False
    layout: dict


class MarkAvailableRequest(BaseModel):
    print_name: str
    is_urn: bool = False


@router.get("/templates")
def list_templates(
    type: str = Query("standard", regex="^(standard|urn)$"),
    current_user: User = Depends(get_current_user),
):
    """List all legacy print templates with availability status."""
    from app.services.legacy_templates import get_all_templates

    is_urn = type == "urn"
    templates = get_all_templates(is_urn)
    return [
        {
            "print_name": t["print_name"],
            "is_urn": is_urn,
            "available": t["available"],
            "default_text_color": t["default_text_color"],
        }
        for t in templates
    ]


@router.post("/background")
def get_background(
    data: BackgroundRequest,
    current_user: User = Depends(get_current_user),
):
    """Get or generate the cached JPEG background for a template."""
    from app.services.legacy_service import get_background_url, TemplateNotAvailable

    try:
        url = get_background_url(data.print_name, data.is_urn)
        return {"background_url": url}
    except TemplateNotAvailable as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/custom-background")
async def upload_custom_background(
    order_id: str = Query(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Process a custom photo into a blurred legacy background."""
    from app.services.legacy_service import process_custom_background_upload

    photo_bytes = await file.read()
    try:
        url = process_custom_background_upload(photo_bytes, order_id)
        return {"background_url": url}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/generate")
def generate_legacy(
    data: GenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate proof JPEG and print TIF for a legacy order."""
    from app.services.legacy_service import generate_final, TemplateNotAvailable

    try:
        result = generate_final(
            order_id=data.order_id,
            layout=data.layout,
            print_name=data.print_name,
            is_urn=data.is_urn,
        )

        # Update personalization task with URLs
        try:
            from app.models.order_personalization_task import OrderPersonalizationTask

            task = (
                db.query(OrderPersonalizationTask)
                .filter(
                    OrderPersonalizationTask.order_id == data.order_id,
                    OrderPersonalizationTask.task_type.in_(["legacy_standard", "legacy_custom"]),
                )
                .first()
            )
            if task:
                task.print_image_url = result["proof_url"]
                task.notes = (task.notes or "") + f"\nProof: {result['proof_url']}\nTIF: {result['tif_url']}"
                db.commit()
        except Exception:
            logger.warning("Could not update task with legacy URLs for order %s", data.order_id)

        return result
    except TemplateNotAvailable as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/proof-status/{task_id}")
def get_proof_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check proof generation status for a legacy task."""
    from app.models.order_personalization_task import OrderPersonalizationTask

    task = (
        db.query(OrderPersonalizationTask)
        .filter(
            OrderPersonalizationTask.id == task_id,
            OrderPersonalizationTask.company_id == current_user.company_id,
        )
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "status": task.status,
        "proof_url": task.proof_url,
        "tif_url": task.tif_url,
        "default_layout": task.default_layout,
        "approved_layout": task.approved_layout,
        "notes": task.notes,
    }


@router.post("/admin/mark-available")
def mark_template_available(
    data: MarkAvailableRequest,
    current_user: User = Depends(require_admin),
):
    """Mark a template as available after TIF upload. Triggers background cache."""
    from app.services.legacy_templates import get_template, STANDARD_TEMPLATES, URN_TEMPLATES
    from app.services.legacy_service import get_background_url

    templates = URN_TEMPLATES if data.is_urn else STANDARD_TEMPLATES
    for t in templates:
        if t["print_name"].lower() == data.print_name.lower():
            t["available"] = True
            try:
                bg_url = get_background_url(data.print_name, data.is_urn)
                return {"available": True, "background_url": bg_url}
            except Exception as e:
                return {"available": True, "background_url": None, "note": str(e)}

    raise HTTPException(status_code=404, detail=f"Template '{data.print_name}' not found")
