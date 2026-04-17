"""SSN and sensitive-field encryption helpers — Fernet symmetric encryption.

Key is read from BRIDGEABLE_ENCRYPTION_KEY env var. If the key is missing at
startup, encryption functions raise explicitly rather than storing plaintext.

Never log plaintext SSN. Never include encrypted bytes in JSON responses —
always redact or return the last-four view instead.
"""

import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken


class EncryptionNotConfiguredError(RuntimeError):
    """Raised when BRIDGEABLE_ENCRYPTION_KEY is not set or invalid."""


@lru_cache(maxsize=1)
def _get_cipher() -> Fernet:
    key = os.getenv("BRIDGEABLE_ENCRYPTION_KEY")
    if not key:
        raise EncryptionNotConfiguredError(
            "BRIDGEABLE_ENCRYPTION_KEY env var is not set. "
            "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        raise EncryptionNotConfiguredError(f"Invalid BRIDGEABLE_ENCRYPTION_KEY: {e}")


def encrypt_ssn(ssn_plaintext: str) -> bytes:
    """Encrypt an SSN (string, e.g. '123-45-6789' or '123456789')."""
    if not ssn_plaintext:
        return b""
    normalized = "".join(c for c in ssn_plaintext if c.isdigit())
    cipher = _get_cipher()
    return cipher.encrypt(normalized.encode("utf-8"))


def decrypt_ssn(ssn_encrypted: bytes | None) -> str | None:
    """Decrypt an encrypted SSN. Returns None if input is None/empty."""
    if not ssn_encrypted:
        return None
    cipher = _get_cipher()
    try:
        return cipher.decrypt(ssn_encrypted).decode("utf-8")
    except InvalidToken:
        return None


def ssn_last_four(ssn_plaintext: str | None) -> str | None:
    """Return last 4 digits for unencrypted display (UI mask)."""
    if not ssn_plaintext:
        return None
    digits = "".join(c for c in ssn_plaintext if c.isdigit())
    return digits[-4:] if len(digits) >= 4 else None


def mask_ssn_display(last_four: str | None) -> str:
    """Return 'XXX-XX-6789' format from last-four."""
    if not last_four or len(last_four) < 4:
        return "•••-••-••••"
    return f"•••-••-{last_four}"
