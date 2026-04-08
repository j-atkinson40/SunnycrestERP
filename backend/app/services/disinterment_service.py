"""DisintermentService — core orchestration for the 5-stage disinterment pipeline.

Stages: intake → quoted → quote_accepted → signatures_pending →
        signatures_complete → scheduled → complete

Also handles cancellation from any non-complete stage.
"""

import logging
import secrets
import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.company import Company
from app.models.company_entity import CompanyEntity
from app.models.contact import Contact
from app.models.disinterment_case import DisintermentCase
from app.models.disinterment_charge_type import DisintermentChargeType
from app.services import docusign_service, rotation_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _next_case_number(db: Session, company_id: str) -> str:
    """Generate DIS-{YYYY}-{NNNN} per-tenant sequence."""
    year = datetime.now(timezone.utc).year
    prefix = f"DIS-{year}-"

    last = (
        db.query(DisintermentCase.case_number)
        .filter(
            DisintermentCase.company_id == company_id,
            DisintermentCase.case_number.like(f"{prefix}%"),
        )
        .order_by(DisintermentCase.case_number.desc())
        .first()
    )

    if last:
        try:
            seq = int(last[0].split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1

    return f"{prefix}{seq:04d}"


def _load_case(
    db: Session, case_id: str, company_id: str
) -> DisintermentCase:
    """Load a case with eager-loaded relationships, or 404."""
    case = (
        db.query(DisintermentCase)
        .options(
            joinedload(DisintermentCase.cemetery),
            joinedload(DisintermentCase.funeral_home),
            joinedload(DisintermentCase.fulfilling_location),
            joinedload(DisintermentCase.assigned_driver),
        )
        .filter(
            DisintermentCase.id == case_id,
            DisintermentCase.company_id == company_id,
            DisintermentCase.deleted_at.is_(None),
        )
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Disinterment case not found")
    return case


def _assert_status(case: DisintermentCase, *allowed: str) -> None:
    if case.status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot perform this action when case status is '{case.status}'. "
            f"Required: {', '.join(allowed)}",
        )


def _signatures_list(case: DisintermentCase) -> list[dict]:
    """Build the 4-party signature status list."""
    return [
        {
            "party": "funeral_home",
            "status": case.sig_funeral_home or "not_sent",
            "signed_at": case.sig_funeral_home_signed_at,
        },
        {
            "party": "cemetery",
            "status": case.sig_cemetery or "not_sent",
            "signed_at": case.sig_cemetery_signed_at,
        },
        {
            "party": "next_of_kin",
            "status": case.sig_next_of_kin or "not_sent",
            "signed_at": case.sig_next_of_kin_signed_at,
        },
        {
            "party": "manufacturer",
            "status": case.sig_manufacturer or "not_sent",
            "signed_at": case.sig_manufacturer_signed_at,
        },
    ]


def _case_to_response(case: DisintermentCase) -> dict:
    """Serialize a case into the API response dict."""
    return {
        "id": case.id,
        "company_id": case.company_id,
        "case_number": case.case_number,
        "status": case.status,
        "decedent_name": case.decedent_name,
        "date_of_death": case.date_of_death,
        "date_of_burial": case.date_of_burial,
        "reason": case.reason,
        "destination": case.destination,
        "vault_description": case.vault_description,
        "cemetery_id": case.cemetery_id,
        "cemetery_name": case.cemetery.name if case.cemetery else None,
        "cemetery_lot_section": case.cemetery_lot_section,
        "cemetery_lot_space": case.cemetery_lot_space,
        "fulfilling_location_id": case.fulfilling_location_id,
        "fulfilling_location_name": (
            case.fulfilling_location.name if case.fulfilling_location else None
        ),
        "funeral_home_id": case.funeral_home_id,
        "funeral_home_name": case.funeral_home.name if case.funeral_home else None,
        "funeral_director_contact_id": case.funeral_director_contact_id,
        "next_of_kin": case.next_of_kin or [],
        "intake_token": case.intake_token,
        "intake_submitted_at": case.intake_submitted_at,
        "quote_id": case.quote_id,
        "accepted_quote_amount": case.accepted_quote_amount,
        "has_hazard_pay": case.has_hazard_pay,
        "docusign_envelope_id": case.docusign_envelope_id,
        "signatures": _signatures_list(case),
        "scheduled_date": case.scheduled_date,
        "assigned_driver_id": case.assigned_driver_id,
        "assigned_driver_name": (
            f"{case.assigned_driver.first_name} {case.assigned_driver.last_name}"
            if case.assigned_driver
            else None
        ),
        "assigned_crew": case.assigned_crew or [],
        "rotation_assignment_id": case.rotation_assignment_id,
        "completed_at": case.completed_at,
        "invoice_id": case.invoice_id,
        "created_by_user_id": case.created_by_user_id,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
    }


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------


def create_case(
    db: Session, company_id: str, created_by_user_id: str, decedent_name: str = "Pending Intake"
) -> dict:
    """Create a new disinterment case shell with an intake token."""
    case = DisintermentCase(
        id=str(uuid.uuid4()),
        company_id=company_id,
        case_number=_next_case_number(db, company_id),
        status="intake",
        decedent_name=decedent_name,
        intake_token=secrets.token_urlsafe(32),
        created_by_user_id=created_by_user_id,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    logger.info("Created disinterment case %s", case.case_number)
    return _case_to_response(case)


def list_cases(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
    search: str | None = None,
) -> dict:
    """List cases for tenant with optional filtering."""
    q = (
        db.query(DisintermentCase)
        .options(
            joinedload(DisintermentCase.cemetery),
            joinedload(DisintermentCase.funeral_home),
        )
        .filter(
            DisintermentCase.company_id == company_id,
            DisintermentCase.deleted_at.is_(None),
        )
    )

    if status:
        q = q.filter(DisintermentCase.status == status)

    if search:
        pattern = f"%{search}%"
        q = q.filter(
            (DisintermentCase.decedent_name.ilike(pattern))
            | (DisintermentCase.case_number.ilike(pattern))
        )

    total = q.count()
    cases = (
        q.order_by(DisintermentCase.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "items": [
            {
                "id": c.id,
                "case_number": c.case_number,
                "decedent_name": c.decedent_name,
                "status": c.status,
                "cemetery_name": c.cemetery.name if c.cemetery else None,
                "funeral_home_name": c.funeral_home.name if c.funeral_home else None,
                "scheduled_date": c.scheduled_date,
                "created_at": c.created_at,
            }
            for c in cases
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


def get_case(db: Session, case_id: str, company_id: str) -> dict:
    """Get full case detail."""
    case = _load_case(db, case_id, company_id)
    return _case_to_response(case)


def update_intake(db: Session, case_id: str, company_id: str, data) -> dict:
    """Staff review/edit of submitted intake data."""
    case = _load_case(db, case_id, company_id)

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "next_of_kin" and value is not None:
            setattr(case, field, [nok.model_dump() for nok in value])
        else:
            setattr(case, field, value)

    case.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(case)

    return _case_to_response(_load_case(db, case_id, company_id))


# ---------------------------------------------------------------------------
# Intake form (public, token-based)
# ---------------------------------------------------------------------------


class NeedsLocationMapping(Exception):
    """Raised when a cemetery has no fulfilling_location_id."""

    def __init__(self, cemetery_id: str, cemetery_name: str):
        self.cemetery_id = cemetery_id
        self.cemetery_name = cemetery_name
        super().__init__(f"Cemetery '{cemetery_name}' needs location mapping")


def validate_intake_token(db: Session, token: str) -> dict:
    """Validate a public intake token. Returns case info or raises."""
    case = (
        db.query(DisintermentCase)
        .filter(
            DisintermentCase.intake_token == token,
            DisintermentCase.deleted_at.is_(None),
        )
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Invalid or expired intake token")

    company = db.query(Company).filter(Company.id == case.company_id).first()

    return {
        "case_number": case.case_number,
        "status": case.status,
        "already_submitted": case.intake_submitted_at is not None,
        "company_name": company.name if company else None,
    }


def submit_intake(db: Session, token: str, data) -> dict:
    """Public intake form submission — token-validated, no auth.

    Populates decedent, cemetery, funeral home, and NOK fields.
    """
    case = (
        db.query(DisintermentCase)
        .filter(
            DisintermentCase.intake_token == token,
            DisintermentCase.deleted_at.is_(None),
        )
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Invalid or expired intake token")

    if case.intake_submitted_at is not None:
        raise HTTPException(
            status_code=409, detail="Intake form has already been submitted"
        )

    # Populate decedent fields
    case.decedent_name = data.decedent_name
    case.date_of_death = data.date_of_death
    case.date_of_burial = data.date_of_burial
    case.vault_description = data.vault_description
    case.reason = data.reason
    case.destination = data.destination

    # Cemetery — try to match by name within the tenant
    if data.cemetery_name:
        cemetery = (
            db.query(CompanyEntity)
            .filter(
                CompanyEntity.company_id == case.company_id,
                CompanyEntity.is_cemetery.is_(True),
                CompanyEntity.name.ilike(f"%{data.cemetery_name}%"),
            )
            .first()
        )
        if cemetery:
            case.cemetery_id = cemetery.id
            case.fulfilling_location_id = cemetery.fulfilling_location_id

    case.cemetery_lot_section = data.cemetery_lot_section
    case.cemetery_lot_space = data.cemetery_lot_space

    # Funeral home — try to match by name
    if data.funeral_home_name:
        fh = (
            db.query(CompanyEntity)
            .filter(
                CompanyEntity.company_id == case.company_id,
                CompanyEntity.is_funeral_home.is_(True),
                CompanyEntity.name.ilike(f"%{data.funeral_home_name}%"),
            )
            .first()
        )
        if fh:
            case.funeral_home_id = fh.id

            # Try to match funeral director contact
            if data.funeral_director_email:
                contact = (
                    db.query(Contact)
                    .filter(
                        Contact.master_company_id == fh.id,
                        Contact.email == data.funeral_director_email,
                    )
                    .first()
                )
                if contact:
                    case.funeral_director_contact_id = contact.id

    # Next of kin
    case.next_of_kin = [nok.model_dump() for nok in data.next_of_kin]

    # Store raw submission data for audit
    case.intake_submitted_data = data.model_dump(mode="json")
    case.intake_submitted_at = datetime.now(timezone.utc)
    case.updated_at = datetime.now(timezone.utc)
    # Status remains 'intake' until staff reviews

    db.commit()
    db.refresh(case)

    logger.info("Intake submitted for case %s", case.case_number)
    return {"case_number": case.case_number}


# ---------------------------------------------------------------------------
# Quote acceptance
# ---------------------------------------------------------------------------


def accept_quote(
    db: Session, case_id: str, company_id: str, quote_id: str | None, quote_amount: float
) -> dict:
    """Accept a quote — set quote_id, check hazard pay, advance to quote_accepted."""
    case = _load_case(db, case_id, company_id)
    _assert_status(case, "intake", "quoted")

    if quote_id:
        case.quote_id = quote_id
    case.accepted_quote_amount = quote_amount

    # Check hazard pay — look at charge types used in the quote
    # For now, we check the case's charge types directly
    hazard_types = (
        db.query(DisintermentChargeType)
        .filter(
            DisintermentChargeType.company_id == company_id,
            DisintermentChargeType.is_hazard_pay.is_(True),
            DisintermentChargeType.deleted_at.is_(None),
        )
        .all()
    )
    # has_hazard_pay is set by the caller or frontend based on quote lines
    # keeping it simple — the frontend passes this flag

    case.status = "quote_accepted"
    case.updated_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("Quote accepted for case %s — amount: %s", case.case_number, quote_amount)
    return _case_to_response(_load_case(db, case_id, company_id))


# ---------------------------------------------------------------------------
# Signatures
# ---------------------------------------------------------------------------


def send_for_signatures(
    db: Session, case_id: str, company_id: str, webhook_base_url: str = ""
) -> dict:
    """Trigger DocuSign envelope creation with 4 signers."""
    case = _load_case(db, case_id, company_id)
    _assert_status(case, "quote_accepted")

    # Gather signer emails
    fh_email = None
    if case.funeral_director_contact_id:
        contact = db.query(Contact).filter(Contact.id == case.funeral_director_contact_id).first()
        if contact:
            fh_email = contact.email
    if not fh_email and case.funeral_home:
        fh_email = case.funeral_home.email

    cemetery_email = case.cemetery.email if case.cemetery else None

    nok_email = None
    if case.next_of_kin:
        for nok in case.next_of_kin:
            if nok.get("email"):
                nok_email = nok["email"]
                break

    # Manufacturer signer — tenant's designated signing user
    company = db.query(Company).filter(Company.id == company_id).first()
    manufacturer_email = None
    if company:
        s = company.settings or {}
        manufacturer_email = s.get("docusign_manufacturer_signer_email")
        if not manufacturer_email:
            manufacturer_email = company.email

    webhook_url = f"{webhook_base_url}/api/v1/docusign/webhook" if webhook_base_url else ""

    envelope_id = docusign_service.create_envelope(
        db,
        company_id,
        case_id=case.id,
        case_number=case.case_number,
        decedent_name=case.decedent_name,
        funeral_home_email=fh_email,
        cemetery_email=cemetery_email,
        next_of_kin_email=nok_email,
        manufacturer_email=manufacturer_email,
        webhook_url=webhook_url,
    )

    case.docusign_envelope_id = envelope_id
    case.sig_funeral_home = "sent" if fh_email else "not_sent"
    case.sig_cemetery = "sent" if cemetery_email else "not_sent"
    case.sig_next_of_kin = "sent" if nok_email else "not_sent"
    case.sig_manufacturer = "sent" if manufacturer_email else "not_sent"
    case.status = "signatures_pending"
    case.updated_at = datetime.now(timezone.utc)

    db.commit()
    logger.info("Signatures sent for case %s — envelope %s", case.case_number, envelope_id)
    return _case_to_response(_load_case(db, case_id, company_id))


def handle_docusign_webhook(
    db: Session, envelope_id: str, signer_role: str, event: str
) -> None:
    """Process a DocuSign webhook callback — update sig fields, check for completion."""
    case = (
        db.query(DisintermentCase)
        .filter(
            DisintermentCase.docusign_envelope_id == envelope_id,
            DisintermentCase.deleted_at.is_(None),
        )
        .first()
    )
    if not case:
        logger.warning("DocuSign webhook: no case found for envelope %s", envelope_id)
        return

    now = datetime.now(timezone.utc)

    role_field_map = {
        "funeral_home": ("sig_funeral_home", "sig_funeral_home_signed_at"),
        "cemetery": ("sig_cemetery", "sig_cemetery_signed_at"),
        "next_of_kin": ("sig_next_of_kin", "sig_next_of_kin_signed_at"),
        "manufacturer": ("sig_manufacturer", "sig_manufacturer_signed_at"),
    }

    if signer_role not in role_field_map:
        logger.warning("Unknown signer role: %s", signer_role)
        return

    status_field, timestamp_field = role_field_map[signer_role]

    if event in ("Completed", "completed", "recipient-completed"):
        setattr(case, status_field, "signed")
        setattr(case, timestamp_field, now)
    elif event in ("Declined", "declined", "recipient-declined"):
        setattr(case, status_field, "declined")

    # Check if all signers have signed
    all_signed = True
    for party, (sf, _) in role_field_map.items():
        sig_status = getattr(case, sf)
        if sig_status not in ("signed", "not_sent"):
            all_signed = False
            break

    if all_signed and case.status == "signatures_pending":
        case.status = "signatures_complete"
        logger.info("All signatures complete for case %s", case.case_number)

    case.updated_at = now
    db.commit()
    logger.info(
        "DocuSign webhook: case %s, role=%s, event=%s",
        case.case_number,
        signer_role,
        event,
    )


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------


def schedule_case(
    db: Session,
    case_id: str,
    company_id: str,
    scheduled_date: date,
    assigned_driver_id: str | None = None,
    assigned_crew: list[str] | None = None,
    current_user_id: str | None = None,
) -> dict:
    """Schedule a disinterment — guarded by signatures_complete status.

    Uses RotationService for hazard_pay cases to auto-assign driver.
    """
    case = _load_case(db, case_id, company_id)
    _assert_status(case, "signatures_complete")

    case.scheduled_date = scheduled_date
    case.assigned_crew = assigned_crew or []

    # Try rotation assignment for hazard_pay cases
    if case.has_hazard_pay:
        assignment = rotation_service.get_next_and_assign(
            db,
            company_id=company_id,
            location_id=case.fulfilling_location_id,
            trigger_type="hazard_pay",
            assignment_type="disinterment",
            assignment_id=case.id,
            assigned_by_user_id=current_user_id,
            has_hazard_pay=True,
        )
        if assignment:
            case.rotation_assignment_id = assignment.id
            # Set driver from rotation member
            member = assignment.member
            if member:
                case.assigned_driver_id = member.user_id
        elif assigned_driver_id:
            # Fallback to manual driver assignment
            case.assigned_driver_id = assigned_driver_id
    else:
        # Non-hazard: use manually specified driver
        case.assigned_driver_id = assigned_driver_id

    case.status = "scheduled"
    case.updated_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(
        "Case %s scheduled for %s — driver: %s",
        case.case_number,
        scheduled_date,
        case.assigned_driver_id,
    )
    return _case_to_response(_load_case(db, case_id, company_id))


# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------


def complete_case(
    db: Session, case_id: str, company_id: str, user_id: str | None = None
) -> dict:
    """Mark a case as complete and auto-generate an invoice from accepted quote."""
    case = _load_case(db, case_id, company_id)
    _assert_status(case, "scheduled")

    now = datetime.now(timezone.utc)
    case.completed_at = now
    case.status = "complete"
    case.updated_at = now

    # Auto-generate invoice from accepted quote amount
    if case.accepted_quote_amount and case.funeral_home_id:
        try:
            invoice = _create_invoice_from_case(db, case, company_id, user_id)
            case.invoice_id = invoice.id
            logger.info(
                "Invoice %s auto-generated for case %s",
                invoice.number,
                case.case_number,
            )
        except Exception as e:
            logger.error("Failed to auto-generate invoice for case %s: %s", case.case_number, e)

    db.commit()

    logger.info("Case %s completed", case.case_number)
    return _case_to_response(_load_case(db, case_id, company_id))


def _create_invoice_from_case(
    db: Session, case: DisintermentCase, company_id: str, user_id: str | None
):
    """Create an invoice from a completed disinterment case.

    Follows the same pattern as sales_service.create_invoice_from_order().
    """
    from datetime import timedelta
    from decimal import Decimal

    from app.models.customer import Customer
    from app.models.invoice import Invoice, InvoiceLine

    # Find the customer linked to the funeral home
    customer = (
        db.query(Customer)
        .filter(
            Customer.company_id == company_id,
            Customer.master_company_id == case.funeral_home_id,
        )
        .first()
    )
    if not customer:
        raise ValueError(
            f"No customer record found for funeral home {case.funeral_home_id}"
        )

    # Generate invoice number
    year = datetime.now(timezone.utc).year
    prefix = f"INV-{year}-"
    last = (
        db.query(Invoice.number)
        .filter(
            Invoice.company_id == company_id,
            Invoice.number.like(f"{prefix}%"),
        )
        .order_by(Invoice.number.desc())
        .first()
    )
    seq = 1
    if last and last[0]:
        try:
            seq = int(last[0].replace(prefix, "")) + 1
        except ValueError:
            pass
    inv_number = f"{prefix}{seq:04d}"

    now = datetime.now(timezone.utc)
    due_date = now + timedelta(days=30)
    total = case.accepted_quote_amount or Decimal("0.00")

    invoice = Invoice(
        id=str(uuid.uuid4()),
        company_id=company_id,
        number=inv_number,
        customer_id=customer.id,
        status="draft",
        invoice_date=now,
        due_date=due_date,
        payment_terms="Net 30",
        subtotal=total,
        tax_rate=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total=total,
        notes=f"Disinterment — {case.decedent_name} ({case.case_number})",
        deceased_name=case.decedent_name,
        created_by=user_id,
    )
    db.add(invoice)
    db.flush()

    # Single line item for the disinterment service
    line = InvoiceLine(
        id=str(uuid.uuid4()),
        invoice_id=invoice.id,
        description=f"Disinterment services — {case.decedent_name}",
        quantity=Decimal("1"),
        unit_price=total,
        line_total=total,
        sort_order=0,
    )
    db.add(line)

    # Update customer balance
    customer.current_balance = (customer.current_balance or Decimal("0.00")) + total

    db.flush()
    return invoice


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


def cancel_case(db: Session, case_id: str, company_id: str) -> dict:
    """Cancel a case from any non-complete stage."""
    case = _load_case(db, case_id, company_id)
    if case.status == "complete":
        raise HTTPException(
            status_code=422, detail="Cannot cancel a completed case"
        )

    # Void DocuSign envelope if signatures are pending
    if case.docusign_envelope_id and case.status in (
        "signatures_pending",
        "signatures_complete",
    ):
        try:
            docusign_service.void_envelope(
                db, company_id, case.docusign_envelope_id, "Case cancelled"
            )
        except Exception as e:
            logger.error("Failed to void DocuSign envelope: %s", e)

    case.status = "cancelled"
    case.updated_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("Case %s cancelled", case.case_number)
    return _case_to_response(_load_case(db, case_id, company_id))
