"""First call extraction — uses Claude Haiku to extract structured intake data from natural language."""

import json
import logging
import re
from datetime import date, datetime

from app.config import settings

logger = logging.getLogger(__name__)

EXTRACTION_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024

SYSTEM_PROMPT = """You are extracting first call information for a funeral home intake form.
Extract only information explicitly stated. Do not infer or assume. Return JSON only. No other text.
Date references like "this morning", "last night", "yesterday" should be resolved relative to today's date.
Phone numbers should be formatted as entered, not reformatted.
Names should be capitalized correctly."""


def _build_user_prompt(text: str, existing_values: dict, today: str) -> str:
    return f"""Extract the following fields from this first call description.
For each field, provide the value and a confidence score (0-1).
Only extract fields where you have clear evidence in the text.

Fields to extract:
- deceased_first_name (string)
- deceased_last_name (string)
- deceased_date_of_death (ISO date YYYY-MM-DD — today is {today})
- deceased_time_of_death (HH:MM 24hr format)
- deceased_place_of_death (enum: hospital, home, nursing_facility, hospice, other)
- deceased_place_of_death_name (string — facility name if applicable)
- deceased_place_of_death_city (string)
- deceased_place_of_death_state (string — 2 letter code)
- deceased_age_at_death (integer)
- deceased_veteran (boolean)
- contact_first_name (string)
- contact_last_name (string)
- contact_relationship (enum: spouse, child, parent, sibling, other)
- contact_phone_primary (string)
- contact_phone_secondary (string)
- contact_email (string)
- disposition_type (enum: burial, cremation, green_burial, donation, entombment)
- service_type (enum: traditional_funeral, graveside_only, memorial_service, direct_burial, direct_cremation, celebration_of_life, no_service)
- disposition_location (string — cemetery name)
- notes (string — anything mentioned that doesn't fit other fields)

Current form values (do not re-extract these unless the new text contradicts them):
{json.dumps(existing_values)}

First call description:
{text}

Return JSON in this exact format:
{{
  "extracted": {{
    "field_name": {{"value": ..., "confidence": 0.0-1.0}}
  }}
}}
Only include fields where you found clear evidence. Omit fields with no evidence."""


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?\s*```$"
    match = re.match(pattern, stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def extract_first_call(text: str, existing_values: dict | None = None) -> dict:
    """Extract structured first call data from natural language text.

    Returns: {
        "extracted": {field: {"value": ..., "confidence": float, "is_new": bool}},
        "not_extracted": [field_names],
        "fields_updated": int
    }
    """
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    existing = existing_values or {}
    today = date.today().isoformat()

    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    message = client.messages.create(
        model=EXTRACTION_MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": _build_user_prompt(text, existing, today),
            }
        ],
    )

    response_text = message.content[0].text
    cleaned = _strip_code_fences(response_text)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse extraction JSON: {response_text[:200]}")
        return {"extracted": {}, "not_extracted": [], "fields_updated": 0}

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
