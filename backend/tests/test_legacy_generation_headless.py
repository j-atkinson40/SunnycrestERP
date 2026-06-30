"""Demo artifacts 3b.1 — Legacy Generation headless dispatch (assembly test).

The load-bearing proof: the Legacy Generation focus RUNS headless and PRODUCES a
real proof artifact (rendered proof bytes via the pure legacy_compositor) — not
merely that the registry entry resolves. Registry-resolves ≠ focus-runs; this
asserts the render produced real output.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.sales_order import SalesOrder
from app.services.generation_focus.headless_dispatch import (
    UnknownGenerationFocusOp,
    dispatch,
    list_dispatch_keys,
)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _order_with_deceased(db, name: str) -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()), name=f"LG-{suffix}", slug=f"lg-{suffix}",
        is_active=True, vertical="manufacturing",
    )
    db.add(co)
    db.commit()
    cust = Customer(id=str(uuid.uuid4()), company_id=co.id, name="FH", is_active=True)
    db.add(cust)
    db.commit()
    order = SalesOrder(
        id=str(uuid.uuid4()), company_id=co.id, number=f"SO-{suffix}",
        customer_id=cust.id, order_date=date.today(), status="confirmed",
        subtotal=Decimal("0"), tax_rate=Decimal("0"), tax_amount=Decimal("0"),
        total=Decimal("0"), deceased_name=name,
    )
    db.add(order)
    db.commit()
    return co.id, order.id


def test_legacy_generation_registered():
    """The focus_id is registered for headless dispatch (necessary, not
    sufficient — the run is the real witness below)."""
    keys = list_dispatch_keys()
    assert ("legacy_proof_generation", "generate_proof") in keys


def test_legacy_generation_runs_and_produces_a_real_proof(db):
    co_id, order_id = _order_with_deceased(db, "Robert James Smith")

    payload = dispatch(
        "legacy_proof_generation", "generate_proof",
        db=db, company_id=co_id, sales_order_id=order_id,
    )

    # It RAN and PRODUCED a real proof (rendered bytes), pulling the order's name.
    assert payload["proof_generated"] is True
    assert payload["proof_size_bytes"] > 0  # a real image was composited
    assert payload["deceased_name"] == "Robert James Smith"


def test_unknown_op_raises(db):
    co_id, _ = _order_with_deceased(db, "X")
    with pytest.raises(UnknownGenerationFocusOp):
        dispatch("legacy_proof_generation", "nope", db=db, company_id=co_id)
