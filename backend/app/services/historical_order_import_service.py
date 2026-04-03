"""Historical order import service.

Handles parsing, column detection, entity matching, import, and enrichment
for historical funeral order data from CSV files.

Privacy rule: The 'Family Name' (decedent name) column is NEVER stored
anywhere — it is stripped before any HistoricalOrder record is created.
"""

from __future__ import annotations

import csv
import difflib
import io
import json
import logging
import re
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from app.models.behavioral_analytics import EntityBehavioralProfile
from app.models.cemetery import Cemetery
from app.models.customer import Customer
from app.models.funeral_home_cemetery_history import FuneralHomeCemeteryHistory
from app.models.historical_order_import import HistoricalOrder, HistoricalOrderImport
from app.models.product import Product

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Columns that detect Sunnycrest green sheet format
SUNNYCREST_REQUIRED_HEADERS = {"Firm", "Deliver to", "Product", "Equipment", "S/O #"}

# Column-to-field mapping for Sunnycrest green sheet
SUNNYCREST_COLUMN_MAPPING: dict[str, str] = {
    "Date": "scheduled_date",
    "Day": "ignore",
    "Firm": "funeral_home_name",
    "Product": "product_name",
    "Qty": "quantity",
    "Deliver to": "cemetery_name",
    "Location": "cemetery_city",
    "Section": "ignore",
    "Family Name": "skip_privacy",      # NEVER stored
    "Equipment": "equipment_description",
    "Time": "service_time",
    "Place": "service_place_type",
    "ETA": "eta_time",
    "By": "order_taken_by",
    "Via": "order_method",
    "Confirmed": "confirmed_by",
    "Kind": "confirmation_method",
    "Comments": "notes",
    "Order Logged": "created_at_raw",
    "S/O #": "source_order_number",
    "Aub/Mex": "fulfillment_type",
    "Spring?": "is_spring_surcharge",
    "CSR": "csr_name",
}

SUNNYCREST_MAPPING_CONFIDENCE: dict[str, float] = {k: 1.0 for k in SUNNYCREST_COLUMN_MAPPING}

# Equipment display → normalized value
EQUIPMENT_MAPPING: dict[str, str] = {
    "full equipment": "Full Equipment",
    "full w/ placer": "Full Equipment + Placer (custom)",
    "full w/placer": "Full Equipment + Placer (custom)",
    "device & grass": "Lowering Device & Grass",
    "device,grass": "Lowering Device & Grass",
    "d,g": "Lowering Device & Grass",
    "device": "Lowering Device Only",
    "none": "No Equipment",
    "": "No Equipment",
    "full cremation": "Full Cremation",
    "tent only": "Tent Only",
    "device, grass, tent - if": "Full Equipment",
    "device, grass, tent": "Full Equipment",
    "chairs": "Extra Chairs",
    "any": "No Specific Equipment",
    "lowering device & grass": "Lowering Device & Grass",
    "lowering device only": "Lowering Device Only",
}

# Equipment values that need a review flag
EQUIPMENT_NEEDS_REVIEW = {
    "Full Equipment + Placer (custom)",
    "No Specific Equipment",
}

# Product names that map to platform products (lowercase key)
PRODUCT_NAME_MAP: dict[str, str | None] = {
    "graveliner": "Graveliner",
    "graveliner-ss": "Graveliner(SS)",
    "graveliner ss": "Graveliner(SS)",
    "monticello": "Monticello",
    "white venetian": "Venetian",
    "gold venetian": "Venetian",
    "venetian": "Venetian",
    "white tribute": "Tribute",
    "tribute": "Tribute",
    "mt urn vlt": "Monticello Urn Vault",
    "monticello urn vault": "Monticello Urn Vault",
    "gl urn vlt": "Graveliner Urn Vault",
    "graveliner urn vault": "Graveliner Urn Vault",
    "copper urn vlt": "Copper Triune Urn Vault",
    "copper triune urn vault": "Copper Triune Urn Vault",
    'love & cherished 19"': 'Loved & Cherished 19"',
    'loved & cherished 19"': 'Loved & Cherished 19"',
    "p-440": "P440 Jewel",
    "p440": "P440 Jewel",
    "p-400ws": "P440WS",
    "p400ws": "P440WS",
    "none": None,  # equipment-only order, no vault
    "": None,
}

# Products to skip (non-vault products)
SKIP_PRODUCTS = {"12 gauge standard", "redi-rock"}

# Products to flag for review
FLAG_REVIEW_PRODUCTS = {"fcrl6000", "full w/ placer"}

# Fulfillment type mapping
FULFILLMENT_MAP: dict[str, str] = {
    "": "standard",
    "transfer": "transfer",
    "shipped direct ground": "direct_ship",
    "shipped direct overnight": "direct_ship",
    "shipped direct ground/overnight": "direct_ship",
    "2nd day air": "expedited",
}

# Suffixes to strip from funeral home names
_FH_SUFFIX_PATTERNS = [
    re.compile(r"\s*\(L\)\s*$", re.IGNORECASE),
    re.compile(r"\s*\(MC\)\s*$", re.IGNORECASE),
    re.compile(r"\s*\(Lic\)\s*$", re.IGNORECASE),
    re.compile(r",\s*$"),
]


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Agentic import filters — skip non-cemetery and non-FH entries
# ---------------------------------------------------------------------------

# Patterns that indicate a delivery location is NOT a cemetery
_NOT_CEMETERY_PATTERNS = [
    "residence", "home", "house", "apt", "apartment", "condo",
    "church", "parish", "cathedral", "temple", "synagogue", "mosque",
    "hospital", "medical center", "nursing home", "hospice", "rehab",
    "funeral home", "funeral parlor", "mortuary", "cremator",
    "fire department", "fire station", "fire house",
    "school", "university", "college", "academy",
    "town hall", "village hall", "city hall", "courthouse",
    "private property", "family plot", "family land",
    "national guard", "armory", "vfw", "american legion", "legion hall",
    "elks", "moose", "eagles", "masonic",
    "tbd", "tba", "unknown", "n/a", "none", "na", "pending",
    "will call", "pick up", "pickup", "office", "shop", "warehouse",
    "same as above", "see above", "ditto",
]

# Patterns that indicate a "funeral home" field is NOT actually a funeral home
_NOT_FUNERAL_HOME_PATTERNS = [
    "cash", "cod", "misc", "miscellaneous", "walk-in", "walkin",
    "counter sale", "over the counter", "otc",
    "do not use", "inactive", "closed", "duplicate", "test",
    "unknown", "n/a", "none", "na", "tbd", "tba", "pending",
    "homeowner", "home owner", "private", "individual",
    "self", "personal",
]


