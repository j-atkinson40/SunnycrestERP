"""Wilbert Ingestion Service — orchestrates PDF parsing + image extraction + web enrichment.

Pipeline:
1. Parse uploaded Wilbert PDF catalog → extract SKUs with dimensions
2. Extract embedded product images from PDF pages
3. Upload images to R2 and set r2_image_key on products
4. Upsert into urn_products table (match by SKU)
5. Optionally enrich from wilbert.com (descriptions, additional images)
6. Log results to urn_catalog_sync_logs
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.urn_catalog_sync_log import UrnCatalogSyncLog
from app.models.urn_product import UrnProduct
from app.services.wilbert_pdf_parser import extract_product_images, parse_pdf_to_dicts

logger = logging.getLogger(__name__)


class WilbertIngestionService:

    @staticmethod
    def ingest_from_pdf(
        db: Session,
        tenant_id: str,
        pdf_path: str | Path,
        enrich_from_website: bool = False,
    ) -> UrnCatalogSyncLog:
        """Full ingestion pipeline: PDF parse → upsert → optional web enrichment.

        Args:
            db: Database session.
            tenant_id: Tenant company ID.
            pdf_path: Path to the Wilbert catalog PDF.
            enrich_from_website: If True, also scrape wilbert.com for descriptions/images.

        Returns:
            UrnCatalogSyncLog with results.
        """
        log = UrnCatalogSyncLog(
            tenant_id=tenant_id,
            status="running",
            sync_type="full_pipeline" if enrich_from_website else "pdf",
            pdf_filename=Path(pdf_path).name,
        )
        db.add(log)
        db.commit()

        try:
            # Step 1: Parse PDF
            logger.info("Parsing PDF: %s", pdf_path)
            products_data = parse_pdf_to_dicts(pdf_path)
            logger.info("PDF yielded %d products", len(products_data))

            if not products_data:
                log.status = "completed"
                log.completed_at = datetime.now(timezone.utc)
                log.error_message = "PDF parsing returned 0 products"
                db.commit()
                return log

            # Step 2: Upsert into urn_products
            added, updated, skipped = WilbertIngestionService._upsert_products(
                db, tenant_id, products_data
            )
            db.flush()

            log.products_added = added
            log.products_updated = updated
            log.products_skipped = skipped

            # Step 3: Extract and upload product images from PDF
            images_uploaded = WilbertIngestionService._extract_and_upload_images(
                db, tenant_id, pdf_path, products_data
            )
            if images_uploaded > 0:
                logger.info("Uploaded %d product images from PDF to R2", images_uploaded)

            # Step 4: Optional web enrichment
            if enrich_from_website:
                try:
                    logger.info("Enriching from wilbert.com...")
                    from app.services.urn_catalog_scraper import UrnCatalogScraper

                    # Get all drop_ship products for this tenant
                    products = (
                        db.query(UrnProduct)
                        .filter(
                            UrnProduct.tenant_id == tenant_id,
                            UrnProduct.source_type == "drop_ship",
                            UrnProduct.is_active == True,
                        )
                        .all()
                    )

                    enriched, not_found = UrnCatalogScraper.enrich_products_from_web(
                        db, tenant_id, products
                    )
                    logger.info(
                        "Web enrichment: %d enriched, %d not found",
                        enriched, not_found,
                    )
                except Exception as e:
                    logger.warning("Web enrichment failed (non-fatal): %s", e)
                    log.error_message = f"Web enrichment failed: {e}"

            # Store images_uploaded as a non-persisted attribute for API response
            log._images_uploaded = images_uploaded

            log.status = "completed"
            log.completed_at = datetime.now(timezone.utc)
            db.commit()

        except Exception as e:
            logger.error("Ingestion failed: %s", e)
            db.rollback()
            log = db.query(UrnCatalogSyncLog).filter(
                UrnCatalogSyncLog.id == log.id
            ).first()
            if log:
                log.status = "failed"
                log.error_message = str(e)[:2000]
                log.completed_at = datetime.now(timezone.utc)
                db.commit()

        return log

    @staticmethod
    def _upsert_products(
        db: Session,
        tenant_id: str,
        products_data: list[dict],
    ) -> tuple[int, int, int]:
        """Upsert parsed product data into urn_products.

        Match by SKU within the tenant. New products default to drop_ship.

        Returns: (added, updated, skipped)
        """
        added = 0
        updated = 0
        skipped = 0

        for pdata in products_data:
            sku = pdata.get("sku")
            if not sku:
                skipped += 1
                continue

            existing = (
                db.query(UrnProduct)
                .filter(
                    UrnProduct.tenant_id == tenant_id,
                    UrnProduct.sku == sku,
                )
                .first()
            )

            if existing:
                changed = False
                # Update fields from PDF — but don't overwrite user-entered data
                update_fields = {
                    "product_type": pdata.get("product_type"),
                    "height": pdata.get("height"),
                    "width_or_diameter": pdata.get("width_or_diameter"),
                    "depth": pdata.get("depth"),
                    "cubic_inches": pdata.get("cubic_inches"),
                    "companion_of_sku": pdata.get("companion_of_sku"),
                    "catalog_page": pdata.get("catalog_page"),
                }
                # Only update description if not already set
                if pdata.get("wilbert_description") and not existing.wilbert_description:
                    update_fields["wilbert_description"] = pdata["wilbert_description"]

                # Only update engravable if PDF says yes (never downgrade)
                if pdata.get("engravable") and not existing.engravable:
                    update_fields["engravable"] = True

                # Update material if not set
                if pdata.get("material") and not existing.material:
                    update_fields["material"] = pdata["material"]

                for field, value in update_fields.items():
                    if value is not None and getattr(existing, field) != value:
                        setattr(existing, field, value)
                        changed = True

                # Re-activate if it was discontinued
                if existing.discontinued:
                    existing.discontinued = False
                    changed = True

                if changed:
                    updated += 1
            else:
                # Determine product type-based naming
                product_type = pdata.get("product_type", "Urn")
                name = pdata.get("name", f"Unknown {sku}")

                product = UrnProduct(
                    tenant_id=tenant_id,
                    name=name,
                    sku=sku,
                    source_type="drop_ship",
                    material=pdata.get("material"),
                    product_type=product_type,
                    height=pdata.get("height"),
                    width_or_diameter=pdata.get("width_or_diameter"),
                    depth=pdata.get("depth"),
                    cubic_inches=pdata.get("cubic_inches"),
                    engravable=pdata.get("engravable", False),
                    companion_of_sku=pdata.get("companion_of_sku"),
                    wilbert_description=pdata.get("wilbert_description"),
                    catalog_page=pdata.get("catalog_page"),
                    is_keepsake_set=product_type in ("Memento", "Heart"),
                )
                db.add(product)
                added += 1

        return added, updated, skipped

    @staticmethod
    def _extract_and_upload_images(
        db: Session,
        tenant_id: str,
        pdf_path: str | Path,
        products_data: list[dict],
    ) -> int:
        """Extract embedded images from the PDF and upload to R2.

        Associates each image with its product via r2_image_key.
        Skips products that already have an r2_image_key (preserves manual uploads).

        Returns the number of images uploaded.
        """
        # Build SKU → catalog_page mapping from parsed data
        product_pages: dict[str, int] = {}
        for pdata in products_data:
            sku = pdata.get("sku")
            page = pdata.get("catalog_page")
            if sku and page:
                product_pages[sku] = page

        if not product_pages:
            logger.info("No product pages to extract images from")
            return 0

        # Extract images from PDF
        try:
            sku_images = extract_product_images(pdf_path, product_pages)
        except Exception as e:
            logger.warning("PDF image extraction failed (non-fatal): %s", e)
            return 0

        if not sku_images:
            logger.info("No images extracted from PDF")
            return 0

        logger.info("Extracted %d images from PDF, uploading to R2...", len(sku_images))

        uploaded = 0
        for sku, jpeg_bytes in sku_images.items():
            # Skip non-SKU keys (page_N fallback keys)
            if sku.startswith("page_"):
                continue

            # Find the product in the database
            product = (
                db.query(UrnProduct)
                .filter(
                    UrnProduct.tenant_id == tenant_id,
                    UrnProduct.sku == sku,
                )
                .first()
            )

            if not product:
                continue

            # Don't overwrite existing R2 images (preserves manual uploads)
            if product.r2_image_key:
                continue

            # Upload to R2
            r2_key = f"tenants/{tenant_id}/urn_catalog/images/{sku.lower()}.jpg"
            try:
                from app.services.legacy_r2_client import upload_bytes

                upload_bytes(jpeg_bytes, r2_key, content_type="image/jpeg")
                product.r2_image_key = r2_key
                uploaded += 1
            except Exception as e:
                logger.warning("Failed to upload image for %s: %s", sku, e)
                continue

        if uploaded > 0:
            db.flush()

        return uploaded

    @staticmethod
    def import_products_from_csv(
        db: Session,
        tenant_id: str,
        rows: list[dict],
    ) -> dict:
        """Import full product data from CSV rows.

        Each row can contain: name, sku, source_type, material, product_type,
        height, width_or_diameter, depth, cubic_inches, engravable,
        base_cost, retail_price, style, color_name, wilbert_description, etc.

        Upserts by SKU (if provided), otherwise creates new.

        Returns: {products_created, products_updated, rows_skipped, errors}
        """
        from decimal import Decimal, InvalidOperation

        created = 0
        updated = 0
        skipped = 0
        errors = []

        # Normalize column names — accept common variations
        COLUMN_MAP = {
            "name": "name",
            "product_name": "name",
            "product name": "name",
            "sku": "sku",
            "item_number": "sku",
            "item number": "sku",
            "item_no": "sku",
            "source_type": "source_type",
            "source type": "source_type",
            "source": "source_type",
            "material": "material",
            "material_category": "material",
            "material category": "material",
            "product_type": "product_type",
            "product type": "product_type",
            "type": "product_type",
            "height": "height",
            "width": "width_or_diameter",
            "width_or_diameter": "width_or_diameter",
            "diameter": "width_or_diameter",
            "depth": "depth",
            "cubic_inches": "cubic_inches",
            "cubic inches": "cubic_inches",
            "capacity": "cubic_inches",
            "engravable": "engravable",
            "base_cost": "base_cost",
            "cost": "base_cost",
            "wholesale_cost": "base_cost",
            "wholesale": "base_cost",
            "retail_price": "retail_price",
            "price": "retail_price",
            "retail": "retail_price",
            "selling_price": "retail_price",
            "style": "style",
            "color": "color_name",
            "color_name": "color_name",
            "description": "wilbert_description",
            "wilbert_description": "wilbert_description",
            "companion_of_sku": "companion_of_sku",
            "companion_of": "companion_of_sku",
            "catalog_page": "catalog_page",
            "page": "catalog_page",
        }

        BOOL_TRUE = {"true", "yes", "1", "y", "x"}
        BOOL_FALSE = {"false", "no", "0", "n", ""}

        def _normalize_row(raw: dict) -> dict:
            """Map raw CSV column names to canonical field names."""
            result = {}
            for key, val in raw.items():
                canonical = COLUMN_MAP.get(key.strip().lower())
                if canonical and val is not None:
                    v = str(val).strip() if val is not None else ""
                    if v:
                        result[canonical] = v
            return result

        def _parse_bool(val: str) -> bool | None:
            v = val.strip().lower()
            if v in BOOL_TRUE:
                return True
            if v in BOOL_FALSE:
                return False
            return None

        def _parse_decimal(val: str) -> Decimal | None:
            try:
                cleaned = val.replace("$", "").replace(",", "").strip()
                if not cleaned:
                    return None
                return Decimal(cleaned)
            except (InvalidOperation, ValueError):
                return None

        def _parse_int(val: str) -> int | None:
            try:
                cleaned = val.replace(",", "").strip()
                if not cleaned:
                    return None
                return int(float(cleaned))
            except (ValueError, TypeError):
                return None

        for i, raw_row in enumerate(rows, start=1):
            try:
                row = _normalize_row(raw_row)
                name = row.get("name", "").strip()
                sku = row.get("sku", "").strip()

                if not name and not sku:
                    skipped += 1
                    continue

                # Try to find existing by SKU
                existing = None
                if sku:
                    existing = (
                        db.query(UrnProduct)
                        .filter(
                            UrnProduct.tenant_id == tenant_id,
                            UrnProduct.sku == sku,
                        )
                        .first()
                    )

                # Parse fields
                base_cost = _parse_decimal(row.get("base_cost", ""))
                retail_price = _parse_decimal(row.get("retail_price", ""))
                cubic_inches = _parse_int(row.get("cubic_inches", ""))
                catalog_page = _parse_int(row.get("catalog_page", ""))
                engravable_val = _parse_bool(row.get("engravable", ""))

                # Normalize source_type
                source_type = row.get("source_type", "").lower().strip()
                if source_type not in ("stocked", "drop_ship"):
                    source_type = "drop_ship"

                if existing:
                    # Update existing product
                    changed = False
                    if name and name != existing.name:
                        existing.name = name
                        changed = True
                    if row.get("material") and row["material"] != existing.material:
                        existing.material = row["material"]
                        changed = True
                    if row.get("product_type") and row["product_type"] != existing.product_type:
                        existing.product_type = row["product_type"]
                        changed = True
                    if row.get("height") and row["height"] != existing.height:
                        existing.height = row["height"]
                        changed = True
                    if row.get("width_or_diameter") and row["width_or_diameter"] != existing.width_or_diameter:
                        existing.width_or_diameter = row["width_or_diameter"]
                        changed = True
                    if row.get("depth") and row["depth"] != existing.depth:
                        existing.depth = row["depth"]
                        changed = True
                    if cubic_inches is not None and cubic_inches != existing.cubic_inches:
                        existing.cubic_inches = cubic_inches
                        changed = True
                    if engravable_val is not None and engravable_val != existing.engravable:
                        existing.engravable = engravable_val
                        changed = True
                    if base_cost is not None:
                        existing.base_cost = base_cost
                        changed = True
                    if retail_price is not None:
                        existing.retail_price = retail_price
                        changed = True
                    if row.get("style") and row["style"] != existing.style:
                        existing.style = row["style"]
                        changed = True
                    if row.get("color_name") and row["color_name"] != existing.color_name:
                        existing.color_name = row["color_name"]
                        changed = True
                    if row.get("wilbert_description") and row["wilbert_description"] != existing.wilbert_description:
                        existing.wilbert_description = row["wilbert_description"]
                        changed = True
                    if row.get("companion_of_sku") and row["companion_of_sku"] != existing.companion_of_sku:
                        existing.companion_of_sku = row["companion_of_sku"]
                        changed = True
                    if catalog_page is not None and catalog_page != existing.catalog_page:
                        existing.catalog_page = catalog_page
                        changed = True
                    if row.get("source_type") and source_type != existing.source_type:
                        existing.source_type = source_type
                        changed = True

                    # Re-activate if discontinued
                    if existing.discontinued:
                        existing.discontinued = False
                        changed = True
                    if not existing.is_active:
                        existing.is_active = True
                        changed = True

                    if changed:
                        updated += 1
                else:
                    # Create new product
                    if not name:
                        name = sku or f"Product Row {i}"

                    product = UrnProduct(
                        tenant_id=tenant_id,
                        name=name,
                        sku=sku or None,
                        source_type=source_type,
                        material=row.get("material"),
                        product_type=row.get("product_type"),
                        height=row.get("height"),
                        width_or_diameter=row.get("width_or_diameter"),
                        depth=row.get("depth"),
                        cubic_inches=cubic_inches,
                        engravable=engravable_val if engravable_val is not None else True,
                        base_cost=base_cost,
                        retail_price=retail_price,
                        style=row.get("style"),
                        color_name=row.get("color_name"),
                        wilbert_description=row.get("wilbert_description"),
                        companion_of_sku=row.get("companion_of_sku"),
                        catalog_page=catalog_page,
                        is_keepsake_set=row.get("product_type", "") in ("Memento", "Heart"),
                    )
                    db.add(product)
                    created += 1

            except Exception as e:
                errors.append(f"Row {i}: {str(e)[:200]}")
                skipped += 1

        if created > 0 or updated > 0:
            db.flush()

        return {
            "products_created": created,
            "products_updated": updated,
            "rows_skipped": skipped,
            "errors": errors[:20],  # cap at 20 error messages
        }

    @staticmethod
    def apply_bulk_markup(
        db: Session,
        tenant_id: str,
        markup_percent: float,
        rounding: str = "1.00",
        material: str | None = None,
        product_type: str | None = None,
        only_unpriced: bool = False,
    ) -> tuple[int, int]:
        """Apply markup percentage to products' base_cost → retail_price.

        Args:
            markup_percent: e.g., 40.0 for 40% markup
            rounding: Round to nearest "0.01", "0.50", "1.00", or "5.00"
            material: Filter by material category
            product_type: Filter by product type
            only_unpriced: Only apply to products without retail_price

        Returns: (updated_count, skipped_count)
        """
        q = db.query(UrnProduct).filter(
            UrnProduct.tenant_id == tenant_id,
            UrnProduct.is_active == True,
            UrnProduct.base_cost.isnot(None),
        )

        if material:
            q = q.filter(UrnProduct.material == material)
        if product_type:
            q = q.filter(UrnProduct.product_type == product_type)
        if only_unpriced:
            q = q.filter(UrnProduct.retail_price.is_(None))

        products = q.all()
        updated = 0
        skipped = 0

        for p in products:
            if p.base_cost is None or float(p.base_cost) <= 0:
                skipped += 1
                continue

            raw = float(p.base_cost) * (1 + markup_percent / 100)
            r = float(rounding)
            if r >= 1:
                new_price = round(raw / r) * r
            else:
                new_price = round(raw, 2)

            from decimal import Decimal
            p.retail_price = Decimal(str(round(new_price, 2)))
            updated += 1

        if updated > 0:
            db.flush()

        return updated, skipped

    @staticmethod
    def import_prices_from_csv(
        db: Session,
        tenant_id: str,
        rows: list[dict],
    ) -> dict:
        """Import prices from CSV data (list of {sku, base_cost, retail_price}).

        Returns: {matched, updated, not_found: [skus]}
        """
        matched = 0
        updated = 0
        not_found = []

        for row in rows:
            sku = row.get("sku", "").strip()
            if not sku:
                continue

            product = (
                db.query(UrnProduct)
                .filter(
                    UrnProduct.tenant_id == tenant_id,
                    UrnProduct.sku == sku,
                )
                .first()
            )

            if not product:
                not_found.append(sku)
                continue

            matched += 1
            changed = False

            if row.get("base_cost") is not None:
                from decimal import Decimal
                product.base_cost = Decimal(str(row["base_cost"]))
                changed = True
            if row.get("retail_price") is not None:
                from decimal import Decimal
                product.retail_price = Decimal(str(row["retail_price"]))
                changed = True

            if changed:
                updated += 1

        if updated > 0:
            db.flush()

        return {
            "matched": matched,
            "updated": updated,
            "not_found": not_found,
        }
