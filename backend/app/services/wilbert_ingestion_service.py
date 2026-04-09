"""Wilbert Ingestion Service — orchestrates PDF parsing + web enrichment.

Pipeline:
1. Parse uploaded Wilbert PDF catalog → extract 270 SKUs with dimensions
2. Upsert into urn_products table (match by SKU)
3. Optionally enrich from wilbert.com (descriptions, images)
4. Log results to urn_catalog_sync_logs
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.urn_catalog_sync_log import UrnCatalogSyncLog
from app.models.urn_product import UrnProduct
from app.services.wilbert_pdf_parser import parse_pdf_to_dicts

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

            # Step 3: Optional web enrichment
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