def _is_likely_cemetery(name: str) -> bool:
    """Check if a delivery location name looks like an actual cemetery."""
    if not name or len(name.strip()) < 3:
        return False
    lower = name.strip().lower()

    # Explicit cemetery indicators — definitely a cemetery
    cemetery_words = ["cemetery", "memorial park", "memorial garden", "mausoleum",
                      "burial ground", "national cemetery", "veterans cemetery"]
    if any(w in lower for w in cemetery_words):
        return True

    # Not-a-cemetery indicators — skip these
    if any(p in lower for p in _NOT_CEMETERY_PATTERNS):
        return False

    # If it's just a number or very short, skip
    if lower.replace(" ", "").isdigit():
        return False
    if len(lower) < 4:
        return False

    # Default: assume it's a cemetery (most entries in the cemetery column are)
    return True


def _is_likely_funeral_home(name: str) -> bool:
    """Check if a funeral home field value is an actual funeral home."""
    if not name or len(name.strip()) < 3:
        return False
    lower = name.strip().lower()

    # Not-a-funeral-home indicators
    if any(p in lower for p in _NOT_FUNERAL_HOME_PATTERNS):
        return False

    # Just a number or very short
    if lower.replace(" ", "").isdigit():
        return False
    if len(lower) < 4:
        return False

    # Looks like a person's name (2 words, no business indicators)
    # Simple heuristic: if it's 2-3 short alpha words with no business keywords, skip
    words = lower.split()
    if len(words) in (2, 3) and all(w.replace(".", "").isalpha() and len(w) <= 15 for w in words):
        business_words = {"funeral", "home", "mortuary", "chapel", "service", "inc", "llc", "co", "fh", "f.h."}
        if not any(w in business_words for w in words):
            return False  # Looks like a person's name, not a business

    return True


def normalize_funeral_home_name(raw: str) -> str:
    """Strip whitespace, special chars, and trailing suffix variants."""
    name = raw.strip().replace("\xa0", " ").replace("\n", " ")
    # Collapse multiple spaces
    name = re.sub(r"\s+", " ", name)
    # Remove known trailing suffixes
    for pattern in _FH_SUFFIX_PATTERNS:
        name = pattern.sub("", name)
    return name.strip()


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


def detect_format(
    headers: list[str],
    sample_rows: list[dict],
    company_id: str | None = None,
) -> dict:
    """Detect the source system and return column mapping with confidence scores.

    Returns:
        {
            "source_system": str,
            "column_mapping": dict,
            "mapping_confidence": dict,
        }
    """
    header_set = set(headers)

    # ── Sunnycrest green sheet detection ────────────────────────────────────
    if SUNNYCREST_REQUIRED_HEADERS.issubset(header_set):
        mapping = {h: SUNNYCREST_COLUMN_MAPPING.get(h, "ignore") for h in headers}
        confidence = {h: SUNNYCREST_MAPPING_CONFIDENCE.get(h, 0.5) for h in headers}
        return {
            "source_system": "sunnycrest_green_sheet",
            "column_mapping": mapping,
            "mapping_confidence": confidence,
        }

    # ── Generic CSV — use Claude for mapping ────────────────────────────────
    try:
        from app.services.ai_service import call_anthropic

        sample_text = "\n".join(
            [str(list(headers))]
            + [
                ", ".join(str(r.get(h, "")) for h in headers[:8])
                for r in sample_rows[:3]
            ]
        )
        prompt = (
            "Map these CSV columns to standard funeral order fields.\n\n"
            "Standard fields: funeral_home_name, cemetery_name, product_name, "
            "equipment_description, scheduled_date, service_time, quantity, notes, "
            "order_number, csr_name, fulfillment_type, is_spring_surcharge.\n"
            "For columns with no match use 'ignore'.\n"
            "For Family Name / decedent name columns use 'skip_privacy'.\n\n"
            f"Headers and sample rows:\n{sample_text}\n\n"
            'Return JSON only: {"<column>": {"field": "<field>", "confidence": 0-1}}'
        )

        result = call_anthropic(prompt, json_mode=True)
        if isinstance(result, dict):
            mapping = {}
            confidence = {}
            for col, v in result.items():
                if isinstance(v, dict):
                    mapping[col] = v.get("field", "ignore")
                    confidence[col] = float(v.get("confidence", 0.5))
                else:
                    mapping[col] = str(v)
                    confidence[col] = 0.5
            return {
                "source_system": "generic_csv",
                "column_mapping": mapping,
                "mapping_confidence": confidence,
            }
    except Exception as exc:
        logger.warning("Claude column mapping failed: %s", exc)

    # Fallback: mark everything as unknown
    return {
        "source_system": "generic_csv",
        "column_mapping": {h: "ignore" for h in headers},
        "mapping_confidence": {h: 0.0 for h in headers},
    }


# ---------------------------------------------------------------------------
# File parsing
# ---------------------------------------------------------------------------


def parse_csv_content(content: str) -> tuple[list[str], list[dict]]:
    """Parse CSV string and return (headers, rows).

    Handles UTF-8 BOM and strips whitespace from all values.
    """
    # Strip BOM if present
    if content.startswith("\ufeff"):
        content = content[1:]

    reader = csv.DictReader(io.StringIO(content))
    headers = reader.fieldnames or []
    headers = [h.strip() for h in headers]

    rows = []
    for row in reader:
        cleaned = {k.strip(): (v.strip() if v else "") for k, v in row.items()}
        rows.append(cleaned)

    return list(headers), rows


# ---------------------------------------------------------------------------
# Entity matching helpers
# ---------------------------------------------------------------------------


def _fuzzy_ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def match_funeral_home(
    db: Session, company_id: str, raw_name: str, fh_cache: dict | None = None
) -> dict:
    """Match a raw funeral home name to an existing customer record.

    Args:
        fh_cache: optional {normalized_name: customer_id} pre-built for perf

    Returns:
        {customer_id, customer_name, confidence, match_type}
    """
    if not raw_name:
        return {"customer_id": None, "customer_name": None, "confidence": 0.0, "match_type": "none"}

    normalized = normalize_funeral_home_name(raw_name)

    # Use cache if provided
    if fh_cache is not None:
        if normalized.lower() in fh_cache:
            entry = fh_cache[normalized.lower()]
            return {
                "customer_id": entry["id"],
                "customer_name": entry["name"],
                "confidence": 1.0,
                "match_type": "exact",
            }
        # Fuzzy against cache keys
        best_key, best_ratio = None, 0.0
        for key, entry in fh_cache.items():
            ratio = _fuzzy_ratio(normalized, key)
            if ratio > best_ratio:
                best_ratio = ratio
                best_key = key
        if best_key and best_ratio >= 0.85:
            entry = fh_cache[best_key]
            return {
                "customer_id": entry["id"],
                "customer_name": entry["name"],
                "confidence": best_ratio,
                "match_type": "fuzzy",
            }
        return {"customer_id": None, "customer_name": None, "confidence": best_ratio, "match_type": "none"}

    # Direct DB query
    customers = (
        db.query(Customer)
        .filter(
            Customer.company_id == company_id,
            Customer.is_active == True,  # noqa: E712
            Customer.customer_type == "funeral_home",
        )
        .all()
    )

    # Exact match (case-insensitive)
    for c in customers:
        if normalize_funeral_home_name(c.name).lower() == normalized.lower():
            return {
                "customer_id": c.id,
                "customer_name": c.name,
                "confidence": 1.0,
                "match_type": "exact",
            }

    # Fuzzy match
    best_match, best_ratio, best_id = None, 0.0, None
    for c in customers:
        ratio = _fuzzy_ratio(normalized, normalize_funeral_home_name(c.name))
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = c.name
            best_id = c.id

    if best_ratio >= 0.85:
        return {
            "customer_id": best_id,
            "customer_name": best_match,
            "confidence": best_ratio,
            "match_type": "fuzzy",
        }

    return {"customer_id": None, "customer_name": None, "confidence": best_ratio, "match_type": "none"}


