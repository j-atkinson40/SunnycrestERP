"""Legacy delivery API — settings, OAuth, Dropbox/Drive save, print shop."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.legacy_settings import LegacySettings, LegacyPrintShopContact
from app.models.legacy_proof import LegacyProof
from app.models.user import User
from app.services.legacy_delivery import (
    get_or_create_settings,
    get_print_shop_contacts,
    calculate_print_deadline,
    dropbox_get_auth_url,
    dropbox_handle_callback,
    dropbox_upload_tif,
    gdrive_get_auth_url,
    gdrive_handle_callback,
    gdrive_upload_tif,
    format_tif_filename,
)

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    print_deadline_days_before: int | None = None
    watermark_enabled: bool | None = None
    watermark_text: str | None = None
    watermark_opacity: float | None = None
    watermark_position: str | None = None
    tif_filename_template: str | None = None
    dropbox_target_folder: str | None = None
    dropbox_auto_save: bool | None = None
    gdrive_folder_id: str | None = None
    gdrive_folder_name: str | None = None
    gdrive_auto_save: bool | None = None
    print_shop_delivery: str | None = None


class ContactCreate(BaseModel):
    name: str
    email: str
    is_primary: bool = False


# ── Settings endpoints ────────────────────────────────────────────────────────

@router.get("/settings")
def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get legacy delivery settings."""
    s = get_or_create_settings(db, current_user.company_id)
    contacts = get_print_shop_contacts(db, current_user.company_id)
    return {
        "print_deadline_days_before": s.print_deadline_days_before,
        "watermark_enabled": s.watermark_enabled,
        "watermark_text": s.watermark_text,
        "watermark_opacity": float(s.watermark_opacity) if s.watermark_opacity else 0.3,
        "watermark_position": s.watermark_position,
        "tif_filename_template": s.tif_filename_template,
        "dropbox_connected": s.dropbox_connected,
        "dropbox_target_folder": s.dropbox_target_folder,
        "dropbox_auto_save": s.dropbox_auto_save,
        "gdrive_connected": s.gdrive_connected,
        "gdrive_folder_id": s.gdrive_folder_id,
        "gdrive_folder_name": s.gdrive_folder_name,
        "gdrive_auto_save": s.gdrive_auto_save,
        "print_shop_delivery": s.print_shop_delivery,
        "contacts": [
            {"id": c.id, "name": c.name, "email": c.email, "is_primary": c.is_primary}
            for c in contacts
        ],
    }


