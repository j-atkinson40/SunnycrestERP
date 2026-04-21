"""Portal authentication — Workflow Arc Phase 8e.2.

Login + refresh + password-reset for portal users. Separate from
tenant auth flow per SPACES_ARCHITECTURE.md §10 ("identity-level
separation") but shares JWT primitives via `core/security.py` with
realm="portal" extension.

Security posture:
  - 8-char password minimum, no complexity rules (portal users may
    be drivers without password-manager access).
  - 10 failed-login attempts within 30 minutes → locked_until
    stamp; 30-minute lockout.
  - IP+email rate limit on login endpoint (in-memory bucket per
    worker, 10 attempts / 30 min).
  - 1-hour single-use password reset tokens.
  - 12-hour access token / 7-day refresh (portal_partner default;
    per-space override via SpaceConfig.session_timeout_minutes).
"""

from __future__ import annotations

import secrets
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.company import Company
from app.models.portal_user import PortalUser

# ── Errors ──────────────────────────────────────────────────────────


class PortalAuthError(Exception):
    """Base portal auth error. `http_status` lets route handlers
    translate cleanly."""

    http_status = 401


class PortalLoginInvalid(PortalAuthError):
    http_status = 401


class PortalLoginLocked(PortalAuthError):
    http_status = 429


class PortalRateLimited(PortalAuthError):
    http_status = 429


# ── Security tunables ───────────────────────────────────────────────

_LOCKOUT_FAILED_THRESHOLD: int = 10
_LOCKOUT_DURATION = timedelta(minutes=30)
_RATE_LIMIT_WINDOW_SECONDS: float = 30 * 60.0
_RATE_LIMIT_MAX_ATTEMPTS: int = 10

# Default TTL for portal access tokens. Overridable per-space via
# SpaceConfig.session_timeout_minutes (Phase 8e.2).
_DEFAULT_ACCESS_TTL_MINUTES: int = 12 * 60
_DEFAULT_REFRESH_TTL_DAYS: int = 7

_PASSWORD_MIN_LENGTH: int = 8


# ── In-memory rate-limit bucket (per-worker, defense-in-depth) ──────


_rate_limit_lock = threading.Lock()
_rate_limit_buckets: dict[tuple[str, str], list[float]] = {}


def _enforce_rate_limit(*, ip: str, email: str) -> None:
    """Raise PortalRateLimited if login attempts from this (ip, email)
    have exceeded 10 in the last 30 minutes. Bucket is per-worker;
    production tenants behind a proxy + multiple workers would
    benefit from a Redis-backed shared bucket — deferred per audit.
    """
    now = time.monotonic()
    key = (ip or "unknown", email.lower())
    with _rate_limit_lock:
        bucket = _rate_limit_buckets.setdefault(key, [])
        # Purge attempts older than the window.
        bucket[:] = [t for t in bucket if now - t < _RATE_LIMIT_WINDOW_SECONDS]
        if len(bucket) >= _RATE_LIMIT_MAX_ATTEMPTS:
            raise PortalRateLimited(
                "Too many login attempts. Try again later."
            )
        bucket.append(now)


def _clear_rate_limit_for_tests() -> None:
    with _rate_limit_lock:
        _rate_limit_buckets.clear()


# ── Authentication ──────────────────────────────────────────────────


def authenticate_portal_user(
    db: Session,
    *,
    company: Company,
    email: str,
    password: str,
    client_ip: str = "unknown",
) -> PortalUser:
    """Authenticate a portal user against a tenant.

    Raises:
        PortalLoginInvalid: email not found, password mismatch,
            user inactive.
        PortalLoginLocked: account locked from failed attempts.
        PortalRateLimited: too many attempts from (ip, email).

    On success: resets failed_login_count, stamps last_login_at.
    """
    _enforce_rate_limit(ip=client_ip, email=email)

    user = (
        db.query(PortalUser)
        .filter(
            PortalUser.email == email.lower().strip(),
            PortalUser.company_id == company.id,
        )
        .first()
    )
    # Generic error message — don't leak whether email exists.
    generic = PortalLoginInvalid("Invalid email or password.")
    if user is None:
        raise generic

    now = datetime.now(timezone.utc)

    # Check lockout first.
    if user.locked_until is not None and user.locked_until > now:
        raise PortalLoginLocked(
            "Account temporarily locked due to too many failed "
            "attempts. Try again in 30 minutes."
        )

    if not user.is_active:
        raise generic

    if user.hashed_password is None:
        # Invite-only user who hasn't set a password yet. Advise
        # them to check their invite email without confirming the
        # email exists.
        raise generic

    if not verify_password(password, user.hashed_password):
        # Track failure + possibly lock the account.
        user.failed_login_count = (user.failed_login_count or 0) + 1
        if user.failed_login_count >= _LOCKOUT_FAILED_THRESHOLD:
            user.locked_until = now + _LOCKOUT_DURATION
            user.failed_login_count = 0
        db.commit()
        raise generic

    # Success — reset failure counter + stamp last_login_at.
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    db.commit()
    return user