def match_cemetery(
    db: Session,
    company_id: str,
    raw_name: str,
    city: str | None = None,
    fh_names_lower: set | None = None,
    cem_cache: dict | None = None,
) -> dict:
    """Match a raw cemetery name to an existing Cemetery record.

    First checks if the name looks like a funeral home delivery destination.

    Returns:
        {cemetery_id, cemetery_name, confidence, match_type, delivery_location_type}
    """
    if not raw_name:
        return {
            "cemetery_id": None, "cemetery_name": None, "confidence": 0.0,
            "match_type": "none", "delivery_location_type": "cemetery",
        }

    normalized = raw_name.strip()
    normalized_lower = normalized.lower()

    # ── Check for FH delivery destination ───────────────────────────────────
    fh_keywords = {"funeral home", "mortuary", "cremation services"}
    if fh_names_lower:
        for kw in fh_keywords:
            if kw in normalized_lower:
                return {
                    "cemetery_id": None, "cemetery_name": normalized, "confidence": 0.9,
                    "match_type": "funeral_home", "delivery_location_type": "funeral_home",
                }
        if normalized_lower in fh_names_lower:
            return {
                "cemetery_id": None, "cemetery_name": normalized, "confidence": 0.95,
                "match_type": "funeral_home", "delivery_location_type": "funeral_home",
            }

    # Fallback keyword check even without fh_names_lower
    for kw in fh_keywords:
        if kw in normalized_lower:
            return {
                "cemetery_id": None, "cemetery_name": normalized, "confidence": 0.8,
                "match_type": "funeral_home", "delivery_location_type": "funeral_home",
            }

    # ── Match against Cemetery table ─────────────────────────────────────────
    if cem_cache is not None:
        if normalized_lower in cem_cache:
            entry = cem_cache[normalized_lower]
            return {
                "cemetery_id": entry["id"], "cemetery_name": entry["name"],
                "confidence": 1.0, "match_type": "exact", "delivery_location_type": "cemetery",
            }
        # Fuzzy
        best_key, best_ratio = None, 0.0
        for key, entry in cem_cache.items():
            ratio = _fuzzy_ratio(normalized, key)
            if ratio > best_ratio:
                best_ratio = ratio
                best_key = key
        if best_key and best_ratio >= 0.80:
            entry = cem_cache[best_key]
            return {
                "cemetery_id": entry["id"], "cemetery_name": entry["name"],
                "confidence": best_ratio, "match_type": "fuzzy", "delivery_location_type": "cemetery",
            }
        return {
            "cemetery_id": None, "cemetery_name": normalized, "confidence": best_ratio,
            "match_type": "none", "delivery_location_type": "cemetery",
        }

    # Direct DB query
    cemeteries = (
        db.query(Cemetery)
        .filter(Cemetery.company_id == company_id, Cemetery.is_active == True)  # noqa: E712
        .all()
    )

    for c in cemeteries:
        if c.name.strip().lower() == normalized_lower:
            return {
                "cemetery_id": c.id, "cemetery_name": c.name, "confidence": 1.0,
                "match_type": "exact", "delivery_location_type": "cemetery",
            }

    best_match, best_ratio, best_id = None, 0.0, None
    for c in cemeteries:
        ratio = _fuzzy_ratio(normalized, c.name.strip())
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = c.name
            best_id = c.id

    if best_ratio >= 0.80:
        return {
            "cemetery_id": best_id, "cemetery_name": best_match, "confidence": best_ratio,
            "match_type": "fuzzy", "delivery_location_type": "cemetery",
        }

    return {
        "cemetery_id": None, "cemetery_name": normalized, "confidence": best_ratio,
        "match_type": "none", "delivery_location_type": "cemetery",
    }


def map_equipment(raw: str) -> tuple[str, bool]:
    """Return (normalized_equipment, needs_review)."""
    cleaned = raw.strip().lower()
    normalized = EQUIPMENT_MAPPING.get(cleaned)
    if normalized is None:
        # Partial matches
        for key, val in EQUIPMENT_MAPPING.items():
            if key and cleaned.startswith(key):
                normalized = val
                break
        if normalized is None:
            normalized = raw.strip() or "No Equipment"
    needs_review = normalized in EQUIPMENT_NEEDS_REVIEW
    return normalized, needs_review


def _parse_date(raw: str) -> date | None:
    """Parse M/D/YYYY or common date formats."""
    if not raw:
        return None
    try:
        # Try M/D/YYYY
        return datetime.strptime(raw.strip(), "%m/%d/%Y").date()
    except ValueError:
        pass
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    except ValueError:
        pass
    try:
        from dateutil import parser as dp
        return dp.parse(raw.strip()).date()
    except Exception:
        return None


def _parse_time(raw: str) -> time | None:
    """Parse HH:MM or H:MM am/pm."""
    if not raw:
        return None
    for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p", "%H%M"):
        try:
            return datetime.strptime(raw.strip(), fmt).time()
        except ValueError:
            continue
    return None


def _map_fulfillment(raw: str) -> str:
    return FULFILLMENT_MAP.get(raw.strip().lower(), "standard")


# ---------------------------------------------------------------------------
# Preview generation (no DB writes — used by /parse endpoint)
# ---------------------------------------------------------------------------


