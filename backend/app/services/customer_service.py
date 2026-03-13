from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.customer_contact import CustomerContact
from app.models.customer_note import CustomerNote
from app.schemas.customer import (
    CustomerContactCreate,
    CustomerContactUpdate,
    CustomerCreate,
    CustomerNoteCreate,
    CustomerUpdate,
)
from app.services import audit_service


# ---------------------------------------------------------------------------
# Customer CRUD
# ---------------------------------------------------------------------------


def get_customers(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
    account_status: str | None = None,
    include_inactive: bool = False,
) -> dict:
    query = db.query(Customer).filter(Customer.company_id == company_id)

    if not include_inactive:
        query = query.filter(Customer.is_active == True)  # noqa: E712

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Customer.name.ilike(pattern),
                Customer.account_number.ilike(pattern),
                Customer.email.ilike(pattern),
                Customer.contact_name.ilike(pattern),
            )
        )

    if account_status:
        query = query.filter(Customer.account_status == account_status)

    total = query.count()
    customers = (
        query.order_by(Customer.name)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": customers, "total": total, "page": page, "per_page": per_page}


def get_customer(db: Session, customer_id: str, company_id: str) -> Customer:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.company_id == company_id)
        .first()
    )
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        )
    return customer


def create_customer(
    db: Session,
    data: CustomerCreate,
    company_id: str,
    actor_id: str | None = None,
) -> Customer:
    # Check account_number uniqueness if provided
    if data.account_number:
        existing = (
            db.query(Customer)
            .filter(
                Customer.account_number == data.account_number,
                Customer.company_id == company_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A customer with this account number already exists",
            )

    customer = Customer(
        company_id=company_id,
        created_by=actor_id,
        **data.model_dump(),
    )
    db.add(customer)
    db.flush()

    audit_service.log_action(
        db,
        company_id,
        "created",
        "customer",
        customer.id,
        user_id=actor_id,
        changes={"name": data.name, "account_number": data.account_number},
    )

    db.commit()
    db.refresh(customer)
    return customer


def update_customer(
    db: Session,
    customer_id: str,
    data: CustomerUpdate,
    company_id: str,
    actor_id: str | None = None,
) -> Customer:
    customer = get_customer(db, customer_id, company_id)

    old_data = {
        "name": customer.name,
        "account_number": customer.account_number,
        "email": customer.email,
        "phone": customer.phone,
        "account_status": customer.account_status,
        "credit_limit": str(customer.credit_limit) if customer.credit_limit is not None else None,
        "payment_terms": customer.payment_terms,
        "is_active": customer.is_active,
    }

    update_data = data.model_dump(exclude_unset=True)

    # Check account_number uniqueness if changing
    if "account_number" in update_data and update_data["account_number"]:
        existing = (
            db.query(Customer)
            .filter(
                Customer.account_number == update_data["account_number"],
                Customer.company_id == company_id,
                Customer.id != customer_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A customer with this account number already exists",
            )

    for field, value in update_data.items():
        setattr(customer, field, value)
    customer.modified_by = actor_id

    new_data = {
        "name": customer.name,
        "account_number": customer.account_number,
        "email": customer.email,
        "phone": customer.phone,
        "account_status": customer.account_status,
        "credit_limit": str(customer.credit_limit) if customer.credit_limit is not None else None,
        "payment_terms": customer.payment_terms,
        "is_active": customer.is_active,
    }
    changes = audit_service.compute_changes(old_data, new_data)
    if changes:
        audit_service.log_action(
            db,
            company_id,
            "updated",
            "customer",
            customer.id,
            user_id=actor_id,
            changes=changes,
        )

    db.commit()
    db.refresh(customer)
    return customer


def deactivate_customer(
    db: Session,
    customer_id: str,
    company_id: str,
    actor_id: str | None = None,
) -> Customer:
    customer = get_customer(db, customer_id, company_id)
    customer.is_active = False

    audit_service.log_action(
        db,
        company_id,
        "deactivated",
        "customer",
        customer.id,
        user_id=actor_id,
        changes={"is_active": {"old": True, "new": False}},
    )

    db.commit()
    db.refresh(customer)
    return customer


# ---------------------------------------------------------------------------
# Credit check
# ---------------------------------------------------------------------------


def check_credit_limit(
    db: Session,
    customer_id: str,
    company_id: str,
    amount: Decimal,
) -> dict:
    customer = get_customer(db, customer_id, company_id)
    credit_limit = customer.credit_limit
    current_balance = customer.current_balance

    if credit_limit is None:
        # No limit set — always allowed
        return {
            "allowed": True,
            "credit_limit": None,
            "current_balance": current_balance,
            "available_credit": None,
            "requested_amount": amount,
        }

    available = credit_limit - current_balance
    return {
        "allowed": (current_balance + amount) <= credit_limit,
        "credit_limit": credit_limit,
        "current_balance": current_balance,
        "available_credit": available,
        "requested_amount": amount,
    }


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def get_customer_stats(db: Session, company_id: str) -> dict:
    base = db.query(Customer).filter(
        Customer.company_id == company_id,
        Customer.is_active == True,  # noqa: E712
    )
    total = base.count()
    active = base.filter(Customer.account_status == "active").count()
    on_hold = base.filter(Customer.account_status == "hold").count()
    suspended = base.filter(Customer.account_status == "suspended").count()

    total_outstanding = (
        db.query(func.coalesce(func.sum(Customer.current_balance), 0))
        .filter(
            Customer.company_id == company_id,
            Customer.is_active == True,  # noqa: E712
        )
        .scalar()
    )

    over_limit = (
        base.filter(
            Customer.credit_limit.isnot(None),
            Customer.current_balance > Customer.credit_limit,
        ).count()
    )

    return {
        "total_customers": total,
        "active_customers": active,
        "on_hold": on_hold,
        "suspended": suspended,
        "total_outstanding": total_outstanding,
        "over_limit_count": over_limit,
    }


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


def get_customer_contacts(
    db: Session, customer_id: str, company_id: str
) -> list[CustomerContact]:
    get_customer(db, customer_id, company_id)  # validates existence
    return (
        db.query(CustomerContact)
        .filter(
            CustomerContact.customer_id == customer_id,
            CustomerContact.company_id == company_id,
        )
        .order_by(CustomerContact.is_primary.desc(), CustomerContact.name)
        .all()
    )


def create_customer_contact(
    db: Session,
    customer_id: str,
    data: CustomerContactCreate,
    company_id: str,
) -> CustomerContact:
    get_customer(db, customer_id, company_id)  # validates existence

    # If this contact is primary, demote any existing primary
    if data.is_primary:
        db.query(CustomerContact).filter(
            CustomerContact.customer_id == customer_id,
            CustomerContact.company_id == company_id,
            CustomerContact.is_primary == True,  # noqa: E712
        ).update({"is_primary": False})

    contact = CustomerContact(
        customer_id=customer_id,
        company_id=company_id,
        **data.model_dump(),
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def update_customer_contact(
    db: Session,
    contact_id: str,
    data: CustomerContactUpdate,
    company_id: str,
) -> CustomerContact:
    contact = (
        db.query(CustomerContact)
        .filter(
            CustomerContact.id == contact_id,
            CustomerContact.company_id == company_id,
        )
        .first()
    )
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )

    update_data = data.model_dump(exclude_unset=True)

    # If promoting to primary, demote others
    if update_data.get("is_primary"):
        db.query(CustomerContact).filter(
            CustomerContact.customer_id == contact.customer_id,
            CustomerContact.company_id == company_id,
            CustomerContact.id != contact_id,
            CustomerContact.is_primary == True,  # noqa: E712
        ).update({"is_primary": False})

    for field, value in update_data.items():
        setattr(contact, field, value)

    db.commit()
    db.refresh(contact)
    return contact


def delete_customer_contact(
    db: Session, contact_id: str, company_id: str
) -> None:
    contact = (
        db.query(CustomerContact)
        .filter(
            CustomerContact.id == contact_id,
            CustomerContact.company_id == company_id,
        )
        .first()
    )
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )
    db.delete(contact)
    db.commit()


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


def get_customer_notes(
    db: Session,
    customer_id: str,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    get_customer(db, customer_id, company_id)  # validates existence

    query = db.query(CustomerNote).filter(
        CustomerNote.customer_id == customer_id,
        CustomerNote.company_id == company_id,
    )
    total = query.count()
    notes = (
        query.order_by(CustomerNote.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": notes, "total": total, "page": page, "per_page": per_page}


def create_customer_note(
    db: Session,
    customer_id: str,
    data: CustomerNoteCreate,
    company_id: str,
    actor_id: str | None = None,
) -> CustomerNote:
    get_customer(db, customer_id, company_id)  # validates existence

    note = CustomerNote(
        customer_id=customer_id,
        company_id=company_id,
        note_type=data.note_type,
        content=data.content,
        created_by=actor_id,
    )
    db.add(note)
    db.flush()

    audit_service.log_action(
        db,
        company_id,
        "created",
        "customer_note",
        note.id,
        user_id=actor_id,
        changes={"customer_id": customer_id, "note_type": data.note_type},
    )

    db.commit()
    db.refresh(note)
    return note
