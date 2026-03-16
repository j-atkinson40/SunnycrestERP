"""Delivery type definitions — tenant-configurable delivery types."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.delivery_type_definition import DeliveryTypeDefinition
from app.models.user import User

router = APIRouter()


class DeliveryTypeCreate(BaseModel):
    key: str
    name: str
    color: str = "gray"
    icon: str | None = None
    description: str | None = None
    driver_instructions: str | None = None
    requires_signature: bool = False
    requires_photo: bool = False
    requires_weight_ticket: bool = False
    allows_partial: bool = False
    sort_order: int = 0


class DeliveryTypeUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    icon: str | None = None
    description: str | None = None
    driver_instructions: str | None = None
    requires_signature: bool | None = None
    requires_photo: bool | None = None
    requires_weight_ticket: bool | None = None
    allows_partial: bool | None = None
    sort_order: int | None = None
    is_active: bool | None = None


def _serialize(dt: DeliveryTypeDefinition) -> dict:
    return {
        "id": dt.id,
        "key": dt.key,
        "name": dt.name,
        "color": dt.color,
        "icon": dt.icon,
        "description": dt.description,
        "driver_instructions": dt.driver_instructions,
        "requires_signature": dt.requires_signature,
        "requires_photo": dt.requires_photo,
        "requires_weight_ticket": dt.requires_weight_ticket,
        "allows_partial": dt.allows_partial,
        "sort_order": dt.sort_order,
        "is_active": dt.is_active,
    }


@router.get("/")
def list_delivery_types(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all delivery types for the current tenant."""
    types = (
        db.query(DeliveryTypeDefinition)
        .filter(
            DeliveryTypeDefinition.company_id == current_user.company_id,
            DeliveryTypeDefinition.is_active.is_(True),
        )
        .order_by(DeliveryTypeDefinition.sort_order, DeliveryTypeDefinition.name)
        .all()
    )
    return [_serialize(t) for t in types]


@router.get("/all")
def list_all_delivery_types(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all delivery types including inactive (admin only)."""
    types = (
        db.query(DeliveryTypeDefinition)
        .filter(DeliveryTypeDefinition.company_id == current_user.company_id)
        .order_by(DeliveryTypeDefinition.sort_order, DeliveryTypeDefinition.name)
        .all()
    )
    return [_serialize(t) for t in types]


@router.post("/", status_code=201)
def create_delivery_type(
    data: DeliveryTypeCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new delivery type for the current tenant."""
    existing = (
        db.query(DeliveryTypeDefinition)
        .filter(
            DeliveryTypeDefinition.company_id == current_user.company_id,
            DeliveryTypeDefinition.key == data.key,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Delivery type '{data.key}' already exists")

    dt = DeliveryTypeDefinition(
        company_id=current_user.company_id,
        **data.model_dump(),
    )
    db.add(dt)
    db.commit()
    db.refresh(dt)
    return _serialize(dt)


@router.patch("/{type_id}")
def update_delivery_type(
    type_id: str,
    data: DeliveryTypeUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a delivery type."""
    dt = (
        db.query(DeliveryTypeDefinition)
        .filter(
            DeliveryTypeDefinition.id == type_id,
            DeliveryTypeDefinition.company_id == current_user.company_id,
        )
        .first()
    )
    if not dt:
        raise HTTPException(status_code=404, detail="Delivery type not found")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(dt, k, v)
    db.commit()
    db.refresh(dt)
    return _serialize(dt)


@router.delete("/{type_id}", status_code=204)
def delete_delivery_type(
    type_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Soft-delete a delivery type (set inactive)."""
    dt = (
        db.query(DeliveryTypeDefinition)
        .filter(
            DeliveryTypeDefinition.id == type_id,
            DeliveryTypeDefinition.company_id == current_user.company_id,
        )
        .first()
    )
    if not dt:
        raise HTTPException(status_code=404, detail="Delivery type not found")
    dt.is_active = False
    db.commit()
