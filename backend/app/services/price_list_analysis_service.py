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
- "Tribute" without a color specification (White or Gray) should be matched to BOTH "White Tribute" and "Gray Tribute" as two separate high_confidence items with the same price. Create TWO items in your output — one matched to White Tribute and one to Gray Tribute.
- Similarly, "Venetian" without a color should match to BOTH "White Venetian" and "Gold Venetian" as two items.
- Products labeled as urn vaults should be matched to the Urn Vault category templates, NOT the Burial Vault templates. Use the exact urn vault template name (e.g. "Monticello Urn Vault" not "Monticello (Urn)").
- If a price list item says just "Veteran" in an urn vault section, match it to "Veteran Urn Vault".

OVERSIZE VAULT HANDLING:
- Oversize vaults come in different dimensions (e.g. 31", 33", 34", 36"). Each size is a separate product.
- When you find an oversize vault with a specific dimension, create it as a SEPARATE item with match_status "custom" (not unmatched).
- Set the extracted_name to include the vault line name plus the size, like: "Continental 34\"", "Monticello 31\"", "Venetian 36\"".
- Do NOT group multiple oversize sizes together. Each size+vault combination is its own product.
- Match oversize vaults to the base vault line template (e.g. Continental Burial Vault) but set match_status to "low_confidence" with reasoning explaining it's an oversize variant, so the manufacturer can confirm.
- If an oversize vault has no specific dimension (just "OS" or "Oversize"), name it with "Oversize" like "Continental Oversize".

EQUIPMENT BUNDLE DETECTION (CRITICAL — do NOT mark these as unmatched):
- Items like "Full Equipment", "Equipment Package", "Equipment w/o Chairs", "Setup Package", "Tent Only", "Equipment Only", "Full Setup" are equipment BUNDLES — flat-rate packages.
- ALWAYS set match_status to "bundle" for these items. NEVER set them to "unmatched".
- Set template_id to null, template_name to the bundle name, confidence to 0.90.
- Do NOT assume bundle contents based on bundle name. Different manufacturers define bundles differently.
- Only suggest bundle components if you find evidence in the price list itself. Evidence means: individual equipment line items whose prices sum to approximately the bundle price (within 20%).
- If you find evidence, include it in the match object:
  "match": {
    "template_id": null,
    "template_name": "Full Equipment",
    "confidence": 0.90,
    "reasoning": "Equipment bundle detected",
    "bundle_components_suggested": [
      {"component": "Lowering Device", "evidence": "Found 'Lowering Device — $65' as individual item"},
      {"component": "Tent", "evidence": "Found 'Tent — $40' as individual item"}
    ]
  }
- If NO individual equipment items are found on the price list, set bundle_components_suggested to an empty array [].
- NEVER suggest components based on bundle name alone.
"""


def analyze_price_list(db: Session, import_id: str) -> None:
    """Run Claude analysis on an extracted price list."""
    imp = db.query(PriceListImport).filter(PriceListImport.id == import_id).first()
    if not imp or not imp.raw_extracted_text:
        return

    imp.status = "matching"
    db.flush()

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
- unmatched (< 0.60): no confident match"""

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

        # Store analysis
        imp.claude_analysis = json.dumps(parsed)
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

            if status == "high_confidence":
                high += 1
                action = "create_product"
            elif status == "low_confidence":
                low += 1
                action = "create_product"
            elif status == "bundle":
                low += 1
                action = "create_bundle"
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
                match_reasoning=match.get("reasoning") if match else None,
                final_product_name=(
                    # Always prefer the canonical DB name over Claude's interpretation
                    template_map.get(match.get("template_id", ""))
                    or match.get("template_name")
                    or item_data.get("extracted_name", "Unknown")
                ) if match else item_data.get("extracted_name", "Unknown"),
                final_price=(
                    Decimal(str(item_data["extracted_price"]))
                    if item_data.get("extracted_price")
                    else None
                ),
                final_sku=item_data.get("extracted_sku"),
                action=action,
            )
            db.add(import_item)

        imp.items_extracted = high + low + unmatched
        imp.items_matched_high_confidence = high
        imp.items_matched_low_confidence = low
        imp.items_unmatched = unmatched
        imp.status = "review_ready"
        db.commit()

    except Exception as e:
        logger.exception("Price list analysis failed: %s", e)
        imp.status = "failed"
        imp.error_message = str(e)[:500]
        db.commit()
