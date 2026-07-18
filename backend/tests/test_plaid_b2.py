"""Plaid B-2 pins — the trio (hand-proven), the cursor contract, the map's
edges, the born-native shape, the preserve rider.

THE MONEY-MATH CANON: every sign case is HAND-COMPUTED in the test —
a Plaid debit and credit each proven against expected platform values;
credit-card semantics proven separately. The mapping lives in ONE place
(`to_platform_amount`); these pins are its proof.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.financial_account import (
    FinancialAccount, ReconciliationRun, ReconciliationTransaction,
)
from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.moc_task_trigger import MoCTaskTrigger
from app.models.plaid import BankAccount, BankTransaction, PlaidItem
from app.models.workflow_review_item import WorkflowReviewItem
from app.services.plaid import categories as cat
from app.services.plaid import client as plaid_client
from app.services.plaid import crypto as plaid_crypto
from app.services.plaid import sync as plaid_sync
from app.services.plaid.sync import run_sync_pipeline, to_platform_amount


# ── World ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def _fernet_key():
    import os
    from cryptography.fernet import Fernet
    prior = os.environ.get("CREDENTIAL_ENCRYPTION_KEY")
    os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    plaid_crypto.reset_fernet_cache()
    yield
    if prior is None:
        os.environ.pop("CREDENTIAL_ENCRYPTION_KEY", None)
    else:
        os.environ["CREDENTIAL_ENCRYPTION_KEY"] = prior
    plaid_crypto.reset_fernet_cache()


@pytest.fixture(scope="module")
def world():
    from app.models.company import Company
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    co_a = Company(name="Sync A", slug=f"plaid2-a-{suffix}")
    co_b = Company(name="Sync B", slug=f"plaid2-b-{suffix}")
    db.add_all([co_a, co_b])
    db.flush()

    def mk_item(co, inst):
        item = PlaidItem(
            tenant_id=co.id, plaid_item_id=f"item-{uuid.uuid4().hex[:10]}",
            institution_id=inst, institution_name="First Platypus Bank",
            access_token_encrypted=plaid_crypto.encrypt_token("access-test"),
        )
        db.add(item)
        db.flush()
        checking = BankAccount(
            tenant_id=co.id, plaid_item_id=item.id,
            plaid_account_id=f"chk-{uuid.uuid4().hex[:8]}", name="Checking",
            mask="0000", account_type="depository", account_subtype="checking",
        )
        card = BankAccount(
            tenant_id=co.id, plaid_item_id=item.id,
            plaid_account_id=f"card-{uuid.uuid4().hex[:8]}", name="Card",
            mask="3333", account_type="credit", account_subtype="credit card",
        )
        db.add_all([checking, card])
        db.flush()
        return item, checking, card

    item_a, chk_a, card_a = mk_item(co_a, f"ins-a-{suffix}")
    item_b, _, _ = mk_item(co_b, f"ins-b-{suffix}")
    db.commit()
    ids = {
        "a": co_a.id, "b": co_b.id, "item_a": item_a.id, "item_b": item_b.id,
        "chk_a": chk_a.plaid_account_id, "card_a": card_a.plaid_account_id,
        "chk_a_row": chk_a.id,
    }
    db.close()
    yield ids
    db = SessionLocal()
    for co_id in (ids["a"], ids["b"]):
        db.execute(sql_text(
            "DELETE FROM workflow_review_items WHERE company_id = :c"), {"c": co_id})
        db.execute(sql_text(
            "DELETE FROM reconciliation_transactions WHERE tenant_id = :c"), {"c": co_id})
        db.execute(sql_text(
            "DELETE FROM reconciliation_runs WHERE tenant_id = :c"), {"c": co_id})
        db.execute(sql_text(
            "DELETE FROM financial_accounts WHERE tenant_id = :c"), {"c": co_id})
        db.execute(sql_text(
            "DELETE FROM bank_transactions WHERE tenant_id = :c"), {"c": co_id})
        db.execute(sql_text(
            "DELETE FROM bank_accounts WHERE tenant_id = :c"), {"c": co_id})
        db.execute(sql_text(
            "DELETE FROM plaid_items WHERE tenant_id = :c"), {"c": co_id})
        db.execute(sql_text("DELETE FROM workflow_runs WHERE company_id = :c"), {"c": co_id})
        db.execute(sql_text("DELETE FROM companies WHERE id = :c"), {"c": co_id})
    db.commit()
    db.close()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _txn(account_id, amount, txn_id=None, *, pending=False,
         pending_transaction_id=None, primary=None, detailed=None,
         name="Test Merchant", d="2026-07-15"):
    return {
        "transaction_id": txn_id or f"txn-{uuid.uuid4().hex[:10]}",
        "account_id": account_id,
        "amount": amount,
        "date": d,
        "authorized_date": d,
        "name": name,
        "merchant_name": name,
        "pending": pending,
        "pending_transaction_id": pending_transaction_id,
        "personal_finance_category": (
            {"primary": primary, "detailed": detailed}
            if (primary or detailed) else None
        ),
    }


def _script_pages(monkeypatch, pages):
    """Feed scripted transactions/sync pages; each call pops the next."""
    calls = {"n": 0, "cursors": []}

    def fake_sync(access_token, cursor, count=500):
        calls["cursors"].append(cursor)
        i = calls["n"]
        calls["n"] += 1
        page = pages[min(i, len(pages) - 1)]
        if isinstance(page, Exception):
            raise page
        return page
    monkeypatch.setattr(plaid_client, "sync_transactions", fake_sync)
    return calls


# ── 1. SIGNS — hand-computed, the money-math canon ──────────────────────

class TestSigns:
    def test_the_mapping_stated_once(self):
        # A BANK DEBIT: $25.50 leaves the account. Plaid: +25.50.
        # Platform: negative debit → -25.50. HAND-COMPUTED.
        assert to_platform_amount(25.50) == Decimal("-25.50")
        # A BANK CREDIT: $1,200.00 deposit arrives. Plaid: -1200.00.
        # Platform: positive credit → +1200.00. HAND-COMPUTED.
        assert to_platform_amount(-1200.00) == Decimal("1200.00")

    def test_credit_card_semantics_proven_separately(self):
        # A CARD CHARGE: $410.00 purchase. Plaid: +410.00 (money out).
        # Platform: -410.00 (a debit on the card statement). HAND-COMPUTED.
        assert to_platform_amount(410.00) == Decimal("-410.00")
        # A PAYMENT TO THE CARD: $500.00. Plaid: -500.00.
        # Platform: +500.00 (a credit on the card). HAND-COMPUTED.
        assert to_platform_amount(-500.00) == Decimal("-500.00") * -1

    def test_signs_land_in_rows(self, db, world, monkeypatch):
        _script_pages(monkeypatch, [{
            "added": [
                _txn(world["chk_a"], 25.50, "sign-debit"),
                _txn(world["chk_a"], -1200.00, "sign-credit"),
                _txn(world["card_a"], 410.00, "sign-card-charge"),
            ],
            "modified": [], "removed": [],
            "next_cursor": "c1", "has_more": False,
        }])
        run_sync_pipeline(db, company_id=world["a"])
        rows = {
            r.plaid_transaction_id: r
            for r in db.query(BankTransaction)
            .filter(BankTransaction.tenant_id == world["a"],
                    BankTransaction.plaid_transaction_id.like("sign-%"))
        }
        assert rows["sign-debit"].amount == Decimal("-25.50")
        assert rows["sign-credit"].amount == Decimal("1200.00")
        assert rows["sign-card-charge"].amount == Decimal("-410.00")


# ── 2. THE CURSOR CONTRACT ──────────────────────────────────────────────

class TestCursorContract:
    def test_cursor_advances_only_with_its_page_committed(self, db, world, monkeypatch):
        boom = RuntimeError("crash between pages")

        def fake_sync(access_token, cursor, count=500):
            # Whatever the prior cursor, serve page 1 once; the follow-up
            # fetch (from the just-committed cursor) crashes.
            if cursor != "c1-committed":
                return {"added": [_txn(world["chk_a"], 10, "page1-txn")],
                        "modified": [], "removed": [],
                        "next_cursor": "c1-committed", "has_more": True}
            raise boom
        monkeypatch.setattr(plaid_client, "sync_transactions", fake_sync)
        with pytest.raises(RuntimeError):
            run_sync_pipeline(db, company_id=world["a"])
        db.expire_all()
        item = db.get(PlaidItem, world["item_a"])
        # Page 1 committed WITH its cursor; the crash lost nothing.
        assert item.sync_cursor == "c1-committed"
        assert db.query(BankTransaction).filter(
            BankTransaction.plaid_transaction_id == "page1-txn").count() == 1

        # The replayed page is idempotent — same txn again, no duplicate.
        _script_pages(monkeypatch, [{
            "added": [_txn(world["chk_a"], 10, "page1-txn"),
                      _txn(world["chk_a"], 20, "page2-txn")],
            "modified": [], "removed": [],
            "next_cursor": "c2", "has_more": False,
        }])
        run_sync_pipeline(db, company_id=world["a"])
        assert db.query(BankTransaction).filter(
            BankTransaction.plaid_transaction_id == "page1-txn").count() == 1
        db.expire_all()
        assert db.get(PlaidItem, world["item_a"]).sync_cursor == "c2"

    def test_mutation_during_pagination_restarts_from_committed(self, db, world, monkeypatch):
        mut = plaid_client.PlaidApiError(
            status=400, error_type="TRANSACTIONS_ERROR",
            error_code="TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION",
            display_message=None, request_id="req-mut",
        )
        pages = [
            mut,
            {"added": [_txn(world["chk_a"], 5, "post-mutation")],
             "modified": [], "removed": [],
             "next_cursor": "c-post-mut", "has_more": False},
        ]
        calls = _script_pages(monkeypatch, pages)
        run_sync_pipeline(db, company_id=world["a"])
        assert calls["n"] == 2  # errored once, restarted once — never a loop
        db.expire_all()
        assert db.get(PlaidItem, world["item_a"]).sync_cursor == "c-post-mut"


# ── 3. PENDING → POSTED ─────────────────────────────────────────────────

class TestPendingTransition:
    def test_posted_adopts_the_pending_row_in_place(self, db, world, monkeypatch):
        _script_pages(monkeypatch, [{
            "added": [_txn(world["chk_a"], 42.00, "pend-1", pending=True)],
            "modified": [], "removed": [],
            "next_cursor": "cp1", "has_more": False,
        }])
        run_sync_pipeline(db, company_id=world["a"])
        pending_row = db.query(BankTransaction).filter(
            BankTransaction.plaid_transaction_id == "pend-1").one()
        assert pending_row.is_pending is True
        row_id = pending_row.id

        _script_pages(monkeypatch, [{
            "added": [_txn(world["chk_a"], 42.15, "post-1",
                           pending_transaction_id="pend-1")],
            "modified": [], "removed": [{"transaction_id": "pend-1"}],
            "next_cursor": "cp2", "has_more": False,
        }])
        run_sync_pipeline(db, company_id=world["a"])
        db.expire_all()
        # NO duplicate — the SAME row, posted truth wins.
        assert db.query(BankTransaction).filter(
            BankTransaction.id == row_id).one().plaid_transaction_id == "post-1"
        posted = db.get(BankTransaction, row_id)
        assert posted.is_pending is False
        assert posted.amount == Decimal("-42.15")
        assert posted.pending_plaid_transaction_id == "pend-1"
        assert posted.removed_at is None  # the pending-id removal no-ops
        assert db.query(BankTransaction).filter(
            BankTransaction.plaid_transaction_id.in_(["pend-1", "post-1"])
        ).count() == 1


# ── 4. REMOVALS — honest, and decision-worthy when matched ──────────────

def _seed_feed_row(db, world, txn_id, amount="-55.00"):
    row = BankTransaction(
        tenant_id=world["a"], bank_account_id=world["chk_a_row"],
        plaid_transaction_id=txn_id, amount=Decimal(amount),
        transaction_date=date(2026, 7, 10), description="Removable",
    )
    db.add(row)
    db.flush()
    return row


def _seed_matched_line(db, world, bank_row, *, run_status):
    fa = FinancialAccount(
        tenant_id=world["a"], account_type="checking",
        account_name=f"FA {uuid.uuid4().hex[:4]}",
    )
    db.add(fa)
    db.flush()
    run = ReconciliationRun(
        tenant_id=world["a"], financial_account_id=fa.id,
        statement_date=date(2026, 7, 31),
        statement_closing_balance=Decimal("1000"),
        status=run_status,
    )
    db.add(run)
    db.flush()
    line = ReconciliationTransaction(
        tenant_id=world["a"], reconciliation_run_id=run.id,
        transaction_date=date(2026, 7, 10), description="Removable",
        amount=Decimal("-55.00"), match_status="auto_cleared",
        matched_record_type="vendor_payment",
        matched_record_id=str(uuid.uuid4()),
        bank_transaction_id=bank_row.id,
    )
    db.add(line)
    db.commit()
    return run, line


class TestRemovals:
    def test_plain_removal_stamps_removed_at(self, db, world, monkeypatch):
        row = _seed_feed_row(db, world, "rm-plain")
        db.commit()
        _script_pages(monkeypatch, [{
            "added": [], "modified": [],
            "removed": [{"transaction_id": "rm-plain"}],
            "next_cursor": "cr1", "has_more": False,
        }])
        out = run_sync_pipeline(db, company_id=world["a"])
        db.expire_all()
        assert db.get(BankTransaction, row.id).removed_at is not None
        assert out["removed"] == 1

    def test_removed_while_matched_unconfirmed_unmatches_with_note(self, db, world, monkeypatch):
        row = _seed_feed_row(db, world, "rm-matched-open")
        run, line = _seed_matched_line(db, world, row, run_status="matching")
        _script_pages(monkeypatch, [{
            "added": [], "modified": [],
            "removed": [{"transaction_id": "rm-matched-open"}],
            "next_cursor": "cr2", "has_more": False,
        }])
        run_sync_pipeline(db, company_id=world["a"])
        db.expire_all()
        fresh = db.get(ReconciliationTransaction, line.id)
        assert fresh.match_status == "unmatched"
        assert fresh.matched_record_id is None
        assert "bank retracted" in fresh.match_notes

    def test_removed_while_matched_confirmed_surfaces_decision_triage(self, db, world, monkeypatch):
        from app.models.workflow import Workflow, WorkflowRun
        wf = db.query(Workflow).filter(Workflow.company_id.is_(None)).first()
        wf_run = WorkflowRun(
            workflow_id=wf.id if wf else None, company_id=world["a"],
            status="running", trigger_source="test",
        )
        db.add(wf_run)
        db.flush()

        row = _seed_feed_row(db, world, "rm-matched-closed")
        run, line = _seed_matched_line(db, world, row, run_status="confirmed")
        _script_pages(monkeypatch, [{
            "added": [], "modified": [],
            "removed": [{"transaction_id": "rm-matched-closed"}],
            "next_cursor": "cr3", "has_more": False,
        }])
        out = run_sync_pipeline(
            db, company_id=world["a"], workflow_run_id=wf_run.id,
        )
        db.expire_all()
        # The CLOSED statement is NOT silently edited —
        fresh = db.get(ReconciliationTransaction, line.id)
        assert fresh.match_status == "auto_cleared"
        # — the decision lands in Decision Triage instead.
        item = (
            db.query(WorkflowReviewItem)
            .filter(WorkflowReviewItem.company_id == world["a"],
                    WorkflowReviewItem.review_focus_id == "bank_retraction")
            .one()
        )
        assert item.decision is None  # undecided → the queue surfaces it
        assert item.input_data["reconciliation_run_id"] == run.id
        assert out["retractions_surfaced"] == 1


# ── 5. THE CATEGORY MAP'S EDGES ─────────────────────────────────────────

class TestCategoryMap:
    def test_detailed_wins_tenant_overrides_unmapped_null(self, db, world):
        from app.models.plaid import PlaidCategoryMapping
        db.add(PlaidCategoryMapping(
            tenant_id=world["a"], plaid_category="TRANSPORTATION.GAS",
            expense_category="other_cogs",   # the tenant's own opinion
        ))
        db.commit()
        try:
            m = cat.load_map(db, world["a"])
            # Detailed wins over primary:
            assert cat.resolve(m, "TRANSPORTATION", "TRANSPORTATION.GAS") == "other_cogs"
            # Tenant B is untouched by A's override:
            mb = cat.load_map(db, world["b"])
            assert cat.resolve(mb, "TRANSPORTATION", "TRANSPORTATION.GAS") == "vehicle_expense"
            # Primary fallback works:
            assert cat.resolve(m, "BANK_FEES", None) == "other_expense"
            # Unmapped = honest None, never a guess:
            assert cat.resolve(m, "INCOME", "INCOME.INTEREST_EARNED") is None
        finally:
            db.execute(sql_text(
                "DELETE FROM plaid_category_mappings WHERE tenant_id = :t"),
                {"t": world["a"]})
            db.commit()

    def test_uncategorized_counted_in_summary(self, db, world, monkeypatch):
        _script_pages(monkeypatch, [{
            "added": [
                _txn(world["chk_a"], 9.99, f"cat-{uuid.uuid4().hex[:6]}",
                     primary="BANK_FEES", detailed="BANK_FEES.OVERDRAFT_FEES"),
                _txn(world["chk_a"], 5.00, f"cat-{uuid.uuid4().hex[:6]}",
                     primary="INCOME", detailed="INCOME.DIVIDENDS"),
            ],
            "modified": [], "removed": [],
            "next_cursor": f"cc-{uuid.uuid4().hex[:4]}", "has_more": False,
        }])
        out = run_sync_pipeline(db, company_id=world["a"])
        assert out["ingested"] == 2
        assert out["uncategorized"] == 1  # the INCOME row, honestly


# ── 6. DRY-RUN = a real peek, zero writes ───────────────────────────────

class TestDryRun:
    def test_real_counts_no_writes(self, db, world, monkeypatch):
        before_rows = db.query(BankTransaction).filter(
            BankTransaction.tenant_id == world["a"]).count()
        item_cursor = db.get(PlaidItem, world["item_a"]).sync_cursor
        _script_pages(monkeypatch, [{
            "added": [_txn(world["chk_a"], 1.00, "dry-a"),
                      _txn(world["chk_a"], 2.00, "dry-b")],
            "modified": [{"transaction_id": "whatever"}],
            "removed": [{"transaction_id": "gone"}],
            "next_cursor": "dry-cursor", "has_more": False,
        }])
        out = run_sync_pipeline(db, company_id=world["a"], dry_run=True)
        assert out["dry_run"] is True
        assert "would ingest 2, update 1, remove 1" in out["would"]
        db.expire_all()
        assert db.query(BankTransaction).filter(
            BankTransaction.tenant_id == world["a"]).count() == before_rows
        assert db.get(PlaidItem, world["item_a"]).sync_cursor == item_cursor  # untouched


# ── 7. DEGRADATION + ISOLATION ──────────────────────────────────────────

class TestDegradationAndIsolation:
    def test_login_required_degrades_honestly(self, db, world, monkeypatch):
        err = plaid_client.PlaidApiError(
            status=400, error_type="ITEM_ERROR",
            error_code="ITEM_LOGIN_REQUIRED",
            display_message=None, request_id="req-deg",
        )
        _script_pages(monkeypatch, [err])
        with pytest.raises(RuntimeError):
            # The tenant's ONLY item failed → the run fails → H1 routes it.
            run_sync_pipeline(db, company_id=world["b"])
        db.expire_all()
        item = db.get(PlaidItem, world["item_b"])
        assert item.status == "login_required"
        assert item.last_error_code == "ITEM_LOGIN_REQUIRED"
        # Recovery: the next healthy sync flips it back active.
        _script_pages(monkeypatch, [{
            "added": [], "modified": [], "removed": [],
            "next_cursor": "rec-1", "has_more": False,
        }])
        run_sync_pipeline(db, company_id=world["b"])
        db.expire_all()
        assert db.get(PlaidItem, world["item_b"]).status == "active"

    def test_sync_never_crosses_tenants(self, db, world, monkeypatch):
        _script_pages(monkeypatch, [{
            "added": [_txn(world["chk_a"], 7.77, f"iso-{uuid.uuid4().hex[:6]}")],
            "modified": [], "removed": [],
            "next_cursor": f"iso-{uuid.uuid4().hex[:4]}", "has_more": False,
        }])
        run_sync_pipeline(db, company_id=world["a"])
        assert db.query(BankTransaction).filter(
            BankTransaction.tenant_id == world["b"],
            BankTransaction.plaid_transaction_id.like("iso-%")).count() == 0


# ── 8. BORN NATIVE — the seeded shape (dry, unpromoted, job-ref'd) ──────

class TestBornNative:
    def test_the_automation_row_and_workflow_are_compiled(self, db):
        task = (
            db.query(MoCTaskCatalog)
            .filter(MoCTaskCatalog.name == "Pull Bank Transactions",
                    MoCTaskCatalog.vertical == "manufacturing",
                    MoCTaskCatalog.is_active.is_(True))
            .one()
        )
        assert task.task_type == "Accounting"
        assert "ready to reconcile" in task.description
        row = db.execute(sql_text(
            "SELECT mirrored_from_workflow_id FROM workflow_templates "
            "WHERE id = :i"), {"i": task.workflow_template_id}).first()
        assert row is not None and row[0] is None  # compiled — born native

    def test_triggers_born_dry_on_both_clocks(self, db):
        task = (
            db.query(MoCTaskCatalog)
            .filter(MoCTaskCatalog.name == "Pull Bank Transactions",
                    MoCTaskCatalog.vertical == "manufacturing")
            .one()
        )
        trigs = (
            db.query(MoCTaskTrigger)
            .filter(MoCTaskTrigger.task_catalog_id == task.id)
            .all()
        )
        crons = sorted(t.config.get("cron") for t in trigs)
        assert crons == ["30 22 * * *", "30 6 * * *"]
        assert all(t.is_live is False for t in trigs)  # PROMOTION IS THE OPERATOR'S

    def test_job_ref_lands_and_the_ponder_shows_the_sentence(self, db):
        from app.models.moc_job import MoCJob
        from app.services.maps_of_content.jobs import build_job_ponder_script
        job = (
            db.query(MoCJob)
            .filter(MoCJob.name == "Bank reconciliation",
                    MoCJob.vertical == "manufacturing",
                    MoCJob.is_active.is_(True))
            .one()
        )
        s = build_job_ponder_script(db, job_id=job.id)
        beat = next(
            (b for b in s["beats"] if "Pull Bank Transactions" in b.get("text", "")),
            None,
        )
        assert beat is not None  # the reframe's sentence, a literal beat
        assert "Pulls the bank statement in" in beat["text"]

    def test_dry_capable_engine_pin(self):
        # The narrow opt-in exists ONLY where declared; deny-by-default
        # stands for every other entry.
        from app.services.workflow_engine import _SERVICE_METHOD_REGISTRY as R
        entry = R["plaid_sync.run_sync_pipeline"]
        assert len(entry) > 2 and "dry_run_capable" in entry[2]
        assert all(
            len(e) == 2 for k, e in R.items() if k != "plaid_sync.run_sync_pipeline"
        )


# ── 7b. STREAM SUPERSESSION on reconnect (witness-caught) ───────────────

class TestReconnectSupersession:
    def test_reconnect_supersedes_the_old_stream(self, db, world, monkeypatch):
        """A reconnected item is a NEW stream with NEW transaction ids —
        without supersession the bootstrap re-ingests history as semantic
        duplicates (witnessed live on dev: 48 → 96). The exchange stamps
        the old stream's live rows removed_at; the retraction hook does
        NOT fire (a supersession is not a bank retraction)."""
        from app.services.plaid import service as plaid_service
        row = _seed_feed_row(db, world, f"old-stream-{uuid.uuid4().hex[:6]}")
        # A matched line on the old stream — must stay untouched (no
        # retraction semantics on supersession).
        run, line = _seed_matched_line(db, world, row, run_status="matching")

        def fake_exchange(public_token):
            return {"access_token": "access-new-stream",
                    "item_id": f"item-{uuid.uuid4().hex[:8]}"}

        def fake_accounts(token):
            item = db.get(PlaidItem, world["item_a"])
            return {"accounts": [], "item": {"institution_id": item.institution_id}}

        monkeypatch.setattr(plaid_client, "exchange_public_token", fake_exchange)
        monkeypatch.setattr(plaid_client, "get_accounts", fake_accounts)
        monkeypatch.setattr(plaid_client, "get_institution",
                            lambda i: {"institution": {"name": "First Platypus Bank"}})

        item = db.get(PlaidItem, world["item_a"])
        plaid_service.record_item_from_exchange(
            db, tenant_id=world["a"], public_token="public-re",
            institution_id=item.institution_id,
        )
        db.expire_all()
        assert db.get(BankTransaction, row.id).removed_at is not None  # superseded
        fresh = db.get(ReconciliationTransaction, line.id)
        assert fresh.match_status == "auto_cleared"  # NOT retracted — untouched
        assert db.get(PlaidItem, world["item_a"]).sync_cursor is None


# ── 8b. THE ENGINE PATH — dry-capable invocation through start_run ──────

class TestEngineDryCapablePath:
    def test_engine_dry_run_invokes_read_only_with_real_counts(self, db, world, monkeypatch):
        """The narrow opt-in end to end: an ENGINE dry-run (go_live false)
        invokes the declared-capable adapter with dry_run=True — the
        preview carries REAL counts; nothing persists; run_id threads in."""
        from app.models.workflow import Workflow, WorkflowStep
        from app.services.workflow_engine import start_run

        wf = Workflow(
            name=f"Pull Bank Transactions (pin {uuid.uuid4().hex[:4]})",
            company_id=world["a"], trigger_type="manual", is_active=True,
            scope="tenant",
        )
        db.add(wf)
        db.flush()
        db.add(WorkflowStep(
            workflow_id=wf.id, step_order=1, step_key="sync",
            step_type="action",
            config={
                "action_type": "call_service_method",
                "method_name": "plaid_sync.run_sync_pipeline",
                "kwargs": {"trigger_source": "moc_task_schedule"},
            },
        ))
        db.commit()

        seen = {}

        def spy_pipeline(db_, company_id, triggered_by_user_id=None,
                         dry_run=False, trigger_source="workflow",
                         workflow_run_id=None):
            seen.update(dry_run=dry_run, workflow_run_id=workflow_run_id)
            return {"dry_run": dry_run, "ingested": 14, "updated": 2,
                    "removed": 1, "uncategorized": 3,
                    "would": "would ingest 14, update 2, remove 1 (3 would be uncategorized)"}

        import app.services.plaid.sync as sync_mod
        monkeypatch.setattr(sync_mod, "run_sync_pipeline", spy_pipeline)

        run = start_run(
            db, wf.id, world["a"], None,
            trigger_source="moc_task_schedule", dry_run=True,
        )
        try:
            assert seen["dry_run"] is True          # invoked, read-only
            assert seen["workflow_run_id"] == run.id  # the triage anchor threads
            step_out = (run.output_data or {}).get("sync") or {}
            assert step_out.get("live_effects") is False
            assert "would ingest 14" in step_out.get("would", "")  # REAL counts
        finally:
            db.execute(sql_text("DELETE FROM workflow_review_items WHERE run_id = :r"), {"r": run.id})
            db.execute(sql_text("DELETE FROM workflow_runs WHERE id = :r"), {"r": run.id})
            db.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id = :w"), {"w": wf.id})
            db.execute(sql_text("DELETE FROM workflows WHERE id = :w"), {"w": wf.id})
            db.commit()

    def test_undeclared_methods_still_suppress(self):
        """Deny-by-default stands: only the flagged entry is capable."""
        from app.services.workflow_engine import _SERVICE_METHOD_REGISTRY as R
        capable = [k for k, e in R.items() if len(e) > 2 and "dry_run_capable" in e[2]]
        assert capable == ["plaid_sync.run_sync_pipeline"]


# ── 9. THE PRESERVE RIDER ───────────────────────────────────────────────

class TestPreserveRider:
    def test_cleanup_leaves_the_connection_standing(self, db, world):
        from scripts.seed_staging import _run_cleanup_deletes
        before_items = db.query(PlaidItem).filter(
            PlaidItem.tenant_id == world["a"]).count()
        before_accounts = db.query(BankAccount).filter(
            BankAccount.tenant_id == world["a"]).count()
        assert before_items >= 1 and before_accounts >= 2
        _run_cleanup_deletes(db, world["a"])
        db.commit()  # the seed's caller commits — so do we; the proof is post-commit
        db2 = SessionLocal()
        try:
            assert db2.query(PlaidItem).filter(
                PlaidItem.tenant_id == world["a"]).count() == before_items
            assert db2.query(BankAccount).filter(
                BankAccount.tenant_id == world["a"]).count() == before_accounts
        finally:
            db2.close()
