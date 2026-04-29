"""Email Primitive credential encryption — Phase W-4b Layer 1 Step 2.

Reuses the existing single-master-key Fernet pattern from
``app/services/credential_service.py``. The encryption key is read
from ``CREDENTIAL_ENCRYPTION_KEY`` env var (same key as
TenantExternalAccount credentials so a single key rotation event
covers both surfaces).

Per Step 2 canon-clarification (logged in commit 0e07dc0 follow-up
discussion + r64 migration docstring): the §3.26.15.8 "per-tenant
key isolation" prose means **per-row FK-scoped isolation under a
single platform master key** — matching the existing canon
discipline applied to SSN encryption + tenant external account
credentials. A future "real per-tenant key derivation" arc may
retrofit all three surfaces uniformly when the threat model
warrants.

Two payload shapes supported:

  - OAuth credentials: dict with keys ``access_token``,
    ``refresh_token`` (nullable for some providers), ``token_expires_at``
    (ISO 8601 UTC).
  - IMAP credentials: dict with keys ``imap_password`` plus any
    plaintext config (server, port, username) that should also stay
    encrypted-at-rest. The server/port/username live in
    ``provider_config`` (plaintext); the password lives in
    ``encrypted_credentials``.

Helpers operate on a single dict + return encrypted-string-or-None.
Callers persist the string into ``EmailAccount.encrypted_credentials``.

Audit-log discipline: this module never writes audit rows itself —
the caller (account_service / oauth_service / sync engine) writes the
``last_credential_op`` denormalized field on EmailAccount + emits an
EmailAuditLog row on every encrypt / decrypt / refresh / revoke event.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class EmailCredentialEncryptionError(RuntimeError):
    """Raised when CREDENTIAL_ENCRYPTION_KEY is missing or invalid, or
    when decryption fails (e.g. key rotation without re-encryption).
    """


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Resolve the platform master key.

    Cached so repeated encrypt/decrypt calls don't re-parse the env
    var. Cache invalidates on process restart (which is the canonical
    key-rotation event window — restart with new key, re-encrypt
    on next refresh / re-OAuth).
    """
    key = os.environ.get("CREDENTIAL_ENCRYPTION_KEY")
    if not key:
        raise EmailCredentialEncryptionError(
            "CREDENTIAL_ENCRYPTION_KEY env var is not set. "
            "Generate one with: "
            "python -c 'from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())'"
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:  # noqa: BLE001 - want to surface root cause
        raise EmailCredentialEncryptionError(
            f"Invalid CREDENTIAL_ENCRYPTION_KEY: {exc}"
        ) from exc


def encrypt_credentials(payload: dict[str, Any]) -> str:
    """Encrypt a credential dict to a Fernet-token string.

    Caller-friendly errors:
      - Empty / None payload returns empty string (caller decides
        whether to persist or no-op).
      - Encryption failure (missing/invalid key) raises
        ``EmailCredentialEncryptionError`` with a clear message.
    """
    if not payload:
        return ""
    fernet = _get_fernet()
    serialized = json.dumps(payload, sort_keys=True).encode("utf-8")
    return fernet.encrypt(serialized).decode("utf-8")


def decrypt_credentials(token: str | None) -> dict[str, Any]:
    """Decrypt a Fernet-token string back to a credential dict.

    Returns ``{}`` for None / empty input (account never had
    credentials persisted yet — typical for Step 1 placeholder rows
    or fresh accounts pending OAuth completion).

    Raises ``EmailCredentialEncryptionError`` when the token is
    malformed (key rotation event without re-encryption — operator
    must re-OAuth to recover, but should be loudly visible in logs).
    """
    if not token:
        return {}
    fernet = _get_fernet()
    try:
        decrypted = fernet.decrypt(token.encode("utf-8"))
    except InvalidToken as exc:
        raise EmailCredentialEncryptionError(
            "Failed to decrypt email credentials — token is malformed "
            "or the encryption key has rotated since these credentials "
            "were stored. Operator must re-OAuth this account."
        ) from exc
    try:
        return json.loads(decrypted.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EmailCredentialEncryptionError(
            f"Decrypted credential payload is not valid JSON: {exc}"
        ) from exc


def redact_for_audit(payload: dict[str, Any]) -> dict[str, Any]:
    """Build an audit-safe redacted view of a credential dict.

    Replaces every value with a presence flag + length to prevent
    accidental token leakage into audit_log.changes JSONB. Use this
    whenever logging changes to credentials.
    """
    return {
        key: {"present": True, "length": len(str(value))}
        for key, value in payload.items()
    }
