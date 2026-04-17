"""Scribe service — extract case fields from arrangement conference transcripts.

Phase 1 (this build): Review Mode only. Transcript is provided already (either
from uploaded audio processed elsewhere, or typed/spoken text).
Phase 2 would add live streaming via Deepgram.

Extraction flow:
  1. POST /fh/cases/:id/scribe/process  (transcript text)
  2. Claude parses into structured JSON with per-field confidence
  3. High-confidence (>= 0.9) fields auto-populate
  4. Medium-confidence (0.7–0.9) fields flagged amber for director review
  5. Low-confidence (< 0.7) fields skipped, noted for review
  6. funeral_case_notes row created with note_type='scribe_extraction'
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.funeral_case import (
    CaseDeceased,
    CaseDisposition,
    CaseInformant,
    CaseService,
    CaseVeteran,
    FuneralCase,
    FuneralCaseNote,
)
from app.services.fh import crypto


SCRIBE_SYSTEM_PROMPT = """You extract funeral arrangement conference details from a transcript or notes.

Return strict JSON matching this schema exactly:
{
  "deceased": {
    "first_name": {"value": string|null, "confidence": 0.0-1.0},
    "middle_name": {"value": string|null, "confidence": 0.0-1.0},
    "last_name": {"value": string|null, "confidence": 0.0-1.0},
    "date_of_birth": {"value": "YYYY-MM-DD"|null, "confidence": 0.0-1.0},
    "date_of_death": {"value": "YYYY-MM-DD"|null, "confidence": 0.0-1.0},
    "sex": {"value": "male"|"female"|"other"|null, "confidence": 0.0-1.0},
    "religion": {"value": string|null, "confidence": 0.0-1.0},
    "occupation": {"value": string|null, "confidence": 0.0-1.0},
    "marital_status": {"value": string|null, "confidence": 0.0-1.0},
    "place_of_death_name": {"value": string|null, "confidence": 0.0-1.0},
    "residence_city": {"value": string|null, "confidence": 0.0-1.0},
    "residence_state": {"value": string|null, "confidence": 0.0-1.0}
  },
  "service": {
    "service_type": {"value": string|null, "confidence": 0.0-1.0},
    "service_date": {"value": "YYYY-MM-DD"|null, "confidence": 0.0-1.0},
    "service_location_name": {"value": string|null, "confidence": 0.0-1.0},
    "officiant_name": {"value": string|null, "confidence": 0.0-1.0}
  },
  "disposition": {
    "disposition_type": {"value": "burial"|"cremation"|"entombment"|"donation"|"other"|null, "confidence": 0.0-1.0}
  },
  "veteran": {
    "ever_in_armed_forces": {"value": true|false|null, "confidence": 0.0-1.0},
    "branch": {"value": string|null, "confidence": 0.0-1.0}
  },
  "informants": [
    {"name": string, "relationship": string, "phone": string|null, "email": string|null, "is_primary": bool, "confidence": 0.0-1.0}
  ]
}

Rules:
- Only extract what was EXPLICITLY mentioned. Never infer.
- High confidence (>=0.9): stated clearly and unambiguously.
- Medium (0.7-0.9): reasonable interpretation of what was said.
- Low (<0.7): unclear — likely needs director review.
- Return null for fields not mentioned.
- Return valid JSON only. No prose, no markdown, no backticks.
"""


def _call_claude_extract(transcript: str) -> dict:
    """Call Claude API to extract fields. Returns empty dict on error."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {}
    try:
        from anthropic import Anthropic
    except ImportError:
        return {}

    client = Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=SCRIBE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": transcript}],
        )
        text = resp.content[0].text if resp.content else ""
        # Strip any accidental markdown fencing
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
        return json.loads(text)
    except Exception:
        return {}


