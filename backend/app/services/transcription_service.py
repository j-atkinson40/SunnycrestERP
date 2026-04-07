"""Transcription service — Deepgram integration for Call Intelligence.

Handles post-call recording transcription via Deepgram Nova-2.
Live streaming transcription (Phase 2) noted but not yet implemented.
"""

import logging

import httpx
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.models.ringcentral_call_log import RingCentralCallLog

logger = logging.getLogger(__name__)

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"


def transcribe_recording(audio_bytes: bytes, content_type: str = "audio/mpeg") -> str | None:
    """Transcribe audio bytes via Deepgram Nova-2 with speaker diarization.

    Returns formatted transcript with speaker labels, or None on failure.
    """
    api_key = getattr(app_settings, "DEEPGRAM_API_KEY", "") or ""
    if not api_key:
        logger.warning("DEEPGRAM_API_KEY not configured — skipping transcription")
        return None

    try:
        resp = httpx.post(
            DEEPGRAM_URL,
            params={
                "model": "nova-2",
                "language": "en-US",
                "punctuate": "true",
                "diarize": "true",
                "utterances": "true",
                "smart_format": "true",
            },
            headers={
                "Authorization": f"Token {api_key}",
                "Content-Type": content_type,
            },
            content=audio_bytes,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.exception("Deepgram transcription request failed")
        return None

    # Format with speaker labels from utterances
    utterances = data.get("results", {}).get("utterances", [])
    if utterances:
        lines = []
        for utt in utterances:
            speaker = utt.get("speaker", 0)
            text = utt.get("transcript", "").strip()
            if text:
                lines.append(f"SPEAKER {speaker}: {text}")
        return "\n".join(lines) if lines else None

    # Fallback to plain transcript if no utterances
    transcript = (
        data.get("results", {})
        .get("channels", [{}])[0]
        .get("alternatives", [{}])[0]
        .get("transcript", "")
    )
    return transcript if transcript else None


def fetch_rc_recording(rc_token: str, recording_id: str) -> bytes | None:
    """Fetch recording audio from RingCentral API.

    Args:
        rc_token: Valid RingCentral access token
        recording_id: RingCentral recording ID

    Returns:
        Audio bytes or None on failure.
    """
    url = f"https://platform.ringcentral.com/restapi/v1.0/account/~/recording/{recording_id}/content"
    try:
        resp = httpx.get(
            url,
            headers={"Authorization": f"Bearer {rc_token}"},
            follow_redirects=True,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.content
    except Exception:
        logger.exception("Failed to fetch RC recording %s", recording_id)
        return None


def get_call_transcript(
    db: Session,
    tenant_id: str,
    call_id: str,
    rc_token: str | None = None,
) -> str | None:
    """Full transcription pipeline for a call log entry.

    1. Fetch recording from RingCentral
    2. Transcribe via Deepgram
    3. Save to call log record
    """
    call_log = (
        db.query(RingCentralCallLog)
        .filter(RingCentralCallLog.id == call_id, RingCentralCallLog.tenant_id == tenant_id)
        .first()
    )
    if not call_log:
        logger.warning("Call log %s not found for tenant %s", call_id, tenant_id)
        return None

    # Return cached transcript if available
    if call_log.transcription:
        return call_log.transcription

    # Need recording ID and RC token to fetch audio
    if not call_log.rc_recording_id:
        logger.info("No recording ID for call %s — skipping transcription", call_id)
        return None

    if not rc_token:
        logger.warning("No RC token available for recording fetch — call %s", call_id)
        return None

    # Fetch recording audio
    audio_bytes = fetch_rc_recording(rc_token, call_log.rc_recording_id)
    if not audio_bytes:
        return None

    # Transcribe
    transcript = transcribe_recording(audio_bytes)
    if not transcript:
        logger.warning("Transcription returned empty for call %s", call_id)
        return None

    # Save
    call_log.transcription = transcript
    call_log.transcription_source = "deepgram"
    db.commit()

    logger.info("Transcribed call %s — %d chars", call_id, len(transcript))
    return transcript


# ---------------------------------------------------------------------------
# Phase 2 — Live streaming transcription (not yet implemented)
# ---------------------------------------------------------------------------
# Would use Deepgram websocket streaming during active call for real-time
# overlay. Build after post-call path is proven.
# See: https://developers.deepgram.com/docs/getting-started-with-live-streaming-audio
