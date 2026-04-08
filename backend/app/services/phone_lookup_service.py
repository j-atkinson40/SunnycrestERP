"""Phone number → customer lookup service for Call Intelligence.

Normalizes incoming phone numbers and searches company_entities, contacts,
and customers to identify the caller. Returns enriched context including
recent invoice metadata and AR balance for the call overlay.
"""

import logging
import re
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.company_entity import CompanyEntity
from app.models.contact import Contact
from app.models.customer import Customer
from app.models.invoice import Invoice

logger = logging.getLogger(__name__)


def normalize_phone(raw: str) -> str:
    """Strip a phone number to digits only. Drops leading '1' if 11 digits (US)."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def _phone_pattern(normalized: str) -> str:
    """Build a LIKE pattern that matches the last 10 digits regardless of formatting."""
    if len(normalized) < 7:
        return f"%{normalized}%"
    return f"%{normalized[-10:]}%"


def lookup_customer_by_phone(
    db: Session,
    tenant_id: str,
    phone_raw: str,
) -> dict[str, Any] | None:
    """Look up a caller by phone number across company_entities, contacts, and customers.

    Returns:
        dict with company_entity_id, customer_id, company_name, caller_name, etc.
        or None if no match.
    """
    normalized = normalize_phone(phone_raw)
    if len(normalized) < 7:
        return None

    pattern = _phone_pattern(normalized)

    # 1. Check company_entities.phone
    entity = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.tenant_id == tenant_id,
            func.regexp_replace(CompanyEntity.phone, r"\D", "", "g").like(f"%{normalized}%"),
        )
        .first()
    )
    if entity:
        # Find linked customer
        customer = (
            db.query(Customer)
            .filter(
                Customer.company_id == tenant_id,
                Customer.master_company_id == entity.id,
            )
            .first()
        )
        return {
            "company_entity_id": entity.id,
            "customer_id": customer.id if customer else None,
            "company_name": entity.name,
            "caller_name": entity.name,
            "phone": entity.phone,
        }

    # 2. Check contacts.phone
    contact = (
        db.query(Contact)
        .filter(
            Contact.tenant_id == tenant_id,
            func.regexp_replace(Contact.phone, r"\D", "", "g").like(f"%{normalized}%"),
        )
        .first()
    )
    if contact:
        entity_id = contact.company_entity_id
        entity_name = None
        customer_id = None
        if entity_id:
            parent = db.query(CompanyEntity).filter(CompanyEntity.id == entity_id).first()
            entity_name = parent.name if parent else None
            customer = (
                db.query(Customer)
                .filter(
                    Customer.company_id == tenant_id,
                    Customer.master_company_id == entity_id,
                )
                .first()
            )
            customer_id = customer.id if customer else None
        return {
            "company_entity_id": entity_id,
            "customer_id": customer_id,
            "company_name": entity_name,
            "caller_name": f"{contact.first_name or ''} {contact.last_name or ''}".strip() or None,
            "phone": contact.phone,
        }

    # 3. Check customers.phone (legacy, pre-CRM)
    customer = (
        db.query(Customer)
        .filter(
            Customer.company_id == tenant_id,
            func.regexp_replace(Customer.phone, r"\D", "", "g").like(f"%{normalized}%"),
        )
        .first()
    )
    if customer:
        return {
            "company_entity_id": customer.master_company_id,
            "customer_id": customer.id,
            "company_name": customer.name,
            "caller_name": customer.name,
            "phone": customer.phone,
        }

    return None


def enrich_customer_context(
    db: Session,
    tenant_id: str,
    customer_id: str | None,
    company_entity_id: str | None = None,
) -> dict[str, Any]:
    """Build enriched context for the call overlay: last order, AR balance, recent invoices.

    Returns dict with:
        last_order_date, open_ar_balance, recent_invoices
    """
    context: dict[str, Any] = {
        "last_order_date": None,
        "open_ar_balance": None,
        "recent_invoices": [],
    }

    if not customer_id:
        return context

    # Last order date — most recent invoice
    last_invoice = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == tenant_id,
            Invoice.customer_id == customer_id,
        )
        .order_by(Invoice.invoice_date.desc())
        .first()
    )
    if last_invoice:
        context["last_order_date"] = (
            last_invoice.invoice_date.isoformat() if last_invoice.invoice_date else None
        )

    # Open AR balance — sum of outstanding invoices
    ar_result = (
        db.query(func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0))
        .filter(
            Invoice.company_id == tenant_id,
            Invoice.customer_id == customer_id,
            Invoice.status.in_(["sent", "overdue", "partial"]),
        )
        .scalar()
    )
    context["open_ar_balance"] = float(ar_result) if ar_result else 0.0

    # Recent invoice metadata from R2 documents
    try:
        from app.services.document_r2_service import get_invoice_metadata_for_customer

        context["recent_invoices"] = get_invoice_metadata_for_customer(
            db, tenant_id, customer_id, limit=5
        )
    except Exception as e:
        logger.warning("Failed to fetch invoice metadata: %s", e)
        context["recent_invoices"] = []

    return context
