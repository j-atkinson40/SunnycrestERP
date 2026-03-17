"""Funeral home case management service."""

import uuid
from datetime import UTC, datetime, date

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func as sa_func, or_

from app.models.fh_case import FHCase
from app.models.fh_case_contact import FHCaseContact
from app.models.fh_case_activity import FHCaseActivity
from app.models.fh_vault_order import FHVaultOrder
from app.models.fh_obituary import FHObituary
from app.models.fh_invoice import FHInvoice
from app.models.fh_payment import FHPayment
from app.models.fh_document import FHDocument
from app.models.user import User

# ---------------------------------------------------------------------------
# Status transition map
# ---------------------------------------------------------------------------

CASE_TRANSITIONS = {
    "first_call": {"in_progress", "cancelled"},
    "in_progress": {"services_scheduled", "cancelled"},
    "services_scheduled": {"services_complete", "cancelled"},
    "services_complete": {"pending_invoice", "cancelled"},
    "pending_invoice": {"invoiced", "cancelled"},
    "invoiced": {"closed"},
    # closed and cancelled are terminal
}


def _validate_case_transition(current: str, target: str) -> None:
    allowed = CASE_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid case status transition: {current} -> {target}",
        )


# ---------------------------------------------------------------------------
# Case number generation
# ---------------------------------------------------------------------------

def _next_case_number(db: Session, company_id: str) -> str:
    """Generate next FH-YYYY-NNNN case number."""
    year = datetime.now(UTC).year
    prefix = f"FH-{year}-"
    count = (
        db.query(sa_func.count(FHCase.id))
        .filter(
            FHCase.company_id == company_id,
            FHCase.case_number.like(f"{prefix}%"),
        )
        .scalar()
    )
    return f"{prefix}{(count or 0) + 1:04d}"


# ---------------------------------------------------------------------------
# Activity logging helper
# ---------------------------------------------------------------------------

def log_activity(
    db: Session,
    tenant_id: str,
    case_id: str,
    activity_type: str,
    description: str,
    performed_by: str | None = None,
    metadata: dict | None = None,
) -> FHCaseActivity:
    """Create an activity log entry for a case."""
    import json

    activity = FHCaseActivity(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        case_id=case_id,
        activity_type=activity_type,
        description=description,
        performed_by=performed_by,
        metadata=json.dumps(metadata) if metadata else None,
    )
    db.add(activity)
    return activity


# ---------------------------------------------------------------------------
# Case CRUD
# ---------------------------------------------------------------------------

def create_from_first_call(
    db: Session,
    tenant_id: str,
    data: dict,
    performed_by_id: str,
) -> FHCase:
    """Create a case from first call intake.

    Required in data:
    - deceased_first_name, deceased_last_name, deceased_date_of_death
    - primary_contact: {first_name, last_name, phone_primary}
    - assigned_director_id
    """
    # Validate required fields
    for field in ("deceased_first_name", "deceased_last_name", "deceased_date_of_death"):
        if not data.get(field):
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    contact_data = data.get("primary_contact")
    if not contact_data or not contact_data.get("first_name") or not contact_data.get("last_name"):
        raise HTTPException(status_code=400, detail="Primary contact first_name and last_name are required")
    if not contact_data.get("phone_primary"):
        raise HTTPException(status_code=400, detail="Primary contact phone_primary is required")
    if not data.get("assigned_director_id"):
        raise HTTPException(status_code=400, detail="assigned_director_id is required")

    case_id = str(uuid.uuid4())
    case = FHCase(
        id=case_id,
        company_id=tenant_id,
        case_number=_next_case_number(db, tenant_id),
        status="first_call",
        deceased_first_name=data["deceased_first_name"],
        deceased_middle_name=data.get("deceased_middle_name"),
        deceased_last_name=data["deceased_last_name"],
        deceased_date_of_birth=data.get("deceased_date_of_birth"),
        deceased_date_of_death=data["deceased_date_of_death"],
        deceased_place_of_death=data.get("deceased_place_of_death"),
        deceased_place_of_death_name=data.get("deceased_place_of_death_name"),
        deceased_place_of_death_city=data.get("deceased_place_of_death_city"),
        deceased_place_of_death_state=data.get("deceased_place_of_death_state"),
        deceased_gender=data.get("deceased_gender"),
        deceased_age_at_death=data.get("deceased_age_at_death"),
        deceased_ssn_last_four=data.get("deceased_ssn_last_four"),
        deceased_veteran=data.get("deceased_veteran", False),
        disposition_type=data.get("disposition_type"),
        service_type=data.get("service_type"),
        assigned_director_id=data["assigned_director_id"],
        referred_by=data.get("referred_by"),
        notes=data.get("notes"),
    )
    db.add(case)
    db.flush()

    # Create primary contact
    contact_id = str(uuid.uuid4())
    contact = FHCaseContact(
        id=contact_id,
        company_id=tenant_id,
        case_id=case_id,
        contact_type="responsible_party",
        first_name=contact_data["first_name"],
        last_name=contact_data["last_name"],
        relationship_to_deceased=contact_data.get("relationship_to_deceased"),
        phone_primary=contact_data["phone_primary"],
        phone_secondary=contact_data.get("phone_secondary"),
        email=contact_data.get("email"),
        address=contact_data.get("address"),
        city=contact_data.get("city"),
        state=contact_data.get("state"),
        zip=contact_data.get("zip"),
        is_primary=True,
        receives_portal_access=contact_data.get("receives_portal_access", False),
        notes=contact_data.get("notes"),
    )
    db.add(contact)
    db.flush()

    # Set primary contact on case
    case.primary_contact_id = contact_id

    # Log activity
    log_activity(
        db,
        tenant_id,
        case_id,
        "first_call_received",
        f"Case created for {data['deceased_first_name']} {data['deceased_last_name']}",
        performed_by=performed_by_id,
    )

    db.commit()
    db.refresh(case)
    return case


