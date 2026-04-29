"""OAuth flow + token-management service — Phase W-4b Layer 1 Step 2.

End-to-end OAuth code-grant infrastructure for Gmail API + Microsoft
Graph providers. CSRF protection via short-lived signed-state nonces
in ``oauth_state_nonces``. Token persistence via Fernet encryption
into ``EmailAccount.encrypted_credentials``.

**Configuration** (env vars):
  - ``GOOGLE_OAUTH_CLIENT_ID`` / ``GOOGLE_OAUTH_CLIENT_SECRET``
  - ``MICROSOFT_OAUTH_CLIENT_ID`` / ``MICROSOFT_OAUTH_CLIENT_SECRET``
  - ``MICROSOFT_OAUTH_TENANT`` (default: ``common``)
  - ``CREDENTIAL_ENCRYPTION_KEY`` (shared with TenantExternalAccount)

In dev/test environments, missing client_id/secret degrade to
placeholder strings so the OAuth-URL generation flow is exercisable
without real credentials. The actual code-exchange POST will fail
loud against placeholder credentials when called against a real
provider — by design.

**Token refresh discipline:**

  - Access token has provider-specific TTL (~1h Gmail, ~1h Graph)
  - Refresh token is long-lived (Gmail: indefinite with offline scope;
    Graph: 90 days inactive expiry)
  - ``ensure_fresh_token(account)`` is the canonical entry point
    every sync/send call goes through. Returns decrypted access token
    or raises ``OAuthAuthError`` requiring user to re-OAuth.
  - Audit log entry on every refresh.

**Step 2 testing constraint:** real OAuth flows require Google /
Microsoft client registration which I can't do in this environment.
Tests mock httpx responses; production verification requires real
provider env follow-up.
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.models.email_primitive import (
    EmailAccount,
    EmailAccountSyncState,
    EmailAuditLog,
    OAuthStateNonce,
)
from app.services.email.account_service import (
    EmailAccountError,
    EmailAccountValidation,
    _audit,
)
from app.services.email.crypto import (
    EmailCredentialEncryptionError,
    decrypt_credentials,
    encrypt_credentials,
    redact_for_audit,
)


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────


class OAuthError(EmailAccountError):
    http_status = 400


class OAuthStateInvalid(OAuthError):
    """Raised when state nonce doesn't match, expired, or already consumed."""


class OAuthAuthError(EmailAccountError):
    """Raised when access/refresh token exchange or refresh fails."""

    http_status = 401


# ─────────────────────────────────────────────────────────────────────
# Provider OAuth endpoints + scopes (canonical per provider docs)
# ─────────────────────────────────────────────────────────────────────


_GMAIL_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
_GMAIL_TOKEN = "https://oauth2.googleapis.com/token"
_GMAIL_SCOPES = " ".join(
    [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.send",
    ]
)


def _msgraph_authorize() -> str:
    tenant = os.environ.get("MICROSOFT_OAUTH_TENANT", "common")
    return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"


def _msgraph_token() -> str:
    tenant = os.environ.get("MICROSOFT_OAUTH_TENANT", "common")
    return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


_MSGRAPH_SCOPES = " ".join(
    ["Mail.ReadWrite", "Mail.Send", "offline_access", "User.Read"]
)


# ─────────────────────────────────────────────────────────────────────
# State nonce — CSRF protection
# ─────────────────────────────────────────────────────────────────────


_NONCE_TTL_MINUTES = 10


def issue_state_nonce(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    provider_type: str,
    redirect_uri: str,
) -> str:
    """Issue a short-lived state nonce for an OAuth flow.

    Returns the nonce string (cryptographically random; stored
    server-side for callback validation). Caller embeds in the
    authorize URL ``state=`` param.
    """
    if provider_type not in ("gmail", "msgraph"):
        raise EmailAccountValidation(
            f"OAuth state nonce only valid for gmail/msgraph providers, "
            f"got {provider_type!r}."
        )
    nonce = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=_NONCE_TTL_MINUTES
    )
    row = OAuthStateNonce(
        nonce=nonce,
        tenant_id=tenant_id,
        user_id=user_id,
        provider_type=provider_type,
        redirect_uri=redirect_uri,
        expires_at=expires_at,
    )
    db.add(row)
    db.flush()
    return nonce


