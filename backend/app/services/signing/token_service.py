"""Signer token generation — Phase D-4.

Tokens are the sole auth mechanism for signer public routes. They must be:
- Cryptographically random (secrets module)
- Long enough to resist brute-forcing (256 bits = 43 chars base64)
- URL-safe (no slashes / padding)
- Unique across all envelopes (enforced by DB UNIQUE constraint)
"""

from __future__ import annotations

import secrets


def generate_signer_token() -> str:
    """Return a 256-bit URL-safe token."""
    return secrets.token_urlsafe(32)
