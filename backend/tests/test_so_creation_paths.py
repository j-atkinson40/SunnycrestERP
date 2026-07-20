"""S&O Session Four pins — creation paths (audit #2 D-1.5 conditional
pricing + rounding discipline + D-9 Beat 7).

FIX 1: conditional pricing resolves AT QUOTE TIME through the same
resolver the order path uses — the quoted number IS the charged number;
conversion carries it unchanged. Both quote systems (Q- and QTE-).
FIX 2: money rounds at defined boundaries — banker's (ROUND_HALF_EVEN),
the verified policy of record — with adversarial .005 pins.
FIX 3: Beat 7's unresolvable-customer 500 refuses loudly instead.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.customer import Customer
from app.models.product import Product


@pytest.fixture(scope="module")
def world():
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User
    db = SessionLocal()
    co = Company(name="CP4", slug=f"cp4-{uuid.uuid4().hex[:6]}")
    db.add(co); db.flush()
    role = Role(company_id=co.id, name="CP4", slug=f"cp4-{uuid.uuid4().hex[:4]}")
    db.add(role); db.flush()
    usr = User(company_id=co.id, email=f"cp4-{uuid.uuid4().hex[:6]}@example.com",
               hashed_password="x", first_name="Pin", last_name="Four",
               role_id=role.id)
    cust = Customer(company_id=co.id, name="CP4 FH",
                    account_number=f"CP-{uuid.uuid4().hex[:6]}",
                    current_balance=Decimal("0.00"))
    # A vault (qualifier via known product_line) + a conditional graveside
    # tent: $150 with a vault on the order, $250 standalone.
    vault = Product(company_id=co.id, name="Monticello Vault",
                    product_line="monticello", price=Decimal("1200.00"))
    tent = Product(company_id=co.id, name="Graveside Tent",
                   price=Decimal("150.00"),
                   price_without_our_product=Decimal("250.00"),
                   has_conditional_pricing=True)
    plain = Product(company_id=co.id, name="Plain Marker",
                    price=Decimal("80.00"))
    db.add_all([usr, cust, vault, tent, plain]); db.commit()
    ids = {"co": co.id, "user": usr.id, "cust": cust.id,
           "vault": vault.id, "tent": tent.id, "plain": plain.id}
    db.close()
    yield ids
    db = SessionLocal()
    for stmt in (
        "DELETE FROM invoice_lines WHERE invoice_id IN (SELECT id FROM invoices WHERE company_id = :c)",
        "DELETE FROM invoices WHERE company_id = :c",
        "DELETE FROM deliveries WHERE company_id = :c",
        "DELETE FROM sales_order_lines WHERE sales_order_id IN (SELECT id FROM sales_orders WHERE company_id = :c)",
        "DELETE FROM sales_orders WHERE company_id = :c",
        "DELETE FROM quote_lines WHERE quote_id IN (SELECT id FROM quotes WHERE company_id = :c)",
        "DELETE FROM quotes WHERE company_id = :c",
        "DELETE FROM vault_items WHERE company_id = :c",
        "DELETE FROM audit_logs WHERE company_id = :c",
        "DELETE FROM crm_activities WHERE company_id = :c",
        "DELETE FROM products WHERE company_id = :c",
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


class TestConditionalPricingReachesQuotes:
    def _q_lines(self, db, quote_id):
        return {r[0]: Decimal(str(r[1])) for r in db.execute(sql_text(
            "SELECT description, unit_price FROM quote_lines WHERE quote_id = :q"),
            {"q": quote_id}).fetchall()}

    def test_order_station_quote_standalone_price(self, db, world):
        """No vault on the quote → the tent quotes at $250 standalone,
        whatever the caller typed."""
        from app.services import quote_service
        q = quote_service.create_quote(
            db, world["co"], world["user"],
            customer_name="CP4 FH", product_line="funeral_vaults",
            line_items=[{"description": "Tent", "product_id": world["tent"],
                         "quantity": 1, "unit_price": "150.00"}],
        )
        assert self._q_lines(db, q["id"])["Tent"] == Decimal("250.00")
        assert Decimal(str(q["total"])) == Decimal("250.00")

    def test_order_station_quote_with_vault_price(self, db, world):
        """Vault on the quote → the tent quotes at the $150 conditional."""
        from app.services import quote_service
        q = quote_service.create_quote(
            db, world["co"], world["user"],
            customer_name="CP4 FH", product_line="funeral_vaults",
            line_items=[
                {"description": "Vault", "product_id": world["vault"],
                 "quantity": 1, "unit_price": "1200.00"},
                {"description": "Tent", "product_id": world["tent"],
                 "quantity": 1, "unit_price": "250.00"},
            ],
        )
        lines = self._q_lines(db, q["id"])
        assert lines["Tent"] == Decimal("150.00")
        assert Decimal(str(q["total"])) == Decimal("1350.00")

    def test_conversion_carries_the_same_number(self, db, world):
        """The reprice-on-convert surprise is dead: quote $150 → order $150."""
        from app.services import quote_service
        q = quote_service.create_quote(
            db, world["co"], world["user"],
            customer_name="CP4 FH", product_line="funeral_vaults",
            line_items=[
                {"description": "Vault", "product_id": world["vault"],
                 "quantity": 1, "unit_price": "1200.00"},
                {"description": "Tent", "product_id": world["tent"],
                 "quantity": 1, "unit_price": "250.00"},
            ],
            customer_id=world["cust"],
        )
        r = quote_service.convert_quote_to_order(
            db, world["co"], world["user"], q["id"])
        order_lines = {row[0]: Decimal(str(row[1])) for row in db.execute(sql_text(
            "SELECT description, unit_price FROM sales_order_lines "
            "WHERE sales_order_id = :o"), {"o": r["id"]}).fetchall()}
        assert order_lines["Tent"] == Decimal("150.00")
        assert Decimal(str(r["total"])) == Decimal(str(q["total"]))

    def test_no_rule_product_quotes_unchanged(self, db, world):
        from app.services import quote_service
        q = quote_service.create_quote(
            db, world["co"], world["user"],
            customer_name="CP4 FH", product_line="funeral_vaults",
            line_items=[{"description": "Marker", "product_id": world["plain"],
                         "quantity": 1, "unit_price": "77.50"}],
        )
        assert self._q_lines(db, q["id"])["Marker"] == Decimal("77.50")

    def test_qte_system_same_resolution(self, db, world):
        """The QTE- (AR) quote system resolves through the same engine."""
        from app.services import sales_service
        from datetime import datetime, timezone

        class _L:
            def __init__(self, pid, desc, price):
                self.product_id = pid; self.description = desc
                self.quantity = Decimal("1"); self.unit_price = Decimal(price)
                self.sort_order = 0

        class _Data:
            customer_id = world["cust"]
            quote_date = datetime.now(timezone.utc)
            expiry_date = quote_date; payment_terms = None
            tax_rate = Decimal("0.00"); notes = None
            lines = [_L(world["tent"], "Tent", "150.00")]  # no vault

        q = sales_service.create_quote(db, world["co"], world["user"], _Data())
        assert Decimal(str(q.total)) == Decimal("250.00")  # standalone


class TestRoundingDiscipline:
    def test_bankers_half_cent_pins(self):
        from app.services.money import line_total, round_money
        # THE POLICY: half-even at the cent (verified policy of record).
        assert round_money(Decimal("0.125")) == Decimal("0.12")  # ties → even
        assert round_money(Decimal("0.135")) == Decimal("0.14")
        assert line_total(3, Decimal("0.335")) == Decimal("1.00")  # 1.005 → even
        assert line_total(1, Decimal("2.675")) == Decimal("2.68")

    def test_many_line_accumulation_no_drift(self, db, world):
        """100 lines of 3 × $0.335: each rounds at its line boundary to
        $1.00 (banker's on the 1.005 tie) — the subtotal is exactly
        $100.00, not the unrounded $100.50 float-ish drift."""
        from app.services import quote_service
        q = quote_service.create_quote(
            db, world["co"], world["user"],
            customer_name="CP4 FH", product_line="funeral_vaults",
            line_items=[{"description": f"W{i}", "quantity": 3,
                         "unit_price": "0.335"} for i in range(100)],
        )
        assert Decimal(str(q["subtotal"])) == Decimal("100.00")

    def test_vault_order_totals_rounded(self):
        from app.services.money import line_total
        # The vault_order_service site now rounds qty × price: 3 × 33.335
        assert line_total(3, Decimal("33.335")) == Decimal("100.00")


class TestBeat7Refusal:
    def test_unresolvable_customer_refuses_loudly(self, db, world):
        from app.services import call_extraction_service as ces

        class _Ext:
            call_type = "order"; vault_type = "monticello"
            master_company_id = None
            deceased_name = "X"; cemetery_name = None
            burial_date = None; burial_time = None
            call_summary = ""; call_log_id = "none"; id = "ext-1"
            draft_order_created = False; draft_order_id = None

        with pytest.raises(ValueError, match="customer"):
            # Refuses before any flush — no IntegrityError 500.
            ces.create_draft_order_from_extraction(db, _Ext(), world["co"])
