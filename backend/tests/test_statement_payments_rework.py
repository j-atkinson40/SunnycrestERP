"""D-1 — Statement payments rework (audit C-1): hand-computed assembly proof.

Every expected value in TestHandComputedStatementMath is computed BY HAND in
the comments below — never by the code under test. The scenario exercises:
a pre-period invoice partially paid before the period (opening balance), an
in-period payment applied to the PRE-period invoice (the double-count edge
from Phase 0 §3), a PARTIAL application with an unapplied remainder, an
intraday period-end boundary invoice, and a draft invoice that must be
excluded.

Plus the loud-failure pins: a broken payment read RAISES, emits no
statements, and records a status="failed" run; and the supersede semantics
for uq_statement_run_period.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.customer_payment import CustomerPayment, CustomerPaymentApplication
from app.models.invoice import Invoice
from app.models.statement import CustomerStatement, StatementRun
from app.services import statement_generation_service as svc


PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _dt(y, m, d, h=12):
    return datetime(y, m, d, h, 0, 0, tzinfo=timezone.utc)


def _mk_tenant(db) -> tuple[str, str]:
    """Fresh company + statement-eligible customer. Returns (company_id, customer_id)."""
    suffix = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()), name=f"D1-{suffix}", slug=f"d1-{suffix}",
        is_active=True, vertical="manufacturing",
    )
    db.add(co)
    db.commit()
    cust = Customer(
        id=str(uuid.uuid4()), company_id=co.id, name=f"D1 Customer {suffix}",
        is_active=True, receives_monthly_statement=True,
    )
    db.add(cust)
    db.commit()
    return co.id, cust.id


def _invoice(db, co_id, cust_id, *, day, total, status="sent", month=6, year=2026, hour=12) -> Invoice:
    inv = Invoice(
        id=str(uuid.uuid4()), company_id=co_id, customer_id=cust_id,
        number=f"INV-{uuid.uuid4().hex[:8]}",
        invoice_date=_dt(year, month, day, hour),
        due_date=_dt(year, month, day, hour),
        status=status, subtotal=Decimal(total), tax_amount=Decimal("0"),
        total=Decimal(total), amount_paid=Decimal("0"),
    )
    db.add(inv)
    db.flush()
    return inv


def _payment(db, co_id, cust_id, *, day, total, month=6, year=2026,
             applications: list[tuple[Invoice, str]] | None = None) -> CustomerPayment:
    p = CustomerPayment(
        id=str(uuid.uuid4()), company_id=co_id, customer_id=cust_id,
        payment_date=_dt(year, month, day), total_amount=Decimal(total),
        payment_method="check",
    )
    db.add(p)
    db.flush()
    for inv, amt in applications or []:
        db.add(CustomerPaymentApplication(
            id=str(uuid.uuid4()), payment_id=p.id, invoice_id=inv.id,
            amount_applied=Decimal(amt),
        ))
        inv.amount_paid = (inv.amount_paid or Decimal("0")) + Decimal(amt)
        if inv.amount_paid >= inv.total:
            inv.status = "paid"
        elif inv.amount_paid > Decimal("0"):
            inv.status = "partial"
    db.flush()
    return p


def _seed_scenario(db) -> tuple[str, str]:
    """The hand-computed scenario. Period = June 2026.

    Invoice A: May 10, $1,000, sent (pre-period)
    Invoice B: June 5, $500, sent (in-period)
    Invoice C: June 30 at 15:00, $250, sent (in-period, intraday boundary)
    Invoice D: June 12, $999, DRAFT (must be excluded from everything)
    Payment P1: May 20, $400 → applied $400 to A (pre-period payment)
    Payment P2: June 15, $600 → applied $600 to A (in-period payment on a
                pre-period invoice — the Phase 0 §3 double-count edge; A is
                now fully paid, status flips to "paid")
    Payment P3: June 20, $200 → applied $150 to B (PARTIAL), $50 UNAPPLIED

    HAND MATH (never from the code under test):
      opening  = A.total 1000 − pre-period applications to pre-period
                 invoices (P1's 400)                       = 600.00
      charges  = B 500 + C 250 (D excluded: draft)          = 750.00
      payments = P2 600 + P3 200 (full check amounts)       = 800.00
      closing  = 600 + 750 − 800                            = 550.00
      cross-check as-of June 30: A residual 0, B residual 350, C 250,
      minus P3's unapplied 50 credit → 600 − 50 = 550 ✓
    """
    co_id, cust_id = _mk_tenant(db)
    inv_a = _invoice(db, co_id, cust_id, day=10, month=5, total="1000")
    inv_b = _invoice(db, co_id, cust_id, day=5, total="500")
    _invoice(db, co_id, cust_id, day=30, hour=15, total="250")
    _invoice(db, co_id, cust_id, day=12, total="999", status="draft")
    _payment(db, co_id, cust_id, day=20, month=5, total="400", applications=[(inv_a, "400")])
    _payment(db, co_id, cust_id, day=15, total="600", applications=[(inv_a, "600")])
    _payment(db, co_id, cust_id, day=20, total="200", applications=[(inv_b, "150")])
    db.commit()
    return co_id, cust_id


class TestHandComputedStatementMath:
    def test_calculate_statement_data_matches_hand_math_exactly(self, db):
        co_id, cust_id = _seed_scenario(db)
        data = svc.calculate_statement_data(db, co_id, cust_id, PERIOD_START, PERIOD_END)

        assert data["opening_balance"] == 600.00
        assert data["invoices_total"] == 750.00
        assert data["payments_total"] == 800.00
        assert data["closing_balance"] == 550.00
        assert data["invoice_count"] == 2  # B + C; draft D excluded

    def test_full_run_emits_the_hand_computed_statement(self, db):
        co_id, cust_id = _seed_scenario(db)
        run = svc.generate_statement_run(db, co_id, None, PERIOD_START, PERIOD_END)

        items = db.query(CustomerStatement).filter(
            CustomerStatement.run_id == run.id,
            CustomerStatement.customer_id == cust_id,
        ).all()
        assert len(items) == 1
        item = items[0]
        assert Decimal(item.previous_balance) == Decimal("600.00")
        assert Decimal(item.new_charges) == Decimal("750.00")
        assert Decimal(item.payments_received) == Decimal("800.00")
        assert Decimal(item.balance_due) == Decimal("550.00")
        # Never again a nonzero-payment customer with a zero-payment statement.
        assert Decimal(item.payments_received) > 0

    def test_soft_deleted_payment_is_excluded(self, db):
        co_id, cust_id = _mk_tenant(db)
        _invoice(db, co_id, cust_id, day=5, total="500")
        p = _payment(db, co_id, cust_id, day=10, total="500")
        p.deleted_at = datetime.now(timezone.utc)
        db.commit()

        data = svc.calculate_statement_data(db, co_id, cust_id, PERIOD_START, PERIOD_END)
        assert data["payments_total"] == 0.00
        assert data["closing_balance"] == 500.00

    def test_post_cutoff_flag_uses_real_payment_and_boundary(self, db):
        co_id, cust_id = _mk_tenant(db)
        _invoice(db, co_id, cust_id, day=5, total="500")
        # Payment ON period_end (intraday) is IN period — not post-cutoff.
        _payment(db, co_id, cust_id, day=30, total="100")
        # Payment July 2 IS post-cutoff.
        _payment(db, co_id, cust_id, day=2, month=7, total="75")
        db.commit()

        customer = db.get(Customer, cust_id)
        data = svc.calculate_statement_data(db, co_id, cust_id, PERIOD_START, PERIOD_END)
        assert data["payments_total"] == 100.00  # June 30 payment counted in-period

        flags = svc.detect_flags(db, co_id, customer, data, PERIOD_END)
        cutoff = [f for f in flags if f["code"] == "payment_after_cutoff"]
        assert len(cutoff) == 1
        assert "$75.00" in cutoff[0]["message"]


class TestLoudFailure:
    def test_broken_payment_read_raises_and_records_failed_run(self, db, monkeypatch):
        co_id, cust_id = _seed_scenario(db)

        def _boom(*a, **k):
            raise RuntimeError("payment read broken (simulated)")

        monkeypatch.setattr(svc, "sum_customer_payments_in_period", _boom)

        with pytest.raises(RuntimeError, match="payment read broken"):
            svc.generate_statement_run(db, co_id, None, PERIOD_START, PERIOD_END)

        # No statement emitted — a wrong money number is worse than no statement.
        assert db.query(CustomerStatement).filter(
            CustomerStatement.tenant_id == co_id
        ).count() == 0
        # The failure is recorded loudly.
        runs = db.query(StatementRun).filter(StatementRun.tenant_id == co_id).all()
        assert len(runs) == 1
        assert runs[0].status == "failed"

    def test_failed_run_is_superseded_by_the_retry(self, db, monkeypatch):
        co_id, cust_id = _seed_scenario(db)

        def _boom(*a, **k):
            raise RuntimeError("boom")

        monkeypatch.setattr(svc, "sum_customer_payments_in_period", _boom)
        with pytest.raises(RuntimeError):
            svc.generate_statement_run(db, co_id, None, PERIOD_START, PERIOD_END)
        monkeypatch.undo()

        run = svc.generate_statement_run(db, co_id, None, PERIOD_START, PERIOD_END)
        assert run.status in ("draft", "in_review")
        # Only the good run remains for the period.
        runs = db.query(StatementRun).filter(StatementRun.tenant_id == co_id).all()
        assert [r.id for r in runs] == [run.id]

    def test_presend_run_superseded_but_sent_run_refused(self, db):
        co_id, cust_id = _seed_scenario(db)
        first = svc.generate_statement_run(db, co_id, None, PERIOD_START, PERIOD_END)

        # Pre-send re-generation supersedes (stale wrong-numbered drafts
        # regenerate — the demo can never surface a pre-fix statement).
        second = svc.generate_statement_run(db, co_id, None, PERIOD_START, PERIOD_END)
        assert second.id != first.id
        assert db.query(StatementRun).filter(
            StatementRun.tenant_id == co_id
        ).count() == 1

        # A run that went out is refused loudly, never clobbered.
        second.status = "sent"
        second.sent_count = 1
        db.commit()
        with pytest.raises(ValueError, match="refusing to regenerate"):
            svc.generate_statement_run(db, co_id, None, PERIOD_START, PERIOD_END)
