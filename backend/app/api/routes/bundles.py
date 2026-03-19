"""Product bundle routes -- CRUD for equipment bundles."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.company_resolver import get_current_company
from app.api.deps import get_current_user
from app.database import get_db
from app.models.company import Company
from app.models.user import User
from app.models.tenant_equipment_item import TenantEquipmentItem
from app.services import bundle_service

logger = logging.getLogger(__name__)
router = APIRouter()


class TenantEquipmentItemCreate(BaseModel):
    name: str
    pricing_type: str = "rental"


class BundleComponentInput(BaseModel):
    product_id: str
    quantity: int = 1


class BundleCreate(BaseModel):
    name: str
    description: str | None = None
    sku: str | None = None
    price: float | None = None
    is_active: bool = True
    sort_order: int = 0
    components: list[BundleComponentInput] = []
    # Conditional pricing
    has_conditional_pricing: bool = False
    standalone_price: float | None = None
    with_vault_price: float | None = None
    vault_qualifier_categories: list[str] | None = None


class BundleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    sku: str | None = None
    price: float | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    components: list[BundleComponentInput] | None = None
    # Conditional pricing
    has_conditional_pricing: bool | None = None
    standalone_price: float | None = None
    with_vault_price: float | None = None
    vault_qualifier_categories: list[str] | None = None


@router.get("/equipment-items")
def list_equipment_items(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """List custom equipment items for this tenant."""
    items = (
        db.query(TenantEquipmentItem)
        .filter(TenantEquipmentItem.company_id == company.id, TenantEquipmentItem.is_active == True)  # noqa: E712
        .order_by(TenantEquipmentItem.name)
        .all()
    )
    return [{"id": i.id, "name": i.name, "pricing_type": i.pricing_type} for i in items]


@router.post("/equipment-items", status_code=201)
def create_equipment_item(
    data: TenantEquipmentItemCreate,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Create a custom equipment item for this tenant."""
    import uuid as _uuid
    existing = db.query(TenantEquipmentItem).filter(
        TenantEquipmentItem.company_id == company.id,
        TenantEquipmentItem.name == data.name.strip(),
    ).first()
    if existing:
        return {"id": existing.id, "name": existing.name, "pricing_type": existing.pricing_type}

    item = TenantEquipmentItem(
        id=str(_uuid.uuid4()),
        company_id=company.id,
        name=data.name.strip(),
        pricing_type=data.pricing_type,
        created_by=current_user.id,
    )
    db.add(item)
    db.commit()
    return {"id": item.id, "name": item.name, "pricing_type": item.pricing_type}