@router.patch("/settings")
def update_settings(
    data: SettingsUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update legacy delivery settings."""
    s = get_or_create_settings(db, current_user.company_id)
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(s, field, val)
    s.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"updated": True}


# ── Print shop contacts ───────────────────────────────────────────────────────

@router.post("/settings/contacts")
def add_contact(
    data: ContactCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    contact = LegacyPrintShopContact(
        id=str(uuid.uuid4()),
        company_id=current_user.company_id,
        name=data.name,
        email=data.email,
        is_primary=data.is_primary,
    )
    # If first contact, make primary
    existing = db.query(LegacyPrintShopContact).filter(
        LegacyPrintShopContact.company_id == current_user.company_id
    ).count()
    if existing == 0:
        contact.is_primary = True
    db.add(contact)
    db.commit()
    return {"id": contact.id}


@router.delete("/settings/contacts/{contact_id}")
def remove_contact(
    contact_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    contact = db.query(LegacyPrintShopContact).filter(
        LegacyPrintShopContact.id == contact_id,
        LegacyPrintShopContact.company_id == current_user.company_id,
    ).first()
    if contact:
        db.delete(contact)
        db.commit()
    return {"deleted": True}


# ── Dropbox OAuth ─────────────────────────────────────────────────────────────

@router.get("/auth/dropbox/connect")
def dropbox_connect(current_user: User = Depends(require_admin)):
    try:
        url = dropbox_get_auth_url(current_user.company_id)
        return {"auth_url": url}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/auth/dropbox/callback")
def dropbox_callback(
    code: str = Query(...),
    state: str = Query(""),
    db: Session = Depends(get_db),
):
    try:
        dropbox_handle_callback(db, code, state)
        return RedirectResponse(url="/legacy/settings?dropbox=connected")
    except Exception as e:
        return RedirectResponse(url=f"/legacy/settings?dropbox=error&msg={e}")


@router.delete("/auth/dropbox/disconnect")
def dropbox_disconnect(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    s = get_or_create_settings(db, current_user.company_id)
    s.dropbox_connected = False
    s.dropbox_access_token = None
    s.dropbox_refresh_token = None
    db.commit()
    return {"disconnected": True}


# ── Google Drive OAuth ────────────────────────────────────────────────────────

@router.get("/auth/gdrive/connect")
def gdrive_connect(current_user: User = Depends(require_admin)):
    try:
        url = gdrive_get_auth_url(current_user.company_id)
        return {"auth_url": url}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/auth/gdrive/callback")
def gdrive_callback(
    code: str = Query(...),
    state: str = Query(""),
    db: Session = Depends(get_db),
):
    try:
        gdrive_handle_callback(db, code, state)
        return RedirectResponse(url="/legacy/settings?gdrive=connected")
    except Exception as e:
        return RedirectResponse(url=f"/legacy/settings?gdrive=error&msg={e}")


@router.delete("/auth/gdrive/disconnect")
def gdrive_disconnect(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    s = get_or_create_settings(db, current_user.company_id)
    s.gdrive_connected = False
    s.gdrive_access_token = None
    s.gdrive_refresh_token = None
    db.commit()
    return {"disconnected": True}


# ── Manual delivery triggers ─────────────────────────────────────────────────

@router.post("/delivery/dropbox/{legacy_id}")
def save_to_dropbox(
    legacy_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually save TIF to Dropbox."""
    proof = db.query(LegacyProof).filter(
        LegacyProof.id == legacy_id, LegacyProof.company_id == current_user.company_id
    ).first()
    if not proof or not proof.tif_url:
        raise HTTPException(status_code=404, detail="No TIF available")

    settings = get_or_create_settings(db, current_user.company_id)
    filename = format_tif_filename(settings.tif_filename_template or "{print_name} - {name}.tif", proof)

    try:
        from app.services import legacy_r2_client as r2
        tif_key = proof.tif_url.rsplit("/", 1)[-1]
        tif_bytes = r2.download_bytes(f"output/{proof.order_id or proof.id}/{tif_key}")
        url = dropbox_upload_tif(db, current_user.company_id, tif_bytes, filename)
        proof.dropbox_file_url = url
        proof.tif_saved_to_dropbox_at = datetime.now(timezone.utc)
        db.commit()
        return {"dropbox_url": url}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/delivery/gdrive/{legacy_id}")
def save_to_gdrive(
    legacy_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually save TIF to Google Drive."""
    proof = db.query(LegacyProof).filter(
        LegacyProof.id == legacy_id, LegacyProof.company_id == current_user.company_id
    ).first()
    if not proof or not proof.tif_url:
        raise HTTPException(status_code=404, detail="No TIF available")

    settings = get_or_create_settings(db, current_user.company_id)
    filename = format_tif_filename(settings.tif_filename_template or "{print_name} - {name}.tif", proof)

    try:
        from app.services import legacy_r2_client as r2
        tif_key = proof.tif_url.rsplit("/", 1)[-1]
        tif_bytes = r2.download_bytes(f"output/{proof.order_id or proof.id}/{tif_key}")
        url = gdrive_upload_tif(db, current_user.company_id, tif_bytes, filename)
        proof.drive_file_url = url
        proof.tif_saved_to_drive_at = datetime.now(timezone.utc)
        db.commit()
        return {"drive_url": url}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
