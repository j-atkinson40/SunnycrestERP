"""Legacy delivery service — Dropbox, Google Drive, print shop email, deadline calc."""

import logging
import uuid
from datetime import date, timedelta, datetime, timezone

from sqlalchemy.orm import Session

from app.models.legacy_proof import LegacyProof
from app.models.legacy_settings import LegacySettings, LegacyPrintShopContact

logger = logging.getLogger(__name__)


# ── Deadline calculation ─────────────────────────────────────────────────────

def calculate_print_deadline(service_date: date, days_before: int = 1) -> dict:
    """Calculate print deadline, skipping weekends."""
    deadline = service_date - timedelta(days=days_before)
    # If weekend, move to previous Friday
    while deadline.weekday() >= 5:  # 5=Sat, 6=Sun
        deadline -= timedelta(days=1)
    return {
        "date": deadline,
        "formatted": deadline.strftime("%A, %B %-d"),
        "is_past": deadline < date.today(),
        "is_today": deadline == date.today(),
    }


def format_tif_filename(template: str, legacy: LegacyProof, customer_name: str = "") -> str:
    """Format TIF filename from template."""
    return (
        template
        .replace("{print_name}", legacy.print_name or "Custom")
        .replace("{name}", legacy.inscription_name or "Unknown")
        .replace("{dates}", legacy.inscription_dates or "")
        .replace("{fh_name}", customer_name or "")
        .replace("{date}", date.today().strftime("%Y-%m-%d"))
        .strip()
    )


# ── Settings helpers ─────────────────────────────────────────────────────────

def get_or_create_settings(db: Session, company_id: str) -> LegacySettings:
    """Get or create legacy settings for a company."""
    settings = db.query(LegacySettings).filter(LegacySettings.company_id == company_id).first()
    if not settings:
        settings = LegacySettings(id=str(uuid.uuid4()), company_id=company_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def get_print_shop_contacts(db: Session, company_id: str) -> list[LegacyPrintShopContact]:
    """Get print shop contacts for a company."""
    return (
        db.query(LegacyPrintShopContact)
        .filter(LegacyPrintShopContact.company_id == company_id)
        .order_by(LegacyPrintShopContact.is_primary.desc())
        .all()
    )


# ── Dropbox ──────────────────────────────────────────────────────────────────

def dropbox_get_auth_url(company_id: str) -> str:
    """Generate Dropbox OAuth authorization URL."""
    from app.config import settings as app_settings
    if not app_settings.DROPBOX_APP_KEY:
        raise RuntimeError("Dropbox not configured — set DROPBOX_APP_KEY")

    from urllib.parse import urlencode
    params = {
        "client_id": app_settings.DROPBOX_APP_KEY,
        "response_type": "code",
        "redirect_uri": f"{app_settings.FRONTEND_URL.rstrip('/')}/api/v1/legacy/auth/dropbox/callback",
        "state": company_id,
        "token_access_type": "offline",
    }
    return f"https://www.dropbox.com/oauth2/authorize?{urlencode(params)}"


def dropbox_handle_callback(db: Session, code: str, company_id: str) -> None:
    """Exchange Dropbox auth code for tokens."""
    from app.config import settings as app_settings
    import requests

    resp = requests.post("https://api.dropboxapi.com/oauth2/token", data={
        "code": code,
        "grant_type": "authorization_code",
        "client_id": app_settings.DROPBOX_APP_KEY,
        "client_secret": app_settings.DROPBOX_APP_SECRET,
        "redirect_uri": f"{app_settings.FRONTEND_URL.rstrip('/')}/api/v1/legacy/auth/dropbox/callback",
    })
    resp.raise_for_status()
    tokens = resp.json()

    settings = get_or_create_settings(db, company_id)
    settings.dropbox_connected = True
    settings.dropbox_access_token = tokens.get("access_token")
    settings.dropbox_refresh_token = tokens.get("refresh_token")
    db.commit()


def dropbox_upload_tif(db: Session, company_id: str, file_bytes: bytes, filename: str) -> str:
    """Upload TIF to Dropbox. Returns shared link URL."""
    settings = get_or_create_settings(db, company_id)
    if not settings.dropbox_connected or not settings.dropbox_access_token:
        raise RuntimeError("Dropbox not connected")

    import requests
    folder = settings.dropbox_target_folder or "/Bridgeable Legacies"
    path = f"{folder}/{filename}"

    # Upload
    resp = requests.post(
        "https://content.dropboxapi.com/2/files/upload",
        headers={
            "Authorization": f"Bearer {settings.dropbox_access_token}",
            "Dropbox-API-Arg": f'{{"path":"{path}","mode":"overwrite"}}',
            "Content-Type": "application/octet-stream",
        },
        data=file_bytes,
    )
    if resp.status_code == 401:
        raise RuntimeError("Dropbox token expired — reconnect required")
    resp.raise_for_status()

    # Create shared link
    link_resp = requests.post(
        "https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings",
        headers={"Authorization": f"Bearer {settings.dropbox_access_token}", "Content-Type": "application/json"},
        json={"path": path, "settings": {"requested_visibility": "public"}},
    )
    if link_resp.status_code == 409:
        # Link already exists
        existing = requests.post(
            "https://api.dropboxapi.com/2/sharing/list_shared_links",
            headers={"Authorization": f"Bearer {settings.dropbox_access_token}", "Content-Type": "application/json"},
            json={"path": path},
        )
        links = existing.json().get("links", [])
        if links:
            return links[0].get("url", "")
    elif link_resp.ok:
        return link_resp.json().get("url", "")

    return ""


# ── Google Drive ─────────────────────────────────────────────────────────────

def gdrive_get_auth_url(company_id: str) -> str:
    """Generate Google Drive OAuth URL."""
    from app.config import settings as app_settings
    if not app_settings.GDRIVE_CLIENT_ID:
        raise RuntimeError("Google Drive not configured — set GDRIVE_CLIENT_ID")

    from urllib.parse import urlencode
    params = {
        "client_id": app_settings.GDRIVE_CLIENT_ID,
        "redirect_uri": f"{app_settings.FRONTEND_URL.rstrip('/')}/api/v1/legacy/auth/gdrive/callback",
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/drive.file",
        "access_type": "offline",
        "state": company_id,
        "prompt": "consent",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def gdrive_handle_callback(db: Session, code: str, company_id: str) -> None:
    """Exchange Google auth code for tokens."""
    from app.config import settings as app_settings
    import requests

    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": app_settings.GDRIVE_CLIENT_ID,
        "client_secret": app_settings.GDRIVE_CLIENT_SECRET,
        "redirect_uri": f"{app_settings.FRONTEND_URL.rstrip('/')}/api/v1/legacy/auth/gdrive/callback",
        "grant_type": "authorization_code",
    })
    resp.raise_for_status()
    tokens = resp.json()

    settings = get_or_create_settings(db, company_id)
    settings.gdrive_connected = True
    settings.gdrive_access_token = tokens.get("access_token")
    settings.gdrive_refresh_token = tokens.get("refresh_token")
    db.commit()


