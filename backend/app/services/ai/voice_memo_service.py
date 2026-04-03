"""Voice memo service — transcription via Deepgram + AI extraction via Claude."""

import json
import logging
import uuid as _uuid
from datetime import date, timedelta

import httpx
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.models.activity_log import ActivityLog
from app.services import ai_settings_service

logger = logging.getLogger(__name__)


def transcribe_audio(audio_bytes: bytes, content_type: str = "audio/webm") -> str | None:
    """Transcribe audio using Deepgram Nova-2 batch API."""
    api_key = getattr(app_settings, "DEEPGRAM_API_KEY", "") or ""
    if not api_key:
        logger.warning("DEEPGRAM_API_KEY not configured")
        return None

    try:
        resp = httpx.post(
            "https://api.deepgram.com/v1/listen",
            params={"model": "nova-2", "smart_format": "true", "punctuate": "true"},
            headers={"Authorization": f"Token {api_key}", "Content-Type": content_type},
            content=audio_bytes,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        transcript = data.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "")
        return transcript if transcript else None
    except Exception:
        logger.exception("Deepgram transcription failed")
        return None


def extract_memo_data(transcript: str, company_context: str | None = None) -> dict:
    """Use Claude to extract structured data from a voice memo transcript."""
    try:
        from app.services.ai_service import call_anthropic
    except ImportError:
        return {"title": transcript[:100], "body": transcript, "activity_type": "note", "confidence": 0.5}

    prompt = f"""Extract structured data from this voice memo by a business owner/employee at a precast concrete manufacturer.

Return JSON only:
{{
  "activity_type": "call"|"visit"|"note"|"complaint"|"follow_up",
  "contact_name": string or null,
  "title": "brief 1-line summary",
  "body": "full cleaned-up notes",
  "outcome": string or null,
  "follow_up_needed": boolean,
  "follow_up_description": string or null,
  "follow_up_days": integer or null,
  "action_items": ["list of action items"]
}}

Voice memo transcript:
{transcript}

{f"Company context: {company_context}" if company_context else ""}"""

    response = call_anthropic(prompt, max_tokens=300)
    if not response:
        return {"title": transcript[:100], "body": transcript, "activity_type": "note", "confidence": 0.5}

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {"title": transcript[:100], "body": transcript, "activity_type": "note", "confidence": 0.5}


def process_voice_memo(
    db: Session,
    tenant_id: str,
    user_id: str,
    audio_bytes: bytes,
    master_company_id: str | None = None,
    content_type: str = "audio/webm",
) -> dict:
    """Full pipeline: transcribe → extract → create activity."""
    if not ai_settings_service.is_enabled(db, tenant_id, "voice_memo", user_id=user_id):
        return {"error": "Voice memo is disabled"}

    # Track usage (estimate ~1 minute per memo)
    ai_settings_service.track_usage(db, tenant_id, "transcription", 1)

    # Transcribe
    transcript = transcribe_audio(audio_bytes, content_type)
    if not transcript:
        return {"error": "Transcription failed — no speech detected"}

    # Get company context
    company_context = None
    if master_company_id:
        from app.models.company_entity import CompanyEntity
        entity = db.query(CompanyEntity).filter(CompanyEntity.id == master_company_id).first()
        if entity:
            company_context = f"{entity.name} ({entity.city}, {entity.state})"

    # Extract structured data
    memo_data = extract_memo_data(transcript, company_context)

    # Create activity
    follow_up_date = None
    if memo_data.get("follow_up_needed"):
        days = memo_data.get("follow_up_days") or 3
        follow_up_date = date.today() + timedelta(days=days)

    activity = ActivityLog(
        id=str(_uuid.uuid4()),
        tenant_id=tenant_id,
        master_company_id=master_company_id,
        logged_by=user_id,
        activity_type=memo_data.get("activity_type", "note"),
        title=memo_data.get("title", transcript[:100]),
        body=memo_data.get("body", transcript),
        outcome=memo_data.get("outcome"),
        follow_up_date=follow_up_date,
        follow_up_assigned_to=user_id if follow_up_date else None,
        source="voice_memo",
        transcript=transcript,
    )
    db.add(activity)
    db.flush()

    return {
        "activity_id": activity.id,
        "transcript": transcript,
        "title": memo_data.get("title", ""),
        "body": memo_data.get("body", ""),
        "activity_type": memo_data.get("activity_type", "note"),
        "follow_up_created": follow_up_date is not None,
        "follow_up_date": follow_up_date.isoformat() if follow_up_date else None,
        "action_items": memo_data.get("action_items", []),
    }
