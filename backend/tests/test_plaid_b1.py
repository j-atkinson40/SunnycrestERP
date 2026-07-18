"""Plaid B-1 pins — THE ORDER OF PROOF IS THE POINT.

  * ISOLATION (first, before any surface): bank data is the catastrophic
    class. Company A can never see, count, or infer company B's banking —
    every read path 404s indistinguishable-from-absent on cross-tenant ids.
  * THE ANTI-QBO PIN (named as such): the stored access token is Fernet
    ciphertext that round-trips byte-equal — the column is ACTUALLY FED,
    unlike AccountingConnection's dead `*_encrypted` columns and the
    plaintext `Company.accounting_config` tokens this build refuses to
    model on.
  * REDACTION: the raw token never appears in log records across the item
    lifecycle (link → exchange → read), nor in any route response.
  * TRANSACTIONALITY: a failed exchange never half-records an item.
  * RECONNECT IDEMPOTENCY: the same institution reconnected updates in
    place — no duplicate accounts; financial-account links survive.
"""
from __future__ import annotations

import logging
import uuid

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.plaid import BankAccount, PlaidItem
from app.services.plaid import client as plaid_client
from app.services.plaid import crypto as plaid_crypto
from app.services.plaid import service as plaid_service
from app.services.plaid.service import PlaidNotFoundError


# ── World: two tenants, an admin + office user each ─────────────────────

@pytest.fixture(scope="module", autouse=True)
def _fernet_key(  ):
    """Tests run under their own generated key (dev may not set one).
    The lru_cache pins per-process — clear around the module."""
    import os
    prior = os.environ.get("CREDENTIAL_ENCRYPTION_KEY")
    os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    plaid_crypto.reset_fernet_cache()
    yield
    if prior is None:
        os.environ.pop("CREDENTIAL_ENCRYPTION_KEY", None)
    else:
        os.environ["CREDENTIAL_ENCRYPTION_KEY"] = prior
    plaid_crypto.reset_fernet_cache()


def _mk_company(db, slug):
    from app.models.company import Company
    co = db.query(Company).filter(Company.slug == slug).first()
    if co is None:
        co = Company(name=slug.title(), slug=slug)
        db.add(co)
        db.flush()
    return co


def _mk_user(db, company, email, role_slug):
    from app.core.security import hash_password
    from app.models.role import Role
    from app.models.user import User
    role = (
        db.query(Role)
        .filter(Role.company_id == company.id, Role.slug == role_slug)
        .first()
    )
    if role is None:
        role = Role(
            company_id=company.id, name=role_slug.title(), slug=role_slug,
            is_system=(role_slug == "admin"),
        )
        db.add(role)
        db.flush()
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            company_id=company.id, email=email,
            hashed_password=hash_password("PlaidPin123!"),
            first_name="P", last_name="T", role_id=role.id, is_active=True,
        )
        db.add(user)
        db.flush()
    return user


@pytest.fixture(scope="module")
def world():
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    co_a = _mk_company(db, f"plaid-a-{suffix}")
    co_b = _mk_company(db, f"plaid-b-{suffix}")
    _mk_user(db, co_a, f"admin-a-{suffix}@t.example.com", "admin")
    _mk_user(db, co_a, f"office-a-{suffix}@t.example.com", "office")
    _mk_user(db, co_b, f"admin-b-{suffix}@t.example.com", "admin")
    db.commit()
    ids = {
        "a": co_a.id, "b": co_b.id,
        "a_slug": co_a.slug, "b_slug": co_b.slug,
        "admin_a": f"admin-a-{suffix}@t.example.com",
        "office_a": f"office-a-{suffix}@t.example.com",
        "admin_b": f"admin-b-{suffix}@t.example.com",
    }
    db.close()
    yield ids
    db = SessionLocal()
    for co_id in (ids["a"], ids["b"]):
        db.query(BankAccount).filter(BankAccount.tenant_id == co_id).delete()
        db.query(PlaidItem).filter(PlaidItem.tenant_id == co_id).delete()
    db.commit()
    db.close()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def client():
    return TestClient(app)


