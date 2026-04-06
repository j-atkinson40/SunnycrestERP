"""Billing Groups — multi-location funeral home group billing."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.company_entity import CompanyEntity
from app.models.customer import Customer
from app.models.user import User
from app.services.crm import billing_group_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreateGroupBody(BaseModel):
    name: str
    billing_preference: str = "separate"
    location_company_entity_ids: list[str]
    billing_contact_customer_id: str | None = None


class UpdateGroupBody(BaseModel):
    name: str | None = None
    billing_preference: str | None = None


class AddLocationBody(BaseModel):
    company_entity_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
def list_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all billing groups for the tenant."""
    return billing_group_service.get_groups(db, current_user.company_id)


@router.post("", status_code=201)
def create_group(
    data: CreateGroupBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new billing group."""
    if len(data.location_company_entity_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 locations required")

    if data.billing_preference not in ("separate", "consolidated_single_payer", "consolidated_split_payment"):
        raise HTTPException(status_code=400, detail="Invalid billing preference")

    group = billing_group_service.create_group(
        db=db,
        tenant_id=current_user.company_id,
        group_name=data.name,
        billing_preference=data.billing_preference,
        location_company_entity_ids=data.location_company_entity_ids,
        billing_contact_customer_id=data.billing_contact_customer_id,
    )
    return billing_group_service.get_group_summary(db, current_user.company_id, group.id)


@router.get("/ungrouped-locations")
def list_ungrouped_locations(
    search: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List funeral home company entities not in any billing group."""
    query = db.query(CompanyEntity).filter(
        CompanyEntity.company_id == current_user.company_id,
        CompanyEntity.is_active == True,
        CompanyEntity.parent_company_id.is_(None),
        CompanyEntity.is_billing_group == False,
        CompanyEntity.is_funeral_home == True,
    )
    if search:
        query = query.filter(CompanyEntity.name.ilike(f"%{search}%"))

    locations = query.order_by(CompanyEntity.name).limit(50).all()

    result = []
    for loc in locations:
        customer = db.query(Customer).filter(
            Customer.master_company_id == loc.id,
            Customer.company_id == current_user.company_id,
        ).first()
        result.append({
            "company_entity_id": loc.id,
            "name": loc.name,
            "city": loc.city,
            "state": loc.state,
            "customer_id": customer.id if customer else None,
        })
    return result


@router.get("/for-customer/{customer_id}")
def get_group_for_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the billing group a customer belongs to, if any."""
    result = billing_group_service.get_group_for_customer(db, customer_id)
    if not result:
        return {"group": None}
    return {"group": result}


@router.get("/{group_id}")
def get_group(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a billing group with full location details."""
    summary = billing_group_service.get_group_summary(db, current_user.company_id, group_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Billing group not found")
    return summary


@router.patch("/{group_id}")
def update_group(
    group_id: str,
    data: UpdateGroupBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a billing group's name or billing preference."""
    if data.billing_preference and data.billing_preference not in (
        "separate", "consolidated_single_payer", "consolidated_split_payment"
    ):
        raise HTTPException(status_code=400, detail="Invalid billing preference")

    group = billing_group_service.update_group(
        db=db,
        tenant_id=current_user.company_id,
        group_id=group_id,
        name=data.name,
        billing_preference=data.billing_preference,
    )
    if not group:
        raise HTTPException(status_code=404, detail="Billing group not found")

    return billing_group_service.get_group_summary(db, current_user.company_id, group_id)


@router.post("/{group_id}/locations")
def add_location(
    group_id: str,
    data: AddLocationBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a location to a billing group."""
    ok = billing_group_service.add_location(
        db, current_user.company_id, group_id, data.company_entity_id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Group or location not found")
    return billing_group_service.get_group_summary(db, current_user.company_id, group_id)


@router.delete("/{group_id}/locations/{location_ce_id}")
def remove_location(
    group_id: str,
    location_ce_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a location from a billing group."""
    ok = billing_group_service.unlink_location(db, current_user.company_id, location_ce_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Location not found or not in a group")
    return billing_group_service.get_group_summary(db, current_user.company_id, group_id)


@router.delete("/{group_id}")
def delete_group(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a billing group. All locations revert to independent billing."""
    ok = billing_group_service.delete_group(db, current_user.company_id, group_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Billing group not found")
    return {"detail": "Billing group deleted"}
