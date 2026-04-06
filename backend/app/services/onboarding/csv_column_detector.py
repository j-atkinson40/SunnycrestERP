"""CSV column detection for cemetery and funeral home imports.

Uses rule-based alias matching first, falls back to Claude for ambiguous columns.
"""

import logging
from difflib import SequenceMatcher

from app.services.ai_service import call_anthropic

logger = logging.getLogger(__name__)

# ── Column alias maps ──────────────────────────────────────────────

CEMETERY_COLUMN_ALIASES: dict[str, list[str]] = {
    "name": [
        "name", "cemetery name", "cemetery", "location", "facility name",
        "full name", "legal name", "location name", "cem name",
    ],
    "address": [
        "address", "street", "address line 1", "addr", "street address",
        "location address", "address 1", "street 1",
    ],
    "city": [
        "city", "town", "municipality", "city name", "city/town",
    ],
    "state": [
        "state", "st", "province", "state code", "state/province",
    ],
    "zip": [
        "zip", "zip code", "postal", "postal code", "zipcode", "zip/postal code",
    ],
    "phone": [
        "phone", "telephone", "tel", "phone number", "main phone",
        "office phone", "contact phone", "phone #",
    ],
    "email": [
        "email", "e-mail", "email address", "contact email", "office email",
    ],
    "contact_name": [
        "contact", "contact name", "manager", "superintendent",
        "director", "contact person", "sexton",
    ],
    "county": [
        "county", "county name",
    ],
    "notes": [
        "notes", "comments", "remarks", "equipment", "equipment notes",
        "special instructions", "description",
    ],
}

FUNERAL_HOME_COLUMN_ALIASES: dict[str, list[str]] = {
    "name": [
        "name", "funeral home name", "funeral home", "company",
        "company name", "business name", "facility", "firm", "firm name",
    ],
    "address": [
        "address", "street", "address line 1", "addr", "street address",
        "location address", "address 1",
    ],
    "city": [
        "city", "town", "municipality", "city name",
    ],
    "state": [
        "state", "st", "province", "state code",
    ],
    "zip": [
        "zip", "zip code", "postal", "postal code", "zipcode",
    ],
    "phone": [
        "phone", "telephone", "tel", "phone number", "main phone",
        "office phone", "phone #",
    ],
    "email": [
        "email", "e-mail", "email address", "contact email",
    ],
    "director_name": [
        "director", "funeral director", "owner", "contact", "manager",
        "primary contact", "contact name",
    ],
    "license_number": [
        "license", "license number", "license #", "fdic", "license no",
        "lic #", "lic no",
    ],
    "fax": [
        "fax", "fax number", "fax #",
    ],
    "website": [
        "website", "web", "url", "web address",
    ],
    "notes": [
        "notes", "comments", "remarks",
    ],
}


def _similarity(a: str, b: str) -> float:
    """SequenceMatcher ratio between two lowercase stripped strings."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def detect_columns(
    headers: list[str],
    sample_rows: list[dict],
    import_type: str,  # "cemetery" | "funeral_home"
) -> dict:
    """Detect column mapping for a CSV file.

    Returns::

        {
            "field_map": {"name": "Cemetery Name", ...},
            "confidence": {"name": 0.99, ...},
            "unmapped_fields": [...],
            "extra_columns": [...],
        }
    """
    alias_map = CEMETERY_COLUMN_ALIASES if import_type == "cemetery" else FUNERAL_HOME_COLUMN_ALIASES

    field_map: dict[str, str] = {}
    confidence: dict[str, float] = {}
    used_headers: set[str] = set()

    # ── Pass 1: exact match ────────────────────────────────────────
    for field, aliases in alias_map.items():
        for alias in aliases:
            for header in headers:
                if header.lower().strip() == alias and header not in used_headers:
                    field_map[field] = header
                    confidence[field] = 1.0
                    used_headers.add(header)
                    break
            if field in field_map:
                break

    # ── Pass 2: fuzzy match for remaining fields ───────────────────
    remaining_fields = [f for f in alias_map if f not in field_map]
    remaining_headers = [h for h in headers if h not in used_headers]

    for field in remaining_fields:
        best_score = 0.0
        best_header = None
        for alias in alias_map[field]:
            for header in remaining_headers:
                score = _similarity(alias, header)
                if score > best_score:
                    best_score = score
                    best_header = header
        if best_score >= 0.80 and best_header:
            field_map[field] = best_header
            confidence[field] = round(best_score, 2)
            used_headers.add(best_header)
            remaining_headers = [h for h in remaining_headers if h not in used_headers]

    # ── Pass 3: AI fallback for critical unmapped fields ───────────
    critical_unmapped = [f for f in ["name", "city"] if f not in field_map]
    ai_remaining_headers = [h for h in headers if h not in used_headers]

    if critical_unmapped and ai_remaining_headers:
        try:
            sample_preview = sample_rows[:3] if sample_rows else []
            result = call_anthropic(
                system_prompt=(
                    f"Map CSV columns to standard {import_type} fields. "
                    "Return ONLY a JSON object mapping standard field names to actual column names. "
                    "Only include fields you are confident about."
                ),
                user_message=(
                    f"Headers: {ai_remaining_headers}\n\n"
                    f"Sample data:\n{sample_preview}\n\n"
                    f"Standard fields: {list(alias_map.keys())}"
                ),
                max_tokens=256,
            )
            if isinstance(result, dict):
                for field_name, col_name in result.items():
                    if (
                        field_name in alias_map
                        and field_name not in field_map
                        and col_name in ai_remaining_headers
                    ):
                        field_map[field_name] = col_name
                        confidence[field_name] = 0.70
                        used_headers.add(col_name)
        except Exception:
            logger.warning("AI column detection failed, continuing with rule-based results")

    unmapped_fields = [f for f in alias_map if f not in field_map]
    extra_columns = [h for h in headers if h not in used_headers]

    return {
        "field_map": field_map,
        "confidence": confidence,
        "unmapped_fields": unmapped_fields,
        "extra_columns": extra_columns,
    }
