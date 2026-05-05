"""Calendar Step 2 — OAuth flow + token-management tests.

Covers state nonce issuance + CSRF validation + code exchange + token
refresh + 401 handling. Mocks httpx via MockTransport so wire format
is verifiable without real Google / Microsoft credentials.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
import pytest

from app.database import SessionLocal
from app.models import Company, Role, User
from app.models.calendar_primitive import CalendarAccount
from app.models.email_primitive import OAuthStateNonce
from app.services.calendar import oauth_service
from app.services.calendar.account_service import (
    CalendarAccountValidation,
)
from app.services.calendar.crypto import decrypt_credentials


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture(autouse=True)
def encryption_key_set():
    """Step 2 OAuth tests require CREDENTIAL_ENCRYPTION_KEY set."""
    if not os.environ.get("CREDENTIAL_ENCRYPTION_KEY"):
        from cryptography.fernet import Fernet

        os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
        # Reset cached fernet so the new key takes effect.
        oauth_service.encrypt_credentials.__globals__["_get_fernet"].cache_clear()


@pytest.fixture
def tenant(db_session):
    import uuid as _uuid

    co = Company(
        id=str(_uuid.uuid4()),
        name=f"OAuth {_uuid.uuid4().hex[:8]}",
        slug=f"oauth{_uuid.uuid4().hex[:8]}",
        vertical="manufacturing",
    )
    db_session.add(co)
    db_session.flush()
    return co


@pytest.fixture
def admin_user(db_session, tenant):
    import uuid as _uuid

    role = Role(
        id=str(_uuid.uuid4()),
        company_id=tenant.id,
        name="Admin",
        slug="admin",
        is_system=True,
    )
    db_session.add(role)
    db_session.flush()

    user = User(
        id=str(_uuid.uuid4()),
        email=f"oa-{_uuid.uuid4().hex[:8]}@oa.test",
        hashed_password="x",
        first_name="OA",
        last_name="User",
        company_id=tenant.id,
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def oauth_account(db_session, tenant, admin_user):
    import uuid as _uuid

    acc = CalendarAccount(
        id=str(_uuid.uuid4()),
        tenant_id=tenant.id,
        account_type="personal",
        display_name="OAuth Test",
        primary_email_address=f"oauth-{_uuid.uuid4().hex[:8]}@oauthtest.test",
        provider_type="google_calendar",
        created_by_user_id=admin_user.id,
    )
    db_session.add(acc)
    db_session.flush()
    return acc


# ─────────────────────────────────────────────────────────────────────
# State nonce CSRF
# ─────────────────────────────────────────────────────────────────────


class TestStateNonce:
    def test_issue_nonce_creates_oauth_state_nonces_row(
        self, db_session, tenant, admin_user
    ):
        nonce = oauth_service.issue_state_nonce(
            db_session,
            tenant_id=tenant.id,
            user_id=admin_user.id,
            provider_type="google_calendar",
            redirect_uri="http://localhost:5173/settings/calendar/oauth-callback",
        )
        assert isinstance(nonce, str)
        assert len(nonce) > 32  # token_urlsafe(32) yields ~43 chars
        row = (
            db_session.query(OAuthStateNonce)
            .filter(OAuthStateNonce.nonce == nonce)
            .first()
        )
        assert row is not None
        assert row.consumed_at is None
        assert row.expires_at > datetime.now(timezone.utc)

    def test_issue_rejects_invalid_provider_type(
        self, db_session, tenant, admin_user
    ):
        with pytest.raises(CalendarAccountValidation):
            oauth_service.issue_state_nonce(
                db_session,
                tenant_id=tenant.id,
                user_id=admin_user.id,
                provider_type="local",  # local doesn't use OAuth
                redirect_uri="http://localhost",
            )

    def test_validate_consumes_nonce(self, db_session, tenant, admin_user):
        nonce = oauth_service.issue_state_nonce(
            db_session,
            tenant_id=tenant.id,
            user_id=admin_user.id,
            provider_type="msgraph",
            redirect_uri="http://localhost",
        )
        oauth_service.validate_and_consume_state_nonce(
            db_session,
            nonce=nonce,
            tenant_id=tenant.id,
            user_id=admin_user.id,
            provider_type="msgraph",
        )
        # Second call raises (single-use replay protection).
        with pytest.raises(oauth_service.OAuthStateInvalid):
            oauth_service.validate_and_consume_state_nonce(
                db_session,
                nonce=nonce,
                tenant_id=tenant.id,
                user_id=admin_user.id,
                provider_type="msgraph",
            )

    def test_validate_rejects_tenant_mismatch(
        self, db_session, tenant, admin_user
    ):
        nonce = oauth_service.issue_state_nonce(
            db_session,
            tenant_id=tenant.id,
            user_id=admin_user.id,
            provider_type="google_calendar",
            redirect_uri="http://localhost",
        )
        with pytest.raises(oauth_service.OAuthStateInvalid):
            oauth_service.validate_and_consume_state_nonce(
                db_session,
                nonce=nonce,
                tenant_id="different-tenant-id",
                user_id=admin_user.id,
                provider_type="google_calendar",
            )

    def test_validate_rejects_expired(self, db_session, tenant, admin_user):
        nonce = oauth_service.issue_state_nonce(
            db_session,
            tenant_id=tenant.id,
            user_id=admin_user.id,
            provider_type="google_calendar",
            redirect_uri="http://localhost",
        )
        # Force expiry.
        row = (
            db_session.query(OAuthStateNonce)
            .filter(OAuthStateNonce.nonce == nonce)
            .first()
        )
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db_session.flush()
        with pytest.raises(oauth_service.OAuthStateInvalid):
            oauth_service.validate_and_consume_state_nonce(
                db_session,
                nonce=nonce,
                tenant_id=tenant.id,
                user_id=admin_user.id,
                provider_type="google_calendar",
            )


# ─────────────────────────────────────────────────────────────────────
# Authorize URL builder
# ─────────────────────────────────────────────────────────────────────


class TestAuthorizeUrl:
    def test_google_authorize_url_includes_canonical_scopes(self):
        url = oauth_service.build_authorize_url(
            provider_type="google_calendar",
            state="abc",
            redirect_uri="http://localhost/callback",
        )
        assert "accounts.google.com" in url
        assert "calendar.events" in url
        assert "calendar.readonly" in url
        assert "state=abc" in url
        assert "access_type=offline" in url

    def test_msgraph_authorize_url_includes_canonical_scopes(self):
        url = oauth_service.build_authorize_url(
            provider_type="msgraph",
            state="abc",
            redirect_uri="http://localhost/callback",
        )
        assert "login.microsoftonline.com" in url
        assert "Calendars.ReadWrite" in url
        assert "offline_access" in url

    def test_local_provider_rejected_for_authorize_url(self):
        with pytest.raises(CalendarAccountValidation):
            oauth_service.build_authorize_url(
                provider_type="local",
                state="abc",
                redirect_uri="http://localhost",
            )


# ─────────────────────────────────────────────────────────────────────
# Token exchange + refresh (mocked httpx)
# ─────────────────────────────────────────────────────────────────────


def _mock_http_client(transport: httpx.MockTransport):
    """Patch oauth_service._http_client to use a MockTransport."""
    return patch.object(
        oauth_service,
        "_http_client",
        return_value=httpx.Client(transport=transport),
    )


class TestTokenExchange:
    def test_complete_oauth_exchange_persists_encrypted_credentials(
        self, db_session, oauth_account, admin_user
    ):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            assert "oauth2.googleapis.com" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "access_token": "ya29.test_access",
                    "refresh_token": "1//test_refresh",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                    "scope": "calendar.events calendar.readonly",
                },
            )

        transport = httpx.MockTransport(mock_handler)
        with _mock_http_client(transport):
            creds = oauth_service.complete_oauth_exchange(
                db_session,
                account=oauth_account,
                code="auth_code_123",
                redirect_uri="http://localhost",
                actor_user_id=admin_user.id,
            )

        assert creds["access_token"] == "ya29.test_access"
        assert creds["refresh_token"] == "1//test_refresh"

        db_session.flush()
        db_session.refresh(oauth_account)
        assert oauth_account.encrypted_credentials  # not None / empty
        assert oauth_account.token_expires_at is not None
        assert oauth_account.last_credential_op == "oauth_complete"

        # Decrypt + verify shape.
        stored = decrypt_credentials(oauth_account.encrypted_credentials)
        assert stored["access_token"] == "ya29.test_access"

    def test_refresh_token_updates_credentials(
        self, db_session, oauth_account, admin_user
    ):
        # Seed initial creds.
        from app.services.calendar.crypto import encrypt_credentials

        old_creds = {
            "access_token": "old_token",
            "refresh_token": "1//refresh_test",
            "token_expires_at": (
                datetime.now(timezone.utc) - timedelta(minutes=5)
            ).isoformat(),
            "token_type": "Bearer",
            "scope": "calendar.events",
        }
        oauth_account.encrypted_credentials = encrypt_credentials(old_creds)
        oauth_account.token_expires_at = datetime.now(
            timezone.utc
        ) - timedelta(minutes=5)
        db_session.flush()

        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "access_token": "new_access_token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            )

        transport = httpx.MockTransport(mock_handler)
        with _mock_http_client(transport):
            new_creds = oauth_service.refresh_token(
                db_session,
                account=oauth_account,
                actor_user_id=admin_user.id,
            )

        assert new_creds["access_token"] == "new_access_token"
        # Refresh token preserved when provider doesn't return a new one.
        assert new_creds["refresh_token"] == "1//refresh_test"
        db_session.refresh(oauth_account)
        assert oauth_account.last_credential_op == "refresh"

    def test_refresh_token_401_raises_oauth_auth_error(
        self, db_session, oauth_account, admin_user
    ):
        from app.services.calendar.crypto import encrypt_credentials

        old_creds = {
            "access_token": "old_token",
            "refresh_token": "expired_refresh",
            "token_expires_at": datetime.now(timezone.utc).isoformat(),
        }
        oauth_account.encrypted_credentials = encrypt_credentials(old_creds)
        db_session.flush()

        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "invalid_grant"})

        transport = httpx.MockTransport(mock_handler)
        with _mock_http_client(transport):
            with pytest.raises(oauth_service.OAuthAuthError):
                oauth_service.refresh_token(
                    db_session,
                    account=oauth_account,
                    actor_user_id=admin_user.id,
                )

        # Failed-refresh audit row written.
        db_session.refresh(oauth_account)
        assert oauth_account.last_credential_op == "refresh_failed"


class TestEnsureFreshToken:
    def test_returns_existing_token_when_not_expired(
        self, db_session, oauth_account
    ):
        from app.services.calendar.crypto import encrypt_credentials

        creds = {
            "access_token": "still_fresh",
            "refresh_token": "rf",
            "token_expires_at": (
                datetime.now(timezone.utc) + timedelta(hours=1)
            ).isoformat(),
        }
        oauth_account.encrypted_credentials = encrypt_credentials(creds)
        oauth_account.token_expires_at = datetime.now(
            timezone.utc
        ) + timedelta(hours=1)
        db_session.flush()

        token = oauth_service.ensure_fresh_token(
            db_session, account=oauth_account
        )
        assert token == "still_fresh"

    def test_refreshes_when_within_buffer(self, db_session, oauth_account):
        from app.services.calendar.crypto import encrypt_credentials

        creds = {
            "access_token": "stale",
            "refresh_token": "rf_test",
            "token_expires_at": (
                datetime.now(timezone.utc) + timedelta(seconds=60)
            ).isoformat(),
        }
        oauth_account.encrypted_credentials = encrypt_credentials(creds)
        oauth_account.token_expires_at = datetime.now(
            timezone.utc
        ) + timedelta(seconds=60)  # within 5-min default buffer
        db_session.flush()

        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "access_token": "fresh_after_refresh",
                    "expires_in": 3600,
                },
            )

        transport = httpx.MockTransport(mock_handler)
        with _mock_http_client(transport):
            token = oauth_service.ensure_fresh_token(
                db_session, account=oauth_account
            )

        assert token == "fresh_after_refresh"

    def test_no_credentials_raises_oauth_auth_error(
        self, db_session, oauth_account
    ):
        # encrypted_credentials is None — fresh account.
        with pytest.raises(oauth_service.OAuthAuthError):
            oauth_service.ensure_fresh_token(
                db_session, account=oauth_account
            )
