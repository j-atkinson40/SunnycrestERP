"""Family portal service — secure access for case contacts."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.fh_portal_session import FHPortalSession
from app.models.fh_case import FHCase
from app.models.fh_case_contact import FHCaseContact
from app.models.fh_obituary import FHObituary
from app.models.fh_vault_order import FHVaultOrder
from app.models.fh_invoice import FHInvoice
from app.models.fh_document import FHDocument
from app.models.company import Company
from app.services.case_service import log_activity


# ---------------------------------------------------------------------------
# Portal session management
# ---------------------------------------------------------------------------

def generate_access_link(
    db: Session,
    tenant_id: str,
    case_id: str,
    contact_id: str,
    performed_by_id: str,
) -> str:
    """Create portal session with secure random token.

    Returns the access token (caller constructs the URL).
    """
    # Verify case and contact
    case = (
        db.query(FHCase)
        .filter(FHCase.id == case_id, FHCase.company_id == tenant_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

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

    # Invalidate any existing session for this contact/case
    existing = (
        db.query(FHPortalSession)
        .filter(
            FHPortalSession.case_id == case_id,
            FHPortalSession.contact_id == contact_id,
        )
        .first()
    )
    if existing:
        db.delete(existing)
        db.flush()

    token = secrets.token_urlsafe(48)
    session = FHPortalSession(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        case_id=case_id,
        contact_id=contact_id,
        access_token=token,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db.add(session)

    # Update contact
    contact.portal_invite_sent_at = datetime.now(UTC)

    log_activity(
        db,
        tenant_id,
        case_id,
        "portal_link_generated",
        f"Portal access link generated for {contact.first_name} {contact.last_name}",
        performed_by=performed_by_id,
        metadata={"contact_id": contact_id},
    )

    db.commit()
    return token


def validate_token(
    db: Session, token: str
) -> tuple[FHCase, FHCaseContact, FHPortalSession] | None:
    """Validate portal access token.

    Returns (case, contact, portal_session) if valid.
    Extends expiration by 7 days on each access.
    Updates last_accessed_at.
    Returns None if expired or not found.
    """
    session = (
        db.query(FHPortalSession)
        .filter(FHPortalSession.access_token == token)
        .first()
    )
    if not session:
        return None

    now = datetime.now(UTC)
    if session.expires_at and session.expires_at < now:
        return None

    # Load case and contact
    case = db.query(FHCase).filter(FHCase.id == session.case_id).first()
    contact = db.query(FHCaseContact).filter(FHCaseContact.id == session.contact_id).first()

    if not case or not contact:
        return None

    # Extend expiration and update access time
    session.expires_at = now + timedelta(days=7)
    session.last_accessed_at = now
    contact.portal_last_login_at = now

    db.commit()
    return (case, contact, session)


def get_portal_data(db: Session, case_id: str, contact_id: str) -> dict:
    """Get filtered case data appropriate for family view.

    Returns safe subset: no internal pricing details on vault orders.
    """
    case = db.query(FHCase).filter(FHCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Funeral home name
    company = db.query(Company).filter(Company.id == case.company_id).first()

    # Obituary
    obituary = (
        db.query(FHObituary)
        .filter(FHObituary.case_id == case_id, FHObituary.company_id == case.company_id)
        .first()
    )

    # Vault order (simplified - NO pricing info)
    vault_order = (
        db.query(FHVaultOrder)
        .filter(FHVaultOrder.case_id == case_id, FHVaultOrder.company_id == case.company_id)
        .first()
    )
    vault_status = None
    if vault_order:
        # Simplify status for family
        simple_map = {
            "draft": "ordered",
            "submitted": "ordered",
            "confirmed": "confirmed",
            "in_production": "confirmed",
            "ready": "confirmed",
            "scheduled_for_delivery": "confirmed",
            "delivered": "delivered",
            "cancelled": "cancelled",
        }
        vault_status = simple_map.get(vault_order.status, vault_order.status)

    # Invoice (totals only)
    invoice = (
        db.query(FHInvoice)
        .filter(FHInvoice.case_id == case_id, FHInvoice.company_id == case.company_id)
        .first()
    )
    invoice_data = None
    if invoice and invoice.status != "void":
        invoice_data = {
            "total": str(invoice.total_amount) if invoice.total_amount else None,
            "amount_paid": str(invoice.amount_paid) if invoice.amount_paid else None,
            "balance_due": str(invoice.balance_due) if invoice.balance_due else None,
            "status": invoice.status,
        }

    # Documents shared with family
    documents = (
        db.query(FHDocument)
        .filter(FHDocument.case_id == case_id, FHDocument.company_id == case.company_id)
        .all()
    )

    return {
        "deceased": {
            "first_name": case.deceased_first_name,
            "middle_name": case.deceased_middle_name,
            "last_name": case.deceased_last_name,
            "date_of_birth": str(case.deceased_date_of_birth) if case.deceased_date_of_birth else None,
            "date_of_death": str(case.deceased_date_of_death) if case.deceased_date_of_death else None,
        },
        "service": {
            "date": str(case.service_date) if case.service_date else None,
            "time": case.service_time,
            "location": case.service_location,
            "type": case.service_type,
        },
        "visitation": {
            "date": str(case.visitation_date) if case.visitation_date else None,
            "start_time": case.visitation_start_time,
            "end_time": case.visitation_end_time,
            "location": case.visitation_location,
        } if case.visitation_date else None,
        "obituary": {
            "content": obituary.content if obituary else None,
            "status": obituary.status if obituary else None,
            "can_approve": (
                obituary.status == "pending_family_approval" if obituary else False
            ),
        },
        "vault_status": vault_status,
        "invoice": invoice_data,
        "documents": [
            {
                "id": doc.id,
                "document_type": doc.document_type,
                "document_name": doc.document_name,
                "file_url": doc.file_url,
            }
            for doc in documents
        ],
        "funeral_home": company.name if company else None,
    }


def submit_obituary_approval(
    db: Session,
    token: str,
    approved: bool,
    change_notes: str | None = None,
) -> dict:
    """Process family's obituary response via portal."""
    result = validate_token(db, token)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired portal token")

    case, contact, session = result

    from app.services.obituary_service import approve, request_changes

    if approved:
        obituary = approve(db, case.company_id, case.id, contact.id)
        return {"status": "approved", "message": "Thank you for approving the obituary."}
    else:
        if not change_notes:
            raise HTTPException(
                status_code=400,
                detail="Please provide notes describing the changes you'd like.",
            )
        obituary = request_changes(db, case.company_id, case.id, contact.id, change_notes)
        return {
            "status": "changes_requested",
            "message": "Your change request has been submitted to the funeral director.",
        }