@router.get("/bundles")
def list_bundles(
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """List all product bundles for the tenant."""
    return bundle_service.list_bundles(db, company.id, active_only)


@router.get("/bundles/{bundle_id}")
def get_bundle(
    bundle_id: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get a single bundle with its components."""
    result = bundle_service.get_bundle(db, company.id, bundle_id)
    if not result:
        raise HTTPException(status_code=404, detail="Bundle not found")
    return result


@router.post("/bundles", status_code=201)
def create_bundle(
    data: BundleCreate,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Create a new product bundle."""
    result = bundle_service.create_bundle(
        db, company.id, current_user.id,
        data.model_dump(),
    )
    db.commit()
    return result


@router.patch("/bundles/{bundle_id}")
def update_bundle(
    bundle_id: str,
    data: BundleUpdate,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update a product bundle."""
    result = bundle_service.update_bundle(
        db, company.id, current_user.id, bundle_id,
        data.model_dump(exclude_none=True),
    )
    if not result:
        raise HTTPException(status_code=404, detail="Bundle not found")
    db.commit()
    return result


@router.delete("/bundles/{bundle_id}")
def delete_bundle(
    bundle_id: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Soft-delete a product bundle."""
    success = bundle_service.delete_bundle(db, company.id, bundle_id)
    if not success:
        raise HTTPException(status_code=404, detail="Bundle not found")
    db.commit()
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Bundle price resolution — for order forms & quick order templates
# ---------------------------------------------------------------------------


class ResolvePriceLineItem(BaseModel):
    product_id: str | None = None
    product_name: str | None = None
    bundle_id: str | None = None


class ResolvePricesRequest(BaseModel):
    line_items: list[ResolvePriceLineItem]


class ResolvedBundlePrice(BaseModel):
    bundle_id: str
    bundle_name: str
    price: float
    tier: str  # "with_vault" | "standalone"
    qualifying_product: str | None = None
    with_vault_price: float | None = None
    standalone_price: float | None = None
    has_conditional_pricing: bool = False


@router.post("/bundles/resolve-prices")
def resolve_bundle_prices(
    data: ResolvePricesRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Resolve conditional bundle prices based on order line item composition.

    Given a list of line items (from a template or order form), determines
    the correct price tier for each bundle item by checking whether any
    vault products are present in the order.

    Returns a list of resolved bundle prices.
    """
    from app.models.product import Product
    from app.models.product_bundle import ProductBundle
    from app.models.product_category import ProductCategory

    # Collect all product_ids from line items
    product_ids = [
        li.product_id for li in data.line_items if li.product_id
    ]

    if not product_ids:
        return []

    # Load products with categories to determine which are vaults
    products = (
        db.query(Product)
        .filter(Product.id.in_(product_ids), Product.company_id == company.id)
        .all()
    )
    product_map = {p.id: p for p in products}

    # Build category name lookup
    cat_ids = [p.category_id for p in products if p.category_id]
    categories = {}
    if cat_ids:
        cats = db.query(ProductCategory).filter(ProductCategory.id.in_(cat_ids)).all()
        categories = {c.id: c.name for c in cats}

    # Determine which product_ids are vaults (category name → slug match)
    def _slugify_cat(name: str) -> str:
        return name.lower().replace(" ", "_").replace("-", "_")

    product_categories: dict[str, str] = {}
    for pid, prod in product_map.items():
        if prod.category_id and prod.category_id in categories:
            product_categories[pid] = _slugify_cat(categories[prod.category_id])

    # Find bundles among line items (by bundle_id or by product_id matching a bundle)
    explicit_bundle_ids = [
        li.bundle_id for li in data.line_items if li.bundle_id
    ]

    # Also check if any product_ids are actually bundles (template line items
    # might reference bundles by product_id)
    all_bundles = (
        db.query(ProductBundle)
        .filter(
            ProductBundle.company_id == company.id,
            ProductBundle.is_active.is_(True),
        )
        .all()
    )
    bundle_map = {b.id: b for b in all_bundles}

    # Check product_ids that might match bundle IDs
    for li in data.line_items:
        if li.product_id and li.product_id in bundle_map:
            if li.product_id not in explicit_bundle_ids:
                explicit_bundle_ids.append(li.product_id)

    # Also match by name
    bundle_name_map = {b.name.lower(): b for b in all_bundles}
    for li in data.line_items:
        if li.product_name:
            matched = bundle_name_map.get(li.product_name.lower())
            if matched and matched.id not in explicit_bundle_ids:
                explicit_bundle_ids.append(matched.id)

    if not explicit_bundle_ids:
        return []

    # Resolve prices for each bundle
    results = []
    for bid in explicit_bundle_ids:
        bundle = bundle_map.get(bid)
        if not bundle:
            continue

        resolved = ResolvedBundlePrice(
            bundle_id=bundle.id,
            bundle_name=bundle.name,
            price=float(bundle.price or 0),
            tier="standalone",
            has_conditional_pricing=bundle.has_conditional_pricing,
            with_vault_price=float(bundle.with_vault_price) if bundle.with_vault_price else None,
            standalone_price=float(bundle.standalone_price) if bundle.standalone_price else None,
        )

        if not bundle.has_conditional_pricing:
            results.append(resolved)
            continue

        # Check if any non-bundle line item qualifies for vault pricing
        qualifier_cats = bundle.vault_qualifier_list
        qualifying_product = None

        for li in data.line_items:
            pid = li.product_id
            if not pid or pid == bundle.id:
                continue
            cat_slug = product_categories.get(pid, "")
            if cat_slug in qualifier_cats:
                qualifying_product = li.product_name or product_map.get(pid, None)
                if qualifying_product and not isinstance(qualifying_product, str):
                    qualifying_product = qualifying_product.name
                break

        if qualifying_product:
            resolved.price = float(bundle.with_vault_price or 0)
            resolved.tier = "with_vault"
            resolved.qualifying_product = qualifying_product
        else:
            resolved.price = float(bundle.standalone_price or 0)
            resolved.tier = "standalone"

        results.append(resolved)

    return results
