"""Classification service — AI-powered company type classification using Claude + Google Places."""

import json
import logging
import re
import time
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.company_entity import CompanyEntity
from app.models.customer import Customer

logger = logging.getLogger(__name__)

# ── Name keyword signals ─────────────────────────────────────────────────────

NAME_SIGNALS = {
    "funeral_home": ["funeral", "mortuary", "chapel", "cremation", "memorial home", "funeral service", "funeral parlor", " fh", "fh ", "(fh)", "f.h.", " fh.", "f.h "],
    "cemetery": ["cemetery", "memorial garden", "memorial park", "mausoleum", "burial ground", "holy cross", "sacred heart", "calvary", "grove", "lawn"],
    "contractor": ["excavat", "septic", "plumbing", "plumber", "construction", "contracting", "contractor", "backhoe", "site work", "grading", "landscap", "environmental", "well & septic", "drain", "sewer", "utility", "earthwork", "digging", "underground"],
    "crematory": ["cremator", "cremation", "cremains"],
    "licensee": ["burial vault", "concrete product", "precast", "vault co", "monument", "wilbert", "vault company", "vault works", " vault", "vault "],
    "church": ["church", "parish", "cathedral", "diocese", "st. ", "saint "],
    "government": ["town of", "county of", "city of", "village of", "state of", "department of", "dept of", "municipality", "highway dept", "water district", "sewer district", "housing authority", "soil & water", "soil and water", "conservation district"],
    "school": ["school", "university", "college", "academy", "board of education", "boces", "suny", " csd", "csd ", "(csd)", "c.s.d.", "central school"],
    "fire_department": ["fire dept", "fire department", "fire district", "fire co", "fire company", "volunteer fire", "fire station", "ems", "ambulance", "rescue squad", " fd", "fd ", "(fd)", "f.d.", " fd.", "f.d "],
    "utility": ["electric", "power authority", "water authority", "gas company", "energy"],
}

AGGREGATE_PATTERNS = ["cod_precast", "cash", "misc", "miscellaneous", "walk-in", "walkin", "counter sale"]

# Old/inactive account indicators — these records should be deactivated
INACTIVE_PATTERNS = ["do not use", "don't use", "dont use", "inactive", "closed", "out of business",
                     "deceased", "no longer", "duplicate", "delete", "removed", "old account", "test account"]

GOOGLE_TYPE_MAP = {
    "funeral_home": "funeral_home", "cemetery": "cemetery",
    "general_contractor": "contractor", "plumber": "contractor",
    "electrician": "contractor", "roofing_contractor": "contractor",
    "church": "church", "local_government_office": "government",
    "crematorium": "crematory",
}


