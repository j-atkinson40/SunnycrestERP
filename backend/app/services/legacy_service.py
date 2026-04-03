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
    order_id: str | None,
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
    import uuid as _uuid
    folder_id = order_id or str(_uuid.uuid4())[:12]
    preset = print_name.replace(" ", "_").replace("—", "-") if print_name else "custom"
    proof_key = f"output/{folder_id}/{preset}_proof.jpg"
    proof_url = r2.upload_bytes(proof_bytes, proof_key, "image/jpeg")

    # Generate print TIF
    tif_bytes = compositor.composite_layout(
        background_bytes, layout, output_width=4800, for_print=True
    )
    tif_key = f"output/{folder_id}/{preset}_final.tif"
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
    approved_layout: dict | None = None,
    family_approved: bool = False,
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

        # Use family-approved layout if available, otherwise build default
        if approved_layout and family_approved:
            layout = approved_layout
            # Ensure text fields are current
            if "text" in layout:
                layout["text"]["name"] = name or layout["text"].get("name", "")
                layout["text"]["dates"] = dates or layout["text"].get("dates", "")
                layout["text"]["additional"] = additional or layout["text"].get("additional", "")
        else:
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

        # Check for uploaded photos and incorporate into layout
        from app.models.order_personalization_photo import OrderPersonalizationPhoto

        photos = (
            db.query(OrderPersonalizationPhoto)
            .filter(OrderPersonalizationPhoto.order_id == order_id)
            .order_by(OrderPersonalizationPhoto.created_at)
            .all()
        )
        if photos:
            photo_layouts = []
            positions = [
                {"x": 0.35, "y": 0.50, "scale": 0.40, "opacity": 1.0},
                {"x": 0.25, "y": 0.35, "scale": 0.30, "opacity": 0.9},
                {"x": 0.20, "y": 0.60, "scale": 0.25, "opacity": 0.85},
                {"x": 0.30, "y": 0.65, "scale": 0.20, "opacity": 0.8},
            ]
            for i, photo in enumerate(photos[:4]):
                pos = positions[min(i, len(positions) - 1)]
                photo_layouts.append({
                    "url": photo.photo_url,
                    "x": pos["x"],
                    "y": pos["y"],
                    "scale": pos["scale"],
                    "opacity": pos["opacity"],
                    "style": "soft_fade",
                })
            layout["photos"] = photo_layouts
            # When photos exist, push text to the right
            if "text" in layout:
                layout["text"]["x"] = 0.75
                layout["text"]["y"] = 0.50

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

        # Create LegacyProof record so proof appears in Legacy Studio library
        import uuid as _uuid
        from app.models.legacy_proof import LegacyProof
        from app.models.sales_order import SalesOrder as _SalesOrder

        order_obj = db.query(_SalesOrder).filter(_SalesOrder.id == order_id).first()

        lp = LegacyProof(
            id=str(_uuid.uuid4()),
            company_id=task.company_id,
            source="order",
            order_id=order_id,
            personalization_task_id=task_id,
            legacy_type="custom" if task.is_custom_legacy else "standard",
            print_name=print_name,
            is_urn=is_urn,
            inscription_name=name,
            inscription_dates=dates,
            inscription_additional=additional,
            customer_id=order_obj.customer_id if order_obj else None,
            deceased_name=order_obj.deceased_name if order_obj else (name or None),
            service_date=getattr(order_obj, "service_date", None),
            proof_url=result["proof_url"],
            tif_url=result["tif_url"],
            background_url=bg_url,
            approved_layout=layout,
            status="proof_generated",
            family_approved=family_approved,
        )
        db.add(lp)
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
