"""API key generation, validation, rate limiting, and usage tracking."""

import json
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import Lock

import bcrypt
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.api_key import ApiKey
from app.models.api_key_usage import ApiKeyUsage

# ---------------------------------------------------------------------------
# In-memory rate limiter (sliding window counter)
# ---------------------------------------------------------------------------
_rate_lock = Lock()
_rate_buckets: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(api_key_id: str, limit: int) -> bool:
    """Return True if request is allowed, False if rate-limited."""
    now = time.time()
    window = 60.0  # 1 minute
    with _rate_lock:
        bucket = _rate_buckets[api_key_id]
        # Prune expired entries
        _rate_buckets[api_key_id] = [t for t in bucket if now - t < window]
        if len(_rate_buckets[api_key_id]) >= limit:
            return False
        _rate_buckets[api_key_id].append(now)
        return True


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------

_KEY_PREFIX = "sk_"  # Standard prefix for all keys


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns (full_key, key_hash, key_prefix).
    """
    raw = secrets.token_urlsafe(32)
    full_key = f"{_KEY_PREFIX}{raw}"
    key_hash = bcrypt.hashpw(full_key.encode(), bcrypt.gensalt()).decode()
    key_prefix = full_key[:12]
    return full_key, key_hash, key_prefix


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def create_api_key(
    db: Session,
    company_id: str,
    created_by: str,
    name: str,
    scopes: list[str],
    rate_limit_per_minute: int = 60,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    """Create a new API key. Returns (model, full_key)."""
    full_key, key_hash, key_prefix = generate_api_key()
    api_key = ApiKey(
        company_id=company_id,
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes=json.dumps(scopes),
        rate_limit_per_minute=rate_limit_per_minute,
        expires_at=expires_at,
        created_by=created_by,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key, full_key


def list_api_keys(db: Session, company_id: str) -> list[ApiKey]:
    return (
        db.query(ApiKey)
        .filter(ApiKey.company_id == company_id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )


def get_api_key(db: Session, key_id: str, company_id: str) -> ApiKey | None:
    return (
        db.query(ApiKey)
        .filter(ApiKey.id == key_id, ApiKey.company_id == company_id)
        .first()
    )


def update_api_key(
    db: Session,
    api_key: ApiKey,
    name: str | None = None,
    scopes: list[str] | None = None,
    rate_limit_per_minute: int | None = None,
    expires_at: datetime | None = None,
    is_active: bool | None = None,
) -> ApiKey:
    if name is not None:
        api_key.name = name
    if scopes is not None:
        api_key.scopes = json.dumps(scopes)
    if rate_limit_per_minute is not None:
        api_key.rate_limit_per_minute = rate_limit_per_minute
    if expires_at is not None:
        api_key.expires_at = expires_at
    if is_active is not None:
        api_key.is_active = is_active
    db.commit()
    db.refresh(api_key)
    return api_key


def revoke_api_key(db: Session, api_key: ApiKey) -> None:
    api_key.is_active = False
    db.commit()


def delete_api_key(db: Session, api_key: ApiKey) -> None:
    db.delete(api_key)
    db.commit()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_api_key(
    db: Session, raw_key: str
) -> tuple[ApiKey | None, str | None]:
    """Validate an API key.

    Returns (api_key, error_message). If valid, error_message is None.
    """
    if not raw_key.startswith(_KEY_PREFIX):
        return None, "Invalid key format"

    prefix = raw_key[:12]
    # Look up candidates by prefix (usually 1 match)
    candidates = (
        db.query(ApiKey)
        .filter(ApiKey.key_prefix == prefix, ApiKey.is_active.is_(True))
        .all()
    )
    for candidate in candidates:
        if bcrypt.checkpw(raw_key.encode(), candidate.key_hash.encode()):
            # Check expiry
            if candidate.expires_at and candidate.expires_at < datetime.now(
                timezone.utc
            ):
                return None, "API key has expired"

            # Check rate limit
            if not _check_rate_limit(
                candidate.id, candidate.rate_limit_per_minute
            ):
                return None, "Rate limit exceeded"

            # Update last used
            candidate.last_used_at = datetime.now(timezone.utc)
            db.commit()

            return candidate, None

    return None, "Invalid API key"


def get_scopes(api_key: ApiKey) -> list[str]:
    """Parse scopes from JSON string."""
    try:
        return json.loads(api_key.scopes)
    except (json.JSONDecodeError, TypeError):
        return []


def has_scope(api_key: ApiKey, required_scope: str) -> bool:
    """Check if an API key has a specific scope."""
    scopes = get_scopes(api_key)
    if "*" in scopes:
        return True
    # Check exact match or wildcard (e.g., "customers.*")
    resource = required_scope.split(".")[0]
    return required_scope in scopes or f"{resource}.*" in scopes


# ---------------------------------------------------------------------------
# Usage tracking
# ---------------------------------------------------------------------------


def record_usage(
    db: Session, api_key_id: str, is_error: bool = False
) -> None:
    """Record a request for hourly aggregation."""
    now = datetime.now(timezone.utc)
    hour_bucket = now.replace(minute=0, second=0, microsecond=0)

    usage = (
        db.query(ApiKeyUsage)
        .filter(
            ApiKeyUsage.api_key_id == api_key_id,
            ApiKeyUsage.hour_bucket == hour_bucket,
        )
        .first()
    )

    if usage:
        usage.request_count += 1
        if is_error:
            usage.error_count += 1
    else:
        usage = ApiKeyUsage(
            api_key_id=api_key_id,
            hour_bucket=hour_bucket,
            request_count=1,
            error_count=1 if is_error else 0,
        )
        db.add(usage)

    db.commit()


def get_usage_stats(
    db: Session, api_key_id: str, hours: int = 24
) -> list[ApiKeyUsage]:
    """Get usage stats for the last N hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return (
        db.query(ApiKeyUsage)
        .filter(
            ApiKeyUsage.api_key_id == api_key_id,
            ApiKeyUsage.hour_bucket >= cutoff,
        )
        .order_by(ApiKeyUsage.hour_bucket.asc())
        .all()
    )


def get_usage_summary(db: Session, api_key_id: str) -> dict:
    """Get 24h summary totals."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    result = (
        db.query(
            func.coalesce(func.sum(ApiKeyUsage.request_count), 0),
            func.coalesce(func.sum(ApiKeyUsage.error_count), 0),
        )
        .filter(
            ApiKeyUsage.api_key_id == api_key_id,
            ApiKeyUsage.hour_bucket >= cutoff,
        )
        .first()
    )
    return {
        "total_requests_24h": result[0] if result else 0,
        "total_errors_24h": result[1] if result else 0,
    }
