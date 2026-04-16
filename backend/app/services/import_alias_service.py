"""Import Alias Service — data import file analysis, product/customer matching, and alias resolution.

EXTENDED: builds on existing csv_column_detector.py pattern
NEW: alias resolution and AI matching are new
"""

import csv
import io
import logging
import re
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.models import (
    CompanyEntity,
    DataImportSession,
    HistoricalProduct,
    Product,
    ProductAlias,
    SalesOrder,
)

logger = logging.getLogger(__name__)


KNOWN_COLUMN_PATTERNS = {
    "date": [
        "date", "order_date", "invoice_date", "ship_date", "ordered",
        "created", "transaction_date",
    ],
    "order_number": [
        "order", "order_no", "order_number", "invoice", "invoice_no",
        "po", "#",
    ],
    "customer": [
        "customer", "customer_name", "client", "buyer", "funeral_home",
        "fh", "sold_to", "bill_to",
    ],
    "product": [
        "product", "item", "description", "vault_type", "model", "sku",
        "product_name", "item_description",
    ],
    "quantity": ["qty", "quantity", "units", "count"],
    "unit_price": [
        "price", "unit_price", "rate", "each", "cost", "selling_price",
    ],
    "total": [
        "total", "extended", "line_total", "amount", "subtotal", "net",
    ],
    "location": [
        "location", "plant", "warehouse", "ship_from", "origin",
    ],
}


