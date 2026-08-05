"""AR-1 C-3 — one membership expression, one value expression.

THE SEAM. Balance, aging, statements, collections, the dashboards and the drift
sweeper all need the same two answers, and before this they each answered both,
differently — five distinct status filters and three different term-counts.

    WHICH invoices are receivable  → `ar_balance.is_receivable()`
    HOW MUCH each one owes         → `Invoice.balance_remaining` (a hybrid)

SYNTHETIC PROOF, DELIBERATELY. Production carries 6 invoices across
`sent`/`overdue`/`paid`, zero credits, zero write-offs, zero `open`, zero
`posted` — so every formula already agrees there and a production diff would
print zeros and prove nothing. These tests CONSTRUCT the cases the old filters
got wrong and show the number moving.

⚠️ OPERATOR-VISIBLE CONSEQUENCE, pinned here so it is not mistaken for a bug:
AGING WILL JUMP the first time an `open` or `posted` invoice exists. Both are
written by production paths (`draft_invoice_service.py:651,706` and
`finance_charge_service.py:384`) and both were invisible to the 3-status aging
filter. That jump is the fix working.

Cleans up its own `arc3-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func

from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.services.ar_balance import RECEIVABLE_EXCLUDED_STATUSES, is_receivable
from app.services.sales_service import get_ar_aging
from tests._cleanup import purge_companies_by_slug

_SLUG = "arc3-"

# The filters that were in use before C-3, kept verbatim so the tests can show
# what each one got wrong rather than assert it.
_OLD_AGING_3 = ("sent", "partial", "overdue")
_OLD_BOARD_4 = ("sent", "open", "partial", "overdue")
_OLD_SWEEPER_EXCLUSION = ("paid", "void", "draft", "write_off")


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
            id=str(uuid.uuid4()), name=f"ARC3 {sfx}", slug=f"{_SLUG}{sfx}",
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
                written_off="0.00") -> Invoice:
        inv = Invoice(
            id=str(uuid.uuid4()), company_id=self.co, customer_id=self.cust.id,
            number=f"INV-{uuid.uuid4().hex[:6]}", status=status,
            invoice_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            due_date=datetime(2026, 5, 31, tzinfo=timezone.utc),
            subtotal=Decimal(total), tax_rate=Decimal("0"),
            tax_amount=Decimal("0"), total=Decimal(total),
            amount_paid=Decimal(paid), amount_credited=Decimal(credited),
            written_off_amount=Decimal(written_off),
        )
        self.s.add(inv); self.s.flush()
        return inv

    def new_sum(self) -> Decimal:
        """The consolidated expression every reader now uses."""
        return self.s.query(
            func.coalesce(func.sum(Invoice.balance_remaining), 0)
        ).filter(Invoice.company_id == self.co, is_receivable()).scalar()

    def old_sum(self, statuses, *, terms=2) -> Decimal:
        """A pre-C-3 formula, reconstructed. `terms` is how many of the four
        that call site subtracted: 2 = the dashboards, 3 = the sweeper."""
        expr = Invoice.total - Invoice.amount_paid
        if terms >= 3:
            expr = expr - Invoice.amount_credited
        if terms >= 4:
            expr = expr - Invoice.written_off_amount
        return self.s.query(func.coalesce(func.sum(expr), 0)).filter(
            Invoice.company_id == self.co, Invoice.status.in_(statuses)
        ).scalar()


# ── the synthetic proof ─────────────────────────────────────────────────────


class TestTheStatusesThatUsedToVanish:
    def test_an_open_invoice_now_counts_and_used_to_be_invisible_to_aging(self, env):
        """`draft_invoice_service` issues invoices at `open` AND posts them to
        the customer balance — so an `open` invoice was counted by the board,
        counted by the sweeper, and MISSING FROM EVERY AGING REPORT.

        HAND MATH: one open invoice of 800.00, nothing paid.
            old 3-status aging : 0.00      ← the bug
            new                : 800.00
        """
        env.invoice(total="800.00", status="open")
        env.s.commit()

        assert env.old_sum(_OLD_AGING_3) == Decimal("0.00")
        assert env.new_sum() == Decimal("800.00")

    def test_a_posted_finance_charge_now_counts(self, env):
        """Finance charges are born `posted` (finance_charge_service.py:384)
        and post to AR at creation. `posted` was in NO inclusion filter — not
        the 3-status, not the board's 4-status — so it was visible only to the
        sweeper.

        HAND MATH: one posted charge of 42.50.
            old 3-status aging : 0.00
            old 4-status board : 0.00      ← `open` was added, `posted` never was
            new                : 42.50
        """
        env.invoice(total="42.50", status="posted")
        env.s.commit()

        assert env.old_sum(_OLD_AGING_3) == Decimal("0.00")
        assert env.old_sum(_OLD_BOARD_4) == Decimal("0.00")
        assert env.new_sum() == Decimal("42.50")

    def test_draft_and_void_stay_out(self, env):
        """The two exclusions, and the only two. A draft is not issued; a void
        is reversed."""
        env.invoice(total="500.00", status="draft")
        env.invoice(total="700.00", status="void")
        env.s.commit()

        assert env.new_sum() == Decimal("0.00")
        assert set(RECEIVABLE_EXCLUDED_STATUSES) == {"draft", "void"}


class TestTheTermsThatUsedToBeWrong:
    def test_a_PARTIAL_write_off_is_the_case_only_the_terms_can_fix(self, env):
        """THE ARGUMENT FOR THE WHOLE SHAPE.

        A partially written-off invoice KEEPS ITS ORDINARY STATUS, so no status
        filter can correct it. Only the four-term value expression can.

        HAND MATH: total 1000.00, paid 200.00, written off 300.00, status
        `overdue` (unchanged by the partial write-off).
            truth          : 1000 − 200 − 0 − 300 = 500.00
            dashboards (2) : 1000 − 200          = 800.00   ← over by 300
            sweeper    (3) : 1000 − 200 − 0      = 800.00   ← over by 300
            new        (4) :                       500.00
        """
        env.invoice(total="1000.00", status="overdue", paid="200.00",
                    written_off="300.00")
        env.s.commit()

        assert env.old_sum(_OLD_AGING_3, terms=2) == Decimal("800.00")
        assert env.old_sum(_OLD_AGING_3, terms=3) == Decimal("800.00")
        assert env.new_sum() == Decimal("500.00")

    def test_a_credit_memo_is_dropped_by_the_two_term_formula(self, env):
        """HAND MATH: total 600.00, credited 150.00, status `sent`.
            truth          : 600 − 0 − 150 − 0 = 450.00
            dashboards (2) : 600               = 600.00   ← over by 150
            new        (4) :                     450.00
        """
        env.invoice(total="600.00", status="sent", credited="150.00")
        env.s.commit()

        assert env.old_sum(_OLD_AGING_3, terms=2) == Decimal("600.00")
        assert env.new_sum() == Decimal("450.00")

    def test_paid_and_fully_written_off_contribute_nothing_without_being_excluded(self, env):
        """WHY THE EXCLUSION LIST IS ONLY TWO LONG. `paid` and `write_off` are
        members, and they self-zero — the value expression carries them.

        HAND MATH:
            paid      : 300 − 300 − 0 − 0 = 0.00
            write_off : 400 − 0 − 0 − 400 = 0.00
            live      : 250 − 0 − 0 − 0   = 250.00
            total                           250.00
        """
        env.invoice(total="300.00", status="paid", paid="300.00")
        env.invoice(total="400.00", status="write_off", written_off="400.00")
        env.invoice(total="250.00", status="sent")
        env.s.commit()

        assert env.new_sum() == Decimal("250.00")


class TestEveryReaderNowAgrees:
    def test_the_hybrid_returns_the_same_number_in_python_and_in_sql(self, env):
        """The point of the hybrid: one definition, two compilation targets. If
        these ever disagree, the two branches have drifted."""
        env.invoice(total="1000.00", status="overdue", paid="200.00",
                    credited="50.00", written_off="300.00")
        env.invoice(total="800.00", status="open")
        env.s.commit()

        python_side = sum(
            (i.balance_remaining for i in
             env.s.query(Invoice).filter(Invoice.company_id == env.co,
                                         is_receivable()).all()),
            Decimal("0.00"),
        )
        # HAND MATH: (1000−200−50−300) + (800) = 450 + 800 = 1250.00
        assert python_side == Decimal("1250.00")
        assert env.new_sum() == python_side

    def test_aging_and_the_balance_sum_agree_on_the_same_customer(self, env):
        """Aging and the AR balance are the two consumers most likely to be
        compared by an operator, and they used to disagree on `open`."""
        env.invoice(total="800.00", status="open")
        env.invoice(total="200.00", status="sent")
        env.s.commit()

        report = get_ar_aging(env.s, env.co)
        aged = sum(
            (c.buckets.total for c in report.customers), Decimal("0.00")
        )
        # HAND MATH: 800.00 + 200.00 = 1000.00, and aging must see the `open`
        # one — pre-C-3 it reported 200.00.
        assert env.new_sum() == Decimal("1000.00")
        assert aged == Decimal("1000.00")

    def test_the_sweeper_formula_is_now_the_shared_one(self, env):
        """The sweeper's own exclusion list was the closest of the five to
        correct, and it still dropped `written_off_amount`. It now uses the
        same expression as everything else."""
        env.invoice(total="1000.00", status="overdue", paid="0.00",
                    written_off="400.00")
        env.s.commit()

        old_sweeper = env.s.query(
            func.coalesce(func.sum(
                Invoice.total - Invoice.amount_paid - Invoice.amount_credited), 0)
        ).filter(
            Invoice.company_id == env.co,
            Invoice.status.notin_(_OLD_SWEEPER_EXCLUSION),
        ).scalar()

        # HAND MATH: truth 1000 − 0 − 0 − 400 = 600.00; old sweeper 1000.00.
        assert old_sweeper == Decimal("1000.00")
        assert env.new_sum() == Decimal("600.00")