def generate_preview(
    db: Session,
    company_id: str,
    rows: list[dict],
    column_mapping: dict[str, str],
) -> dict:
    """Analyze parsed rows and return a rich preview without writing anything.

    Privacy: 'Family Name' values are never included in any preview output.
    """
    fh_field = next((c for c, f in column_mapping.items() if f == "funeral_home_name"), None)
    cem_field = next((c for c, f in column_mapping.items() if f == "cemetery_name"), None)
    prod_field = next((c for c, f in column_mapping.items() if f == "product_name"), None)
    equip_field = next((c for c, f in column_mapping.items() if f == "equipment_description"), None)
    date_field = next((c for c, f in column_mapping.items() if f == "scheduled_date"), None)

    # Build FH / cemetery caches for fast matching
    fh_cache = _build_fh_cache(db, company_id)
    cem_cache = _build_cem_cache(db, company_id)
    fh_names_lower = {k for k in fh_cache.keys()}

    fh_names_seen: dict[str, dict] = {}
    cem_names_seen: dict[str, dict] = {}
    product_names: list[str] = []
    product_unmatched: list[str] = []
    equipment_counter: Counter = Counter()
    dates: list[date] = []

    for row in rows:
        # Funeral homes
        if fh_field:
            raw_fh = row.get(fh_field, "").strip()
            if raw_fh and raw_fh not in fh_names_seen:
                result = match_funeral_home(db, company_id, raw_fh, fh_cache)
                fh_names_seen[raw_fh] = result

        # Cemeteries
        if cem_field:
            raw_cem = row.get(cem_field, "").strip()
            if raw_cem and raw_cem not in cem_names_seen:
                result = match_cemetery(db, company_id, raw_cem, None, fh_names_lower, cem_cache)
                cem_names_seen[raw_cem] = result

        # Products
        if prod_field:
            raw_prod = row.get(prod_field, "").strip()
            if raw_prod:
                product_names.append(raw_prod)
                normalized = PRODUCT_NAME_MAP.get(raw_prod.lower())
                if normalized is None and raw_prod.lower() not in PRODUCT_NAME_MAP:
                    product_unmatched.append(raw_prod)

        # Equipment
        if equip_field:
            raw_eq = row.get(equip_field, "").strip()
            eq_mapped, _ = map_equipment(raw_eq)
            equipment_counter[eq_mapped] += 1

        # Dates
        if date_field:
            raw_dt = row.get(date_field, "").strip()
            parsed = _parse_date(raw_dt)
            if parsed:
                dates.append(parsed)

    # Aggregate FH stats
    fh_matched = sum(1 for v in fh_names_seen.values() if v["customer_id"])
    fh_unmatched = len(fh_names_seen) - fh_matched
    fh_sample = list(fh_names_seen.keys())[:5]

    # Aggregate cemetery stats (exclude FH-delivery ones)
    cem_real = {k: v for k, v in cem_names_seen.items() if v.get("delivery_location_type") != "funeral_home"}
    cem_matched = sum(1 for v in cem_real.values() if v["cemetery_id"])
    cem_unmatched = len(cem_real) - cem_matched
    cem_sample = list(cem_real.keys())[:5]

    # Product stats
    prod_counter = Counter(product_names)
    total_products = len(set(p.lower() for p in product_names))
    unique_unmapped = list(dict.fromkeys(p for p in product_unmatched if p.lower() not in SKIP_PRODUCTS))[:10]
    prod_matched = total_products - len(set(p.lower() for p in product_unmatched))

    date_range = {}
    if dates:
        date_range = {"earliest": str(min(dates)), "latest": str(max(dates))}

    # Warnings
    warnings = []
    placer_count = sum(
        1 for r in rows if equip_field and "placer" in r.get(equip_field, "").lower()
    )
    if placer_count > 0:
        warnings.append(
            f"{placer_count} orders use 'Full w/ Placer' equipment which isn't in your "
            f"catalog. These will import with the equipment noted for reference."
        )
    if fh_unmatched > 0:
        warnings.append(
            f"{fh_unmatched} funeral home{'s' if fh_unmatched > 1 else ''} couldn't be "
            f"matched to existing customers. They'll be created automatically."
        )
    if unique_unmapped:
        warnings.append(
            f"{len(unique_unmapped)} product name(s) couldn't be mapped to your catalog: "
            f"{', '.join(unique_unmapped[:5])}{'...' if len(unique_unmapped) > 5 else ''}. "
            f"These will import with the raw name preserved."
        )

    # Top products
    top_products = prod_counter.most_common(5)

    return {
        "funeral_homes": {
            "count": len(fh_names_seen),
            "sample": fh_sample,
            "matched": fh_matched,
            "unmatched": fh_unmatched,
        },
        "cemeteries": {
            "count": len(cem_real),
            "sample": cem_sample,
            "matched": cem_matched,
            "unmatched": cem_unmatched,
        },
        "products": {
            "count": total_products,
            "matched": prod_matched,
            "unmatched": len(unique_unmapped),
            "unmapped": unique_unmapped,
            "top": [{"name": n, "count": c} for n, c in top_products],
        },
        "date_range": date_range,
        "equipment_breakdown": dict(equipment_counter),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Cache builders (called once per import to minimize DB round-trips)
# ---------------------------------------------------------------------------


def _build_fh_cache(db: Session, company_id: str) -> dict:
    """Return {normalized_lower_name: {id, name}} for all funeral home customers."""
    customers = (
        db.query(Customer)
        .filter(
            Customer.company_id == company_id,
            Customer.is_active == True,  # noqa: E712
            Customer.customer_type == "funeral_home",
        )
        .all()
    )
    return {normalize_funeral_home_name(c.name).lower(): {"id": c.id, "name": c.name} for c in customers}


def _build_cem_cache(db: Session, company_id: str) -> dict:
    """Return {lower_name: {id, name, county, city}} for all active cemeteries."""
    cemeteries = (
        db.query(Cemetery)
        .filter(Cemetery.company_id == company_id, Cemetery.is_active == True)  # noqa: E712
        .all()
    )
    return {
        c.name.strip().lower(): {"id": c.id, "name": c.name, "county": c.county, "city": c.city}
        for c in cemeteries
    }


def _build_product_cache(db: Session, company_id: str) -> dict:
    """Return {lower_name: {id, name}} for all active products."""
    products = (
        db.query(Product)
        .filter(Product.company_id == company_id, Product.is_active == True)  # noqa: E712
        .all()
    )
    return {p.name.strip().lower(): {"id": p.id, "name": p.name} for p in products}


def _match_product(raw_name: str, product_cache: dict) -> tuple[str | None, float]:
    """Return (product_id, confidence)."""
    if not raw_name:
        return None, 0.0
    lower = raw_name.strip().lower()

    # Check skip list
    for skip in SKIP_PRODUCTS:
        if skip in lower:
            return None, 0.0

    # Check known mapping
    mapped_name = PRODUCT_NAME_MAP.get(lower)
    if mapped_name is None and lower in PRODUCT_NAME_MAP:
        # Explicit None → no-vault order
        return None, 1.0
    if mapped_name:
        lower_mapped = mapped_name.lower()
        if lower_mapped in product_cache:
            return product_cache[lower_mapped]["id"], 1.0
        # Fuzzy match against catalog using the mapped name
        raw_name = mapped_name

    # Fuzzy match against product catalog
    best_id, best_ratio = None, 0.0
    for name, entry in product_cache.items():
        ratio = _fuzzy_ratio(raw_name, name)
        if ratio > best_ratio:
            best_ratio = ratio
            best_id = entry["id"]

    if best_ratio >= 0.80:
        return best_id, best_ratio
    return None, best_ratio


# ---------------------------------------------------------------------------
# Main import runner
# ---------------------------------------------------------------------------


def run_import(
    db: Session,
    import_record: HistoricalOrderImport,
    rows: list[dict],
    column_mapping: dict[str, str],
    create_missing_customers: bool = True,
    create_missing_cemeteries: bool = True,
    cutover_date: date | None = None,
) -> dict:
    """Process all rows and create HistoricalOrder records.

    Returns a summary dict with final counts.
    """
    company_id = import_record.company_id
    import_id = import_record.id

    # ── Build lookup tables (one DB round-trip each) ─────────────────────────
    fh_cache = _build_fh_cache(db, company_id)
    cem_cache = _build_cem_cache(db, company_id)
    product_cache = _build_product_cache(db, company_id)
    fh_names_lower: set[str] = set(fh_cache.keys())

    # ── Map column names to field names ──────────────────────────────────────
    field_to_col: dict[str, str] = {}
    for col, field in column_mapping.items():
        if field not in ("ignore", "skip_privacy") and field:
            field_to_col[field] = col

    def _get(row: dict, field: str, default: str = "") -> str:
        col = field_to_col.get(field, "")
        return row.get(col, default).strip() if col else default

    # Counters
    imported = 0
    skipped = 0
    errors = 0
    customers_created = 0
    customers_matched = 0
    cemeteries_created = 0
    cemeteries_matched = 0
    new_warnings: list[str] = []

    # Track newly created entities (to add to caches mid-import)
    created_fh: dict[str, str] = {}   # normalized_lower → customer_id
    created_cem: dict[str, str] = {}  # lower_name → cemetery_id

    placer_count = 0
    review_product_count: Counter = Counter()

    for i, row in enumerate(rows):
        try:
            # ── Privacy: never access Family Name column ─────────────────────
            # (column_mapping marks it as skip_privacy; we never read it)

            # ── Extract and validate scheduled_date ─────────────────────────
            raw_date = _get(row, "scheduled_date")
            sched_date = _parse_date(raw_date)

            # Skip future rows (past cutover date = live orders, don't import)
            if cutover_date and sched_date and sched_date >= cutover_date:
                skipped += 1
                continue

            # ── Funeral home matching / creation ─────────────────────────────
            raw_fh = _get(row, "funeral_home_name")
            customer_id: str | None = None
            fh_confidence = 0.0

            if raw_fh:
                norm_fh = normalize_funeral_home_name(raw_fh)
                norm_lower = norm_fh.lower()

                # Check mid-import created cache
                if norm_lower in created_fh:
                    customer_id = created_fh[norm_lower]
                    fh_confidence = 1.0
                    customers_matched += 1
                else:
                    result = match_funeral_home(db, company_id, raw_fh, fh_cache)
                    if result["customer_id"]:
                        customer_id = result["customer_id"]
                        fh_confidence = result["confidence"]
                        customers_matched += 1
                    elif create_missing_customers and _is_likely_funeral_home(raw_fh):
                        # Create new funeral home customer (filtered)
                        from app.services.customer_service import quick_create_customer
                        new_cust = quick_create_customer(
                            db, company_id, norm_fh, customer_type="funeral_home"
                        )
                        customer_id = new_cust.id
                        fh_confidence = 1.0
                        fh_cache[norm_lower] = {"id": new_cust.id, "name": new_cust.name}
                        created_fh[norm_lower] = new_cust.id
                        customers_created += 1

            # ── Cemetery matching / creation ──────────────────────────────────
            raw_cem = _get(row, "cemetery_name")
            cemetery_id: str | None = None
            cem_confidence = 0.0
            delivery_loc = "cemetery"

            if raw_cem:
                cem_lower = raw_cem.strip().lower()

                if cem_lower in created_cem:
                    cemetery_id = created_cem[cem_lower]
                    cem_confidence = 1.0
                    delivery_loc = "cemetery"
                    cemeteries_matched += 1
                else:
                    cem_result = match_cemetery(
                        db, company_id, raw_cem,
                        city=_get(row, "cemetery_city") or None,
                        fh_names_lower=fh_names_lower,
                        cem_cache=cem_cache,
                    )
                    delivery_loc = cem_result.get("delivery_location_type", "cemetery")

                    if cem_result["cemetery_id"]:
                        cemetery_id = cem_result["cemetery_id"]
                        cem_confidence = cem_result["confidence"]
                        cemeteries_matched += 1
                    elif delivery_loc == "cemetery" and create_missing_cemeteries and _is_likely_cemetery(raw_cem):
                        from app.services.cemetery_service import create_cemetery as _create_cem
                        new_cem = _create_cem(
                            db, company_id,
                            name=raw_cem.strip(),
                            city=_get(row, "cemetery_city") or None,
                        )
                        cemetery_id = new_cem.id
                        cem_confidence = 1.0
                        cem_cache[cem_lower] = {"id": new_cem.id, "name": new_cem.name, "county": None, "city": None}
                        created_cem[cem_lower] = new_cem.id
                        cemeteries_created += 1

            # ── Product matching ──────────────────────────────────────────────
            raw_prod = _get(row, "product_name")
            product_id: str | None = None
            prod_confidence = 0.0
            needs_review = False

            if raw_prod:
                prod_id, prod_conf = _match_product(raw_prod, product_cache)
                product_id = prod_id
                prod_confidence = prod_conf
                if raw_prod.lower() in FLAG_REVIEW_PRODUCTS:
                    needs_review = True
                    review_product_count[raw_prod] += 1

            # ── Equipment ─────────────────────────────────────────────────────
            raw_eq = _get(row, "equipment_description")
            eq_mapped, eq_review = map_equipment(raw_eq)
            if eq_review:
                needs_review = True
                if "placer" in raw_eq.lower():
                    placer_count += 1

            # ── Confidence check ─────────────────────────────────────────────
            if fh_confidence < 0.75 or cem_confidence < 0.75:
                needs_review = True

            # ── Quantity ─────────────────────────────────────────────────────
            raw_qty = _get(row, "quantity")
            try:
                quantity = int(raw_qty) if raw_qty else 1
            except ValueError:
                quantity = 1

            # ── Fulfillment / spring surcharge ────────────────────────────────
            raw_fulfillment = _get(row, "fulfillment_type")
            fulfillment = _map_fulfillment(raw_fulfillment)

            raw_spring = _get(row, "is_spring_surcharge")
            is_spring = raw_spring.strip().lower() == "spring"

            # ── Create HistoricalOrder record ────────────────────────────────
            order = HistoricalOrder(
                id=str(uuid.uuid4()),
                company_id=company_id,
                import_id=import_id,
                customer_id=customer_id,
                cemetery_id=cemetery_id,
                product_id=product_id,
                raw_funeral_home=raw_fh or None,
                raw_cemetery=raw_cem or None,
                raw_product=raw_prod or None,
                raw_equipment=raw_eq or None,
                scheduled_date=sched_date,
                service_time=_parse_time(_get(row, "service_time")),
                service_place_type=_get(row, "service_place_type") or None,
                equipment_description=eq_mapped,
                equipment_mapped=eq_mapped,
                quantity=quantity,
                fulfillment_type=fulfillment,
                delivery_location_type=delivery_loc,
                is_spring_surcharge=is_spring,
                order_method=_get(row, "order_method") or None,
                csr_name=_get(row, "csr_name") or None,
                source_order_number=_get(row, "source_order_number") or None,
                notes=_get(row, "notes") or None,
                funeral_home_match_confidence=fh_confidence if raw_fh else None,
                cemetery_match_confidence=cem_confidence if raw_cem else None,
                product_match_confidence=prod_confidence if raw_prod else None,
                needs_review=needs_review,
            )
            db.add(order)
            imported += 1

            # Flush in batches to avoid huge transactions
            if imported % 200 == 0:
                db.flush()

        except Exception as exc:
            logger.warning("Error importing row %d: %s", i, exc)
            errors += 1

    db.flush()

    # ── Warnings ──────────────────────────────────────────────────────────────
    if placer_count > 0:
        new_warnings.append(
            f"{placer_count} order(s) use 'Full w/ Placer' equipment — imported as "
            f"'Full Equipment + Placer (custom)'. Not mapped to a catalog product."
        )
    for prod_name, count in review_product_count.most_common(5):
        if prod_name.lower() not in ("full w/ placer", "full w/placer"):
            new_warnings.append(
                f"{count} order(s) with product '{prod_name}' flagged for manual review."
            )

    # ── Update import record ──────────────────────────────────────────────────
    import_record.imported_rows = imported
    import_record.skipped_rows = skipped
    import_record.error_rows = errors
    import_record.customers_created = customers_created
    import_record.customers_matched = customers_matched
    import_record.cemeteries_created = cemeteries_created
    import_record.cemeteries_matched = cemeteries_matched
    existing_warnings = list(import_record.warnings or [])
    import_record.warnings = existing_warnings + new_warnings
    import_record.status = "enriching"
    db.flush()

    # ── Run enrichment ────────────────────────────────────────────────────────
    enrich_counts = enrich_from_historical_orders(db, company_id, import_record)

    import_record.fh_cemetery_pairs_created = enrich_counts.get("pairs_created", 0)

    # ── Sync to CRM: create company_entities + classify ──────────────────
    crm_stats = _sync_to_crm(db, company_id)

    import_record.status = "complete"
    import_record.completed_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "customers_created": customers_created,
        "customers_matched": customers_matched,
        "cemeteries_created": cemeteries_created,
        "cemeteries_matched": cemeteries_matched,
        "fh_cemetery_pairs": enrich_counts.get("pairs_created", 0),
        "crm_entities_created": crm_stats.get("entities_created", 0),
        "crm_classified": crm_stats.get("classified", 0),
        "recommended_templates": import_record.recommended_templates,
        "warnings": import_record.warnings,
    }