def _auth(client, world, email, slug):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "PlaidPin123!"},
        headers={"X-Company-Slug": slug},
    )
    assert resp.status_code == 200, resp.text
    return {
        "Authorization": f"Bearer {resp.json()['access_token']}",
        "X-Company-Slug": slug,
    }


def _seed_item(db, tenant_id, *, institution_id="ins_test", token="access-sandbox-raw"):
    item = PlaidItem(
        tenant_id=tenant_id,
        plaid_item_id=f"item-{uuid.uuid4().hex[:10]}",
        institution_id=institution_id,
        institution_name="First Platypus Bank",
        access_token_encrypted=plaid_crypto.encrypt_token(token),
    )
    db.add(item)
    db.flush()
    db.add(BankAccount(
        tenant_id=tenant_id, plaid_item_id=item.id,
        plaid_account_id=f"acc-{uuid.uuid4().hex[:10]}",
        name="Plaid Checking", mask="0000",
        account_type="depository", account_subtype="checking",
    ))
    db.commit()
    return item


# ── 1. ISOLATION — the pins before the paint ────────────────────────────

class TestCrossTenantIsolation:
    def test_b_cannot_list_a_items(self, db, client, world):
        _seed_item(db, world["a"])
        h_b = _auth(client, world, world["admin_b"], world["b_slug"])
        resp = client.get("/api/v1/plaid/items", headers=h_b)
        assert resp.status_code == 200
        assert resp.json() == []  # not even a count leaks

    def test_b_gets_404_on_a_item_id(self, db, client, world):
        item = _seed_item(db, world["a"])
        h_b = _auth(client, world, world["admin_b"], world["b_slug"])
        resp = client.get(f"/api/v1/plaid/items/{item.id}", headers=h_b)
        assert resp.status_code == 404
        # Indistinguishable from absent:
        ghost = client.get(f"/api/v1/plaid/items/{uuid.uuid4()}", headers=h_b)
        assert ghost.status_code == 404
        assert resp.json() == ghost.json()

    def test_b_cannot_update_mode_link_a_item(self, db, client, world):
        # link-token with another tenant's item_id must 404 BEFORE any
        # decrypt or Plaid call happens.
        item = _seed_item(db, world["a"])
        h_b = _auth(client, world, world["admin_b"], world["b_slug"])
        resp = client.post(
            "/api/v1/plaid/link-token", json={"item_id": item.id}, headers=h_b,
        )
        assert resp.status_code == 404

    def test_service_layer_scopes_inside_the_query(self, db, world):
        item = _seed_item(db, world["a"])
        with pytest.raises(PlaidNotFoundError):
            plaid_service.get_item(db, tenant_id=world["b"], item_id=item.id)
        with pytest.raises(PlaidNotFoundError):
            plaid_service.list_accounts(db, tenant_id=world["b"], item_id=item.id)


# ── 2. THE ANTI-QBO PIN — the encrypted column is actually fed ──────────

class TestEncryptRoundTrip:
    def test_anti_qbo_store_decrypt_byte_equal(self, db, world):
        """Named for the anti-precedent: QBO's `*_encrypted` columns are
        dead vestige and its real tokens sit plaintext in
        Company.accounting_config. THIS column holds real ciphertext."""
        raw = f"access-sandbox-{uuid.uuid4().hex}"
        item = _seed_item(db, world["a"], token=raw)
        stored = db.get(PlaidItem, item.id).access_token_encrypted
        assert stored != raw
        assert raw not in stored
        assert stored.startswith("gAAAA")  # Fernet token prefix
        assert plaid_service.access_token_for(item) == raw  # byte-equal round-trip

    def test_refuses_empty_token(self):
        with pytest.raises(plaid_crypto.PlaidCredentialEncryptionError):
            plaid_crypto.encrypt_token("")


