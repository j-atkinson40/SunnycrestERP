"""The QBO decommission pins (r134 — the plaintext purge).

  * PURGE SURGICAL + IDEMPOTENT: exactly the credential trio leaves
    accounting_config; non-credential qbo_* metadata and non-QBO keys
    survive; a second pass touches zero rows.
  * ZERO READERS: no application code reads the purged keys anymore —
    asserted at the source level so a future re-introduction fails loudly.
  * VESTIGE GONE: the never-fed `*_encrypted` columns no longer exist in
    schema OR model.
  * RETIRED SURFACES answer honestly (410 + the sentence), never a void.
"""
from __future__ import annotations

import json
import pathlib
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text as sql_text

from app.database import SessionLocal, engine
from app.main import app

RETIRED = "QBO integration is retired — Bridgeable is the accounting system."

PURGE_SQL = """
    UPDATE companies
    SET accounting_config = (
        accounting_config::jsonb - 'qbo_access_token'
            - 'qbo_refresh_token' - 'qbo_client_secret'
    )::text
    WHERE accounting_config IS NOT NULL
      AND accounting_config != ''
      AND (
        accounting_config::jsonb ? 'qbo_access_token'
        OR accounting_config::jsonb ? 'qbo_refresh_token'
        OR accounting_config::jsonb ? 'qbo_client_secret'
      )
"""


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


class TestPurge:
    def test_surgical_and_idempotent(self, db):
        from app.models.company import Company
        slug = f"qbo-purge-{uuid.uuid4().hex[:6]}"
        co = Company(
            name="Purge Co", slug=slug,
            accounting_config=json.dumps({
                "qbo_access_token": "PLAINTEXT-AT",
                "qbo_refresh_token": "PLAINTEXT-RT",
                "qbo_client_secret": "PLAINTEXT-CS",
                "qbo_realm_id": "12345",            # non-credential metadata
                "qbo_connected_at": "2026-01-01",   # non-credential metadata
                "unrelated_setting": "keep-me",     # non-QBO neighbor
            }),
        )
        db.add(co)
        db.commit()
        try:
            r1 = db.execute(sql_text(PURGE_SQL))
            db.commit()
            assert r1.rowcount >= 1
            cfg = json.loads(db.get(Company, co.id).accounting_config)
            # The trio is GONE —
            assert "qbo_access_token" not in cfg
            assert "qbo_refresh_token" not in cfg
            assert "qbo_client_secret" not in cfg
            # — and ONLY the trio (surgical).
            assert cfg["qbo_realm_id"] == "12345"
            assert cfg["qbo_connected_at"] == "2026-01-01"
            assert cfg["unrelated_setting"] == "keep-me"
            # Idempotent: the second pass finds nothing.
            db2 = SessionLocal()
            r2 = db2.execute(sql_text(PURGE_SQL))
            db2.rollback()
            db2.close()
            assert r2.rowcount == 0
        finally:
            db.execute(sql_text("DELETE FROM companies WHERE id = :i"), {"i": co.id})
            db.commit()


class TestZeroReaders:
    def test_no_source_reads_the_purged_keys(self):
        """Source-level assertion: nothing under app/ mentions the purged
        credential keys. Only the migration + this test may."""
        root = pathlib.Path(__file__).resolve().parents[1] / "app"
        offenders = []
        for f in root.rglob("*.py"):
            body = f.read_text(encoding="utf-8", errors="ignore")
            for key in ("qbo_access_token", "qbo_refresh_token", "qbo_client_secret"):
                if key in body:
                    offenders.append(f"{f.relative_to(root)}:{key}")
        assert offenders == [], f"purged-key readers reappeared: {offenders}"

    def test_credential_reader_modules_are_deleted(self):
        root = pathlib.Path(__file__).resolve().parents[1] / "app" / "services" / "accounting"
        assert not (root / "qbo_oauth_service.py").exists()
        assert not (root / "qbo_provider.py").exists()


