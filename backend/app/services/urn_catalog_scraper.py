"""UrnCatalogScraper — crawls Wilbert's public catalog for urn product data.

Scrapes wilbert.com category listing pages and individual product detail pages
to extract descriptions, images, and related product links. Uses real CSS
selectors discovered during site research (April 2026).

Website is server-rendered ASP.NET WebForms — no JS/headless browser needed.

Also supports automatic PDF catalog fetching via fetch_catalog_pdf() — downloads
the Cremation Choices catalog PDF from Wilbert's public URL, detects changes via
MD5 hash comparison, and triggers re-parsing when a new version is found.
"""

import hashlib
import logging
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.urn_catalog_sync_log import UrnCatalogSyncLog
from app.models.urn_product import UrnProduct
from app.services.wilbert_scraper_config import (
    CATALOG_PDF_PAGE_URL,
    CATALOG_PDF_URL,
    CATEGORY_URLS,
    DETAIL_SELECTORS,
    LISTING_SELECTORS,
    MAX_PRODUCTS_PER_RUN,
    SCRAPE_DELAY_S,
    SITE_ORIGIN,
    USER_AGENT,
)

logger = logging.getLogger(__name__)


def _get_http_client():
    """Lazy import httpx to avoid import errors when not installed."""
    import httpx
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=30,
        follow_redirects=True,
    )


def _get_soup(html: str):
    """Lazy import BeautifulSoup."""
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "html.parser")


