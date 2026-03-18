"""Catalog Builder — creates products in bulk from structured category/line selections."""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_substitution_rule import ProductSubstitutionRule

logger = logging.getLogger(__name__)

# SKU prefix map for Wilbert lines
WILBERT_SKU_PREFIXES = {
    "Monticello": "MONT",
    "Venetian": "VEN",
    "Triune": "TRI",
    "Wilbert Testimonial": "TEST",
    "Wilbert Bronze": "WBRZ",
    "Wilbert Copper": "WCOP",
    "Wilbert Stainless": "WSTL",
    "Wilbert Veteran": "WVET",
    "Infant / Baby Vault": "INF",
    "Oversize Vault": "OVER",
}

VARIANT_SUFFIXES = {
    "STD-1P": "Standard 1-Piece",
    "STD-2P": "Standard 2-Piece",
    "OS-1P": "Oversize 1-Piece",
    "OS-2P": "Oversize 2-Piece",
}


def build_catalog(
    db: Session,
    tenant_id: str,
    user_id: str,
    data: dict,
) -> dict:
    """Build a complete product catalog from structured selections.

    data format:
    {
        "burial_vaults": {
            "enabled": true,
            "wilbert_lines": [
                {"name": "Monticello", "base_price": 1200, "variants": [
                    {"variant": "STD-1P", "price": 1200},
                    {"variant": "STD-2P", "price": 1380},
                    ...
                ]},
            ],
            "own_lines": [
                {"name": "Custom Vault", "sku_prefix": "CUST", "base_price": 800, "variants": [...]},
            ],
        },
        "urn_vaults": {
            "enabled": true,
            "items": [{"name": "Standard Concrete Urn Vault", "price": 350}, ...],
        },
        "urns": {
            "enabled": true,
            "items": [{"name": "Standard Concrete Urn", "price": 150}, ...],
        },
        "cemetery_equipment": {
            "enabled": true,
            "rental_items": [
                {"name": "Lowering Device", "price": 150, "rental_unit": "service"},
                {"name": "Cremation Table", "price": 125, "rental_unit": "service"},
                ...
            ],
            "sold_items": [
                {"name": "Burial Straps", "price": 45, "unit": "set"},
                ...
            ],
            "chairs": {"enabled": true, "price": 75, "chairs_per_set": 4},
            "create_cremation_substitution": true,
        },
        "markup_settings": {"two_piece_pct": 15, "oversize_pct": 20},
    }

    Returns: {"products_created": int, "substitution_rules_created": int}
    """
    products_created = 0
    created_products: dict[str, str] = {}  # name → product_id mapping

    try:
        # ── Burial Vaults ──
        bv = data.get("burial_vaults", {})
        if bv.get("enabled"):
            for line in bv.get("wilbert_lines", []):
                prefix = WILBERT_SKU_PREFIXES.get(line["name"], line["name"][:4].upper())
                for variant in line.get("variants", []):
                    name = f"{line['name']} {VARIANT_SUFFIXES.get(variant['variant'], variant['variant'])}"
                    sku = f"{prefix}-{variant['variant']}"
                    p = Product(
                        id=str(uuid.uuid4()),
                        company_id=tenant_id,
                        name=name,
                        sku=sku,
                        price=Decimal(str(variant["price"])),
                        unit_of_measure="each",
                        is_active=True,
                        pricing_type="sale",
                        source="catalog_builder",
                        is_inventory_tracked=True,
                        product_line=line["name"],
                        variant_type=variant["variant"],
                        created_by=user_id,
                    )
                    db.add(p)
                    products_created += 1

            for line in bv.get("own_lines", []):
                prefix = line.get("sku_prefix", line["name"][:4].upper())
                for variant in line.get("variants", []):
                    name = f"{line['name']} {VARIANT_SUFFIXES.get(variant['variant'], variant['variant'])}"
                    sku = f"{prefix}-{variant['variant']}"
                    p = Product(
                        id=str(uuid.uuid4()),
                        company_id=tenant_id,
                        name=name,
                        sku=sku,
                        price=Decimal(str(variant["price"])),
                        unit_of_measure="each",
                        is_active=True,
                        pricing_type="sale",
                        source="catalog_builder",
                        is_inventory_tracked=True,
                        product_line=line["name"],
                        variant_type=variant["variant"],
                        created_by=user_id,
                    )
                    db.add(p)
                    products_created += 1

        # ── Urn Vaults ──
        uv = data.get("urn_vaults", {})
        if uv.get("enabled"):
            for item in uv.get("items", []):
                p = Product(
                    id=str(uuid.uuid4()),
                    company_id=tenant_id,
                    name=item["name"],
                    sku=_generate_sku(item["name"]),
                    price=Decimal(str(item["price"])),
                    unit_of_measure="each",
                    pricing_type="sale",
                    source="catalog_builder",
                    is_inventory_tracked=True,
                    product_line="Urn Vaults",
                    created_by=user_id,
                )
                db.add(p)
                products_created += 1

        # ── Urns ──
        urns = data.get("urns", {})
        if urns.get("enabled"):
            for item in urns.get("items", []):
                p = Product(
                    id=str(uuid.uuid4()),
                    company_id=tenant_id,
                    name=item["name"],
                    sku=_generate_sku(item["name"]),
                    price=Decimal(str(item["price"])),
                    unit_of_measure="each",
                    pricing_type="sale",
                    source="catalog_builder",
                    is_inventory_tracked=False,  # urns typically resale
                    product_line="Urns",
                    created_by=user_id,
                )
                db.add(p)
                products_created += 1

        # ── Cemetery Equipment ──
        ce = data.get("cemetery_equipment", {})
        if ce.get("enabled"):
            lowering_device_id = None
            cremation_table_id = None

            for item in ce.get("rental_items", []):
                pid = str(uuid.uuid4())
                p = Product(
                    id=pid,
                    company_id=tenant_id,
                    name=item["name"],
                    sku=_generate_sku(item["name"]),
                    price=Decimal(str(item["price"])),
                    unit_of_measure=item.get("rental_unit", "service"),
                    pricing_type="rental",
                    rental_unit=item.get("rental_unit", "service"),
                    source="catalog_builder",
                    is_inventory_tracked=False,
                    product_line="Cemetery Equipment",
                    created_by=user_id,
                )
                db.add(p)
                products_created += 1

                if "lowering" in item["name"].lower():
                    lowering_device_id = pid
                if "cremation table" in item["name"].lower():
                    cremation_table_id = pid

            # Chairs
            chairs = ce.get("chairs", {})
            if chairs.get("enabled"):
                p = Product(
                    id=str(uuid.uuid4()),
                    company_id=tenant_id,
                    name=f"Graveside Chairs (set of {chairs.get('chairs_per_set', 4)})",
                    sku="CHAIR-SET",
                    price=Decimal(str(chairs["price"])),
                    unit_of_measure="set",
                    pricing_type="rental",
                    rental_unit="set",
                    default_quantity=chairs.get("chairs_per_set", 4),
                    source="catalog_builder",
                    is_inventory_tracked=False,
                    product_line="Cemetery Equipment",
                    created_by=user_id,
                )
                db.add(p)
                products_created += 1

            # Sold items
            for item in ce.get("sold_items", []):
                p = Product(
                    id=str(uuid.uuid4()),
                    company_id=tenant_id,
                    name=item["name"],
                    sku=_generate_sku(item["name"]),
                    price=Decimal(str(item["price"])),
                    unit_of_measure=item.get("unit", "each"),
                    pricing_type="sale",
                    source="catalog_builder",
                    is_inventory_tracked=False,
                    product_line="Cemetery Equipment",
                    created_by=user_id,
                )
                db.add(p)
                products_created += 1

            # Cremation table substitution rule
            sub_rules_created = 0
            if ce.get("create_cremation_substitution") and lowering_device_id and cremation_table_id:
                rule = ProductSubstitutionRule(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    rule_name="Cremation Table replaces Lowering Device for cremation orders",
                    trigger_field="disposition_type",
                    trigger_value="cremation",
                    substitute_out_product_id=lowering_device_id,
                    substitute_in_product_id=cremation_table_id,
                    applies_to="order_suggestions",
                    is_active=True,
                )
                db.add(rule)
                sub_rules_created = 1

        db.commit()
        return {
            "products_created": products_created,
            "substitution_rules_created": sub_rules_created if ce.get("enabled") else 0,
        }

    except Exception as e:
        db.rollback()
        logger.exception("Catalog builder failed")
        raise ValueError(f"Failed to create catalog: {str(e)}")


def get_existing_products(db: Session, tenant_id: str) -> list[dict]:
    """Get existing products created by catalog builder for detection on return visits."""
    products = (
        db.query(Product)
        .filter(
            Product.company_id == tenant_id,
            Product.source == "catalog_builder",
        )
        .all()
    )
    return [
        {
            "id": p.id,
            "name": p.name,
            "product_line": p.product_line,
            "variant_type": p.variant_type,
            "price": float(p.price) if p.price else None,
            "sku": p.sku,
            "pricing_type": p.pricing_type,
        }
        for p in products
    ]


def _generate_sku(name: str) -> str:
    """Generate a simple SKU from a product name."""
    words = name.upper().split()
    if len(words) >= 2:
        return f"{words[0][:3]}-{words[1][:3]}"
    return words[0][:6] if words else "PROD"