def _apply_extraction(
    db: Session,
    case_id: str,
    company_id: str,
    extraction: dict,
    director_id: str | None,
    auto_threshold: float = 0.9,
) -> dict:
    """Apply Scribe extraction to case records. Returns summary of changes."""
    applied = {"auto_applied": 0, "needs_review": 0, "skipped": 0}

    # Deceased
    dec_extract = extraction.get("deceased") or {}
    if dec_extract:
        dec = db.query(CaseDeceased).filter(CaseDeceased.case_id == case_id).first()
        if dec:
            confidence_map: dict[str, float] = {}
            for field_key in [
                "first_name", "middle_name", "last_name", "date_of_birth", "date_of_death",
                "sex", "religion", "occupation", "marital_status", "place_of_death_name",
                "residence_city", "residence_state",
            ]:
                entry = dec_extract.get(field_key)
                if not entry or not isinstance(entry, dict):
                    continue
                value = entry.get("value")
                conf = float(entry.get("confidence") or 0)
                if value is None:
                    continue
                if conf >= auto_threshold:
                    # Coerce dates
                    if field_key in ("date_of_birth", "date_of_death") and isinstance(value, str):
                        try:
                            from datetime import date as _date
                            value = _date.fromisoformat(value)
                        except Exception:
                            continue
                    setattr(dec, field_key, value)
                    confidence_map[field_key] = conf
                    applied["auto_applied"] += 1
                elif conf >= 0.7:
                    confidence_map[field_key] = conf
                    applied["needs_review"] += 1
                else:
                    applied["skipped"] += 1
            dec.field_confidence = confidence_map

    # Service
    svc_extract = extraction.get("service") or {}
    if svc_extract:
        svc = db.query(CaseService).filter(CaseService.case_id == case_id).first()
        if svc:
            for field_key in ["service_type", "service_location_name", "officiant_name"]:
                entry = svc_extract.get(field_key)
                if isinstance(entry, dict) and entry.get("value") and (entry.get("confidence") or 0) >= auto_threshold:
                    setattr(svc, field_key, entry["value"])
                    applied["auto_applied"] += 1
                elif isinstance(entry, dict) and entry.get("value"):
                    applied["needs_review"] += 1
            # service_date
            sd = svc_extract.get("service_date")
            if isinstance(sd, dict) and sd.get("value") and (sd.get("confidence") or 0) >= auto_threshold:
                try:
                    from datetime import date as _date
                    svc.service_date = _date.fromisoformat(sd["value"])
                    applied["auto_applied"] += 1
                except Exception:
                    pass

    # Disposition
    disp_extract = extraction.get("disposition") or {}
    if disp_extract:
        disp_entry = disp_extract.get("disposition_type")
        if isinstance(disp_entry, dict) and disp_entry.get("value") and (disp_entry.get("confidence") or 0) >= auto_threshold:
            disp = db.query(CaseDisposition).filter(CaseDisposition.case_id == case_id).first()
            if disp:
                disp.disposition_type = disp_entry["value"]
                applied["auto_applied"] += 1

    # Veteran
    vet_extract = extraction.get("veteran") or {}
    if vet_extract:
        vet = db.query(CaseVeteran).filter(CaseVeteran.case_id == case_id).first()
        if vet:
            e = vet_extract.get("ever_in_armed_forces")
            if isinstance(e, dict) and e.get("value") is not None and (e.get("confidence") or 0) >= auto_threshold:
                vet.ever_in_armed_forces = bool(e["value"])
                applied["auto_applied"] += 1
            b = vet_extract.get("branch")
            if isinstance(b, dict) and b.get("value") and (b.get("confidence") or 0) >= auto_threshold:
                vet.branch = b["value"]
                applied["auto_applied"] += 1

    # Informants (append — never replace existing)
    informants = extraction.get("informants") or []
    existing_names = {
        i.name.lower().strip()
        for i in db.query(CaseInformant).filter(CaseInformant.case_id == case_id).all()
    }
    for inf in informants:
        if not isinstance(inf, dict):
            continue
        name = (inf.get("name") or "").strip()
        conf = float(inf.get("confidence") or 0)
        if not name or conf < 0.7 or name.lower() in existing_names:
            continue
        db.add(CaseInformant(
            id=str(uuid.uuid4()),
            case_id=case_id,
            company_id=company_id,
            name=name,
            relationship=inf.get("relationship"),
            phone=inf.get("phone"),
            email=inf.get("email"),
            is_primary=bool(inf.get("is_primary", False)),
        ))
        if conf >= auto_threshold:
            applied["auto_applied"] += 1
        else:
            applied["needs_review"] += 1

    # Note the extraction run
    db.add(FuneralCaseNote(
        id=str(uuid.uuid4()),
        case_id=case_id,
        company_id=company_id,
        note_type="scribe_extraction",
        content=f"Scribe extraction processed: "
                f"{applied['auto_applied']} auto-applied, "
                f"{applied['needs_review']} need review, "
                f"{applied['skipped']} skipped.",
        author_id=director_id,
        extraction_payload=extraction,
    ))

    db.commit()
    return applied


def process_transcript(
    db: Session,
    case_id: str,
    transcript: str,
    director_id: str | None = None,
) -> dict:
    """Process a full transcript through Claude extraction and apply to the case."""
    case = db.query(FuneralCase).filter(FuneralCase.id == case_id).first()
    if not case:
        raise ValueError("Case not found")

    extraction = _call_claude_extract(transcript)
    if not extraction:
        # No API key or Claude failed — still record the note
        db.add(FuneralCaseNote(
            id=str(uuid.uuid4()),
            case_id=case_id,
            company_id=case.company_id,
            note_type="scribe_extraction",
            content="Scribe run — no extraction (API unavailable or empty response). Transcript stored.",
            author_id=director_id,
        ))
        db.commit()
        return {"extraction": {}, "auto_applied": 0, "needs_review": 0, "skipped": 0}

    result = _apply_extraction(db, case_id, case.company_id, extraction, director_id)
    result["extraction"] = extraction
    return result


def extract_from_nl(
    db: Session,
    case_id: str,
    text: str,
    director_id: str | None = None,
) -> dict:
    """Natural language input extraction — same pipeline as transcript, different entry point."""
    return process_transcript(db, case_id, text, director_id)
