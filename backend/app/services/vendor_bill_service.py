"""Service layer for Vendor Bills — CRUD, approval, PO linking, status management."""

import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_line import PurchaseOrderLine
from app.models.vendor import Vendor
from app.models.vendor_bill import VendorBill
from app.models.vendor_bill_line import VendorBillLine
from app.services import audit_service


# ---------------------------------------------------------------------------
# Bill number generation (BILL-YYYY-####)
# ---------------------------------------------------------------------------


def _next_bill_number(db: Session, company_id: str) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"BILL-{year}-"
    last = (
        db.query(VendorBill.number)
        .filter(
            VendorBill.company_id == company_id,
            VendorBill.number.like(f"{prefix}%"),
        )
        .order_by(VendorBill.number.desc())
        .first()
    )
    if last and last[0]:
        try:
            seq = int(last[0].replace(prefix, "")) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


def _active_filter():
    return VendorBill.deleted_at.is_(None)


def _parse_payment_terms_days(terms: str | None) -> int | None:
    """Extract number of days from payment terms like 'Net 30'."""
    if not terms:
        return None
    match = re.search(r"(\d+)", terms)
    return int(match.group(1)) if match else None


def _recalc_bill_totals(bill: VendorBill) -> None:
    """Recalculate subtotal & total from non-deleted lines."""
    subtotal = Decimal("0.00")
    for line in bill.lines:
        if line.deleted_at is None:
            subtotal += line.amount
    bill.subtotal = subtotal
    bill.total = subtotal + (bill.tax_amount or Decimal("0.00"))


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def get_vendor_bills(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
    status: str | None = None,
    vendor_id: str | None = None,
    due_from: str | None = None,
    due_to: str | None = None,
) -> dict:
    query = db.query(VendorBill).filter(
        VendorBill.company_id == company_id, _active_filter()
    )
    if search:
        term = f"%{search}%"
        query = query.filter(
            (VendorBill.number.ilike(term))
            | (VendorBill.vendor_invoice_number.ilike(term))
        )
    if status:
        query = query.filter(VendorBill.status == status)
    if vendor_id:
        query = query.filter(VendorBill.vendor_id == vendor_id)
    if due_from:
        query = query.filter(VendorBill.due_date >= due_from)
    if due_to:
        query = query.filter(VendorBill.due_date <= due_to)

    total = query.count()
    items = (
        query.options(joinedload(VendorBill.vendor))
        .order_by(VendorBill.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def get_vendor_bill(db: Session, bill_id: str, company_id: str) -> VendorBill:
    bill = (
        db.query(VendorBill)
        .options(
            joinedload(VendorBill.vendor),
            joinedload(VendorBill.purchase_order),
            joinedload(VendorBill.lines),
            joinedload(VendorBill.approver),
            joinedload(VendorBill.creator),
        )
        .filter(
            VendorBill.id == bill_id,
            VendorBill.company_id == company_id,
            _active_filter(),
        )
        .first()
    )
    if not bill:
        raise HTTPException(status_code=404, detail="Vendor bill not found")
    return bill


def create_vendor_bill(
    db: Session, data, company_id: str, actor_id: str
) -> VendorBill:
    # Auto-calculate due_date from payment_terms if not provided
    due_date = data.due_date
    if not due_date and data.vendor_id:
        vendor = db.query(Vendor).filter(Vendor.id == data.vendor_id).first()
        if vendor and vendor.payment_terms:
            days = _parse_payment_terms_days(vendor.payment_terms)
            if days and data.bill_date:
                from dateutil.parser import parse as parse_date
                bd = parse_date(data.bill_date)
                due_date = (bd + timedelta(days=days)).isoformat()

    if not due_date:
        due_date = data.bill_date  # fallback: due immediately

    bill = VendorBill(
        id=str(uuid.uuid4()),
        company_id=company_id,
        number=_next_bill_number(db, company_id),
        vendor_id=data.vendor_id,
        vendor_invoice_number=data.vendor_invoice_number,
        po_id=data.po_id,
        status="pending",
        bill_date=data.bill_date,
        due_date=due_date,
        tax_amount=data.tax_amount or Decimal("0.00"),
        payment_terms=data.payment_terms,
        notes=data.notes,
        created_by=actor_id,
    )
    db.add(bill)
    db.flush()

    # If po_id is set and no lines provided, pre-populate from PO lines
    lines_data = data.lines
    if data.po_id and not lines_data:
        po_lines = (
            db.query(PurchaseOrderLine)
            .filter(
                PurchaseOrderLine.po_id == data.po_id,
                PurchaseOrderLine.deleted_at.is_(None),
            )
            .order_by(PurchaseOrderLine.sort_order)
            .all()
        )
        lines_data = []
        for pl in po_lines:
            from app.schemas.vendor_bill import BillLineCreate
            lines_data.append(BillLineCreate(
                po_line_id=pl.id,
                description=pl.description,
                quantity=pl.quantity_ordered,
                unit_cost=pl.unit_cost,
                amount=pl.line_total,
                sort_order=pl.sort_order,
            ))

    for idx, ld in enumerate(lines_data):
        line = VendorBillLine(
            id=str(uuid.uuid4()),
            bill_id=bill.id,
            po_line_id=ld.po_line_id,
            description=ld.description,
            quantity=ld.quantity,
            unit_cost=ld.unit_cost,
            amount=ld.amount,
            expense_category=ld.expense_category if hasattr(ld, "expense_category") else None,
            sort_order=ld.sort_order if hasattr(ld, "sort_order") and ld.sort_order else idx,
        )
        db.add(line)

    db.flush()
    db.refresh(bill)
    _recalc_bill_totals(bill)
    db.flush()

    audit_service.log_action(
        db, company_id, "created", "vendor_bill", bill.id,
        user_id=actor_id,
        changes={"number": bill.number, "vendor_id": bill.vendor_id, "total": str(bill.total)},
    )
    db.commit()
    return bill


def update_vendor_bill(
    db: Session, bill_id: str, data, company_id: str, actor_id: str
) -> VendorBill:
    bill = get_vendor_bill(db, bill_id, company_id)

    if bill.status in ("approved", "paid", "void"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot modify bill in '{bill.status}' status",
        )

    for field in ("vendor_id", "vendor_invoice_number", "po_id",
                  "bill_date", "due_date", "tax_amount", "payment_terms", "notes"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(bill, field, val)

    bill.modified_by = actor_id
    bill.modified_at = datetime.now(timezone.utc)

    if data.lines is not None:
        # Soft-delete old lines
        for old_line in bill.lines:
            if old_line.deleted_at is None:
                old_line.deleted_at = datetime.now(timezone.utc)

        for idx, ld in enumerate(data.lines):
            line = VendorBillLine(
                id=str(uuid.uuid4()),
                bill_id=bill.id,
                po_line_id=ld.po_line_id,
                description=ld.description,
                quantity=ld.quantity,
                unit_cost=ld.unit_cost,
                amount=ld.amount,
                expense_category=ld.expense_category,
                sort_order=ld.sort_order or idx,
            )
            db.add(line)

    db.flush()
    db.refresh(bill)
    _recalc_bill_totals(bill)

    audit_service.log_action(
        db, company_id, "updated", "vendor_bill", bill.id,
        user_id=actor_id,
    )
    db.commit()
    return bill


def approve_vendor_bill(
    db: Session, bill_id: str, company_id: str, actor_id: str
) -> VendorBill:
    bill = get_vendor_bill(db, bill_id, company_id)
    if bill.status not in ("pending", "draft"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve bill in '{bill.status}' status",
        )
    bill.status = "approved"
    bill.approved_by = actor_id
    bill.approved_at = datetime.now(timezone.utc)
    bill.modified_by = actor_id
    bill.modified_at = datetime.now(timezone.utc)

    audit_service.log_action(
        db, company_id, "approved", "vendor_bill", bill.id,
        user_id=actor_id,
    )
    db.commit()
    return bill


def void_vendor_bill(
    db: Session, bill_id: str, company_id: str, actor_id: str
) -> VendorBill:
    bill = get_vendor_bill(db, bill_id, company_id)
    if bill.amount_paid > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot void a bill with payments applied",
        )
    bill.status = "void"
    bill.modified_by = actor_id
    bill.modified_at = datetime.now(timezone.utc)

    audit_service.log_action(
        db, company_id, "voided", "vendor_bill", bill.id,
        user_id=actor_id,
    )
    db.commit()
    return bill


def get_bills_due(
    db: Session, company_id: str, days: int = 30
) -> list[VendorBill]:
    cutoff = datetime.now(timezone.utc) + timedelta(days=days)
    return (
        db.query(VendorBill)
        .options(joinedload(VendorBill.vendor))
        .filter(
            VendorBill.company_id == company_id,
            _active_filter(),
            VendorBill.status.in_(["pending", "approved", "partial"]),
            VendorBill.due_date <= cutoff,
        )
        .order_by(VendorBill.due_date)
        .all()
    )


def get_bills_overdue(db: Session, company_id: str) -> list[VendorBill]:
    now = datetime.now(timezone.utc)
    return (
        db.query(VendorBill)
        .options(joinedload(VendorBill.vendor))
        .filter(
            VendorBill.company_id == company_id,
            _active_filter(),
            VendorBill.status.in_(["pending", "approved", "partial"]),
            VendorBill.due_date < now,
        )
        .order_by(VendorBill.due_date)
        .all()
    )


def soft_delete_vendor_bill(
    db: Session, bill_id: str, company_id: str, actor_id: str
) -> None:
    bill = get_vendor_bill(db, bill_id, company_id)
    if bill.status not in ("draft", "pending"):
        raise HTTPException(
            status_code=400,
            detail="Only draft/pending bills can be deleted",
        )
    now = datetime.now(timezone.utc)
    bill.deleted_at = now
    for line in bill.lines:
        if line.deleted_at is None:
            line.deleted_at = now

    audit_service.log_action(
        db, company_id, "deleted", "vendor_bill", bill.id,
        user_id=actor_id,
    )
    db.commit()
