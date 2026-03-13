import csv
import io
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.vendor import Vendor
from app.models.vendor_contact import VendorContact
from app.models.vendor_note import VendorNote
from app.schemas.vendor import (
    VendorContactCreate,
    VendorContactUpdate,
    VendorCreate,
    VendorNoteCreate,
    VendorUpdate,
)
from app.services import audit_service
from app.services.sync_log_service import complete_sync_log, create_sync_log


# ---------------------------------------------------------------------------
# Vendor CRUD
# ---------------------------------------------------------------------------


def get_vendors(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
    vendor_status: str | None = None,
    include_inactive: bool = False,
) -> dict:
    query = db.query(Vendor).filter(Vendor.company_id == company_id)

    if not include_inactive:
        query = query.filter(Vendor.is_active == True)  # noqa: E712

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Vendor.name.ilike(pattern),
                Vendor.account_number.ilike(pattern),
                Vendor.email.ilike(pattern),
                Vendor.contact_name.ilike(pattern),
            )
        )

    if vendor_status:
        query = query.filter(Vendor.vendor_status == vendor_status)

    total = query.count()
    vendors = (
        query.order_by(Vendor.name)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": vendors, "total": total, "page": page, "per_page": per_page}


def get_vendor(db: Session, vendor_id: str, company_id: str) -> Vendor:
    vendor = (
        db.query(Vendor)
        .filter(Vendor.id == vendor_id, Vendor.company_id == company_id)
        .first()
    )
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found"
        )
    return vendor


