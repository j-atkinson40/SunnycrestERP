"""Phase R-6.2b — Cloudflare Turnstile CAPTCHA verification.

Backend verification site for the intake adapter substrate. The
frontend renders the Turnstile widget below intake form fields; the
token from the widget travels in the request body to /submit,
/presign, /complete endpoints. This module verifies the token against
Cloudflare's siteverify API.

Graceful-degradation discipline (mirrors R-6.2a.1's R2-optional
pattern):

  - Missing TURNSTILE_SECRET_KEY in non-production: log warning +
    return True (allow). Keeps local dev + CI flows usable when
    Turnstile keys aren't provisioned.

  - Missing TURNSTILE_SECRET_KEY in production: raise
    CaptchaConfigurationError. Prevents silent insecurity — if
    Turnstile is supposed to be active and isn't configured, fail
    loudly so ops notices.

  - Verification failure (Cloudflare returns success=False or
    network error): raise CaptchaVerificationError.

Architectural pattern locked (CLAUDE.md §4):
  CAPTCHA backend verification mirrors R-6.2a.1 graceful-degradation
  pattern (dev-friendly absent; production-strict).
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings


logger = logging.getLogger(__name__)


_TURNSTILE_VERIFY_URL = (
    "https://challenges.cloudflare.com/turnstile/v0/siteverify"
)
_VERIFY_TIMEOUT_SECONDS = 5.0


class CaptchaError(Exception):
    """Base — carries http_status for FastAPI translation."""

    http_status: int = 400


class CaptchaConfigurationError(CaptchaError):
    """Production deployment missing TURNSTILE_SECRET_KEY."""

    http_status: int = 500


class CaptchaVerificationError(CaptchaError):
    """Token absent, malformed, or rejected by Cloudflare."""

    http_status: int = 403


def verify_turnstile_token(
    token: str | None,
    *,
    ip_address: str | None = None,
    environment: str | None = None,
) -> bool:
    """Verify a Turnstile token against Cloudflare's siteverify API.

    Returns True on success. Raises ``CaptchaVerificationError`` on
    explicit failure, ``CaptchaConfigurationError`` on missing secret
    in production.

    Args:
        token: Turnstile token from the frontend widget. None means
            the frontend didn't render the widget OR the user didn't
            complete the challenge.
        ip_address: Remote client IP for Cloudflare's optional
            remoteip check. Pass None when unknown — Cloudflare
            handles it.
        environment: Environment string ("production" / "staging" /
            "dev"). Defaults to settings.ENVIRONMENT — surface
            override exists for testability.

    Raises:
        CaptchaConfigurationError: secret missing in production.
        CaptchaVerificationError: token invalid OR Cloudflare rejects.
    """
    env = environment if environment is not None else settings.ENVIRONMENT
    secret = settings.TURNSTILE_SECRET_KEY

    if not secret:
        # Graceful degradation in non-production. Mirror of R-6.2a.1
        # R2-optional pattern: development workflows shouldn't be
        # blocked by missing infrastructure secrets.
        if env == "production":
            raise CaptchaConfigurationError(
                "TURNSTILE_SECRET_KEY is required in production. "
                "Set it in the Railway dashboard before serving "
                "public intake traffic."
            )
        logger.warning(
            "[captcha] TURNSTILE_SECRET_KEY unset in environment=%r; "
            "allowing submission. Set the key before deploying to "
            "production.",
            env,
        )
        return True

    if not token:
        raise CaptchaVerificationError(
            "CAPTCHA verification required. Please complete the "
            "challenge before submitting."
        )

    payload: dict[str, str] = {"secret": secret, "response": token}
    if ip_address:
        payload["remoteip"] = ip_address

    try:
        with httpx.Client(timeout=_VERIFY_TIMEOUT_SECONDS) as client:
            response = client.post(_TURNSTILE_VERIFY_URL, data=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.exception(
            "[captcha] Turnstile siteverify HTTP error: %s", exc
        )
        raise CaptchaVerificationError(
            "CAPTCHA verification service unavailable. Please retry."
        ) from exc

    if not isinstance(data, dict) or data.get("success") is not True:
        error_codes = (
            data.get("error-codes", []) if isinstance(data, dict) else []
        )
        logger.warning(
            "[captcha] Turnstile rejected token: error_codes=%s",
            error_codes,
        )
        raise CaptchaVerificationError(
            "CAPTCHA verification failed. Please try again."
        )

    return True
