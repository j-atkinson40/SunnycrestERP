"""Wilbert catalog scraper configuration.

All Wilbert-specific selectors and field mappings live here.
Zero selectors should be hardcoded in scraper logic.
"""

# Wilbert's public catalog root
CATALOG_BASE_URL = "https://www.wilbert.com/urns"

# CSS selectors for product data extraction
PRODUCT_SELECTORS = {
    "product_card": ".product-card, .product-item",
    "name": ".product-name, .product-title, h3",
    "sku": ".product-sku, [data-sku]",
    "material": ".product-material, .material-type",
    "style": ".product-style, .style-name",
    "colors": ".color-option, .color-swatch",
    "fonts": ".font-option, .font-name",
    "image": ".product-image img, .product-photo img",
    "detail_link": "a.product-link, .product-card a",
    "price": ".product-price, .price",
    "photo_etch_badge": ".photo-etch, .photo-capable",
    "keepsake_badge": ".keepsake-set, .companion-set",
    "companion_items": ".companion-item, .set-piece",
}

# Selectors for product detail pages
DETAIL_SELECTORS = {
    "description": ".product-description, .product-details",
    "dimensions": ".product-dimensions, .dimensions",
    "capacity": ".product-capacity, .capacity",
    "color_gallery": ".color-gallery img, .color-options img",
    "font_samples": ".font-samples, .available-fonts",
}

# Polite crawl delay (milliseconds)
SCRAPE_DELAY_MS = 1500

# User agent string for scraper requests
USER_AGENT = (
    "BridgeableCatalogSync/1.0 "
    "(+https://getbridgeable.com; catalog sync for Wilbert licensees)"
)

# Maximum products per scrape run (safety limit)
MAX_PRODUCTS_PER_RUN = 500

# Field mapping: Wilbert catalog field → UrnProduct model field
FIELD_MAPPING = {
    "name": "name",
    "sku": "sku",
    "material": "material",
    "style": "style",
    "colors": "available_colors",
    "fonts": "available_fonts",
    "image_url": "image_url",
    "catalog_url": "wilbert_catalog_url",
    "photo_etch": "photo_etch_capable",
    "is_keepsake": "is_keepsake_set",
    "companions": "companion_skus",
}