def cleanup_company_name(name: str) -> dict:
    """Clean up a company name. Returns the cleaned name and a list of actions taken.

    Tracks every change so the user can see what was done and revert if needed.
    """
    if not name:
        return {"cleaned": name, "changed": False, "actions": []}

    original = name
    actions = []

    # 1. Strip leading/trailing whitespace
    cleaned = name.strip()
    if cleaned != name:
        actions.append("Trimmed leading/trailing whitespace")

    # 2. Collapse multiple spaces into one
    collapsed = re.sub(r"\s{2,}", " ", cleaned)
    if collapsed != cleaned:
        actions.append(f"Collapsed extra spaces (had multiple consecutive spaces)")
        cleaned = collapsed

    # 3. Convert ALL CAPS to Title Case (only if entire name is uppercase)
    if cleaned == cleaned.upper() and len(cleaned) > 3:
        # Preserve certain abbreviations
        PRESERVE_UPPER = {"LLC", "INC", "CO", "FH", "F.H.", "NY", "PA", "NJ", "CT", "MA",
                          "VT", "NH", "ME", "OH", "DBA", "II", "III", "IV", "PC", "PLLC",
                          "LP", "LLP", "NA", "PO", "APT"}
        words = cleaned.split()
        title_words = []
        for w in words:
            # Strip punctuation for comparison but keep it in output
            bare = w.strip(".,()&-")
            if bare.upper() in PRESERVE_UPPER:
                title_words.append(w.upper())
            else:
                title_words.append(w.capitalize())
            # Fix common patterns
        cleaned = " ".join(title_words)

        # Fix "Mcdonald" → "McDonald" etc.
        cleaned = re.sub(r"\bMc([a-z])", lambda m: f"Mc{m.group(1).upper()}", cleaned)

        actions.append("Converted from ALL CAPS to Title Case")

    # 4. Fix common punctuation issues
    # "Johnson , Inc" → "Johnson, Inc"
    fixed_punct = re.sub(r"\s+,", ",", cleaned)
    if fixed_punct != cleaned:
        actions.append("Fixed spacing before commas")
        cleaned = fixed_punct

    # "Johnson,Inc" → "Johnson, Inc"
    fixed_comma = re.sub(r",(\S)", r", \1", cleaned)
    if fixed_comma != cleaned:
        actions.append("Added space after commas")
        cleaned = fixed_comma

    # 5. Normalize "&" spacing: "A&B" → "A & B", "A &B" → "A & B"
    fixed_amp = re.sub(r"(\S)&(\S)", r"\1 & \2", cleaned)
    fixed_amp = re.sub(r"(\S)& ", r"\1 & ", fixed_amp)
    fixed_amp = re.sub(r" &(\S)", r" & \1", fixed_amp)
    if fixed_amp != cleaned:
        actions.append("Normalized spacing around &")
        cleaned = fixed_amp

    # 6. Remove trailing periods (unless abbreviation like "Inc.")
    if cleaned.endswith(".") and not cleaned.endswith("Inc.") and not cleaned.endswith("Co.") and not cleaned.endswith("F.H."):
        cleaned = cleaned.rstrip(".")
        actions.append("Removed trailing period")

    changed = cleaned != original
    return {"cleaned": cleaned, "changed": changed, "actions": actions, "original": original}


def revert_company_name(db: Session, company_entity_id: str) -> dict:
    """Revert a company name to its original pre-cleanup value."""
    entity = db.query(CompanyEntity).filter(CompanyEntity.id == company_entity_id).first()
    if not entity:
        return {"error": "not_found"}
    if not entity.original_name:
        return {"error": "no_original", "message": "No original name stored — name was never cleaned up"}

    reverted_from = entity.name
    entity.name = entity.original_name
    entity.original_name = None
    entity.name_cleanup_actions = None

    return {"reverted": True, "name": entity.name, "was": reverted_from}


# Words that indicate a business, not an individual
BUSINESS_INDICATORS = {
    "inc", "llc", "ltd", "corp", "co", "company", "companies", "group", "assoc",
    "association", "associates", "services", "service", "supply", "supplies",
    "sons", "brothers", "bros", "enterprises", "enterprise", "industries",
    "contracting", "construction", "excavating", "plumbing", "electric",
    "funeral", "mortuary", "cemetery", "church", "school", "fire", "town",
    "county", "city", "village", "state", "dept", "department", "district",
    "authority", "commission", "board", "agency", "foundation", "institute",
    "hospital", "clinic", "realty", "properties", "property", "management",
    "trucking", "transport", "paving", "roofing", "heating", "cooling",
    "hvac", "auto", "garage", "shop", "store", "market", "farm", "dairy",
    "nursery", "landscaping", "tree", "lawn", "masonry", "concrete",
    "steel", "iron", "lumber", "building", "builders", "homes", "housing",
    "development", "developers", "engineering", "engineers", "design",
    "consulting", "consultants", "solutions", "systems", "technology",
    "electric", "electrical", "mechanical", "welding", "fabrication",
    "rental", "rentals", "equipment", "oil", "gas", "energy", "power",
    "vault", "precast", "monument", "memorial", "wilbert",
    "dba", "pllc", "pc", "llp", "lp", "na",
}