def validate_and_consume_state_nonce(
    db: Session,
    *,
    nonce: str,
    tenant_id: str,
    user_id: str,
    provider_type: str,
) -> OAuthStateNonce:
    """Validate the state nonce + atomic consume (single-use).

    Raises ``OAuthStateInvalid`` if the nonce is missing, expired,
    already consumed, or doesn't match (tenant_id, user_id,
    provider_type) tuple. Single-use semantics enforced by
    ``consumed_at`` flip in the same transaction.
    """
    row = db.query(OAuthStateNonce).filter(OAuthStateNonce.nonce == nonce).first()
    if not row:
        raise OAuthStateInvalid("OAuth state nonce not found.")
    if row.consumed_at is not None:
        raise OAuthStateInvalid("OAuth state nonce already consumed (replay).")
    if row.expires_at < datetime.now(timezone.utc):
        raise OAuthStateInvalid("OAuth state nonce expired.")
    if row.tenant_id != tenant_id:
        raise OAuthStateInvalid("OAuth state nonce tenant mismatch.")
    if row.user_id != user_id:
        raise OAuthStateInvalid("OAuth state nonce user mismatch.")
    if row.provider_type != provider_type:
        raise OAuthStateInvalid("OAuth state nonce provider mismatch.")
    row.consumed_at = datetime.now(timezone.utc)
    db.flush()
    return row


# ─────────────────────────────────────────────────────────────────────
# Authorize URL builders (real, replacing Step 1 placeholders)
# ─────────────────────────────────────────────────────────────────────


def build_authorize_url(
    *,
    provider_type: str,
    state: str,
    redirect_uri: str,
) -> str:
    """Build a real provider authorize URL with configured client_id +
    canonical scopes.

    Uses ``REPLACE_IN_STEP_2`` placeholder when client_id env var is
    not set (dev/test). Placeholder URLs hit the real provider and
    fail loud with "invalid client" — that's the desired behavior.
    """
    if provider_type == "gmail":
        client_id = os.environ.get(
            "GOOGLE_OAUTH_CLIENT_ID", "REPLACE_IN_STEP_2_GOOGLE_CLIENT_ID"
        )
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _GMAIL_SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "include_granted_scopes": "true",
        }
        return f"{_GMAIL_AUTHORIZE}?{urlencode(params)}"
    if provider_type == "msgraph":
        client_id = os.environ.get(
            "MICROSOFT_OAUTH_CLIENT_ID", "REPLACE_IN_STEP_2_MS_CLIENT_ID"
        )
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _MSGRAPH_SCOPES,
            "response_mode": "query",
            "state": state,
        }
        return f"{_msgraph_authorize()}?{urlencode(params)}"
    raise EmailAccountValidation(
        f"Provider {provider_type!r} does not use OAuth."
    )


# ─────────────────────────────────────────────────────────────────────
# Code → token exchange
# ─────────────────────────────────────────────────────────────────────


def _http_client() -> httpx.Client:
    """Build the httpx client for token requests.

    Pulled out so tests can monkey-patch a transport (httpx.MockTransport)
    without touching the calling code.
    """
    return httpx.Client(timeout=30.0)


def _exchange_gmail(
    *, code: str, redirect_uri: str
) -> dict[str, Any]:
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
    body = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    with _http_client() as client:
        r = client.post(_GMAIL_TOKEN, data=body)
    if r.status_code != 200:
        raise OAuthAuthError(
            f"Gmail token exchange failed (status={r.status_code}): "
            f"{r.text[:300]}"
        )
    return r.json()


def _exchange_msgraph(
    *, code: str, redirect_uri: str
) -> dict[str, Any]:
    client_id = os.environ.get("MICROSOFT_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("MICROSOFT_OAUTH_CLIENT_SECRET", "")
    body = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "scope": _MSGRAPH_SCOPES,
    }
    with _http_client() as client:
        r = client.post(_msgraph_token(), data=body)
    if r.status_code != 200:
        raise OAuthAuthError(
            f"MS Graph token exchange failed (status={r.status_code}): "
            f"{r.text[:300]}"
        )
    return r.json()


