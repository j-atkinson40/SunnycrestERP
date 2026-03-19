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
      "match_status": "high_confidence|low_confidence|unmatched"
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
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        response_text = message.content[0].text
        # Strip code fences if present
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", response_text.strip())
        cleaned = re.sub(r"\n?\s*```$", "", cleaned)

        parsed = json.loads(cleaned)

        # Store analysis
        imp.claude_analysis = json.dumps(parsed)
        imp.extraction_token_usage = json.dumps(
            {
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            }
        )

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
                matched_template_name=match.get("template_name") if match else None,
                match_confidence=(
                    Decimal(str(match["confidence"]))
                    if match and match.get("confidence")
                    else None
                ),
                match_reasoning=match.get("reasoning") if match else None,
                final_product_name=(
                    match.get("template_name")
                    or item_data.get("extracted_name", "Unknown")
                ),
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
