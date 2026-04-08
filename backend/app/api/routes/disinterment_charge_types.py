"""CRUD endpoints for disinterment charge types."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_extension, require_permission
from app.models.user import User
from app.schemas.disinterment import (
    ChargeTypeCreate,
    ChargeTypeResponse,
    ChargeTypeUpdate,
)
from app.services import disinterment_charge_type_service as svc

router = APIRouter()


@router.get("")
def list_charge_types(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    _mod: User = Depends(require_extension("disinterment_management")),
    current_user: User = Depends(require_permission("disinterments.view")),
):
    """List all charge types for the tenant."""
    items = svc.list_charge_types(db, current_user.company_id, include_inactive)
    return [ChargeTypeResponse.model_validate(ct) for ct in items]


@router.post("", status_code=201)
def create_charge_type(
    data: ChargeTypeCreate,
    db: Session = Depends(get_db),
    _mod: User = Depends(require_extension("disinterment_management")),
    current_user: User = Depends(require_permission("disinterment_settings.manage")),
):
    """Create a new charge type."""
    ct = svc.create_charge_type(db, current_user.company_id, data)
    return ChargeTypeResponse.model_validate(ct)


@router.patch("/{charge_type_id}")
def update_charge_type(
    charge_type_id: str,
    data: ChargeTypeUpdate,
    db: Session = Depends(get_db),
    _mod: User = Depends(require_extension("disinterment_management")),
    current_user: User = Depends(require_permission("disinterment_settings.manage")),
):
    """Update a charge type."""
    ct = svc.update_charge_type(db, charge_type_id, current_user.company_id, data)
    return ChargeTypeResponse.model_validate(ct)


@router.delete("/{charge_type_id}", status_code=204)
def delete_charge_type(
    charge_type_id: str,
    db: Session = Depends(get_db),
    _mod: User = Depends(require_extension("disinterment_management")),
    current_user: User = Depends(require_permission("disinterment_settings.manage")),
):
    """Soft-delete a charge type."""
    svc.soft_delete_charge_type(db, charge_type_id, current_user.company_id)
