"""Sunnycrest product seeder — idempotent one-time seed for all Sunnycrest products."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_category import ProductCategory


def _get_or_create_category(
    db: Session, company_id: str, name: str
) -> ProductCategory:
    """Get existing category or create it."""
    cat = (
        db.query(ProductCategory)
        .filter(
            ProductCategory.company_id == company_id,
            ProductCategory.name == name,
            ProductCategory.parent_id.is_(None),
        )
        .first()
    )
    if cat:
        return cat

    cat = ProductCategory(
        id=str(uuid.uuid4()),
        company_id=company_id,
        name=name,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(cat)
    db.flush()
    return cat


def _product_exists(db: Session, company_id: str, name: str) -> bool:
    """Check if a product with this name already exists for the company."""
    return (
        db.query(Product)
        .filter(
            Product.company_id == company_id,
            Product.name == name,
        )
        .first()
        is not None
    )


def seed_sunnycrest_products(db: Session) -> dict:
    """Seed all Sunnycrest products. Idempotent — skips existing by name.

    Returns: {"created": N, "skipped": N, "errors": [...]}
    """
    from app.models.company import Company

    company = (
        db.query(Company)
        .filter(Company.slug == "sunnycrest")
        .first()
    )
    if not company:
        return {"created": 0, "skipped": 0, "errors": ["Company with slug 'sunnycrest' not found"]}

    company_id = company.id
    now = datetime.now(timezone.utc)
    created = 0
    skipped = 0
    errors = []

    # -----------------------------------------------------------------------
    # Categories
    # -----------------------------------------------------------------------
    cat_burial = _get_or_create_category(db, company_id, "Burial Vaults")
    cat_urn_vaults = _get_or_create_category(db, company_id, "Urn Vaults")
    cat_urns = _get_or_create_category(db, company_id, "Urns")
    cat_graveside = _get_or_create_category(db, company_id, "Graveside Service")
    cat_fees = _get_or_create_category(db, company_id, "Fees")

    # -----------------------------------------------------------------------
    # Product definitions
    # Format: (name, category, price, kwargs_dict)
    # -----------------------------------------------------------------------
    products_to_seed = [
        # --- Burial Vaults ---
        ("Wilbert Bronze", cat_burial, Decimal("13452.00"), {
            "wilbert_sku": "BV-WBR", "product_line": "Wilbert Bronze",
        }),
        ("Bronze Triune", cat_burial, Decimal("3864.00"), {
            "wilbert_sku": "BV-BTR", "product_line": "Triune",
        }),
        ("Copper Triune", cat_burial, Decimal("3457.00"), {
            "wilbert_sku": "BV-CTR", "product_line": "Triune",
        }),
        ("SST Triune", cat_burial, Decimal("2850.00"), {
            "wilbert_sku": "BV-STR", "product_line": "Triune",
        }),
        ("Cameo Rose", cat_burial, Decimal("2850.00"), {
            "wilbert_sku": "BV-CR", "product_line": "Cameo Rose",
        }),
        ("Veteran Triune", cat_burial, Decimal("2850.00"), {
            "wilbert_sku": "BV-VTR", "product_line": "Veteran",
        }),
        ("Tribute", cat_burial, Decimal("2570.00"), {
            "wilbert_sku": "BV-TRB", "product_line": "Tribute",
        }),
        ("Venetian", cat_burial, Decimal("1934.00"), {
            "wilbert_sku": "BV-VEN", "product_line": "Venetian",
        }),
        ("Continental", cat_burial, Decimal("1607.00"), {
            "wilbert_sku": "BV-CON", "product_line": "Continental",
        }),
        ("Salute", cat_burial, Decimal("1475.00"), {
            "wilbert_sku": "BV-SAL", "product_line": "Salute",
        }),
        ("Monticello", cat_burial, Decimal("1405.00"), {
            "wilbert_sku": "BV-MON", "product_line": "Monticello",
        }),
        ("Monarch", cat_burial, Decimal("1176.00"), {
            "wilbert_sku": "BV-MCH", "product_line": "Monarch",
        }),
        ("Graveliner", cat_burial, Decimal("996.00"), {
            "wilbert_sku": "BV-GL", "product_line": "Graveliner",
        }),
        ("Graveliner (SS)", cat_burial, Decimal("880.00"), {
            "wilbert_sku": "BV-GLSS", "product_line": "Graveliner",
        }),
        ('Continental 34"', cat_burial, Decimal("2179.00"), {
            "wilbert_sku": "BV-CON34", "product_line": "Continental",
        }),
        ('Graveliner 34"', cat_burial, Decimal("1492.00"), {
            "wilbert_sku": "BV-GL34", "product_line": "Graveliner",
        }),
        ('Graveliner 38"', cat_burial, Decimal("2060.00"), {
            "wilbert_sku": "BV-GL38", "product_line": "Graveliner",
        }),
        ("Pine Box", cat_burial, None, {
            "wilbert_sku": "BV-PB", "product_line": "Pine Box",
            "is_call_office": True,
        }),
        ('Loved & Cherished 19"', cat_burial, Decimal("239.00"), {
            "wilbert_sku": "BV-LC19", "product_line": "Loved & Cherished",
            "variant_type": '19"',
        }),
        ('Loved & Cherished 24"', cat_burial, Decimal("374.00"), {
            "wilbert_sku": "BV-LC24", "product_line": "Loved & Cherished",
            "variant_type": '24"',
        }),
        ('Loved & Cherished 31"', cat_burial, Decimal("452.00"), {
            "wilbert_sku": "BV-LC31", "product_line": "Loved & Cherished",
            "variant_type": '31"',
        }),

        # --- Urn Vaults ---
        ("Bronze Triune Urn Vault", cat_urn_vaults, Decimal("855.00"), {
            "wilbert_sku": "UV-BTR", "product_line": "Triune",
        }),
        ("Copper Triune Urn Vault", cat_urn_vaults, Decimal("835.00"), {
            "wilbert_sku": "UV-CTR", "product_line": "Triune",
        }),
        ("SST Triune Urn Vault", cat_urn_vaults, Decimal("822.00"), {
            "wilbert_sku": "UV-STR", "product_line": "Triune",
        }),
        ("Cameo Rose Urn Vault", cat_urn_vaults, Decimal("822.00"), {
            "wilbert_sku": "UV-CR", "product_line": "Cameo Rose",
        }),
        ("Veteran Triune Urn Vault", cat_urn_vaults, Decimal("822.00"), {
            "wilbert_sku": "UV-VTR", "product_line": "Veteran",
        }),
        ("Venetian Urn Vault", cat_urn_vaults, Decimal("616.00"), {
            "wilbert_sku": "UV-VEN", "product_line": "Venetian",
        }),
        ("Monticello Urn Vault", cat_urn_vaults, Decimal("493.00"), {
            "wilbert_sku": "UV-MON", "product_line": "Monticello",
        }),
        ("Salute Urn Vault", cat_urn_vaults, Decimal("436.00"), {
            "wilbert_sku": "UV-SAL", "product_line": "Salute",
        }),
        ("Graveliner Urn Vault", cat_urn_vaults, Decimal("284.00"), {
            "wilbert_sku": "UV-GL", "product_line": "Graveliner",
        }),
        ("Cream & Gold Urn Vault", cat_urn_vaults, Decimal("510.00"), {
            "wilbert_sku": "UV-CG", "product_line": "Universal",
        }),
        ("White & Silver Urn Vault", cat_urn_vaults, Decimal("510.00"), {
            "wilbert_sku": "UV-WS", "product_line": "Universal",
        }),

        # --- Urns ---
        ("P445 Country Bouquet", cat_urns, Decimal("151.00"), {"sku": "P445"}),
        ("P440 Jewel", cat_urns, Decimal("142.00"), {"sku": "P440"}),
        ("P440A Moon Stone", cat_urns, Decimal("142.00"), {"sku": "P440A"}),
        ("P440B Sedona", cat_urns, Decimal("142.00"), {"sku": "P440B"}),
        ("P363 Victorian", cat_urns, Decimal("212.00"), {"sku": "P363"}),
        ("P600 Arlington", cat_urns, Decimal("462.00"), {"sku": "P600"}),
        ("P300 Cream & Gold", cat_urns, Decimal("124.00"), {
            "sku": "P300", "product_line": "Regal",
        }),
        ("P300WS White & Silver", cat_urns, Decimal("110.00"), {
            "sku": "P300WS", "product_line": "Regal",
        }),
        ("P300P Pebble Dust", cat_urns, Decimal("113.00"), {
            "sku": "P300P", "product_line": "Regal",
        }),
        ("P310 Cream & Gold", cat_urns, Decimal("135.00"), {
            "sku": "P310", "product_line": "Tribute",
        }),
        ("P310WS White & Silver", cat_urns, Decimal("111.00"), {
            "sku": "P310WS", "product_line": "Tribute",
        }),
        ("P310P Pebble Dust", cat_urns, Decimal("118.00"), {
            "sku": "P310P", "product_line": "Tribute",
        }),

        # --- Graveside Service (conditional pricing) ---
        ("Full Equipment", cat_graveside, Decimal("300.00"), {
            "has_conditional_pricing": True,
            "price_without_our_product": Decimal("600.00"),
            "pricing_type": "rental",
            "is_lowering_device": True,
        }),
        ("Lowering Device & Grass", cat_graveside, Decimal("185.00"), {
            "has_conditional_pricing": True,
            "price_without_our_product": Decimal("487.00"),
            "pricing_type": "rental",
            "is_lowering_device": True,
        }),
        ("Lowering Device Only", cat_graveside, Decimal("140.00"), {
            "has_conditional_pricing": True,
            "price_without_our_product": Decimal("487.00"),
            "pricing_type": "rental",
            "is_lowering_device": True,
        }),
        # Vault Placer — $0.00, added automatically for funeral homes that prefer it
        ("Vault Placer", cat_graveside, Decimal("0.00"), {
            "sku": "PLACER-01",
            "description": "Vault placement device for lowering device service",
            "unit_of_measure": "each",
            "pricing_type": "sale",
            "is_placer": True,
            "is_inventory_tracked": False,
        }),
        ("Tent Only", cat_graveside, Decimal("225.00"), {
            "has_conditional_pricing": True,
            "price_without_our_product": Decimal("557.00"),
            "pricing_type": "rental",
        }),
        ("Extra Chairs (over 8)", cat_graveside, Decimal("5.00"), {
            "has_conditional_pricing": True,
            "price_without_our_product": Decimal("8.00"),
            "pricing_type": "rental",
        }),

        # --- Other Charges / Fees ---
        ("Sunday & Holiday", cat_fees, Decimal("550.00"), {}),
        ("Saturday Spring Burial", cat_fees, Decimal("200.00"), {}),
        ("Late Arrival per 1/2 hr after 4pm", cat_fees, Decimal("75.00"), {}),
        ("Legacy Rush Fee", cat_fees, Decimal("100.00"), {}),
        ("Late Notice", cat_fees, Decimal("250.00"), {}),
    ]

    for name, category, price, kwargs in products_to_seed:
        try:
            if _product_exists(db, company_id, name):
                skipped += 1
                continue

            product = Product(
                id=str(uuid.uuid4()),
                company_id=company_id,
                category_id=category.id,
                name=name,
                price=price,
                is_active=True,
                source="seeder",
                created_at=now,
                updated_at=now,
            )

            # Apply optional fields
            for key, val in kwargs.items():
                if hasattr(product, key):
                    setattr(product, key, val)

            db.add(product)
            created += 1

        except Exception as exc:
            errors.append(f"{name}: {exc}")

    db.flush()

    # Ensure product flags are set correctly (idempotent — safe to run after seeding)
    flag_placer_and_lowering_products(db, company_id)

    return {"created": created, "skipped": skipped, "errors": errors}


def flag_placer_and_lowering_products(db: Session, company_id: str) -> dict:
    """Idempotent: set is_lowering_device and is_placer flags on existing products.

    Safe to call multiple times — only updates products that need it.
    Returns {"updated": N}
    """
    updated = 0

    lowering_device_names = ["Full Equipment", "Lowering Device & Grass", "Lowering Device Only"]
    placer_names = ["Vault Placer"]

    for name in lowering_device_names:
        product = (
            db.query(Product)
            .filter(Product.company_id == company_id, Product.name == name)
            .first()
        )
        if product and not product.is_lowering_device:
            product.is_lowering_device = True
            updated += 1

    for name in placer_names:
        product = (
            db.query(Product)
            .filter(Product.company_id == company_id, Product.name == name)
            .first()
        )
        if product and not product.is_placer:
            product.is_placer = True
            updated += 1

    if updated:
        db.flush()

    return {"updated": updated}