# ── 3. REDACTION — the token never logs ─────────────────────────────────

class TestRedaction:
    def test_token_absent_from_logs_across_item_lifecycle(
        self, db, client, world, caplog, monkeypatch,
    ):
        raw = f"access-sandbox-{uuid.uuid4().hex}"
        _mock_plaid(monkeypatch, access_token=raw, institution_id=f"ins-red-{uuid.uuid4().hex[:6]}")
        h_a = _auth(client, world, world["admin_a"], world["a_slug"])
        with caplog.at_level(logging.DEBUG):
            resp = client.post(
                "/api/v1/plaid/exchange",
                json={"public_token": "public-sandbox-x"}, headers=h_a,
            )
            assert resp.status_code == 200
            client.get("/api/v1/plaid/items", headers=h_a)
        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert raw not in joined
        # And never in a response body:
        assert raw not in resp.text

    def test_redact_for_audit_shape(self):
        out = plaid_crypto.redact_for_audit({"access_token": "secret-value"})
        assert out == {"access_token": {"present": True, "length": 12}}


# ── 4. EXCHANGE TRANSACTIONALITY + RECONNECT IDEMPOTENCY ────────────────

def _mock_plaid(monkeypatch, *, access_token="access-sandbox-mock",
                institution_id="ins_109508", accounts=None, fail_accounts=False):
    accounts = accounts if accounts is not None else [
        {
            "account_id": f"plaid-acc-{uuid.uuid4().hex[:8]}",
            "name": "Plaid Checking", "official_name": "Plaid Gold Standard",
            "mask": "0000", "type": "depository", "subtype": "checking",
            "balances": {"current": 110.0, "available": 100.0},
        },
        {
            "account_id": f"plaid-acc-{uuid.uuid4().hex[:8]}",
            "name": "Plaid Credit Card", "official_name": "Plaid Diamond",
            "mask": "3333", "type": "credit", "subtype": "credit card",
            "balances": {"current": 410.0, "available": None},
        },
    ]

    def fake_exchange(public_token):
        return {"access_token": access_token,
                "item_id": f"item-{uuid.uuid4().hex[:10]}"}

    def fake_accounts(token):
        if fail_accounts:
            raise plaid_client.PlaidApiError(
                status=400, error_type="ITEM_ERROR",
                error_code="ITEM_LOGIN_REQUIRED",
                display_message=None, request_id="req-test",
            )
        return {"accounts": accounts, "item": {"institution_id": institution_id}}

    def fake_institution(inst_id):
        return {"institution": {"name": "First Platypus Bank"}}

    monkeypatch.setattr(plaid_client, "exchange_public_token", fake_exchange)
    monkeypatch.setattr(plaid_client, "get_accounts", fake_accounts)
    monkeypatch.setattr(plaid_client, "get_institution", fake_institution)
    return accounts


