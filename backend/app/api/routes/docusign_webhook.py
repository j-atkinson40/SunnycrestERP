"""DocuSign Connect webhook receiver with HMAC signature validation.

Receives events: envelope-sent, recipient-completed, recipient-declined,
envelope-completed. Validates X-DocuSign-Signature-1 HMAC header.

No tenant auth — DocuSign calls this directly.
"""

import hashlib
import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.database import get_db
from app.services import disinterment_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_hmac_key() -> str | None:
    """Get the DocuSign Connect HMAC key from app settings.

    Set via DOCUSIGN_HMAC_KEY env var or tenant settings.
    """
    return getattr(app_settings, "DOCUSIGN_HMAC_KEY", None) or ""


def _validate_hmac_signature(request_body: bytes, signature_header: str) -> bool:
    """Validate the X-DocuSign-Signature-1 HMAC-SHA256 header."""
    hmac_key = _get_hmac_key()
    if not hmac_key:
        # No HMAC key configured — skip validation in dev
        env = getattr(app_settings, "ENVIRONMENT", "dev")
        if env != "production":
            logger.warning("DocuSign HMAC key not configured — skipping validation (dev mode)")
            return True
        return False

    import base64

    expected = hmac.new(
        hmac_key.encode("utf-8"),
        request_body,
        hashlib.sha256,
    ).digest()
    expected_b64 = base64.b64encode(expected).decode("utf-8")

    return hmac.compare_digest(expected_b64, signature_header)


def _extract_recipient_events(payload: dict) -> list[tuple[str, str]]:
    """Extract (signer_role, event) pairs from a DocuSign Connect payload.

    DocuSign sends XML or JSON — we parse JSON here.
    Handles both envelope-level and recipient-level events.
    """
    events = []

    # Recipient-level events
    recipients = payload.get("recipients", {})
    signers = recipients.get("signers", [])
    for signer in signers:
        role = signer.get("roleName", "")
        status = signer.get("status", "")
        if role and status:
            events.append((role, status))

    # Also check envelope status
    envelope_status = payload.get("status", "")
    if envelope_status == "completed":
        # When envelope completes, all signers are done
        for signer in signers:
            role = signer.get("roleName", "")
            if role:
                events.append((role, "Completed"))

    return events


@router.post("/webhook")
async def docusign_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """DocuSign Connect webhook receiver.

    Validates HMAC signature, extracts signer events, and updates
    disinterment case signature status.
    """
    body = await request.body()

    # Validate HMAC signature
    signature_header = request.headers.get("X-DocuSign-Signature-1", "")
    if not _validate_hmac_signature(body, signature_header):
        logger.warning("DocuSign webhook: invalid HMAC signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        logger.error("DocuSign webhook: failed to parse JSON body")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    envelope_id = payload.get("envelopeId") or payload.get("envelope_id", "")
    if not envelope_id:
        logger.warning("DocuSign webhook: no envelope ID in payload")
        return {"status": "ignored", "reason": "no envelope_id"}

    # Extract and process events
    events = _extract_recipient_events(payload)
    if not events:
        # Try simple event format
        signer_role = payload.get("signerRole", payload.get("role_name", ""))
        event_status = payload.get("event", payload.get("status", ""))
        if signer_role and event_status:
            events = [(signer_role, event_status)]

    processed = 0
    for signer_role, event in events:
        disinterment_service.handle_docusign_webhook(
            db, envelope_id, signer_role, event
        )
        processed += 1

    logger.info(
        "DocuSign webhook processed: envelope=%s, events=%d",
        envelope_id,
        processed,
    )
    return {"status": "ok", "processed": processed}
