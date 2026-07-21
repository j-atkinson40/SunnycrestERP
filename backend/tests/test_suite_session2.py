"""Suite Session 2 pins — the cheap season closes.

Finance-charge surface: forgive-with-reason persists; the charge queue is
tenant-isolated (item verbs, run reads, and POST all refuse cross-tenant).
Accounts CRUD: type honesty (four types, deactivate leaves the list).
Snapshot wire: running a report feeds the trend engine.
Map beat: the exceptions job carries the late-charges beat and STAYS
honestly coming (the surface is not the arc).
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.finance_charge import FinanceChargeItem, FinanceChargeRun
from app.services import finance_charge_service as fc


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _cleanup(db, company_ids: list[str]) -> None:
    for cid in company_ids:
        for stmt in (
            "DELETE FROM report_snapshots WHERE tenant_id = :c",
            "DELETE FROM report_runs WHERE tenant_id = :c",
            "DELETE FROM users WHERE company_id = :c",
            "DELETE FROM finance_charge_items WHERE tenant_id = :c",
            "DELETE FROM finance_charge_runs WHERE tenant_id = :c",
            "DELETE FROM financial_accounts WHERE tenant_id = :c",
            "DELETE FROM invoices WHERE company_id = :c",
            "DELETE FROM customers WHERE company_id = :c",
            "DELETE FROM vaults WHERE company_id = :c",
            "DELETE FROM company_modules WHERE company_id = :c",
            "DELETE FROM companies WHERE id = :c",
        ):
            try:
                db.execute(sql_text(stmt), {"c": cid})
                db.commit()
            except Exception:
                db.rollback()


def _company(db, tag: str) -> Company:
    co = Company(name=f"S2 {tag}", slug=f"s2-{tag}-{uuid.uuid4().hex[:6]}")
    db.add(co)
    db.commit()
    return co


def _run_with_item(db, tenant_id: str) -> tuple[FinanceChargeRun, FinanceChargeItem]:
    cust = Customer(company_id=tenant_id, name="Hopkins FH")
    db.add(cust)
    db.flush()
    run = FinanceChargeRun(
        tenant_id=tenant_id, run_number=f"FC-T-{uuid.uuid4().hex[:6]}",
        charge_month=6, charge_year=2026, calculation_date=date(2026, 6, 27),
        rate_applied=Decimal("1.5"), balance_basis="past_due_only",
        compound=False, grace_days=0,
        minimum_amount=Decimal("2.00"), minimum_balance=Decimal("10.00"),
    )
    db.add(run)
    db.flush()
    item = FinanceChargeItem(
        tenant_id=tenant_id, run_id=run.id, customer_id=cust.id,
        eligible_balance=Decimal("1000.00"), rate_applied=Decimal("1.5"),
        calculated_amount=Decimal("15.00"), final_amount=Decimal("15.00"),
        prior_finance_charge_balance=Decimal("0"),
        review_status="pending",
    )
    db.add(item)
    db.commit()
    return run, item


class TestTheEngineActuallyRuns:
    """Two born-dormant bugs died in Session 2: (1) the q6p7 migration's
    customer columns were never declared on the ORM model, so the engine's
    eligibility query raised AttributeError; (2) Invoice.due_date is a
    datetime and the aging math subtracted it from a date. The engine had
    never completed a run. This pin is the whole path, hand-proven:
    $1,000 past due × 1.5% = $15.00."""

    def test_full_calculation_hand_proven(self, db):
        from datetime import datetime, timedelta, timezone
        from app.models.invoice import Invoice
        co = _company(db, "er")
        try:
            cust = Customer(company_id=co.id, name="Hopkins FH",
                            billing_profile="monthly_statement")
            db.add(cust)
            db.flush()
            inv = Invoice(
                company_id=co.id, customer_id=cust.id,
                number=f"INV-ER-{uuid.uuid4().hex[:6]}",
                invoice_date=datetime.now(timezone.utc) - timedelta(days=75),
                due_date=datetime.now(timezone.utc) - timedelta(days=45),
                status="overdue", total=Decimal("1000.00"),
                amount_paid=Decimal("0"),
            )
            db.add(inv)
            db.commit()
            fc.update_settings(db, co.id, {"enabled": True})
            out = fc.run_calculation(db, co.id, date.today(), "manual")
            assert out is not None and out["already_exists"] is False
            assert out["customers_charged"] == 1
            assert out["total"] == 15.0  # $1,000 × 1.5%
            items = fc.get_run_items(db, out["run_id"])
            assert items[0]["final_amount"] == 15.0
            assert items[0]["review_status"] == "pending"
        finally:
            _cleanup(db, [co.id])


class TestForgiveWithReason:
    def test_forgiveness_note_persists(self, db):
        co = _company(db, "fw")
        try:
            _, item = _run_with_item(db, co.id)
            ok = fc.forgive_item(db, item.id, "user-1",
                                 "goodwill — first offense", tenant_id=co.id)
            assert ok is True
            db.expire_all()
            fresh = db.query(FinanceChargeItem).filter(
                FinanceChargeItem.id == item.id).one()
            assert fresh.review_status == "forgiven"
            assert fresh.forgiveness_note == "goodwill — first offense"
            assert fresh.reviewed_by == "user-1"
            # forgiven is terminal for review: approve refuses
            assert fc.approve_item(db, item.id, "user-1", tenant_id=co.id) is False
        finally:
            _cleanup(db, [co.id])


class TestChargeQueueIsolation:
    def test_item_verbs_refuse_cross_tenant(self, db):
        co_a, co_b = _company(db, "ia"), _company(db, "ib")
        try:
            _, item = _run_with_item(db, co_a.id)
            assert fc.forgive_item(db, item.id, "u", "x", tenant_id=co_b.id) is False
            assert fc.approve_item(db, item.id, "u", tenant_id=co_b.id) is False
            db.expire_all()
            fresh = db.query(FinanceChargeItem).filter(
                FinanceChargeItem.id == item.id).one()
            assert fresh.review_status == "pending"  # untouched
        finally:
            _cleanup(db, [co_a.id, co_b.id])

    def test_post_refuses_foreign_run(self, db):
        co_a, co_b = _company(db, "pa"), _company(db, "pb")
        try:
            run, item = _run_with_item(db, co_a.id)
            fc.approve_item(db, item.id, "u", tenant_id=co_a.id)
            out = fc.post_approved_charges(db, run.id, co_b.id, "u")
            assert out.get("error") == "Run not found"
            db.expire_all()
            fresh = db.query(FinanceChargeItem).filter(
                FinanceChargeItem.id == item.id).one()
            assert fresh.posted is False and fresh.invoice_id is None
        finally:
            _cleanup(db, [co_a.id, co_b.id])

    def test_run_routes_scope_by_tenant(self, db):
        from app.api.routes.finance_charges import _owned_run
        from fastapi import HTTPException
        co_a, co_b = _company(db, "ra"), _company(db, "rb")
        try:
            run, _ = _run_with_item(db, co_a.id)
            assert _owned_run(db, run.id, co_a.id).id == run.id
            with pytest.raises(HTTPException) as e:
                _owned_run(db, run.id, co_b.id)
            assert e.value.status_code == 404
        finally:
            _cleanup(db, [co_a.id, co_b.id])


class TestSettingsWrite:
    def test_settings_round_trip(self, db):
        co = _company(db, "st")
        try:
            changed = fc.update_settings(db, co.id, {
                "enabled": True, "rate_monthly": 2.0, "grace_days": 5,
                "not_a_key": "ignored",
            })
            assert changed == 3  # unknown key silently dropped
            s = fc.get_settings(db, co.id)
            assert s["enabled"] is True
            assert s["rate_monthly"] == 2.0
            assert s["grace_days"] == 5
        finally:
            _cleanup(db, [co.id])


class TestSnapshotWire:
    def test_report_run_feeds_the_trend_engine(self, db):
        from app.api.routes.reports import income_statement
        from app.services.report_intelligence_service import get_trend_data
        from app.models.role import Role
        from app.models.user import User
        co = _company(db, "sn")
        try:
            role = db.query(Role).first()
            assert role is not None, "dev DB has no roles seeded"
            user = User(company_id=co.id,
                        email=f"s2-{uuid.uuid4().hex[:6]}@test.internal",
                        hashed_password="x", first_name="S2", last_name="Test",
                        role_id=role.id)
            db.add(user)
            db.commit()

            class _U:
                company_id = co.id
                id = user.id
            data = income_statement(
                period_start="2026-06-01", period_end="2026-06-30",
                comparison_start=None, comparison_end=None,
                current_user=_U(), db=db,
            )
            assert "total_revenue" in data
            trends = get_trend_data(db, co.id, "income_statement")
            assert len(trends) == 1
            assert "net_income" in trends[0]["key_metrics"]
        finally:
            _cleanup(db, [co.id])


class TestAccountsCrud:
    def test_type_honesty_and_deactivate(self, db):
        from app.api.routes.reconciliation import (
            AccountCreate, AccountUpdate, create_account, list_accounts,
            update_account,
        )
        co = _company(db, "ac")
        try:
            class _U:
                company_id = co.id
                id = "user-1"
            u = _U()
            ids = {}
            for atype in ("checking", "savings", "credit_card", "loan"):
                out = create_account(
                    AccountCreate(account_type=atype, account_name=f"{atype} acct"),
                    current_user=u, db=db)
                ids[atype] = out["id"]
            rows = list_accounts(current_user=u, db=db)
            assert {r["account_type"] for r in rows} == {
                "checking", "savings", "credit_card", "loan"}
            # deactivate the loan — it leaves the active list
            update_account(
                ids["loan"],
                AccountUpdate(account_type="loan", account_name="loan acct",
                              is_active=False),
                current_user=u, db=db)
            rows = list_accounts(current_user=u, db=db)
            assert "loan" not in {r["account_type"] for r in rows}
            assert len(rows) == 3
        finally:
            _cleanup(db, [co.id])


class TestTheMapBeat:
    def test_exceptions_job_carries_the_beat_and_stays_coming(self, db):
        from app.models.moc_job import MoCJob
        from app.services.maps_of_content import jobs as jobs_svc
        from scripts.seed_suite_jobs import main
        main()  # idempotent; appends the beat where absent
        job = db.query(MoCJob).filter(
            MoCJob.name == "Handle the exceptions",
            MoCJob.task_type == "Accounting", MoCJob.is_active).one()
        story = (job.ponder or {}).get("story") or []
        beat = next((b for b in story if b.get("key") == "today-late-charges"), None)
        assert beat is not None
        assert beat["link"]["href"] == "/financials/finance-charges"
        assert "forgiven with a reason" in beat["text"]
        # the beat sits with the today-void beat, before the COMING beats
        keys = [b.get("key") for b in story]
        assert keys.index("today-late-charges") == keys.index("today-void") + 1
        # the surface is NOT the arc — the card stays honestly coming
        state = jobs_svc.coming_state(db, job)
        assert state is not None and state["is_coming"] is True

    def test_beat_append_is_idempotent(self, db):
        from app.models.moc_job import MoCJob
        from scripts.seed_suite_jobs import main
        main()
        main()
        job = db.query(MoCJob).filter(
            MoCJob.name == "Handle the exceptions",
            MoCJob.task_type == "Accounting", MoCJob.is_active).one()
        story = (job.ponder or {}).get("story") or []
        assert sum(1 for b in story if b.get("key") == "today-late-charges") == 1