def submit_message(db: Session, token: str, message_text: str) -> dict:
    """Family sends message to director. Creates activity log entry."""
    result = validate_token(db, token)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired portal token")

    case, contact, session = result

    log_activity(
        db,
        case.company_id,
        case.id,
        "portal_message",
        f"Message from {contact.first_name} {contact.last_name}: {message_text}",
        metadata={
            "contact_id": contact.id,
            "message": message_text,
            "source": "family_portal",
        },
    )

    db.commit()
    return {"status": "sent", "message": "Your message has been sent to the funeral director."}


def upload_portal_document(
    db: Session,
    token: str,
    document_type: str,
    document_name: str,
    file_url: str,
) -> dict:
    """Family uploads document via portal. Creates FHDocument record."""
    result = validate_token(db, token)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired portal token")

    case, contact, session = result

    doc = FHDocument(
        id=str(uuid.uuid4()),
        company_id=case.company_id,
        case_id=case.id,
        document_type=document_type,
        document_name=document_name,
        file_url=file_url,
        uploaded_by=contact.id,
        notes=f"Uploaded via family portal by {contact.first_name} {contact.last_name}",
    )
    db.add(doc)

    log_activity(
        db,
        case.company_id,
        case.id,
        "document_uploaded",
        f"Document '{document_name}' uploaded via portal by {contact.first_name} {contact.last_name}",
        metadata={
            "document_type": document_type,
            "document_name": document_name,
            "contact_id": contact.id,
            "source": "family_portal",
        },
    )

    db.commit()
    db.refresh(doc)
    return {
        "id": doc.id,
        "document_type": doc.document_type,
        "document_name": doc.document_name,
        "status": "uploaded",
    }
