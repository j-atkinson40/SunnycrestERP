"""Funeral Home Case Management API routes."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_module, require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.fh_case import CremationStatusUpdate
from app.schemas.first_call import FirstCallExtractionRequest
from app.services import case_service
from app.services import fh_invoice_service
from app.services import obituary_service
from app.services import vault_order_service
from app.services import portal_service

router = APIRouter(
    dependencies=[Depends(require_module("funeral_home"))],
)


# ---------------------------------------------------------------------------
# Request / Response schemas (inline)
# ---------------------------------------------------------------------------


class FirstCallCreate(BaseModel):
    deceased_first_name: str
    deceased_last_name: str
    deceased_date_of_death: date
    deceased_place_of_death: str | None = None
    deceased_place_of_death_name: str | None = None
    primary_contact_first_name: str
    primary_contact_last_name: str
    primary_contact_phone: str
    assigned_director_id: str
    notes: str | None = None
    referred_by: str | None = None


class CaseUpdate(BaseModel):
    deceased_first_name: str | None = None
    deceased_last_name: str | None = None
    deceased_date_of_death: date | None = None
    deceased_place_of_death: str | None = None
    deceased_place_of_death_name: str | None = None
    assigned_director_id: str | None = None
    notes: str | None = None
    referred_by: str | None = None
    disposition_type: str | None = None
    service_date: date | None = None
    service_time: str | None = None
    service_location: str | None = None
    visitation_date: date | None = None
    visitation_time: str | None = None
    visitation_location: str | None = None
    cemetery_name: str | None = None
    burial_section: str | None = None
    burial_lot: str | None = None


class StatusUpdate(BaseModel):
    status: str
    notes: str | None = None


class ContactCreate(BaseModel):
    contact_type: str
    first_name: str
    last_name: str
    relationship_to_deceased: str | None = None
    phone_primary: str | None = None
    phone_secondary: str | None = None
    email: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    is_primary: bool | None = None
    receives_portal_access: bool | None = None
    notes: str | None = None


class ContactUpdate(BaseModel):
    contact_type: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    relationship_to_deceased: str | None = None
    phone_primary: str | None = None
    phone_secondary: str | None = None
    email: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    is_primary: bool | None = None
    receives_portal_access: bool | None = None
    notes: str | None = None


class ServiceCreate(BaseModel):
    service_code: str | None = None
    service_name: str
    service_category: str
    description: str | None = None
    quantity: float
    unit_price: float
    is_required: bool | None = None
    notes: str | None = None


class ServiceUpdate(BaseModel):
    service_code: str | None = None
    service_name: str | None = None
    service_category: str | None = None
    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    is_required: bool | None = None
    notes: str | None = None


class BulkServiceAdd(BaseModel):
    item_codes: list[str]


class PaymentCreate(BaseModel):
    payment_date: date
    amount: float
    payment_method: str
    reference_number: str | None = None
    notes: str | None = None


class InvoiceSend(BaseModel):
    email: str


class ObituaryGenerate(BaseModel):
    surviving_family: str | None = None
    education: str | None = None
    career: str | None = None
    military_service: str | None = None
    hobbies: str | None = None
    faith: str | None = None
    accomplishments: str | None = None
    special_memories: str | None = None
    tone_preference: str | None = "warm"


class ObituarySave(BaseModel):
    content: str


class ObituaryApprovalSend(BaseModel):
    contact_id: str


class ObituaryPublish(BaseModel):
    locations: list[str]


class VaultOrderCreate(BaseModel):
    manufacturer_tenant_id: str
    vault_product_id: str
    vault_product_name: str
    vault_product_sku: str | None = None
    quantity: int = 1
    unit_price: float
    requested_delivery_date: date
    delivery_address: str
    delivery_contact_name: str
    delivery_contact_phone: str
    special_instructions: str | None = None


class DocumentCreate(BaseModel):
    document_type: str
    document_name: str
    file_url: str
    notes: str | None = None


# ---------------------------------------------------------------------------
# Cases — list & create (literal paths before parameterized)
# ---------------------------------------------------------------------------


@router.get("/")
def list_cases(
    status: str | None = None,
    assigned_director_id: str | None = None,
    service_date_from: date | None = None,
    service_date_to: date | None = None,
    disposition_type: str | None = None,
    search: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_cases.view")),
):
    """List cases with optional filters."""
    return case_service.list_cases(
        db,
        current_user.company_id,
        status=status,
        assigned_director_id=assigned_director_id,
        service_date_from=service_date_from,
        service_date_to=service_date_to,
        disposition_type=disposition_type,
        search=search,
        skip=skip,
        limit=limit,
    )


@router.post("/", status_code=201)
def create_case(
    data: FirstCallCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_cases.create")),
):
    """Create a new case from first call information."""
    return case_service.create_from_first_call(
        db,
        current_user.company_id,
        data.model_dump(exclude_none=True),
        current_user.id,
    )


@router.get("/board")
def get_case_board(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_cases.view")),
):
    """Get kanban board view of active cases."""
    return case_service.get_case_board(db, current_user.company_id)


# ---------------------------------------------------------------------------
# First Call AI extraction (literal path — before /cases/{case_id})
# ---------------------------------------------------------------------------


@router.post("/extract-first-call")
def extract_first_call_endpoint(
    data: FirstCallExtractionRequest,
    current_user: User = Depends(get_current_user),
):
    """Extract structured first call data from natural language text."""
    import logging
    import traceback
    logger = logging.getLogger("first_call_extraction")

    try:
        from app.services.first_call_extraction_service import extract_first_call
        result = extract_first_call(data.text, data.existing_values)
        return result
    except Exception as e:
        # Capture full error chain
        root = e
        while root.__cause__ or root.__context__:
            root = root.__cause__ or root.__context__
        detail = f"{type(e).__name__}: {e} | Root: {type(root).__name__}: {root}"
        logger.error(f"First call extraction failed: {detail}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=detail)


# ---------------------------------------------------------------------------
# Vault catalog routes (literal paths — before /cases/{case_id})
# ---------------------------------------------------------------------------


@router.get("/vault-orders/manufacturer-catalog")
def get_manufacturer_catalog(
    manufacturer_tenant_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_vault_orders.view")),
):
    """Browse manufacturer product catalog."""
    return vault_order_service.get_manufacturer_catalog(
        db, current_user.company_id, manufacturer_tenant_id
    )


@router.get("/vault-orders/manufacturers")
def list_manufacturers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_vault_orders.view")),
):
    """List linked manufacturer relationships."""
    return vault_order_service.get_manufacturer_relationships(
        db, current_user.company_id
    )


@router.post("/vault-orders/manufacturers", status_code=201)
def link_manufacturer(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_vault_orders.create")),
):
    """Link a manufacturer relationship."""
    return vault_order_service.create_manufacturer_relationship(
        db, current_user.company_id, data
    )


# ---------------------------------------------------------------------------
# Case detail & actions (parameterized — after literal paths)
# ---------------------------------------------------------------------------


@router.get("/{case_id}")
def get_case(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_cases.view")),
):
    """Get full case summary."""
    result = case_service.get_case_summary(db, current_user.company_id, case_id)
    if not result:
        raise HTTPException(status_code=404, detail="Case not found")
    return result


@router.patch("/{case_id}")
def update_case(
    case_id: str,
    data: CaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_cases.edit")),
):
    """Update case details."""
    case = case_service.get_case(db, current_user.company_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    updates = data.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(case, key, value)
    db.commit()
    db.refresh(case)
    return case


@router.patch("/{case_id}/status")
def update_case_status(
    case_id: str,
    data: StatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_cases.edit")),
):
    """Transition case status."""
    result = case_service.update_status(
        db,
        current_user.company_id,
        case_id,
        data.status,
        current_user.id,
        notes=data.notes,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Case not found")
    return result


@router.patch("/{case_id}/cremation")
def update_cremation_status(
    case_id: str,
    data: CremationStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_cases.edit")),
):
    """Update cremation tracking fields on a case."""
    case = case_service.get_case(db, current_user.company_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    updates = data.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(case, key, value)
    # Convert date objects to strings for JSON-safe metadata
    meta = {k: v.isoformat() if isinstance(v, date) else v for k, v in updates.items()}
    case_service.log_activity(
        db,
        current_user.company_id,
        case_id,
        activity_type="cremation_updated",
        description=f"Cremation details updated: {', '.join(updates.keys())}",
        performed_by=current_user.id,
        metadata=meta,
    )
    db.commit()
    db.refresh(case)
    return case


@router.get("/{case_id}/activity")
def get_case_activity(
    case_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_cases.view")),
):
    """Get case activity timeline."""
    return case_service.get_activity(
        db, current_user.company_id, case_id, skip=skip, limit=limit
    )


# ---------------------------------------------------------------------------
# Contacts (nested under case)
# ---------------------------------------------------------------------------


@router.get("/{case_id}/contacts")
def list_contacts(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_cases.view")),
):
    """List contacts for a case."""
    return case_service.list_contacts(db, current_user.company_id, case_id)


@router.post("/{case_id}/contacts", status_code=201)
def add_contact(
    case_id: str,
    data: ContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_cases.edit")),
):
    """Add a contact to a case."""
    return case_service.add_contact(
        db,
        current_user.company_id,
        case_id,
        data.model_dump(exclude_none=True),
        current_user.id,
    )


@router.put("/{case_id}/contacts/{contact_id}")
def update_contact(
    case_id: str,
    contact_id: str,
    data: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_cases.edit")),
):
    """Update a case contact."""
    result = case_service.update_contact(
        db,
        current_user.company_id,
        case_id,
        contact_id,
        data.model_dump(exclude_none=True),
    )
    if not result:
        raise HTTPException(status_code=404, detail="Contact not found")
    return result


@router.post("/{case_id}/contacts/{contact_id}/send-portal-invite")
def send_portal_invite(
    case_id: str,
    contact_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_portal.manage")),
):
    """Generate and send a portal access link to a contact."""
    token = portal_service.generate_access_link(
        db, current_user.company_id, case_id, contact_id, current_user.id
    )
    return {"token": token, "detail": "Portal invite sent"}


# ---------------------------------------------------------------------------
# Services (nested under case)
# ---------------------------------------------------------------------------


@router.get("/{case_id}/services")
def list_services(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_cases.view")),
):
    """List services on a case."""
    return fh_invoice_service.list_services(db, current_user.company_id, case_id)


@router.post("/{case_id}/services", status_code=201)
def add_service(
    case_id: str,
    data: ServiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_cases.edit")),
):
    """Add a service to a case."""
    return fh_invoice_service.add_service_to_case(
        db,
        current_user.company_id,
        case_id,
        data.model_dump(exclude_none=True),
        current_user.id,
    )


@router.post("/{case_id}/services/bulk", status_code=201)
def bulk_add_services(
    case_id: str,
    data: BulkServiceAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_cases.edit")),
):
    """Bulk add services from price list item codes."""
    return fh_invoice_service.add_services_from_price_list(
        db, current_user.company_id, case_id, data.item_codes, current_user.id
    )


@router.put("/{case_id}/services/{service_id}")
def update_service(
    case_id: str,
    service_id: str,
    data: ServiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_cases.edit")),
):
    """Update a service on a case."""
    result = fh_invoice_service.update_service(
        db,
        current_user.company_id,
        case_id,
        service_id,
        data.model_dump(exclude_none=True),
    )
    if not result:
        raise HTTPException(status_code=404, detail="Service not found")
    return result


@router.delete("/{case_id}/services/{service_id}", status_code=204)
def remove_service(
    case_id: str,
    service_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_cases.edit")),
):
    """Remove a service from a case."""
    fh_invoice_service.remove_service(db, current_user.company_id, case_id, service_id)


# ---------------------------------------------------------------------------
# Vault Order (nested under case)
# ---------------------------------------------------------------------------


@router.get("/{case_id}/vault-order")
def get_vault_order(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_vault_orders.view")),
):
    """Get vault order for a case."""
    result = vault_order_service.get_vault_order(
        db, current_user.company_id, case_id
    )
    if not result:
        raise HTTPException(status_code=404, detail="Vault order not found")
    return result


@router.post("/{case_id}/vault-order", status_code=201)
def submit_vault_order(
    case_id: str,
    data: VaultOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_vault_orders.create")),
):
    """Submit a vault order for a case."""
    return vault_order_service.submit_vault_order(
        db,
        current_user.company_id,
        case_id,
        data.model_dump(exclude_none=True),
        current_user.id,
    )


@router.patch("/{case_id}/vault-order/sync")
def sync_vault_order(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_vault_orders.view")),
):
    """Sync vault order status from manufacturer."""
    order = vault_order_service.get_vault_order(
        db, current_user.company_id, case_id
    )
    if not order:
        raise HTTPException(status_code=404, detail="Vault order not found")
    return vault_order_service.sync_vault_order_status(
        db, current_user.company_id, order.id
    )


# ---------------------------------------------------------------------------
# Obituary (nested under case)
# ---------------------------------------------------------------------------


@router.get("/{case_id}/obituary")
def get_obituary(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_obituaries.view")),
):
    """Get obituary for a case."""
    result = obituary_service.get_obituary(db, current_user.company_id, case_id)
    if not result:
        raise HTTPException(status_code=404, detail="Obituary not found")
    return result


@router.post("/{case_id}/obituary/generate", status_code=201)
def generate_obituary(
    case_id: str,
    data: ObituaryGenerate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_obituaries.create")),
):
    """Generate obituary with AI from biographical data."""
    return obituary_service.generate_with_ai(
        db,
        current_user.company_id,
        case_id,
        data.model_dump(exclude_none=True),
        current_user.id,
    )


@router.put("/{case_id}/obituary")
def save_obituary(
    case_id: str,
    data: ObituarySave,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_obituaries.edit")),
):
    """Save edited obituary content."""
    return obituary_service.save_obituary(
        db, current_user.company_id, case_id, data.content, current_user.id
    )


@router.post("/{case_id}/obituary/send-for-approval")
def send_obituary_for_approval(
    case_id: str,
    data: ObituaryApprovalSend,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_obituaries.edit")),
):
    """Send obituary to family contact for approval."""
    return obituary_service.send_for_family_approval(
        db, current_user.company_id, case_id, data.contact_id, current_user.id
    )


@router.post("/{case_id}/obituary/publish")
def publish_obituary(
    case_id: str,
    data: ObituaryPublish,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_obituaries.edit")),
):
    """Mark obituary as published to specified locations."""
    return obituary_service.mark_published(
        db, current_user.company_id, case_id, data.locations, current_user.id
    )


# ---------------------------------------------------------------------------
# Invoice (nested under case)
# ---------------------------------------------------------------------------


@router.get("/{case_id}/invoice")
def get_invoice(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_invoices.view")),
):
    """Get invoice for a case."""
    result = fh_invoice_service.get_invoice(db, current_user.company_id, case_id)
    if not result:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return result


@router.post("/{case_id}/invoice/generate", status_code=201)
def generate_invoice(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_invoices.create")),
):
    """Generate invoice from case services."""
    return fh_invoice_service.generate_from_case(
        db, current_user.company_id, case_id, current_user.id
    )


@router.post("/{case_id}/invoice/send")
def send_invoice(
    case_id: str,
    data: InvoiceSend,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_invoices.edit")),
):
    """Send invoice to family via email."""
    fh_invoice_service.send_invoice(
        db, current_user.company_id, case_id, data.email, current_user.id
    )
    return {"detail": "Invoice sent"}


@router.post("/{case_id}/invoice/payments", status_code=201)
def record_payment(
    case_id: str,
    data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_invoices.edit")),
):
    """Record a payment on a case invoice."""
    return fh_invoice_service.record_payment(
        db,
        current_user.company_id,
        case_id,
        data.model_dump(exclude_none=True),
        current_user.id,
    )


@router.post("/{case_id}/invoice/void")
def void_invoice(
    case_id: str,
    data: dict | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_invoices.void")),
):
    """Void a case invoice."""
    reason = data.get("reason") if data else None
    fh_invoice_service.void_invoice(
        db, current_user.company_id, case_id, current_user.id, reason
    )
    return {"detail": "Invoice voided"}


@router.get("/{case_id}/payments")
def list_payments(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_invoices.view")),
):
    """List payments for a case."""
    return fh_invoice_service.get_payments(db, current_user.company_id, case_id)


# ---------------------------------------------------------------------------
# Documents (nested under case)
# ---------------------------------------------------------------------------


@router.post("/{case_id}/documents", status_code=201)
def upload_document(
    case_id: str,
    data: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_cases.edit")),
):
    """Upload a document to a case."""
    case_service.log_activity(
        db,
        current_user.company_id,
        case_id,
        activity_type="document_uploaded",
        description=f"Document uploaded: {data.document_name}",
        performed_by=current_user.id,
        metadata=data.model_dump(),
    )
    return {"detail": "Document uploaded", "document_name": data.document_name}
