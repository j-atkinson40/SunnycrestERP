"""Charge Matching Service — maps detected import charges to existing charge_library_items."""

import logging
import re
from difflib import SequenceMatcher
from sqlalchemy.orm import Session

from app.models.charge_library_item import ChargeLibraryItem
from app.models.price_list_import import PriceListImportItem

logger = logging.getLogger(__name__)

# Standard charge key mapping from detected charge patterns
CHARGE_KEY_MAP = {
    "delivery_fee": ["delivery fee", "delivery charge", "delivery"],
    "mileage_fuel_surcharge": ["mileage", "fuel surcharge", "fuel charge", "per mile", "travel charge", "mileage fee"],
    "after_hours_delivery": ["after hours", "after-hours", "emergency delivery", "emergency fee"],
    "rush_order_fee": ["rush fee", "rush charge", "rush order", "priority fee", "same day"],
    "return_trip_fee": ["return trip", "return visit", "second delivery", "second attempt"],
    "vault_personalization": ["personalization", "engraving", "legacy print", "inscription", "name plate", "memorial personalization", "custom engraving"],
    "disinterment_service": ["disinterment", "dis-interment", "exhumation"],
    "re_interment_service": ["re-interment", "reinterment", "re interment"],
    "liner_installation": ["liner installation", "liner install"],
    "grave_space_setup": ["grave setup", "grave space", "setup fee", "service fee"],
    "overtime_weekend_labor": ["overtime", "weekend", "saturday", "sunday"],
    "holiday_charge": ["holiday charge", "holiday fee", "holiday service", "holiday delivery"],
}


def _string_similarity(a: str, b: str) -> float:
    """Calculate string similarity ratio (0.0 - 1.0)."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _suggest_charge_key(extracted_name: str) -> str | None:
    """Suggest a charge_key based on the extracted charge name."""
    name_lower = extracted_name.lower()
    for key, patterns in CHARGE_KEY_MAP.items():
        for pattern in patterns:
            if pattern in name_lower:
                return key
    return None


def _suggest_pricing_type(charge_category: str | None, extracted_name: str) -> str:
    """Suggest pricing type based on category and name."""
    name_lower = extracted_name.lower()
    if "per mile" in name_lower or "mileage" in name_lower:
        return "per_mile"
    if charge_category == "surcharge":
        return "fixed"
    if charge_category == "delivery":
        return "variable"
    return "variable"


def match_charges_for_import(
    db: Session,
    tenant_id: str,
    import_items: list[PriceListImportItem],
) -> None:
    """Match charge-type import items to existing charge_library_items.

    Mutates the import_items in place with match results.
    """
    # Load all existing charges for the tenant
    existing_charges = (
        db.query(ChargeLibraryItem)
        .filter(ChargeLibraryItem.tenant_id == tenant_id)
        .all()
    )
    charge_by_key = {c.charge_key: c for c in existing_charges}

    for item in import_items:
        if item.match_status not in ("custom", "charge"):
            continue

        name = item.extracted_name or ""

        # Determine charge_key suggestion if not already set
        if not item.charge_key_suggestion:
            item.charge_key_suggestion = _suggest_charge_key(name)

        # Determine pricing type suggestion
        if not item.pricing_type_suggestion:
            item.pricing_type_suggestion = _suggest_pricing_type(
                item.charge_category, name
            )

        # Set charge_key_to_use
        if not item.charge_key_to_use:
            item.charge_key_to_use = item.charge_key_suggestion

        # Match 1: Exact charge_key match
        if item.charge_key_to_use and item.charge_key_to_use in charge_by_key:
            existing = charge_by_key[item.charge_key_to_use]
            item.charge_match_type = "exact_key"
            item.matched_charge_id = existing.id
            item.matched_charge_name = existing.charge_name
            if item.action == "skip":
                item.action = "create_custom"  # re-enable for charge library
            logger.info(
                "Charge '%s' matched by key to '%s'", name, existing.charge_name
            )
            continue

        # Match 2: Fuzzy name match
        best_match = None
        best_score = 0.0
        for charge in existing_charges:
            score = _string_similarity(name, charge.charge_name)
            if score > best_score and score >= 0.75:
                best_score = score
                best_match = charge

        if best_match:
            item.charge_match_type = "name_similarity"
            item.matched_charge_id = best_match.id
            item.matched_charge_name = best_match.charge_name
            item.charge_key_to_use = best_match.charge_key
            if item.action == "skip":
                item.action = "create_custom"
            logger.info(
                "Charge '%s' fuzzy matched to '%s' (score=%.2f)",
                name, best_match.charge_name, best_score,
            )
            continue

        # No match — will create new
        item.charge_match_type = "no_match"
        if item.action == "skip":
            item.action = "create_custom"
        logger.info("Charge '%s' — no match found, will create new", name)

    db.flush()
