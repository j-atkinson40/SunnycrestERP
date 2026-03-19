"""Product bundle service -- CRUD for equipment bundles."""

import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.models.product_bundle import ProductBundle, ProductBundleComponent
from app.models.product import Product

logger = logging.getLogger(__name__)


def list_bundles(db: Session, tenant_id: str, active_only: bool = True) -> list[dict]:
    """List all bundles for a tenant with their components."""
    q = db.query(ProductBundle).options(
        joinedload(ProductBundle.components).joinedload(ProductBundleComponent.product)
    ).filter(ProductBundle.company_id == tenant_id)
    if active_only:
        q = q.filter(ProductBundle.is_active == True)  # noqa: E712
    bundles = q.order_by(ProductBundle.sort_order, ProductBundle.name).all()
    return [_bundle_to_dict(b) for b in bundles]


def get_bundle(db: Session, tenant_id: str, bundle_id: str) -> dict | None:
    """Get a single bundle by ID."""
    b = db.query(ProductBundle).options(
        joinedload(ProductBundle.components).joinedload(ProductBundleComponent.product)
    ).filter(
        ProductBundle.id == bundle_id,
        ProductBundle.company_id == tenant_id,
    ).first()
    return _bundle_to_dict(b) if b else None


def create_bundle(db: Session, tenant_id: str, user_id: str, data: dict) -> dict:
    """Create a new product bundle with components."""
    if not data.get("components"):
        raise ValueError("At least one component is required")

    has_cond = data.get("has_conditional_pricing", False)
    standalone = Decimal(str(data["standalone_price"])) if data.get("standalone_price") is not None else None
    with_vault = Decimal(str(data["with_vault_price"])) if data.get("with_vault_price") is not None else None
    # When conditional pricing is on, bundle.price stores standalone_price for backward compat
    base_price = Decimal(str(data["price"])) if data.get("price") is not None else None
    if has_cond and standalone is not None:
        base_price = standalone

    bundle = ProductBundle(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        name=data["name"],
        description=data.get("description"),
        sku=data.get("sku"),
        price=base_price,
        is_active=data.get("is_active", True),
        sort_order=data.get("sort_order", 0),
        source=data.get("source", "manual"),
        has_conditional_pricing=has_cond,
        standalone_price=standalone,
        with_vault_price=with_vault,
        vault_qualifier_categories=(
            json.dumps(data["vault_qualifier_categories"])
            if data.get("vault_qualifier_categories")
            else '["burial_vault","urn_vault"]'
        ),
        created_by=user_id,
    )
    db.add(bundle)

    for i, comp in enumerate(data.get("components", [])):
        c = ProductBundleComponent(
            id=str(uuid.uuid4()),
            bundle_id=bundle.id,
            product_id=comp["product_id"],
            quantity=comp.get("quantity", 1),
            sort_order=i,
        )
        db.add(c)

    db.flush()
    db.refresh(bundle)
    # Re-query with joins to get full data
    return get_bundle(db, tenant_id, bundle.id)


def update_bundle(db: Session, tenant_id: str, user_id: str, bundle_id: str, data: dict) -> dict | None:
    """Update a bundle and optionally its components."""
    bundle = db.query(ProductBundle).filter(
        ProductBundle.id == bundle_id,
        ProductBundle.company_id == tenant_id,
    ).first()
    if not bundle:
        return None

    for field in ["name", "description", "sku", "is_active", "sort_order"]:
        if field in data:
            setattr(bundle, field, data[field])
    if "price" in data:
        bundle.price = Decimal(str(data["price"])) if data["price"] is not None else None

    # Conditional pricing
    if "has_conditional_pricing" in data:
        bundle.has_conditional_pricing = data["has_conditional_pricing"]
    if "standalone_price" in data:
        bundle.standalone_price = Decimal(str(data["standalone_price"])) if data["standalone_price"] is not None else None
    if "with_vault_price" in data:
        bundle.with_vault_price = Decimal(str(data["with_vault_price"])) if data["with_vault_price"] is not None else None
    if "vault_qualifier_categories" in data:
        bundle.vault_qualifier_categories = json.dumps(data["vault_qualifier_categories"]) if data["vault_qualifier_categories"] else '["burial_vault","urn_vault"]'
    # Sync bundle.price with standalone_price for backward compat
    if bundle.has_conditional_pricing and bundle.standalone_price is not None:
        bundle.price = bundle.standalone_price

    bundle.modified_by = user_id

    # Replace components if provided
    if "components" in data:
        # Delete existing components
        db.query(ProductBundleComponent).filter(
            ProductBundleComponent.bundle_id == bundle_id
        ).delete()
        for i, comp in enumerate(data["components"]):
            c = ProductBundleComponent(
                id=str(uuid.uuid4()),
                bundle_id=bundle.id,
                product_id=comp["product_id"],
                quantity=comp.get("quantity", 1),
                sort_order=i,
            )
            db.add(c)

    db.flush()
    return get_bundle(db, tenant_id, bundle.id)