def _looks_like_individual(name_lower: str) -> bool:
    """Check if a name looks like a person rather than a business."""
    # Remove common punctuation for analysis
    clean = re.sub(r"[.,\-'()]", " ", name_lower).strip()
    words = clean.split()

    if not words:
        return False

    # If any word is a business indicator, it's not an individual
    for w in words:
        if w in BUSINESS_INDICATORS:
            return False

    # Also check the original name for any keyword from NAME_SIGNALS
    for keywords in NAME_SIGNALS.values():
        for kw in keywords:
            if kw in name_lower:
                return False

    # Patterns that suggest a personal name:
    # 1. Two or three short words (first + last, or first + middle + last)
    # 2. Words with initials like "J.J." or "E."
    # 3. No numbers in the name

    if re.search(r"\d", clean):
        return False  # Has numbers — probably an address or business

    if len(words) > 4:
        return False  # Too many words for a personal name

    if len(words) < 2:
        return False  # Single word — ambiguous, don't auto-classify

    # Count how many words look like name parts (short, capitalized, or initials)
    name_like = 0
    for w in words:
        # Initials: "j", "jj", "e" (single/double letters)
        if len(w) <= 2:
            name_like += 1
        # Normal name word (no special characters, reasonable length)
        elif len(w) <= 15 and w.isalpha():
            name_like += 1

    # If all words look like name parts, it's likely an individual
    return name_like == len(words) and len(words) >= 2


def classify_company(db: Session, company_entity_id: str, use_google_places: bool = False) -> dict:
    """Classify a single company using name analysis, order history, and optionally AI + Google."""
    entity = db.query(CompanyEntity).filter(CompanyEntity.id == company_entity_id).first()
    if not entity:
        return {"error": "not_found"}

    # Skip aggregates
    if entity.is_aggregate:
        return {"status": "skipped", "reason": "aggregate"}

    name_lower = (entity.name or "").lower().strip()
    if any(name_lower.startswith(p) or name_lower == p for p in AGGREGATE_PATTERNS):
        entity.is_aggregate = True
        entity.customer_type = None
        entity.classification_source = "auto_high"
        entity.classification_confidence = Decimal("1.000")
        entity.classification_reasons = ["Aggregate/cash sales record"]
        return {"status": "aggregate"}

    # Check for old/inactive accounts — deactivate them
    if any(p in name_lower for p in INACTIVE_PATTERNS):
        matched = [p for p in INACTIVE_PATTERNS if p in name_lower]
        entity.is_active = False
        entity.customer_type = None
        entity.classification_source = "auto_high"
        entity.classification_confidence = Decimal("1.000")
        entity.classification_reasons = [f"Old/inactive account: name contains '{matched[0]}'"]
        return {"status": "deactivated", "reason": f"Inactive pattern: {matched[0]}"}

    # ── Name cleanup ────────────────────────────────────────────────────
    cleanup_result = cleanup_company_name(entity.name)
    if cleanup_result["changed"]:
        entity.original_name = entity.name
        entity.name = cleanup_result["cleaned"]
        entity.name_cleanup_actions = cleanup_result["actions"]
        name_lower = entity.name.lower().strip()

    # ── Check for individual (personal name, not a business) ──────────────
    if _looks_like_individual(name_lower):
        entity.customer_type = "individual"
        entity.classification_source = "auto_high"
        entity.classification_confidence = Decimal("0.880")
        entity.classification_reasons = ["Name appears to be a person, not a business"]
        return {"status": "classified", "customer_type": "individual", "confidence": 0.88, "reasons": ["Name appears to be a person, not a business"]}

    # ── Signal 1: Name analysis ──────────────────────────────────────────
    name_matches = {}
    for ctype, keywords in NAME_SIGNALS.items():
        matches = [k for k in keywords if k in name_lower]
        if matches:
            name_matches[ctype] = matches

    # ── Signal 2: Order history ──────────────────────────────────────────
    customer = db.query(Customer).filter(Customer.master_company_id == company_entity_id).first()
    order_data = _get_order_signals(db, customer.id if customer else None)

    # ── Signal 3: Domain analysis ────────────────────────────────────────
    domain_signals = {}
    email = entity.email or ""
    if "@" in email:
        domain = email.split("@")[1].lower()
        if domain.endswith(".gov"):
            domain_signals["government"] = True
        if domain.endswith(".edu"):
            domain_signals["school"] = True
        if "funeral" in domain:
            domain_signals["funeral_home"] = True
        if "church" in domain or "diocese" in domain:
            domain_signals["church"] = True

    # ── Determine classification ─────────────────────────────────────────
    result = _rule_based_classify(name_matches, order_data, domain_signals, entity.name)

    # ── Try Claude AI for uncertain cases ────────────────────────────────
    if result["confidence"] < 0.80:
        try:
            ai_result = _ai_classify(entity, name_matches, order_data)
            if ai_result and ai_result.get("confidence", 0) > result["confidence"]:
                result = ai_result
        except Exception:
            logger.exception("AI classification failed for %s", entity.name)

    # ── Apply results ────────────────────────────────────────────────────
    entity.customer_type = result.get("customer_type")
    entity.contractor_type = result.get("contractor_type")
    entity.classification_confidence = Decimal(str(round(result.get("confidence", 0), 3)))
    entity.classification_reasons = result.get("reasons", [])
    entity.is_active_customer = order_data.get("is_active", False)
    entity.first_order_year = order_data.get("first_order_year")

    if result.get("confidence", 0) >= 0.85:
        entity.classification_source = "auto_high"
    elif result.get("confidence", 0) >= 0.60:
        entity.classification_source = "pending_review"
    else:
        entity.classification_source = "pending_review"

    # Set role flags from classification
    if entity.customer_type == "funeral_home":
        entity.is_funeral_home = True
    elif entity.customer_type == "cemetery":
        entity.is_cemetery = True

    return result


