"""D-2 — the payables silent-zeros, pinned (audit C-3; the D-1 standard).

Every expected value in the hand-math classes is computed BY HAND in the
comments — never by the code under test — with an INDEPENDENT cross-check
(Σ buckets == Σ outstanding computed separately; Σ rollup == Σ bill totals).
Hermetic fixtures throughout.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.vendor import Vendor
from app.models.vendor_bill import VendorBill
from app.models.vendor_bill_line import VendorBillLine
from app.services import financial_report_service as frs

AS_OF = date(2026, 6, 30)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _mk_company(db) -> str:
    suffix = uuid.uuid4().hex[:6]
    co = Company(id=str(uuid.uuid4()), name=f"D2-{suffix}", slug=f"d2-{suffix}",
                 is_active=True, vertical="manufacturing")
    db.add(co)
    db.commit()
    return co.id


def _mk_vendor(db, co_id: str, name: str) -> Vendor:
    v = Vendor(id=str(uuid.uuid4()), company_id=co_id, name=name,
               account_number=f"V-{uuid.uuid4().hex[:8]}")
    db.add(v)
    db.flush()
    return v


def _dt(y, m, d):
    return datetime(y, m, d, 12, 0, tzinfo=timezone.utc)


def _bill(db, co_id, vendor, *, total, paid="0", status="approved",
          bill_date=None, due=None, deleted=False,
          lines: list[tuple[str | None, str]] | None = None) -> VendorBill:
    b = VendorBill(
        id=str(uuid.uuid4()), company_id=co_id, vendor_id=vendor.id,
        number=f"BILL-{uuid.uuid4().hex[:8]}", status=status,
        bill_date=bill_date or _dt(2026, 6, 10),
        due_date=due or _dt(2026, 7, 10),
        subtotal=Decimal(total), tax_amount=Decimal("0"),
        total=Decimal(total), amount_paid=Decimal(paid),
    )
    if deleted:
        b.deleted_at = datetime.now(timezone.utc)
    db.add(b)
    db.flush()
    for category, amount in lines or []:
        db.add(VendorBillLine(
            id=str(uuid.uuid4()), bill_id=b.id, description=category or "line",
            amount=Decimal(amount), expense_category=category,
        ))
    return b


class TestAPAgingHandMath:
    def test_buckets_match_hand_math_with_partial_and_boundary(self, db):
        """HAND MATH (as_of 2026-06-30, aging from due_date):
          V1 bill A: $1000 paid $400, due 06-20 (10 days past) → 600 in days_1_30
          V1 bill B: $500, due 07-05 (future)                 → 500 current
          V1 bill C: $250, due 06-30 (BOUNDARY, 0 days)       → 250 current
          V2 bill D: $200, due 03-27 (95 days past)           → 200 days_over_90
          Excluded: a PAID bill, a DRAFT bill, a soft-DELETED bill.
          V1 total = 600+500+250 = 1350 (current 750, 1-30 600)
          V2 total = 200 (over-90 200)
          Grand total = 1550."""
        co = _mk_company(db)
        v1 = _mk_vendor(db, co, "Auburn Aggregate")
        v2 = _mk_vendor(db, co, "Wilbert Supply")
        _bill(db, co, v1, total="1000", paid="400", status="partial", due=_dt(2026, 6, 20))
        _bill(db, co, v1, total="500", due=_dt(2026, 7, 5))
        _bill(db, co, v1, total="250", due=_dt(2026, 6, 30))
        _bill(db, co, v2, total="200", due=_dt(2026, 3, 27))
        _bill(db, co, v1, total="999", paid="999", status="paid", due=_dt(2026, 6, 1))
        _bill(db, co, v1, total="888", status="draft", due=_dt(2026, 6, 1))
        _bill(db, co, v1, total="777", due=_dt(2026, 6, 1), deleted=True)
        db.commit()

        r = frs.get_ap_aging_report(db, co, AS_OF)

        assert r["vendor_count"] == 2
        by_name = {v["vendor_name"]: v for v in r["vendors"]}
        v1r = by_name["Auburn Aggregate"]
        assert v1r["current"] == 750.0        # B 500 + boundary C 250
        assert v1r["days_1_30"] == 600.0      # A: 1000 − 400 partial
        assert v1r["days_31_60"] == 0.0
        assert v1r["total"] == 1350.0
        v2r = by_name["Wilbert Supply"]
        assert v2r["days_over_90"] == 200.0
        assert v2r["total"] == 200.0
        assert r["totals"]["total"] == 1550.0

        # INDEPENDENT CROSS-CHECK: Σ buckets == Σ outstanding computed
        # separately from the raw rows (never the code under test).
        outstanding = db.query(VendorBill).filter(
            VendorBill.company_id == co,
            VendorBill.deleted_at.is_(None),
            VendorBill.status.in_(["pending", "approved", "partial"]),
        ).all()
        independent_total = float(sum(b.total - b.amount_paid for b in outstanding))
        assert r["totals"]["total"] == independent_total
        bucket_sum = sum(
            v[k] for v in r["vendors"]
            for k in ["current", "days_1_30", "days_31_60", "days_61_90", "days_over_90"]
        )
        assert bucket_sum == independent_total

    def test_empty_tenant_is_honestly_empty(self, db):
        co = _mk_company(db)
        r = frs.get_ap_aging_report(db, co, AS_OF)
        assert r["vendor_count"] == 0 and r["vendors"] == []

    def test_loud_failure_no_silent_empty(self, db, monkeypatch):
        import app.services.ap_aging_service as aps

        co = _mk_company(db)

        def _boom(*a, **k):
            raise RuntimeError("aging read broken (simulated)")

        monkeypatch.setattr(aps, "get_ap_aging", _boom)
        with pytest.raises(RuntimeError, match="aging read broken"):
            frs.get_ap_aging_report(db, co, AS_OF)


class TestExpenseRollupHandMath:
    def test_rollup_matches_hand_math_and_ties_to_bill_totals(self, db):
        """HAND MATH (period June 2026, bill_date, end-exclusive):
          Bill E (approved, 06-10): lines Concrete 700 + Safety Supplies 300;
            total 1050 (tax 50 uncategorized at line level)
          Bill F (paid, 06-30 BOUNDARY): one uncategorized line 100; total 100
          Bill G (draft): EXCLUDED · Bill H (07-02): EXCLUDED by period
          Rollup: Concrete 700, Safety Supplies 300, General Expenses 100,
                  remainder 50 → Σ 1150 == Σ qualifying bill totals."""
        co = _mk_company(db)
        v = _mk_vendor(db, co, "Uline")
        e = _bill(db, co, v, total="1050", bill_date=_dt(2026, 6, 10),
                  lines=[("Concrete", "700"), ("Safety Supplies", "300")])
        e.tax_amount = Decimal("50")
        _bill(db, co, v, total="100", status="paid", bill_date=_dt(2026, 6, 30),
              lines=[(None, "100")])
        _bill(db, co, v, total="999", status="draft", bill_date=_dt(2026, 6, 15),
              lines=[("Concrete", "999")])
        _bill(db, co, v, total="500", bill_date=_dt(2026, 7, 2),
              lines=[("Concrete", "500")])
        db.commit()

        rows = frs._sum_by_gl_type(db, co, date(2026, 6, 1), date(2026, 6, 30), "expense")
        by_name = {r["account_name"]: r["amount"] for r in rows}
        assert by_name["Concrete"] == 700.0
        assert by_name["Safety Supplies"] == 300.0
        assert by_name["General Expenses"] == 100.0  # the uncategorized line
        assert by_name["Tax & uncategorized remainder"] == 50.0

        # A bill that WOULD have been dropped pre-fix (the swallow returned
        # [] on every call) is asserted PRESENT:
        assert rows, "pre-fix behavior (always empty) has returned"

        # INDEPENDENT CROSS-CHECK: Σ rollup == Σ qualifying bill totals.
        independent = db.query(VendorBill).filter(
            VendorBill.company_id == co,
            VendorBill.deleted_at.is_(None),
            VendorBill.status.notin_(("draft", "void")),
            VendorBill.bill_date >= _dt(2026, 6, 1),
            VendorBill.bill_date < _dt(2026, 7, 1),
        ).all()
        assert round(sum(r["amount"] for r in rows), 2) == float(sum(b.total for b in independent)) == 1150.0

    def test_cogs_returns_empty_honestly(self, db):
        """No COGS dimension exists; the old 0.6 heuristic was dead code
        (the swallow fired first) — [] preserves ALL observed behavior."""
        co = _mk_company(db)
        v = _mk_vendor(db, co, "Uline")
        _bill(db, co, v, total="1000", bill_date=_dt(2026, 6, 10), lines=[("Concrete", "1000")])
        db.commit()
        assert frs._sum_by_gl_type(db, co, date(2026, 6, 1), date(2026, 6, 30), "cogs") == []

    def test_loud_failure_no_silent_empty(self, db, monkeypatch):
        co = _mk_company(db)

        class _Broken:  # module-level model ref replaced → query construction raises
            pass

        monkeypatch.setattr(frs, "VendorBillLine", _Broken)
        with pytest.raises(Exception):
            frs._sum_by_gl_type(db, co, date(2026, 6, 1), date(2026, 6, 30), "expense")


class TestPnLIntegration:
    def test_income_statement_carries_the_expenses(self, db):
        """The headline consumer: pre-fix the P&L overstated profit by ALL
        vendor-bill expenses. Post-fix the expense section is real."""
        co = _mk_company(db)
        v = _mk_vendor(db, co, "Uline")
        _bill(db, co, v, total="800", bill_date=_dt(2026, 6, 10), lines=[("Concrete", "800")])
        db.commit()

        pnl = frs.get_income_statement(db, co, date(2026, 6, 1), date(2026, 6, 30))
        assert pnl["total_expenses"] == 800.0
        assert pnl["expenses"][0]["account_name"] == "Concrete"
        assert pnl["net_income"] == -800.0  # no revenue in the fixture
        assert pnl["total_cogs"] == 0
