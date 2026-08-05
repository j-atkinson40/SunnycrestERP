"""AR-1 C-1 — the Sage import is a live AR drift producer. CHARACTERIZATION.

`import_open_invoices` (`data_migration_service.py:784`) creates invoices at
`status="sent"` or `"overdue"` — ISSUED, not draft — and never calls
`post_invoice_to_ar`, never touches `customers.current_balance`. So an imported
invoice is visible to AR aging, to the financials board, and to the nightly
sweeper's computed total, while the stored balance stays where it was.

The sweeper then "corrects" the customer upward on its next run, writes a log
line, and fails to raise its alert (the alert has never worked — AR-1 B-3). Its
own docstring names "a data import" as a hypothetical cause of drift
(`proactive_agents.py:513-518`); it is not hypothetical, it is this function.

This matters now rather than eventually because the Sage cutover runs through
this service. The first real import would silently produce drift on every
imported customer.

WHY POSTING IS THE RIGHT FIX AND NOT A DOUBLE-COUNT. Verified before changing
anything:
  * `import_customers` (`:736`) creates `Customer(...)` with NO
    `current_balance`, so every imported customer starts at the column default
    of 0 — there is no separately-imported balance for a post to duplicate.
  * The imported invoice's `total` is `abs_balance`, the OUTSTANDING balance
    from Sage (`:866-869`), with `amount_paid=Decimal("0")` (`:870`). So
    `post_invoice_to_ar`'s `+ invoice.total` adds exactly the open amount.

Cleans up its own `arc1-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.services.data_migration_service import import_open_invoices
from tests._cleanup import purge_companies_by_slug

_SLUG = "arc1-"
_CUTOVER = date(2026, 6, 30)


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
            id=str(uuid.uuid4()), name=f"ARC1 {sfx}", slug=f"{_SLUG}{sfx}",
            is_active=True, vertical="manufacturing",
        )
        s.add(self.company); s.flush()
        self.co = self.company.id

    def customer(self, *, balance="0.00") -> Customer:
        c = Customer(
            id=str(uuid.uuid4()), company_id=self.co, name="Hopkins FH",
            is_active=True, current_balance=Decimal(balance),
        )
        self.s.add(c); self.s.flush()
        return c

    def run_import(self, customer, rows: list[dict]) -> dict:
        """Drive the real importer with a Sage-shaped parsed row set."""
        return import_open_invoices(
            self.s,
            tenant_id=self.co,
            parsed_invoices=rows,
            customer_id_map={"SAGECUST": customer.id},
            cutover_date=_CUTOVER,
        )


def _row(*, number: str, balance: str, days_delinquent: int = 0) -> dict:
    """One parsed Sage AR row. `balance` is the OUTSTANDING amount, and Sage
    expresses a customer credit as a NEGATIVE balance."""
    return {
        "sage_customer_no": "SAGECUST",
        "invoice_number": number,
        "balance": Decimal(balance),
        "days_delinquent": days_delinquent,
        "invoice_date": datetime(2026, 5, 1, tzinfo=timezone.utc),
        "due_date": datetime(2026, 5, 31, tzinfo=timezone.utc),
    }


class TestImportedInvoicePostsToAR:
    """DELIBERATE PIN FLIPS — AR-1 C-1. The two characterizations replaced here
    read, verbatim:

        def test_WRONGNESS_an_imported_invoice_leaves_the_balance_untouched(self, env):
            inv = ...
            assert inv.status == "sent"                 # ISSUED, not draft
            assert inv.total == Decimal("1200.00")
            assert inv.amount_paid == Decimal("0.00")
            # ...and yet:
            assert cust.current_balance == Decimal("0.00")

        def test_WRONGNESS_the_drift_is_exactly_what_the_sweeper_would_correct(self, env):
            computed = sum(...)
            assert computed == Decimal("1500.00")
            assert cust.current_balance == Decimal("0.00")
            assert computed - cust.current_balance == Decimal("1500.00")   # the drift

    The drift is zero now because the importer posts at creation, the same way
    finance charges do.
    """

    def test_an_imported_invoice_moves_the_balance(self, env):
        """HAND MATH: opening 0.00 + imported total 1200.00 = 1200.00."""
        cust = env.customer(balance="0.00")
        env.s.commit()

        env.run_import(cust, [_row(number="INV-1", balance="1200.00")])
        env.s.commit()
        env.s.refresh(cust)

        inv = env.s.query(Invoice).filter(Invoice.company_id == env.co).one()
        assert inv.status == "sent"                 # still ISSUED, not draft
        assert inv.total == Decimal("1200.00")
        assert inv.amount_paid == Decimal("0.00")
        assert cust.current_balance == Decimal("1200.00")

    def test_the_drift_the_sweeper_would_have_corrected_is_now_zero(self, env):
        """HAND MATH: 1200.00 + 300.00 = 1500.00 receivable, 1500.00 stored,
        difference 0.00. The sweeper has nothing to correct on this path."""
        cust = env.customer(balance="0.00")
        env.s.commit()

        env.run_import(cust, [
            _row(number="INV-1", balance="1200.00"),
            _row(number="INV-2", balance="300.00", days_delinquent=45),
        ])
        env.s.commit()
        env.s.refresh(cust)

        computed = sum(
            (i.total - i.amount_paid for i in
             env.s.query(Invoice).filter(Invoice.company_id == env.co).all()),
            Decimal("0.00"),
        )
        assert computed == Decimal("1500.00")
        assert cust.current_balance == Decimal("1500.00")
        assert computed - cust.current_balance == Decimal("0.00")

    def test_posting_adds_to_an_existing_balance_rather_than_replacing_it(self, env):
        """HAND MATH: opening 250.00 + 1200.00 = 1450.00. `post_invoice_to_ar`
        increments; a customer with a prior balance keeps it."""
        cust = env.customer(balance="250.00")
        env.s.commit()

        env.run_import(cust, [_row(number="INV-1", balance="1200.00")])
        env.s.commit()
        env.s.refresh(cust)

        assert cust.current_balance == Decimal("1450.00")

    def test_a_skipped_duplicate_does_not_post_twice(self, env):
        """The importer skips a row whose `sage_invoice_id` already exists
        (`data_migration_service.py:822-832`). Re-running must not re-post —
        otherwise a retried import doubles every balance."""
        cust = env.customer(balance="0.00")
        env.s.commit()

        rows = [_row(number="INV-1", balance="1200.00")]
        env.run_import(cust, rows)
        env.s.commit()
        result = env.run_import(cust, rows)          # same row again
        env.s.commit()
        env.s.refresh(cust)

        assert result["skipped"] == 1
        assert cust.current_balance == Decimal("1200.00")   # NOT 2400.00

    def test_an_overdue_row_is_also_issued(self, env):
        """`days_delinquent > 0` → `overdue`, which is equally issued. Both of
        the importer's status outcomes are receivable."""
        cust = env.customer()
        env.s.commit()

        env.run_import(cust, [_row(number="INV-9", balance="500.00",
                                   days_delinquent=90)])
        env.s.commit()

        inv = env.s.query(Invoice).filter(Invoice.company_id == env.co).one()
        assert inv.status == "overdue"


