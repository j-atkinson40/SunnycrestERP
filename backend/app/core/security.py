from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict, *, realm: str = "tenant") -> str:
    """Create a JWT access token.

    Args:
        data: Payload data (must include ``sub``).
        realm: ``"tenant"`` (default) or ``"platform"``.  The realm is baked
               into the token so platform and tenant tokens cannot be used
               interchangeably.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
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