# ---------------------------------------------------------------------------
# CRM Sync — create company_entities + classify after import
# ---------------------------------------------------------------------------


def _sync_to_crm(db: Session, tenant_id: str) -> dict:
    """Create company_entities for new customers/cemeteries and run classification."""
    import uuid as _uuid
    stats = {"entities_created": 0, "classified": 0}

    try:
        # Check if company_entities table exists
        db.execute(text("SELECT 1 FROM company_entities LIMIT 0"))
    except Exception:
        db.rollback()
        return stats  # CRM tables not created yet — skip silently

    try:
        from app.models.company_entity import CompanyEntity
        from app.models.customer import Customer
        from app.models.cemetery import Cemetery

        # Create entities for customers without one
        customers = db.query(Customer).filter(
            Customer.company_id == tenant_id,
            Customer.is_active == True,
            Customer.master_company_id.is_(None),
        ).all()

        for c in customers:
            eid = str(_uuid.uuid4())
            is_fh = (getattr(c, "customer_type", None) or "").lower() in ("funeral_home", "funeral home")
            entity = CompanyEntity(
                id=eid, company_id=tenant_id, name=c.name,
                phone=c.phone, email=c.email, website=c.website,
                address_line1=c.address_line1, address_line2=c.address_line2,
                city=c.city, state=c.state, zip=c.zip_code, country=c.country or "US",
                is_customer=True, is_funeral_home=is_fh,
            )
            db.add(entity)
            c.master_company_id = eid
            stats["entities_created"] += 1

        # Create entities for cemeteries without one
        cemeteries = db.query(Cemetery).filter(
            Cemetery.company_id == tenant_id,
            Cemetery.is_active == True,
            Cemetery.master_company_id.is_(None),
        ).all()

        for cem in cemeteries:
            # Check if entity with same name already exists
            existing = db.query(CompanyEntity).filter(
                CompanyEntity.company_id == tenant_id,
                CompanyEntity.name == cem.name,
            ).first()
            if existing:
                existing.is_cemetery = True
                cem.master_company_id = existing.id
            else:
                eid = str(_uuid.uuid4())
                entity = CompanyEntity(
                    id=eid, company_id=tenant_id, name=cem.name,
                    phone=cem.phone, address_line1=getattr(cem, "address", None),
                    city=cem.city, state=cem.state, zip=cem.zip_code,
                    is_cemetery=True,
                )
                db.add(entity)
                cem.master_company_id = eid
                stats["entities_created"] += 1

        db.flush()

        # Run classification on new entities
        try:
            from app.services.crm.classification_service import run_bulk_classification
            result = run_bulk_classification(db, tenant_id, use_google_places=False)
            stats["classified"] = result.get("total_processed", 0)
        except Exception:
            logger.warning("CRM classification after import failed (non-fatal)", exc_info=True)

        # Populate manufacturer profiles with historical order stats
        try:
            stats["profiles_updated"] = _populate_profiles_from_history(db, tenant_id)
        except Exception:
            logger.warning("CRM profile population from history failed (non-fatal)", exc_info=True)

    except Exception:
        logger.warning("CRM sync after import failed (non-fatal)", exc_info=True)

    return stats