def create_portal_tokens(
    user: PortalUser,
    *,
    access_ttl_minutes: int | None = None,
    refresh_ttl_days: int | None = None,
) -> dict[str, str]:
    """Create a portal-realm access + refresh token pair.

    Access token carries scope claims:
      - sub: portal_user.id
      - realm: "portal"
      - company_id: tenant id
      - space_id: the portal user's assigned_space_id (required;
        middleware rejects tokens without it)
    """
    access_ttl = access_ttl_minutes or _DEFAULT_ACCESS_TTL_MINUTES
    refresh_ttl = refresh_ttl_days or _DEFAULT_REFRESH_TTL_DAYS

    base_payload = {
        "sub": user.id,
        "company_id": user.company_id,
        "space_id": user.assigned_space_id or "",
    }
    access = create_access_token(
        base_payload,
        realm="portal",
        expires_minutes=access_ttl,
    )
    # create_refresh_token uses settings.REFRESH_TOKEN_EXPIRE_DAYS;
    # we encode our own refresh explicitly to allow per-realm TTL.
    from app.config import settings as _settings
    from jose import jwt

    refresh_expire = datetime.now(timezone.utc) + timedelta(days=refresh_ttl)
    refresh_payload = {
        **base_payload,
        "type": "refresh",
        "realm": "portal",
        "exp": refresh_expire,
    }
    refresh = jwt.encode(
        refresh_payload, _settings.SECRET_KEY, algorithm=_settings.ALGORITHM
    )
    return {"access_token": access, "refresh_token": refresh}


def verify_portal_refresh_token(token: str) -> dict:
    """Decode and validate a portal refresh token. Returns the
    payload on success; raises PortalAuthError on failure."""
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise PortalAuthError("Invalid refresh token") from exc
    if payload.get("type") != "refresh":
        raise PortalAuthError("Not a refresh token")
    if payload.get("realm") != "portal":
        raise PortalAuthError("Wrong token realm")
    return payload


# ── Password management ─────────────────────────────────────────────


def validate_password_strength(password: str) -> None:
    """Minimum 8 chars. No complexity requirements — portal users
    may be drivers without password manager access; complex rules
    become a support burden."""
    if not password or len(password) < _PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {_PASSWORD_MIN_LENGTH} characters."
        )


def set_portal_password(
    db: Session, *, user: PortalUser, new_password: str
) -> None:
    """Hash + persist a new password. Clears recovery tokens."""
    validate_password_strength(new_password)
    user.hashed_password = hash_password(new_password)
    user.recovery_token = None
    user.recovery_token_expires_at = None
    user.invite_token = None
    user.invite_token_expires_at = None
    user.failed_login_count = 0
    user.locked_until = None
    db.commit()


def issue_recovery_token(
    db: Session, *, user: PortalUser, ttl_hours: int = 1
) -> str:
    """Generate a single-use 1-hour recovery token. Returns the
    plaintext token (server also stores it; this is the only time
    the caller sees it — it's emailed to the user)."""
    token = secrets.token_urlsafe(32)
    user.recovery_token = token
    user.recovery_token_expires_at = datetime.now(timezone.utc) + timedelta(
        hours=ttl_hours
    )
    db.commit()
    return token


def consume_recovery_token(
    db: Session, *, company: Company, token: str, new_password: str
) -> PortalUser:
    """Exchange a recovery token for a new password. Validates the
    token (exists, not expired, tenant matches) and clears it.

    Raises PortalAuthError if the token is invalid/expired.
    """
    user = (
        db.query(PortalUser)
        .filter(
            PortalUser.company_id == company.id,
            PortalUser.recovery_token == token,
        )
        .first()
    )
    now = datetime.now(timezone.utc)
    if user is None:
        raise PortalAuthError("Invalid or expired recovery token.")
    exp = user.recovery_token_expires_at
    if exp is None or exp < now:
        raise PortalAuthError("Recovery token has expired.")

    set_portal_password(db, user=user, new_password=new_password)
    return user