class TestNegativeSageBalanceSignInversion:
    """FOUND WHILE PINNING C-1, NOT FIXED — and it GATES the C-1 fix.

    Sage expresses a customer credit as a NEGATIVE balance. The importer takes
    `abs_balance` (`data_migration_service.py:843`) and writes it as the
    invoice `total` with `status="sent"` (`:847-848`), commenting
    "credit / overpayment — treat as sent with credit balance".

    The result is that a customer CREDIT of $500 is imported as a $500
    RECEIVABLE — the sign is inverted, and the invoice asserts the customer
    owes money the tenant actually owes them.

    Today that is contained: the importer never posts to AR, so the wrong sign
    reaches aging and the dashboards but not the stored balance. **Routing this
    function through `post_invoice_to_ar` would push the inverted amount into
    `current_balance` too**, turning a $500 credit into a $500 debit — a
    $1,000 swing per credit row.

    So this is pinned BEFORE the C-1 fix rather than after, and the fix must
    decide what to do with it. It is not mine to decide.
    """

    def test_WRONGNESS_a_sage_credit_becomes_a_positive_receivable(self, env):
        cust = env.customer(balance="0.00")
        env.s.commit()

        env.run_import(cust, [_row(number="CREDIT-1", balance="-500.00")])
        env.s.commit()

        inv = env.s.query(Invoice).filter(Invoice.company_id == env.co).one()
        # The tenant OWES this customer 500. The invoice says the reverse.
        assert inv.total == Decimal("500.00")      # positive, not -500
        assert inv.status == "sent"                # receivable, not a credit
        # Contained ONLY because nothing posts it to the balance yet:
        env.s.refresh(cust)
        assert cust.current_balance == Decimal("0.00")