def delete_bundle(db: Session, tenant_id: str, bundle_id: str) -> bool:
    """Soft-delete a bundle (set is_active=False)."""
    bundle = db.query(ProductBundle).filter(
        ProductBundle.id == bundle_id,
        ProductBundle.company_id == tenant_id,
    ).first()
    if not bundle:
        return False
    bundle.is_active = False
    db.flush()
    return True


def create_bundles_from_catalog_builder(
    db: Session,
    tenant_id: str,
    user_id: str,
    bundles_data: list[dict],
    product_id_map: dict[str, str],
) -> int:
    """Create bundles during catalog builder flow.

    bundles_data: [{"name": "Full Equipment", "price": 350, "component_names": ["Lowering Device", "Tent", ...]}]
    product_id_map: {"Lowering Device": "uuid-123", ...} -- maps product names to IDs
    """
    created = 0
    for bd in bundles_data:
        components = []
        for cname in bd.get("component_names", []):
            pid = product_id_map.get(cname)
            if pid:
                components.append({"product_id": pid, "quantity": 1})

        if not components:
            continue

        bundle = ProductBundle(
            id=str(uuid.uuid4()),
            company_id=tenant_id,
            name=bd["name"],
            description=bd.get("description"),
            sku=bd.get("sku"),
            price=Decimal(str(bd["price"])) if bd.get("price") is not None else None,
            is_active=True,
            sort_order=created,
            source="catalog_builder",
            created_by=user_id,
        )
        db.add(bundle)

        for i, comp in enumerate(components):
            c = ProductBundleComponent(
                id=str(uuid.uuid4()),
                bundle_id=bundle.id,
                product_id=comp["product_id"],
                quantity=comp.get("quantity", 1),
                sort_order=i,
            )
            db.add(c)
        created += 1

    return created


def _bundle_to_dict(b: ProductBundle) -> dict:
    """Serialize a bundle to a dict."""
    components = []
    component_total = Decimal("0")
    for c in b.components:
        prod = c.product
        item_price = prod.price if prod and prod.price else Decimal("0")
        components.append({
            "id": c.id,
            "product_id": c.product_id,
            "product_name": prod.name if prod else "Unknown",
            "product_sku": prod.sku if prod else None,
            "product_price": float(item_price),
            "quantity": c.quantity,
            "sort_order": c.sort_order,
        })
        component_total += item_price * c.quantity

    bundle_price = float(b.price) if b.price else None
    savings = float(component_total - b.price) if b.price and component_total > 0 else None

    return {
        "id": b.id,
        "company_id": b.company_id,
        "name": b.name,
        "description": b.description,
        "sku": b.sku,
        "price": bundle_price,
        "is_active": b.is_active,
        "sort_order": b.sort_order,
        "source": b.source,
        "components": components,
        "component_count": len(components),
        "a_la_carte_total": float(component_total),
        "savings": savings,
        # Conditional pricing
        "has_conditional_pricing": b.has_conditional_pricing,
        "standalone_price": float(b.standalone_price) if b.standalone_price is not None else None,
        "with_vault_price": float(b.with_vault_price) if b.with_vault_price is not None else None,
        "vault_qualifier_categories": b.vault_qualifier_list,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    }
