"""Funeral home invoice and services management."""

import uuid
from datetime import UTC, datetime, date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.models.fh_invoice import FHInvoice
from app.models.fh_payment import FHPayment
from app.models.fh_service import FHService
from app.models.fh_case import FHCase
from app.models.fh_price_list import FHPriceListItem
from app.services.case_service import log_activity, update_status

# ---------------------------------------------------------------------------
# Invoice number generation
# ---------------------------------------------------------------------------

def _next_invoice_number(db: Session, company_id: str) -> str:
    """Generate next INV-YYYY-NNNN invoice number."""
    year = datetime.now(UTC).year
    prefix = f"INV-{year}-"
    count = (
        db.query(sa_func.count(FHInvoice.id))
        .filter(
            FHInvoice.company_id == company_id,
            FHInvoice.invoice_number.like(f"{prefix}%"),
        )
        .scalar()
    )
    return f"{prefix}{(count or 0) + 1:04d}"


# ---------------------------------------------------------------------------
# Invoice operations
# ---------------------------------------------------------------------------

def generate_from_case(
    db: Session,
    tenant_id: str,
    case_id: str,
    performed_by_id: str,
) -> FHInvoice:
    """Generate invoice from all selected fh_services records.

    1. Query all FHService where case_id and is_selected=True
    2. Calculate subtotal
    3. Calculate tax_amount (0 for now -- funeral services often tax-exempt)
    4. Create FHInvoice with auto-generated number
    5. Update case status to 'pending_invoice' if currently 'services_complete'
    6. Log activity
    7. Return invoice
    """
    # Verify case exists
    case = (
        db.query(FHCase)
        .filter(FHCase.id == case_id, FHCase.company_id == tenant_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Check for existing invoice
    existing = (
        db.query(FHInvoice)
        .filter(
            FHInvoice.case_id == case_id,
            FHInvoice.company_id == tenant_id,
            FHInvoice.status != "void",
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="An active invoice already exists for this case",
        )

    # Get selected services
    services = (
        db.query(FHService)
        .filter(
            FHService.case_id == case_id,
            FHService.company_id == tenant_id,
            FHService.is_selected.is_(True),
        )
        .all()
    )
    if not services:
        raise HTTPException(
            status_code=400,
            detail="No services selected for this case",
        )

    # Calculate totals
    subtotal = sum(
        (s.extended_price or Decimal("0.00")) for s in services
    )
    tax_amount = Decimal("0.00")  # Funeral services typically tax-exempt
    total_amount = subtotal + tax_amount

    invoice = FHInvoice(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        case_id=case_id,
        invoice_number=_next_invoice_number(db, tenant_id),
        status="draft",
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total_amount,
        amount_paid=Decimal("0.00"),
        balance_due=total_amount,
        due_date=date.today(),
        notes=None,
    )
    db.add(invoice)

    # Attempt to transition case status
    if case.status == "services_complete":
        case.status = "pending_invoice"
        case.updated_at = datetime.now(UTC)

    log_activity(
        db,
        tenant_id,
        case_id,
        "invoice_generated",
        f"Invoice {invoice.invoice_number} generated for ${total_amount:.2f}",
        performed_by=performed_by_id,
        metadata={"invoice_number": invoice.invoice_number, "total": str(total_amount)},
    )

    db.commit()
    db.refresh(invoice)
    return invoice


def get_invoice(db: Session, tenant_id: str, case_id: str) -> FHInvoice | None:
    """Get invoice for case with payments."""
    return (
        db.query(FHInvoice)
        .filter(
            FHInvoice.case_id == case_id,
            FHInvoice.company_id == tenant_id,
        )
        .first()
    )


def send_invoice(
    db: Session,
    tenant_id: str,
    case_id: str,
    email: str,
    performed_by_id: str,
) -> FHInvoice:
    """Mark invoice as sent. Update case status to 'invoiced'."""
    invoice = get_invoice(db, tenant_id, case_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status == "void":
        raise HTTPException(status_code=400, detail="Cannot send a voided invoice")

    invoice.status = "sent"
    invoice.sent_at = datetime.now(UTC)
    invoice.sent_to_email = email

    # Update case status
    case = (
        db.query(FHCase)
        .filter(FHCase.id == case_id, FHCase.company_id == tenant_id)
        .first()
    )
    if case and case.status == "pending_invoice":
        case.status = "invoiced"
        case.updated_at = datetime.now(UTC)

    log_activity(
        db,
        tenant_id,
        case_id,
        "invoice_sent",
        f"Invoice {invoice.invoice_number} sent to {email}",
        performed_by=performed_by_id,
        metadata={"email": email, "invoice_number": invoice.invoice_number},
    )

    db.commit()
    db.refresh(invoice)
    return invoice


def record_payment(
    db: Session,
    tenant_id: str,
    case_id: str,
    data: dict,
    performed_by_id: str,
) -> FHPayment:
    """Record payment against invoice.

    1. Create FHPayment record
    2. Update invoice amounts
    3. If fully paid: auto-transition case to 'closed'
    """
    invoice = get_invoice(db, tenant_id, case_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status == "void":
        raise HTTPException(status_code=400, detail="Cannot apply payment to a voided invoice")

    amount = Decimal(str(data["amount"]))
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be positive")

    payment = FHPayment(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        case_id=case_id,
        invoice_id=invoice.id,
        payment_date=data.get("payment_date", date.today()),
        amount=amount,
        payment_method=data.get("payment_method"),
        reference_number=data.get("reference_number"),
        received_by=performed_by_id,
        notes=data.get("notes"),
    )
    db.add(payment)

    # Update invoice
    invoice.amount_paid = (invoice.amount_paid or Decimal("0.00")) + amount
    invoice.balance_due = (invoice.total_amount or Decimal("0.00")) - invoice.amount_paid

    if invoice.balance_due <= Decimal("0.00"):
        invoice.status = "paid"
        invoice.balance_due = Decimal("0.00")
    elif invoice.amount_paid > Decimal("0.00"):
        invoice.status = "partially_paid"

    log_activity(
        db,
        tenant_id,
        case_id,
        "payment_received",
        f"Payment of ${amount:.2f} received ({data.get('payment_method', 'N/A')})",
        performed_by=performed_by_id,
        metadata={
            "amount": str(amount),
            "payment_method": data.get("payment_method"),
            "reference_number": data.get("reference_number"),
        },
    )

    # Auto-close case if fully paid
    if invoice.status == "paid":
        case = (
            db.query(FHCase)
            .filter(FHCase.id == case_id, FHCase.company_id == tenant_id)
            .first()
        )
        if case and case.status == "invoiced":
            case.status = "closed"
            case.closed_at = datetime.now(UTC)
            case.updated_at = datetime.now(UTC)

            log_activity(
                db,
                tenant_id,
                case_id,
                "case_closed",
                "Case automatically closed after full payment received",
                performed_by=performed_by_id,
            )

    db.commit()
    db.refresh(payment)
    return payment


def void_invoice(
    db: Session,
    tenant_id: str,
    case_id: str,
    performed_by_id: str,
    reason: str | None = None,
) -> FHInvoice:
    """Void invoice."""
    invoice = get_invoice(db, tenant_id, case_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status == "paid":
        raise HTTPException(status_code=400, detail="Cannot void a fully paid invoice")

    invoice.status = "void"

    log_activity(
        db,
        tenant_id,
        case_id,
        "invoice_voided",
        f"Invoice {invoice.invoice_number} voided" + (f": {reason}" if reason else ""),
        performed_by=performed_by_id,
        metadata={"reason": reason, "invoice_number": invoice.invoice_number},
    )

    db.commit()
    db.refresh(invoice)
    return invoice


def get_payments(db: Session, tenant_id: str, case_id: str) -> list[FHPayment]:
    """List all payments for a case."""
    return (
        db.query(FHPayment)
        .filter(FHPayment.case_id == case_id, FHPayment.company_id == tenant_id)
        .order_by(FHPayment.payment_date.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# Services management
# ---------------------------------------------------------------------------

def add_service_to_case(
    db: Session,
    tenant_id: str,
    case_id: str,
    data: dict,
    performed_by_id: str,
) -> FHService:
    """Add a service line item to a case from price list or custom."""
    # Verify case exists
    case = (
        db.query(FHCase)
        .filter(FHCase.id == case_id, FHCase.company_id == tenant_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    quantity = Decimal(str(data.get("quantity", 1)))
    unit_price = Decimal(str(data.get("unit_price", "0.00")))
    extended_price = quantity * unit_price

    # Get max sort order
    max_sort = (
        db.query(sa_func.max(FHService.sort_order))
        .filter(FHService.case_id == case_id, FHService.company_id == tenant_id)
        .scalar()
    ) or 0

    service = FHService(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        case_id=case_id,
        service_category=data.get("service_category"),
        service_code=data.get("service_code"),
        service_name=data["service_name"],
        description=data.get("description"),
        quantity=quantity,
        unit_price=unit_price,
        extended_price=extended_price,
        is_required=data.get("is_required", False),
        is_selected=data.get("is_selected", True),
        is_package_item=data.get("is_package_item", False),
        package_id=data.get("package_id"),
        notes=data.get("notes"),
        sort_order=data.get("sort_order", max_sort + 10),
    )
    db.add(service)

    log_activity(
        db,
        tenant_id,
        case_id,
        "services_selected",
        f"Service added: {data['service_name']} (${extended_price:.2f})",
        performed_by=performed_by_id,
    )

    db.commit()
    db.refresh(service)
    return service


def update_service(
    db: Session,
    tenant_id: str,
    case_id: str,
    service_id: str,
    data: dict,
) -> FHService:
    """Update service quantity, price, selection. Recalculate extended_price."""
    service = (
        db.query(FHService)
        .filter(
            FHService.id == service_id,
            FHService.case_id == case_id,
            FHService.company_id == tenant_id,
        )
        .first()
    )
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    updatable_fields = (
        "service_category", "service_code", "service_name", "description",
        "quantity", "unit_price", "is_selected", "is_package_item",
        "package_id", "notes", "sort_order",
    )
    for key in updatable_fields:
        if key in data:
            if key in ("quantity", "unit_price"):
                setattr(service, key, Decimal(str(data[key])))
            else:
                setattr(service, key, data[key])

    # Recalculate extended price
    service.extended_price = (service.quantity or Decimal("1")) * (service.unit_price or Decimal("0.00"))

    db.commit()
    db.refresh(service)
    return service


def remove_service(
    db: Session,
    tenant_id: str,
    case_id: str,
    service_id: str,
) -> None:
    """Remove service if not is_required. Raise error if required by law."""
    service = (
        db.query(FHService)
        .filter(
            FHService.id == service_id,
            FHService.case_id == case_id,
            FHService.company_id == tenant_id,
        )
        .first()
    )
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    if service.is_required:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove a required service item",
        )

    db.delete(service)
    db.commit()


def list_services(db: Session, tenant_id: str, case_id: str) -> list[FHService]:
    """List all services for a case, ordered by sort_order."""
    return (
        db.query(FHService)
        .filter(FHService.case_id == case_id, FHService.company_id == tenant_id)
        .order_by(FHService.sort_order, FHService.service_name)
        .all()
    )


def add_services_from_price_list(
    db: Session,
    tenant_id: str,
    case_id: str,
    item_codes: list[str],
    performed_by_id: str,
) -> list[FHService]:
    """Bulk add services from price list item codes."""
    # Verify case exists
    case = (
        db.query(FHCase)
        .filter(FHCase.id == case_id, FHCase.company_id == tenant_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Get price list items
    price_items = (
        db.query(FHPriceListItem)
        .filter(
            FHPriceListItem.company_id == tenant_id,
            FHPriceListItem.item_code.in_(item_codes),
            FHPriceListItem.is_active.is_(True),
        )
        .all()
    )

    if not price_items:
        raise HTTPException(status_code=404, detail="No matching price list items found")

    # Get max sort order
    max_sort = (
        db.query(sa_func.max(FHService.sort_order))
        .filter(FHService.case_id == case_id, FHService.company_id == tenant_id)
        .scalar()
    ) or 0

    created = []
    for idx, pi in enumerate(price_items):
        quantity = Decimal("1")
        extended_price = quantity * (pi.unit_price or Decimal("0.00"))

        service = FHService(
            id=str(uuid.uuid4()),
            company_id=tenant_id,
            case_id=case_id,
            service_category=pi.category,
            service_code=pi.item_code,
            service_name=pi.item_name,
            description=pi.description,
            quantity=quantity,
            unit_price=pi.unit_price or Decimal("0.00"),
            extended_price=extended_price,
            is_required=pi.is_required_by_law or False,
            is_selected=True,
            is_package_item=False,
            notes=None,
            sort_order=max_sort + ((idx + 1) * 10),
        )
        db.add(service)
        created.append(service)

    if created:
        log_activity(
            db,
            tenant_id,
            case_id,
            "services_selected",
            f"{len(created)} services added from price list",
            performed_by=performed_by_id,
            metadata={"item_codes": item_codes},
        )

    db.commit()
    for s in created:
        db.refresh(s)
    return created
