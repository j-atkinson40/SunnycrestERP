"""The SMTP hardening pins (r136) — the anti-QBO pin's third sibling.

  * ROUND-TRIP: stored ≠ raw, gAAAA prefix carried, decrypts byte-equal.
  * ENCRYPT-AT-WRITE: the service encrypts raw input; already-ciphertext
    input passes untouched (API idempotency).
  * THE SEND PATH decrypts at use — smtplib.login receives the RAW
    password, never the ciphertext (the one consumer that matters).
  * MIGRATION SEMANTICS: plaintext encrypted, ciphertext skipped — the
    census arithmetic proven against seeded rows.
  * NO CLIENT LEAK: the settings serializer never carries the column.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.services.email import crypto as ec


@pytest.fixture(scope="module", autouse=True)
def _key():
    import os
    from cryptography.fernet import Fernet
    prior = os.environ.get("CREDENTIAL_ENCRYPTION_KEY")
    os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    ec._get_fernet.cache_clear()
    yield
    if prior is None:
        os.environ.pop("CREDENTIAL_ENCRYPTION_KEY", None)
    else:
        os.environ["CREDENTIAL_ENCRYPTION_KEY"] = prior
    ec._get_fernet.cache_clear()


@pytest.fixture(scope="module")
def world():
    from app.models.company import Company
    db = SessionLocal()
    co = Company(name="SMTP Co", slug=f"smtp-{uuid.uuid4().hex[:6]}")
    db.add(co); db.commit()
    cid = co.id
    db.close()
    yield {"co": cid}
    db = SessionLocal()
    db.execute(sql_text(
        "DELETE FROM platform_email_settings WHERE tenant_id = :c"), {"c": cid})
    db.execute(sql_text("DELETE FROM companies WHERE id = :c"), {"c": cid})
    db.commit(); db.close()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback(); s.close()


class TestRoundTrip:
    def test_anti_qbo_sibling_stored_is_ciphertext(self):
        raw = f"smtp-pass-{uuid.uuid4().hex}"
        stored = ec.encrypt_secret(raw)
        assert stored != raw and raw not in stored
        assert stored.startswith("gAAAA")
        assert ec.is_fernet_ciphertext(stored)
        assert ec.decrypt_secret(stored) == raw  # byte-equal round-trip

    def test_none_passes_and_empty_refused(self):
        assert ec.decrypt_secret(None) is None
        with pytest.raises(ec.EmailCredentialEncryptionError):
            ec.encrypt_secret("")


class TestEncryptAtWrite:
    def test_service_encrypts_raw_and_passes_ciphertext(self, db, world):
        from app.services.platform_email_service import update_email_settings
        raw = f"pw-{uuid.uuid4().hex[:8]}"
        s = update_email_settings(db, world["co"], {
            "smtp_host": "smtp.example.com", "smtp_username": "mailer",
            "smtp_password_encrypted": raw,
        })
        assert s.smtp_password_encrypted != raw
        assert s.smtp_password_encrypted.startswith("gAAAA")
        assert ec.decrypt_secret(s.smtp_password_encrypted) == raw
        # A round-tripped ciphertext write passes untouched (no double-wrap).
        stored = s.smtp_password_encrypted
        s2 = update_email_settings(db, world["co"], {
            "smtp_password_encrypted": stored,
        })
        assert s2.smtp_password_encrypted == stored


class TestSendDecryptsAtUse:
    def test_login_receives_the_raw_password(self, db, world, monkeypatch):
        from app.services import platform_email_service as pes
        raw = f"pw-{uuid.uuid4().hex[:8]}"
        pes.update_email_settings(db, world["co"], {
            "smtp_host": "smtp.example.com", "smtp_port": 587,
            "smtp_username": "mailer", "smtp_password_encrypted": raw,
            "smtp_use_tls": False,
        })
        seen = {}

        class FakeSMTP:
            def __init__(self, *a, **k): pass
            def starttls(self): pass
            def login(self, user, password): seen.update(user=user, password=password)
            def quit(self): pass
        monkeypatch.setattr(pes.smtplib, "SMTP", FakeSMTP)
        out = pes.verify_smtp(db, world["co"])
        assert out["success"] is True
        assert seen["password"] == raw          # decrypted AT USE
        assert not seen["password"].startswith("gAAAA")


class TestMigrationSemantics:
    def test_encrypts_plaintext_skips_ciphertext(self, db, world):
        """The r136 body's exact logic against seeded rows."""
        import os
        from cryptography.fernet import Fernet
        db.execute(sql_text(
            "UPDATE platform_email_settings SET smtp_password_encrypted = :v "
            "WHERE tenant_id = :c"), {"v": "plain-legacy-pw", "c": world["co"]})
        db.commit()
        rows = db.execute(sql_text(
            "SELECT id, smtp_password_encrypted FROM platform_email_settings "
            "WHERE smtp_password_encrypted IS NOT NULL AND smtp_password_encrypted != ''"
        )).fetchall()
        plaintext = [(r[0], r[1]) for r in rows if not r[1].startswith("gAAAA")]
        f = Fernet(os.environ["CREDENTIAL_ENCRYPTION_KEY"].encode())
        for row_id, value in plaintext:
            db.execute(sql_text(
                "UPDATE platform_email_settings SET smtp_password_encrypted = :c "
                "WHERE id = :i"), {"c": f.encrypt(value.encode()).decode(), "i": row_id})
        db.commit()
        stored = db.execute(sql_text(
            "SELECT smtp_password_encrypted FROM platform_email_settings "
            "WHERE tenant_id = :c"), {"c": world["co"]}).scalar()
        assert stored.startswith("gAAAA")
        assert ec.decrypt_secret(stored) == "plain-legacy-pw"
        # Second pass: zero plaintext remains (idempotent).
        rows2 = db.execute(sql_text(
            "SELECT smtp_password_encrypted FROM platform_email_settings "
            "WHERE smtp_password_encrypted IS NOT NULL AND smtp_password_encrypted != ''"
        )).fetchall()
        assert all(r[0].startswith("gAAAA") for r in rows2)


class TestNoClientLeak:
    def test_serializer_never_carries_the_column(self):
        import inspect
        from app.api.routes.price_management import _serialize_email_settings
        assert "smtp_password_encrypted" not in inspect.getsource(
            _serialize_email_settings)
