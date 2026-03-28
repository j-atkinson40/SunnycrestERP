"""Use Claude Sonnet to analyze price lists and match to Wilbert catalog."""
import json
import logging
import re
from decimal import Decimal

import anthropic
from sqlalchemy.orm import Session

from app.config import settings
from app.models.price_list_import import PriceListImport, PriceListImportItem
from app.models.product_catalog_template import ProductCatalogTemplate

logger = logging.getLogger(__name__)
ANALYSIS_MODEL = "claude-sonnet-4-20250514"


def _try_parse_json(cleaned: str, raw_response: str, was_truncated: bool) -> dict | None:
    """Try multiple strategies to parse JSON from Claude's response."""
    # Strategy 1: direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 2: fix trailing commas more aggressively
    attempt = re.sub(r",\s*([}\]])", r"\1", cleaned)
    try:
        return json.loads(attempt)
    except json.JSONDecodeError:
        pass

    # Strategy 3: if truncated, try to close the JSON structure
    if was_truncated:
        # Find the last complete item by looking for the last "},"
        last_complete = cleaned.rfind("},")
        if last_complete > 0:
            truncated = cleaned[: last_complete + 1]  # up to and including the }
            # Close the items array and summary
            truncated += '], "summary": {"total_items": 0, "matched_high": 0, "matched_low": 0, "unmatched": 0}}'
            truncated = re.sub(r",\s*([}\]])", r"\1", truncated)
            try:
                return json.loads(truncated)
            except json.JSONDecodeError:
                pass

    # Strategy 4: extract just the items array
    items_match = re.search(r'"items"\s*:\s*\[', cleaned)
    if items_match:
        # Find all complete item objects
        items_start = items_match.end()
        items = []
        depth = 0
        current_start = None
        for i, ch in enumerate(cleaned[items_start:], start=items_start):
            if ch == "{":
                if depth == 0:
                    current_start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and current_start is not None:
                    item_str = cleaned[current_start : i + 1]
                    item_str = re.sub(r",\s*([}\]])", r"\1", item_str)
                    try:
                        items.append(json.loads(item_str))
                    except json.JSONDecodeError:
                        pass
                    current_start = None
            elif ch == "]" and depth == 0:
                break

        if items:
            logger.info("Recovered %d items via manual extraction", len(items))
            return {
                "items": items,
                "summary": {
                    "total_items": len(items),
                    "matched_high": 0,
                    "matched_low": 0,
                    "unmatched": 0,
                },
            }

    logger.error("All JSON parse strategies failed for response (%d chars)", len(raw_response))
    return None


