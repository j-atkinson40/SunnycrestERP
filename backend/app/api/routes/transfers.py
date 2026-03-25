"""Licensee transfer API routes."""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.licensee_transfer import LicenseeTransfer
from app.models.user import User
from app.services.licensee_transfer_service import (
    accept_transfer,
    check_cemetery_in_territory,
    create_passthrough,
    create_transfer,
    decline_transfer,
    find_area_licensees,
    fulfill_transfer,
    get_transfers,
    record_off_platform_cost,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class TransferCreate(BaseModel):
    area_tenant_id: str | None = None
    area_licensee_name: str | None = None
    area_licensee_contact: str | None = None
    is_platform_transfer: bool = True
    source_order_id: str | None = None
    funeral_home_customer_id: str | None = None
    funeral_home_name: str | None = None
    deceased_name: str | None = None
    service_date: date | None = None
    cemetery_name: str | None = None
    cemetery_address: str | None = None
    cemetery_city: str | None = None
    cemetery_state: str | None = None
    cemetery_county: str | None = None
    cemetery_zip: str | None = None
    cemetery_place_id: str | None = None
    transfer_items: list[dict] = []
    special_instructions: str | None = None


class DeclineRequest(BaseModel):
    reason: str


class PassthroughRequest(BaseModel):
    markup_percentage: float = 0


class RecordCostRequest(BaseModel):
    amount: float
    reference_number: str | None = None
    notes: str | None = None


class CancelRequest(BaseModel):
    reason: str


@router.get("")
def list_transfers(
    direction: str = Query("all"),
    status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_transfers(db, current_user.company_id, direction, status)


@router.post("", status_code=201)
def create_new_transfer(
    body: TransferCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    transfer = create_transfer(db, current_user.company_id, body.model_dump(), current_user.id)
    return {"id": transfer.id, "transfer_number": transfer.transfer_number, "status": transfer.status}


@router.get("/find-licensees")
def find_licensees(
    state: str,
    county: str,
    zip: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return find_area_licensees(db, state, county, zip, current_user.company_id)


@router.get("/check-territory")
def check_territory(
    state: str,
    county: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    in_territory = check_cemetery_in_territory(db, current_user.company_id, state, county)
    return {"in_territory": in_territory}


@router.get("/{transfer_id}")
def get_transfer(
    transfer_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    transfer = db.query(LicenseeTransfer).filter(LicenseeTransfer.id == transfer_id).first()
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    if transfer.home_tenant_id != current_user.company_id and transfer.area_tenant_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return {
        "id": transfer.id,
        "transfer_number": transfer.transfer_number,
        "status": transfer.status,
        "is_platform_transfer": transfer.is_platform_transfer,
        "home_tenant_id": transfer.home_tenant_id,
        "area_tenant_id": transfer.area_tenant_id,
        "area_licensee_name": transfer.area_licensee_name,
        "funeral_home_name": transfer.funeral_home_name,
        "deceased_name": transfer.deceased_name,
        "service_date": str(transfer.service_date) if transfer.service_date else None,
        "cemetery_name": transfer.cemetery_name,
        "cemetery_city": transfer.cemetery_city,
        "cemetery_state": transfer.cemetery_state,
        "cemetery_county": transfer.cemetery_county,
        "transfer_items": transfer.transfer_items,
        "special_instructions": transfer.special_instructions,
        "area_charge_amount": float(transfer.area_charge_amount) if transfer.area_charge_amount else None,
        "markup_percentage": float(transfer.markup_percentage) if transfer.markup_percentage else 0,
        "passthrough_amount": float(transfer.passthrough_amount) if transfer.passthrough_amount else None,
        "area_order_id": transfer.area_order_id,
        "area_invoice_id": transfer.area_invoice_id,
        "home_vendor_bill_id": transfer.home_vendor_bill_id,
        "home_passthrough_invoice_id": transfer.home_passthrough_invoice_id,
        "requested_at": transfer.requested_at.isoformat() if transfer.requested_at else None,
        "accepted_at": transfer.accepted_at.isoformat() if transfer.accepted_at else None,
        "fulfilled_at": transfer.fulfilled_at.isoformat() if transfer.fulfilled_at else None,
        "decline_reason": transfer.decline_reason,
    }


@router.post("/{transfer_id}/accept")
def accept(
    transfer_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = accept_transfer(db, transfer_id, current_user.id)
    if not result:
        raise HTTPException(status_code=400, detail="Cannot accept this transfer")
    return {"status": result.status}


@router.post("/{transfer_id}/decline")
def decline(
    transfer_id: str,
    body: DeclineRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = decline_transfer(db, transfer_id, current_user.id, body.reason)
    if not result:
        raise HTTPException(status_code=400, detail="Cannot decline this transfer")
    return {"status": result.status}


@router.post("/{transfer_id}/fulfill")
def mark_fulfilled(
    transfer_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = fulfill_transfer(db, transfer_id, current_user.id)
    if not result:
        raise HTTPException(status_code=400, detail="Cannot fulfill this transfer")
    return {"status": result.status}


@router.post("/{transfer_id}/passthrough")
def create_passthrough_invoice(
    transfer_id: str,
    body: PassthroughRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = create_passthrough(db, transfer_id, body.markup_percentage, current_user.id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{transfer_id}/record-cost")
def record_cost(
    transfer_id: str,
    body: RecordCostRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = record_off_platform_cost(db, transfer_id, body.amount, body.reference_number, body.notes)
    if not result:
        raise HTTPException(status_code=404, detail="Transfer not found")
    return {"status": result.status}


@router.post("/{transfer_id}/cancel")
def cancel_transfer(
    transfer_id: str,
    body: CancelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    transfer = db.query(LicenseeTransfer).filter(LicenseeTransfer.id == transfer_id).first()
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    if transfer.status in ("fulfilled", "invoiced", "billed_through", "settled"):
        raise HTTPException(status_code=400, detail="Cannot cancel a transfer in this status")
    transfer.status = "cancelled"
    transfer.cancelled_by = current_user.id
    transfer.cancelled_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    transfer.cancellation_reason = body.reason
    db.commit()
    return {"status": "cancelled"}
