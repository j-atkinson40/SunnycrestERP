"""Legacy print orchestration — coordinates R2 storage, templates, and compositor."""

import logging

from app.services import legacy_r2_client as r2
from app.services import legacy_compositor as compositor
from app.services.legacy_templates import get_template, get_available_templates

logger = logging.getLogger(__name__)


class TemplateNotAvailable(Exception):
    pass


def get_background_url(print_name: str, is_urn: bool = False) -> str:
    """Get or generate the cached JPEG background for a template.

    Downloads TIF from R2, flattens to JPEG, caches, returns public URL.
    """
    template = get_template(print_name, is_urn)
    if not template or not template["available"]:
        raise TemplateNotAvailable(f"Template '{print_name}' not available")

    cache_key = template["cache_key"]

    # Check cache first
    if r2.exists(cache_key):
        return r2.get_public_url(cache_key)

    # Download TIF, flatten, cache
    tif_bytes = r2.download_bytes(template["r2_key"])
    jpeg_bytes = compositor.flatten_tif_to_jpeg(tif_bytes)
    return r2.upload_bytes(jpeg_bytes, cache_key, "image/jpeg")


def process_custom_background_upload(photo_bytes: bytes, order_id: str) -> str:
    """Process a custom photo into a blurred background. Returns URL."""
    bg_bytes = compositor.process_custom_background(photo_bytes)
    r2_key = f"cache/custom/{order_id}_bg.jpg"
    return r2.upload_bytes(bg_bytes, r2_key, "image/jpeg")


def generate_final(
    order_id: str,
    layout: dict,
    print_name: str | None = None,
    is_urn: bool = False,
    custom_background_url: str | None = None,
) -> dict:
    """Generate proof JPEG and print TIF for a legacy order.

    Returns: {"proof_url": str, "tif_url": str}
    """
    # Get background
    if print_name:
        template = get_template(print_name, is_urn)
        if not template:
            raise TemplateNotAvailable(f"Template '{print_name}' not found")
        background_bytes = r2.download_bytes(template["r2_key"])
        # Flatten TIF to usable format
        background_bytes = compositor.flatten_tif_to_jpeg(background_bytes)
    elif custom_background_url:
        # Extract R2 key from URL and download
        key = custom_background_url.split("/", 3)[-1] if "/" in custom_background_url else custom_background_url
        background_bytes = r2.download_bytes(key)
    else:
        raise ValueError("Either print_name or custom_background_url required")

    # Download photos referenced in layout
    import httpx

    for photo in layout.get("photos", []):
        if "url" in photo and "image_bytes" not in photo:
            try:
                resp = httpx.get(photo["url"], timeout=30)
                photo["image_bytes"] = resp.content
            except Exception as e:
                logger.warning("Failed to download photo %s: %s", photo.get("url"), e)

    # Generate preview JPEG
    proof_bytes = compositor.composite_layout(
        background_bytes, layout, output_width=2400, for_print=False
    )
    preset = print_name.replace(" ", "_").replace("—", "-") if print_name else "custom"
    proof_key = f"output/{order_id}/{preset}_proof.jpg"
    proof_url = r2.upload_bytes(proof_bytes, proof_key, "image/jpeg")

    # Generate print TIF
    tif_bytes = compositor.composite_layout(
        background_bytes, layout, output_width=4800, for_print=True
    )
    tif_key = f"output/{order_id}/{preset}_final.tif"
    tif_url = r2.upload_bytes(tif_bytes, tif_key, "image/tiff")

    return {"proof_url": proof_url, "tif_url": tif_url}


def generate_legacy_proof_async(
    task_id: str,
    order_id: str,
    print_name: str,
    is_urn: bool,
    name: str | None,
    dates: str | None,
    additional: str | None,
) -> None:
    """Background task: auto-generate a legacy proof for a new order.

    Called via FastAPI BackgroundTasks after order creation.
    """
    from app.database import SessionLocal
    from app.models.order_personalization_task import OrderPersonalizationTask

    db = SessionLocal()
    try:
        task = db.query(OrderPersonalizationTask).filter(OrderPersonalizationTask.id == task_id).first()
        if not task:
            return

        template = get_template(print_name, is_urn)
        if not template or not template["available"]:
            task.notes = "Template not yet available for this print — manual design required"
            task.status = "pending"
            db.commit()
            return

        # Get background
        bg_url = get_background_url(print_name, is_urn)

        # Build default layout
        layout = {
            "photos": [],
            "text": {
                "name": name or "",
                "dates": dates or "",
                "additional": additional or "",
                "x": 0.75,
                "y": 0.50,
                "font_size": 0.07,
                "color": template.get("default_text_color", "white"),
                "shadow": True,
            },
        }

        # Generate proof
        result = generate_final(
            order_id=order_id,
            layout=layout,
            print_name=print_name,
            is_urn=is_urn,
        )

        task.proof_url = result["proof_url"]
        task.tif_url = result["tif_url"]
        task.default_layout = layout
        task.status = "in_progress"  # proof generated, awaiting review
        db.commit()

    except TemplateNotAvailable:
        try:
            task = db.query(OrderPersonalizationTask).filter(OrderPersonalizationTask.id == task_id).first()
            if task:
                task.notes = "Template not yet available for this print — manual design required"
                task.status = "pending"
                db.commit()
        except Exception:
            pass
    except Exception as e:
        logger.exception("Failed to auto-generate legacy proof for task %s: %s", task_id, e)
        try:
            task = db.query(OrderPersonalizationTask).filter(OrderPersonalizationTask.id == task_id).first()
            if task:
                task.notes = f"Auto-generation failed: {e}"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def get_available_prints(is_urn: bool = False) -> list[dict]:
    """Return available templates with background URLs if cached."""
    templates = get_available_templates(is_urn)
    result = []
    for t in templates:
        bg_url = None
        try:
            if r2.exists(t["cache_key"]):
                bg_url = r2.get_public_url(t["cache_key"])
        except Exception:
            pass
        result.append({
            "print_name": t["print_name"],
            "is_urn": is_urn,
            "available": t["available"],
            "background_url": bg_url,
            "default_text_color": t["default_text_color"],
        })
    return result
