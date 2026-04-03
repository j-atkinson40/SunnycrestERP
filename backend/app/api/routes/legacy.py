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
    order_id: str | None = None
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
    from app.services import legacy_r2_client as r2

    is_urn = type == "urn"
    templates = get_all_templates(is_urn)
    results = []
    for t in templates:
        # Build thumbnail URL from the cached background JPEG in R2
        thumbnail_url = None
        if t["available"]:
            try:
                thumbnail_url = r2.get_public_url(t["cache_key"])
            except Exception:
                pass
        results.append({
            "print_name": t["print_name"],
            "is_urn": is_urn,
            "available": t["available"],
            "default_text_color": t["default_text_color"],
            "thumbnail_url": thumbnail_url,
        })
    return results


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


class PreviewRequest(BaseModel):
    print_name: str | None = None
    is_urn: bool = False
    is_custom: bool = False
    background_url: str | None = None
    layout: dict


@router.post("/generate-preview")
def generate_preview(
    data: PreviewRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate a proof JPEG preview (no TIF, no order association).

    Used by the order station to show proofs before order is saved.
    Preview files stored temporarily in R2 cache/previews/.
    """
    import uuid as _uuid
    from app.services import legacy_compositor as compositor
    from app.services import legacy_r2_client as r2
    from app.services.legacy_service import get_background_url, TemplateNotAvailable

    try:
        # Get background
        if data.print_name and not data.is_custom:
            bg_url = get_background_url(data.print_name, data.is_urn)
            bg_bytes = r2.download_bytes(
                f"cache/{'urn' if data.is_urn else 'standard'}/"
                + data.print_name.replace(" ", "_").replace("—", "-") + "_bg.jpg"
            )
        elif data.background_url:
            key = data.background_url.rsplit("/", 1)[-1] if "/" in data.background_url else data.background_url
            bg_bytes = r2.download_bytes(f"cache/custom/{key}")
        else:
            raise HTTPException(status_code=400, detail="print_name or background_url required")

        # Generate proof JPEG only (no TIF)
        proof_bytes = compositor.composite_layout(
            bg_bytes, data.layout, output_width=2400, for_print=False
        )

        preview_id = str(_uuid.uuid4())[:12]
        proof_key = f"cache/previews/{preview_id}_proof.jpg"
        proof_url = r2.upload_bytes(proof_bytes, proof_key, "image/jpeg")

        return {"proof_url": proof_url}
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


@router.post("/admin/upload-template")
async def upload_template_tif(
    file: UploadFile = File(...),
    template_type: str = Query("standard", regex="^(standard|urn|bv_standard|bv_urn)$"),
    current_user: User = Depends(require_admin),
):
    """Upload a template TIF file to R2 storage.

    The filename must match the r2_key filename for a registered template
    (e.g., WLP-AmFlag.tif, BV-CrossSet-Custom.tif).
    """
    from app.services import legacy_r2_client as r2
    from app.services.legacy_templates import get_all_templates

    if not file.filename or not file.filename.lower().endswith((".tif", ".tiff")):
        raise HTTPException(status_code=400, detail="Only TIF files accepted")

    # Determine R2 folder
    folder_map = {
        "standard": "templates/standard",
        "urn": "templates/urn",
        "bv_standard": "templates/bv_standard",
        "bv_urn": "templates/bv_urn",
    }
    folder = folder_map[template_type]
    r2_key = f"{folder}/{file.filename}"

    file_bytes = await file.read()
    size_mb = len(file_bytes) / (1024 * 1024)

    try:
        url = r2.upload_bytes(file_bytes, r2_key, "image/tiff")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Check if this matches a registered template
    is_urn = template_type in ("urn", "bv_urn")
    all_templates = get_all_templates(is_urn)
    matched = None
    for t in all_templates:
        if t["r2_key"] == r2_key:
            matched = t["print_name"]
            t["available"] = True
            break

    return {
        "uploaded": True,
        "r2_key": r2_key,
        "url": url,
        "size_mb": round(size_mb, 1),
        "matched_template": matched,
    }


@router.post("/admin/upload-templates-bulk")
async def upload_templates_bulk(
    files: list[UploadFile] = File(...),
    template_type: str = Query("standard", regex="^(standard|urn|bv_standard|bv_urn)$"),
    current_user: User = Depends(require_admin),
):
    """Upload multiple template TIF files at once."""
    from app.services import legacy_r2_client as r2
    from app.services.legacy_templates import get_all_templates

    folder_map = {
        "standard": "templates/standard",
        "urn": "templates/urn",
        "bv_standard": "templates/bv_standard",
        "bv_urn": "templates/bv_urn",
    }
    folder = folder_map[template_type]
    is_urn = template_type in ("urn", "bv_urn")
    all_templates = get_all_templates(is_urn)

    results = []
    for file in files:
        if not file.filename or not file.filename.lower().endswith((".tif", ".tiff")):
            results.append({"filename": file.filename, "error": "Not a TIF file"})
            continue

        r2_key = f"{folder}/{file.filename}"
        file_bytes = await file.read()
        try:
            url = r2.upload_bytes(file_bytes, r2_key, "image/tiff")
            matched = None
            for t in all_templates:
                if t["r2_key"] == r2_key:
                    matched = t["print_name"]
                    t["available"] = True
                    break
            results.append({
                "filename": file.filename,
                "r2_key": r2_key,
                "size_mb": round(len(file_bytes) / (1024 * 1024), 1),
                "matched_template": matched,
            })
        except Exception as e:
            results.append({"filename": file.filename, "error": str(e)})

    uploaded = [r for r in results if "error" not in r]
    return {"uploaded": len(uploaded), "errors": len(results) - len(uploaded), "results": results}


@router.get("/admin/template-status")
def template_upload_status(
    type: str = Query("standard", regex="^(standard|urn)$"),
    current_user: User = Depends(require_admin),
):
    """Check which registered templates have TIF files in R2."""
    from app.services import legacy_r2_client as r2
    from app.services.legacy_templates import get_all_templates

    is_urn = type == "urn"
    templates = get_all_templates(is_urn)
    results = []
    for t in templates:
        in_r2 = r2.exists(t["r2_key"])
        results.append({
            "print_name": t["print_name"],
            "r2_key": t["r2_key"],
            "available": t["available"],
            "in_r2": in_r2,
        })
    return results


@router.post("/admin/generate-thumbnails")
def generate_all_thumbnails(
    type: str = Query("standard", regex="^(standard|urn)$"),
    current_user: User = Depends(require_admin),
):
    """Pre-generate cached JPEG thumbnails for all templates that have TIFs in R2."""
    from app.services import legacy_r2_client as r2
    from app.services import legacy_compositor as compositor
    from app.services.legacy_templates import get_all_templates

    is_urn = type == "urn"
    templates = get_all_templates(is_urn)
    generated = 0
    skipped = 0
    errors = 0

    for t in templates:
        cache_key = t["cache_key"]
        # Skip if already cached
        if r2.exists(cache_key):
            skipped += 1
            continue
        # Skip if TIF doesn't exist
        if not r2.exists(t["r2_key"]):
            skipped += 1
            continue
        try:
            tif_bytes = r2.download_bytes(t["r2_key"])
            jpeg_bytes = compositor.flatten_tif_to_jpeg(tif_bytes)
            r2.upload_bytes(jpeg_bytes, cache_key, "image/jpeg")
            generated += 1
            logger.info("Generated thumbnail for %s", t["print_name"])
        except Exception as e:
            errors += 1
            logger.warning("Failed to generate thumbnail for %s: %s", t["print_name"], e)

    return {"generated": generated, "skipped": skipped, "errors": errors, "total": len(templates)}
