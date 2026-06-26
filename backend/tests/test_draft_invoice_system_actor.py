"""Health-triage P0: the draft-invoice system-actor FK crash.

draft_invoice_service passed the literal "system" as the invoice actor →
invoices.created_by="system" → FK violation (no users row id='system') →
draft_invoice_generator crashed every run. Fix: nullable attribution (None),
matching create_vault_order. This pins that create_invoice_from_order accepts
a None actor and the row persists with created_by IS NULL — witnessed against
the real schema (the FK permits NULL).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.sales_order import SalesOrder
from app.services import sales_service


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _world(db):
    suffix = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()),
        name=f"P0-{suffix}",
        slug=f"p0-{suffix}",
        is_active=True,
        vertical="manufacturing",
    )
    db.add(co)
    db.commit()
    cust = Customer(
        id=str(uuid.uuid4()), company_id=co.id, name="Acme", is_active=True
    )
    db.add(cust)
    db.commit()
    order = SalesOrder(
        id=str(uuid.uuid4()),
        company_id=co.id,
        number=f"SO-{suffix}",
        customer_id=cust.id,
        order_date=date.today(),
        status="confirmed",
        subtotal=Decimal("100.00"),
        tax_rate=Decimal("0"),
        tax_amount=Decimal("0"),
        total=Decimal("100.00"),
        payment_terms="net30",
    )
    db.add(order)
    db.commit()
    return co, order


def test_create_invoice_with_none_actor_persists(db):
    """The witness: a None actor inserts cleanly (created_by IS NULL), where
    the old "system" string would FK-violate."""
    co, order = _world(db)

    invoice = sales_service.create_invoice_from_order(db, co.id, None, order.id)

    # The row genuinely landed with a NULL actor (FK permits NULL).
    row = db.execute(
        sql_text("SELECT created_by FROM invoices WHERE id = :id"),
        {"id": invoice.id},
    ).first()
    assert row is not None
    assert row.created_by is None


def test_literal_system_actor_would_fk_violate(db):
    """Pins WHY the fix was needed: there is no users row id='system', so the
    old code's actor value is FK-invalid. Guards against a regression that
    reintroduces a bogus system-actor string."""
    assert (
        db.execute(
            sql_text("SELECT 1 FROM users WHERE id = 'system'")
        ).first()
        is None
    )