WILBERT_VARIATIONS = """
Common Wilbert product name variations:
- Monticello: MON, Monti, Monticello Std, Monticello OS
- Venetian: VEN, Venetian Std, White Venetian, Gold Venetian
- Graveliner: GL, Grave Liner, Liner, GVL
- Salute: SAL, Salute to Veterans
- Continental: CON, Cont
- Triune: TRI, Stainless Triune, SS Triune, Cameo Rose, CR Triune, Bronze Triune, Copper Triune
- Veteran: VET, Veterans, Veteran Triune
- Tribute: White Tribute, Gray Tribute
- Oversize variants: OS, O/S, Oversize, OVS
- 1-Piece vs 2-Piece: 1P, 2P, 1-PC, 2-PC, One Piece, Two Piece
- Infant variants: INF, Infant, Baby, Loved & Cherished
- Urn Vault: UV, Urn Vlt
- Wilbert Bronze: WBR, Bronze
- Monarch: MRC

IMPORTANT MATCHING RULES:
- When a price list item ALREADY specifies a color (e.g. "Gold Venetian Burial Vault", "White Tribute Burial Vault", "Gray Tribute"), match it directly to the corresponding catalog template as HIGH_CONFIDENCE. Do NOT treat these as color-split results — they are explicit matches.
- "Tribute" without a color specification (White or Gray) should be matched to BOTH "White Tribute" and "Gray Tribute" as two separate high_confidence items with the same price. Create TWO items in your output — one matched to White Tribute and one to Gray Tribute. Only split when no color is specified.
- Similarly, "Venetian" without a color should match to BOTH "White Venetian" and "Gold Venetian" as two items. Only split when no color is specified. If the price list says "Gold Venetian" or "White Venetian", match directly at high_confidence.
- Products in an urn vault section of the price list MUST be matched to the Urn Vault category templates, NOT the Burial Vault templates. Use the exact urn vault template name (e.g. "Monticello Urn Vault" not "Monticello Burial Vault").
- CRITICAL: For items in an urn vault section, ALWAYS include "Urn Vault" in the extracted_name. For example, if the price list has a section labeled "URN VAULTS" and lists "Monticello" under it, the extracted_name MUST be "Monticello Urn Vault", NOT just "Monticello". The section context determines the product type.
- If a price list item says just "Veteran" in an urn vault section, match it to "Veteran Urn Vault" with extracted_name "Veteran Urn Vault".
- Similarly, "Venetian" in an urn vault section → extracted_name "Venetian Urn Vault", "Salute" in an urn vault section → extracted_name "Salute Urn Vault", etc.

OVERSIZE VAULT HANDLING:
- Oversize vaults come in different dimensions (e.g. 31", 33", 34", 36"). Each size is a separate product.
- When you find an oversize vault with a specific dimension, create it as a SEPARATE item with match_status "custom" (not unmatched).
- Set the extracted_name to include the vault line name plus the size, like: "Continental 34\"", "Monticello 31\"", "Venetian 36\"".
- Do NOT group multiple oversize sizes together. Each size+vault combination is its own product.
- Match oversize vaults to the base vault line template (e.g. Continental Burial Vault) but set match_status to "low_confidence" with reasoning explaining it's an oversize variant, so the manufacturer can confirm.
- If an oversize vault has no specific dimension (just "OS" or "Oversize"), name it with "Oversize" like "Continental Oversize".

CLASSIFICATION PRIORITY ORDER:
1. First check if item is an overage/add-on charge (Extra X, Additional X, X Over N)
2. Then check if item is an equipment bundle (Full Equipment, X Only, X & Y)
3. Then check if item is a regular product
4. Default to unmatched if none match
An item matching overage patterns should NEVER be classified as a bundle, even if it contains equipment keywords.

OVERAGE / ADD-ON CHARGE DETECTION:
- Items like "Extra Chairs (Over 8)", "Additional Chair", "Chairs Over 8", "Extra Chairs" are per-unit overage charges, NOT bundles.
- These are charges for additional units beyond a standard threshold.
- Set match_status to "custom" (they are custom products the manufacturer defines).
- Do NOT set match_status to "bundle" for overage items.
- Examples:
  * "Extra Chairs (Over 8)" → match_status "custom", NOT a bundle
  * "Additional Chairs" → match_status "custom", NOT a bundle

EQUIPMENT BUNDLE DETECTION (CRITICAL — do NOT mark these as unmatched):
- Items like "Full Equipment", "Equipment Package", "Equipment w/o Chairs", "Setup Package", "Full Setup" are equipment BUNDLES — flat-rate packages.
- ALWAYS set match_status to "bundle" for these items. NEVER set them to "unmatched".
- Set template_id to null, template_name to the bundle name, confidence to 0.90.

PARTIAL BUNDLE DISAMBIGUATION — "ONLY" SUFFIX:
- When a line item name ends with "Only" it is ALWAYS a partial equipment bundle, NEVER an individual product.
- "Only" indicates this is a bundle containing just that one item as a package option.
- Examples:
  * "Lowering Device Only" → match_status "bundle", extracted_name "Lowering Device Only"
  * "Tent Only" → match_status "bundle", extracted_name "Tent Only"
  * "Chairs Only" → match_status "bundle", extracted_name "Chairs Only"
- Do NOT match these against individual product templates. Do NOT strip "Only" from the name.
- The bundle name should be preserved exactly as written on the price list.

COMPOUND BUNDLE NAMES WITH AMPERSAND (&):
- Line items with "&" connecting equipment item names are partial bundles containing those items.
- "[Item] & [Item]" → match_status "bundle" containing both named items.
- Examples:
  * "Lowering Device & Grass" → bundle containing lowering device + grass mats
  * "Lowering Device & Tent" → bundle containing lowering device + tent
  * "Tent & Chairs" → bundle containing tent + chairs
- For compound bundles, set bundle_components_suggested based on the named items:
  "bundle_components_suggested": [
    {"component": "Lowering Device", "evidence": "Named explicitly in bundle title 'Lowering Device & Grass'"},
    {"component": "Grass Mats", "evidence": "Named explicitly in bundle title as 'Grass' — refers to grass mats"}
  ]
- "Grass" in a bundle name refers to grass mats / artificial turf. Map "Grass" → "Grass Mats".
- This is the ONE case where component suggestions are based on name — because the components are explicitly stated in the bundle title.

EVIDENCE-BASED COMPONENT SUGGESTIONS (for non-compound bundles):
- Do NOT assume bundle contents based on bundle name alone. Different manufacturers define bundles differently.
- Only suggest components if you find evidence in the price list: individual equipment line items whose prices sum to approximately the bundle price (within 20%).
- If evidence found:
  "bundle_components_suggested": [
    {"component": "Lowering Device", "evidence": "Found 'Lowering Device — $65' as individual item on price list"}
  ]
- If NO evidence: set bundle_components_suggested to an empty array [].

CONDITIONAL PRICING — TWO FORMATS:

FORMAT A — TABULAR (two price columns):
Some price lists present conditional pricing as a table with two price columns. Recognize these column header patterns as conditional pricing indicators:
  "With Our Product" / "Without Our Product"
  "With Vault" / "Without Vault"
  "With Product" / "Without Product"
  "W/ Product" / "W/O Product"
  "Vault Order" / "Equipment Only"
When you detect a table with two price columns matching these patterns:
- Extract BOTH prices from each row
- "With Our Product" column = with_vault_price (typically the lower price)
- "Without Our Product" column = standalone_price (typically the higher price)
- Set has_conditional_pricing = true
- Do NOT set price_variant_type — both prices come from one row

Return format for tabular conditional pricing:
{
  "raw_text": "Full Equipment  $300  $600",
  "extracted_name": "Full Equipment",
  "extracted_price": 300.00,
  "extracted_price_with_vault": 300.00,
  "extracted_price_standalone": 600.00,
  "has_conditional_pricing": true,
  "match_status": "bundle"
}

FORMAT B — SEPARATE LINE ITEMS (variant name pairs):
When you see two items that appear to be the same bundle at different prices with variant name suffixes, recognize them as a conditional pricing pair:
  "[Bundle Name] with Vault" / "[Bundle Name] Only"
  "[Bundle Name] w/ Vault" / "[Bundle Name] w/o Vault"
  "[Bundle Name] — Vault Order" / "[Bundle Name] — Equipment Only"
The with-vault item has the lower price. The standalone item has the higher price.
When detected as a pair — mark both items:
- The with-vault item: set is_bundle_price_variant = true, price_variant_type = "with_vault"
- The standalone item: set is_bundle_price_variant = true, price_variant_type = "standalone"
- Set a matching bundle_variant_group on both items (use the base bundle name without the suffix)
- Post-processing will merge them into a single conditional pricing item.

"With Our Product" and "Without Our Product" are price tier headers — NEVER treat them as product names or match them against product templates.

CHARGE DETECTION:
After checking for overage charges, equipment bundles, and products — classify remaining items as charges if they match these patterns:

OVERAGE CHARGES (match_status: custom, charge_category: surcharge):
Already handled by existing overage patterns. These have item_type "overage_charge".

FLAT SERVICE FEES (match_status: custom, charge_category: service):
- Setup fee, Service fee, Administrative fee
- After-hours fee, After hours delivery, Emergency delivery
- Holiday charge, Holiday delivery, Holiday service
- Weekend charge, Weekend delivery
- Return trip, Return visit, Second delivery attempt

MILEAGE AND FUEL (match_status: custom, charge_category: delivery):
- Mileage charge, Fuel surcharge, Fuel charge
- Per mile, Mileage fee, Travel charge
- Delivery charge, Delivery fee (if not already a product)

RUSH AND EMERGENCY (match_status: custom, charge_category: surcharge):
- Rush fee, Rush charge, Rush order
- Emergency fee, Emergency delivery, Priority fee
- Same day delivery, Same day service

PERSONALIZATION (match_status: custom, charge_category: service):
- Personalization, Engraving, Legacy print
- Inscription, Custom engraving, Name plate
- Memorial personalization

DISINTERMENT AND REINTERMENT (match_status: custom, charge_category: service):
- Disinterment, Dis-interment
- Re-interment, Reinterment
- Removal and reinterment, Exhumation

For detected charges, set:
- match_status: "custom"
- charge_category: "service" | "delivery" | "surcharge" | "labor"
- charge_key_suggestion: the most likely matching key from this list:
  delivery_fee, mileage_fuel_surcharge, after_hours_delivery, rush_order_fee,
  return_trip_fee, vault_personalization, disinterment_service, re_interment_service,
  liner_installation, grave_space_setup, overtime_weekend_labor, holiday_charge
- If no standard key matches, set charge_key_suggestion to null.
"""


