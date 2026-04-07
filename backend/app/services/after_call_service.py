"""After-call service — orchestrates the post-call intelligence pipeline.

Triggered when a call ends (via webhook or manual reprocess):
  1. Wait for recording to become available
  2. Transcribe via Deepgram
  3. Extract order data via Claude
  4. Create draft order if applicable
  5. Emit SSE event to frontend

Also handles voicemail transcription.
"""

import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.ringcentral_call_log import RingCentralCallLog

logger = logging.getLogger(__name__)

# Delay before attempting recording fetch (RC needs time to process)
RECORDING_WAIT_SECONDS = 10


def process_call_after_end(
    db: Session,
    call_id: str,
    tenant_id: str,
    rc_token: str | None = None,
) -> dict:
    """Full post-call pipeline: transcribe → extract → draft order.

    Args:
        db: Database session
        call_id: ringcentral_call_log.id
        tenant_id: Tenant company ID
        rc_token: Valid RingCentral access token for recording fetch

    Returns:
        dict with pipeline results
    """
    call_log = (
        db.query(RingCentralCallLog)
        .filter(RingCentralCallLog.id == call_id, RingCentralCallLog.tenant_id == tenant_id)
        .first()
    )
    if not call_log:
        logger.warning("Call log %s not found", call_id)
        return {"error": "Call not found"}

    # Skip if order already created during the call
    if call_log.order_created:
        logger.info("Call %s already has order — skipping pipeline", call_id)
        return {"skipped": True, "reason": "order_already_created"}

    result: dict = {"call_id": call_id, "transcript": None, "extraction": None, "order_id": None}

    # Step 1 — Transcription
    transcript = call_log.transcription  # May already be cached
    if not transcript and call_log.rc_recording_id:
        # Brief wait for recording availability
        time.sleep(RECORDING_WAIT_SECONDS)

        from app.services.transcription_service import get_call_transcript

        transcript = get_call_transcript(db, tenant_id, call_id, rc_token)

    if not transcript:
        # No recording — create minimal extraction from caller info
        transcript = _build_minimal_context(call_log)
        if not transcript:
            logger.info("No transcript or context for call %s — skipping extraction", call_id)
            return result

    result["transcript"] = transcript

    # Step 2 — Claude extraction
    from app.services.call_extraction_service import (
        create_draft_order_from_extraction,
        extract_order_from_transcript,
    )

    extraction = extract_order_from_transcript(
        db=db,
        transcript=transcript,
        tenant_id=tenant_id,
        call_id=call_id,
        existing_company_id=call_log.company_entity_id,
    )
    result["extraction"] = {
        "id": extraction.id,
        "call_type": extraction.call_type,
        "urgency": extraction.urgency,
        "missing_fields": extraction.missing_fields,
        "funeral_home": extraction.funeral_home_name,
        "deceased": extraction.deceased_name,
        "vault_type": extraction.vault_type,
    }

    # Step 3 — Draft order creation
    if extraction.call_type == "order":
        order_id = create_draft_order_from_extraction(db, extraction, tenant_id)
        result["order_id"] = order_id

    db.commit()
    logger.info("After-call pipeline complete for %s — type=%s", call_id, extraction.call_type)
    return result


def process_voicemail(
    db: Session,
    call_id: str,
    tenant_id: str,
    rc_token: str | None = None,
    rc_voicemail_text: str | None = None,
) -> dict:
    """Handle voicemail: transcribe and extract.

    RC may provide its own voicemail transcription. If not, fetch audio
    and run through Deepgram.
    """
    call_log = (
        db.query(RingCentralCallLog)
        .filter(RingCentralCallLog.id == call_id, RingCentralCallLog.tenant_id == tenant_id)
        .first()
    )
    if not call_log:
        return {"error": "Call not found"}

    call_log.call_status = "voicemail"

    # Use RC-provided transcription if available
    transcript = rc_voicemail_text
    if not transcript and call_log.rc_recording_id:
        from app.services.transcription_service import get_call_transcript

        transcript = get_call_transcript(db, tenant_id, call_id, rc_token)

    if not transcript:
        logger.info("No voicemail transcript available for call %s", call_id)
        db.commit()
        return {"call_id": call_id, "transcript": None}

    call_log.transcription = transcript
    call_log.transcription_source = "ringcentral" if rc_voicemail_text else "deepgram"

    # Run extraction
    from app.services.call_extraction_service import (
        create_draft_order_from_extraction,
        extract_order_from_transcript,
    )

    extraction = extract_order_from_transcript(
        db=db,
        transcript=transcript,
        tenant_id=tenant_id,
        call_id=call_id,
        existing_company_id=call_log.company_entity_id,
    )

    order_id = None
    if extraction.call_type == "order":
        order_id = create_draft_order_from_extraction(db, extraction, tenant_id)

    db.commit()
    return {"call_id": call_id, "transcript": transcript, "order_id": order_id}


def reprocess_call(
    db: Session,
    call_id: str,
    tenant_id: str,
) -> dict:
    """Re-run Claude extraction on existing transcript.

    Useful when extraction missed something or prompt is updated.
    """
    call_log = (
        db.query(RingCentralCallLog)
        .filter(RingCentralCallLog.id == call_id, RingCentralCallLog.tenant_id == tenant_id)
        .first()
    )
    if not call_log:
        return {"error": "Call not found"}

    if not call_log.transcription:
        return {"error": "No transcript available for reprocessing"}

    from app.services.call_extraction_service import extract_order_from_transcript

    extraction = extract_order_from_transcript(
        db=db,
        transcript=call_log.transcription,
        tenant_id=tenant_id,
        call_id=call_id,
        existing_company_id=call_log.company_entity_id,
    )
    db.commit()

    return {
        "call_id": call_id,
        "extraction_id": extraction.id,
        "call_type": extraction.call_type,
        "missing_fields": extraction.missing_fields,
    }


def _build_minimal_context(call_log: RingCentralCallLog) -> str | None:
    """Build minimal context string from caller info when no transcript exists."""
    parts = []
    if call_log.caller_name:
        parts.append(f"Caller: {call_log.caller_name}")
    if call_log.caller_number:
        parts.append(f"Number: {call_log.caller_number}")
    if call_log.duration_seconds:
        mins = call_log.duration_seconds // 60
        secs = call_log.duration_seconds % 60
        parts.append(f"Duration: {mins}m {secs}s")
    if call_log.direction:
        parts.append(f"Direction: {call_log.direction}")

    if not parts:
        return None

    return "Call metadata (no recording available):\n" + "\n".join(parts)
