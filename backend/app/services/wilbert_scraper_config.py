"""Wilbert catalog scraper configuration.

All Wilbert-specific URLs, selectors and field mappings live here.
Zero selectors should be hardcoded in scraper logic.

Based on research crawl of wilbert.com (April 2026):
- Server-rendered ASP.NET WebForms — no JS required
- Product images are 750x750 PNG/JPG
- Detail pages at /{product-slug}/ (root-level, NOT under /store/)
"""

# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------

CATALOG_BASE_URL = "https://www.wilbert.com/store/cremation/urns/"

# Direct URL to the Wilbert Cremation Choices catalog PDF (Volume 11)
CATALOG_PDF_URL = "https://www.wilbert.com/assets/1/7/CCV8-Cremation_Choices_Catalog.pdf"

# Landing page that links to the PDF (fallback — scan for .pdf links if direct URL changes)
CATALOG_PDF_PAGE_URL = "https://www.wilbert.com/cremation/cremation-choices-catalog/"

CATEGORY_URLS = {
    "Ceramic": "/store/cremation/urns/ceramic/",
    "Cloisonne": "/store/cremation/urns/cloisonne/",
    "Cultured Marble": "/store/cremation/urns/cultured-marble/",
    "Eco": "/store/cremation/urns/eco/",
    "Glass": "/store/cremation/urns/glass/",
    "Metal": "/store/cremation/urns/metal/",
    "Stone": "/store/cremation/urns/stone/",
    "Synthetic": "/store/cremation/urns/synthetic/",
    "Wood": "/store/cremation/urns/wood/",
}

MEMENTO_URL = "/store/cremation/mementos/"
JEWELRY_URL = "/store/cremation/memorial-jewelry/"

SITE_ORIGIN = "https://www.wilbert.com"

# ---------------------------------------------------------------------------
# CSS selectors — Listing page (/store/cremation/urns/{material}/)
# ---------------------------------------------------------------------------

LISTING_SELECTORS = {
    # Product grid
    "product_grid": ".product-list",
    "product_items": ".product-list > a, .product-list > div > a",
    "product_image": ".product-list img",
    "product_name": ".product-list img[alt]",  # name is in alt attribute
    "product_link": ".product-list a[href]",

    # Category navigation
    "category_nav": ".sub-nav",
    "active_category": ".sub-nav a.current",
    "category_links": ".sub-nav a[href*='/urns/']",

    # Pagination (if exists)
    "pagination": ".pagination, .pager",
}

# ---------------------------------------------------------------------------
# CSS selectors — Product detail page (/{product-slug}/)
# ---------------------------------------------------------------------------

DETAIL_SELECTORS = {
    # Core product info
    "product_name": "h1.item-name",
    "main_image": "#productImage img.main-image",
    "image_src": "#productImage img.main-image",
    "schema_product": "div[itemscope][itemtype='http://schema.org/Product']",

    # Descriptions
    "short_description": "div.item-desc p:first-child",
    "long_description": "div.item-desc p:nth-child(2)",
    "all_descriptions": "div.item-desc p",

    # Related products (mementos, companions)
    "related_section": "div.recommendation",
    "related_items": "div.recommendation .product-card, div.recommendation a",

    # SKU inference from image filename
    # Pattern: /(P\d{4}|D\d{4})-/ in img src
    "image_sku_regex": r"(P\d{4}|D\d{4})",
}

# ---------------------------------------------------------------------------
# Crawl settings
# ---------------------------------------------------------------------------

# Polite crawl delay (seconds)
SCRAPE_DELAY_S = 1.5

# User agent string for scraper requests
USER_AGENT = (
    "BridgeableCatalogSync/1.0 "
    "(+https://getbridgeable.com; catalog sync for Wilbert licensees)"
)

# Maximum products per scrape run (safety limit)
MAX_PRODUCTS_PER_RUN = 500

# ---------------------------------------------------------------------------
# Field mapping: scraped field → UrnProduct model field
# ---------------------------------------------------------------------------

FIELD_MAPPING = {
    "name": "name",
    "sku": "sku",
    "material": "material",
    "style": "style",
    "colors": "available_colors",
    "image_url": "image_url",
    "catalog_url": "wilbert_catalog_url",
    "short_description": "wilbert_description",
    "long_description": "wilbert_long_description",
}