def _populate_profiles_from_history(db: Session, tenant_id: str) -> int:
    """Update ManufacturerCompanyProfile stats from historical_orders data."""
    import uuid as _uuid
    from decimal import Decimal

    try:
        db.execute(text("SELECT 1 FROM manufacturer_company_profiles LIMIT 0"))
    except Exception:
        db.rollback()
        return 0

    from app.models.manufacturer_company_profile import ManufacturerCompanyProfile
    from app.models.company_entity import CompanyEntity
    from app.models.customer import Customer
    from app.models.historical_order_import import HistoricalOrder

    updated = 0

    # Get all customer entities for this tenant
    customer_entities = (
        db.query(CompanyEntity)
        .filter(CompanyEntity.company_id == tenant_id, CompanyEntity.is_customer == True)
        .all()
    )

    for entity in customer_entities:
        customer = db.query(Customer).filter(Customer.master_company_id == entity.id).first()
        if not customer:
            continue

        # Get historical order stats
        row = db.execute(text("""
            SELECT
                COUNT(*) as total_orders,
                MIN(scheduled_date) as first_order,
                MAX(scheduled_date) as last_order,
                COUNT(DISTINCT raw_product) as product_count
            FROM historical_orders
            WHERE customer_id = :cid AND company_id = :tid
        """), {"cid": customer.id, "tid": tenant_id}).fetchone()

        if not row or row.total_orders == 0:
            continue

        # Get most common product
        top_product = db.execute(text("""
            SELECT raw_product, COUNT(*) as cnt
            FROM historical_orders
            WHERE customer_id = :cid AND company_id = :tid
            AND raw_product IS NOT NULL
            GROUP BY raw_product ORDER BY cnt DESC LIMIT 1
        """), {"cid": customer.id, "tid": tenant_id}).fetchone()

        # Ensure profile exists
        profile = db.query(ManufacturerCompanyProfile).filter(
            ManufacturerCompanyProfile.master_company_id == entity.id
        ).first()
        if not profile:
            profile = ManufacturerCompanyProfile(
                id=str(_uuid.uuid4()),
                company_id=tenant_id,
                master_company_id=entity.id,
            )
            db.add(profile)

        # Update with historical data (don't overwrite if live data is newer)
        if not profile.last_order_date or (row.last_order and row.last_order > (profile.last_order_date or row.last_order)):
            profile.last_order_date = row.last_order

        profile.order_count_all_time = max(profile.order_count_all_time or 0, row.total_orders)

        if row.first_order:
            entity.first_order_year = row.first_order.year

        if top_product:
            profile.most_ordered_vault_name = top_product.raw_product

        # Set active status based on historical recency
        if row.last_order:
            from datetime import date as _date
            days_since = (_date.today() - row.last_order).days
            if days_since < 365:
                entity.is_active_customer = True

        updated += 1

    db.flush()
    return updated


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------


