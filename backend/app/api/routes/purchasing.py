"""Purchase order API routes."""

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.purchase_order import PurchaseOrder, PurchaseOrderReceipt, PurchaseOrderReceiptLine
from app.models.purchase_order_line import PurchaseOrderLine
from app.models.vendor import Vendor
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──

class POLineCreate(BaseModel):
    description: str
    unit: str | None = None
    quantity_ordered: float
    unit_price: float
    vendor_item_code: str | None = None


class POCreate(BaseModel):
    vendor_id: str
    expected_delivery_date: str | None = None
    notes: str | None = None
    internal_notes: str | None = None
    shipping_address: str | None = None
    tax_amount: float = 0
    shipping_amount: float = 0
    lines: list[POLineCreate]


class ReceiptLineCreate(BaseModel):
    po_line_id: str
    quantity_received: float
    condition: str = "good"
    condition_notes: str | None = None


class ReceiptCreate(BaseModel):
    received_date: str | None = None
    notes: str | None = None
    lines: list[ReceiptLineCreate]


# ── PO CRUD ──

@router.get("/orders")
def list_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pos = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.company_id == current_user.company_id, PurchaseOrder.deleted_at.is_(None))
        .order_by(PurchaseOrder.created_at.desc())
        .limit(100)
        .all()
    )
    return [_serialize_po(p, db) for p in pos]


@router.post("/orders")
def create_order(
    body: POCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Generate PO number
    last = db.query(func.count(PurchaseOrder.id)).filter(PurchaseOrder.company_id == current_user.company_id).scalar() or 0
    po_number = f"PO-{last + 1001}"

    subtotal = sum(Decimal(str(l.quantity_ordered)) * Decimal(str(l.unit_price)) for l in body.lines)
    total = subtotal + Decimal(str(body.tax_amount)) + Decimal(str(body.shipping_amount))

    po = PurchaseOrder(
        company_id=current_user.company_id,
        number=po_number,
        vendor_id=body.vendor_id,
        status="draft",
        order_date=datetime.now(timezone.utc),
        expected_delivery_date=date.fromisoformat(body.expected_delivery_date) if body.expected_delivery_date else None,
        subtotal=subtotal,
        tax_amount=Decimal(str(body.tax_amount)),
        shipping_amount=Decimal(str(body.shipping_amount)),
        total_amount=total,
        total=total,
        notes=body.notes,
        internal_notes=body.internal_notes,
        shipping_address=body.shipping_address,
        created_by=current_user.id,
    )
    db.add(po)
    db.flush()

    for i, line in enumerate(body.lines):
        lt = Decimal(str(line.quantity_ordered)) * Decimal(str(line.unit_price))
        db.add(PurchaseOrderLine(
            po_id=po.id,
            sort_order=i + 1,
            description=line.description,
            quantity_ordered=Decimal(str(line.quantity_ordered)),
            unit_cost=Decimal(str(line.unit_price)),
            line_total=lt,
        ))

    db.commit()
    db.refresh(po)
    return {"id": po.id, "po_number": po_number, "status": po.status, "total": float(total)}


@router.get("/orders/{po_id}")
def get_order(
    po_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id, PurchaseOrder.company_id == current_user.company_id,
    ).first()
    if not po:
        raise HTTPException(404, "PO not found")
    return _serialize_po_detail(po, db)


@router.post("/orders/{po_id}/approve")
def approve_order(
    po_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id, PurchaseOrder.company_id == current_user.company_id,
    ).first()
    if not po:
        raise HTTPException(404, "PO not found")
    po.status = "approved"
    po.approval_status = "approved"
    po.approved_by = current_user.id
    po.approved_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "approved"}


@router.post("/orders/{po_id}/send")
def send_order(
    po_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id, PurchaseOrder.company_id == current_user.company_id,
    ).first()
    if not po:
        raise HTTPException(404, "PO not found")
    po.status = "sent"
    po.sent_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "sent"}


@router.post("/orders/{po_id}/close")
def close_order(
    po_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id, PurchaseOrder.company_id == current_user.company_id,
    ).first()
    if not po:
        raise HTTPException(404, "PO not found")
    po.status = "closed"
    db.commit()
    return {"status": "closed"}


# ── Receiving ──

