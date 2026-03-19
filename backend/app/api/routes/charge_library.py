"""Charge Library routes — manage fee/surcharge templates for a tenant."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.company_resolver import get_current_company
from app.api.deps import get_current_user
from app.database import get_db
from app.models.company import Company
from app.models.user import User
from app.schemas.charge_library import (
    ChargeLibraryBulkSaveRequest,
    ChargeLibraryItemCreate,
    ChargeLibraryItemResponse,
)
from app.services import charge_library_service

router = APIRouter()


@router.get("/charges", response_model=list[ChargeLibraryItemResponse])
def list_charges(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """List all charges for the current tenant."""
    items = charge_library_service.list_charges(db, company.id)
    # Parse zone_config JSON for response
    return [_to_response(item) for item in items]


@router.post("/charges/seed", response_model=list[ChargeLibraryItemResponse])
def seed_charges(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Seed default charges for the tenant (called during onboarding init)."""
    created = charge_library_service.seed_default_charges(db, company.id)
    db.commit()
    # Return the full list (seeded + any pre-existing)
    items = charge_library_service.list_charges(db, company.id)
    return [_to_response(item) for item in items]


@router.put("/charges/bulk", response_model=list[ChargeLibraryItemResponse])
def bulk_save_charges(
    data: ChargeLibraryBulkSaveRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Bulk save all charge configurations."""
    charges_data = [c.model_dump() for c in data.charges]
    charge_library_service.bulk_save_charges(db, company.id, charges_data)
    db.commit()
    items = charge_library_service.list_charges(db, company.id)
    return [_to_response(item) for item in items]


@router.post("/charges/custom", response_model=ChargeLibraryItemResponse, status_code=201)
def create_custom_charge(
    data: ChargeLibraryItemCreate,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Create a custom charge library item."""
    try:
        item = charge_library_service.create_custom_charge(
            db, company.id, **data.model_dump()
        )
        db.commit()
        db.refresh(item)
        return _to_response(item)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/charges/enabled", response_model=list[ChargeLibraryItemResponse])
def get_enabled_charges(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get only enabled charges — used by order forms to suggest charges."""
    items = charge_library_service.get_enabled_charges(db, company.id)
    return [_to_response(item) for item in items]


def _to_response(item) -> dict:
    """Convert a ChargeLibraryItem ORM instance to a response-friendly dict."""
    return {
        "id": item.id,
        "charge_key": item.charge_key,
        "charge_name": item.charge_name,
        "category": item.category,
        "description": item.description,
        "is_enabled": item.is_enabled,
        "is_system": item.is_system,
        "pricing_type": item.pricing_type,
        "fixed_amount": float(item.fixed_amount) if item.fixed_amount is not None else None,
        "per_mile_rate": float(item.per_mile_rate) if item.per_mile_rate is not None else None,
        "free_radius_miles": float(item.free_radius_miles) if item.free_radius_miles is not None else None,
        "zone_config": item.zone_config_parsed,
        "guidance_min": float(item.guidance_min) if item.guidance_min is not None else None,
        "guidance_max": float(item.guidance_max) if item.guidance_max is not None else None,
        "variable_placeholder": item.variable_placeholder,
        "auto_suggest": item.auto_suggest,
        "auto_suggest_trigger": item.auto_suggest_trigger,
        "invoice_label": item.invoice_label,
        "sort_order": item.sort_order,
        "notes": item.notes,
    }