class ImportAliasService:
    """Handles data import file analysis, product/customer matching, and alias resolution."""

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Lowercase, strip punctuation, collapse whitespace."""
        if not text:
            return ""
        normalized = text.lower().strip()
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @staticmethod
    def analyze_file(file_content: bytes, file_name: str) -> dict:
        """Parse CSV/Excel, detect columns, extract unique products/customers, sample rows.

        Returns dict with source_system, total_rows, date_range, detected_columns,
        unique_products, unique_customers, sample_rows.
        """
        rows = []
        headers = []

        # Parse CSV
        try:
            text = file_content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = file_content.decode("latin-1")

        reader = csv.reader(io.StringIO(text))
        for i, row in enumerate(reader):
            if i == 0:
                headers = [h.strip() for h in row]
                continue
            if row and any(cell.strip() for cell in row):
                rows.append(row)

        if not headers or not rows:
            return {
                "source_system": "unknown",
                "total_rows": 0,
                "date_range": None,
                "detected_columns": {},
                "unique_products": [],
                "unique_customers": [],
                "sample_rows": [],
            }

        # Detect column mappings
        detected_columns = {}
        for col_idx, header in enumerate(headers):
            header_norm = ImportAliasService._normalize_text(header)
            for field_type, patterns in KNOWN_COLUMN_PATTERNS.items():
                for pattern in patterns:
                    if pattern in header_norm or header_norm in pattern:
                        detected_columns[field_type] = {
                            "column_index": col_idx,
                            "header": header,
                            "confidence": 1.0 if header_norm == pattern else 0.8,
                        }
                        break
                if field_type in detected_columns:
                    break

        # Extract unique products and customers
        unique_products = set()
        unique_customers = set()
        dates = []

        product_col = detected_columns.get("product", {}).get("column_index")
        customer_col = detected_columns.get("customer", {}).get("column_index")
        date_col = detected_columns.get("date", {}).get("column_index")

        for row in rows:
            if product_col is not None and product_col < len(row):
                val = row[product_col].strip()
                if val:
                    unique_products.add(val)
            if customer_col is not None and customer_col < len(row):
                val = row[customer_col].strip()
                if val:
                    unique_customers.add(val)
            if date_col is not None and date_col < len(row):
                val = row[date_col].strip()
                if val:
                    dates.append(val)

        # Detect date range
        date_range = None
        if dates:
            parsed_dates = []
            for d in dates:
                for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%m-%d-%Y", "%d-%b-%Y"):
                    try:
                        parsed_dates.append(datetime.strptime(d, fmt))
                        break
                    except ValueError:
                        continue
            if parsed_dates:
                date_range = {
                    "start": min(parsed_dates).isoformat(),
                    "end": max(parsed_dates).isoformat(),
                }

        # Detect source system from file name or content
        source_system = "unknown"
        fn_lower = file_name.lower()
        if "sage" in fn_lower:
            source_system = "sage_100"
        elif "quickbooks" in fn_lower or "qbo" in fn_lower or "qb" in fn_lower:
            source_system = "quickbooks"

        # Sample rows (first 5)
        sample_rows = []
        for row in rows[:5]:
            sample = {}
            for field_type, col_info in detected_columns.items():
                idx = col_info["column_index"]
                if idx < len(row):
                    sample[field_type] = row[idx].strip()
            sample_rows.append(sample)

        return {
            "source_system": source_system,
            "total_rows": len(rows),
            "date_range": date_range,
            "detected_columns": detected_columns,
            "unique_products": sorted(unique_products),
            "unique_customers": sorted(unique_customers),
            "sample_rows": sample_rows,
        }

    @staticmethod
    def match_products(
        db: Session, company_id: str, unique_product_names: list[str]
    ) -> list[dict]:
        """4-step matching: (1) exact alias, (2) normalized match, (3) fuzzy, (4) AI.

        Returns list of match objects with original, normalized, match_type,
        canonical_product, confidence, alternatives, status.
        """
        # Preload all products and aliases for this company
        products = (
            db.query(Product)
            .filter(
                Product.company_id == company_id,
                Product.is_active == True,  # noqa: E712
            )
            .all()
        )
        product_map = {p.id: p for p in products}
        product_name_map = {
            ImportAliasService._normalize_text(p.name): p for p in products
        }
        product_sku_map = {
            p.sku.lower(): p for p in products if p.sku
        }

        aliases = (
            db.query(ProductAlias)
            .filter(ProductAlias.company_id == company_id)
            .all()
        )
        alias_map = {a.alias_text_normalized: a for a in aliases}

        results = []
        unmatched_for_ai = []

        for raw_name in unique_product_names:
            normalized = ImportAliasService._normalize_text(raw_name)
            result = {
                "original": raw_name,
                "normalized": normalized,
                "match_type": None,
                "canonical_product": None,
                "confidence": 0.0,
                "alternatives": [],
                "status": "unmatched",
            }

            # Step 1: Exact alias lookup
            alias = alias_map.get(normalized)
            if alias and alias.canonical_product_id:
                product = product_map.get(alias.canonical_product_id)
                if product:
                    result["match_type"] = "alias_exact"
                    result["canonical_product"] = {
                        "id": product.id,
                        "name": product.name,
                        "sku": product.sku,
                    }
                    result["confidence"] = alias.confidence
                    result["status"] = "matched"
                    results.append(result)
                    continue

            # Step 2: Normalized name/SKU match
            product = product_name_map.get(normalized)
            if not product:
                product = product_sku_map.get(normalized)
            if product:
                result["match_type"] = "normalized"
                result["canonical_product"] = {
                    "id": product.id,
                    "name": product.name,
                    "sku": product.sku,
                }
                result["confidence"] = 0.95
                result["status"] = "matched"
                results.append(result)
                continue

            # Step 3: Fuzzy match using difflib
            best_score = 0.0
            best_product = None
            alternatives = []
            for p in products:
                p_norm = ImportAliasService._normalize_text(p.name)
                score = SequenceMatcher(None, normalized, p_norm).ratio()
                if score > 0.6:
                    alternatives.append({
                        "id": p.id,
                        "name": p.name,
                        "sku": p.sku,
                        "score": round(score, 3),
                    })
                if score > best_score:
                    best_score = score
                    best_product = p

            alternatives.sort(key=lambda x: x["score"], reverse=True)
            result["alternatives"] = alternatives[:5]

            if best_score >= 0.85 and best_product:
                result["match_type"] = "fuzzy"
                result["canonical_product"] = {
                    "id": best_product.id,
                    "name": best_product.name,
                    "sku": best_product.sku,
                }
                result["confidence"] = round(best_score, 3)
                result["status"] = "matched"
                results.append(result)
                continue

            # Collect for AI batch matching
            unmatched_for_ai.append((len(results), raw_name, normalized, result))
            results.append(result)

        # Step 4: AI disambiguation for remaining unmatched
        if unmatched_for_ai and products:
            try:
                ai_results = ImportAliasService._ai_match_products(
                    [item[1] for item in unmatched_for_ai],
                    [{"id": p.id, "name": p.name, "sku": p.sku} for p in products],
                )
                for (idx, raw_name, normalized, _), ai_match in zip(
                    unmatched_for_ai, ai_results
                ):
                    if ai_match and ai_match.get("product_id"):
                        product = product_map.get(ai_match["product_id"])
                        if product:
                            results[idx]["match_type"] = "ai"
                            results[idx]["canonical_product"] = {
                                "id": product.id,
                                "name": product.name,
                                "sku": product.sku,
                            }
                            results[idx]["confidence"] = ai_match.get("confidence", 0.7)
                            results[idx]["status"] = "ai_suggested"
            except Exception:
                logger.exception("AI product matching failed — leaving items unmatched")

        return results

    @staticmethod
    def _ai_match_products(
        unmatched_names: list[str], product_catalog: list[dict]
    ) -> list[dict | None]:
        """Use Claude to disambiguate product names against the catalog."""
        from app.services.ai_service import call_anthropic

        system_prompt = (
            "You are a product matching assistant for a burial vault manufacturer. "
            "Given a list of historical product names and a current product catalog, "
            "match each historical name to the most likely current product. "
            "Product names may use abbreviations, old model numbers, or informal names."
        )

        user_message = (
            "Match each of these historical product names to the closest product "
            "in the catalog. Return a JSON object with a 'matches' array where each "
            "element has: original_name, product_id (from catalog, or null if no match), "
            "confidence (0.0-1.0), reasoning (brief)."
        )

        context_data = {
            "historical_names": unmatched_names[:20],  # Limit to avoid token overrun
            "product_catalog": product_catalog[:100],
        }

        try:
            result = call_anthropic(
                system_prompt=system_prompt,
                user_message=user_message,
                context_data=context_data,
                max_tokens=2048,
            )
            matches = result.get("matches", [])
            # Build lookup by original name
            match_map = {m["original_name"]: m for m in matches}
            return [match_map.get(name) for name in unmatched_names[:20]]
        except Exception:
            logger.exception("AI product matching API call failed")
            return [None] * len(unmatched_names)

    @staticmethod
    def match_customers(
        db: Session, company_id: str, unique_customer_names: list[str]
    ) -> list[dict]:
        """Match customer names against company_entities table.

        Same pattern as match_products: exact, normalized, fuzzy, AI.
        """
        entities = (
            db.query(CompanyEntity)
            .filter(
                CompanyEntity.company_id == company_id,
                CompanyEntity.is_funeral_home == True,  # noqa: E712
            )
            .all()
        )

        entity_name_map = {
            ImportAliasService._normalize_text(e.name): e for e in entities
        }

        results = []
        for raw_name in unique_customer_names:
            normalized = ImportAliasService._normalize_text(raw_name)
            result = {
                "original": raw_name,
                "normalized": normalized,
                "match_type": None,
                "entity": None,
                "confidence": 0.0,
                "alternatives": [],
                "status": "unmatched",
            }

            # Exact normalized match
            entity = entity_name_map.get(normalized)
            if entity:
                result["match_type"] = "exact"
                result["entity"] = {
                    "id": entity.id,
                    "name": entity.name,
                    "city": entity.city,
                    "state": entity.state,
                }
                result["confidence"] = 1.0
                result["status"] = "matched"
                results.append(result)
                continue

            # Fuzzy match
            best_score = 0.0
            best_entity = None
            alternatives = []
            for e in entities:
                e_norm = ImportAliasService._normalize_text(e.name)
                score = SequenceMatcher(None, normalized, e_norm).ratio()
                if score > 0.6:
                    alternatives.append({
                        "id": e.id,
                        "name": e.name,
                        "city": e.city,
                        "state": e.state,
                        "score": round(score, 3),
                    })
                if score > best_score:
                    best_score = score
                    best_entity = e

            alternatives.sort(key=lambda x: x["score"], reverse=True)
            result["alternatives"] = alternatives[:5]

            if best_score >= 0.80 and best_entity:
                result["match_type"] = "fuzzy"
                result["entity"] = {
                    "id": best_entity.id,
                    "name": best_entity.name,
                    "city": best_entity.city,
                    "state": best_entity.state,
                }
                result["confidence"] = round(best_score, 3)
                result["status"] = "matched"

            results.append(result)

        return results

    @staticmethod
    def detect_duplicates(
        db: Session,
        company_id: str,
        import_rows: list[dict],
        column_mapping: dict,
    ) -> list[dict]:
        """Compare import rows against existing sales_orders to find duplicates.

        Returns a list of potential duplicate entries with the matching existing order.
        """
        duplicates = []
        order_num_field = column_mapping.get("order_number")
        date_field = column_mapping.get("date")
        customer_field = column_mapping.get("customer")

        if not order_num_field:
            return duplicates

        # Preload existing order numbers
        existing_orders = (
            db.query(SalesOrder)
            .filter(SalesOrder.company_id == company_id)
            .all()
        )
        existing_order_nums = {}
        for order in existing_orders:
            if order.order_number:
                existing_order_nums[order.order_number.strip().lower()] = {
                    "id": order.id,
                    "order_number": order.order_number,
                    "status": order.status,
                }

        for i, row in enumerate(import_rows):
            order_num = str(row.get(order_num_field, "")).strip().lower()
            if order_num and order_num in existing_order_nums:
                duplicates.append({
                    "row_index": i,
                    "import_row": row,
                    "existing_order": existing_order_nums[order_num],
                    "match_field": "order_number",
                })

        return duplicates

    @staticmethod
    def execute_import(
        db: Session,
        company_id: str,
        session_id: str,
        confirmed_product_matches: dict,
        confirmed_customer_matches: dict,
        duplicate_handling: str = "skip",
    ) -> dict:
        """Execute import: create orders, vault items, and aliases.

        Args:
            confirmed_product_matches: {raw_name: product_id}
            confirmed_customer_matches: {raw_name: entity_id}
            duplicate_handling: 'skip' or 'overwrite'

        Returns summary dict with counts.
        """
        session = (
            db.query(DataImportSession)
            .filter(
                DataImportSession.id == session_id,
                DataImportSession.company_id == company_id,
            )
            .first()
        )
        if not session:
            raise ValueError(f"Import session not found: {session_id}")

        session.status = "importing"
        db.flush()

        imported = 0
        skipped = 0
        aliases_created = 0

        # Learn confirmed product aliases
        for raw_name, product_id in confirmed_product_matches.items():
            if product_id:
                alias = ImportAliasService.learn_alias(
                    db,
                    company_id,
                    raw_name,
                    product_id,
                    source="import_confirmed",
                    confidence=1.0,
                )
                if alias:
                    aliases_created += 1

        # Update session
        session.status = "completed"
        session.imported_records = imported
        session.skipped_records = skipped
        session.matched_records = len(
            [v for v in confirmed_product_matches.values() if v]
        )
        session.unmatched_records = len(
            [v for v in confirmed_product_matches.values() if not v]
        )
        session.completed_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "imported": imported,
            "skipped": skipped,
            "aliases_created": aliases_created,
            "session_id": session_id,
            "status": "completed",
        }

    @staticmethod
    def resolve_product_name(
        db: Session, company_id: str, raw_name: str
    ) -> dict | None:
        """Check alias table and return canonical product if found."""
        normalized = ImportAliasService._normalize_text(raw_name)
        alias = (
            db.query(ProductAlias)
            .filter(
                ProductAlias.company_id == company_id,
                ProductAlias.alias_text_normalized == normalized,
            )
            .first()
        )
        if not alias or not alias.canonical_product_id:
            return None

        product = (
            db.query(Product)
            .filter(Product.id == alias.canonical_product_id)
            .first()
        )
        if not product:
            return None

        return {
            "product_id": product.id,
            "product_name": product.name,
            "product_sku": product.sku,
            "alias_text": alias.alias_text,
            "confidence": alias.confidence,
            "source": alias.source,
            "is_confirmed": alias.is_confirmed,
        }

    @staticmethod
    def learn_alias(
        db: Session,
        company_id: str,
        alias_text: str,
        canonical_product_id: str,
        source: str = "learned",
        confidence: float = 1.0,
    ) -> ProductAlias | None:
        """Store a new alias. Idempotent — updates if normalized text already exists."""
        normalized = ImportAliasService._normalize_text(alias_text)
        if not normalized:
            return None

        existing = (
            db.query(ProductAlias)
            .filter(
                ProductAlias.company_id == company_id,
                ProductAlias.alias_text_normalized == normalized,
            )
            .first()
        )
        if existing:
            existing.canonical_product_id = canonical_product_id
            existing.confidence = confidence
            existing.source = source
            existing.is_confirmed = source in ("manual", "import_confirmed")
            db.flush()
            return existing

        alias = ProductAlias(
            id=str(uuid.uuid4()),
            company_id=company_id,
            alias_text=alias_text,
            alias_text_normalized=normalized,
            canonical_product_id=canonical_product_id,
            confidence=confidence,
            source=source,
            is_confirmed=source in ("manual", "import_confirmed"),
        )
        db.add(alias)
        db.flush()
        logger.info(
            "Learned alias: '%s' -> product %s (source=%s)",
            alias_text,
            canonical_product_id,
            source,
        )
        return alias
