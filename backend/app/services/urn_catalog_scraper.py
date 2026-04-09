"""UrnCatalogScraper — crawls Wilbert's public catalog for urn products."""

import logging
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.urn_catalog_sync_log import UrnCatalogSyncLog
from app.models.urn_product import UrnProduct
from app.services.wilbert_scraper_config import (
    CATALOG_BASE_URL,
    DETAIL_SELECTORS,
    FIELD_MAPPING,
    MAX_PRODUCTS_PER_RUN,
    PRODUCT_SELECTORS,
    SCRAPE_DELAY_MS,
    USER_AGENT,
)

logger = logging.getLogger(__name__)


class UrnCatalogScraper:

    @staticmethod
    def run_full_scrape(db: Session, tenant_id: str) -> UrnCatalogSyncLog:
        """Crawl Wilbert's public catalog and populate UrnProduct table.

        Seeds new products; updates existing ones by SKU match.
        Logs results to UrnCatalogSyncLog.
        """
        log = UrnCatalogSyncLog(
            tenant_id=tenant_id,
            status="running",
        )
        db.add(log)
        db.commit()

        try:
            products_data = UrnCatalogScraper._fetch_catalog(CATALOG_BASE_URL)

            added = 0
            updated = 0
            for pdata in products_data[:MAX_PRODUCTS_PER_RUN]:
                sku = pdata.get("sku")
                if not sku:
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
                    for catalog_field, model_field in FIELD_MAPPING.items():
                        new_val = pdata.get(catalog_field)
                        if new_val is not None and getattr(existing, model_field, None) != new_val:
                            setattr(existing, model_field, new_val)
                            changed = True
                    if changed:
                        existing.discontinued = False
                        updated += 1
                else:
                    product = UrnProduct(
                        tenant_id=tenant_id,
                        source_type="drop_ship",
                        engravable=True,
                    )
                    for catalog_field, model_field in FIELD_MAPPING.items():
                        val = pdata.get(catalog_field)
                        if val is not None:
                            setattr(product, model_field, val)
                    db.add(product)
                    added += 1

            db.flush()

            log.products_added = added
            log.products_updated = updated
            log.status = "completed"
            log.completed_at = datetime.now(timezone.utc)
            db.commit()

        except Exception as e:
            logger.error("Catalog scrape failed: %s", e)
            db.rollback()
            log = db.query(UrnCatalogSyncLog).filter(UrnCatalogSyncLog.id == log.id).first()
            if log:
                log.status = "failed"
                log.error_message = str(e)[:2000]
                log.completed_at = datetime.now(timezone.utc)
                db.commit()

        return log

    @staticmethod
    def run_delta_sync(db: Session, tenant_id: str) -> UrnCatalogSyncLog:
        """Re-crawl known catalog URLs, diff against existing records.

        Soft-discontinues removed products.
        """
        log = UrnCatalogSyncLog(
            tenant_id=tenant_id,
            status="running",
        )
        db.add(log)
        db.commit()

        try:
            existing_products = (
                db.query(UrnProduct)
                .filter(
                    UrnProduct.tenant_id == tenant_id,
                    UrnProduct.source_type == "drop_ship",
                    UrnProduct.wilbert_catalog_url.isnot(None),
                    UrnProduct.discontinued == False,
                )
                .all()
            )

            updated = 0
            discontinued = 0
            seen_skus = set()

            for product in existing_products:
                try:
                    page_data = UrnCatalogScraper._fetch_product_page(
                        product.wilbert_catalog_url
                    )
                    if page_data:
                        changed = False
                        for catalog_field, model_field in FIELD_MAPPING.items():
                            new_val = page_data.get(catalog_field)
                            if new_val is not None and getattr(product, model_field, None) != new_val:
                                setattr(product, model_field, new_val)
                                changed = True
                        if changed:
                            updated += 1
                        if product.sku:
                            seen_skus.add(product.sku)
                    else:
                        # Page gone — soft discontinue
                        product.discontinued = True
                        discontinued += 1

                    time.sleep(SCRAPE_DELAY_MS / 1000)

                except Exception as e:
                    logger.warning(
                        "Failed to sync product %s: %s", product.id, e
                    )

            log.products_updated = updated
            log.products_discontinued = discontinued
            log.status = "completed"
            log.completed_at = datetime.now(timezone.utc)
            db.commit()

        except Exception as e:
            logger.error("Delta sync failed: %s", e)
            db.rollback()
            log = db.query(UrnCatalogSyncLog).filter(UrnCatalogSyncLog.id == log.id).first()
            if log:
                log.status = "failed"
                log.error_message = str(e)[:2000]
                log.completed_at = datetime.now(timezone.utc)
                db.commit()

        return log

    @staticmethod
    def _fetch_catalog(base_url: str) -> list[dict]:
        """Fetch and parse the Wilbert catalog listing page.

        Returns list of product data dicts extracted using PRODUCT_SELECTORS.
        """
        try:
            import httpx
            resp = httpx.get(
                base_url,
                headers={"User-Agent": USER_AGENT},
                timeout=30,
                follow_redirects=True,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error("Failed to fetch catalog at %s: %s", base_url, e)
            return []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
        except ImportError:
            logger.error("beautifulsoup4 not installed — cannot parse catalog")
            return []

        products = []
        cards = soup.select(PRODUCT_SELECTORS["product_card"])
        for card in cards:
            pdata = {}
            for field, selector in PRODUCT_SELECTORS.items():
                if field == "product_card":
                    continue
                el = card.select_one(selector)
                if el:
                    if field == "image":
                        pdata["image_url"] = el.get("src", "")
                    elif field == "colors":
                        pdata["colors"] = [
                            e.get("title", e.text.strip())
                            for e in card.select(selector)
                        ]
                    elif field == "fonts":
                        pdata["fonts"] = [
                            e.text.strip() for e in card.select(selector)
                        ]
                    elif field == "detail_link":
                        href = el.get("href", "")
                        if href and not href.startswith("http"):
                            href = base_url.rstrip("/") + "/" + href.lstrip("/")
                        pdata["catalog_url"] = href
                    elif field == "photo_etch_badge":
                        pdata["photo_etch"] = True
                    elif field == "keepsake_badge":
                        pdata["is_keepsake"] = True
                    else:
                        pdata[field] = el.text.strip()

            if pdata.get("name") or pdata.get("sku"):
                products.append(pdata)

            time.sleep(SCRAPE_DELAY_MS / 1000)

        return products

    @staticmethod
    def _fetch_product_page(url: str) -> dict | None:
        """Fetch and parse a single product detail page.

        Returns product data dict or None if page not found.
        """
        try:
            import httpx
            resp = httpx.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=30,
                follow_redirects=True,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
        except Exception as e:
            logger.warning("Failed to fetch product page %s: %s", url, e)
            return None

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
        except ImportError:
            return None

        pdata = {}
        for field, selector in {**PRODUCT_SELECTORS, **DETAIL_SELECTORS}.items():
            if field in ("product_card", "detail_link"):
                continue
            el = soup.select_one(selector)
            if el:
                if field == "image":
                    pdata["image_url"] = el.get("src", "")
                elif field in ("colors", "color_gallery"):
                    pdata["colors"] = [
                        e.get("title", e.get("alt", ""))
                        for e in soup.select(selector)
                    ]
                elif field in ("fonts", "font_samples"):
                    pdata["fonts"] = [e.text.strip() for e in soup.select(selector)]
                else:
                    pdata[field] = el.text.strip()

        return pdata if pdata else None
