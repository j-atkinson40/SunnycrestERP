"""Contact service — CRUD + auto-population from platform users."""

import uuid as _uuid

from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.company_entity import CompanyEntity


def get_contacts(db: Session, master_company_id: str, company_id: str) -> dict:
    """Return confirmed and suggested contacts for a company entity."""
    all_contacts = (
        db.query(Contact)
        .filter(
            Contact.master_company_id == master_company_id,
            Contact.company_id == company_id,
            Contact.is_active == True,
        )
        .order_by(Contact.is_primary.desc(), Contact.name)
        .all()
    )

    confirmed = [c for c in all_contacts if not c.linked_auto]
    suggested = [c for c in all_contacts if c.linked_auto]

    return {"confirmed": confirmed, "suggested": suggested}


def create_contact(
    db: Session,
    master_company_id: str,
    company_id: str,
    data: dict,
    created_by: str | None = None,
) -> Contact:
    """Create a new contact."""
    if data.get("is_primary"):
        _clear_primary(db, master_company_id)

    contact = Contact(
        id=str(_uuid.uuid4()),
        company_id=company_id,
        master_company_id=master_company_id,
        name=data["name"],
        title=data.get("title"),
        phone=data.get("phone"),
        phone_ext=data.get("phone_ext"),
        mobile=data.get("mobile"),
        email=data.get("email"),
        role=data.get("role"),
        is_primary=data.get("is_primary", False),
        receives_invoices=data.get("receives_invoices", False),
        receives_legacy_proofs=data.get("receives_legacy_proofs", False),
        linked_user_id=data.get("linked_user_id"),
        linked_auto=data.get("linked_auto", False),
        notes=data.get("notes"),
        created_by=created_by,
    )
    db.add(contact)
    db.flush()
    return contact


def update_contact(db: Session, contact: Contact, data: dict) -> Contact:
    """Update contact fields."""
    if data.get("is_primary") and not contact.is_primary:
        _clear_primary(db, contact.master_company_id)

    for field in (
        "name", "title", "phone", "phone_ext", "mobile", "email", "role",
        "is_primary", "receives_invoices", "receives_legacy_proofs", "notes",
    ):
        if field in data:
            setattr(contact, field, data[field])

    db.flush()
    return contact


def soft_delete_contact(db: Session, contact: Contact) -> None:
    """Soft-delete a contact. Clears primary flag."""
    contact.is_active = False
    contact.is_primary = False
    db.flush()


def hard_delete_contact(db: Session, contact: Contact) -> None:
    """Hard-delete a contact (for dismissed suggestions)."""
    db.delete(contact)
    db.flush()


def confirm_contact(db: Session, contact: Contact) -> Contact:
    """Confirm an auto-suggested contact."""
    contact.linked_auto = False
    db.flush()
    return contact


def set_primary(db: Session, contact_id: str, master_company_id: str) -> None:
    """Set a contact as primary, clearing others."""
    _clear_primary(db, master_company_id)
    db.query(Contact).filter(Contact.id == contact_id).update({"is_primary": True})
    db.flush()


def get_proof_recipients(db: Session, master_company_id: str, company_id: str) -> list[str]:
    """Return email addresses for contacts that receive legacy proofs."""
    contacts = (
        db.query(Contact.email)
        .filter(
            Contact.master_company_id == master_company_id,
            Contact.company_id == company_id,
            Contact.receives_legacy_proofs == True,
            Contact.is_active == True,
            Contact.email.isnot(None),
        )
        .all()
    )
    return [c[0] for c in contacts if c[0]]


def get_invoice_recipients(db: Session, master_company_id: str, company_id: str) -> list[str]:
    """Return email addresses for contacts that receive invoices."""
    contacts = (
        db.query(Contact.email)
        .filter(
            Contact.master_company_id == master_company_id,
            Contact.company_id == company_id,
            Contact.receives_invoices == True,
            Contact.is_active == True,
            Contact.email.isnot(None),
        )
        .all()
    )
    return [c[0] for c in contacts if c[0]]


def _clear_primary(db: Session, master_company_id: str) -> None:
    """Unset is_primary on all contacts for this company entity."""
    db.query(Contact).filter(
        Contact.master_company_id == master_company_id,
        Contact.is_primary == True,
    ).update({"is_primary": False})
