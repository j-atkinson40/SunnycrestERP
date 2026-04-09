"""UrnCatalogScraper — crawls Wilbert's public catalog for urn product data.

Scrapes wilbert.com category listing pages and individual product detail pages
to extract descriptions, images, and related product links. Uses real CSS
selectors discovered during site research (April 2026).

Website is server-rendered ASP.NET WebForms — no JS/headless browser needed.
"""

import logging
import re
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.urn_catalog_sync_log import UrnCatalogSyncLog
from app.models.urn_product import UrnProduct
from app.services.wilbert_scraper_config import (
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
