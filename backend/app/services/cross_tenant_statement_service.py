"""Cross-tenant statement delivery service."""

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.fh_manufacturer_relationship import FHManufacturerRelationship
from app.models.received_statement import ReceivedStatement, StatementPayment
from app.models.statement import CustomerStatement

logger = logging.getLogger(__name__)


def deliver_statement_cross_tenant(
    db: Session, customer_statement_id: str, tenant_id: str,
) -> bool:
    """Deliver a statement cross-tenant to a connected funeral home."""
    stmt = (
        db.query(CustomerStatement)
        .filter(
            CustomerStatement.id == customer_statement_id,
            CustomerStatement.tenant_id == tenant_id,
        )
        .first()
    )
    if not stmt or stmt.delivery_method != "platform":
        return False

    manufacturer = db.query(Company).filter(Company.id == tenant_id).first()
    if not manufacturer:
        return False

    # Find the relationship to get the funeral home tenant
    relationship = (
        db.query(FHManufacturerRelationship)
        .filter(
            FHManufacturerRelationship.manufacturer_tenant_id == tenant_id,
            FHManufacturerRelationship.platform_billing_enabled.is_(True),
            FHManufacturerRelationship.status == "active",
        )
        .first()
    )
    if not relationship or not relationship.funeral_home_tenant_id:
        stmt.status = "failed"
        stmt.send_error = "No active platform connection found"
        db.commit()
        return False

    fh_tenant_id = relationship.funeral_home_tenant_id

    try:
        # Create received_statement on the funeral home side
        received = ReceivedStatement(
            tenant_id=fh_tenant_id,
            from_tenant_id=tenant_id,
            from_tenant_name=manufacturer.name,
            customer_statement_id=stmt.id,
            statement_period_month=stmt.statement_period_month,
            statement_period_year=stmt.statement_period_year,
            previous_balance=stmt.previous_balance,
            new_charges=stmt.new_charges,
            payments_received=stmt.payments_received,
            balance_due=stmt.balance_due,
            invoice_count=stmt.invoice_count,
            statement_pdf_url=stmt.statement_pdf_url,  # Will be copied in production
            status="unread",
        )
        db.add(received)
        db.flush()

        # Update manufacturer's customer_statement
        stmt.status = "sent"
        stmt.sent_at = datetime.now(timezone.utc)
        stmt.cross_tenant_delivered_at = datetime.now(timezone.utc)
        stmt.cross_tenant_received_statement_id = received.id
        db.commit()
        return True

    except Exception as e:
        logger.error("Cross-tenant delivery failed for %s: %s", customer_statement_id, e)
        db.rollback()
        stmt.status = "failed"
        stmt.send_error = str(e)[:500]
        db.commit()
        return False


def deliver_all_platform_for_run(
    db: Session, run_id: str, tenant_id: str,
) -> dict:
    """Deliver all platform statements in a run cross-tenant."""
    stmts = (
        db.query(CustomerStatement)
        .filter(
            CustomerStatement.run_id == run_id,
            CustomerStatement.delivery_method == "platform",
            CustomerStatement.status == "ready",
        )
        .all()
    )
    delivered = 0
    failed = 0
    for stmt in stmts:
        if deliver_statement_cross_tenant(db, stmt.id, tenant_id):
            delivered += 1
        else:
            failed += 1
    return {"delivered": delivered, "failed": failed}


# ---------------------------------------------------------------------------
# Funeral home side — received statements
# ---------------------------------------------------------------------------


def get_received_statements(
    db: Session, tenant_id: str,
) -> list[dict]:
    stmts = (
        db.query(ReceivedStatement)
        .filter(ReceivedStatement.tenant_id == tenant_id)
        .order_by(
            ReceivedStatement.statement_period_year.desc(),
            ReceivedStatement.statement_period_month.desc(),
        )
        .all()
    )
    return [
        {
            "id": s.id,
            "from_tenant_name": s.from_tenant_name,
            "month": s.statement_period_month,
            "year": s.statement_period_year,
            "balance_due": str(s.balance_due),
            "invoice_count": s.invoice_count,
            "status": s.status,
            "received_at": s.received_at.isoformat() if s.received_at else None,
            "read_at": s.read_at.isoformat() if s.read_at else None,
            "statement_pdf_url": s.statement_pdf_url,
        }
        for s in stmts
    ]


