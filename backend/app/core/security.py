import base64
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.config import settings

# ── Fernet for reversible PIN encryption ──────────────────────────

_fernet_instance: Fernet | None = None


def _get_fernet() -> Fernet:
    """Derive a stable Fernet key from SECRET_KEY via PBKDF2."""
    global _fernet_instance
    if _fernet_instance is None:
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            settings.SECRET_KEY.encode(),
            b"sunnycrest-pin-encryption-salt",
            100_000,
        )
        key = base64.urlsafe_b64encode(dk[:32])
        _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_pin(pin: str) -> str:
    """Encrypt a 4-digit PIN with Fernet (AES). Returns base64 token string."""
    return _get_fernet().encrypt(pin.encode()).decode()


def decrypt_pin(encrypted: str) -> str:
    """Decrypt a Fernet-encrypted PIN back to plaintext."""
    return _get_fernet().decrypt(encrypted.encode()).decode()


def verify_pin(plain_pin: str, encrypted: str) -> bool:
    """Verify a plaintext PIN against its encrypted form."""
    try:
        return decrypt_pin(encrypted) == plain_pin
    except Exception:
        return False


# ── Password hashing (bcrypt) ────────────────────────────────────


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(
    data: dict, *, realm: str = "tenant", expires_minutes: int | None = None
) -> str:
    """Create a JWT access token.

    Args:
        data: Payload data (must include ``sub``).
        realm: ``"tenant"`` (default) or ``"platform"``.  The realm is baked
               into the token so platform and tenant tokens cannot be used
               interchangeably.
        expires_minutes: Override the default access token TTL.
    """
    ttl = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=ttl)
    to_encode = {**data, "exp": expire, "type": "access", "realm": realm}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict, *, realm: str = "tenant") -> str:
    """Create a JWT refresh token.

    Args:
        data: Payload data (must include ``sub``).
        realm: ``"tenant"`` (default) or ``"platform"``.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    to_encode = {**data, "exp": expire, "type": "refresh", "realm": realm}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_impersonation_token(data: dict, *, ttl_minutes: int = 30) -> str:
    """Create a short-lived impersonation token.

    These are tenant-realm tokens with an ``impersonation`` flag and a short
    TTL.  They cannot be refreshed.

    Args:
        data: Must include ``sub``, ``company_id``, ``platform_user_id``,
              ``session_id``.
        ttl_minutes: Token lifetime in minutes (default 30).
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    to_encode = {
        **data,
        "exp": expire,
        "type": "access",
        "realm": "tenant",
        "impersonation": True,
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
