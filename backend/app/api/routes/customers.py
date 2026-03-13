from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_module, require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.customer import (
    BalanceAdjustmentCreate,
    BalanceAdjustmentResponse,
    CustomerContactCreate,
    CustomerContactResponse,
    CustomerContactUpdate,
    CustomerCreate,
    CustomerListItem,
    CustomerNoteCreate,
    CustomerNoteResponse,
    CustomerResponse,
    CustomerStats,
    CustomerUpdate,
    PaginatedBalanceAdjustments,
    PaginatedCustomers,
)
from app.services import customer_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _note_to_response(note) -> dict:
    data = CustomerNoteResponse.model_validate(note).model_dump()
    if note.author:
        data["created_by_name"] = f"{note.author.first_name or ''} {note.author.last_name or ''}".strip() or note.author.email
    else:
        data["created_by_name"] = None
    return data


def _adjustment_to_response(adj) -> dict:
    data = BalanceAdjustmentResponse.model_validate(adj).model_dump()
    if adj.author:
        data["created_by_name"] = f"{adj.author.first_name or ''} {adj.author.last_name or ''}".strip() or adj.author.email
    else:
        data["created_by_name"] = None
    return data


def _customer_to_response(customer) -> dict:
    data = CustomerResponse.model_validate(customer).model_dump()
    data["contacts"] = [
        CustomerContactResponse.model_validate(c).model_dump()
        for c in (customer.contacts or [])
    ]
    data["recent_notes"] = [
        _note_to_response(n) for n in (customer.customer_notes or [])[:10]
    ]
    return data


# ---------------------------------------------------------------------------
# Customer endpoints
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=CustomerStats)
def customer_stats(
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.view")),
):
    return customer_service.get_customer_stats(db, current_user.company_id)


@router.get("", response_model=PaginatedCustomers)
def list_customers(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    account_status: str | None = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.view")),
):
    result = customer_service.get_customers(
        db,
        current_user.company_id,
        page,
        per_page,
        search,
        account_status,
        include_inactive,
    )
    return {
        "items": [
            CustomerListItem.model_validate(c).model_dump()
            for c in result["items"]
        ],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.post("", status_code=201)
def create_customer(
    data: CustomerCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.create")),
):
    customer = customer_service.create_customer(
        db, data, current_user.company_id, actor_id=current_user.id
    )
    db.refresh(customer)
    return _customer_to_response(customer)


@router.get("/{customer_id}")
def read_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.view")),
):
    customer = customer_service.get_customer(
        db, customer_id, current_user.company_id
    )
    return _customer_to_response(customer)


@router.patch("/{customer_id}")
def update_customer(
    customer_id: str,
    data: CustomerUpdate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.edit")),
):
    customer = customer_service.update_customer(
        db, customer_id, data, current_user.company_id, actor_id=current_user.id
    )
    db.refresh(customer)
    return _customer_to_response(customer)


@router.delete("/{customer_id}")
def delete_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.delete")),
):
    customer_service.deactivate_customer(
        db, customer_id, current_user.company_id, actor_id=current_user.id
    )
    return {"detail": "Customer deactivated"}


# ---------------------------------------------------------------------------
# Contact endpoints
# ---------------------------------------------------------------------------


@router.get("/{customer_id}/contacts", response_model=list[CustomerContactResponse])
def list_contacts(
    customer_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.view")),
):
    contacts = customer_service.get_customer_contacts(
        db, customer_id, current_user.company_id
    )
    return [CustomerContactResponse.model_validate(c).model_dump() for c in contacts]


@router.post("/{customer_id}/contacts", status_code=201)
def create_contact(
    customer_id: str,
    data: CustomerContactCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.edit")),
):
    contact = customer_service.create_customer_contact(
        db, customer_id, data, current_user.company_id
    )
    return CustomerContactResponse.model_validate(contact).model_dump()


@router.patch("/{customer_id}/contacts/{contact_id}")
def update_contact(
    customer_id: str,
    contact_id: str,
    data: CustomerContactUpdate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.edit")),
):
    contact = customer_service.update_customer_contact(
        db, contact_id, data, current_user.company_id
    )
    return CustomerContactResponse.model_validate(contact).model_dump()


@router.delete("/{customer_id}/contacts/{contact_id}")
def delete_contact(
    customer_id: str,
    contact_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.edit")),
):
    customer_service.delete_customer_contact(
        db, contact_id, current_user.company_id
    )
    return {"detail": "Contact deleted"}


# ---------------------------------------------------------------------------
# Note endpoints
# ---------------------------------------------------------------------------


@router.get("/{customer_id}/notes")
def list_notes(
    customer_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.view")),
):
    result = customer_service.get_customer_notes(
        db, customer_id, current_user.company_id, page, per_page
    )
    return {
        "items": [_note_to_response(n) for n in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.post("/{customer_id}/notes", status_code=201)
def create_note(
    customer_id: str,
    data: CustomerNoteCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.edit")),
):
    note = customer_service.create_customer_note(
        db, customer_id, data, current_user.company_id, actor_id=current_user.id
    )
    return _note_to_response(note)


# ---------------------------------------------------------------------------
# Credit check
# ---------------------------------------------------------------------------


@router.get("/{customer_id}/credit-check")
def credit_check(
    customer_id: str,
    amount: Decimal = Query(..., gt=0),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.view")),
):
    return customer_service.check_credit_limit(
        db, customer_id, current_user.company_id, amount
    )


# ---------------------------------------------------------------------------
# Balance Adjustment endpoints
# ---------------------------------------------------------------------------


@router.get("/{customer_id}/adjustments", response_model=PaginatedBalanceAdjustments)
def list_adjustments(
    customer_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.view")),
):
    result = customer_service.get_balance_adjustments(
        db, customer_id, current_user.company_id, page, per_page
    )
    return {
        "items": [_adjustment_to_response(a) for a in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.post("/{customer_id}/adjustments", status_code=201)
def create_adjustment(
    customer_id: str,
    data: BalanceAdjustmentCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.edit")),
):
    adjustment = customer_service.create_balance_adjustment(
        db, customer_id, current_user.company_id, current_user.id, data
    )
    return _adjustment_to_response(adjustment)