EQUIPMENT_KEYWORDS = {
    "lowering", "device", "tent", "grass", "mats", "chairs",
    "straps", "equipment", "setup", "canopy", "cremation", "table",
}


_OVERAGE_PATTERNS = [
    re.compile(r"extra\s+\w+\s*\(over\s+\d+\)", re.IGNORECASE),   # "Extra Chairs (Over 8)"
    re.compile(r"additional\s+\w+", re.IGNORECASE),                 # "Additional Chair"
    re.compile(r"\w+\s+over\s+\d+", re.IGNORECASE),                # "Chairs over 8"
    re.compile(r"extra\s+\w+", re.IGNORECASE),                      # "Extra Chairs"
]


def _reclassify_bundle_items(items: list[dict]) -> list[dict]:
    """Post-process Claude's output to catch misclassified equipment bundles.

    Guard 0: Overage/add-on charges must NOT be bundles.
    Guard 1: Items ending in "Only" must be bundles.
    Guard 2: Items with " & " between equipment keywords must be bundles.
    """
    for item in items:
        name = (item.get("extracted_name") or "").strip()
        status = item.get("match_status", "")

        # Guard 0: Overage/add-on charges — must never be classified as bundle
        is_overage = any(p.search(name) for p in _OVERAGE_PATTERNS)
        if is_overage:
            if status == "bundle":
                logger.info(
                    "Reclassifying '%s' from bundle to custom — overage charge",
                    name,
                )
                item["match_status"] = "custom"
                item["match"] = {
                    "template_id": None,
                    "template_name": name,
                    "confidence": 0.85,
                    "reasoning": f"Overage/add-on charge — per-unit charge beyond a threshold",
                }
            continue  # skip all other guards for overage items

        # Guard 1: "Only" suffix → always a bundle
        if name.lower().endswith(" only") and status != "bundle":
            logger.info(
                "Reclassifying '%s' from %s to bundle — ends with 'Only'",
                name, status,
            )
            item["match_status"] = "bundle"
            if item.get("match"):
                item["match"]["template_id"] = None
                item["match"]["reasoning"] = (
                    f"Reclassified: '{name}' ends with 'Only' — partial equipment bundle"
                )
            else:
                item["match"] = {
                    "template_id": None,
                    "template_name": name,
                    "confidence": 0.90,
                    "reasoning": f"Reclassified: '{name}' ends with 'Only' — partial equipment bundle",
                }

        # Guard 2: " & " between equipment-related words → compound bundle
        if " & " in name and status != "bundle":
            parts = name.lower().split(" & ")
            all_equipment = all(
                any(kw in part for kw in EQUIPMENT_KEYWORDS) for part in parts
            )
            if all_equipment:
                logger.info(
                    "Reclassifying '%s' from %s to bundle — compound equipment name",
                    name, status,
                )
                item["match_status"] = "bundle"
                # Build component suggestions from the compound name
                components = []
                for part in parts:
                    part_clean = part.strip().title()
                    # Map common short names
                    if "grass" in part.lower():
                        part_clean = "Grass Mats"
                    elif "tent" in part.lower():
                        part_clean = "Cemetery Tent"
                    elif "chair" in part.lower():
                        part_clean = "Chairs"
                    elif "lowering" in part.lower():
                        part_clean = "Lowering Device"
                    components.append({
                        "component": part_clean,
                        "evidence": f"Named explicitly in bundle title '{name}'",
                    })
                item["match"] = {
                    "template_id": None,
                    "template_name": name,
                    "confidence": 0.90,
                    "reasoning": f"Compound equipment bundle — components named in title",
                    "bundle_components_suggested": components,
                }

    return items


