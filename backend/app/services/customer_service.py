import csv
import io
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.balance_adjustment import BalanceAdjustment
from app.models.customer import Customer
from app.models.customer_contact import CustomerContact
from app.models.customer_note import CustomerNote
from app.schemas.customer import (
    BalanceAdjustmentCreate,
    CustomerContactCreate,
    CustomerContactUpdate,
    CustomerCreate,
    CustomerNoteCreate,
    CustomerUpdate,
)
from app.services import audit_service
from app.services.sync_log_service import complete_sync_log, create_sync_log


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
    customer_type: str | None = None,
    include_hidden: bool = False,
) -> dict:
    query = db.query(Customer).filter(Customer.company_id == company_id)

    if not include_inactive:
        query = query.filter(Customer.is_active == True)  # noqa: E712

    if not include_hidden:
        query = query.filter(Customer.is_extension_hidden.isnot(True))

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

    if customer_type:
        query = query.filter(Customer.customer_type == customer_type)

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
        Customer.customer_type == "funeral_home",
        Customer.is_extension_hidden.isnot(True),
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


# ---------------------------------------------------------------------------
# Balance Adjustments
# ---------------------------------------------------------------------------


def create_balance_adjustment(
    db: Session,
    customer_id: str,
    company_id: str,
    actor_id: str | None,
    data: BalanceAdjustmentCreate,
) -> BalanceAdjustment:
    customer = get_customer(db, customer_id, company_id)

    # For charges, enforce credit limit
    if data.adjustment_type == "charge" and customer.credit_limit is not None:
        new_balance = customer.current_balance + data.amount
        if new_balance > customer.credit_limit:
            available = customer.credit_limit - customer.current_balance
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Charge of ${data.amount} would exceed credit limit. "
                    f"Available credit: ${max(available, Decimal('0'))}"
                ),
            )

    adjustment = BalanceAdjustment(
        company_id=company_id,
        customer_id=customer_id,
        adjustment_type=data.adjustment_type,
        amount=data.amount,
        description=data.description,
        reference_number=data.reference_number,
        created_by=actor_id,
    )
    db.add(adjustment)

    # Update customer balance
    if data.adjustment_type == "charge":
        customer.current_balance = customer.current_balance + data.amount
    else:
        customer.current_balance = customer.current_balance - data.amount
        # Don't let balance go negative
        if customer.current_balance < Decimal("0"):
            customer.current_balance = Decimal("0")

    # Auto-hold if over limit
    if (
        customer.credit_limit is not None
        and customer.current_balance > customer.credit_limit
        and customer.account_status == "active"
    ):
        customer.account_status = "hold"
        # Add a credit note explaining the auto-hold
        auto_note = CustomerNote(
            customer_id=customer_id,
            company_id=company_id,
            note_type="credit",
            content=(
                f"Account automatically placed on hold — balance "
                f"${customer.current_balance} exceeds credit limit "
                f"${customer.credit_limit}."
            ),
            created_by=actor_id,
        )
        db.add(auto_note)

    # Auto-restore if payment brings balance back under limit
    if (
        data.adjustment_type == "payment"
        and customer.credit_limit is not None
        and customer.current_balance <= customer.credit_limit
        and customer.account_status == "hold"
    ):
        customer.account_status = "active"
        auto_note = CustomerNote(
            customer_id=customer_id,
            company_id=company_id,
            note_type="credit",
            content=(
                f"Account automatically restored to active — balance "
                f"${customer.current_balance} is within credit limit "
                f"${customer.credit_limit}."
            ),
            created_by=actor_id,
        )
        db.add(auto_note)

    customer.modified_by = actor_id

    audit_service.log_action(
        db,
        company_id,
        "created",
        "balance_adjustment",
        adjustment.id,
        user_id=actor_id,
        changes={
            "customer_id": customer_id,
            "type": data.adjustment_type,
            "amount": str(data.amount),
            "new_balance": str(customer.current_balance),
        },
    )

    db.commit()
    db.refresh(adjustment)
    return adjustment