def gdrive_upload_tif(db: Session, company_id: str, file_bytes: bytes, filename: str) -> str:
    """Upload TIF to Google Drive. Returns shareable link URL."""
    settings = get_or_create_settings(db, company_id)
    if not settings.gdrive_connected or not settings.gdrive_access_token:
        raise RuntimeError("Google Drive not connected")

    import requests
    import json

    metadata = {"name": filename}
    if settings.gdrive_folder_id:
        metadata["parents"] = [settings.gdrive_folder_id]

    # Multipart upload
    boundary = "legacy_upload_boundary"
    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: image/tiff\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--".encode()

    resp = requests.post(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
        headers={
            "Authorization": f"Bearer {settings.gdrive_access_token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
        },
        data=body,
    )
    if resp.status_code == 401:
        raise RuntimeError("Google Drive token expired — reconnect required")
    resp.raise_for_status()
    file_id = resp.json().get("id", "")

    # Make shareable
    if file_id:
        requests.post(
            f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions",
            headers={"Authorization": f"Bearer {settings.gdrive_access_token}", "Content-Type": "application/json"},
            json={"role": "reader", "type": "anyone"},
        )
        return f"https://drive.google.com/file/d/{file_id}/view"

    return ""


# ── Auto-delivery on approval ────────────────────────────────────────────────

def run_auto_delivery(db: Session, legacy_proof_id: str, company_id: str) -> None:
    """Run auto-delivery checks after approval (Dropbox + Drive)."""
    try:
        settings = get_or_create_settings(db, company_id)
        proof = db.query(LegacyProof).filter(LegacyProof.id == legacy_proof_id).first()
        if not proof or not proof.tif_url:
            return

        # Download TIF from R2
        from app.services import legacy_r2_client as r2
        tif_key = proof.tif_url.rsplit("/", 1)[-1] if "/" in proof.tif_url else proof.tif_url

        # Build filename
        customer_name = ""
        if proof.customer_id:
            from app.models.customer import Customer
            cust = db.query(Customer).filter(Customer.id == proof.customer_id).first()
            if cust:
                customer_name = cust.name
        filename = format_tif_filename(
            settings.tif_filename_template or "{print_name} - {name}.tif",
            proof, customer_name
        )

        tif_bytes = None

        # Dropbox auto-save
        if settings.dropbox_connected and settings.dropbox_auto_save:
            try:
                if tif_bytes is None:
                    tif_bytes = r2.download_bytes(f"output/{proof.order_id or proof.id}/{tif_key}")
                url = dropbox_upload_tif(db, company_id, tif_bytes, filename)
                proof.dropbox_file_url = url
                proof.tif_saved_to_dropbox_at = datetime.now(timezone.utc)
                db.commit()
            except Exception as e:
                logger.warning("Dropbox auto-save failed for %s: %s", legacy_proof_id, e)

        # Drive auto-save
        if settings.gdrive_connected and settings.gdrive_auto_save:
            try:
                if tif_bytes is None:
                    tif_bytes = r2.download_bytes(f"output/{proof.order_id or proof.id}/{tif_key}")
                url = gdrive_upload_tif(db, company_id, tif_bytes, filename)
                proof.drive_file_url = url
                proof.tif_saved_to_drive_at = datetime.now(timezone.utc)
                db.commit()
            except Exception as e:
                logger.warning("Drive auto-save failed for %s: %s", legacy_proof_id, e)

    except Exception as e:
        logger.exception("Auto-delivery failed for legacy %s: %s", legacy_proof_id, e)