class UrnCatalogScraper:

    @staticmethod
    def scrape_all_categories() -> list[dict]:
        """Scrape all category listing pages and detail pages.

        Returns list of product dicts with keys:
            name, sku (inferred), image_url, catalog_url,
            short_description, long_description, material,
            related_items (list of {name, item_number})
        """
        client = _get_http_client()
        all_products = []

        for category_name, category_path in CATEGORY_URLS.items():
            url = SITE_ORIGIN + category_path
            logger.info("Scraping category: %s (%s)", category_name, url)

            try:
                resp = client.get(url)
                resp.raise_for_status()
            except Exception as e:
                logger.error("Failed to fetch category %s: %s", category_name, e)
                continue

            soup = _get_soup(resp.text)
            product_links = soup.select(LISTING_SELECTORS["product_link"])

            seen_urls = set()
            for link_el in product_links:
                href = link_el.get("href", "")
                if not href or href in seen_urls:
                    continue
                seen_urls.add(href)

                # Extract name from image alt text
                img = link_el.select_one("img")
                listing_name = img.get("alt", "").strip() if img else ""
                listing_image = ""
                if img:
                    src = img.get("src", "")
                    if src and not src.startswith("http"):
                        src = SITE_ORIGIN + src
                    listing_image = src

                # Build full detail URL
                detail_url = href
                if not detail_url.startswith("http"):
                    detail_url = SITE_ORIGIN + detail_url

                all_products.append({
                    "listing_name": listing_name,
                    "listing_image": listing_image,
                    "detail_url": detail_url,
                    "material": category_name.lower(),
                    "material_category": category_name,
                })

                if len(all_products) >= MAX_PRODUCTS_PER_RUN:
                    break

            time.sleep(SCRAPE_DELAY_S)

        # Now fetch each detail page
        enriched = []
        for pdata in all_products:
            try:
                detail = UrnCatalogScraper._fetch_detail_page(
                    client, pdata["detail_url"]
                )
                if detail:
                    pdata.update(detail)
                enriched.append(pdata)
            except Exception as e:
                logger.warning(
                    "Failed to fetch detail for %s: %s",
                    pdata.get("listing_name", "unknown"),
                    e,
                )
                enriched.append(pdata)  # keep listing data even without detail

            time.sleep(SCRAPE_DELAY_S)

        client.close()
        return enriched

    @staticmethod
    def _fetch_detail_page(client, url: str) -> dict | None:
        """Fetch a product detail page and extract structured data."""
        try:
            resp = client.get(url)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", url, e)
            return None

        soup = _get_soup(resp.text)
        data = {}

        # Product name
        name_el = soup.select_one(DETAIL_SELECTORS["product_name"])
        if name_el:
            data["name"] = name_el.text.strip()

        # Main image
        img_el = soup.select_one(DETAIL_SELECTORS["main_image"])
        if img_el:
            src = img_el.get("src", "")
            if src and not src.startswith("http"):
                src = SITE_ORIGIN + src
            data["image_url"] = src

            # Infer SKU from image filename (e.g., P2013-CloisonneOpal-750.jpg)
            sku_match = re.search(DETAIL_SELECTORS["image_sku_regex"], src)
            if sku_match:
                data["sku_from_image"] = sku_match.group(1)

        # Short description
        short_el = soup.select_one(DETAIL_SELECTORS["short_description"])
        if short_el:
            data["short_description"] = short_el.text.strip()

        # Long description
        long_el = soup.select_one(DETAIL_SELECTORS["long_description"])
        if long_el:
            data["long_description"] = long_el.text.strip()

        # Related products (mementos, companions)
        related_section = soup.select_one(DETAIL_SELECTORS["related_section"])
        if related_section:
            related_items = []
            # Extract item numbers from text
            text = related_section.get_text()
            item_matches = re.findall(r"Item Number:\s*(P\d{4}|D\d{4})", text)
            for item_num in item_matches:
                related_items.append({"item_number": item_num})
            data["related_items"] = related_items

        data["catalog_url"] = url
        return data

    @staticmethod
    def enrich_products_from_web(
        db: Session,
        tenant_id: str,
        products: list[UrnProduct],
    ) -> tuple[int, int]:
        """Enrich existing UrnProduct records with website data.

        Matches by SKU (from image filename) or by name similarity.
        Returns (enriched_count, not_found_count).
        """
        web_data = UrnCatalogScraper.scrape_all_categories()

        # Build lookup by SKU and by normalized name
        by_sku: dict[str, dict] = {}
        by_name: dict[str, dict] = {}
        for wd in web_data:
            sku = wd.get("sku_from_image")
            if sku:
                by_sku[sku.upper()] = wd
            name = wd.get("name") or wd.get("listing_name") or ""
            # Normalize: "Opal Cloisonne Urn" -> "opal cloisonne"
            norm_name = re.sub(r"\s+(urn|memento|heart|pendant)$", "", name.lower()).strip()
            if norm_name:
                by_name[norm_name] = wd

        enriched = 0
        not_found = 0

        for product in products:
            wd = None

            # Try SKU match first
            if product.sku:
                wd = by_sku.get(product.sku.upper())

            # Try name match
            if not wd and product.name:
                norm = re.sub(r"\s+(urn|memento|heart|pendant)$", "", product.name.lower()).strip()
                wd = by_name.get(norm)

            if wd:
                changed = False
                if wd.get("short_description") and not product.wilbert_description:
                    product.wilbert_description = wd["short_description"]
                    changed = True
                if wd.get("long_description") and not product.wilbert_long_description:
                    product.wilbert_long_description = wd["long_description"]
                    changed = True
                if wd.get("image_url") and not product.image_url:
                    product.image_url = wd["image_url"]
                    changed = True
                if wd.get("catalog_url") and not product.wilbert_catalog_url:
                    product.wilbert_catalog_url = wd["catalog_url"]
                    changed = True
                if changed:
                    enriched += 1
            else:
                not_found += 1

        if enriched > 0:
            db.flush()

        return enriched, not_found

    @staticmethod
    def download_product_image(image_url: str) -> bytes | None:
        """Download a product image from wilbert.com. Returns bytes or None."""
        try:
            client = _get_http_client()
            resp = client.get(image_url)
            resp.raise_for_status()
            client.close()
            return resp.content
        except Exception as e:
            logger.warning("Failed to download image %s: %s", image_url, e)
            return None

    # ------------------------------------------------------------------
    # Automatic PDF catalog fetch
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_pdf_url() -> str | None:
        """Return the direct PDF URL.

        First tries the known static URL.  If that 404s, falls back to
        scraping the catalog landing page for any .pdf link.
        """
        client = _get_http_client()
        try:
            resp = client.head(CATALOG_PDF_URL, follow_redirects=True)
            if resp.status_code < 400:
                return CATALOG_PDF_URL
        except Exception:
            pass

        # Fallback: scrape the landing page for a PDF link
        try:
            resp = client.get(CATALOG_PDF_PAGE_URL)
            resp.raise_for_status()
            soup = _get_soup(resp.text)
            for a in soup.select("a[href$='.pdf']"):
                href = a.get("href", "")
                if "cremation" in href.lower() or "catalog" in href.lower():
                    if not href.startswith("http"):
                        href = SITE_ORIGIN + href
                    return href
        except Exception as e:
            logger.warning("Failed to scrape catalog landing page: %s", e)
        finally:
            client.close()

        return None

    @staticmethod
    def fetch_catalog_pdf(
        db: Session,
        tenant_id: str,
        *,
        force: bool = False,
    ) -> dict:
        """Download the Wilbert catalog PDF and trigger parsing if changed.

        Returns dict with keys:
            downloaded (bool) — whether a PDF was fetched
            changed (bool) — whether the PDF differs from the stored version
            path (str|None) — temp path to the downloaded file (caller should delete)
            pdf_url (str|None) — the resolved download URL
            sync_log_id (str|None) — ID of the ingestion sync log if parsing ran
            products_added (int)
            products_updated (int)
            products_skipped (int)
        """
        from app.models.urn_tenant_settings import UrnTenantSettings

        result = {
            "downloaded": False,
            "changed": False,
            "path": None,
            "pdf_url": None,
            "sync_log_id": None,
            "products_added": 0,
            "products_updated": 0,
            "products_skipped": 0,
        }

        # Resolve the PDF URL
        pdf_url = UrnCatalogScraper._resolve_pdf_url()
        if not pdf_url:
            logger.error("SSC: could not resolve Wilbert catalog PDF URL")
            return result
        result["pdf_url"] = pdf_url

        # Download the PDF
        client = _get_http_client()
        try:
            logger.info("Fetching catalog PDF from %s", pdf_url)
            resp = client.get(pdf_url)
            resp.raise_for_status()
            pdf_bytes = resp.content
            result["downloaded"] = True
        except Exception as e:
            logger.error("Failed to download catalog PDF: %s", e)
            return result
        finally:
            client.close()

        # Compute MD5 hash
        new_hash = hashlib.md5(pdf_bytes).hexdigest()

        # Get or create tenant settings
        settings = (
            db.query(UrnTenantSettings)
            .filter(UrnTenantSettings.tenant_id == tenant_id)
            .first()
        )
        if not settings:
            settings = UrnTenantSettings(tenant_id=tenant_id)
            db.add(settings)
            db.flush()

        old_hash = settings.catalog_pdf_hash

        if old_hash == new_hash and not force:
            logger.info(
                "Catalog PDF unchanged (hash %s) — skipping parse", new_hash[:12]
            )
            settings.catalog_pdf_last_fetched = datetime.now(timezone.utc)
            db.commit()
            return result

        result["changed"] = True

        # Save to temp file for parsing
        tmp = tempfile.NamedTemporaryFile(
            suffix=".pdf", prefix="wilbert_catalog_", delete=False
        )
        tmp.write(pdf_bytes)
        tmp.close()
        result["path"] = tmp.name
        logger.info(
            "Catalog PDF changed (old=%s new=%s) — saved to %s",
            (old_hash or "none")[:12],
            new_hash[:12],
            tmp.name,
        )

        # Upload to R2 for archival
        r2_key = f"catalogs/wilbert/cremation-choices-{new_hash[:12]}.pdf"
        try:
            from app.services.legacy_r2_client import upload_bytes

            upload_bytes(pdf_bytes, r2_key, content_type="application/pdf")
        except Exception as exc:
            logger.warning("R2 upload of catalog PDF failed (non-fatal): %s", exc)
            r2_key = settings.catalog_pdf_r2_key  # keep old key

        # Update tenant settings
        settings.catalog_pdf_hash = new_hash
        settings.catalog_pdf_last_fetched = datetime.now(timezone.utc)
        settings.catalog_pdf_r2_key = r2_key
        db.commit()

        # Trigger ingestion — always enrich from website too
        from app.services.wilbert_ingestion_service import WilbertIngestionService

        log = WilbertIngestionService.ingest_from_pdf(
            db, tenant_id, tmp.name, enrich_from_website=True
        )
        result["sync_log_id"] = log.id
        result["products_added"] = log.products_added
        result["products_updated"] = log.products_updated
        result["products_skipped"] = log.products_skipped

        return result

    @staticmethod
    def run_full_scrape(
        db: Session,
        tenant_id: str,
    ) -> dict:
        """Run a complete catalog sync: PDF fetch + website enrichment.

        Steps:
        1. fetch_catalog_pdf() — downloads and parses PDF if changed
        2. Website enrichment — scrapes wilbert.com for descriptions/images
        3. Cross-reference — flags products in PDF not found on website
        4. Returns combined results

        Returns dict with pdf_result, web_enriched, web_not_found, sync_log_id.
        """
        # Step 1: PDF fetch
        pdf_result = UrnCatalogScraper.fetch_catalog_pdf(db, tenant_id)

        # Clean up temp file
        if pdf_result.get("path"):
            import os
            try:
                os.unlink(pdf_result["path"])
            except OSError:
                pass

        # Step 2: Website enrichment
        products = (
            db.query(UrnProduct)
            .filter(
                UrnProduct.tenant_id == tenant_id,
                UrnProduct.source_type == "drop_ship",
                UrnProduct.is_active == True,
            )
            .all()
        )

        web_enriched = 0
        web_not_found = 0
        try:
            web_enriched, web_not_found = UrnCatalogScraper.enrich_products_from_web(
                db, tenant_id, products
            )
        except Exception as e:
            logger.warning("Website enrichment failed (non-fatal): %s", e)

        # Step 3: Cross-reference — products in DB without web descriptions
        missing_web = (
            db.query(UrnProduct)
            .filter(
                UrnProduct.tenant_id == tenant_id,
                UrnProduct.source_type == "drop_ship",
                UrnProduct.is_active == True,
                UrnProduct.wilbert_description.is_(None),
                UrnProduct.wilbert_long_description.is_(None),
            )
            .count()
        )
        if missing_web > 0:
            logger.info(
                "Cross-reference: %d products from PDF have no website description",
                missing_web,
            )

        # Create combined sync log
        log = UrnCatalogSyncLog(
            tenant_id=tenant_id,
            status="completed",
            sync_type="full_pipeline",
            products_added=pdf_result["products_added"],
            products_updated=pdf_result["products_updated"] + web_enriched,
            products_skipped=pdf_result["products_skipped"],
            completed_at=datetime.now(timezone.utc),
        )
        db.add(log)
        db.commit()

        return {
            "pdf_downloaded": pdf_result["downloaded"],
            "pdf_changed": pdf_result["changed"],
            "pdf_url": pdf_result.get("pdf_url"),
            "products_added": pdf_result["products_added"],
            "products_updated": pdf_result["products_updated"],
            "products_skipped": pdf_result["products_skipped"],
            "web_enriched": web_enriched,
            "web_not_found": web_not_found,
            "missing_web_descriptions": missing_web,
            "sync_log_id": log.id,
        }

    @staticmethod
    def run_delta_sync(
        db: Session,
        tenant_id: str,
    ) -> dict:
        """Lightweight sync: fetch PDF (hash check makes it cheap) only.

        Only re-parses if Wilbert published a new catalog version.
        """
        pdf_result = UrnCatalogScraper.fetch_catalog_pdf(db, tenant_id)

        # Clean up temp file
        if pdf_result.get("path"):
            import os
            try:
                os.unlink(pdf_result["path"])
            except OSError:
                pass

        return {
            "pdf_downloaded": pdf_result["downloaded"],
            "pdf_changed": pdf_result["changed"],
            "pdf_url": pdf_result.get("pdf_url"),
            "products_added": pdf_result["products_added"],
            "products_updated": pdf_result["products_updated"],
            "products_skipped": pdf_result["products_skipped"],
            "sync_log_id": pdf_result.get("sync_log_id"),
        }