def _refresh_gmail(*, refresh_token: str) -> dict[str, Any]:
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
    body = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    with _http_client() as client:
        r = client.post(_GMAIL_TOKEN, data=body)
    if r.status_code != 200:
        raise OAuthAuthError(
            f"Gmail token refresh failed (status={r.status_code}): "
            f"{r.text[:300]}"
        )
    return r.json()


def _refresh_msgraph(*, refresh_token: str) -> dict[str, Any]:
    client_id = os.environ.get("MICROSOFT_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("MICROSOFT_OAUTH_CLIENT_SECRET", "")
    body = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": _MSGRAPH_SCOPES,
    }
    with _http_client() as client:
        r = client.post(_msgraph_token(), data=body)
    if r.status_code != 200:
        raise OAuthAuthError(
            f"MS Graph token refresh failed (status={r.status_code}): "
            f"{r.text[:300]}"
        )
    return r.json()


# ─────────────────────────────────────────────────────────────────────
# High-level lifecycle: complete-OAuth, refresh-token, ensure-fresh-token
# ─────────────────────────────────────────────────────────────────────


def _build_credentials_payload(token_response: dict[str, Any]) -> dict[str, Any]:
    """Normalize provider token response to canonical credential shape.

    Both Gmail + MSGraph return ``{access_token, refresh_token,
    expires_in, token_type, scope, ...}``. We persist the canonical
    fields + compute ``token_expires_at`` for fast scheduling.
    """
    expires_in = int(token_response.get("expires_in", 3600))
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return {
        "access_token": token_response["access_token"],
        "refresh_token": token_response.get("refresh_token"),
        "token_expires_at": expires_at.isoformat(),
        "token_type": token_response.get("token_type", "Bearer"),
        "scope": token_response.get("scope", ""),
    }


def complete_oauth_exchange(
    db: Session,
    *,
    account: EmailAccount,
    code: str,
    redirect_uri: str,
    actor_user_id: str | None,
) -> dict[str, Any]:
    """Exchange authorization code → tokens → persist encrypted.

    Idempotent at the DB row level: if the account already has
    credentials, this OVERWRITES them (re-auth flow). Audit log
    records the operation.

    Returns the canonical credentials dict (decrypted) for use by
    the caller (typically to immediately kick off initial backfill).
    """
    if account.provider_type == "gmail":
        token_response = _exchange_gmail(code=code, redirect_uri=redirect_uri)
    elif account.provider_type == "msgraph":
        token_response = _exchange_msgraph(code=code, redirect_uri=redirect_uri)
    else:
        raise EmailAccountValidation(
            f"complete_oauth_exchange not applicable for provider "
            f"{account.provider_type!r}."
        )

    creds = _build_credentials_payload(token_response)
    encrypted = encrypt_credentials(creds)

    account.encrypted_credentials = encrypted
    account.token_expires_at = datetime.fromisoformat(creds["token_expires_at"])
    account.last_credential_op = "oauth_complete"
    account.last_credential_op_at = datetime.now(timezone.utc)

    _audit(
        db,
        tenant_id=account.tenant_id,
        actor_user_id=actor_user_id,
        action="credentials_persisted",
        entity_type="email_account",
        entity_id=account.id,
        changes={
            "operation": "oauth_complete",
            "provider_type": account.provider_type,
            "credential_fields": redact_for_audit(creds),
            "token_expires_at": creds["token_expires_at"],
        },
    )
    db.flush()
    return creds


