"""Sales-tax arc pins — the three-axis chain, the accumulator, the return.

Hand-proven resolution per axis (the six the gates demand): product-
exempt, job-cert, customer-cert, expired-cert-taxable, flag-gap,
plain-taxable. Accumulator idempotency (recompute-and-replace = byte-
identical reruns). The return's math cross-checked against a hand-built
quarter. Isolation everywhere — certificates are tenant money-law.
Period math on the NY sales-tax calendar.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.product import Product
from app.models.tax import TaxJurisdiction, TaxRate
from app.models.tax_filing import TaxCertificate, TaxPeriod
from app.services.tax_service import resolve_line_tax
from app.services import tax_filing_service as tfs


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _cleanup(db, company_ids):
    for cid in company_ids:
        for stmt in (
            "DELETE FROM tax_periods WHERE company_id = :c",
            "DELETE FROM tax_certificates WHERE company_id = :c",
            "DELETE FROM report_runs WHERE tenant_id = :c",
            "DELETE FROM invoices WHERE company_id = :c",
            "DELETE FROM sales_order_lines WHERE sales_order_id IN (SELECT id FROM sales_orders WHERE company_id = :c)",
            "DELETE FROM sales_orders WHERE company_id = :c",
            "DELETE FROM products WHERE company_id = :c",
            "DELETE FROM tax_jurisdictions WHERE tenant_id = :c",
            "DELETE FROM tax_rates WHERE tenant_id = :c",
            "DELETE FROM customers WHERE company_id = :c",
            "DELETE FROM users WHERE company_id = :c",
            "DELETE FROM vaults WHERE company_id = :c",
            "DELETE FROM company_modules WHERE company_id = :c",
            "DELETE FROM companies WHERE id = :c",
        ):
            try:
                db.execute(sql_text(stmt), {"c": cid})
                db.commit()
            except Exception:
                db.rollback()


def _world(db, tag: str):
    """Company + Cayuga 7% jurisdiction + customer (zip 13021) + products."""
    co = Company(name=f"TAX {tag}", slug=f"tax-{tag}-{uuid.uuid4().hex[:6]}")
    db.add(co)
    db.flush()
    rate = TaxRate(tenant_id=co.id, rate_name="Cayuga 7",
                   rate_percentage=Decimal("7.0"))
    db.add(rate)
    db.flush()
    jur = TaxJurisdiction(tenant_id=co.id, jurisdiction_name="Cayuga NY",
                          state="NY", county="Cayuga", tax_rate_id=rate.id)
    cust = Customer(company_id=co.id, name="Auburn FH", zip_code="13021")
    vault = Product(company_id=co.id, name="Monticello Vault",
                    price=Decimal("1000.00"))  # tax_class default 'inherit'
    marker = Product(company_id=co.id, name="Memorial Marker",
                     price=Decimal("500.00"), tax_class="exempt")
    db.add_all([jur, cust, vault, marker])
    db.commit()
    return co, cust, vault, marker


class TestTheSixAxes:
    def test_plain_taxable_via_jurisdiction(self, db):
        co, cust, vault, _ = _world(db, "a1")
        try:
            out = resolve_line_tax(
                db, co.id,
                lines=[{"product_id": vault.id, "amount": Decimal("1000.00"),
                        "description": "Vault"}],
                customer_id=cust.id)
            assert out.tax_amount == Decimal("70.00")
            assert out.source == "jurisdiction"
            assert "Cayuga County, NY" in out.reason
        finally:
            _cleanup(db, [co.id])

    def test_product_exempt_answers_zero_with_its_reason(self, db):
        co, cust, _, marker = _world(db, "a2")
        try:
            out = resolve_line_tax(
                db, co.id,
                lines=[{"product_id": marker.id, "amount": Decimal("500.00"),
                        "description": "Marker"}],
                customer_id=cust.id)
            assert out.tax_amount == Decimal("0.00")
            assert out.source == "product_exempt"
            assert out.exempt_lines[0]["reason"] == "product: Memorial Marker — exempt class"
        finally:
            _cleanup(db, [co.id])

    def test_mixed_lines_tax_only_the_taxable(self, db):
        """$1,000 taxable + $500 product-exempt @7% → tax $70, stated."""
        co, cust, vault, marker = _world(db, "a3")
        try:
            out = resolve_line_tax(
                db, co.id,
                lines=[
                    {"product_id": vault.id, "amount": Decimal("1000.00")},
                    {"product_id": marker.id, "amount": Decimal("500.00")},
                ],
                customer_id=cust.id)
            assert out.tax_amount == Decimal("70.00")
            assert out.taxable_subtotal == Decimal("1000.00")
            assert out.exempt_subtotal == Decimal("500.00")
            assert "1 line(s) product-exempt ($500.00)" in out.reason
        finally:
            _cleanup(db, [co.id])

    def test_job_certificate_exempts_the_order(self, db):
        from app.models.sales_order import SalesOrder
        co, cust, vault, _ = _world(db, "a4")
        try:
            so = SalesOrder(company_id=co.id, number=f"SO-T-{uuid.uuid4().hex[:6]}",
                            customer_id=cust.id, status="confirmed",
                            order_date=datetime.now(timezone.utc))
            db.add(so)
            db.flush()
            db.add(TaxCertificate(
                company_id=co.id, customer_id=cust.id, sales_order_id=so.id,
                cert_type="resale", cert_number="JOB-777", state="NY"))
            db.commit()
            out = resolve_line_tax(
                db, co.id,
                lines=[{"product_id": vault.id, "amount": Decimal("1000.00")}],
                customer_id=cust.id, sales_order_id=so.id)
            assert out.tax_amount == Decimal("0.00")
            assert out.source == "job_certificate"
            assert "job certificate resale (JOB-777)" in out.reason
        finally:
            _cleanup(db, [co.id])

    def test_customer_blanket_certificate_exempts(self, db):
        co, cust, vault, _ = _world(db, "a5")
        try:
            db.add(TaxCertificate(
                company_id=co.id, customer_id=cust.id,
                cert_type="resale", cert_number="NY-BLANKET-1",
                valid_through=date.today() + timedelta(days=365)))
            db.commit()
            out = resolve_line_tax(
                db, co.id,
                lines=[{"product_id": vault.id, "amount": Decimal("1000.00")}],
                customer_id=cust.id)
            assert out.tax_amount == Decimal("0.00")
            assert out.source == "customer_certificate"
            assert "valid through" in out.reason
        finally:
            _cleanup(db, [co.id])

    def test_expired_certificate_is_simply_absent(self, db):
        """Dated validity does the work — expired cert → TAXABLE."""
        co, cust, vault, _ = _world(db, "a6")
        try:
            db.add(TaxCertificate(
                company_id=co.id, customer_id=cust.id,
                cert_type="resale", cert_number="OLD-1",
                valid_through=date.today() - timedelta(days=1)))
            db.commit()
            out = resolve_line_tax(
                db, co.id,
                lines=[{"product_id": vault.id, "amount": Decimal("1000.00")}],
                customer_id=cust.id)
            assert out.tax_amount == Decimal("70.00")
            assert out.source == "jurisdiction"
        finally:
            _cleanup(db, [co.id])

    def test_flag_without_cert_taxable_with_gap(self, db):
        co, cust, vault, _ = _world(db, "a7")
        try:
            cust.tax_exempt = True
            db.commit()
            out = resolve_line_tax(
                db, co.id,
                lines=[{"product_id": vault.id, "amount": Decimal("1000.00")}],
                customer_id=cust.id)
            assert out.tax_amount == Decimal("70.00")
            assert out.gaps and "exemption flag" in out.gaps[0]
            assert "GAP: exemption flag without certificate" in out.reason
        finally:
            _cleanup(db, [co.id])


def _invoice(db, co, cust, *, total, tax, when, source=None, exempt=Decimal("0.00"),
             jurisdiction=None, status="sent"):
    inv = Invoice(
        company_id=co.id, customer_id=cust.id,
        number=f"INV-T-{uuid.uuid4().hex[:6]}",
        invoice_date=when, due_date=when + timedelta(days=30),
        status=status, subtotal=Decimal(total), total=Decimal(total) + Decimal(tax),
        tax_amount=Decimal(tax),
        tax_rate=Decimal("0.07") if Decimal(tax) > 0 else Decimal("0"),
        tax_source=source, exempt_amount=exempt,
        tax_jurisdiction=jurisdiction,
    )
    db.add(inv)
    db.commit()
    return inv


class TestTheAccumulatorAndReturn:
    def test_hand_built_quarter(self, db):
        """Q2 2026 (Jun–Aug), Cayuga: two taxable invoices ($1,000 @7% =
        $70 each) + one product-exempt ($500) + one unclassified zero →
        gross $3,000 · taxable $2,000 · exempt $1,000 · tax $140, with
        the unclassified row in the gaps list."""
        co, cust, _, _ = _world(db, "q1")
        try:
            when = datetime(2026, 7, 10, tzinfo=timezone.utc)
            _invoice(db, co, cust, total="1000.00", tax="70.00", when=when,
                     source="jurisdiction", jurisdiction="Cayuga County, NY")
            _invoice(db, co, cust, total="1000.00", tax="70.00", when=when,
                     source="jurisdiction", jurisdiction="Cayuga County, NY")
            _invoice(db, co, cust, total="500.00", tax="0.00", when=when,
                     source="product_exempt", exempt=Decimal("500.00"),
                     jurisdiction="Cayuga County, NY")
            _invoice(db, co, cust, total="500.00", tax="0.00", when=when)  # unclassified

            out = tfs.accumulate_period(db, co.id, "2026-Q2")
            assert out["invoices"] == 4
            ret = tfs.get_return(db, co.id, "2026-Q2")
            assert ret["totals"]["gross_sales"] == 3000.0
            assert ret["totals"]["taxable_sales"] == 2000.0
            assert ret["totals"]["exempt_sales"] == 1000.0
            assert ret["totals"]["tax_computed"] == 140.0
            cay = next(j for j in ret["jurisdictions"]
                       if j["jurisdiction"] == "Cayuga County, NY")
            assert cay["exempt_by_class"].get("product_exempt") == 500.0
            assert any("zero tax with no recorded exemption" in g for g in ret["gaps"])
            assert ret["due_date"] == "2026-09-20"  # 20th after Aug 31
        finally:
            _cleanup(db, [co.id])

    def test_accumulation_is_idempotent(self, db):
        """Recompute-and-replace: re-running yields byte-identical rows
        (the sweeper-class parity — zero drift)."""
        co, cust, _, _ = _world(db, "q2")
        try:
            when = datetime(2026, 7, 10, tzinfo=timezone.utc)
            _invoice(db, co, cust, total="1000.00", tax="70.00", when=when,
                     source="jurisdiction", jurisdiction="Cayuga County, NY")
            tfs.accumulate_period(db, co.id, "2026-Q2")
            snap1 = [
                (r.jurisdiction_name, str(r.gross_sales), str(r.taxable_sales),
                 str(r.exempt_sales), str(r.tax_computed), r.invoice_count)
                for r in db.query(TaxPeriod).filter(
                    TaxPeriod.company_id == co.id).order_by(TaxPeriod.jurisdiction_name)
            ]
            tfs.accumulate_period(db, co.id, "2026-Q2")
            db.expire_all()
            snap2 = [
                (r.jurisdiction_name, str(r.gross_sales), str(r.taxable_sales),
                 str(r.exempt_sales), str(r.tax_computed), r.invoice_count)
                for r in db.query(TaxPeriod).filter(
                    TaxPeriod.company_id == co.id).order_by(TaxPeriod.jurisdiction_name)
            ]
            assert snap1 == snap2 and len(snap1) == 1
        finally:
            _cleanup(db, [co.id])

    def test_finance_charges_and_drafts_stay_out(self, db):
        co, cust, _, _ = _world(db, "q3")
        try:
            when = datetime(2026, 7, 10, tzinfo=timezone.utc)
            fc = _invoice(db, co, cust, total="15.00", tax="0.00", when=when)
            fc.is_finance_charge = True
            _invoice(db, co, cust, total="999.00", tax="0.00", when=when,
                     status="draft")
            db.commit()
            out = tfs.accumulate_period(db, co.id, "2026-Q2")
            assert out["invoices"] == 0
        finally:
            _cleanup(db, [co.id])

    def test_tax_summary_stub_is_dead(self, db):
        """get_tax_summary reads real classification now — the
        hardcoded-zero stub died by replacement."""
        from app.services.financial_report_service import get_tax_summary
        co, cust, _, _ = _world(db, "q4")
        try:
            when = datetime(2026, 7, 10, tzinfo=timezone.utc)
            _invoice(db, co, cust, total="1000.00", tax="70.00", when=when,
                     source="jurisdiction", jurisdiction="Cayuga County, NY")
            out = get_tax_summary(db, co.id, date(2026, 7, 1), date(2026, 7, 31))
            assert out["total_tax"] == 70.0
            assert out["jurisdictions"][0]["jurisdiction"] == "Cayuga County, NY"
        finally:
            _cleanup(db, [co.id])


class TestNYPeriodCalendar:
    """The rule, pinned: NY quarterly sales-tax calendar — Q1 Mar–May,
    Q2 Jun–Aug, Q3 Sep–Nov, Q4 Dec–Feb — BY INVOICE DATE; due the 20th
    after period end."""

    def test_assignment_by_invoice_date(self, db):
        assert tfs.period_for_date(date(2026, 4, 15))["key"] == "2026-Q1"
        assert tfs.period_for_date(date(2026, 7, 21))["key"] == "2026-Q2"
        assert tfs.period_for_date(date(2026, 10, 1))["key"] == "2026-Q3"
        assert tfs.period_for_date(date(2026, 12, 31))["key"] == "2026-Q4"
        # Jan/Feb belong to the PRIOR year's Q4 (Dec–Feb straddles)
        assert tfs.period_for_date(date(2027, 1, 15))["key"] == "2026-Q4"
        assert tfs.period_for_date(date(2027, 2, 28))["key"] == "2026-Q4"

    def test_due_dates(self, db):
        assert tfs.due_date_for_period(date(2026, 5, 31)) == date(2026, 6, 20)
        assert tfs.due_date_for_period(date(2027, 2, 28)) == date(2027, 3, 20)


class TestIsolation:
    def test_certificates_are_tenant_scoped(self, db):
        co_a, cust_a, vault_a, _ = _world(db, "ia")
        co_b, cust_b, vault_b, _ = _world(db, "ib")
        try:
            # A's blanket cert must not exempt B's identically-named world
            db.add(TaxCertificate(
                company_id=co_a.id, customer_id=cust_a.id,
                cert_type="resale", cert_number="A-ONLY"))
            db.commit()
            out_b = resolve_line_tax(
                db, co_b.id,
                lines=[{"product_id": vault_b.id, "amount": Decimal("1000.00")}],
                customer_id=cust_b.id)
            assert out_b.tax_amount == Decimal("70.00")  # B still taxes

            # B cannot read A's return
            when = datetime(2026, 7, 10, tzinfo=timezone.utc)
            _invoice(db, co_a, cust_a, total="1000.00", tax="70.00", when=when,
                     source="jurisdiction", jurisdiction="Cayuga County, NY")
            tfs.accumulate_period(db, co_a.id, "2026-Q2")
            ret_b = tfs.get_return(db, co_b.id, "2026-Q2")
            assert ret_b["totals"]["tax_computed"] == 0
        finally:
            _cleanup(db, [co_a.id, co_b.id])

    def test_product_exemption_is_per_company(self, db):
        co_a, cust_a, _, marker_a = _world(db, "pa")
        co_b, cust_b, vault_b, _ = _world(db, "pb")
        try:
            # A's exempt marker id resolved in B's book: unknown product →
            # taxable (products are looked up company-scoped).
            out = resolve_line_tax(
                db, co_b.id,
                lines=[{"product_id": marker_a.id, "amount": Decimal("500.00")}],
                customer_id=cust_b.id)
            assert out.tax_amount == Decimal("35.00")  # 7% of 500
        finally:
            _cleanup(db, [co_a.id, co_b.id])


class TestCrossTenantZeroDies:
    """THE VAULT-ORDER SITE (Beat 8's landing): the hardcoded $0 died —
    the cross-tenant sale resolves through the three-axis chain.
    Hand-proven BOTH ways: a product-exempt vault answers $0 WITH its
    documented reason; a taxable vault taxes honestly through the
    FH-mirror customer's county."""

    def _cross_world(self, db, tag):
        from app.models.fh_case import FHCase
        from app.models.fh_manufacturer_relationship import FHManufacturerRelationship
        mfg, _cust, vault, marker = _world(db, tag)  # Cayuga 7% book
        fh = Company(name=f"FH {tag}", slug=f"fh-{tag}-{uuid.uuid4().hex[:6]}")
        db.add(fh)
        db.flush()
        # The cross-tenant mirror: the FH exists as a Customer row in the
        # manufacturer's book with id == the FH tenant id (the FK's law).
        mirror = Customer(id=fh.id, company_id=mfg.id, name=fh.name,
                          zip_code="13021")
        rel = FHManufacturerRelationship(
            funeral_home_tenant_id=fh.id, manufacturer_tenant_id=mfg.id)
        case = FHCase(company_id=fh.id,
                      case_number=f"FC-T-{uuid.uuid4().hex[:5]}",
                      deceased_first_name="John", deceased_last_name="Smith",
                      deceased_date_of_death=date(2026, 7, 1))
        db.add_all([mirror, rel, case])
        db.commit()
        return mfg, fh, case, vault, marker

    def _submit(self, db, fh, mfg, case, product, price):
        from app.services.vault_order_service import submit_vault_order
        return submit_vault_order(
            db, fh.id, case.id,
            {"manufacturer_tenant_id": mfg.id, "vault_product_id": product.id,
             "vault_product_name": product.name, "quantity": 1,
             "unit_price": price},
            performed_by_id=None,
        )

    def test_taxable_vault_taxes_honestly(self, db):
        from app.models.sales_order import SalesOrder
        mfg, fh, case, vault, _ = self._cross_world(db, "x1")
        try:
            vo = self._submit(db, fh, mfg, case, vault, "1000.00")
            so = db.query(SalesOrder).filter(
                SalesOrder.id == vo.manufacturer_order_id).one()
            assert so.tax_amount == Decimal("70.00")
            assert so.total == Decimal("1070.00")
            assert "resolved: 7% — Cayuga County, NY" in (so.notes or "")
        finally:
            self._cross_cleanup(db, mfg, fh)

    def test_product_exempt_vault_answers_zero_with_reason(self, db):
        from app.models.sales_order import SalesOrder
        mfg, fh, case, _, marker = self._cross_world(db, "x2")
        try:
            vo = self._submit(db, fh, mfg, case, marker, "500.00")
            so = db.query(SalesOrder).filter(
                SalesOrder.id == vo.manufacturer_order_id).one()
            assert so.tax_amount == Decimal("0.00")
            assert so.total == Decimal("500.00")
            assert "product-exempt" in (so.notes or "")
        finally:
            self._cross_cleanup(db, mfg, fh)

    def _cross_cleanup(self, db, mfg, fh):
        for stmt in (
            "DELETE FROM fh_vault_orders WHERE company_id = :c",
            "DELETE FROM fh_case_activity WHERE case_id IN (SELECT id FROM fh_cases WHERE company_id = :c)",
            "DELETE FROM fh_case_contacts WHERE case_id IN (SELECT id FROM fh_cases WHERE company_id = :c)",
            "DELETE FROM fh_cases WHERE company_id = :c",
            "DELETE FROM fh_manufacturer_relationships WHERE funeral_home_tenant_id = :c",
            "DELETE FROM deliveries WHERE company_id = :m",
            "DELETE FROM delivery_settings WHERE company_id = :m",
        ):
            try:
                db.execute(sql_text(stmt), {"c": fh.id, "m": mfg.id})
                db.commit()
            except Exception:
                db.rollback()
        _cleanup(db, [mfg.id, fh.id])