def _get_order_signals(db: Session, customer_id: str | None) -> dict:
    """Analyze order history for classification signals."""
    if not customer_id:
        return {"total_orders": 0, "is_active": False}

    try:
        row = db.execute(text("""
            SELECT
                COUNT(*) as total_orders,
                MIN(so.created_at) as first_order,
                MAX(so.created_at) as last_order
            FROM sales_orders so
            WHERE so.customer_id = :cid AND so.status != 'cancelled'
        """), {"cid": customer_id}).fetchone()

        if not row or row.total_orders == 0:
            return {"total_orders": 0, "is_active": False}

        is_active = False
        if row.last_order:
            days_since = (datetime.now(timezone.utc) - row.last_order).days if hasattr(row.last_order, "tzinfo") and row.last_order.tzinfo else 365
            is_active = days_since < 365

        first_year = row.first_order.year if row.first_order else None

        return {
            "total_orders": row.total_orders,
            "is_active": is_active,
            "first_order_year": first_year,
            "last_order": row.last_order,
        }
    except Exception:
        logger.exception("Failed to query order history for customer %s", customer_id)
        return {"total_orders": 0, "is_active": False}


def _rule_based_classify(name_matches: dict, order_data: dict, domain_signals: dict, company_name: str) -> dict:
    """Rule-based classification from signals."""
    reasons = []
    customer_type = None
    contractor_type = None
    confidence = 0.0

    # Strong name match
    if "funeral_home" in name_matches:
        customer_type = "funeral_home"
        confidence = 0.92
        reasons.append(f"Name contains: {', '.join(name_matches['funeral_home'])}")
    elif "cemetery" in name_matches:
        customer_type = "cemetery"
        confidence = 0.90
        reasons.append(f"Name contains: {', '.join(name_matches['cemetery'])}")
    elif "contractor" in name_matches:
        customer_type = "contractor"
        confidence = 0.85
        reasons.append(f"Name contains: {', '.join(name_matches['contractor'])}")
        contractor_type = "general"
    elif "church" in name_matches:
        customer_type = "church"
        confidence = 0.88
        reasons.append(f"Name contains: {', '.join(name_matches['church'])}")
    elif "government" in name_matches:
        customer_type = "government"
        confidence = 0.90
        reasons.append(f"Name contains: {', '.join(name_matches['government'])}")
    elif "crematory" in name_matches:
        customer_type = "crematory"
        confidence = 0.88
        reasons.append(f"Name contains: {', '.join(name_matches['crematory'])}")
    elif "licensee" in name_matches:
        customer_type = "licensee"
        confidence = 0.85
        reasons.append(f"Name contains: {', '.join(name_matches['licensee'])}")
    elif "school" in name_matches:
        customer_type = "school"
        confidence = 0.90
        reasons.append(f"Name contains: {', '.join(name_matches['school'])} — occasional buyer")
    elif "fire_department" in name_matches:
        customer_type = "fire_department"
        confidence = 0.90
        reasons.append(f"Name contains: {', '.join(name_matches['fire_department'])} — occasional buyer")
    elif "utility" in name_matches:
        customer_type = "utility"
        confidence = 0.88
        reasons.append(f"Name contains: {', '.join(name_matches['utility'])} — occasional buyer")
    else:
        # No name match — default to contractor (most common non-FH type)
        total = order_data.get("total_orders", 0)
        customer_type = "contractor"
        if total > 0:
            contractor_type = "general"
            confidence = 0.55
            reasons.append(f"{total} orders, no clear name signal — defaulting to contractor")
        else:
            contractor_type = "occasional"
            confidence = 0.40
            reasons.append("No name signal, no order history — defaulting to contractor for review")

    # Domain boost
    for dtype, matched in domain_signals.items():
        if matched and dtype == customer_type:
            confidence = min(1.0, confidence + 0.05)
            reasons.append(f"Email domain confirms: {dtype}")

    # Order count boost for contractors
    total = order_data.get("total_orders", 0)
    if customer_type == "contractor":
        if total <= 3:
            contractor_type = "occasional"
            reasons.append(f"Only {total} orders — occasional buyer")
        elif total > 10:
            reasons.append(f"Active: {total} orders")

    return {
        "customer_type": customer_type,
        "contractor_type": contractor_type,
        "confidence": confidence,
        "reasons": reasons,
    }