def _build_bundle_reasoning(match: dict, status: str) -> str | None:
    """Build enriched reasoning for bundle items that includes component info."""
    reasoning = match.get("reasoning", "")
    if status != "bundle":
        return reasoning or None

    components = match.get("bundle_components_suggested", [])
    if not components:
        return reasoning or None

    # Append component suggestion details to reasoning
    comp_parts = []
    for comp in components:
        name = comp.get("component", "")
        evidence = comp.get("evidence", "")
        if "Named explicitly" in evidence:
            comp_parts.append(f"{name} [named-in-title]")
        elif evidence:
            comp_parts.append(f"{name} [price-evidence]")
        else:
            comp_parts.append(name)

    if comp_parts:
        suffix = " | Suggested components: " + ", ".join(comp_parts)
        reasoning = (reasoning or "") + suffix

    return reasoning or None


_URN_INDICATORS = re.compile(
    r"\burn\b|\bUV\b|\burn\s*vlt\b|\burn\s*vault\b",
    re.IGNORECASE,
)


def _fix_urn_vault_items(items: list[dict], templates: list) -> list[dict]:
    """Post-process: ensure urn vault items have 'Urn Vault' in the name and
    are matched to the correct urn vault template (not burial vault).

    Three detection strategies:
    1. extracted_name contains urn indicators (urn, UV, urn vlt)
    2. Claude set template_name to an urn vault but template_id points to burial vault
    3. Claude matched to a burial vault template but extracted_name says "Urn Vault"
    """
    # Build lookups
    urn_templates_by_base: dict[str, object] = {}
    burial_template_ids: set[str] = set()
    for t in templates:
        name_lower = t.product_name.lower()
        if "urn vault" in name_lower:
            base = name_lower.replace(" urn vault", "").strip()
            urn_templates_by_base[base] = t
        elif "burial vault" in name_lower:
            burial_template_ids.add(t.id)

    for item in items:
        extracted = item.get("extracted_name", "")
        raw = item.get("raw_text", "")
        match = item.get("match") or {}
        template_name = match.get("template_name", "")
        template_id = match.get("template_id")

        # template_name already says "Urn Vault" — just fix extracted_name and template_id
        if template_name and "urn vault" in template_name.lower():
            if "urn vault" not in extracted.lower():
                item["extracted_name"] = template_name
            # Ensure template_id also points to the urn vault template (not burial vault)
            tpl_base = template_name.lower().replace(" urn vault", "").strip()
            if tpl_base in urn_templates_by_base:
                correct_tpl = urn_templates_by_base[tpl_base]
                if template_id != correct_tpl.id:
                    logger.info(
                        "Fixing urn vault template_id: %s → %s for '%s'",
                        template_id, correct_tpl.id, template_name,
                    )
                    match["template_id"] = correct_tpl.id
            continue

        # Detect: is this supposed to be an urn vault?
        is_urn = False

        # Strategy 1: extracted_name or raw_text has urn indicators
        context = f"{extracted} {raw}"
        if _URN_INDICATORS.search(context):
            is_urn = True

        # Strategy 2: Claude matched to a burial vault template, but the
        # extracted_name contains "Urn Vault" (Claude got the name right but wrong ID)
        if not is_urn and "urn vault" in extracted.lower():
            is_urn = True

        if not is_urn:
            continue

        # Find the base vault line name
        # Strip common suffixes to get "monticello", "venetian", etc.
        base = extracted.lower()
        for suffix in [" urn vault", " urn vlt", " uv", " burial vault"]:
            base = base.replace(suffix, "")
        base = base.strip()

        # Also try from template_name
        if base not in urn_templates_by_base:
            alt_base = template_name.lower().replace(" burial vault", "").strip()
            if alt_base in urn_templates_by_base:
                base = alt_base

        # Correct to the urn vault template
        if base in urn_templates_by_base:
            correct_tpl = urn_templates_by_base[base]
            logger.info(
                "Correcting urn vault: '%s' → '%s' (template %s)",
                extracted, correct_tpl.product_name, correct_tpl.id,
            )
            item["match"] = {
                **(match or {}),
                "template_id": correct_tpl.id,
                "template_name": correct_tpl.product_name,
                "reasoning": (match.get("reasoning", "") or "")
                + " [Corrected: matched to urn vault template]",
            }
            # Also fix extracted_name to include "Urn Vault"
            if "urn vault" not in extracted.lower():
                item["extracted_name"] = correct_tpl.product_name
        else:
            # No template match — at minimum ensure name says "Urn Vault"
            if "urn vault" not in extracted.lower():
                if "burial vault" in extracted.lower():
                    item["extracted_name"] = extracted.replace("Burial Vault", "Urn Vault").replace("burial vault", "Urn Vault")
                else:
                    item["extracted_name"] = f"{extracted} Urn Vault"
            if template_name and "burial vault" in template_name.lower():
                item["match"]["template_name"] = template_name.replace("Burial Vault", "Urn Vault")
            logger.info("Corrected urn vault name: '%s' → '%s'", extracted, item["extracted_name"])

    return items


