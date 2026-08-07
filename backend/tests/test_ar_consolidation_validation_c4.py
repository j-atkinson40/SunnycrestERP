"""AR-1 C-4 — validation across the arc, through the REAL readers.

C-1, C-2 and C-3 each pin their own slice. This file is the cross-check: one
customer, one mixed invoice set, hand-computed once, and every consumer asked
independently whether it agrees.

The point is that these are the ACTUAL code paths — `get_ar_aging`, the
sweeper's own computation, the consolidated expression the dashboards use, the
Sage importer — not reconstructions of them. A reconstruction can agree with a
formula while the caller uses a different one.

⚠️ WHAT IS **NOT** TRUE YET, stated here because a validation section reading
"drift reports" would be true and misleading:

    THE SWEEPER STILL REWRITES `current_balance`. Phase 3 shipped
    report-ALONGSIDE-correct, deliberately. Removing the correction while the
    only report destination had never rendered a row would have left drift
    neither fixed nor seen. The correction is retained until the triage queue
    exists to receive the report; phase 4 removes it and flips
    `report_payload["corrections_applied"]` to False.

    `test_drift_reports_AND_STILL_CORRECTS` below pins that as the current
    state, so nobody reading this in October assumes the rewrite stopped.

Same discipline as "L-3 complete does not mean reconciliation ties to the GL."

Cleans up its own `arc4-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func

from app.database import SessionLocal
from app.models.agent_anomaly import AgentAnomaly
from app.models.agent import AgentJob
from app.models.company import Company
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.services.ar_balance import is_receivable
from app.services.data_migration_service import import_open_invoices
from app.services.proactive_agents import run_ar_balance_reconciliation
from app.services.sales_service import get_ar_aging
from tests._cleanup import purge_companies_by_slug

_SLUG = "arc4-"


@pytest.fixture(autouse=True)
def _purge():
    yield
    s = SessionLocal()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")
    finally:
        s.close()


@pytest.fixture
def env():
    s = SessionLocal()
    yield _Env(s)
    s.rollback()
    s.close()


class _Env:
    def __init__(self, s):
        self.s = s
        sfx = uuid.uuid4().hex[:8]
        self.company = Company(
            id=str(uuid.uuid4()), name=f"ARC4 {sfx}", slug=f"{_SLUG}{sfx}",
            is_active=True, vertical="manufacturing",
        )
        s.add(self.company); s.flush()
        self.co = self.company.id
        self.cust = Customer(
            id=str(uuid.uuid4()), company_id=self.co, name="Hopkins FH",
            is_active=True, current_balance=Decimal("0.00"),
        )
        s.add(self.cust); s.flush()

    def invoice(self, *, total, status, paid="0.00", credited="0.00",
                written_off="0.00", day=1):
        inv = Invoice(
            id=str(uuid.uuid4()), company_id=self.co, customer_id=self.cust.id,
            number=f"INV-{uuid.uuid4().hex[:6]}", status=status,
            invoice_date=datetime(2026, 5, day, tzinfo=timezone.utc),
            due_date=datetime(2026, 5, 31, tzinfo=timezone.utc),
            subtotal=Decimal(total), tax_rate=Decimal("0"),
            tax_amount=Decimal("0"), total=Decimal(total),
            amount_paid=Decimal(paid), amount_credited=Decimal(credited),
            written_off_amount=Decimal(written_off),
        )
        self.s.add(inv); self.s.flush()
        return inv

    def consolidated(self) -> Decimal:
        return self.s.query(
            func.coalesce(func.sum(Invoice.balance_remaining), 0)
        ).filter(Invoice.company_id == self.co, is_receivable()).scalar()


def _mixed_set(env) -> Decimal:
    """One customer, every status and every term exercised at once.

    HAND MATH, per invoice, total − paid − credited − written_off:

        sent      1000.00 − 200.00 −   0.00 −   0.00 =  800.00
        open       800.00 −   0.00 −   0.00 −   0.00 =  800.00   (aging blind pre-C-3)
        posted      42.50 −   0.00 −   0.00 −   0.00 =   42.50   (aging blind pre-C-3)
        overdue   1000.00 − 200.00 −   0.00 − 300.00 =  500.00   (partial write-off)
        sent       600.00 −   0.00 − 150.00 −   0.00 =  450.00   (credit memo)
        paid       300.00 − 300.00 −   0.00 −   0.00 =    0.00   (member, self-zeroes)
        write_off  400.00 −   0.00 −   0.00 − 400.00 =    0.00   (member, self-zeroes)
        draft      500.00                              EXCLUDED
        void       700.00                              EXCLUDED
                                                       ---------
                                                        2592.50
    """
    env.invoice(total="1000.00", status="sent", paid="200.00")
    env.invoice(total="800.00", status="open")
    env.invoice(total="42.50", status="posted")
    env.invoice(total="1000.00", status="overdue", paid="200.00", written_off="300.00")
    env.invoice(total="600.00", status="sent", credited="150.00")
    env.invoice(total="300.00", status="paid", paid="300.00")
    env.invoice(total="400.00", status="write_off", written_off="400.00")
    env.invoice(total="500.00", status="draft")
    env.invoice(total="700.00", status="void")
    env.s.commit()
    return Decimal("2592.50")


class TestEveryReaderReturnsTheSameNumber:
    def test_the_consolidated_expression_matches_the_hand_math(self, env):
        expected = _mixed_set(env)
        assert env.consolidated() == expected

    def test_the_python_branch_matches_the_sql_branch(self, env):
        """The hybrid's two compilation targets. If these disagree the
        definition has forked, which is the failure C-3 exists to prevent."""
        expected = _mixed_set(env)
        python_side = sum(
            (i.balance_remaining for i in
             env.s.query(Invoice).filter(Invoice.company_id == env.co,
                                         is_receivable()).all()),
            Decimal("0.00"),
        )
        assert python_side == expected == env.consolidated()

    def test_aging_matches(self, env):
        """`get_ar_aging` is the real reader an operator looks at."""
        expected = _mixed_set(env)
        report = get_ar_aging(env.s, env.co)
        aged = sum((c.buckets.total for c in report.customers), Decimal("0.00"))
        assert aged == expected
        assert report.company_summary.total == expected

    def test_the_sweeper_computes_the_same_number(self, env):
        """The sweeper is asked indirectly: give the customer the RIGHT stored
        balance and it must find no drift. If its formula still differed by a
        term it would 'correct' a correct balance."""
        expected = _mixed_set(env)
        env.cust.current_balance = expected
        env.s.commit()

        result = run_ar_balance_reconciliation(env.s, env.co)

        assert result["drift_reported"] == 0
        assert result["balances_corrected"] == 0
        env.s.refresh(env.cust)
        assert env.cust.current_balance == expected      # untouched


class TestAgingIncludesWhatTheExclusionSays:
    def test_open_and_posted_are_in_aging_now(self, env):
        """The two statuses the old 3-status filter dropped. Both are written
        by production paths and both post to AR."""
        env.invoice(total="800.00", status="open")
        env.invoice(total="42.50", status="posted")
        env.s.commit()

        report = get_ar_aging(env.s, env.co)
        # HAND MATH: 800.00 + 42.50 = 842.50
        assert report.company_summary.total == Decimal("842.50")

    def test_draft_and_void_are_not(self, env):
        env.invoice(total="500.00", status="draft")
        env.invoice(total="700.00", status="void")
        env.s.commit()

        report = get_ar_aging(env.s, env.co)
        assert report.company_summary.total == Decimal("0.00")
        assert report.customers == []


class TestAnImportedInvoiceMovesTheBalance:
    def test_end_to_end_through_the_real_importer(self, env):
        """C-1, cross-checked at the integration level rather than in isolation:
        import → balance moves → the sweeper then finds nothing to correct."""
        import_open_invoices(
            env.s, tenant_id=env.co,
            parsed_invoices=[{
                "sage_customer_no": "SAGECUST",
                "invoice_number": "SAGE-1",
                "balance": Decimal("1200.00"),
                "days_delinquent": 0,
                "invoice_date": datetime(2026, 5, 1, tzinfo=timezone.utc),
                "due_date": datetime(2026, 5, 31, tzinfo=timezone.utc),
            }],
            customer_id_map={"SAGECUST": env.cust.id},
            cutover_date=date(2026, 6, 30),
        )
        env.s.commit()
        env.s.refresh(env.cust)

        assert env.cust.current_balance == Decimal("1200.00")
        assert env.consolidated() == Decimal("1200.00")

        # And the sweeper agrees — no drift where there used to be 1200.00 of it.
        result = run_ar_balance_reconciliation(env.s, env.co)
        assert result["drift_reported"] == 0


class TestWhatIsDeferred:
    """THE HONEST CLAUSE. Read this before believing "drift reports"."""

    def test_drift_reports_AND_STILL_CORRECTS(self, env):
        """PHASE 3 STATE, PINNED AS SUCH.

        The sweeper reports drift durably AND still rewrites `current_balance`.
        Both halves are asserted here so the deferral is impossible to misread:
        a future reader who assumes the rewrite stopped will find this test
        saying otherwise, and phase 4 will have to flip it deliberately.
        """
        env.invoice(total="900.00", status="sent")
        env.s.commit()
        assert env.cust.current_balance == Decimal("0.00")

        result = run_ar_balance_reconciliation(env.s, env.co)

        # It REPORTS — durably, with the before-value.
        assert result["drift_reported"] == 1
        anomaly = (
            env.s.query(AgentAnomaly)
            .join(AgentJob, AgentAnomaly.agent_job_id == AgentJob.id)
            .filter(AgentJob.tenant_id == env.co).one()
        )
        assert anomaly.entity_id == env.cust.id
        assert anomaly.amount == Decimal("900.00")
        assert "was $0.00" in anomaly.description

        # ...AND IT STILL CORRECTS. This is the deferred half.
        env.s.refresh(env.cust)
        assert env.cust.current_balance == Decimal("900.00")
        assert result["balances_corrected"] == 1

        job = env.s.query(AgentJob).filter(AgentJob.tenant_id == env.co).one()
        # The handle phase 4 flips. If this is still True in a release that
        # claims the sweeper only reports, the claim is wrong.
        assert job.report_payload["corrections_applied"] is True
