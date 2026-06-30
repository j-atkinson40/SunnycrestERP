"""Demo artifacts 3c — Invoice & Statement Run composition (assembly test).

The load-bearing JCF-1 proof: the workflow's composition PRODUCES real artifacts
against the (backend-health-corrected) services — real invoices from eligible
orders + a real statement_run — not merely that the registry is wired. Runs the
adapters (what `call_service_method` invokes) end-to-end.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.sales_order import SalesOrder, SalesOrderLine
from app.services.workflows.invoice_statement_adapter import (
    run_invoice_generation,
    run_statement_run,
)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _eligible_order(db) -> str:
    """A funeral order eligible for draft invoicing (confirmed, due today,
    not yet invoiced) with a line. Returns company_id."""
    suffix = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()), name=f"IS-{suffix}", slug=f"is-{suffix}",
        is_active=True, vertical="manufacturing",
    )
    db.add(co)
    db.commit()
    cust = Customer(id=str(uuid.uuid4()), company_id=co.id, name="Hopkins FH", is_active=True)
    db.add(cust)
    db.commit()
    order = SalesOrder(
        id=str(uuid.uuid4()), company_id=co.id, number=f"SO-{suffix}",
        customer_id=cust.id, order_date=date.today(), required_date=date.today(),
        status="confirmed", order_type="funeral",
        subtotal=Decimal("1000"), tax_rate=Decimal("0"), tax_amount=Decimal("0"),
        total=Decimal("1000"), payment_terms="net30",
    )
    db.add(order)
    db.flush()
    db.add(SalesOrderLine(
        id=str(uuid.uuid4()), sales_order_id=order.id, description="Vault",
        quantity=1, unit_price=Decimal("1000"), line_total=Decimal("1000"),
        sort_order=0,
    ))
    db.commit()
    return co.id


def test_invoice_generation_produces_real_invoices(db):
    co_id = _eligible_order(db)
    result = run_invoice_generation(db, company_id=co_id)

    assert result["invoices_generated"] >= 1
    # A real Invoice row landed for the tenant.
    n = db.query(Invoice).filter(Invoice.company_id == co_id).count()
    assert n == result["total_invoices"] >= 1


def test_statement_run_produces_a_real_run(db):
    co_id = _eligible_order(db)
    result = run_statement_run(db, company_id=co_id, triggered_by_user_id=None)

    # A real StatementRun row was created (even with 0 eligible customers — the
    # composition produced the run artifact).
    from app.models.statement import StatementRun

    run = db.get(StatementRun, result["statement_run_id"])
    assert run is not None
    assert run.tenant_id == co_id
    assert result["period_start"] and result["period_end"]