def _group_bundle_variants(items: list[dict]) -> list[dict]:
    """Post-process: merge Format B variant pairs into single conditional pricing items.

    Finds items with is_bundle_price_variant=True, groups by bundle_variant_group,
    merges with_vault and standalone variants into one item with both prices.
    """
    variant_groups: dict[str, list[dict]] = {}
    for item in items:
        if not item.get("is_bundle_price_variant"):
            continue
        key = item.get("bundle_variant_group") or item.get("extracted_name", "")
        if key not in variant_groups:
            variant_groups[key] = []
        variant_groups[key].append(item)

    for group_name, group_items in variant_groups.items():
        with_vault = None
        standalone = None
        for gi in group_items:
            if gi.get("price_variant_type") == "with_vault":
                with_vault = gi
            elif gi.get("price_variant_type") == "standalone":
                standalone = gi

        if with_vault and standalone:
            # Merge into the with_vault item
            with_vault["extracted_price_with_vault"] = with_vault.get("extracted_price")
            with_vault["extracted_price_standalone"] = standalone.get("extracted_price")
            with_vault["has_conditional_pricing"] = True
            with_vault["extracted_name"] = group_name  # Use base name
            # Mark standalone as absorbed
            standalone["match_status"] = "absorbed_into_variant"
            standalone["action"] = "skip"
            logger.info(
                "Merged bundle variant pair '%s': vault=$%s, standalone=$%s",
                group_name,
                with_vault.get("extracted_price"),
                standalone.get("extracted_price"),
            )

    # Filter out absorbed items
    return [i for i in items if i.get("match_status") != "absorbed_into_variant"]


_CHARGE_PATTERNS = {
    "service": [
        re.compile(r"setup\s+fee", re.IGNORECASE),
        re.compile(r"service\s+fee", re.IGNORECASE),
        re.compile(r"after[\s-]*hours", re.IGNORECASE),
        re.compile(r"emergency\s+(delivery|fee|service)", re.IGNORECASE),
        re.compile(r"return\s+(trip|visit)", re.IGNORECASE),
        re.compile(r"second\s+(delivery|attempt)", re.IGNORECASE),
        re.compile(r"personali[sz]ation", re.IGNORECASE),
        re.compile(r"engrav(ing|e)", re.IGNORECASE),
        re.compile(r"legacy\s+print", re.IGNORECASE),
        re.compile(r"inscription", re.IGNORECASE),
        re.compile(r"name\s*plate", re.IGNORECASE),
        re.compile(r"dis[\s-]*interment", re.IGNORECASE),
        re.compile(r"re[\s-]*interment", re.IGNORECASE),
        re.compile(r"exhumation", re.IGNORECASE),
        re.compile(r"liner\s+install", re.IGNORECASE),
        re.compile(r"grave\s+(space\s+)?setup", re.IGNORECASE),
    ],
    "delivery": [
        re.compile(r"mileage", re.IGNORECASE),
        re.compile(r"fuel\s+(sur)?charge", re.IGNORECASE),
        re.compile(r"per\s+mile", re.IGNORECASE),
        re.compile(r"travel\s+charge", re.IGNORECASE),
        re.compile(r"delivery\s+(fee|charge)", re.IGNORECASE),
    ],
    "surcharge": [
        re.compile(r"rush\s+(fee|charge|order)", re.IGNORECASE),
        re.compile(r"priority\s+fee", re.IGNORECASE),
        re.compile(r"same\s+day", re.IGNORECASE),
        re.compile(r"holiday", re.IGNORECASE),
        re.compile(r"weekend\s+(charge|delivery|fee)", re.IGNORECASE),
    ],
    "labor": [
        re.compile(r"overtime", re.IGNORECASE),
        re.compile(r"saturday\s+(charge|fee|labor|delivery)", re.IGNORECASE),
        re.compile(r"sunday\s+(charge|fee|labor|delivery)", re.IGNORECASE),
    ],
}


