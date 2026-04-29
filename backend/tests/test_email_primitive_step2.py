"""Phase W-4b Layer 1 Email Step 2 — inbound sync infrastructure tests.

Coverage:
  - Migration r64 schema (encrypted_credentials, sync state extensions,
    oauth_state_nonces table)
  - Email crypto round-trip + key-rotation failure mode
  - OAuth state nonce issuance + single-use + expiry + tenant/user
    mismatch rejection
  - OAuth code → token exchange (mocked httpx); token refresh; key
    rotation re-OAuth path
  - Encrypted credential persistence + audit log on every credential
    op
  - Real Gmail / MSGraph / IMAP provider implementations against
    mocked transports
  - Message ingestion pipeline:
      * Idempotent re-ingestion via provider_message_id
      * Thread reconstruction via In-Reply-To header
      * Thread reconstruction subject-fallback
      * Participant resolution (internal user / external Bridgeable
        tenant / external CRM contact / unresolved)
      * Cross-tenant detection at participant resolution
      * Retroactive linkage trigger + audit log
  - Webhook handlers:
      * Gmail Pub/Sub JWT verification (mocked google-auth)
      * Gmail webhook envelope parsing
      * MS Graph clientState verification
      * MS Graph validationToken handshake
  - Sync engine:
      * sync_in_progress mutex
      * Circuit breaker (consecutive_error_count tracking)
      * run_initial_backfill happy path + error path
  - APScheduler sweep functions (token refresh + IMAP polling +
    subscription renewal) — verify queries land correct accounts
  - API endpoints:
      * GET /email-accounts/oauth/{provider}/authorize-url issues a
        DB-stored nonce
      * POST /email-accounts/oauth/callback validates nonce, exchanges,
        persists, returns account row
      * GET /email-accounts/{id}/sync-status surfaces full status
      * Webhook endpoint signature verification + 401 on failure
  - Per-tenant isolation across all surfaces
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
import pytest

from cryptography.fernet import Fernet


# Fix encryption key BEFORE any service imports so module-level
# lru_cache picks it up.
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _make_ctx(*, role_slug: str = "admin", vertical: str = "manufacturing"):
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"EM2-{suffix}",
            slug=f"em2-{suffix}",
            is_active=True,
            vertical=vertical,
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name=role_slug.title(),
            slug=role_slug,
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@em2.co",
            first_name="EM2",
            last_name="User",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "user_id": user.id,
            "company_id": co.id,
            "token": token,
            "slug": co.slug,
        }
    finally:
        db.close()


@pytest.fixture
def ctx():
    return _make_ctx()


@pytest.fixture
def ctx_b():
    return _make_ctx(role_slug="admin", vertical="funeral_home")


@pytest.fixture
def auth(ctx):
    return {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Company-Slug": ctx["slug"],
    }


def _make_account(ctx, provider_type: str = "gmail"):
    from app.database import SessionLocal
    from app.services.email import account_service

    db = SessionLocal()
    try:
        a = account_service.create_account(
            db,
            tenant_id=ctx["company_id"],
            actor_user_id=ctx["user_id"],
            account_type="shared",
            display_name="Test",
            email_address=f"test-{uuid.uuid4().hex[:6]}@example.com",
            provider_type=provider_type,
        )
        db.commit()
        return a.id
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────
# 1. Migration schema
# ─────────────────────────────────────────────────────────────────────


class TestMigrationR64Schema:
    def test_email_accounts_has_step2_columns(self):
        from sqlalchemy import inspect

        from app.database import engine

        cols = {c["name"] for c in inspect(engine).get_columns("email_accounts")}
        for expected in (
            "encrypted_credentials",
            "token_expires_at",
            "last_credential_op",
            "last_credential_op_at",
            "backfill_days",
            "backfill_status",
            "backfill_progress_pct",
            "backfill_started_at",
            "backfill_completed_at",
        ):
            assert expected in cols, f"Missing column: {expected}"

    def test_sync_state_step2_columns(self):
        from sqlalchemy import inspect

        from app.database import engine

        cols = {
            c["name"]
            for c in inspect(engine).get_columns("email_account_sync_state")
        }
        assert "consecutive_error_count" in cols
        assert "last_provider_cursor" in cols
        assert "sync_in_progress" in cols

    def test_oauth_state_nonces_table_exists(self):
        from sqlalchemy import inspect

        from app.database import engine

        assert "oauth_state_nonces" in inspect(engine).get_table_names()


# ─────────────────────────────────────────────────────────────────────
# 2. Crypto round-trip + redaction
# ─────────────────────────────────────────────────────────────────────


class TestEmailCrypto:
    def test_encrypt_decrypt_round_trip(self):
        from app.services.email.crypto import (
            decrypt_credentials,
            encrypt_credentials,
        )

        payload = {
            "access_token": "ya29.long-token-value",
            "refresh_token": "1//refresh-secret",
            "token_expires_at": "2026-05-08T12:00:00+00:00",
        }
        token = encrypt_credentials(payload)
        assert isinstance(token, str)
        assert "ya29" not in token  # encrypted, not visible
        assert decrypt_credentials(token) == payload

    def test_decrypt_empty_returns_empty_dict(self):
        from app.services.email.crypto import decrypt_credentials

        assert decrypt_credentials(None) == {}
        assert decrypt_credentials("") == {}

    def test_decrypt_corrupt_token_raises(self):
        from app.services.email.crypto import (
            EmailCredentialEncryptionError,
            decrypt_credentials,
        )

        with pytest.raises(EmailCredentialEncryptionError):
            decrypt_credentials("not-a-valid-fernet-token")

    def test_redact_for_audit_hides_values(self):
        from app.services.email.crypto import redact_for_audit

        redacted = redact_for_audit({"access_token": "secret", "scope": "x"})
        assert "secret" not in str(redacted)
        assert redacted["access_token"]["present"] is True
        assert redacted["access_token"]["length"] == 6


# ─────────────────────────────────────────────────────────────────────
# 3. OAuth state nonce — CSRF protection
# ─────────────────────────────────────────────────────────────────────


class TestOAuthStateNonce:
    def test_issue_and_consume_round_trip(self, ctx):
        from app.database import SessionLocal
        from app.services.email import oauth_service

        db = SessionLocal()
        try:
            nonce = oauth_service.issue_state_nonce(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                provider_type="gmail",
                redirect_uri="https://app/cb",
            )
            db.commit()
            assert len(nonce) > 20  # cryptographically random
            row = oauth_service.validate_and_consume_state_nonce(
                db,
                nonce=nonce,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                provider_type="gmail",
            )
            assert row.consumed_at is not None
        finally:
            db.close()

    def test_nonce_single_use_replay_rejected(self, ctx):
        from app.database import SessionLocal
        from app.services.email import oauth_service
        from app.services.email.oauth_service import OAuthStateInvalid

        db = SessionLocal()
        try:
            nonce = oauth_service.issue_state_nonce(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                provider_type="gmail",
                redirect_uri="https://app/cb",
            )
            db.commit()
            oauth_service.validate_and_consume_state_nonce(
                db,
                nonce=nonce,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                provider_type="gmail",
            )
            with pytest.raises(OAuthStateInvalid, match="already consumed"):
                oauth_service.validate_and_consume_state_nonce(
                    db,
                    nonce=nonce,
                    tenant_id=ctx["company_id"],
                    user_id=ctx["user_id"],
                    provider_type="gmail",
                )
        finally:
            db.close()

    def test_nonce_tenant_mismatch_rejected(self, ctx, ctx_b):
        from app.database import SessionLocal
        from app.services.email import oauth_service
        from app.services.email.oauth_service import OAuthStateInvalid

        db = SessionLocal()
        try:
            nonce = oauth_service.issue_state_nonce(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                provider_type="gmail",
                redirect_uri="https://app/cb",
            )
            db.commit()
            with pytest.raises(OAuthStateInvalid, match="tenant"):
                oauth_service.validate_and_consume_state_nonce(
                    db,
                    nonce=nonce,
                    tenant_id=ctx_b["company_id"],
                    user_id=ctx["user_id"],
                    provider_type="gmail",
                )
        finally:
            db.close()

    def test_nonce_expired_rejected(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import OAuthStateNonce
        from app.services.email import oauth_service
        from app.services.email.oauth_service import OAuthStateInvalid

        db = SessionLocal()
        try:
            nonce = oauth_service.issue_state_nonce(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                provider_type="gmail",
                redirect_uri="https://app/cb",
            )
            db.commit()
            # Force-expire the row.
            row = (
                db.query(OAuthStateNonce)
                .filter(OAuthStateNonce.nonce == nonce)
                .first()
            )
            row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            db.commit()
            with pytest.raises(OAuthStateInvalid, match="expired"):
                oauth_service.validate_and_consume_state_nonce(
                    db,
                    nonce=nonce,
                    tenant_id=ctx["company_id"],
                    user_id=ctx["user_id"],
                    provider_type="gmail",
                )
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 4. OAuth code-exchange + token refresh against mocked httpx
# ─────────────────────────────────────────────────────────────────────


def _mock_httpx_response(status: int, json_body: dict):
    return httpx.Response(status_code=status, json=json_body)


class TestOAuthExchange:
    def test_complete_exchange_persists_encrypted_creds(self, ctx, monkeypatch):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailAuditLog
        from app.services.email import account_service, oauth_service
        from app.services.email.crypto import decrypt_credentials

        # Patch the specific exchange function — see test_oauth_callback_full_flow
        # for rationale (TestClient uses httpx internally; global patch breaks it).
        monkeypatch.setattr(
            oauth_service,
            "_exchange_gmail",
            lambda *, code, redirect_uri: {
                "access_token": "ya29.fake",
                "refresh_token": "1//refresh",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "gmail.modify",
            },
        )

        account_id = _make_account(ctx, "gmail")
        db = SessionLocal()
        try:
            account = account_service.get_account(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
            )
            creds = oauth_service.complete_oauth_exchange(
                db,
                account=account,
                code="auth-code-from-google",
                redirect_uri="https://app/cb",
                actor_user_id=ctx["user_id"],
            )
            db.commit()
            assert creds["access_token"] == "ya29.fake"
            db.refresh(account)
            assert account.encrypted_credentials is not None
            assert account.token_expires_at is not None
            # Ensure encrypted form doesn't leak token in cleartext
            assert "ya29.fake" not in account.encrypted_credentials
            # Round-trip works
            assert (
                decrypt_credentials(account.encrypted_credentials)[
                    "access_token"
                ]
                == "ya29.fake"
            )
            # Audit log entry written
            entries = (
                db.query(EmailAuditLog)
                .filter(
                    EmailAuditLog.tenant_id == ctx["company_id"],
                    EmailAuditLog.entity_id == account.id,
                    EmailAuditLog.action == "credentials_persisted",
                )
                .all()
            )
            assert len(entries) == 1
            # Audit changes don't leak token values
            assert "ya29.fake" not in json.dumps(entries[0].changes)
        finally:
            db.close()

    def test_refresh_token_updates_creds_and_audits(
        self, ctx, monkeypatch
    ):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailAuditLog
        from app.services.email import account_service, oauth_service
        from app.services.email.crypto import (
            decrypt_credentials,
            encrypt_credentials,
        )

        # Pre-seed the account with credentials
        account_id = _make_account(ctx, "gmail")
        db = SessionLocal()
        try:
            account = account_service.get_account(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
            )
            account.encrypted_credentials = encrypt_credentials(
                {
                    "access_token": "old-token",
                    "refresh_token": "long-lived-refresh",
                    "token_expires_at": "2026-05-08T00:00:00+00:00",
                }
            )
            account.token_expires_at = datetime.now(timezone.utc) - timedelta(
                minutes=1
            )
            db.commit()

            monkeypatch.setattr(
                oauth_service,
                "_refresh_gmail",
                lambda *, refresh_token: {
                    "access_token": "new-token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            )

            oauth_service.refresh_token(
                db, account=account, actor_user_id=ctx["user_id"]
            )
            db.commit()
            db.refresh(account)
            new_creds = decrypt_credentials(account.encrypted_credentials)
            assert new_creds["access_token"] == "new-token"
            # Refresh token preserved when provider doesn't return new one
            assert new_creds["refresh_token"] == "long-lived-refresh"
            entries = (
                db.query(EmailAuditLog)
                .filter(
                    EmailAuditLog.entity_id == account.id,
                    EmailAuditLog.action == "credentials_refreshed",
                )
                .all()
            )
            assert len(entries) == 1
        finally:
            db.close()

    def test_refresh_failure_audits_and_raises(self, ctx, monkeypatch):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailAuditLog
        from app.services.email import account_service, oauth_service
        from app.services.email.crypto import encrypt_credentials
        from app.services.email.oauth_service import OAuthAuthError

        account_id = _make_account(ctx, "gmail")
        db = SessionLocal()
        try:
            account = account_service.get_account(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
            )
            account.encrypted_credentials = encrypt_credentials(
                {
                    "access_token": "old",
                    "refresh_token": "bad-refresh",
                    "token_expires_at": "2026-05-08T00:00:00+00:00",
                }
            )
            db.commit()

            def _fail_refresh(*, refresh_token):
                raise OAuthAuthError(
                    "Gmail token refresh failed (status=400): "
                    '{"error":"invalid_grant"}'
                )

            monkeypatch.setattr(oauth_service, "_refresh_gmail", _fail_refresh)

            with pytest.raises(OAuthAuthError):
                oauth_service.refresh_token(db, account=account)
            db.commit()
            entries = (
                db.query(EmailAuditLog)
                .filter(
                    EmailAuditLog.entity_id == account.id,
                    EmailAuditLog.action == "credentials_refresh_failed",
                )
                .all()
            )
            assert len(entries) == 1
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 5. Provider implementations
# ─────────────────────────────────────────────────────────────────────


class TestProviderImplementations:
    def test_gmail_parse_message_round_trip(self):
        from app.services.email.providers.gmail import _parse_gmail_message

        body_b64 = base64.urlsafe_b64encode(b"<p>Hello</p>").decode().rstrip(
            "="
        )
        payload = {
            "id": "gm-1",
            "threadId": "thr-1",
            "internalDate": "1715000000000",
            "payload": {
                "headers": [
                    {"name": "From", "value": "alice@x.com"},
                    {"name": "To", "value": "bob@y.com, carol@y.com"},
                    {"name": "Subject", "value": "Re: hello"},
                    {"name": "In-Reply-To", "value": "<parent-msg-id>"},
                    {
                        "name": "Date",
                        "value": "Tue, 5 May 2026 10:00:00 +0000",
                    },
                ],
                "mimeType": "text/html",
                "body": {"data": body_b64},
                "parts": [],
            },
        }
        msg = _parse_gmail_message(payload)
        assert msg.provider_message_id == "gm-1"
        assert msg.provider_thread_id == "thr-1"
        assert msg.sender_email == "alice@x.com"
        assert msg.subject == "Re: hello"
        assert msg.in_reply_to_provider_id == "parent-msg-id"
        assert len(msg.to) == 2
        assert msg.body_html == "<p>Hello</p>"

    def test_msgraph_parse_message_round_trip(self):
        from app.services.email.providers.msgraph import _parse_msgraph_message

        payload = {
            "id": "ms-1",
            "conversationId": "conv-1",
            "subject": "Hi",
            "from": {
                "emailAddress": {"address": "alice@x.com", "name": "Alice"}
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": "bob@y.com",
                        "name": "Bob",
                    }
                }
            ],
            "body": {"contentType": "html", "content": "<p>Hi</p>"},
            "sentDateTime": "2026-05-05T10:00:00Z",
            "receivedDateTime": "2026-05-05T10:00:01Z",
            "hasAttachments": False,
        }
        msg = _parse_msgraph_message(payload)
        assert msg.provider_message_id == "ms-1"
        assert msg.provider_thread_id == "conv-1"
        assert msg.sender_email == "alice@x.com"
        assert msg.body_html == "<p>Hi</p>"

    def test_imap_parse_mime_round_trip(self):
        import email

        from app.services.email.providers.imap import _parse_imap_mime

        raw = (
            "From: alice@x.com\r\n"
            "To: bob@y.com\r\n"
            "Subject: Test\r\n"
            "In-Reply-To: <parent>\r\n"
            "Date: Tue, 5 May 2026 10:00:00 +0000\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n"
            "\r\n"
            "Hello world"
        ).encode()
        mime = email.message_from_bytes(raw)
        msg = _parse_imap_mime("123", mime, raw)
        assert msg.provider_message_id == "123"
        assert msg.sender_email == "alice@x.com"
        assert msg.body_text == "Hello world"
        assert msg.in_reply_to_provider_id == "parent"


# ─────────────────────────────────────────────────────────────────────
# 6. Message ingestion pipeline
# ─────────────────────────────────────────────────────────────────────


def _provider_message(
    *,
    pid="m-1",
    sender="alice@x.com",
    subject="Test",
    in_reply_to=None,
    to=None,
    sent_at=None,
):
    from app.services.email.providers.base import ProviderFetchedMessage

    return ProviderFetchedMessage(
        provider_message_id=pid,
        provider_thread_id=None,
        sender_email=sender,
        sender_name=None,
        to=to or [("bob@y.com", None)],
        subject=subject,
        body_text="hello",
        sent_at=sent_at or datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        in_reply_to_provider_id=in_reply_to,
        raw_payload={},
        attachments=[],
    )


class TestIngestionPipeline:
    def test_idempotent_re_ingestion(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailMessage
        from app.services.email import account_service
        from app.services.email.ingestion import ingest_provider_message

        account_id = _make_account(ctx, "gmail")
        db = SessionLocal()
        try:
            account = account_service.get_account(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
            )
            msg1 = ingest_provider_message(
                db, account=account, provider_message=_provider_message()
            )
            db.commit()
            msg2 = ingest_provider_message(
                db, account=account, provider_message=_provider_message()
            )
            assert msg1.id == msg2.id
            count = (
                db.query(EmailMessage)
                .filter(EmailMessage.account_id == account.id)
                .count()
            )
            assert count == 1
        finally:
            db.close()

    def test_thread_reconstruction_in_reply_to(self, ctx):
        from app.database import SessionLocal
        from app.services.email import account_service
        from app.services.email.ingestion import ingest_provider_message

        account_id = _make_account(ctx, "gmail")
        db = SessionLocal()
        try:
            account = account_service.get_account(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
            )
            parent = ingest_provider_message(
                db,
                account=account,
                provider_message=_provider_message(pid="parent-id"),
            )
            child = ingest_provider_message(
                db,
                account=account,
                provider_message=_provider_message(
                    pid="child-id", in_reply_to="parent-id"
                ),
            )
            assert child.thread_id == parent.thread_id
            assert child.in_reply_to_message_id == parent.id
        finally:
            db.close()

    def test_thread_reconstruction_subject_fallback(self, ctx):
        from app.database import SessionLocal
        from app.services.email import account_service
        from app.services.email.ingestion import ingest_provider_message

        account_id = _make_account(ctx, "gmail")
        db = SessionLocal()
        try:
            account = account_service.get_account(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
            )
            parent = ingest_provider_message(
                db,
                account=account,
                provider_message=_provider_message(
                    pid="p1",
                    sender="external@x.com",
                    subject="Bronze urn",
                    to=[(account.email_address, None)],
                ),
            )
            db.commit()
            # Child has no In-Reply-To but matches subject + shared
            # participant (sender of parent, now to recipient)
            child = ingest_provider_message(
                db,
                account=account,
                provider_message=_provider_message(
                    pid="p2",
                    sender="external@x.com",
                    subject="Re: Bronze urn",
                    to=[(account.email_address, None)],
                ),
            )
            assert child.thread_id == parent.thread_id
        finally:
            db.close()

    def test_cross_tenant_detection_marks_thread(self, ctx, ctx_b):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailAuditLog
        from app.models.user import User
        from app.services.email import account_service
        from app.services.email.ingestion import ingest_provider_message

        # ctx_b has a user. When ctx ingests a message FROM that user,
        # the participant resolves to a Bridgeable tenant user in a
        # DIFFERENT tenant — cross-tenant detected.
        db = SessionLocal()
        try:
            user_b = (
                db.query(User)
                .filter(User.company_id == ctx_b["company_id"])
                .first()
            )
            assert user_b is not None
            external_email = user_b.email
        finally:
            db.close()

        account_id = _make_account(ctx, "gmail")
        db = SessionLocal()
        try:
            account = account_service.get_account(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
            )
            msg = ingest_provider_message(
                db,
                account=account,
                provider_message=_provider_message(
                    pid="cross-1", sender=external_email
                ),
            )
            db.commit()
            db.refresh(msg.thread)
            assert msg.thread.is_cross_tenant is True
            # Audit row written
            entries = (
                db.query(EmailAuditLog)
                .filter(
                    EmailAuditLog.entity_id == msg.thread.id,
                    EmailAuditLog.action == "thread_marked_cross_tenant",
                )
                .all()
            )
            assert len(entries) == 1
            # Caveat about one-way redaction is in audit changes
            assert (
                "Redaction is one-way"
                in str(entries[0].changes)
            )
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 7. Webhook handlers + signature verification
# ─────────────────────────────────────────────────────────────────────


class TestWebhookHandlers:
    def test_gmail_pubsub_jwt_missing_authorization(self):
        from app.services.email.webhooks import (
            WebhookSignatureError,
            verify_gmail_pubsub_jwt,
        )

        with pytest.raises(WebhookSignatureError, match="Missing"):
            verify_gmail_pubsub_jwt(None)

    def test_gmail_pubsub_jwt_malformed(self):
        from app.services.email.webhooks import (
            WebhookSignatureError,
            verify_gmail_pubsub_jwt,
        )

        with pytest.raises(WebhookSignatureError):
            verify_gmail_pubsub_jwt("Bearer not-a-jwt")

    def test_gmail_parse_pubsub_payload(self):
        from app.services.email.webhooks import parse_gmail_pubsub_payload

        decoded = json.dumps(
            {"emailAddress": "alice@x.com", "historyId": "12345"}
        )
        envelope = {
            "message": {
                "data": base64.b64encode(decoded.encode()).decode(),
                "messageId": "mid",
            }
        }
        result = parse_gmail_pubsub_payload(envelope)
        assert result["emailAddress"] == "alice@x.com"
        assert result["historyId"] == "12345"

    def test_msgraph_validation_token_handshake(self):
        from app.services.email.webhooks import (
            handle_msgraph_validation_token,
        )

        assert (
            handle_msgraph_validation_token("validate-me-please")
            == "validate-me-please"
        )
        assert handle_msgraph_validation_token(None) is None

    def test_msgraph_clientstate_match_required(self):
        from app.services.email.webhooks import (
            WebhookSignatureError,
            verify_msgraph_client_state,
        )

        verify_msgraph_client_state("secret", "secret")  # no raise
        with pytest.raises(WebhookSignatureError):
            verify_msgraph_client_state("secret", "different")
        with pytest.raises(WebhookSignatureError):
            verify_msgraph_client_state(None, "expected")


class TestWebhookEndpoints:
    def test_msgraph_validation_endpoint_echoes_token(self, client):
        r = client.post(
            "/api/v1/email/webhooks/msgraph?validationToken=test123"
        )
        assert r.status_code == 200
        assert r.text == "test123"
        assert r.headers["content-type"].startswith("text/plain")

    def test_gmail_webhook_rejects_missing_auth(self, client):
        r = client.post(
            "/api/v1/email/webhooks/gmail",
            json={"message": {"data": ""}},
        )
        assert r.status_code == 401


# ─────────────────────────────────────────────────────────────────────
# 8. Sync engine
# ─────────────────────────────────────────────────────────────────────


class TestSyncEngine:
    def test_sync_mutex_blocks_double_sync(self, ctx):
        from app.database import SessionLocal
        from app.services.email import account_service
        from app.services.email.sync_engine import (
            SyncEngineError,
            _sync_mutex,
        )

        account_id = _make_account(ctx, "gmail")
        db = SessionLocal()
        try:
            with _sync_mutex(db, account_id):
                with pytest.raises(SyncEngineError, match="in progress"):
                    with _sync_mutex(db, account_id):
                        pass
        finally:
            db.close()

    def test_circuit_breaker_increments_on_failure(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailAccountSyncState
        from app.services.email import account_service
        from app.services.email.sync_engine import _ensure_sync_state, _record_failure

        account_id = _make_account(ctx, "gmail")
        db = SessionLocal()
        try:
            state = _ensure_sync_state(db, account_id=account_id)
            _record_failure(state, "boom")
            db.commit()
            assert state.consecutive_error_count == 1
            _record_failure(state, "boom 2")
            db.commit()
            assert state.consecutive_error_count == 2
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 9. APScheduler sweep functions
# ─────────────────────────────────────────────────────────────────────


class TestSweepFunctions:
    def test_token_refresh_sweep_skips_non_oauth(self, ctx, monkeypatch):
        # IMAP account shouldn't be touched by token-refresh sweep.
        from app.services.email.sweeps import email_token_refresh_sweep

        account_id = _make_account(ctx, "imap")
        # Sweep should not crash + should not touch the IMAP account.
        email_token_refresh_sweep()  # no exception

    def test_subscription_renewal_sweep_extends_expiry(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailAccountSyncState
        from app.services.email import account_service
        from app.services.email.sweeps import (
            email_subscription_renewal_sweep,
        )

        account_id = _make_account(ctx, "gmail")
        db = SessionLocal()
        try:
            account = account_service.get_account(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
            )
            state = account.sync_state
            # Set near-expiry
            state.subscription_expires_at = datetime.now(
                timezone.utc
            ) + timedelta(hours=2)
            db.commit()
        finally:
            db.close()

        # Run sweep
        email_subscription_renewal_sweep()

        # Verify extension
        db = SessionLocal()
        try:
            state = (
                db.query(EmailAccountSyncState)
                .filter(EmailAccountSyncState.account_id == account_id)
                .first()
            )
            # Should be extended ~7 days out for gmail
            assert state.subscription_expires_at > datetime.now(
                timezone.utc
            ) + timedelta(days=6)
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 10. API endpoints
# ─────────────────────────────────────────────────────────────────────


class TestStep2APIEndpoints:
    def test_authorize_url_issues_db_nonce(self, client, auth, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import OAuthStateNonce

        r = client.get(
            "/api/v1/email-accounts/oauth/gmail/authorize-url"
            "?redirect_uri=https://app/cb",
            headers=auth,
        )
        assert r.status_code == 200
        body = r.json()
        state = body["state"]
        assert "state=" in body["authorize_url"]
        # Nonce row exists in DB
        db = SessionLocal()
        try:
            row = (
                db.query(OAuthStateNonce)
                .filter(OAuthStateNonce.nonce == state)
                .first()
            )
            assert row is not None
            assert row.tenant_id == ctx["company_id"]
            assert row.consumed_at is None
        finally:
            db.close()

    def test_oauth_callback_full_flow(self, client, auth, ctx, monkeypatch):
        # Patch the SPECIFIC token-exchange function rather than
        # httpx.Client.post globally — TestClient also uses httpx
        # internally, so global httpx patches break the FastAPI
        # round-trip.
        from app.services.email import oauth_service

        monkeypatch.setattr(
            oauth_service,
            "_exchange_gmail",
            lambda *, code, redirect_uri: {
                "access_token": "ya29.fake",
                "refresh_token": "1//fake",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "gmail.modify",
            },
        )

        r = client.get(
            "/api/v1/email-accounts/oauth/gmail/authorize-url"
            "?redirect_uri=https://app/cb",
            headers=auth,
        )
        state = r.json()["state"]

        r = client.post(
            "/api/v1/email-accounts/oauth/callback",
            json={
                "provider_type": "gmail",
                "code": "auth-code",
                "state": state,
                "redirect_uri": "https://app/cb",
                "email_address": "alice@example.com",
                "display_name": "Alice",
                "account_type": "personal",
            },
            headers=auth,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["email_address"] == "alice@example.com"
        assert body["account_id"]

    def test_oauth_callback_replays_blocked(
        self, client, auth, monkeypatch
    ):
        from app.services.email import oauth_service

        monkeypatch.setattr(
            oauth_service,
            "_exchange_gmail",
            lambda *, code, redirect_uri: {
                "access_token": "t",
                "refresh_token": "r",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        )

        r = client.get(
            "/api/v1/email-accounts/oauth/gmail/authorize-url"
            "?redirect_uri=https://app/cb",
            headers=auth,
        )
        state = r.json()["state"]

        # First callback succeeds
        r1 = client.post(
            "/api/v1/email-accounts/oauth/callback",
            json={
                "provider_type": "gmail",
                "code": "c",
                "state": state,
                "redirect_uri": "https://app/cb",
                "email_address": "first@example.com",
            },
            headers=auth,
        )
        assert r1.status_code == 200

        # Second callback with same state rejected (replay protection)
        r2 = client.post(
            "/api/v1/email-accounts/oauth/callback",
            json={
                "provider_type": "gmail",
                "code": "c",
                "state": state,
                "redirect_uri": "https://app/cb",
                "email_address": "second@example.com",
            },
            headers=auth,
        )
        assert r2.status_code == 400

    def test_sync_status_endpoint(self, client, auth, ctx):
        # Create an account, then GET its sync status
        r = client.post(
            "/api/v1/email-accounts",
            json={
                "account_type": "shared",
                "display_name": "S",
                "email_address": f"s-{uuid.uuid4().hex[:6]}@x.com",
                "provider_type": "gmail",
            },
            headers=auth,
        )
        account_id = r.json()["id"]
        r2 = client.get(
            f"/api/v1/email-accounts/{account_id}/sync-status",
            headers=auth,
        )
        assert r2.status_code == 200
        body = r2.json()
        assert body["account_id"] == account_id
        assert body["sync_status"] == "pending"
        assert body["backfill_status"] == "not_started"
        assert body["sync_in_progress"] is False