def enrich_from_historical_orders(
    db: Session,
    company_id: str,
    import_record: HistoricalOrderImport,
) -> dict:
    """Post-import enrichment: build FH-cemetery history, behavioral profiles, templates, hints."""
    import_id = import_record.id
    pairs_created = 0

    # ── STEP 1: FH-Cemetery shortlist (funeral_home_cemetery_history) ─────────
    pair_rows = (
        db.query(
            HistoricalOrder.customer_id,
            HistoricalOrder.cemetery_id,
            func.count().label("cnt"),
            func.max(HistoricalOrder.scheduled_date).label("last_date"),
        )
        .filter(
            HistoricalOrder.import_id == import_id,
            HistoricalOrder.customer_id.isnot(None),
            HistoricalOrder.cemetery_id.isnot(None),
            HistoricalOrder.delivery_location_type == "cemetery",
        )
        .group_by(HistoricalOrder.customer_id, HistoricalOrder.cemetery_id)
        .all()
    )

    for customer_id, cemetery_id, cnt, last_date in pair_rows:
        existing = (
            db.query(FuneralHomeCemeteryHistory)
            .filter(
                FuneralHomeCemeteryHistory.company_id == company_id,
                FuneralHomeCemeteryHistory.customer_id == customer_id,
                FuneralHomeCemeteryHistory.cemetery_id == cemetery_id,
            )
            .first()
        )
        if existing:
            existing.order_count = (existing.order_count or 0) + cnt
            if last_date and (not existing.last_order_date or last_date > existing.last_order_date):
                existing.last_order_date = last_date
        else:
            new_history = FuneralHomeCemeteryHistory(
                id=str(uuid.uuid4()),
                company_id=company_id,
                customer_id=customer_id,
                cemetery_id=cemetery_id,
                order_count=cnt,
                last_order_date=last_date,
            )
            db.add(new_history)
            pairs_created += 1

    db.flush()

    # ── STEP 2: Behavioral profiles per funeral home customer ─────────────────
    customer_rows = (
        db.query(HistoricalOrder.customer_id)
        .filter(
            HistoricalOrder.import_id == import_id,
            HistoricalOrder.customer_id.isnot(None),
        )
        .distinct()
        .all()
    )

    for (customer_id,) in customer_rows:
        orders = (
            db.query(HistoricalOrder)
            .filter(
                HistoricalOrder.import_id == import_id,
                HistoricalOrder.customer_id == customer_id,
            )
            .all()
        )
        if not orders:
            continue

        vault_names = [o.raw_product for o in orders if o.raw_product and o.raw_product.lower() != "none"]
        eq_names = [o.equipment_mapped for o in orders if o.equipment_mapped]
        places = [o.service_place_type for o in orders if o.service_place_type]
        dates_with_data = [o.scheduled_date for o in orders if o.scheduled_date]

        most_common_vault = Counter(vault_names).most_common(1)[0][0] if vault_names else None
        most_common_equipment = Counter(eq_names).most_common(1)[0][0] if eq_names else None
        preferred_place = Counter(places).most_common(1)[0][0] if places else None

        avg_monthly = 0.0
        if dates_with_data:
            months_span = max(
                1,
                (max(dates_with_data) - min(dates_with_data)).days / 30.0,
            )
            avg_monthly = round(len(orders) / months_span, 2)

        profile_data = {
            "historical_order_count": len(orders),
            "most_common_vault": most_common_vault,
            "most_common_equipment": most_common_equipment,
            "preferred_service_place": preferred_place,
            "avg_monthly_volume": avg_monthly,
            "data_source": "historical_import",
            "import_id": import_id,
        }

        existing_profile = (
            db.query(EntityBehavioralProfile)
            .filter(
                EntityBehavioralProfile.tenant_id == company_id,
                EntityBehavioralProfile.entity_type == "customer",
                EntityBehavioralProfile.entity_id == customer_id,
            )
            .first()
        )
        if existing_profile:
            existing_profile.profile_data = profile_data
            existing_profile.last_computed_at = datetime.now(timezone.utc)
            existing_profile.updated_at = datetime.now(timezone.utc)
            if dates_with_data:
                existing_profile.last_order_date = max(dates_with_data)
        else:
            new_profile = EntityBehavioralProfile(
                id=str(uuid.uuid4()),
                tenant_id=company_id,
                entity_type="customer",
                entity_id=customer_id,
                profile_data=profile_data,
                last_order_date=max(dates_with_data) if dates_with_data else None,
            )
            db.add(new_profile)

    db.flush()

    # ── STEP 3: Template recommendations ─────────────────────────────────────
    total_orders = (
        db.query(func.count())
        .filter(
            HistoricalOrder.import_id == import_id,
            HistoricalOrder.raw_product.isnot(None),
        )
        .scalar()
        or 1
    )

    combo_rows = (
        db.query(
            HistoricalOrder.raw_product,
            HistoricalOrder.equipment_mapped,
            func.count().label("cnt"),
        )
        .filter(
            HistoricalOrder.import_id == import_id,
            HistoricalOrder.raw_product.isnot(None),
            HistoricalOrder.raw_product != "",
            HistoricalOrder.raw_product.isnot(None),
        )
        .group_by(HistoricalOrder.raw_product, HistoricalOrder.equipment_mapped)
        .order_by(func.count().desc())
        .limit(10)
        .all()
    )

    recommended_templates = []
    for prod, equip, cnt in combo_rows:
        pct = round(cnt / total_orders * 100, 1)
        template_name = f"{prod} + {equip}" if equip and equip != "No Equipment" else prod
        recommended_templates.append(
            {
                "product_name": prod,
                "equipment": equip or "No Equipment",
                "order_count": cnt,
                "pct_of_total": pct,
                "suggested_template_name": template_name,
            }
        )

    import_record.recommended_templates = recommended_templates
    db.flush()

    # ── STEP 4: Cemetery equipment hints ─────────────────────────────────────
    cem_hint_rows = (
        db.query(HistoricalOrder.cemetery_id, func.count().label("total"))
        .filter(
            HistoricalOrder.import_id == import_id,
            HistoricalOrder.cemetery_id.isnot(None),
        )
        .group_by(HistoricalOrder.cemetery_id)
        .having(func.count() >= 10)
        .all()
    )

    hints: list[str] = []
    for cem_id, total in cem_hint_rows:
        none_count = (
            db.query(func.count())
            .filter(
                HistoricalOrder.import_id == import_id,
                HistoricalOrder.cemetery_id == cem_id,
                or_(
                    HistoricalOrder.equipment_mapped == "No Equipment",
                    HistoricalOrder.equipment_mapped.is_(None),
                ),
            )
            .scalar()
            or 0
        )
        pct_none = none_count / total if total else 0
        if pct_none > 0.70:
            cem_obj = db.query(Cemetery).filter(Cemetery.id == cem_id).first()
            cem_name = cem_obj.name if cem_obj else cem_id
            hints.append(
                f"Hint: {cem_name} has 'No Equipment' on {int(pct_none * 100)}% of orders — "
                f"they may provide their own equipment. Review in Settings → Cemeteries."
            )

    if hints:
        existing_warnings = list(import_record.warnings or [])
        import_record.warnings = existing_warnings + hints

    db.flush()

    # ── STEP 5: Seasonal analysis ─────────────────────────────────────────────
    month_rows = (
        db.query(
            func.extract("month", HistoricalOrder.scheduled_date).label("mo"),
            func.count().label("cnt"),
        )
        .filter(
            HistoricalOrder.import_id == import_id,
            HistoricalOrder.scheduled_date.isnot(None),
        )
        .group_by("mo")
        .all()
    )

    if month_rows:
        month_counts = {int(row.mo): row.cnt for row in month_rows}
        avg_count = sum(month_counts.values()) / len(month_counts)
        peak_months = [m for m, c in month_counts.items() if c > avg_count * 1.3]
        peak_multiplier = (
            round(max(month_counts.values()) / avg_count, 2) if avg_count > 0 else 1.0
        )

        # Store on company settings
        try:
            from app.models.company import Company

            company = db.query(Company).filter(Company.id == company_id).first()
            if company:
                company.set_setting(
                    "seasonal_pattern",
                    {
                        "peak_months": sorted(peak_months),
                        "peak_multiplier": peak_multiplier,
                        "spring_surcharge_months": [m for m in peak_months if m in (3, 4, 5)],
                        "computed_from_import": import_id,
                    },
                )
                db.flush()
        except Exception as exc:
            logger.warning("Could not store seasonal pattern: %s", exc)

    # ── STEP 6: Placer preference detection ──────────────────────────────────
    placer_summary: dict = {"auto_set": [], "suggested": []}
    try:
        from app.services.funeral_home_preference_service import (
            detect_placer_preferences_from_history,
        )
        placer_summary = detect_placer_preferences_from_history(db, company_id, import_id)

        if placer_summary["auto_set"]:
            auto_names = [r["name"] for r in placer_summary["auto_set"]]
            existing_warnings = list(import_record.warnings or [])
            import_record.warnings = existing_warnings + [
                f"Placer preference auto-enabled for {len(auto_names)} funeral "
                f"home(s) based on order history: {', '.join(auto_names[:5])}"
                + (" and more." if len(auto_names) > 5 else ".")
            ]

        if placer_summary["suggested"]:
            existing_warnings = list(import_record.warnings or [])
            import_record.warnings = existing_warnings + [
                f"{r['name']} uses a placer on {r['placer_rate']}% of lowering device orders — "
                "consider enabling the placer preference."
                for r in placer_summary["suggested"][:5]
            ]

        db.flush()
    except Exception as exc:
        logger.warning("Placer detection failed: %s", exc)

    return {"pairs_created": pairs_created, "placer_auto_set": len(placer_summary.get("auto_set", []))}