def update_status(
    db: Session,
    tenant_id: str,
    case_id: str,
    new_status: str,
    performed_by_id: str,
    notes: str | None = None,
) -> FHCase:
    """Validate state machine transition and update case status."""
    case = (
        db.query(FHCase)
        .filter(FHCase.id == case_id, FHCase.company_id == tenant_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    old_status = case.status
    _validate_case_transition(old_status, new_status)

    case.status = new_status
    case.updated_at = datetime.now(UTC)

    if new_status == "closed":
        case.closed_at = datetime.now(UTC)

    log_activity(
        db,
        tenant_id,
        case_id,
        "status_changed",
        f"Status changed from {old_status} to {new_status}" + (f": {notes}" if notes else ""),
        performed_by=performed_by_id,
        metadata={"old_status": old_status, "new_status": new_status, "notes": notes},
    )

    db.commit()
    db.refresh(case)
    return case


def get_case(db: Session, tenant_id: str, case_id: str) -> FHCase:
    """Get single case with related records eagerly loaded."""
    case = (
        db.query(FHCase)
        .options(
            joinedload(FHCase.contacts),
            joinedload(FHCase.vault_order),
            joinedload(FHCase.obituary),
            joinedload(FHCase.invoice),
        )
        .filter(FHCase.id == case_id, FHCase.company_id == tenant_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def list_cases(
    db: Session,
    tenant_id: str,
    status: str | None = None,
    assigned_director_id: str | None = None,
    service_date_from: date | None = None,
    service_date_to: date | None = None,
    disposition_type: str | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> dict:
    """List cases with filters. Search matches case_number, deceased name, contact name."""
    query = db.query(FHCase).filter(FHCase.company_id == tenant_id)

    if status:
        query = query.filter(FHCase.status == status)
    if assigned_director_id:
        query = query.filter(FHCase.assigned_director_id == assigned_director_id)
    if service_date_from:
        query = query.filter(FHCase.service_date >= service_date_from)
    if service_date_to:
        query = query.filter(FHCase.service_date <= service_date_to)
    if disposition_type:
        query = query.filter(FHCase.disposition_type == disposition_type)
    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                FHCase.case_number.ilike(term),
                FHCase.deceased_first_name.ilike(term),
                FHCase.deceased_last_name.ilike(term),
            )
        )

    total = query.count()
    items = (
        query.order_by(FHCase.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_case_board(db: Session, tenant_id: str) -> dict:
    """All active cases grouped by status for kanban board."""
    active_statuses = [
        "first_call",
        "in_progress",
        "services_scheduled",
        "services_complete",
        "pending_invoice",
        "invoiced",
    ]
    cases = (
        db.query(FHCase)
        .filter(
            FHCase.company_id == tenant_id,
            FHCase.status.in_(active_statuses),
        )
        .order_by(FHCase.created_at.desc())
        .all()
    )

    today = date.today()
    board: dict[str, list] = {s: [] for s in active_statuses}

    for case in cases:
        # Get vault order status if exists
        vault_order = (
            db.query(FHVaultOrder)
            .filter(FHVaultOrder.case_id == case.id, FHVaultOrder.company_id == tenant_id)
            .first()
        )
        # Check for pending obituary
        obituary = (
            db.query(FHObituary)
            .filter(FHObituary.case_id == case.id, FHObituary.company_id == tenant_id)
            .first()
        )
        # Get director name
        director_name = None
        if case.assigned_director_id:
            director = db.query(User).filter(User.id == case.assigned_director_id).first()
            if director:
                director_name = f"{director.first_name} {director.last_name}" if hasattr(director, "first_name") else director.email

        days_since_opened = (today - case.created_at.date()).days if case.created_at else 0

        card = {
            "id": case.id,
            "case_number": case.case_number,
            "deceased_name": f"{case.deceased_first_name} {case.deceased_last_name}",
            "service_date": str(case.service_date) if case.service_date else None,
            "assigned_director_name": director_name,
            "days_since_opened": days_since_opened,
            "vault_order_status": vault_order.status if vault_order else None,
            "has_pending_obituary": (
                obituary is not None and obituary.status == "pending_family_approval"
            ) if obituary else False,
            "status": case.status,
        }
        board.setdefault(case.status, []).append(card)

    return board


def get_case_summary(db: Session, tenant_id: str, case_id: str) -> dict:
    """Full case with ALL related records for detail page."""
    case = get_case(db, tenant_id, case_id)

    contacts = (
        db.query(FHCaseContact)
        .filter(FHCaseContact.case_id == case_id, FHCaseContact.company_id == tenant_id)
        .all()
    )
    services_query = (
        db.query(FHCase)  # placeholder — actual FHService query
        .filter(FHCase.id == "impossible")  # will be replaced
    )
    # Services
    from app.models.fh_service import FHService
    services = (
        db.query(FHService)
        .filter(FHService.case_id == case_id, FHService.company_id == tenant_id)
        .order_by(FHService.sort_order)
        .all()
    )

    vault_order = (
        db.query(FHVaultOrder)
        .filter(FHVaultOrder.case_id == case_id, FHVaultOrder.company_id == tenant_id)
        .first()
    )
    obituary = (
        db.query(FHObituary)
        .filter(FHObituary.case_id == case_id, FHObituary.company_id == tenant_id)
        .first()
    )
    invoice = (
        db.query(FHInvoice)
        .filter(FHInvoice.case_id == case_id, FHInvoice.company_id == tenant_id)
        .first()
    )
    payments = (
        db.query(FHPayment)
        .filter(FHPayment.case_id == case_id, FHPayment.company_id == tenant_id)
        .order_by(FHPayment.payment_date.desc())
        .all()
    )
    documents = (
        db.query(FHDocument)
        .filter(FHDocument.case_id == case_id, FHDocument.company_id == tenant_id)
        .all()
    )
    recent_activity = (
        db.query(FHCaseActivity)
        .filter(FHCaseActivity.case_id == case_id, FHCaseActivity.company_id == tenant_id)
        .order_by(FHCaseActivity.created_at.desc())
        .limit(20)
        .all()
    )

    return {
        "case": case,
        "contacts": contacts,
        "services": services,
        "vault_order": vault_order,
        "obituary": obituary,
        "invoice": invoice,
        "payments": payments,
        "documents": documents,
        "recent_activity": recent_activity,
    }


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

def add_contact(
    db: Session,
    tenant_id: str,
    case_id: str,
    data: dict,
    performed_by_id: str,
) -> FHCaseContact:
    """Add contact to case."""
    # Verify case exists
    case = (
        db.query(FHCase)
        .filter(FHCase.id == case_id, FHCase.company_id == tenant_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    contact = FHCaseContact(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        case_id=case_id,
        contact_type=data.get("contact_type", "family"),
        first_name=data["first_name"],
        last_name=data["last_name"],
        relationship_to_deceased=data.get("relationship_to_deceased"),
        phone_primary=data.get("phone_primary"),
        phone_secondary=data.get("phone_secondary"),
        email=data.get("email"),
        address=data.get("address"),
        city=data.get("city"),
        state=data.get("state"),
        zip=data.get("zip"),
        is_primary=data.get("is_primary", False),
        receives_portal_access=data.get("receives_portal_access", False),
        notes=data.get("notes"),
    )
    db.add(contact)

    log_activity(
        db,
        tenant_id,
        case_id,
        "contact_added",
        f"Contact added: {data['first_name']} {data['last_name']}",
        performed_by=performed_by_id,
    )

    db.commit()
    db.refresh(contact)
    return contact


def update_contact(
    db: Session,
    tenant_id: str,
    case_id: str,
    contact_id: str,
    data: dict,
) -> FHCaseContact:
    """Update contact details."""
    contact = (
        db.query(FHCaseContact)
        .filter(
            FHCaseContact.id == contact_id,
            FHCaseContact.case_id == case_id,
            FHCaseContact.company_id == tenant_id,
        )
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    updatable_fields = (
        "contact_type", "first_name", "last_name", "relationship_to_deceased",
        "phone_primary", "phone_secondary", "email", "address", "city", "state",
        "zip", "is_primary", "receives_portal_access", "notes",
    )
    for key in updatable_fields:
        if key in data:
            setattr(contact, key, data[key])

    db.commit()
    db.refresh(contact)
    return contact


def list_contacts(db: Session, tenant_id: str, case_id: str) -> list[FHCaseContact]:
    """List all contacts for a case."""
    return (
        db.query(FHCaseContact)
        .filter(FHCaseContact.case_id == case_id, FHCaseContact.company_id == tenant_id)
        .order_by(FHCaseContact.is_primary.desc(), FHCaseContact.last_name)
        .all()
    )


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------

def get_activity(
    db: Session,
    tenant_id: str,
    case_id: str,
    skip: int = 0,
    limit: int = 50,
) -> list[FHCaseActivity]:
    """Get activity timeline for case, ordered by created_at desc."""
    return (
        db.query(FHCaseActivity)
        .filter(FHCaseActivity.case_id == case_id, FHCaseActivity.company_id == tenant_id)
        .order_by(FHCaseActivity.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
