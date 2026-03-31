"""Vault supplier configuration API."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Company, User, VaultSupplier

router = APIRouter()


class VaultSupplierCreate(BaseModel):
    vendor_id: str
    order_quantity: int
    lead_time_days: int = 3
    delivery_schedule: str = "on_demand"
    delivery_days: list[str] = []
    is_primary: bool = True
    notes: str | None = None


class VaultSupplierUpdate(BaseModel):
    order_quantity: int | None = None
    lead_time_days: int | None = None
    delivery_schedule: str | None = None
    delivery_days: list[str] | None = None
    is_primary: bool | None = None
    notes: str | None = None


@router.get("/")
def list_vault_suppliers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List active vault suppliers for the current tenant."""
    suppliers = db.query(VaultSupplier).filter(
        VaultSupplier.company_id == current_user.company_id,
        VaultSupplier.is_active == True,
    ).all()
    return suppliers


@router.post("/")
def create_vault_supplier(
    data: VaultSupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new vault supplier configuration."""
    supplier = VaultSupplier(
        id=str(uuid.uuid4()),
        company_id=current_user.company_id,
        **data.model_dump(),
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.patch("/{supplier_id}")
def update_vault_supplier(
    supplier_id: str,
    data: VaultSupplierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a vault supplier configuration."""
    supplier = db.query(VaultSupplier).filter(
        VaultSupplier.id == supplier_id,
        VaultSupplier.company_id == current_user.company_id,
    ).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(supplier, k, v)
    supplier.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.delete("/{supplier_id}")
def delete_vault_supplier(
    supplier_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a vault supplier."""
    supplier = db.query(VaultSupplier).filter(
        VaultSupplier.id == supplier_id,
        VaultSupplier.company_id == current_user.company_id,
    ).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    supplier.is_active = False
    db.commit()
    return {"message": "Supplier removed"}


@router.get("/inventory-status")
def get_vault_inventory_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current vault inventory status with projections for all products."""
    from app.models import InventoryItem, Product
    from app.services.vault_inventory_service import build_suggested_order, check_reorder_needed

    company_id = current_user.company_id

    products = db.query(Product).filter(
        Product.company_id == company_id,
        Product.is_active == True,
    ).all()

    items = []
    for product in products:
        inv = db.query(InventoryItem).filter(
            InventoryItem.company_id == company_id,
            InventoryItem.product_id == product.id,
        ).first()
        if not inv:
            continue
        check = check_reorder_needed(db, company_id, product.id)
        items.append({
            "product_id": product.id,
            "product_name": product.name,
            "quantity_on_hand": int(inv.quantity_on_hand or 0),
            "reorder_point": int(inv.reorder_point or 0),
            "reorder_status": (
                "critical" if int(inv.quantity_on_hand or 0) <= int(inv.reorder_point or 0)
                else "low" if int(inv.quantity_on_hand or 0) <= int(inv.reorder_point or 0) * 2
                else "good"
            ),
            "needs_reorder": check.get("needs_reorder", False) if check else False,
            "urgent": check.get("urgent", False) if check else False,
            "next_delivery": check.get("next_delivery") if check else None,
            "order_deadline": check.get("order_deadline") if check else None,
        })

    suggestion = build_suggested_order(db, company_id)

    return {
        "products": items,
        "suggestion": suggestion,
    }


@router.patch("/fulfillment-mode")
def update_fulfillment_mode(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the company's vault fulfillment mode."""
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    mode = data.get("vault_fulfillment_mode")
    if mode not in ("produce", "purchase", "hybrid"):
        raise HTTPException(status_code=400, detail="Invalid mode")
    company.vault_fulfillment_mode = mode
    db.commit()
    return {"vault_fulfillment_mode": mode}
