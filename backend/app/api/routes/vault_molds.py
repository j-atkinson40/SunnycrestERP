"""Vault mold configuration API routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.production_mold_config_service import (
    get_daily_capacity_summary,
    get_mold_configs,
    upsert_mold_configs,
    validate_production_entry,
)

router = APIRouter()


# ── Pydantic schemas ─────────────────────────────────────────────────────────


class MoldConfigItem(BaseModel):
    product_id: str
    daily_capacity: int = 1
    is_active: bool = True
    notes: str | None = None


class AssembleRequest(BaseModel):
    quantity: int


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("")
def list_mold_configs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all vault mold configs for the tenant with product and stock data."""
    return get_mold_configs(db, current_user.company_id)


@router.post("", status_code=status.HTTP_201_CREATED)
def batch_upsert_mold_configs(
    configs: list[MoldConfigItem],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Batch upsert mold configs (used by onboarding save)."""
    results = upsert_mold_configs(
        db,
        current_user.company_id,
        [c.model_dump() for c in configs],
    )

    # Fire onboarding hook
    try:
        from app.services.onboarding_hooks import on_vault_mold_config_setup

        on_vault_mold_config_setup(db, current_user.company_id)
    except Exception:
        pass

    return {"count": len(results)}


@router.patch("/{product_id}")
def update_single_mold_config(
    product_id: str,
    body: MoldConfigItem,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a single mold config by product ID."""
    results = upsert_mold_configs(
        db,
        current_user.company_id,
        [body.model_dump()],
    )
    if not results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    return {"updated": True}


@router.get("/capacity-summary")
def get_capacity_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return daily capacity per product for the production log UI."""
    return get_daily_capacity_summary(db, current_user.company_id)


@router.post("/validate")
def validate_entries(
    entries: list[dict],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Validate production entries against mold capacity."""
    return validate_production_entry(db, current_user.company_id, entries)


# ── Spare component assembly ─────────────────────────────────────────────────


@router.post("/assemble/{product_id}")
def assemble_components(
    product_id: str,
    body: AssembleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Assemble spare covers + bases into complete vaults."""
    from app.models.inventory_item import InventoryItem
    from app.models.inventory_transaction import InventoryTransaction

    inv = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.company_id == current_user.company_id,
            InventoryItem.product_id == product_id,
        )
        .first()
    )
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No inventory record for this product",
        )

    covers = inv.spare_covers or 0
    bases = inv.spare_bases or 0

    if covers < body.quantity or bases < body.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient spare components: {covers} covers, {bases} bases available",
        )

    inv.spare_covers = covers - body.quantity
    inv.spare_bases = bases - body.quantity
    inv.quantity_on_hand = (inv.quantity_on_hand or 0) + body.quantity
    inv.updated_at = datetime.now(timezone.utc)

    tx = InventoryTransaction(
        company_id=current_user.company_id,
        product_id=product_id,
        transaction_type="assemble",
        quantity_change=body.quantity,
        quantity_after=inv.quantity_on_hand,
        reference=f"Assembled {body.quantity} vault(s) from spare components",
        created_by=current_user.id,
    )
    db.add(tx)
    db.commit()

    return {
        "assembled": body.quantity,
        "quantity_on_hand": inv.quantity_on_hand,
        "spare_covers": inv.spare_covers,
        "spare_bases": inv.spare_bases,
    }
