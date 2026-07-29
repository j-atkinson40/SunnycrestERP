"""S-1b — the scheduled Plaid sweep's LOUD-FAILURE guarantee.

The non-negotiable, proven here: one item's failure NEVER aborts the sweep
for others; every failure is recorded DURABLY (the WHAT = status +
last_error_code, and the WHEN = last_error_at); EXPECTED Plaid failures
(re-auth) are kept distinct from UNEXPECTED our-code failures
(status="internal_error"); and the run fails ONLY on the unexpected kind —
a routine re-auth is a successful sweep, not a twice-daily cry-wolf (most
tenants have one bank item; Hopkins has one).
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.plaid import BankAccount, PlaidItem
from app.services.plaid import client as plaid_client
from app.services.plaid import crypto as plaid_crypto
from app.services.plaid.sync import run_sync_pipeline


@pytest.fixture(scope="module", autouse=True)
def _fernet_key():
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


# Distinct tokens route the mock: one item fails, the others sync clean.
_FAIL_TOKEN = "tok-fail"
_OK1, _OK2 = "tok-ok-1", "tok-ok-2"


@pytest.fixture
def world():
    """One tenant with THREE bank items — fail-first (created_at order) so
    the sweep must continue past a failure to reach the other two."""
    from app.models.company import Company
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    co = Company(name="LoudFail Co", slug=f"loudfail-{suffix}")
    db.add(co)
    db.flush()

    def mk(tok, inst):
        item = PlaidItem(
            tenant_id=co.id, plaid_item_id=f"item-{uuid.uuid4().hex[:10]}",
            institution_id=inst, institution_name=inst,
            access_token_encrypted=plaid_crypto.encrypt_token(tok),
        )
        db.add(item)
        db.flush()
        acct = BankAccount(
            tenant_id=co.id, plaid_item_id=item.id,
            plaid_account_id=f"chk-{uuid.uuid4().hex[:8]}", name="Checking",
            mask="0000", account_type="depository", account_subtype="checking",
        )
        db.add(acct)
        db.flush()
        return item.id

    ids = {
        "co": co.id,
        "fail": mk(_FAIL_TOKEN, "Fail Bank"),
        "ok1": mk(_OK1, "OK Bank 1"),
        "ok2": mk(_OK2, "OK Bank 2"),
    }
    db.commit()
    db.close()
    yield ids
    db = SessionLocal()
    db.execute(sql_text("DELETE FROM bank_transactions WHERE tenant_id=:c"), {"c": ids["co"]})
    db.execute(sql_text("DELETE FROM bank_accounts WHERE tenant_id=:c"), {"c": ids["co"]})
    db.execute(sql_text("DELETE FROM plaid_items WHERE tenant_id=:c"), {"c": ids["co"]})
    db.execute(sql_text("DELETE FROM companies WHERE id=:c"), {"c": ids["co"]})
    db.commit()
    db.close()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _empty_page():
    return {"added": [], "modified": [], "removed": [], "next_cursor": "c1", "has_more": False}


def _mock_client(monkeypatch, *, fail_exc, fail_tokens=(_FAIL_TOKEN,)):
    """Route sync_transactions on the (decrypted) access token: fail_tokens
    raise fail_exc; everyone else returns a clean empty page. get_accounts
    is stubbed so the best-effort balance refresh never hits the network."""
    def fake_sync(access_token, cursor, count=500):
        if access_token in fail_tokens:
            raise fail_exc
        return _empty_page()
    monkeypatch.setattr(plaid_client, "sync_transactions", fake_sync)
    monkeypatch.setattr(plaid_client, "get_accounts", lambda access_token: {"accounts": []})


def _plaid_error(code):
    return plaid_client.PlaidApiError(
        status=400, error_type="ITEM_ERROR", error_code=code,
        display_message=None, request_id="req-test",
    )


class TestExpectedFailureIsolatedAndRecorded:
    def test_one_item_login_required_isolates_and_records_what_and_when(
        self, db, world, monkeypatch
    ):
        _mock_client(monkeypatch, fail_exc=_plaid_error("ITEM_LOGIN_REQUIRED"))
        summary = run_sync_pipeline(db, company_id=world["co"])
        # The sweep COMPLETED for the other two items.
        assert summary["items_synced"] == 2
        assert summary["items_errored"] == 1
        assert summary["items_errored_unexpected"] == 0
        # The failed item: WHAT + WHEN recorded durably; expected marker.
        failed = db.get(PlaidItem, world["fail"])
        assert failed.status == "login_required"
        assert failed.last_error_code == "ITEM_LOGIN_REQUIRED"
        assert failed.last_error_at is not None
        # The other items actually synced (stayed active).
        assert db.get(PlaidItem, world["ok1"]).status == "active"
        assert db.get(PlaidItem, world["ok2"]).status == "active"

    def test_all_items_expected_fail_is_a_successful_sweep_no_raise(
        self, db, world, monkeypatch
    ):
        # EVERY item needs re-auth — the cry-wolf guard: a successful sweep
        # with recorded states, NOT a run failure (must not raise).
        _mock_client(
            monkeypatch, fail_exc=_plaid_error("ITEM_LOGIN_REQUIRED"),
            fail_tokens=(_FAIL_TOKEN, _OK1, _OK2),
        )
        summary = run_sync_pipeline(db, company_id=world["co"])  # MUST NOT raise
        assert summary["items_synced"] == 0
        assert summary["items_errored"] == 3
        assert summary["items_errored_unexpected"] == 0
        for k in ("fail", "ok1", "ok2"):
            it = db.get(PlaidItem, world[k])
            assert it.status == "login_required"
            assert it.last_error_at is not None


class TestUnexpectedFailureIsolatedRecordedAndRaises:
    def test_non_plaid_exception_records_internal_error_isolates_then_raises(
        self, db, world, monkeypatch
    ):
        # A bug in OUR code (not a Plaid error) — the newly-covered path.
        _mock_client(monkeypatch, fail_exc=ValueError("boom in our code"))
        with pytest.raises(RuntimeError, match="internal error"):
            run_sync_pipeline(db, company_id=world["co"])
        # DESPITE the raise, the failure is recorded durably AND the sweep
        # completed for the other items (committed before the end-raise).
        failed = db.get(PlaidItem, world["fail"])
        assert failed.status == "internal_error"       # DISTINCT from a bank problem
        assert failed.last_error_code == "ValueError"  # the "what" (type name, not a trace)
        assert failed.last_error_at is not None         # the "when"
        # Isolation: the two OK items synced despite the internal error.
        assert db.get(PlaidItem, world["ok1"]).status == "active"
        assert db.get(PlaidItem, world["ok2"]).status == "active"

    def test_mixed_expected_and_unexpected_raises_but_both_recorded(
        self, db, world, monkeypatch
    ):
        # fail item → ValueError (unexpected); ok1 → re-auth (expected);
        # ok2 → clean. Run raises (unexpected present) but all states land.
        def fake_sync(access_token, cursor, count=500):
            if access_token == _FAIL_TOKEN:
                raise ValueError("our bug")
            if access_token == _OK1:
                raise _plaid_error("ITEM_LOGIN_REQUIRED")
            return _empty_page()
        monkeypatch.setattr(plaid_client, "sync_transactions", fake_sync)
        monkeypatch.setattr(plaid_client, "get_accounts", lambda access_token: {"accounts": []})
        with pytest.raises(RuntimeError):
            run_sync_pipeline(db, company_id=world["co"])
        assert db.get(PlaidItem, world["fail"]).status == "internal_error"
        assert db.get(PlaidItem, world["ok1"]).status == "login_required"
        assert db.get(PlaidItem, world["ok2"]).status == "active"