@router.post("/orders/{po_id}/receipts")
def receive_order(
    po_id: str,
    body: ReceiptCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id, PurchaseOrder.company_id == current_user.company_id,
    ).first()
    if not po:
        raise HTTPException(404, "PO not found")

    receipt_count = db.query(func.count(PurchaseOrderReceipt.id)).filter(
        PurchaseOrderReceipt.purchase_order_id == po_id,
    ).scalar() or 0
    receipt_number = f"RCV-{po.number}-{receipt_count + 1}"

    receipt = PurchaseOrderReceipt(
        tenant_id=current_user.company_id,
        purchase_order_id=po_id,
        receipt_number=receipt_number,
        received_date=date.fromisoformat(body.received_date) if body.received_date else date.today(),
        received_by=current_user.id,
        notes=body.notes,
    )
    db.add(receipt)
    db.flush()

    has_shortage = False
    has_overage = False
    has_damage = False

    for rl in body.lines:
        po_line = db.query(PurchaseOrderLine).filter(PurchaseOrderLine.id == rl.po_line_id).first()
        expected = float(po_line.quantity_ordered) if po_line else 0
        received = rl.quantity_received

        if received < expected:
            has_shortage = True
        if received > expected:
            has_overage = True
        if rl.condition == "damaged":
            has_damage = True

        db.add(PurchaseOrderReceiptLine(
            tenant_id=current_user.company_id,
            receipt_id=receipt.id,
            po_line_id=rl.po_line_id,
            quantity_received=Decimal(str(received)),
            quantity_expected=Decimal(str(expected)),
            condition=rl.condition,
            condition_notes=rl.condition_notes,
        ))

        # Update PO line quantity_received
        if po_line:
            po_line.quantity_received = (po_line.quantity_received or Decimal(0)) + Decimal(str(received))

    receipt.has_shortage = has_shortage
    receipt.has_overage = has_overage
    receipt.has_damage = has_damage
    receipt.status = "discrepancy" if (has_shortage or has_overage or has_damage) else "complete"

    # Update PO status
    all_lines = db.query(PurchaseOrderLine).filter(PurchaseOrderLine.po_id == po_id).all()
    all_received = all(float(l.quantity_received or 0) >= float(l.quantity_ordered) for l in all_lines)
    po.status = "fully_received" if all_received else "partially_received"
    if all_received:
        po.delivered_date = date.today()
        po.match_status = "pending_invoice"

    db.commit()
    return {"id": receipt.id, "receipt_number": receipt_number, "status": receipt.status}


@router.get("/orders/{po_id}/receipts")
def list_receipts(
    po_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    receipts = db.query(PurchaseOrderReceipt).filter(
        PurchaseOrderReceipt.purchase_order_id == po_id,
        PurchaseOrderReceipt.tenant_id == current_user.company_id,
    ).order_by(PurchaseOrderReceipt.created_at.desc()).all()
    return [
        {
            "id": r.id, "receipt_number": r.receipt_number,
            "received_date": str(r.received_date), "status": r.status,
            "has_shortage": r.has_shortage, "has_damage": r.has_damage,
        }
        for r in receipts
    ]


# ── Committed spend for cash flow ──

@router.get("/committed-spend")
def get_committed_spend(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Weekly committed spend from open POs for cash flow zone."""
    from datetime import timedelta
    today = date.today()
    weeks = []
    for i in range(5):
        ws = today + timedelta(weeks=i)
        we = ws + timedelta(days=6)
        total = db.query(func.coalesce(func.sum(PurchaseOrder.total_amount), 0)).filter(
            PurchaseOrder.company_id == current_user.company_id,
            PurchaseOrder.status.in_(["approved", "sent", "partially_received"]),
            PurchaseOrder.expected_delivery_date >= ws,
            PurchaseOrder.expected_delivery_date <= we,
        ).scalar() or 0
        weeks.append({"week_start": str(ws), "amount": float(total)})
    return weeks


# ── Helpers ──

def _serialize_po(po: PurchaseOrder, db: Session) -> dict:
    vendor = db.query(Vendor).filter(Vendor.id == po.vendor_id).first()
    return {
        "id": po.id, "po_number": po.number, "status": po.status,
        "vendor_name": vendor.vendor_name if vendor else "Unknown",
        "total_amount": float(po.total_amount or po.total or 0),
        "order_date": po.order_date.isoformat() if po.order_date else None,
        "expected_delivery_date": str(po.expected_delivery_date) if po.expected_delivery_date else None,
        "match_status": po.match_status,
        "approval_status": po.approval_status,
    }


def _serialize_po_detail(po: PurchaseOrder, db: Session) -> dict:
    vendor = db.query(Vendor).filter(Vendor.id == po.vendor_id).first()
    lines = db.query(PurchaseOrderLine).filter(PurchaseOrderLine.po_id == po.id).order_by(PurchaseOrderLine.sort_order).all()
    return {
        **_serialize_po(po, db),
        "vendor_id": po.vendor_id,
        "subtotal": float(po.subtotal),
        "tax_amount": float(po.tax_amount),
        "shipping_amount": float(po.shipping_amount or 0),
        "notes": po.notes, "internal_notes": po.internal_notes,
        "lines": [
            {
                "id": l.id, "description": l.description, "unit": l.unit,
                "quantity_ordered": float(l.quantity_ordered), "quantity_received": float(l.quantity_received or 0),
                "unit_price": float(l.unit_cost), "line_total": float(l.line_total),
            }
            for l in lines
        ],
    }
