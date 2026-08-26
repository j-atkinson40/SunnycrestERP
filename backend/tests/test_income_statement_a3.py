"""LEDGER-1 A-3 — the income statement moves onto the ledger. CHARACTERIZATION.

Tests tagged WRONGNESS pass against the CURRENT code and are flipped in the same
commit, prior bodies quoted verbatim in the flipped test's docstring.

WHAT IS WRONG TODAY. `_sum_invoices_by_gl_type` carries the comment "Simple
aggregation — group by a generic 'Sales Revenue' for now" and:

  * IGNORES its own `gl_type` argument entirely — every call returns revenue
  * fabricates a `4000 / Sales Revenue` row that need not exist on the chart
  * sums with `float(i.total)` in a file whose module docstring reads
    "All monetary calculations use Decimal, never float"
  * reads INVOICES, so a posted journal entry is invisible to the P&L

Its neighbour `_sum_by_gl_type` is NOT a stub — it is a documented, honest
implementation that returns [] for cogs because no COGS dimension existed in the
model. r174 created that dimension. A-3 completes a function that correctly
declined to guess; it does not fix a stub.

PRODUCTION, read-only 2026-08-26: 15 journal entries, ALL draft, 0 posted, 30
lines, one tenant. So the first honest income statement is empty — the same
answer the trial balance gives, for the same reason.

Cleans up its own `is3-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models.accounting_analysis import TenantGLMapping
from app.models.company import Company
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.services import financial_report_service as frs
from app.services.journal_entry_service import JournalLineSpec, create_journal_entry
from tests._cleanup import purge_companies_by_slug

_SLUG = "is3-"
_START = date(2026, 1, 1)
_END = date(2026, 12, 31)


@pytest.fixture(autouse=True)
def _purge():
    yield
    s = SessionLocal()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")
    finally:
        s.close()


class _Env:
    def __init__(self, s):
        self.s = s
        sfx = uuid.uuid4().hex[:8]
        self.company = Company(id=str(uuid.uuid4()), name=f"IS3 {sfx}",
                               slug=f"{_SLUG}{sfx}", is_active=True,
                               vertical="manufacturing")
        s.add(self.company); s.flush()
        self.co = self.company.id
        self._n = 0

    def gl(self, *, number, name, category):
        m = TenantGLMapping(id=str(uuid.uuid4()), tenant_id=self.co,
                            platform_category=category, account_number=number,
                            account_name=name, is_active=True)
        self.s.add(m); self.s.flush()
        return m

    def post(self, *, lines, when=None, status="posted"):
        """`lines` is [(TenantGLMapping, debit, credit), ...]."""
        self._n += 1
        when = when or date(2026, 6, 30)
        return create_journal_entry(
            self.s, tenant_id=self.co, entry_number=f"IS3-{self._n:04d}",
            entry_type="manual", status=status, entry_date=when,
            period_month=when.month, period_year=when.year,
            description=f"probe {self._n}",
            lines=[JournalLineSpec(gl_account_id=m.id, gl_account_number=m.account_number,
                                   gl_account_name=m.account_name,
                                   debit_amount=Decimal(d), credit_amount=Decimal(c))
                   for m, d, c in lines])

    def invoice(self, *, total, when=None):
        cust = Customer(id=str(uuid.uuid4()), company_id=self.co,
                        name="IS3 customer", account_number=f"C{self._n}")
        self.s.add(cust); self.s.flush()
        inv = Invoice(id=str(uuid.uuid4()), company_id=self.co, customer_id=cust.id,
                      number=f"INV-{uuid.uuid4().hex[:6]}", status="sent",
                      invoice_date=when or date(2026, 6, 30),
                      due_date=when or date(2026, 6, 30), total=Decimal(total))
        self.s.add(inv); self.s.flush()
        return inv


@pytest.fixture
def env():
    s = SessionLocal()
    e = _Env(s)
    yield e
    s.rollback(); s.close()


# ── DELIBERATE PIN FLIPS ────────────────────────────────────────────────────


def _sec(r, category):
    return next(x for x in r["sections"] if x["category"] == category)


class TestTheLedgerIsTheSource:
    """The four characterizations this class replaces read, verbatim:

        def test_WRONGNESS_revenue_is_a_fabricated_account(self, env):
            env.invoice(total="1000.00"); env.s.commit()
            r = frs.get_income_statement(env.s, env.co, _START, _END)
            assert r["revenue"] == [{"account_number": "4000",
                                     "account_name": "Sales Revenue",
                                     "amount": 1000.0}]

        def test_WRONGNESS_the_amount_is_a_float(self, env):
            ... assert isinstance(r["revenue"][0]["amount"], float)

        def test_WRONGNESS_gl_type_is_ignored(self, env):
            got = frs._sum_invoices_by_gl_type(env.s, env.co, _START, _END, "cogs")
            assert got == [{"account_number": "4000", "account_name": "Sales Revenue",
                            "amount": 500.0}]

        def test_WRONGNESS_a_posted_journal_entry_is_invisible(self, env):
            ... assert r["revenue"] == [] and r["total_revenue"] == 0

    All four passed. `_sum_invoices_by_gl_type` is gone.
    """

    def test_a_posted_journal_entry_IS_the_revenue(self, env):
        rev = env.gl(number="5010", name="PRECAST SALES", category="revenue")
        cash = env.gl(number="1010", name="Cash", category="current_asset")
        env.post(lines=[(cash, "2500.00", "0.00"), (rev, "0.00", "2500.00")])
        env.s.commit()
        r = frs.get_income_statement(env.s, env.co, _START, _END)
        assert _sec(r, "revenue")["accounts"] == [
            {"account_number": "5010", "account_name": "PRECAST SALES",
             "amount": Decimal("2500.00")}]
        assert r["total_revenue"] == Decimal("2500.00")

    def test_the_account_is_the_real_one_not_a_fabricated_4000(self, env):
        rev = env.gl(number="5010", name="PRECAST SALES", category="revenue")
        cash = env.gl(number="1010", name="Cash", category="current_asset")
        env.post(lines=[(cash, "100.00", "0.00"), (rev, "0.00", "100.00")])
        env.s.commit()
        r = frs.get_income_statement(env.s, env.co, _START, _END)
        numbers = {a["account_number"] for a in _sec(r, "revenue")["accounts"]}
        assert numbers == {"5010"}
        assert "4000" not in numbers

    def test_amounts_are_Decimal_never_float(self, env):
        rev = env.gl(number="5010", name="PRECAST SALES", category="revenue")
        cash = env.gl(number="1010", name="Cash", category="current_asset")
        env.post(lines=[(cash, "0.10", "0.00"), (rev, "0.00", "0.10")])
        env.post(lines=[(cash, "0.20", "0.00"), (rev, "0.00", "0.20")])
        env.s.commit()
        r = frs.get_income_statement(env.s, env.co, _START, _END)
        # 0.10 + 0.20 == 0.30 exactly; in binary float it is 0.30000000000000004
        assert _sec(r, "revenue")["total"] == Decimal("0.30")
        assert isinstance(r["net_income"], Decimal)

    def test_an_invoice_alone_is_NOT_revenue(self, env):
        """The mirror of the flip. Revenue is what the ledger says; an invoice
        with no posting behind it is an AR fact, and the reconciliation below is
        where that discrepancy surfaces."""
        env.invoice(total="1000.00")
        env.s.commit()
        r = frs.get_income_statement(env.s, env.co, _START, _END)
        assert _sec(r, "revenue")["accounts"] == []
        assert r["has_postings"] is False


class TestTheEmptyLedgerAgain:

    def test_no_postings_is_the_honest_first_answer(self, env):
        r = frs.get_income_statement(env.s, env.co, _START, _END)
        assert r["has_postings"] is False
        assert r["total_revenue"] == Decimal("0")
        assert r["net_income"] == Decimal("0")
        assert all(s["accounts"] == [] for s in r["sections"])


class TestOrderAndSubtotals:

    def test_the_sections_are_in_the_ruled_order(self, env):
        assert [s["category"] for s in
                frs.get_income_statement(env.s, env.co, _START, _END)["sections"]] == [
            "revenue", "contra_revenue", "cogs", "delivery_cost",
            "expense", "tax_expense", "other_income", "other_expense"]

    def test_gross_profit_excludes_delivery_cost(self, env):
        """The ruling: delivery is a cost of getting product to the customer,
        not of producing it, so it sits BELOW gross profit. Burying it in COGS
        makes gross margin incomparable across licensees who deliver
        differently."""
        rev = env.gl(number="5010", name="SALES", category="revenue")
        cogs = env.gl(number="5500", name="MATERIALS", category="cogs")
        dely = env.gl(number="5600", name="FREIGHT OUT", category="delivery_cost")
        cash = env.gl(number="1010", name="Cash", category="current_asset")
        env.post(lines=[(cash, "1000.00", "0.00"), (rev, "0.00", "1000.00")])
        env.post(lines=[(cogs, "400.00", "0.00"), (cash, "0.00", "400.00")])
        env.post(lines=[(dely, "150.00", "0.00"), (cash, "0.00", "150.00")])
        env.s.commit()
        r = frs.get_income_statement(env.s, env.co, _START, _END)
        # gross profit = revenue 1000.00 - contra 0.00 - cogs 400.00 = 600.00
        assert r["gross_profit"] == Decimal("600.00")
        # delivery 150.00 sits BELOW it: operating income = 600.00 - 150.00 - 0.00
        assert r["operating_income"] == Decimal("450.00")
        assert _sec(r, "delivery_cost")["total"] == Decimal("150.00")

    def test_contra_revenue_reduces_revenue(self, env):
        rev = env.gl(number="5010", name="SALES", category="revenue")
        contra = env.gl(number="5150", name="REFUNDS-RETURNS", category="contra_revenue")
        cash = env.gl(number="1010", name="Cash", category="current_asset")
        env.post(lines=[(cash, "1000.00", "0.00"), (rev, "0.00", "1000.00")])
        env.post(lines=[(contra, "75.00", "0.00"), (cash, "0.00", "75.00")])
        env.s.commit()
        r = frs.get_income_statement(env.s, env.co, _START, _END)
        # contra is DEBIT-natured: 75.00 debits - 0 credits = 75.00
        assert _sec(r, "contra_revenue")["total"] == Decimal("75.00")
        # gross profit = 1000.00 - 75.00 - 0.00 = 925.00
        assert r["gross_profit"] == Decimal("925.00")

    def test_net_income_end_to_end(self, env):
        rev = env.gl(number="5010", name="SALES", category="revenue")
        cogs = env.gl(number="5500", name="MATERIALS", category="cogs")
        dely = env.gl(number="5600", name="FREIGHT OUT", category="delivery_cost")
        exp = env.gl(number="6000", name="RENT", category="expense")
        tax = env.gl(number="9100", name="TAX", category="tax_expense")
        oi = env.gl(number="9300", name="INTEREST INCOME", category="other_income")
        oe = env.gl(number="9130", name="INTEREST EXPENSE", category="other_expense")
        cash = env.gl(number="1010", name="Cash", category="current_asset")
        for acct, amt in [(cogs, "400.00"), (dely, "150.00"), (exp, "200.00"),
                          (tax, "50.00"), (oe, "25.00")]:
            env.post(lines=[(acct, amt, "0.00"), (cash, "0.00", amt)])
        env.post(lines=[(cash, "1000.00", "0.00"), (rev, "0.00", "1000.00")])
        env.post(lines=[(cash, "30.00", "0.00"), (oi, "0.00", "30.00")])
        env.s.commit()
        r = frs.get_income_statement(env.s, env.co, _START, _END)
        # gross    = 1000.00 - 0.00 - 400.00           =  600.00
        # operating=  600.00 - 150.00 - 200.00         =  250.00
        # net      =  250.00 -  50.00 + 30.00 - 25.00  =  205.00
        assert r["gross_profit"] == Decimal("600.00")
        assert r["operating_income"] == Decimal("250.00")
        assert r["net_income"] == Decimal("205.00")
        # gross margin = 600.00 / 1000.00 = 60.0%
        assert r["gross_margin_percent"] == Decimal("60.0")


class TestNothingIsSilentlyDropped:

    def test_balance_sheet_accounts_do_not_appear(self, env):
        cash = env.gl(number="1010", name="Cash", category="current_asset")
        rev = env.gl(number="5010", name="SALES", category="revenue")
        env.post(lines=[(cash, "100.00", "0.00"), (rev, "0.00", "100.00")])
        env.s.commit()
        r = frs.get_income_statement(env.s, env.co, _START, _END)
        everywhere = {a["account_number"] for s in r["sections"] for a in s["accounts"]}
        assert "1010" not in everywhere
        assert r["unplaceable"]["accounts"] == [], "cash is not unplaceable, it is a balance-sheet account"

    def test_other_and_unclassified_are_reported_not_guessed(self, env):
        """`other` may be an income OR a balance-sheet account. Assigning it
        either way would be a guess, so it is stated and excluded from net
        income with the amount shown."""
        oth = env.gl(number="9400", name="SUSPENSE - MISC.", category="other")
        cash = env.gl(number="1010", name="Cash", category="current_asset")
        env.post(lines=[(oth, "42.00", "0.00"), (cash, "0.00", "42.00")])
        env.s.commit()
        r = frs.get_income_statement(env.s, env.co, _START, _END)
        assert [a["account_number"] for a in r["unplaceable"]["accounts"]] == ["9400"]
        assert r["unplaceable"]["net_amount"] == Decimal("42.00")
        assert r["unplaceable"]["excluded_from_net_income"] is True
        assert r["net_income"] == Decimal("0")

    def test_a_line_with_no_GL_mapping_is_surfaced_with_its_reason(self, env):
        """`create_journal_entry` does no GL lookup — only the API-level
        `create_entry` validates — so an unresolvable gl_account_id is possible.
        Dropping it would be wrong in the way hardest to notice."""
        from app.services.journal_entry_service import JournalLineSpec, create_journal_entry
        cash = env.gl(number="1010", name="Cash", category="current_asset")
        create_journal_entry(
            env.s, tenant_id=env.co, entry_number="IS3-ORPHAN", entry_type="manual",
            status="posted", entry_date=date(2026, 6, 30), period_month=6,
            period_year=2026, description="orphan",
            lines=[JournalLineSpec(gl_account_id=str(uuid.uuid4()),
                                   gl_account_number="7777", gl_account_name="Ghost",
                                   credit_amount=Decimal("99.00")),
                   JournalLineSpec(gl_account_id=cash.id, gl_account_number="1010",
                                   gl_account_name="Cash", debit_amount=Decimal("99.00"))])
        env.s.commit()
        r = frs.get_income_statement(env.s, env.co, _START, _END)
        orphan = next(a for a in r["unplaceable"]["accounts"] if a["account_number"] == "7777")
        assert "no GL mapping" in orphan["reason"]
        assert orphan["category"] is None


class TestRevenueReconcilesToTheARSubledger:
    """Live from A-3, and it could not have been meaningful before: until
    revenue came from the GL, the reported figure WAS the invoice total, so the
    two sides were the same number and agreement was tautological."""

    def test_agreement_is_reported_when_they_match(self, env):
        rev = env.gl(number="5010", name="SALES", category="revenue")
        cash = env.gl(number="1010", name="Cash", category="current_asset")
        env.post(lines=[(cash, "1000.00", "0.00"), (rev, "0.00", "1000.00")])
        env.invoice(total="1000.00")
        env.s.commit()
        rec = frs.get_income_statement(env.s, env.co, _START, _END)["reconciliation"]
        assert rec["gl_revenue"] == Decimal("1000.00")
        assert rec["ar_subledger_revenue"] == Decimal("1000.00")
        assert rec["difference"] == Decimal("0")
        assert rec["agrees"] is True

    def test_a_difference_is_reported_with_both_figures(self, env):
        rev = env.gl(number="5010", name="SALES", category="revenue")
        cash = env.gl(number="1010", name="Cash", category="current_asset")
        env.post(lines=[(cash, "1000.00", "0.00"), (rev, "0.00", "1000.00")])
        env.invoice(total="900.00")
        env.s.commit()
        rec = frs.get_income_statement(env.s, env.co, _START, _END)["reconciliation"]
        # GL 1000.00 - AR 900.00 = 100.00 recognised without an invoice behind it
        assert rec["difference"] == Decimal("100.00")
        assert rec["agrees"] is False
        assert rec["gl_revenue"] == Decimal("1000.00")
        assert rec["ar_subledger_revenue"] == Decimal("900.00")

    def test_invoices_with_no_posting_show_as_a_NEGATIVE_difference(self, env):
        """The common real case today: invoices raised, nothing posted. The
        report must say so rather than showing a matching zero on both sides."""
        env.invoice(total="500.00")
        env.s.commit()
        rec = frs.get_income_statement(env.s, env.co, _START, _END)["reconciliation"]
        # GL 0 - AR 500.00 = -500.00
        assert rec["difference"] == Decimal("-500.00")
        assert rec["agrees"] is False


class TestExpensesReconcileToTheAPSubledger:
    """Symmetric to the AR side, and load-bearing for a different reason.

    `ar_invoice_posting` exists, so an invoice CAN reach the ledger. Nothing
    posts vendor bills to the GL — there is no AP posting path at all — so
    ledger expenses are structurally empty rather than merely empty today.

    Before A-3 the P&L showed vendor-bill expenses through `_sum_by_gl_type`,
    which D-2 did real work to make honest. Reading the ledger is correct, but
    those expenses stop appearing, and this is what stops that being silent.
    """

    def test_bills_with_no_posting_show_as_a_NEGATIVE_difference(self, env):
        from datetime import datetime, timezone

        from app.models.vendor import Vendor
        from app.models.vendor_bill import VendorBill

        v = Vendor(id=str(uuid.uuid4()), company_id=env.co, name="IS3 vendor",
                   account_number=f"V-{uuid.uuid4().hex[:8]}")
        env.s.add(v); env.s.flush()
        env.s.add(VendorBill(
            id=str(uuid.uuid4()), company_id=env.co, vendor_id=v.id,
            number=f"BILL-{uuid.uuid4().hex[:8]}", status="approved",
            bill_date=datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc),
            due_date=datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc),
            subtotal=Decimal("750.00"), tax_amount=Decimal("0"),
            total=Decimal("750.00"), amount_paid=Decimal("0")))
        env.s.commit()
        r = frs.get_income_statement(env.s, env.co, _START, _END)
        rec = r["expense_reconciliation"]
        # GL 0 - AP 750.00 = -750.00, and the P&L shows no expense at all
        assert rec["gl_expense"] == Decimal("0")
        assert rec["ap_subledger_expense"] == Decimal("750.00")
        assert rec["difference"] == Decimal("-750.00")
        assert rec["agrees"] is False
        assert "No AP-to-GL posting path exists" in rec["note"]

    def test_the_gl_side_sums_cogs_delivery_and_expense(self, env):
        cogs = env.gl(number="5500", name="MATERIALS", category="cogs")
        dely = env.gl(number="5600", name="FREIGHT OUT", category="delivery_cost")
        exp = env.gl(number="6000", name="RENT", category="expense")
        cash = env.gl(number="1010", name="Cash", category="current_asset")
        for acct, amt in [(cogs, "400.00"), (dely, "150.00"), (exp, "200.00")]:
            env.post(lines=[(acct, amt, "0.00"), (cash, "0.00", amt)])
        env.s.commit()
        rec = frs.get_income_statement(env.s, env.co, _START, _END)["expense_reconciliation"]
        # 400.00 + 150.00 + 200.00 = 750.00
        assert rec["gl_expense"] == Decimal("750.00")

    def test_a_bill_timestamped_LATE_on_the_closing_day_is_included(self, env):
        """`VendorBill.bill_date` is a DATETIME. A naive `<= period_end` compares
        a timestamp against midnight and silently drops everything billed later
        that day — invisible unless a bill happens to land on the boundary.
        End-exclusive, per the D-1/D-2 discipline."""
        from datetime import datetime, timezone

        from app.models.vendor import Vendor
        from app.models.vendor_bill import VendorBill

        v = Vendor(id=str(uuid.uuid4()), company_id=env.co, name="IS3 boundary",
                   account_number=f"V-{uuid.uuid4().hex[:8]}")
        env.s.add(v); env.s.flush()
        env.s.add(VendorBill(
            id=str(uuid.uuid4()), company_id=env.co, vendor_id=v.id,
            number=f"BILL-{uuid.uuid4().hex[:8]}", status="approved",
            # _END is 2026-12-31; this is 23:59 on that day
            bill_date=datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc),
            due_date=datetime(2027, 1, 30, 12, 0, tzinfo=timezone.utc),
            subtotal=Decimal("10.00"), tax_amount=Decimal("0"),
            total=Decimal("10.00"), amount_paid=Decimal("0")))
        env.s.commit()
        rec = frs.get_income_statement(env.s, env.co, _START, _END)["expense_reconciliation"]
        assert rec["ap_subledger_expense"] == Decimal("10.00"), \
            "a bill on the closing day must not fall through the boundary"


class TestTheTaxAgentDistinguishesZeroFromAbsence:
    """A-3 consequence, and the reason it needed handling rather than noting.

    `estimated_tax_prep_agent` reads `get_income_statement`. Before A-3 that
    returned invoice-derived figures, which are non-zero. Now it reads the
    ledger, so a tenant with nothing posted yields net income of exactly zero —
    and the agent's message was `f"Period net income: ${x:,.2f}"`, which renders
    "$0.00" as a computed result indistinguishable from a business that broke
    even. That annualizes into a $0.00 estimated tax payment an operator could
    act on.

    An estimate of zero because nothing has POSTED is a different statement from
    an estimate of zero because nothing is OWED. Only one of them is an answer.

    This agent had NO test file before A-3 and was not in ci_gate.txt.
    """

    def _agent(self, env):
        """`_period_start`/`_period_end` read `self.job`, which `run_job` sets.

        Stubbed with a namespace carrying EXACTLY the two attributes the step
        reads, not a MagicMock. A MagicMock would answer every attribute
        access, so a step that started reading `job.something_else` would keep
        passing against a mock that invented it.
        """
        from types import SimpleNamespace

        from app.services.agents.estimated_tax_prep_agent import EstimatedTaxPrepAgent
        a = EstimatedTaxPrepAgent(db=env.s, tenant_id=env.co, job_id=None, dry_run=True)
        a.job = SimpleNamespace(period_start=_START, period_end=_END)
        return a

    def test_an_empty_ledger_raises_an_anomaly_and_says_ABSENCE(self, env):
        r = self._agent(env)._step_compute_income_statement()
        assert r.data["has_postings"] is False
        codes = {a.anomaly_type for a in r.anomalies}
        assert "no_posted_ledger_activity" in codes
        assert "not because there was no income" in next(
            a.description for a in r.anomalies
            if a.anomaly_type == "no_posted_ledger_activity")

    def test_the_message_does_not_present_a_computed_figure(self, env):
        r = self._agent(env)._step_compute_income_statement()
        assert "$0.00" not in r.message
        assert "nothing has been posted" in r.message

    def test_a_posted_ledger_still_reports_normally(self, env):
        """The guard must not swallow the real path — a fix that always warned
        would satisfy the two tests above."""
        from datetime import date as _d
        rev = env.gl(number="5010", name="SALES", category="revenue")
        cash = env.gl(number="1010", name="Cash", category="current_asset")
        env.post(lines=[(cash, "1000.00", "0.00"), (rev, "0.00", "1000.00")],
                 when=_d.today())
        env.s.commit()
        r = self._agent(env)._step_compute_income_statement()
        assert r.data["has_postings"] is True
        assert "no_posted_ledger_activity" not in {a.anomaly_type for a in r.anomalies}
        assert "$" in r.message
