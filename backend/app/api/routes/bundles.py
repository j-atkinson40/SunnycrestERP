"""Product bundle routes -- CRUD for equipment bundles."""

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