def refresh_token(
    db: Session,
    *,
    account: EmailAccount,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    """Refresh an OAuth access token using the stored refresh token.

    Updates ``encrypted_credentials`` + ``token_expires_at`` in the
    same transaction. Audit log entry on success or failure.

    Raises ``OAuthAuthError`` if the refresh fails — caller should
    surface "reconnect required" to the operator.
    """
    try:
        creds = decrypt_credentials(account.encrypted_credentials)
    except EmailCredentialEncryptionError as exc:
        raise OAuthAuthError(
            "Stored credentials are corrupted or encrypted under a "
            "rotated key — operator must re-OAuth this account."
        ) from exc

    refresh = creds.get("refresh_token")
    if not refresh:
        raise OAuthAuthError(
            "No refresh_token stored for this account — operator must "
            "re-OAuth (initial offline_access scope may have been "
            "skipped)."
        )

    try:
        if account.provider_type == "gmail":
            token_response = _refresh_gmail(refresh_token=refresh)
        elif account.provider_type == "msgraph":
            token_response = _refresh_msgraph(refresh_token=refresh)
        else:
            raise EmailAccountValidation(
                f"refresh_token not applicable for provider "
                f"{account.provider_type!r}."
            )
    except OAuthAuthError:
        # Audit the FAILED refresh before re-raising. Operators see
        # the failed-refresh row in email_audit_log to diagnose
        # provider-side revocations.
        account.last_credential_op = "refresh_failed"
        account.last_credential_op_at = datetime.now(timezone.utc)
        _audit(
            db,
            tenant_id=account.tenant_id,
            actor_user_id=actor_user_id,
            action="credentials_refresh_failed",
            entity_type="email_account",
            entity_id=account.id,
            changes={
                "operation": "refresh",
                "provider_type": account.provider_type,
            },
        )
        db.flush()
        raise

    new_creds = _build_credentials_payload(token_response)
    # Some providers (Gmail) don't return a fresh refresh_token on
    # every refresh — preserve the old one if absent.
    if not new_creds.get("refresh_token"):
        new_creds["refresh_token"] = refresh

    account.encrypted_credentials = encrypt_credentials(new_creds)
    account.token_expires_at = datetime.fromisoformat(
        new_creds["token_expires_at"]
    )
    account.last_credential_op = "refresh"
    account.last_credential_op_at = datetime.now(timezone.utc)

    _audit(
        db,
        tenant_id=account.tenant_id,
        actor_user_id=actor_user_id,
        action="credentials_refreshed",
        entity_type="email_account",
        entity_id=account.id,
        changes={
            "operation": "refresh",
            "provider_type": account.provider_type,
            "new_expires_at": new_creds["token_expires_at"],
        },
    )
    db.flush()
    return new_creds


def ensure_fresh_token(
    db: Session,
    *,
    account: EmailAccount,
    refresh_buffer_seconds: int = 300,
) -> str:
    """Return a non-expired access token, refreshing if needed.

    Canonical entry point every sync/send call goes through. Refreshes
    proactively when within ``refresh_buffer_seconds`` of expiry (5min
    default) so a long-running sync doesn't hit a 401 mid-stream.

    Returns the decrypted access_token string. Raises ``OAuthAuthError``
    when the account requires re-OAuth.
    """
    creds = decrypt_credentials(account.encrypted_credentials)
    if not creds.get("access_token"):
        raise OAuthAuthError(
            "Account has no stored access token — operator must complete "
            "OAuth flow."
        )

    expires_at = account.token_expires_at
    if expires_at is not None:
        threshold = datetime.now(timezone.utc) + timedelta(
            seconds=refresh_buffer_seconds
        )
        if expires_at <= threshold:
            creds = refresh_token(db, account=account)

    return creds["access_token"]


def revoke_credentials(
    db: Session,
    *,
    account: EmailAccount,
    actor_user_id: str | None,
) -> None:
    """Clear stored credentials + audit the revocation.

    Does NOT call the provider revoke endpoint (real revocation is a
    network call that may fail; the local row is the source of truth
    for "this account no longer has working credentials"). Step 3+
    can wire provider-side revocation when we add a Disconnect button
    for OAuth accounts.
    """
    account.encrypted_credentials = None
    account.token_expires_at = None
    account.last_credential_op = "revoke"
    account.last_credential_op_at = datetime.now(timezone.utc)

    _audit(
        db,
        tenant_id=account.tenant_id,
        actor_user_id=actor_user_id,
        action="credentials_revoked",
        entity_type="email_account",
        entity_id=account.id,
        changes={
            "operation": "revoke",
            "provider_type": account.provider_type,
        },
    )
    db.flush()