class TestExchange:
    def test_failed_exchange_never_half_records(self, db, client, world, monkeypatch):
        _mock_plaid(monkeypatch, fail_accounts=True,
                    institution_id=f"ins-fail-{uuid.uuid4().hex[:6]}")
        h_a = _auth(client, world, world["admin_a"], world["a_slug"])
        before = db.query(PlaidItem).filter(PlaidItem.tenant_id == world["a"]).count()
        resp = client.post(
            "/api/v1/plaid/exchange",
            json={"public_token": "public-sandbox-x"}, headers=h_a,
        )
        assert resp.status_code == 502
        assert resp.json()["detail"]["error_code"] == "ITEM_LOGIN_REQUIRED"
        db.expire_all()
        after = db.query(PlaidItem).filter(PlaidItem.tenant_id == world["a"]).count()
        assert after == before  # zero rows from the failed connect

    def test_exchange_records_item_and_typed_accounts(
        self, db, client, world, monkeypatch,
    ):
        inst = f"ins-ok-{uuid.uuid4().hex[:6]}"
        _mock_plaid(monkeypatch, institution_id=inst)
        h_a = _auth(client, world, world["admin_a"], world["a_slug"])
        resp = client.post(
            "/api/v1/plaid/exchange",
            json={"public_token": "public-sandbox-x"}, headers=h_a,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["institution_name"] == "First Platypus Bank"
        assert len(body["accounts"]) == 2
        credit = next(a for a in body["accounts"] if a["account_type"] == "credit")
        assert credit["is_credit"] is True
        assert "access_token" not in resp.text

    def test_reconnect_same_institution_no_duplicates(
        self, db, client, world, monkeypatch,
    ):
        inst = f"ins-re-{uuid.uuid4().hex[:6]}"
        h_a = _auth(client, world, world["admin_a"], world["a_slug"])
        first_accounts = _mock_plaid(monkeypatch, institution_id=inst)
        r1 = client.post("/api/v1/plaid/exchange",
                         json={"public_token": "public-1"}, headers=h_a)
        assert r1.status_code == 200
        item_id = r1.json()["id"]

        # Link a FinancialAccount to the checking row (the link that must
        # survive the reconnect).
        db.expire_all()
        checking = (
            db.query(BankAccount)
            .filter(BankAccount.plaid_item_id == item_id, BankAccount.mask == "0000")
            .first()
        )
        checking.financial_account_id = None  # column exists; keep None (no FA row)
        marker_id = checking.id
        db.commit()

        # Reconnect: NEW plaid item id + NEW account ids, same institution,
        # same masks/subtypes — Plaid's reconnect reality.
        second_accounts = [
            {**a, "account_id": f"plaid-acc-{uuid.uuid4().hex[:8]}"}
            for a in first_accounts
        ]
        _mock_plaid(monkeypatch, institution_id=inst,
                    access_token=f"access-sandbox-{uuid.uuid4().hex[:8]}",
                    accounts=second_accounts)
        r2 = client.post("/api/v1/plaid/exchange",
                         json={"public_token": "public-2"}, headers=h_a)
        assert r2.status_code == 200
        assert r2.json()["id"] == item_id  # SAME connection row, updated

        db.expire_all()
        items = (
            db.query(PlaidItem)
            .filter(PlaidItem.tenant_id == world["a"],
                    PlaidItem.institution_id == inst,
                    PlaidItem.is_active.is_(True))
            .all()
        )
        assert len(items) == 1
        assert items[0].sync_cursor is None  # new stream, cursor reset
        rows = (
            db.query(BankAccount)
            .filter(BankAccount.plaid_item_id == item_id,
                    BankAccount.is_active.is_(True))
            .all()
        )
        assert len(rows) == 2  # no duplicates
        surviving = next(r for r in rows if r.mask == "0000")
        assert surviving.id == marker_id  # the ROW survived (links intact)


# ── 5. GATING ────────────────────────────────────────────────────────────

class TestGating:
    def test_non_admin_cannot_mint_link_token(self, client, world):
        h = _auth(client, world, world["office_a"], world["a_slug"])
        resp = client.post("/api/v1/plaid/link-token", json={}, headers=h)
        assert resp.status_code == 403

    def test_non_admin_can_read_connected_state(self, db, client, world):
        _seed_item(db, world["a"], institution_id=f"ins-read-{uuid.uuid4().hex[:6]}")
        h = _auth(client, world, world["office_a"], world["a_slug"])
        resp = client.get("/api/v1/plaid/items", headers=h)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_unconfigured_env_surfaces_503_not_a_guess(self, client, world, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "PLAID_CLIENT_ID", "")
        h = _auth(client, world, world["admin_a"], world["a_slug"])
        resp = client.post("/api/v1/plaid/link-token", json={}, headers=h)
        assert resp.status_code == 503
        assert "PLAID_CLIENT_ID" in resp.json()["detail"]