def create_vendor(
    db: Session,
    data: VendorCreate,
    company_id: str,
    actor_id: str | None = None,
) -> Vendor:
    # Check account_number uniqueness if provided
    if data.account_number:
        existing = (
            db.query(Vendor)
            .filter(
                Vendor.account_number == data.account_number,
                Vendor.company_id == company_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A vendor with this account number already exists",
            )

    vendor = Vendor(
        company_id=company_id,
        created_by=actor_id,
        **data.model_dump(),
    )
    db.add(vendor)
    db.flush()

    audit_service.log_action(
        db,
        company_id,
        "created",
        "vendor",
        vendor.id,
        user_id=actor_id,
        changes={"name": data.name, "account_number": data.account_number},
    )

    db.commit()
    db.refresh(vendor)
    return vendor


def update_vendor(
    db: Session,
    vendor_id: str,
    data: VendorUpdate,
    company_id: str,
    actor_id: str | None = None,
) -> Vendor:
    vendor = get_vendor(db, vendor_id, company_id)

    old_data = {
        "name": vendor.name,
        "account_number": vendor.account_number,
        "email": vendor.email,
        "phone": vendor.phone,
        "vendor_status": vendor.vendor_status,
        "payment_terms": vendor.payment_terms,
        "is_active": vendor.is_active,
    }

    update_data = data.model_dump(exclude_unset=True)

    # Check account_number uniqueness if changing
    if "account_number" in update_data and update_data["account_number"]:
        existing = (
            db.query(Vendor)
            .filter(
                Vendor.account_number == update_data["account_number"],
                Vendor.company_id == company_id,
                Vendor.id != vendor_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A vendor with this account number already exists",
            )

    for field, value in update_data.items():
        setattr(vendor, field, value)
    vendor.modified_by = actor_id

    new_data = {
        "name": vendor.name,
        "account_number": vendor.account_number,
        "email": vendor.email,
        "phone": vendor.phone,
        "vendor_status": vendor.vendor_status,
        "payment_terms": vendor.payment_terms,
        "is_active": vendor.is_active,
    }
    changes = audit_service.compute_changes(old_data, new_data)
    if changes:
        audit_service.log_action(
            db,
            company_id,
            "updated",
            "vendor",
            vendor.id,
            user_id=actor_id,
            changes=changes,
        )

    db.commit()
    db.refresh(vendor)
    return vendor


def deactivate_vendor(
    db: Session,
    vendor_id: str,
    company_id: str,
    actor_id: str | None = None,
) -> Vendor:
    vendor = get_vendor(db, vendor_id, company_id)
    vendor.is_active = False

    audit_service.log_action(
        db,
        company_id,
        "deactivated",
        "vendor",
        vendor.id,
        user_id=actor_id,
        changes={"is_active": {"old": True, "new": False}},
    )

    db.commit()
    db.refresh(vendor)
    return vendor


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def get_vendor_stats(db: Session, company_id: str) -> dict:
    base = db.query(Vendor).filter(
        Vendor.company_id == company_id,
        Vendor.is_active == True,  # noqa: E712
    )
    total = base.count()
    active = base.filter(Vendor.vendor_status == "active").count()
    on_hold = base.filter(Vendor.vendor_status == "on_hold").count()

    return {
        "total_vendors": total,
        "active_vendors": active,
        "on_hold": on_hold,
    }


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


def get_vendor_contacts(
    db: Session, vendor_id: str, company_id: str
) -> list[VendorContact]:
    get_vendor(db, vendor_id, company_id)  # validates existence
    return (
        db.query(VendorContact)
        .filter(
            VendorContact.vendor_id == vendor_id,
            VendorContact.company_id == company_id,
        )
        .order_by(VendorContact.is_primary.desc(), VendorContact.name)
        .all()
    )


def create_vendor_contact(
    db: Session,
    vendor_id: str,
    data: VendorContactCreate,
    company_id: str,
) -> VendorContact:
    get_vendor(db, vendor_id, company_id)  # validates existence

    # If this contact is primary, demote any existing primary
    if data.is_primary:
        db.query(VendorContact).filter(
            VendorContact.vendor_id == vendor_id,
            VendorContact.company_id == company_id,
            VendorContact.is_primary == True,  # noqa: E712
        ).update({"is_primary": False})

    contact = VendorContact(
        vendor_id=vendor_id,
        company_id=company_id,
        **data.model_dump(),
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def update_vendor_contact(
    db: Session,
    contact_id: str,
    data: VendorContactUpdate,
    company_id: str,
) -> VendorContact:
    contact = (
        db.query(VendorContact)
        .filter(
            VendorContact.id == contact_id,
            VendorContact.company_id == company_id,
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
        db.query(VendorContact).filter(
            VendorContact.vendor_id == contact.vendor_id,
            VendorContact.company_id == company_id,
            VendorContact.id != contact_id,
            VendorContact.is_primary == True,  # noqa: E712
        ).update({"is_primary": False})

    for field, value in update_data.items():
        setattr(contact, field, value)

    db.commit()
    db.refresh(contact)
    return contact


def delete_vendor_contact(
    db: Session, contact_id: str, company_id: str
) -> None:
    contact = (
        db.query(VendorContact)
        .filter(
            VendorContact.id == contact_id,
            VendorContact.company_id == company_id,
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


def get_vendor_notes(
    db: Session,
    vendor_id: str,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    get_vendor(db, vendor_id, company_id)  # validates existence

    query = db.query(VendorNote).filter(
        VendorNote.vendor_id == vendor_id,
        VendorNote.company_id == company_id,
    )
    total = query.count()
    notes = (
        query.order_by(VendorNote.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": notes, "total": total, "page": page, "per_page": per_page}


def create_vendor_note(
    db: Session,
    vendor_id: str,
    data: VendorNoteCreate,
    company_id: str,
    actor_id: str | None = None,
) -> VendorNote:
    get_vendor(db, vendor_id, company_id)  # validates existence

    note = VendorNote(
        vendor_id=vendor_id,
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
        "vendor_note",
        note.id,
        user_id=actor_id,
        changes={"vendor_id": vendor_id, "note_type": data.note_type},
    )

    db.commit()
    db.refresh(note)
    return note


# ---------------------------------------------------------------------------
# CSV Import
# ---------------------------------------------------------------------------

# Mapping of flexible header names → canonical field names
_VENDOR_HEADER_MAP: dict[str, str] = {
    # Name (required)
    "name": "name",
    "vendor name": "name",
    "vendor_name": "name",
    "company name": "name",
    "company_name": "name",
    "supplier": "name",
    "supplier name": "name",
    # Account number
    "account number": "account_number",
    "account_number": "account_number",
    "account #": "account_number",
    "acct #": "account_number",
    "acct": "account_number",
    "vendor number": "account_number",
    "vendor #": "account_number",
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
    # Purchasing info
    "payment terms": "payment_terms",
    "payment_terms": "payment_terms",
    "terms": "payment_terms",
    "lead time": "lead_time_days",
    "lead_time": "lead_time_days",
    "lead time days": "lead_time_days",
    "lead_time_days": "lead_time_days",
    "minimum order": "minimum_order",
    "minimum_order": "minimum_order",
    "min order": "minimum_order",
    "min_order": "minimum_order",
    # Other
    "tax id": "tax_id",
    "tax_id": "tax_id",
    "ein": "tax_id",
    "notes": "notes",
    "comments": "notes",
    "sage id": "sage_vendor_id",
    "sage_vendor_id": "sage_vendor_id",
    "sage vendor id": "sage_vendor_id",
}


def _normalise_vendor_headers(raw_headers: list[str]) -> dict[str, str]:
    """Map raw CSV headers to canonical vendor field names."""
    mapping: dict[str, str] = {}
    for h in raw_headers:
        key = h.strip().lower()
        if key in _VENDOR_HEADER_MAP:
            mapping[h] = _VENDOR_HEADER_MAP[key]
    return mapping


def import_vendors_from_csv(
    db: Session,
    file_content: bytes,
    company_id: str,
    actor_id: str | None = None,
) -> dict:
    """Parse a CSV file and bulk-create vendors.

    Returns {"created": int, "skipped": int, "errors": [{"row": int, "message": str}]}
    """
    # Create sync log entry
    sync_log = create_sync_log(
        db,
        company_id,
        sync_type="csv_import",
        source="csv_file",
        destination="vendors",
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

    header_map = _normalise_vendor_headers(list(reader.fieldnames))
    if "name" not in header_map.values():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must contain a 'name' or 'Vendor Name' column",
        )

    errors: list[dict[str, object]] = []
    created = 0
    skipped = 0

    # Pre-load existing account numbers for fast duplicate checking
    existing_accounts: set[str] = {
        a[0].upper()
        for a in db.query(Vendor.account_number)
        .filter(
            Vendor.company_id == company_id,
            Vendor.account_number.isnot(None),
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
            errors.append({"row": row_num, "message": "Missing vendor name"})
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

        # Parse lead_time_days
        lead_time_days = None
        raw_lead = row.get("lead_time_days", "").strip()
        if raw_lead:
            try:
                lead_time_days = int(raw_lead)
            except ValueError:
                errors.append(
                    {"row": row_num, "message": f"Invalid lead time: {raw_lead}"}
                )
                skipped += 1
                continue

        # Parse minimum_order
        minimum_order = None
        try:
            raw_min = row.get("minimum_order", "").strip()
            if raw_min:
                minimum_order = Decimal(
                    raw_min.replace(",", "").replace("$", "")
                )
        except (InvalidOperation, ValueError):
            errors.append(
                {"row": row_num, "message": f"Invalid minimum order: {row.get('minimum_order')}"}
            )
            skipped += 1
            continue

        # Build vendor record
        vendor = Vendor(
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
            payment_terms=row.get("payment_terms", "").strip() or None,
            lead_time_days=lead_time_days,
            minimum_order=minimum_order,
            tax_id=row.get("tax_id", "").strip() or None,
            notes=row.get("notes", "").strip() or None,
            sage_vendor_id=row.get("sage_vendor_id", "").strip() or None,
            created_by=actor_id,
        )
        db.add(vendor)
        db.flush()

        if acct:
            existing_accounts.add(acct.upper())
        created += 1

    if created > 0:
        audit_service.log_action(
            db,
            company_id,
            "bulk_imported",
            "vendor",
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
