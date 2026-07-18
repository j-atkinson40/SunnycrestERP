"""Plaid access-token encryption — the Fernet-layer reuse (B-1).

Same single-master-key pattern as ``credential_service.py`` /
``email/crypto.py`` / ``calendar/crypto.py``: key from the
``CREDENTIAL_ENCRYPTION_KEY`` env var (the shared rotation surface —
deliberately NOT ``fh/crypto``'s divergent ``BRIDGEABLE_ENCRYPTION_KEY``),
read from os.environ so it never enters the pydantic settings object.

THE ANTI-QBO DISCIPLINE: ``PlaidItem.access_token_encrypted`` is written
exclusively through ``encrypt_token`` — the column is actually fed, unlike
AccountingConnection's dead ``*_encrypted`` columns. The round-trip pin in
test_plaid_b1.py is named for this.

NEVER-LOGGED: the raw token exists in exactly two places — the exchange
write path and the decrypt-for-API-call path. It is never a route response
field, never in audit changes (use ``redact_for_audit``), never logged.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class PlaidCredentialEncryptionError(RuntimeError):
    """CREDENTIAL_ENCRYPTION_KEY missing/invalid, or decryption failed
    (key rotation without re-link — operator must reconnect the item)."""


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    key = os.environ.get("CREDENTIAL_ENCRYPTION_KEY")
    if not key:
        raise PlaidCredentialEncryptionError(
            "CREDENTIAL_ENCRYPTION_KEY env var is not set. Generate one "
            "with: python -c 'from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())'"
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:  # noqa: BLE001 — surface the root cause
        raise PlaidCredentialEncryptionError(
            f"Invalid CREDENTIAL_ENCRYPTION_KEY: {exc}"
        ) from exc


def reset_fernet_cache() -> None:
    """Test hook — the lru_cache pins the key for the process lifetime
    (process restart is the canonical rotation window); tests that set
    their own key must clear it."""
    _get_fernet.cache_clear()


def encrypt_token(token: str) -> str:
    if not token:
        raise PlaidCredentialEncryptionError("Refusing to encrypt an empty token")
    return _get_fernet().encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str | None) -> str:
    if not ciphertext:
        raise PlaidCredentialEncryptionError(
            "No stored access token — the item was never fully linked"
        )
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise PlaidCredentialEncryptionError(
            "Failed to decrypt Plaid access token — the encryption key has "
            "rotated since this item was linked. Reconnect the bank to recover."
        ) from exc


def redact_for_audit(payload: dict[str, Any]) -> dict[str, Any]:
    """Presence + length only — the email/calendar crypto convention.
    Use for ANY audit/log write that touches item lifecycle payloads."""
    return {
        key: {"present": True, "length": len(str(value))}
        for key, value in payload.items()
    }