class TestVestigeGone:
    def test_columns_dropped_from_schema_and_model(self):
        cols = {c["name"] for c in inspect(engine).get_columns("accounting_connections")}
        assert "qbo_access_token_encrypted" not in cols
        assert "qbo_refresh_token_encrypted" not in cols
        assert "sage_api_key_encrypted" not in cols
        from app.models.accounting_connection import AccountingConnection
        model_cols = {c.key for c in AccountingConnection.__table__.columns}
        assert not any("encrypted" in c for c in model_cols)


class TestRetiredSurfaces:
    @pytest.fixture(scope="class")
    def admin(self):
        from app.core.security import hash_password
        from app.models.company import Company
        from app.models.role import Role
        from app.models.user import User
        db = SessionLocal()
        suffix = uuid.uuid4().hex[:6]
        co = Company(name="Retire Co", slug=f"qbo-ret-{suffix}")
        db.add(co); db.flush()
        role = Role(company_id=co.id, name="Admin", slug="admin", is_system=True)
        db.add(role); db.flush()
        email = f"qbo-ret-{suffix}@t.example.com"
        db.add(User(
            company_id=co.id, email=email,
            hashed_password=hash_password("QboRet123!"),
            first_name="Q", last_name="R", role_id=role.id, is_active=True,
        ))
        db.commit()
        ids = {"slug": co.slug, "email": email, "co": co.id}
        db.close()
        yield ids
        db = SessionLocal()
        db.execute(sql_text("DELETE FROM audit_logs WHERE company_id = :c"), {"c": ids["co"]})
        db.execute(sql_text("DELETE FROM accounting_connections WHERE company_id = :c"), {"c": ids["co"]})
        db.execute(sql_text("DELETE FROM users WHERE company_id = :c"), {"c": ids["co"]})
        db.execute(sql_text("DELETE FROM roles WHERE company_id = :c"), {"c": ids["co"]})
        db.execute(sql_text("DELETE FROM companies WHERE id = :c"), {"c": ids["co"]})
        db.commit(); db.close()

    def _headers(self, client, admin):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": admin["email"], "password": "QboRet123!"},
            headers={"X-Company-Slug": admin["slug"]},
        )
        assert resp.status_code == 200, resp.text
        return {
            "Authorization": f"Bearer {resp.json()['access_token']}",
            "X-Company-Slug": admin["slug"],
        }

    def test_qbo_routes_answer_410_with_the_sentence(self, admin):
        client = TestClient(app)
        h = self._headers(client, admin)
        for method, path in [
            ("post", "/api/v1/accounting/qbo/connect"),
            ("post", "/api/v1/accounting/qbo/disconnect"),
            ("post", "/api/v1/accounting-connection/qbo/connect"),
            ("post", "/api/v1/accounting-connection/qbo/connected"),
            ("post", "/api/v1/accounting-connection/qbo/income-accounts"),
        ]:
            resp = getattr(client, method)(path, headers=h)
            assert resp.status_code == 410, f"{path}: {resp.status_code}"
            assert RETIRED in resp.text, path
        # The unauthenticated callback too:
        resp = client.get("/api/v1/accounting/qbo/callback")
        assert resp.status_code == 410

    def test_select_provider_refuses_qbo_honestly(self, admin):
        client = TestClient(app)
        h = self._headers(client, admin)
        resp = client.post(
            "/api/v1/accounting-connection/select-provider",
            json={"provider": "quickbooks_online"}, headers=h,
        )
        assert resp.status_code == 410
        assert RETIRED in resp.text
        # The living providers stay selectable.
        resp = client.post(
            "/api/v1/accounting-connection/select-provider",
            json={"provider": "sage_100"}, headers=h,
        )
        assert resp.status_code == 200

    def test_provider_catalog_no_longer_offers_qbo(self, admin):
        client = TestClient(app)
        h = self._headers(client, admin)
        resp = client.get("/api/v1/accounting/providers", headers=h)
        assert resp.status_code == 200
        keys = [p["key"] for p in resp.json()]
        assert "quickbooks_online" not in keys
        assert "sage_csv" in keys