def _ai_classify(entity: CompanyEntity, name_matches: dict, order_data: dict) -> dict | None:
    """Use Claude to classify uncertain companies."""
    try:
        from app.services.ai_service import call_anthropic
    except ImportError:
        return None

    prompt = f"""Classify this business customer for a precast concrete manufacturer in upstate New York.

Company: {entity.name}
City: {entity.city or 'unknown'}, State: {entity.state or 'unknown'}
Email: {entity.email or 'none'}
Total orders: {order_data.get('total_orders', 0)}
Active (12mo): {order_data.get('is_active', False)}
Name keyword matches: {json.dumps(name_matches)}

Classify as ONE of: funeral_home, cemetery, contractor, crematory, licensee, church, government, individual, other
For contractors also set contractor_type: full_service, wastewater_only, redi_rock_only, general, occasional

Return JSON: {{"customer_type": str, "contractor_type": str|null, "confidence": float, "reasons": [str]}}"""

    try:
        response = call_anthropic(prompt, max_tokens=200)
        if response:
            data = json.loads(response)
            return {
                "customer_type": data.get("customer_type"),
                "contractor_type": data.get("contractor_type"),
                "confidence": float(data.get("confidence", 0.5)),
                "reasons": data.get("reasons", ["AI classification"]),
            }
    except Exception:
        logger.exception("Claude classification failed for %s", entity.name)

    return None


def run_bulk_classification(db: Session, tenant_id: str, use_google_places: bool = False) -> dict:
    """Classify all unclassified companies for a tenant."""
    entities = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.company_id == tenant_id,
            CompanyEntity.is_aggregate == False,
        )
        .filter(
            (CompanyEntity.classification_source.is_(None)) |
            (CompanyEntity.classification_source == "pending_review")
        )
        .all()
    )

    total = len(entities)
    stats = {
        "total_processed": 0, "auto_classified": 0, "needs_review": 0,
        "unknown": 0, "errors": 0,
        "breakdown": {
            "funeral_home": 0, "contractor": 0, "cemetery": 0,
            "crematory": 0, "church": 0, "government": 0,
            "licensee": 0, "individual": 0, "other": 0, "unclassified": 0,
        },
    }

    for i, entity in enumerate(entities):
        try:
            result = classify_company(db, entity.id, use_google_places=use_google_places)
            ctype = result.get("customer_type") or "unclassified"
            conf = result.get("confidence", 0)

            if ctype in stats["breakdown"]:
                stats["breakdown"][ctype] += 1
            else:
                stats["breakdown"]["other"] += 1

            if conf >= 0.85:
                stats["auto_classified"] += 1
            elif conf >= 0.60:
                stats["needs_review"] += 1
            else:
                stats["unknown"] += 1

            stats["total_processed"] += 1
        except Exception:
            logger.exception("Classification error for %s", entity.id)
            stats["errors"] += 1

        # Commit every 50 records
        if (i + 1) % 50 == 0:
            db.commit()
            logger.info("Classified %d / %d companies", i + 1, total)
            time.sleep(0.5)

    db.commit()
    logger.info("Bulk classification complete: %s", stats)
    return stats