def _classify_charge_items(items: list[dict]) -> list[dict]:
    """Post-process: classify items as charges based on name patterns.

    Items that match charge patterns get charge_category set.
    Items already classified as custom by Claude's overage detection keep their status.
    """
    for item in items:
        name = (item.get("extracted_name") or "").strip()
        status = item.get("match_status", "")

        # Skip items already well-classified
        if status in ("high_confidence", "low_confidence", "bundle"):
            continue

        # If Claude already set charge_category, keep it
        if item.get("charge_category"):
            continue

        # Check if item matches charge patterns
        for category, patterns in _CHARGE_PATTERNS.items():
            if any(p.search(name) for p in patterns):
                item["charge_category"] = category
                if status != "custom":
                    item["match_status"] = "custom"
                break

    return items


def _promote_exact_matches(items: list[dict], templates: list) -> list[dict]:
    """Promote low_confidence items to high_confidence if they exactly match a template.

    Claude sometimes marks color-specific vaults (e.g. 'Gold Venetian Burial Vault')
    as low_confidence when the price list already has the full name. If the template_id
    or template_name is an exact match, promote to high_confidence.
    """
    template_names = {t.product_name.lower(): t for t in templates}
    template_ids = {t.id for t in templates}

    for item in items:
        if item.get("match_status") != "low_confidence":
            continue
        # Don't promote bundles
        match = item.get("match") or {}
        template_id = match.get("template_id")
        template_name = (match.get("template_name") or "").strip()

        # Check 1: template_id is a valid template
        if template_id and template_id in template_ids:
            item["match_status"] = "high_confidence"
            logger.info(
                "Promoted '%s' to high_confidence — exact template_id match",
                item.get("extracted_name"),
            )
            continue

        # Check 2: template_name exactly matches a catalog template
        if template_name.lower() in template_names:
            tpl = template_names[template_name.lower()]
            item["match_status"] = "high_confidence"
            match["template_id"] = tpl.id
            logger.info(
                "Promoted '%s' to high_confidence — exact template_name match '%s'",
                item.get("extracted_name"), tpl.product_name,
            )

    return items


def _apply_billing_terms_to_settings(db: Session, tenant_id: str, billing_terms: dict) -> None:
    """Auto-populate tenant settings from extracted billing terms.

    Only fills in values that are currently null/unset — never overwrites
    existing configuration.
    """
    try:
        from app.models.company import Company

        company = db.query(Company).filter(Company.id == tenant_id).first()
        if not company:
            return

        settings_map = {
            "early_payment_discount_percentage": billing_terms.get("early_payment_discount_percent"),
            "early_payment_discount_cutoff_day": billing_terms.get("early_payment_discount_days"),
            "finance_charge_rate_monthly": billing_terms.get("finance_charge_rate_monthly"),
            "finance_charge_basis": billing_terms.get("finance_charge_basis"),
        }

        updated: list[str] = []
        for key, value in settings_map.items():
            if value is None:
                continue
            # Only set if not already configured
            existing = company.settings.get(key) if company.settings else None
            if existing is None:
                company.set_setting(key, value)
                updated.append(key)

        if updated:
            db.flush()
            logger.info(
                "Auto-populated billing settings for tenant %s: %s",
                tenant_id,
                ", ".join(updated),
            )
    except Exception as exc:
        logger.warning("Could not apply billing terms to settings: %s", exc)


_DIMENSION_RE = re.compile(r'\d+\s*"')