# ---------------------------------------------------------------------------
# Status / top-N helpers (used by GET endpoints and downstream onboarding)
# ---------------------------------------------------------------------------


def get_latest_import(db: Session, company_id: str) -> HistoricalOrderImport | None:
    return (
        db.query(HistoricalOrderImport)
        .filter(
            HistoricalOrderImport.company_id == company_id,
            HistoricalOrderImport.status == "complete",
        )
        .order_by(HistoricalOrderImport.completed_at.desc())
        .first()
    )


def get_top_cemeteries_from_history(
    db: Session, company_id: str, limit: int = 20
) -> list[dict]:
    """Return the most-ordered cemeteries from historical data for wizard pre-population."""
    rows = (
        db.query(
            HistoricalOrder.cemetery_id,
            HistoricalOrder.raw_cemetery,
            func.count().label("order_count"),
        )
        .filter(
            HistoricalOrder.company_id == company_id,
            HistoricalOrder.delivery_location_type == "cemetery",
        )
        .group_by(HistoricalOrder.cemetery_id, HistoricalOrder.raw_cemetery)
        .order_by(func.count().desc())
        .limit(limit)
        .all()
    )

    results = []
    for cem_id, raw_name, count in rows:
        entry: dict[str, Any] = {"raw_name": raw_name, "order_count": count}
        if cem_id:
            cem = db.query(Cemetery).filter(Cemetery.id == cem_id).first()
            if cem:
                entry.update(
                    {
                        "cemetery_id": cem.id,
                        "name": cem.name,
                        "city": cem.city,
                        "state": cem.state,
                        "county": cem.county,
                    }
                )
        if "name" not in entry:
            entry["name"] = raw_name
        results.append(entry)
    return results