def get_balance_adjustments(
    db: Session,
    customer_id: str,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    get_customer(db, customer_id, company_id)  # validates existence

    query = db.query(BalanceAdjustment).filter(
        BalanceAdjustment.customer_id == customer_id,
        BalanceAdjustment.company_id == company_id,
    )
    total = query.count()
    adjustments = (
        query.order_by(BalanceAdjustment.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": adjustments, "total": total, "page": page, "per_page": per_page}


# ---------------------------------------------------------------------------
# CSV Import
# ---------------------------------------------------------------------------

# Mapping of flexible header names → canonical field names
_CUSTOMER_HEADER_MAP: dict[str, str] = {
    # Name (required)
    "name": "name",
    "customer name": "name",
    "customer_name": "name",
    "company name": "name",
    "company_name": "name",
    # Account number
    "account number": "account_number",
    "account_number": "account_number",
    "account #": "account_number",
    "acct #": "account_number",
    "acct": "account_number",
    # Email
    "email": "email",
    "email address": "email",
    "email_address": "email",
    # Phone
    "phone": "phone",
    "phone number": "phone",
    "phone_number": "phone",
    # Fax
    "fax": "fax",
    "fax number": "fax",
    "fax_number": "fax",
    # Contact
    "contact": "contact_name",
    "contact name": "contact_name",
    "contact_name": "contact_name",
    "primary contact": "contact_name",
    # Website
    "website": "website",
    "web": "website",
    "url": "website",
    # Address
    "address": "address_line1",
    "address line 1": "address_line1",
    "address_line1": "address_line1",
    "street": "address_line1",
    "street address": "address_line1",
    "address line 2": "address_line2",
    "address_line2": "address_line2",
    "suite": "address_line2",
    "apt": "address_line2",
    # City / State / Zip / Country
    "city": "city",
    "state": "state",
    "state/province": "state",
    "province": "state",
    "zip": "zip_code",
    "zip code": "zip_code",
    "zip_code": "zip_code",
    "postal code": "zip_code",
    "postal_code": "zip_code",
    "country": "country",
    # Charge account
    "credit limit": "credit_limit",
    "credit_limit": "credit_limit",
    "payment terms": "payment_terms",
    "payment_terms": "payment_terms",
    "terms": "payment_terms",
    # Other
    "tax exempt": "tax_exempt",
    "tax_exempt": "tax_exempt",
    "tax id": "tax_id",
    "tax_id": "tax_id",
    "ein": "tax_id",
    "notes": "notes",
    "comments": "notes",
    "sage id": "sage_customer_id",
    "sage_customer_id": "sage_customer_id",
    "sage customer id": "sage_customer_id",
}


def _normalise_customer_headers(raw_headers: list[str]) -> dict[str, str]:
    """Map raw CSV headers to canonical customer field names."""
    mapping: dict[str, str] = {}
    for h in raw_headers:
        key = h.strip().lower()
        if key in _CUSTOMER_HEADER_MAP:
            mapping[h] = _CUSTOMER_HEADER_MAP[key]
    return mapping


def import_customers_from_csv(
    db: Session,
    file_content: bytes,
    company_id: str,
    actor_id: str | None = None,
) -> dict:
    """Parse a CSV file and bulk-create customers.

    Returns {"created": int, "skipped": int, "errors": [{"row": int, "message": str}]}
    """
    # Create sync log entry
    sync_log = create_sync_log(
        db,
        company_id,
        sync_type="csv_import",
        source="csv_file",
        destination="customers",
    )

    try:
        text = file_content.decode("utf-8-sig")  # handles BOM from Excel
    except UnicodeDecodeError:
        text = file_content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty or has no headers",
        )

    header_map = _normalise_customer_headers(list(reader.fieldnames))
    if "name" not in header_map.values():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must contain a 'name' or 'Customer Name' column",
        )

    errors: list[dict[str, object]] = []
    created = 0
    skipped = 0

    # Pre-load existing account numbers for fast duplicate checking
    existing_accounts: set[str] = {
        a[0].upper()
        for a in db.query(Customer.account_number)
        .filter(
            Customer.company_id == company_id,
            Customer.account_number.isnot(None),
        )
        .all()
    }

    for row_num, raw_row in enumerate(reader, start=2):  # row 1 = headers
        # Map raw headers to canonical names
        row: dict[str, str] = {}
        for raw_key, value in raw_row.items():
            canonical = header_map.get(raw_key)
            if canonical:
                row[canonical] = (value or "").strip()

        name = row.get("name", "").strip()
        if not name:
            errors.append({"row": row_num, "message": "Missing customer name"})
            skipped += 1
            continue

        # Check for duplicate account numbers
        acct = row.get("account_number", "").strip() or None
        if acct and acct.upper() in existing_accounts:
            errors.append(
                {"row": row_num, "message": f"Duplicate account number: {acct}"}
            )
            skipped += 1
            continue

        # Parse credit limit
        credit_limit = None
        try:
            raw_limit = row.get("credit_limit", "").strip()
            if raw_limit:
                credit_limit = Decimal(
                    raw_limit.replace(",", "").replace("$", "")
                )
        except (InvalidOperation, ValueError):
            errors.append(
                {"row": row_num, "message": f"Invalid credit limit: {row.get('credit_limit')}"}
            )
            skipped += 1
            continue

        # Parse tax_exempt
        tax_exempt = False
        raw_tax = row.get("tax_exempt", "").strip().lower()
        if raw_tax in ("true", "yes", "1", "y"):
            tax_exempt = True

        # Build customer record
        customer = Customer(
            company_id=company_id,
            name=name,
            account_number=acct,
            email=row.get("email", "").strip() or None,
            phone=row.get("phone", "").strip() or None,
            fax=row.get("fax", "").strip() or None,
            contact_name=row.get("contact_name", "").strip() or None,
            website=row.get("website", "").strip() or None,
            address_line1=row.get("address_line1", "").strip() or None,
            address_line2=row.get("address_line2", "").strip() or None,
            city=row.get("city", "").strip() or None,
            state=row.get("state", "").strip() or None,
            zip_code=row.get("zip_code", "").strip() or None,
            country=row.get("country", "").strip() or "US",
            credit_limit=credit_limit,
            payment_terms=row.get("payment_terms", "").strip() or None,
            tax_exempt=tax_exempt,
            tax_id=row.get("tax_id", "").strip() or None,
            notes=row.get("notes", "").strip() or None,
            sage_customer_id=row.get("sage_customer_id", "").strip() or None,
            created_by=actor_id,
        )
        db.add(customer)
        db.flush()

        if acct:
            existing_accounts.add(acct.upper())
        created += 1

    if created > 0:
        audit_service.log_action(
            db,
            company_id,
            "bulk_imported",
            "customer",
            None,
            user_id=actor_id,
            changes={"count": created},
        )

    # Complete sync log
    error_summary = (
        "; ".join(f"Row {e['row']}: {e['message']}" for e in errors[:10])
        if errors
        else None
    )
    complete_sync_log(db, sync_log, created, skipped, error_summary)
    db.commit()

    return {"created": created, "skipped": skipped, "errors": errors}
