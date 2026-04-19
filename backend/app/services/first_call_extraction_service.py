"""First call extraction — Intelligence-layer wrapper for funeral intake extraction.

Phase 2c-2 migration: routes through the managed `scribe.extract_first_call`
prompt. Field taxonomy is distinct from `scribe.extract_case_fields` (this is
pre-case-creation first-call intake; the Scribe prompt operates on arrangement
conferences) — intentionally kept as separate prompts.
"""

import json
import logging
from datetime import date

from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)


def extract_first_call(
    db: Session,
    text: str,
    existing_values: dict | None = None,
    *,
    company_id: str | None = None,
) -> dict:
    """Extract structured first call data from natural language text.

    Returns: {
        "extracted": {field: {"value": ..., "confidence": float, "is_new": bool}},
        "not_extracted": [field_names],
        "fields_updated": int
    }

    caller_entity_id is intentionally null — the FuneralCase hasn't been
    created yet at first-call extraction time.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    existing = existing_values or {}
    today = date.today().isoformat()

    from app.services.intelligence import intelligence_service

    result = intelligence_service.execute(
        db,
        prompt_key="scribe.extract_first_call",
        variables={
            "text": text,
            "existing_values": json.dumps(existing),
            "today": today,
        },
        company_id=company_id,
        caller_module="first_call_extraction_service.extract_first_call",
        caller_entity_type="funeral_case",  # case not yet created
        caller_entity_id=None,
        caller_fh_case_id=None,
    )

    if result.status != "success" or not isinstance(result.response_parsed, dict):
        logger.warning(
            "First-call extraction failed: status=%s error=%s",
            result.status, result.error_message,
        )
        return {"extracted": {}, "not_extracted": [], "fields_updated": 0}

    parsed = result.response_parsed
    raw_extracted = parsed.get("extracted", {})

    # All possible fields
    ALL_FIELDS = [
        "deceased_first_name",
        "deceased_last_name",
        "deceased_date_of_death",
        "deceased_time_of_death",
        "deceased_place_of_death",
        "deceased_place_of_death_name",
        "deceased_place_of_death_city",
        "deceased_place_of_death_state",
        "deceased_age_at_death",
        "deceased_veteran",
        "contact_first_name",
        "contact_last_name",
        "contact_relationship",
        "contact_phone_primary",
        "contact_phone_secondary",
        "contact_email",
        "disposition_type",
        "service_type",
        "disposition_location",
        "notes",
    ]

    # Mark is_new based on whether the value differs from existing
    result_extracted = {}
    fields_updated = 0

    for field, data in raw_extracted.items():
        if not isinstance(data, dict) or "value" not in data:
            continue
        confidence = data.get("confidence", 0.5)
        value = data["value"]

        is_new = field not in existing or str(existing.get(field, "")) != str(value)
        result_extracted[field] = {
            "value": value,
            "confidence": confidence,
            "is_new": is_new,
        }
        if is_new and confidence >= 0.75:
            fields_updated += 1

    not_extracted = [f for f in ALL_FIELDS if f not in result_extracted]

    return {
        "extracted": result_extracted,
        "not_extracted": not_extracted,
        "fields_updated": fields_updated,
    }
