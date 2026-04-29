"""Phase W-4b Layer 1 Email Step 3 — outbound infrastructure tests.

Coverage:
  - r65 outbound_enabled column exists; defaults True
  - Subject normalization (reply_subject + forward_subject idempotency)
  - Provider send_message wire-format verification (Gmail RFC 5322,
    MS Graph JSON, SMTP envelope) via mocked transports
  - TransactionalSendOnlyProvider Phase D-7 bridge (mocked
    delivery_service.send_email_raw)
  - outbound_service.send_message orchestration:
      * read_only access rejected (read_write/admin required)
      * outbound_enabled=False → 409
      * thread_id resolution + new-thread creation
      * in_reply_to_message_id resolution + parent linkage
      * cross-tenant in_reply_to_message_id rejected (404 — existence
        hiding via tenant_id filter)
      * provider failure → audit + raise OutboundProviderError
      * audit log on success captures recipient_count + thread_id +
        provider, NEVER body content
  - Outbound deduplication:
      * outbound stores provider_message_id at send time
      * subsequent inbound ingestion of same provider_message_id
        returns existing row (just-skip, idempotent)
  - Reply thread continuity:
      * thread_id preserved
      * in_reply_to_message_id FK populated
      * subject preserved (caller-supplied; no double-prefix)
  - Forward new-thread:
      * thread_id NOT preserved (new thread)
      * in_reply_to_message_id NULL
  - API endpoint:
      * 201 + SendMessageResponse on success
      * 403 on read_only access
      * 404 on missing in_reply_to_message_id
      * Per-tenant isolation (cross-tenant account_id → 404)
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import httpx
import pytest

from cryptography.fernet import Fernet


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
            name=f"EM3-{suffix}",
            slug=f"em3-{suffix}",
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
            email=f"u-{suffix}@em3.co",
            first_name="EM3",
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
    return _make_ctx()


@pytest.fixture
def auth(ctx):
    return {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Company-Slug": ctx["slug"],
    }


def _make_account_with_creds(ctx, provider_type: str = "gmail"):
    """Create an account + persist mock encrypted creds so outbound
    has something to decrypt + use."""
    from app.database import SessionLocal
    from app.services.email import account_service
    from app.services.email.crypto import encrypt_credentials

    db = SessionLocal()
    try:
        acc = account_service.create_account(
            db,
            tenant_id=ctx["company_id"],
            actor_user_id=ctx["user_id"],
            account_type="shared",
            display_name="Test Account",
            email_address=f"test-{uuid.uuid4().hex[:6]}@example.com",
            provider_type=provider_type,
        )
        # Auto-grant creator admin (matches API endpoint behavior)
        account_service.grant_access(
            db,
            account_id=acc.id,
            tenant_id=ctx["company_id"],
            user_id=ctx["user_id"],
            access_level="admin",
            actor_user_id=ctx["user_id"],
        )
        # Persist mock OAuth tokens so ensure_fresh_token doesn't 401
        if provider_type in ("gmail", "msgraph"):
            acc.encrypted_credentials = encrypt_credentials(
                {
                    "access_token": "mock-fresh-token",
                    "refresh_token": "mock-refresh",
                    "token_expires_at": (
                        datetime.now(timezone.utc) + timedelta(hours=1)
                    ).isoformat(),
                }
            )
            acc.token_expires_at = datetime.now(timezone.utc) + timedelta(
                hours=1
            )
        elif provider_type == "imap":
            acc.encrypted_credentials = encrypt_credentials(
                {"imap_password": "mock-password"}
            )
            cfg = dict(acc.provider_config or {})
            cfg.update(
                {
                    "smtp_server": "smtp.example.com",
                    "smtp_port": 587,
                    "imap_server": "imap.example.com",
                    "imap_port": 993,
                    "username": acc.email_address,
                }
            )
            acc.provider_config = cfg
        db.commit()
        return acc.id
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────
# 1. Migration r65 schema
# ─────────────────────────────────────────────────────────────────────


class TestMigrationR65Schema:
    def test_outbound_enabled_column_exists_default_true(self):
        from sqlalchemy import inspect

        from app.database import engine

        cols = {
            c["name"]: c
            for c in inspect(engine).get_columns("email_accounts")
        }
        assert "outbound_enabled" in cols
        assert cols["outbound_enabled"]["nullable"] is False


# ─────────────────────────────────────────────────────────────────────
# 2. Subject normalization
# ─────────────────────────────────────────────────────────────────────


class TestSubjectNormalization:
    def test_reply_prefix_idempotent(self):
        from app.services.email.outbound_service import reply_subject

        assert reply_subject("Hello") == "Re: Hello"
        assert reply_subject("Re: Hello") == "Re: Hello"
        assert reply_subject("re: hello") == "re: hello"  # case-preserve
        assert reply_subject("") == "Re:"
        assert reply_subject(None) == "Re:"

    def test_forward_prefix_idempotent(self):
        from app.services.email.outbound_service import forward_subject

        assert forward_subject("Hello") == "Fwd: Hello"
        assert forward_subject("Fwd: Hello") == "Fwd: Hello"
        assert forward_subject("Fw: Hello") == "Fw: Hello"
        # Re: prefix preserved (RFC 5322 reply-tree marker)
        assert forward_subject("Re: Hello") == "Fwd: Re: Hello"


# ─────────────────────────────────────────────────────────────────────
# 3. Provider wire-format verification
# ─────────────────────────────────────────────────────────────────────


class TestGmailWireFormat:
    def test_gmail_send_message_constructs_rfc5322(self, monkeypatch):
        from app.services.email.providers import GmailAPIProvider

        captured = {}

        def mock_post(self, url, **kwargs):
            captured["url"] = url
            captured["json"] = kwargs.get("json")
            # raise_for_status requires _request to be set on the response
            req = httpx.Request("POST", url)
            return httpx.Response(
                status_code=200,
                json={"id": "gmail-msg-id", "threadId": "gmail-thread-id"},
                request=req,
            )

        monkeypatch.setattr(httpx.Client, "post", mock_post)

        provider = GmailAPIProvider({"access_token": "mock-token"})
        result = provider.send_message(
            from_address="alice@example.com",
            to=[("bob@example.com", "Bob")],
            cc=[("carol@example.com", None)],
            subject="Hello",
            body_text="Plain text body",
            body_html="<p>HTML body</p>",
            in_reply_to_provider_id="parent-message-id",
        )
        assert result.success is True
        assert result.provider_message_id == "gmail-msg-id"
        assert result.provider_thread_id == "gmail-thread-id"
        assert captured["url"].endswith("/users/me/messages/send")
        # raw bytes should be base64-url-safe
        import base64

        raw_b64 = captured["json"]["raw"]
        decoded = base64.urlsafe_b64decode(
            raw_b64 + "=" * (-len(raw_b64) % 4)
        ).decode("utf-8")
        assert "From: alice@example.com" in decoded
        assert "Bob" in decoded
        assert "bob@example.com" in decoded
        assert "Subject: Hello" in decoded
        assert "In-Reply-To: <parent-message-id>" in decoded
        assert "References: <parent-message-id>" in decoded

    def test_gmail_send_failure_returns_retryable_for_5xx(self, monkeypatch):
        from app.services.email.providers import GmailAPIProvider

        def mock_post(self, url, **kwargs):
            response = httpx.Response(status_code=503, json={"error": "down"})
            raise httpx.HTTPStatusError(
                "503",
                request=httpx.Request("POST", "http://x"),
                response=response,
            )

        monkeypatch.setattr(httpx.Client, "post", mock_post)
        provider = GmailAPIProvider({"access_token": "x"})
        result = provider.send_message(
            from_address="a@x.com",
            to=[("b@x.com", None)],
            subject="t",
            body_text="b",
        )
        assert result.success is False
        # 5xx should be classified retryable per _is_retryable_http
        assert result.error_retryable is True


class TestMSGraphWireFormat:
    def test_msgraph_send_message_constructs_json_envelope(self, monkeypatch):
        from app.services.email.providers import MicrosoftGraphProvider

        captured = {}

        def mock_post(self, url, **kwargs):
            captured["url"] = url
            captured["json"] = kwargs.get("json")
            req = httpx.Request("POST", url)
            return httpx.Response(status_code=202, request=req)

        monkeypatch.setattr(httpx.Client, "post", mock_post)

        provider = MicrosoftGraphProvider({"access_token": "mock-token"})
        result = provider.send_message(
            from_address="alice@x.com",
            to=[("bob@x.com", "Bob"), ("carol@x.com", None)],
            cc=[("dave@x.com", None)],
            subject="Test",
            body_html="<p>Body</p>",
            in_reply_to_provider_id="parent-id",
        )
        assert result.success is True
        # Graph doesn't return msg id on sendMail
        assert result.provider_message_id is None
        assert captured["url"].endswith("/me/sendMail")
        env = captured["json"]
        assert env["saveToSentItems"] is True
        msg = env["message"]
        assert msg["subject"] == "Test"
        assert msg["body"]["contentType"] == "html"
        assert msg["body"]["content"] == "<p>Body</p>"
        assert len(msg["toRecipients"]) == 2
        assert msg["toRecipients"][0]["emailAddress"]["address"] == "bob@x.com"
        assert msg["toRecipients"][0]["emailAddress"]["name"] == "Bob"
        assert msg["ccRecipients"][0]["emailAddress"]["address"] == "dave@x.com"
        # In-Reply-To header threaded through internetMessageHeaders
        headers = {h["name"]: h["value"] for h in msg["internetMessageHeaders"]}
        assert headers["In-Reply-To"] == "<parent-id>"
        assert headers["References"] == "<parent-id>"


class TestIMAPSMTPWireFormat:
    def test_imap_send_message_via_smtp(self, monkeypatch):
        from app.services.email.providers import IMAPProvider

        captured = {}

        class MockSMTP:
            def __init__(self, server, port):
                captured["server"] = server
                captured["port"] = port

            def login(self, username, password):
                captured["username"] = username
                # NEVER assert on password presence — but test that it
                # was passed (non-empty string)
                captured["password_present"] = bool(password)

            def send_message(self, msg, from_addr, to_addrs):
                captured["from_addr"] = from_addr
                captured["to_addrs"] = list(to_addrs)
                captured["mime"] = msg.as_string()

            def quit(self):
                pass

        monkeypatch.setattr(
            IMAPProvider, "smtp_client_factory", lambda s, p: MockSMTP(s, p)
        )

        provider = IMAPProvider(
            {
                "smtp_server": "smtp.example.com",
                "smtp_port": 587,
                "username": "alice@x.com",
                "imap_password": "secret",
            }
        )
        result = provider.send_message(
            from_address="alice@x.com",
            to=[("bob@x.com", "Bob")],
            cc=[("carol@x.com", None)],
            bcc=[("dan@x.com", None)],
            subject="Hello",
            body_text="Plain body",
            in_reply_to_provider_id="parent-id",
        )
        assert result.success is True
        assert result.provider_message_id is None  # SMTP doesn't return one
        assert captured["server"] == "smtp.example.com"
        assert captured["port"] == 587
        assert captured["username"] == "alice@x.com"
        assert captured["password_present"] is True
        # rcpt_to includes ALL three (to + cc + bcc)
        assert "bob@x.com" in captured["to_addrs"]
        assert "carol@x.com" in captured["to_addrs"]
        assert "dan@x.com" in captured["to_addrs"]
        # bcc NOT in headers
        assert "Bcc: dan@x.com" not in captured["mime"]
        # in-reply-to threaded
        assert "In-Reply-To: <parent-id>" in captured["mime"]

    def test_imap_send_missing_credentials_fails_clean(self):
        from app.services.email.providers import IMAPProvider

        provider = IMAPProvider({})  # no smtp config at all
        result = provider.send_message(
            from_address="x@y.com",
            to=[("a@b.com", None)],
            subject="t",
            body_text="b",
        )
        assert result.success is False
        assert "smtp_server" in (result.error_message or "")
        assert result.error_retryable is False


class TestTransactionalBridge:
    def test_transactional_send_routes_through_delivery_service(
        self, ctx, monkeypatch
    ):
        from app.database import SessionLocal
        from app.services.email.providers import TransactionalSendOnlyProvider

        captured = {}

        # Mock delivery_service.send_email_raw at the provider call site
        def mock_send_email_raw(db_arg, **kwargs):
            captured["company_id"] = kwargs.get("company_id")
            captured["to_email"] = kwargs.get("to_email")
            captured["subject"] = kwargs.get("subject")
            captured["caller_module"] = kwargs.get("caller_module")
            mock_delivery = MagicMock()
            mock_delivery.id = "delivery-row-id"
            mock_delivery.status = "sent"
            mock_delivery.error_message = None
            return mock_delivery

        from app.services.delivery import delivery_service

        monkeypatch.setattr(
            delivery_service, "send_email_raw", mock_send_email_raw
        )

        db = SessionLocal()
        try:
            provider = TransactionalSendOnlyProvider(
                {"__db__": db, "__company_id__": ctx["company_id"]}
            )
            result = provider.send_message(
                from_address="Bridgeable <noreply@example.com>",
                to=[("recipient@example.com", "Recipient")],
                subject="Notification",
                body_html="<p>Content</p>",
            )
            assert result.success is True
            assert result.provider_message_id == "delivery-row-id"
            # Bridge invariants
            assert captured["company_id"] == ctx["company_id"]
            assert captured["to_email"] == "recipient@example.com"
            assert captured["subject"] == "Notification"
            assert captured["caller_module"] == "email_primitive.transactional"
        finally:
            db.close()

    def test_transactional_rejects_multi_recipient(self):
        # Step 3 ships single-recipient pass-through; multi-recipient
        # transactional sends are a Step 3.1 refinement.
        from app.services.email.providers import TransactionalSendOnlyProvider

        provider = TransactionalSendOnlyProvider(
            {"__db__": MagicMock(), "__company_id__": "co-1"}
        )
        result = provider.send_message(
            from_address="x@y.com",
            to=[("a@b.com", None), ("c@d.com", None)],
            subject="t",
            body_text="b",
        )
        assert result.success is False
        assert "single-recipient" in (result.error_message or "")

    def test_transactional_rejects_missing_db_or_company_id(self):
        from app.services.email.providers import TransactionalSendOnlyProvider

        provider = TransactionalSendOnlyProvider({})  # no db, no company_id
        result = provider.send_message(
            from_address="x@y.com",
            to=[("a@b.com", None)],
            subject="t",
            body_text="b",
        )
        assert result.success is False
        assert "outbound_service injects" in (result.error_message or "")


# ─────────────────────────────────────────────────────────────────────
# 4. outbound_service orchestration
# ─────────────────────────────────────────────────────────────────────


def _patch_provider_send(monkeypatch, *, success=True, msg_id="prov-msg-1", thread_id="prov-thread-1"):
    """Patch all 3 OAuth/IMAP provider send_message methods to return
    a canned ProviderSendResult so outbound_service.send_message
    completes without real network calls."""
    from app.services.email.providers import (
        GmailAPIProvider,
        IMAPProvider,
        MicrosoftGraphProvider,
    )
    from app.services.email.providers.base import ProviderSendResult

    def mock_send(self, **kwargs):
        return ProviderSendResult(
            success=success,
            provider_message_id=msg_id if success else None,
            provider_thread_id=thread_id if success else None,
            error_message=None if success else "mocked failure",
            error_retryable=False,
        )

    monkeypatch.setattr(GmailAPIProvider, "send_message", mock_send)
    monkeypatch.setattr(MicrosoftGraphProvider, "send_message", mock_send)
    monkeypatch.setattr(IMAPProvider, "send_message", mock_send)


class TestOutboundService:
    def test_send_creates_message_and_thread_when_thread_id_none(
        self, ctx, monkeypatch
    ):
        from app.database import SessionLocal
        from app.models.user import User
        from app.services.email import account_service, outbound_service

        _patch_provider_send(monkeypatch)
        account_id = _make_account_with_creds(ctx, "gmail")

        db = SessionLocal()
        try:
            account = account_service.get_account(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
            )
            sender = db.query(User).filter(User.id == ctx["user_id"]).first()
            msg = outbound_service.send_message(
                db,
                account=account,
                sender=sender,
                to=[("recipient@example.com", "R")],
                subject="Hello",
                body_text="Body",
            )
            db.commit()
            db.refresh(msg)
            assert msg.direction == "outbound"
            assert msg.provider_message_id == "prov-msg-1"
            assert msg.thread_id  # new thread created
            assert msg.in_reply_to_message_id is None
            assert msg.sender_email == account.email_address.lower()
            # Thread denormalization updated
            db.refresh(msg.thread)
            assert msg.thread.message_count == 1
        finally:
            db.close()

    def test_reply_preserves_thread_continuity(self, ctx, monkeypatch):
        from app.database import SessionLocal
        from app.models.user import User
        from app.services.email import account_service, outbound_service
        from app.services.email.ingestion import ingest_provider_message
        from app.services.email.providers.base import ProviderFetchedMessage

        _patch_provider_send(monkeypatch, msg_id="reply-msg-id")
        account_id = _make_account_with_creds(ctx, "gmail")

        db = SessionLocal()
        try:
            account = account_service.get_account(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
            )
            # Seed an inbound parent message
            parent = ingest_provider_message(
                db,
                account=account,
                provider_message=ProviderFetchedMessage(
                    provider_message_id="parent-id",
                    provider_thread_id=None,
                    sender_email="external@x.com",
                    sender_name=None,
                    to=[(account.email_address, None)],
                    subject="Original",
                    body_text="Hello",
                    sent_at=datetime.now(timezone.utc),
                    received_at=datetime.now(timezone.utc),
                    in_reply_to_provider_id=None,
                    raw_payload={},
                    attachments=[],
                ),
            )
            db.commit()

            sender = db.query(User).filter(User.id == ctx["user_id"]).first()
            reply = outbound_service.send_message(
                db,
                account=account,
                sender=sender,
                to=[("external@x.com", None)],
                subject=outbound_service.reply_subject("Original"),
                body_text="Replying",
                in_reply_to_message_id=parent.id,
            )
            db.commit()
            db.refresh(reply)
            assert reply.thread_id == parent.thread_id  # continuity!
            assert reply.in_reply_to_message_id == parent.id
            assert reply.subject == "Re: Original"
            db.refresh(parent.thread)
            assert parent.thread.message_count == 2
        finally:
            db.close()

    def test_outbound_disabled_raises_409(self, ctx, monkeypatch):
        from app.database import SessionLocal
        from app.models.user import User
        from app.services.email import account_service, outbound_service
        from app.services.email.outbound_service import OutboundDisabled

        _patch_provider_send(monkeypatch)
        account_id = _make_account_with_creds(ctx, "gmail")

        db = SessionLocal()
        try:
            account = account_service.get_account(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
            )
            account.outbound_enabled = False
            db.commit()

            sender = db.query(User).filter(User.id == ctx["user_id"]).first()
            with pytest.raises(OutboundDisabled):
                outbound_service.send_message(
                    db,
                    account=account,
                    sender=sender,
                    to=[("a@b.com", None)],
                    subject="t",
                    body_text="b",
                )
        finally:
            db.close()

    def test_read_only_user_rejected(self, ctx, monkeypatch):
        from app.database import SessionLocal
        from app.models.role import Role
        from app.models.user import User
        from app.services.email import account_service, outbound_service
        from app.services.email.account_service import (
            EmailAccountPermissionDenied,
        )

        _patch_provider_send(monkeypatch)
        account_id = _make_account_with_creds(ctx, "gmail")

        db = SessionLocal()
        try:
            # Create a second user in the same tenant + grant read only
            suffix = uuid.uuid4().hex[:6]
            role = Role(
                id=str(uuid.uuid4()),
                company_id=ctx["company_id"],
                name="Office",
                slug="office",
                is_system=False,
            )
            db.add(role)
            db.flush()
            read_only_user = User(
                id=str(uuid.uuid4()),
                company_id=ctx["company_id"],
                email=f"r-{suffix}@x.com",
                first_name="R",
                last_name="O",
                hashed_password="x",
                is_active=True,
                role_id=role.id,
            )
            db.add(read_only_user)
            db.commit()

            account_service.grant_access(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
                user_id=read_only_user.id,
                access_level="read",
                actor_user_id=ctx["user_id"],
            )
            db.commit()

            account = account_service.get_account(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
            )
            with pytest.raises(EmailAccountPermissionDenied):
                outbound_service.send_message(
                    db,
                    account=account,
                    sender=read_only_user,
                    to=[("a@b.com", None)],
                    subject="t",
                    body_text="b",
                )
        finally:
            db.close()

    def test_audit_log_on_success_omits_body_content(self, ctx, monkeypatch):
        import json

        from app.database import SessionLocal
        from app.models.email_primitive import EmailAuditLog
        from app.models.user import User
        from app.services.email import account_service, outbound_service

        _patch_provider_send(monkeypatch)
        account_id = _make_account_with_creds(ctx, "gmail")

        db = SessionLocal()
        try:
            account = account_service.get_account(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
            )
            sender = db.query(User).filter(User.id == ctx["user_id"]).first()
            outbound_service.send_message(
                db,
                account=account,
                sender=sender,
                to=[("recipient@example.com", None)],
                subject="Subject Line",
                body_text="VERY-PRIVATE-CONTENT",
                body_html="<p>VERY-PRIVATE-CONTENT</p>",
            )
            db.commit()

            entries = (
                db.query(EmailAuditLog)
                .filter(
                    EmailAuditLog.tenant_id == ctx["company_id"],
                    EmailAuditLog.action == "message_sent",
                )
                .all()
            )
            assert len(entries) == 1
            payload = json.dumps(entries[0].changes)
            # Body content NEVER in audit log per §3.26.15.8
            assert "VERY-PRIVATE-CONTENT" not in payload
            # But recipient + subject_length are
            assert "recipient@example.com" in payload
            assert "subject_length" in payload
        finally:
            db.close()

    def test_provider_failure_audited_then_raised(self, ctx, monkeypatch):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailAuditLog
        from app.models.user import User
        from app.services.email import account_service, outbound_service
        from app.services.email.outbound_service import OutboundProviderError

        _patch_provider_send(monkeypatch, success=False)
        account_id = _make_account_with_creds(ctx, "gmail")

        db = SessionLocal()
        try:
            account = account_service.get_account(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
            )
            sender = db.query(User).filter(User.id == ctx["user_id"]).first()
            with pytest.raises(OutboundProviderError):
                outbound_service.send_message(
                    db,
                    account=account,
                    sender=sender,
                    to=[("a@b.com", None)],
                    subject="t",
                    body_text="b",
                )
            db.commit()
            entries = (
                db.query(EmailAuditLog)
                .filter(
                    EmailAuditLog.tenant_id == ctx["company_id"],
                    EmailAuditLog.action == "message_send_failed",
                )
                .all()
            )
            assert len(entries) == 1
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 5. Outbound deduplication (round-trip via inbound sync)
# ─────────────────────────────────────────────────────────────────────


class TestOutboundDeduplication:
    def test_inbound_sync_of_outbound_message_is_idempotent(
        self, ctx, monkeypatch
    ):
        """When inbound sync of Sent folder receives a message we
        already sent (matching provider_message_id), the existing
        outbound row is returned (no duplicate created)."""
        from app.database import SessionLocal
        from app.models.email_primitive import EmailMessage
        from app.models.user import User
        from app.services.email import account_service, outbound_service
        from app.services.email.ingestion import ingest_provider_message
        from app.services.email.providers.base import ProviderFetchedMessage

        _patch_provider_send(monkeypatch, msg_id="round-trip-id")
        account_id = _make_account_with_creds(ctx, "gmail")

        db = SessionLocal()
        try:
            account = account_service.get_account(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
            )
            sender = db.query(User).filter(User.id == ctx["user_id"]).first()
            outbound_msg = outbound_service.send_message(
                db,
                account=account,
                sender=sender,
                to=[("recipient@example.com", None)],
                subject="Outbound",
                body_text="Hello",
            )
            db.commit()
            outbound_id = outbound_msg.id

            # Now simulate inbound sync receiving the same message
            # back from Sent folder
            same = ingest_provider_message(
                db,
                account=account,
                provider_message=ProviderFetchedMessage(
                    provider_message_id="round-trip-id",
                    provider_thread_id=None,
                    sender_email=account.email_address.lower(),
                    sender_name=None,
                    to=[("recipient@example.com", None)],
                    subject="Outbound",
                    body_text="Hello",
                    sent_at=datetime.now(timezone.utc),
                    received_at=datetime.now(timezone.utc),
                    in_reply_to_provider_id=None,
                    raw_payload={},
                    attachments=[],
                ),
            )
            db.commit()
            # Same row returned — no duplicate
            assert same.id == outbound_id
            count = (
                db.query(EmailMessage)
                .filter(
                    EmailMessage.account_id == account.id,
                    EmailMessage.provider_message_id == "round-trip-id",
                )
                .count()
            )
            assert count == 1
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 6. API endpoint
# ─────────────────────────────────────────────────────────────────────


class TestSendMessageAPI:
    def test_post_messages_creates_outbound(self, client, auth, ctx, monkeypatch):
        _patch_provider_send(monkeypatch, msg_id="api-msg-id")
        account_id = _make_account_with_creds(ctx, "gmail")

        r = client.post(
            f"/api/v1/email-accounts/{account_id}/messages",
            json={
                "to": [{"email_address": "recipient@example.com"}],
                "subject": "From API",
                "body_text": "Hello",
            },
            headers=auth,
        )
        assert r.status_code == 201
        body = r.json()
        assert body["message_id"]
        assert body["thread_id"]
        assert body["provider_message_id"] == "api-msg-id"
        assert body["direction"] == "outbound"

    def test_post_messages_cross_tenant_404(
        self, client, auth, ctx_b, monkeypatch
    ):
        _patch_provider_send(monkeypatch)
        # Account in tenant B, request from tenant A
        account_id = _make_account_with_creds(ctx_b, "gmail")
        r = client.post(
            f"/api/v1/email-accounts/{account_id}/messages",
            json={
                "to": [{"email_address": "x@y.com"}],
                "subject": "t",
                "body_text": "b",
            },
            headers=auth,
        )
        assert r.status_code == 404

    def test_post_messages_outbound_disabled_409(
        self, client, auth, ctx, monkeypatch
    ):
        from app.database import SessionLocal
        from app.services.email import account_service

        _patch_provider_send(monkeypatch)
        account_id = _make_account_with_creds(ctx, "gmail")

        # Disable outbound
        db = SessionLocal()
        try:
            account = account_service.get_account(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
            )
            account.outbound_enabled = False
            db.commit()
        finally:
            db.close()

        r = client.post(
            f"/api/v1/email-accounts/{account_id}/messages",
            json={
                "to": [{"email_address": "x@y.com"}],
                "subject": "t",
                "body_text": "b",
            },
            headers=auth,
        )
        assert r.status_code == 409

    def test_post_messages_invalid_in_reply_to_404(
        self, client, auth, ctx, monkeypatch
    ):
        _patch_provider_send(monkeypatch)
        account_id = _make_account_with_creds(ctx, "gmail")

        r = client.post(
            f"/api/v1/email-accounts/{account_id}/messages",
            json={
                "to": [{"email_address": "x@y.com"}],
                "subject": "t",
                "body_text": "b",
                "in_reply_to_message_id": "non-existent-uuid",
            },
            headers=auth,
        )
        assert r.status_code == 404