def get_received_statement_detail(
    db: Session, statement_id: str, tenant_id: str,
) -> dict | None:
    s = (
        db.query(ReceivedStatement)
        .filter(
            ReceivedStatement.id == statement_id,
            ReceivedStatement.tenant_id == tenant_id,
        )
        .first()
    )
    if not s:
        return None

    # Mark as read
    if s.status == "unread":
        s.status = "read"
        s.read_at = datetime.now(timezone.utc)
        db.commit()

    # Get payments
    payments = (
        db.query(StatementPayment)
        .filter(StatementPayment.received_statement_id == s.id)
        .order_by(StatementPayment.payment_date.desc())
        .all()
    )

    return {
        "id": s.id,
        "from_tenant_name": s.from_tenant_name,
        "month": s.statement_period_month,
        "year": s.statement_period_year,
        "previous_balance": str(s.previous_balance),
        "new_charges": str(s.new_charges),
        "payments_received": str(s.payments_received),
        "balance_due": str(s.balance_due),
        "invoice_count": s.invoice_count,
        "status": s.status,
        "statement_pdf_url": s.statement_pdf_url,
        "received_at": s.received_at.isoformat() if s.received_at else None,
        "dispute_notes": s.dispute_notes,
        "payments": [
            {
                "id": p.id,
                "amount": str(p.amount),
                "payment_method": p.payment_method,
                "payment_reference": p.payment_reference,
                "payment_date": str(p.payment_date),
                "notes": p.notes,
                "acknowledged": p.acknowledged_by_manufacturer,
            }
            for p in payments
        ],
    }


def record_payment(
    db: Session,
    tenant_id: str,
    received_statement_id: str,
    user_id: str,
    amount: Decimal,
    payment_method: str,
    payment_date: str,
    payment_reference: str | None = None,
    notes: str | None = None,
) -> StatementPayment | None:
    stmt = (
        db.query(ReceivedStatement)
        .filter(
            ReceivedStatement.id == received_statement_id,
            ReceivedStatement.tenant_id == tenant_id,
        )
        .first()
    )
    if not stmt:
        return None

    from datetime import date as date_type
    payment = StatementPayment(
        tenant_id=tenant_id,
        received_statement_id=received_statement_id,
        amount=amount,
        payment_method=payment_method,
        payment_reference=payment_reference,
        payment_date=date_type.fromisoformat(payment_date),
        notes=notes,
        submitted_by=user_id,
    )
    db.add(payment)

    # Update statement status
    total_paid = sum(
        p.amount
        for p in db.query(StatementPayment)
        .filter(StatementPayment.received_statement_id == received_statement_id)
        .all()
    ) + amount

    if total_paid >= stmt.balance_due:
        stmt.status = "paid"
    else:
        stmt.status = "payment_initiated"
    stmt.payment_id = payment.id

    db.commit()
    db.refresh(payment)

    # Update manufacturer side (non-blocking — best effort)
    try:
        mfr_stmt = (
            db.query(CustomerStatement)
            .filter(CustomerStatement.id == stmt.customer_statement_id)
            .first()
        )
        if mfr_stmt:
            mfr_stmt.payment_received_cross_tenant = True
            mfr_stmt.payment_amount_cross_tenant = amount
            mfr_stmt.payment_received_at = datetime.now(timezone.utc)
            db.commit()
    except Exception as e:
        logger.warning("Failed to update manufacturer statement: %s", e)

    return payment


def dispute_statement(
    db: Session, tenant_id: str, statement_id: str, notes: str,
) -> bool:
    stmt = (
        db.query(ReceivedStatement)
        .filter(
            ReceivedStatement.id == statement_id,
            ReceivedStatement.tenant_id == tenant_id,
        )
        .first()
    )
    if not stmt:
        return False
    stmt.status = "disputed"
    stmt.dispute_notes = notes
    db.commit()
    return True


def get_unread_count(db: Session, tenant_id: str) -> int:
    return (
        db.query(ReceivedStatement)
        .filter(
            ReceivedStatement.tenant_id == tenant_id,
            ReceivedStatement.status == "unread",
        )
        .count()
    )
