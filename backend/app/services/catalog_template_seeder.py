"""Seed product catalog templates for Wilbert vault lines.

Runs at startup to ensure all Wilbert product lines are available
for price list import matching and catalog builder selection.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.product_catalog_template import ProductCatalogTemplate

logger = logging.getLogger(__name__)

WILBERT_BURIAL_VAULTS = [
    ("Wilbert Bronze Burial Vault", "BV-WBR", "Premium bronze-finished Wilbert vault"),
    ("Bronze Triune Burial Vault", "BV-BTRI", "Bronze Triune three-piece protective vault"),
    ("Copper Triune Burial Vault", "BV-CTRI", "Copper Triune three-piece protective vault"),
    ("Stainless Steel Triune Burial Vault", "BV-SSTRI", "Stainless steel Triune three-piece protective vault"),
    ("Cameo Rose Triune Burial Vault", "BV-CRTRI", "Cameo Rose Triune three-piece protective vault"),
    ("Veteran Triune Burial Vault", "BV-VTRI", "Military tribute Triune vault"),
    ("White Tribute Burial Vault", "BV-WTRIB", "White Tribute entry-level vault"),
    ("Gray Tribute Burial Vault", "BV-GTRIB", "Gray Tribute entry-level vault"),
    ("White Venetian Burial Vault", "BV-WVEN", "White finish Venetian air-sealed vault"),
    ("Gold Venetian Burial Vault", "BV-GVEN", "Gold finish Venetian air-sealed vault"),
    ("Continental Burial Vault", "BV-CON", "Continental reinforced concrete vault"),
    ("Salute Burial Vault", "BV-SAL", "Salute reinforced concrete vault"),
    ("Monarch Burial Vault", "BV-MRC", "Monarch reinforced concrete vault"),
    ("Graveliner", "GL-STD", "Standard concrete grave liner"),
    ("Graveliner (Social Service)", "GL-SS", "Social service concrete grave liner"),
    ('Loved & Cherished 19"', "LC-19", "Infant/child vault 19 inch"),
    ('Loved & Cherished 24"', "LC-24", "Infant/child vault 24 inch"),
    ('Loved & Cherished 31"', "LC-31", "Infant/child vault 31 inch"),
]

WILBERT_URN_VAULTS = [
    ("Bronze Triune Urn Vault", "UV-BTRI", "Bronze Triune urn vault"),
    ("Copper Triune Urn Vault", "UV-CTRI", "Copper Triune urn vault"),
    ("Stainless Steel Triune Urn Vault", "UV-SSTRI", "Stainless Steel Triune urn vault"),
    ("Cameo Rose Triune Urn Vault", "UV-CRTRI", "Cameo Rose Triune urn vault"),
    ("Universal Urn Vault (Cream & Gold)", "UV-UCG", "Universal urn vault cream and gold finish"),
    ("Universal Urn Vault (White & Silver)", "UV-UWS", "Universal urn vault white and silver finish"),
    ("White Venetian Urn Vault", "UV-WVEN", "White Venetian urn vault"),
    ("Gold Venetian Urn Vault", "UV-GVEN", "Gold Venetian urn vault"),
    ("Salute Urn Vault", "UV-SAL", "Salute urn vault"),
    ("Monticello Urn Vault", "UV-MON", "Monticello urn vault"),
    ("Graveliner Urn Vault", "UV-GL", "Graveliner urn vault"),
]

CEMETERY_EQUIPMENT = [
    ("Lowering Device", "CE-LD", "Lowering device rental per service"),
    ("Cremation Table", "CE-CT", "Cremation table rental per service"),
    ("Cemetery Tent - Single", "CE-TS", "Single tent (seats ~50) rental per service"),
    ("Cemetery Tent - Double", "CE-TD", "Double tent (seats ~100) rental per service"),
    ("Grass Mats", "CE-GM", "Artificial turf/grass mats rental per service"),
    ("Graveside Chairs", "CE-CH", "Graveside chairs rental per set"),
]


def seed_wilbert_templates(db: Session) -> None:
    """Seed all Wilbert product catalog templates. Idempotent — skips existing."""
    try:
        existing = {
            t.product_name
            for t in db.query(ProductCatalogTemplate)
            .filter(ProductCatalogTemplate.preset == "manufacturing")
            .all()
        }

        now = datetime.now(timezone.utc)
        added = 0

        for name, sku, desc in WILBERT_BURIAL_VAULTS:
            if name not in existing:
                db.add(ProductCatalogTemplate(
                    id=str(uuid.uuid4()),
                    preset="manufacturing",
                    category="Burial Vaults",
                    product_name=name,
                    product_description=desc,
                    sku_prefix=sku,
                    default_unit="each",
                    is_manufactured=True,
                    sort_order=added + 10,
                    created_at=now,
                ))
                added += 1

        for name, sku, desc in WILBERT_URN_VAULTS:
            if name not in existing:
                db.add(ProductCatalogTemplate(
                    id=str(uuid.uuid4()),
                    preset="manufacturing",
                    category="Urn Vaults",
                    product_name=name,
                    product_description=desc,
                    sku_prefix=sku,
                    default_unit="each",
                    is_manufactured=True,
                    sort_order=added + 30,
                    created_at=now,
                ))
                added += 1

        for name, sku, desc in CEMETERY_EQUIPMENT:
            if name not in existing:
                db.add(ProductCatalogTemplate(
                    id=str(uuid.uuid4()),
                    preset="manufacturing",
                    category="Cemetery Equipment",
                    product_name=name,
                    product_description=desc,
                    sku_prefix=sku,
                    default_unit="each",
                    is_manufactured=False,
                    sort_order=added + 50,
                    created_at=now,
                ))
                added += 1

        if added > 0:
            db.commit()
            logger.info("Seeded %d Wilbert product catalog templates", added)
        else:
            logger.info("Wilbert product catalog templates already up to date")

    except Exception as e:
        logger.warning("Failed to seed Wilbert templates: %s", e)
        db.rollback()