def _resolve_final_name(
    extracted_name: str,
    template_id: str | None,
    template_map: dict[str, str],
    match: dict,
) -> str:
    """Choose the best final product name.

    Normally we prefer the canonical template name so products are named
    consistently.  Exception: when the extracted name contains a dimension
    suffix (e.g. 34\", 38\") that the template name doesn't have — that
    means it's an oversize variant and we must keep the specific size.
    In that case we build the name as "<base line> <dimension> Burial Vault".
    """
    canonical = template_map.get(template_id or "", "") or match.get("template_name") or ""
    extracted = extracted_name or ""

    # If extracted name has a dimension and canonical doesn't, it's an oversize variant
    dim_in_extracted = _DIMENSION_RE.search(extracted)
    dim_in_canonical = _DIMENSION_RE.search(canonical)

    if dim_in_extracted and not dim_in_canonical:
        # Build a proper name: strip generic suffixes from extracted, keep dimension
        # e.g. "Graveliner 34\"" → "Graveliner 34\" Burial Vault"
        name = extracted.strip()
        # Append "Burial Vault" if neither name already has it
        if "burial vault" not in name.lower() and "burial vault" in canonical.lower():
            name = f"{name} Burial Vault"
        logger.info(
            "Preserving dimension variant name: '%s' (template: '%s')",
            name, canonical,
        )
        return name

    # Default: canonical template name wins
    return canonical or extracted or "Unknown"


