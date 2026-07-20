"""D-11 U-1 pins — one money core (the $77 divergence dies).

THE PARITY PIN OF THIS ARC: identical inputs through both faces →
IDENTICAL money, hand-computed. $1,000 + $100 delivery @ 7% (Cayuga
County via the customer's zip) → $1,177 on Q- AND QTE- — the
investigation's worked divergence, dead.

Plus: the refusal (no resolution + no override → loud), the exemption
reason ($0 WITH its why), the override (explicit, carried as explicit,
including explicit zero), and the walk-in's honest unresolved reason.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.customer import Customer
from app.models.tax import TaxJurisdiction, TaxRate
from app.services import quote_service, sales_service


@pytest.fixture(scope="module")
def world():
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User
    db = SessionLocal()
    co = Company(name="U1", slug=f"u1-{uuid.uuid4().hex[:6]}")
    db.add(co); db.flush()
    role = Role(company_id=co.id, name="U1", slug=f"u1-{uuid.uuid4().hex[:4]}")
    db.add(role); db.flush()
    usr = User(company_id=co.id, email=f"u1-{uuid.uuid4().hex[:6]}@example.com",
               hashed_password="x", first_name="Pin", last_name="U1",
               role_id=role.id)
    # Cayuga County NY @ 7% — resolvable via zip 13021 (Auburn).
    rate = TaxRate(tenant_id=co.id, rate_name="Cayuga 7",
                   rate_percentage=Decimal("7.0"))
    db.add_all([usr, rate]); db.flush()
    jur = TaxJurisdiction(tenant_id=co.id, jurisdiction_name="Cayuga NY",
                          state="NY", county="Cayuga", tax_rate_id=rate.id)
    resolvable = Customer(company_id=co.id, name="Auburn FH",
                          account_number=f"U1-{uuid.uuid4().hex[:5]}",
                          zip_code="13021")
    exempt = Customer(company_id=co.id, name="Exempt FH",
                      account_number=f"U1-{uuid.uuid4().hex[:5]}",
                      zip_code="13021", tax_exempt=True)
    nozip = Customer(company_id=co.id, name="Nowhere FH",
                     account_number=f"U1-{uuid.uuid4().hex[:5]}")
    db.add_all([jur, resolvable, exempt, nozip]); db.commit()
    ids = {"co": co.id, "user": usr.id, "cust": resolvable.id,
           "exempt": exempt.id, "nozip": nozip.id}
    db.close()
    yield ids
    db = SessionLocal()
    for stmt in (
        "DELETE FROM quote_lines WHERE quote_id IN (SELECT id FROM quotes WHERE company_id = :c)",
        "DELETE FROM quotes WHERE company_id = :c",
        "DELETE FROM vault_items WHERE company_id = :c",
        "DELETE FROM audit_logs WHERE company_id = :c",
        "DELETE FROM crm_activities WHERE company_id = :c",
        "DELETE FROM tax_jurisdictions WHERE tenant_id = :c",
        "DELETE FROM tax_rates WHERE tenant_id = :c",
        "DELETE FROM vaults WHERE company_id = :c",
        "DELETE FROM company_modules WHERE company_id = :c",
        "DELETE FROM financial_accounts WHERE company_id = :c",
        "DELETE FROM customers WHERE company_id = :c",
        "DELETE FROM users WHERE company_id = :c",
        "DELETE FROM roles WHERE company_id = :c",
        "DELETE FROM companies WHERE id = :c",
    ):
        try:
            db.execute(sql_text(stmt), {"c": ids["co"]})
            db.commit()
        except Exception:
            db.rollback()
    db.close()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback(); s.close()


def _qte(db, world, customer_id, *, lines, tax_rate=None):
    class _L:
        def __init__(self, desc, price):
            self.product_id = None; self.description = desc
            self.quantity = Decimal("1"); self.unit_price = Decimal(price)
            self.sort_order = 0

    class _Data:
        pass
    d = _Data()
    d.customer_id = customer_id
    d.quote_date = datetime.now(timezone.utc)
    d.expiry_date = d.quote_date
    d.payment_terms = None
    d.tax_rate = tax_rate
    d.notes = None
    d.lines = [_L(desc, price) for desc, price in lines]
    return sales_service.create_quote(db, world["co"], world["user"], d)


class TestTheParityPin:
    """$1,000 vault + $100 delivery @ 7% → $1,177. Both faces. Dead divergence."""

    def test_q_face_1177(self, db, world):
        q = quote_service.create_quote(
            db, world["co"], world["user"],
            customer_name="Auburn FH", product_line="funeral_vaults",
            line_items=[{"description": "Vault", "quantity": 1,
                         "unit_price": "1000.00"}],
            customer_id=world["cust"], delivery_charge=100,
        )
        assert Decimal(str(q["total"])) == Decimal("1177.00")
        assert "resolved: 7% — Cayuga County, NY" in q["tax_reason"]

    def test_qte_face_1177_same_truth(self, db, world):
        q = _qte(db, world, world["cust"],
                 lines=[("Vault", "1000.00"), ("Delivery", "100.00")])
        assert Decimal(str(q.total)) == Decimal("1177.00")
        assert Decimal(str(q.tax_amount)) == Decimal("77.00")
        assert "resolved: 7% — Cayuga County, NY" in q.tax_reason


class TestTheRefusal:
    def test_unresolvable_no_override_refuses_loudly(self, db, world):
        with pytest.raises(HTTPException) as e:
            _qte(db, world, world["nozip"], lines=[("Vault", "1000.00")])
        assert e.value.status_code == 400
        assert "explicit" in e.value.detail  # tells the caller the way out


class TestTheExemptionReason:
    def test_exempt_answers_zero_with_its_why(self, db, world):
        q = _qte(db, world, world["exempt"], lines=[("Vault", "1000.00")])
        assert Decimal(str(q.tax_amount)) == Decimal("0.00")
        assert Decimal(str(q.total)) == Decimal("1000.00")
        assert q.tax_reason == "exempt: Exempt FH is tax-exempt"


class TestTheOverride:
    def test_explicit_override_carried_as_explicit(self, db, world):
        q = _qte(db, world, world["nozip"], lines=[("Vault", "1000.00")],
                 tax_rate=Decimal("0.07"))
        assert Decimal(str(q.tax_amount)) == Decimal("70.00")
        assert q.tax_reason == "override: 7% (explicit)"

    def test_explicit_zero_is_legitimate_and_says_so(self, db, world):
        q = _qte(db, world, world["nozip"], lines=[("Vault", "1000.00")],
                 tax_rate=Decimal("0"))
        assert Decimal(str(q.tax_amount)) == Decimal("0.00")
        assert q.tax_reason == "override: 0% (explicit)"

    def test_override_beats_resolution(self, db, world):
        """An explicit rate wins even when the engine could resolve —
        deliberate, and the reason says which authority answered."""
        q = _qte(db, world, world["cust"], lines=[("Vault", "1000.00")],
                 tax_rate=Decimal("0.05"))
        assert Decimal(str(q.tax_amount)) == Decimal("50.00")
        assert "override" in q.tax_reason


class TestTheWalkIn:
    def test_q_face_walk_in_unresolved_with_reason(self, db, world):
        """The Order-Station walk-in (no customer) keeps its tolerated $0 —
        now carrying WHY instead of silence."""
        q = quote_service.create_quote(
            db, world["co"], world["user"],
            customer_name="Walk-in", product_line="funeral_vaults",
            line_items=[{"description": "Vault", "quantity": 1,
                         "unit_price": "1000.00"}],
        )
        assert Decimal(str(q["total"])) == Decimal("1000.00")
        assert q["tax_reason"].startswith("unresolved:")
