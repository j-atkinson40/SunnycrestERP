"""Suite map expression pins — the accounting area at eleven.

Three real jobs carded whole; two never-faces in the coming grammar;
COMPLETION-BY-REALITY pinned for both (the checker reads code
capability — the arc landing flips the card with zero manual steps);
the cash glance's three faces; story/deep-link integrity.
"""
from __future__ import annotations

import sys
import types
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.moc_job import MoCJob
from app.services.maps_of_content import jobs as jobs_svc


@pytest.fixture(scope="module", autouse=True)
def _seeded():
    from scripts.seed_suite_jobs import main
    main()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback(); s.close()


def _job(db, name: str) -> MoCJob:
    return db.query(MoCJob).filter(
        MoCJob.name == name, MoCJob.task_type == "Accounting",
        MoCJob.is_active).one()


class TestTheEleven:
    def test_area_holds_eleven(self, db):
        n = db.query(MoCJob).filter(
            MoCJob.task_type == "Accounting", MoCJob.is_active).count()
        assert n == 11

    def test_never_faces_are_coming_today(self, db):
        for name in ("Handle the exceptions", "File sales tax"):
            job = _job(db, name)
            state = jobs_svc.coming_state(db, job)
            assert state is not None and state["is_coming"] is True

    def test_real_jobs_are_not_coming(self, db):
        for name in ("Pay the bills", "Watch the cash",
                     "Understand the numbers"):
            assert jobs_svc.coming_state(db, _job(db, name)) is None


class TestCompletionByReality:
    def test_exceptions_arc_flips_on_the_verb(self, db, monkeypatch):
        """The write-off verb appearing on sales_service IS the arc
        landing — the card flips real with zero manual steps."""
        import app.services.sales_service as ss
        job = _job(db, "Handle the exceptions")
        assert jobs_svc.coming_state(db, job)["is_coming"] is True
        monkeypatch.setattr(ss, "write_off_invoice", lambda *a, **k: None,
                            raising=False)
        assert jobs_svc.coming_state(db, job)["is_coming"] is False

    def test_tax_arc_flips_on_the_module(self, db, monkeypatch):
        job = _job(db, "File sales tax")
        assert jobs_svc.coming_state(db, job)["is_coming"] is True
        monkeypatch.setitem(sys.modules, "app.services.tax_filing_service",
                            types.ModuleType("tax_filing_service"))
        assert jobs_svc.coming_state(db, job)["is_coming"] is False


class TestCashGlanceFaces:
    def test_teach_face_without_a_feed(self, db):
        from app.models.company import Company
        co = Company(name="GX1", slug=f"gx1-{uuid.uuid4().hex[:6]}")
        db.add(co); db.commit()
        try:
            out = jobs_svc.GLANCE_SOURCES["cash_position"](db, co.id)
            assert out["kind"] == "teach"
            assert "Connect a bank" in out["text"]
        finally:
            for stmt in ("DELETE FROM vaults WHERE company_id = :c",
                         "DELETE FROM company_modules WHERE company_id = :c",
                         "DELETE FROM financial_accounts WHERE tenant_id = :c",
                         "DELETE FROM companies WHERE id = :c"):
                try:
                    db.execute(sql_text(stmt), {"c": co.id}); db.commit()
                except Exception:
                    db.rollback()

    def test_live_face_with_balances(self, db):
        from app.models.company import Company
        from app.models.plaid import BankAccount, PlaidItem
        from app.services.plaid import crypto as plaid_crypto
        co = Company(name="GX2", slug=f"gx2-{uuid.uuid4().hex[:6]}")
        db.add(co); db.flush()
        item = PlaidItem(
            tenant_id=co.id, plaid_item_id=f"it-{uuid.uuid4().hex[:8]}",
            institution_id="ins_x", institution_name="X",
            access_token_encrypted=plaid_crypto.encrypt_token("t"))
        db.add(item); db.flush()
        db.add(BankAccount(
            tenant_id=co.id, plaid_item_id=item.id,
            plaid_account_id=f"a-{uuid.uuid4().hex[:8]}", name="Chk",
            account_type="depository", current_balance=Decimal("1234.00"),
            balance_as_of=datetime.now(timezone.utc)))
        db.commit()
        try:
            out = jobs_svc.GLANCE_SOURCES["cash_position"](db, co.id)
            assert out["kind"] == "live"
            assert out["text"] == "$1,234 on hand"
            assert out["as_of"] is not None
        finally:
            for stmt in ("DELETE FROM bank_accounts WHERE tenant_id = :c",
                         "DELETE FROM plaid_items WHERE tenant_id = :c",
                         "DELETE FROM vaults WHERE company_id = :c",
                         "DELETE FROM company_modules WHERE company_id = :c",
                         "DELETE FROM financial_accounts WHERE tenant_id = :c",
                         "DELETE FROM companies WHERE id = :c"):
                try:
                    db.execute(sql_text(stmt), {"c": co.id}); db.commit()
                except Exception:
                    db.rollback()

    def test_card_payload_carries_glance_and_coming(self, db):
        job = _job(db, "Watch the cash")

        class _U:
            company_id = "nonexistent-tenant"
        out = jobs_svc.job_card_payload(db, job, user=_U())
        assert out["glance_live"] is not None  # teach face for the unknown
        assert out["coming"] is None
        nf = jobs_svc.job_card_payload(db, _job(db, "Handle the exceptions"))
        assert nf["coming"]["is_coming"] is True


class TestTheStories:
    ROUTED = {"/ap/bills", "/ap/payments", "/ap/aging",
              "/financials/bank-activity", "/financials/board",
              "/financials/finance-charges",
              "/reports", "/ar/statements", "/journal-entries",
              "/ar/invoices", "/settings/tax", "/settings/accounts"}

    def test_ponders_build_with_census_backed_beats(self, db):
        for name, must_contain in (
            ("Pay the bills", "COMING — the batch payment run"),
            ("Watch the cash", "owed, never as cash"),
            ("Understand the numbers", "subledgers and journals"),
            ("Handle the exceptions", "voiding works"),
            ("File sales tax", "gathers nothing"),
        ):
            script = jobs_svc.build_job_ponder_script(
                db, job_id=_job(db, name).id)
            joined = " ".join(b["text"] for b in script["beats"])
            assert must_contain.lower() in joined.lower(), name

    def test_deep_links_stay_on_routed_paths(self, db):
        for name in ("Pay the bills", "Watch the cash",
                     "Understand the numbers", "Handle the exceptions",
                     "File sales tax"):
            script = jobs_svc.build_job_ponder_script(
                db, job_id=_job(db, name).id)
            for b in script["beats"]:
                link = b.get("link")
                if link and link.get("href", "").startswith("/"):
                    base = link["href"].split("?")[0]
                    if not base.startswith("/bridgeable-map"):
                        assert base in self.ROUTED, (name, base)