def analyze_price_list(db: Session, import_id: str) -> None:
    """Run Claude analysis on an extracted price list."""
    imp = db.query(PriceListImport).filter(PriceListImport.id == import_id).first()
    if not imp or not imp.raw_extracted_text:
        return

    imp.status = "matching"
    db.commit()

    # Build catalog reference from product_catalog_templates
    templates = (
        db.query(ProductCatalogTemplate)
        .filter(ProductCatalogTemplate.preset == "manufacturing")
        .all()
    )

    catalog_ref = "\n".join(
        [
            f"Template ID: {t.id} | Name: {t.product_name} | Category: {t.category} | SKU Prefix: {t.sku_prefix}"
            for t in templates
        ]
    )

    # Truncate text to ~50000 chars
    text = imp.raw_extracted_text[:50000]

    system_prompt = (
        "You are analyzing a funeral vault manufacturer's price list to extract "
        "products and prices, then matching them to a known product catalog.\n"
        "Be precise about prices — extract the exact dollar amount shown.\n"
        "Be thorough about product names — recognize variations and abbreviations.\n"
        "Be honest about confidence — flag anything ambiguous.\n"
        "IMPORTANT: When you match a product to the catalog, use the EXACT template_name "
        "from the catalog as the template_name in your response. Do NOT modify, shorten, "
        "or create your own product name. For example, if the catalog has "
        "'Monticello Urn Vault', return exactly 'Monticello Urn Vault' — not "
        "'Monticello (Urn)' or 'Monticello Urn'.\n"
        "Return JSON only. No other text."
    )

    user_prompt = f"""Here is a price list from a Wilbert burial vault licensee. Extract every product and its selling price, then match each product to the known catalog below.

KNOWN PRODUCT CATALOG:
{catalog_ref}

{WILBERT_VARIATIONS}

PRICE LIST CONTENT:
{text}

For each item in the price list, return:
{{
  "items": [
    {{
      "raw_text": "the original line from the price list",
      "extracted_name": "your interpretation of the product name",
      "extracted_price": 0.00,
      "extracted_sku": "SKU if present or null",
      "extracted_price_with_vault": null,
      "extracted_price_standalone": null,
      "has_conditional_pricing": false,
      "is_bundle_price_variant": false,
      "price_variant_type": null,
      "bundle_variant_group": null,
      "charge_category": null,
      "charge_key_suggestion": null,
      "match": {{
        "template_id": "uuid-string or null",
        "template_name": "matched product name",
        "confidence": 0.95,
        "reasoning": "explanation"
      }},
      "match_status": "high_confidence|low_confidence|unmatched|bundle"
    }}
  ],
  "summary": {{
    "total_items": 0,
    "matched_high": 0,
    "matched_low": 0,
    "unmatched": 0
  }}
}}

Confidence thresholds:
- high_confidence (>= 0.85): clear match
- low_confidence (0.60-0.84): likely match but needs confirmation
- unmatched (< 0.60): no confident match

Also look for and extract any billing or payment policy information present in the document.
Return these in an additional top-level field alongside "items" and "summary":

"billing_terms": {{
  "payment_terms_days": <integer or null>,
  "early_payment_discount_percent": <decimal or null>,
  "early_payment_discount_days": <integer or null>,
  "finance_charge_rate_monthly": <decimal or null>,
  "finance_charge_basis": <"past_due_only" | "total_balance" | null>,
  "holidays": <string[] or null>,
  "raw_text": "<the exact text found in the document describing billing terms>"
}} or null if no billing terms are found.

Examples of billing term text to look for:
- "Net 30", "Due on receipt", "Payment due within 30 days"
- "5% discount if paid by the 15th", "2% 10 net 30"
- "Finance charge of 2% per month on balances over 30 days"
- "Observed holidays: New Year's Day, Memorial Day, July 4th, ..."
- Any section titled "Terms", "Payment Terms", "Billing Policy" """

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=ANALYSIS_MODEL,
            max_tokens=16384,  # Large enough for 50+ product price lists
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        response_text = message.content[0].text
        stop_reason = message.stop_reason

        # If truncated (max_tokens hit), try to repair the JSON
        if stop_reason == "max_tokens":
            logger.warning("Claude response was truncated — attempting JSON repair")

        # Strip code fences if present
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", response_text.strip())
        cleaned = re.sub(r"\n?\s*```$", "", cleaned)

        # Fix common JSON issues: trailing commas
        cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)

        parsed = _try_parse_json(cleaned, response_text, stop_reason == "max_tokens")
        if parsed is None:
            imp.status = "failed"
            imp.error_message = "Could not parse Claude response as JSON"
            imp.claude_analysis = response_text[:10000]
            db.commit()
            return

        # Post-process: reclassify misclassified bundle items
        if "items" in parsed:
            parsed["items"] = _reclassify_bundle_items(parsed["items"])
            parsed["items"] = _group_bundle_variants(parsed["items"])
            parsed["items"] = _fix_urn_vault_items(parsed["items"], templates)
            parsed["items"] = _promote_exact_matches(parsed["items"], templates)
            parsed["items"] = _classify_charge_items(parsed["items"])

        # Store analysis
        imp.claude_analysis = json.dumps(parsed)

        # Extract and store billing terms if found
        billing_terms = parsed.get("billing_terms")
        if billing_terms and isinstance(billing_terms, dict) and billing_terms.get("raw_text"):
            imp.billing_terms_json = json.dumps(billing_terms)
            _apply_billing_terms_to_settings(db, imp.tenant_id, billing_terms)

        imp.extraction_token_usage = json.dumps(
            {
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            }
        )

        # Build a template lookup map for canonical names
        template_map = {t.id: t.product_name for t in templates}

        # Create import items
        high = low = unmatched = 0
        for item_data in parsed.get("items", []):
            match = item_data.get("match") or {}
            status = item_data.get("match_status", "unmatched")

            # Charge items always default to create_custom (add to library)
            is_charge = bool(item_data.get("charge_category"))

            if status == "high_confidence":
                high += 1
                action = "create_product"
            elif status == "low_confidence":
                low += 1
                action = "create_product"
            elif status == "bundle":
                low += 1
                action = "create_bundle"
            elif is_charge:
                unmatched += 1
                action = "create_custom"
            else:
                unmatched += 1
                action = "skip"

            import_item = PriceListImportItem(
                tenant_id=imp.tenant_id,
                import_id=imp.id,
                raw_text=item_data.get("raw_text", "")[:500],
                extracted_name=item_data.get("extracted_name", "Unknown"),
                extracted_price=(
                    Decimal(str(item_data["extracted_price"]))
                    if item_data.get("extracted_price")
                    else None
                ),
                extracted_sku=item_data.get("extracted_sku"),
                match_status=status,
                matched_template_id=match.get("template_id") if match else None,
                matched_template_name=(
                    # Use canonical name from DB if we have the template_id
                    template_map.get(match.get("template_id", ""), match.get("template_name"))
                    if match else None
                ),
                match_confidence=(
                    Decimal(str(match["confidence"]))
                    if match and match.get("confidence")
                    else None
                ),
                match_reasoning=_build_bundle_reasoning(match, status) if match else None,
                final_product_name=(
                    _resolve_final_name(
                        item_data.get("extracted_name", ""),
                        match.get("template_id"),
                        template_map,
                        match,
                    )
                ) if match else item_data.get("extracted_name", "Unknown"),
                final_price=(
                    Decimal(str(item_data["extracted_price"]))
                    if item_data.get("extracted_price")
                    else None
                ),
                final_sku=item_data.get("extracted_sku"),
                action=action,
                # Conditional pricing
                extracted_price_with_vault=(
                    Decimal(str(item_data["extracted_price_with_vault"]))
                    if item_data.get("extracted_price_with_vault")
                    else None
                ),
                extracted_price_standalone=(
                    Decimal(str(item_data["extracted_price_standalone"]))
                    if item_data.get("extracted_price_standalone")
                    else None
                ),
                has_conditional_pricing=bool(item_data.get("has_conditional_pricing", False)),
                is_bundle_price_variant=bool(item_data.get("is_bundle_price_variant", False)),
                price_variant_type=item_data.get("price_variant_type"),
                charge_category=item_data.get("charge_category"),
                charge_key_suggestion=item_data.get("charge_key_suggestion"),
            )
            db.add(import_item)

        imp.items_extracted = high + low + unmatched
        imp.items_matched_high_confidence = high
        imp.items_matched_low_confidence = low
        imp.items_unmatched = unmatched

        # Run charge matching for charge-type items
        from app.services.charge_matching_service import match_charges_for_import

        charge_items = (
            db.query(PriceListImportItem)
            .filter(
                PriceListImportItem.import_id == imp.id,
                PriceListImportItem.charge_category.isnot(None),
            )
            .all()
        )
        if charge_items:
            match_charges_for_import(db, imp.tenant_id, charge_items)

        imp.status = "review_ready"
        db.commit()

    except Exception as e:
        logger.exception("Price list analysis failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        imp.status = "failed"
        imp.error_message = str(e)[:500]
        db.commit()
