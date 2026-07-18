"""The Plaid API client (B-1) — thin, env-driven, honest about errors.

httpx-direct (the platform's existing HTTP dependency) against Plaid's
JSON-POST API — no SDK. Base URL from ``PLAID_ENV`` (sandbox default);
credentials from ``PLAID_CLIENT_ID`` / ``PLAID_SECRET`` (env only, set by
the operator in Railway + dev .env — never the repo).

ERROR HONESTY: Plaid failures raise ``PlaidApiError`` carrying
``error_code`` / ``error_type`` / ``request_id`` — legible, never
swallowed. LOGGING DISCIPLINE: this module logs error_code + request_id
ONLY — never wholesale response bodies (they can echo request context;
the qbo_provider ``resp.text`` pattern is the documented mistake), and
never any token.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE_URLS = {
    "sandbox": "https://sandbox.plaid.com",
    "production": "https://production.plaid.com",
}
_TIMEOUT = 30.0


class PlaidNotConfiguredError(RuntimeError):
    """PLAID_CLIENT_ID / PLAID_SECRET absent — surface, don't guess."""


class PlaidApiError(RuntimeError):
    """A Plaid API error, carried legibly."""

    def __init__(self, *, status: int, error_type: str, error_code: str,
                 display_message: str | None, request_id: str | None):
        self.status = status
        self.error_type = error_type
        self.error_code = error_code
        self.display_message = display_message
        self.request_id = request_id
        super().__init__(f"Plaid {error_type}/{error_code} (request {request_id})")


def _base_url() -> str:
    env = (settings.PLAID_ENV or "sandbox").lower()
    if env not in _BASE_URLS:
        raise PlaidNotConfiguredError(
            f"PLAID_ENV={env!r} is not one of {sorted(_BASE_URLS)}"
        )
    return _BASE_URLS[env]


def _post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    if not settings.PLAID_CLIENT_ID or not settings.PLAID_SECRET:
        raise PlaidNotConfiguredError(
            "PLAID_CLIENT_ID / PLAID_SECRET are not set — the operator sets "
            "them in backend/.env (dev) and Railway Variables (staging)."
        )
    payload = {
        "client_id": settings.PLAID_CLIENT_ID,
        "secret": settings.PLAID_SECRET,
        **body,
    }
    resp = httpx.post(f"{_base_url()}{path}", json=payload, timeout=_TIMEOUT)
    if resp.status_code != 200:
        try:
            err = resp.json()
        except Exception:  # noqa: BLE001 — non-JSON error body
            err = {}
        error_code = err.get("error_code", "UNKNOWN")
        request_id = err.get("request_id")
        # error_code + request_id ONLY — never the body, never a token.
        logger.warning(
            "Plaid %s failed: %s/%s (request %s)",
            path, err.get("error_type", "HTTP_%d" % resp.status_code),
            error_code, request_id,
        )
        raise PlaidApiError(
            status=resp.status_code,
            error_type=err.get("error_type", f"HTTP_{resp.status_code}"),
            error_code=error_code,
            display_message=err.get("display_message"),
            request_id=request_id,
        )
    return resp.json()


# ── The B-1 surface (link + exchange + accounts) ────────────────────────


def create_link_token(*, client_user_id: str, client_name: str = "Bridgeable",
                      access_token: str | None = None) -> dict[str, Any]:
    """link/token/create. Pass ``access_token`` for UPDATE MODE (re-auth
    of a degraded item — §3's reconnect path)."""
    body: dict[str, Any] = {
        "user": {"client_user_id": client_user_id},
        "client_name": client_name,
        "language": "en",
        "country_codes": ["US"],
    }
    if access_token:
        body["access_token"] = access_token  # update mode: no products key
    else:
        body["products"] = ["transactions"]
    return _post("/link/token/create", body)


def exchange_public_token(public_token: str) -> dict[str, Any]:
    """item/public_token/exchange → {access_token, item_id, request_id}."""
    return _post("/item/public_token/exchange", {"public_token": public_token})


def get_accounts(access_token: str) -> dict[str, Any]:
    """accounts/get → {accounts: [...], item: {institution_id, ...}}."""
    return _post("/accounts/get", {"access_token": access_token})


def sync_transactions(access_token: str, cursor: str | None,
                      count: int = 500) -> dict[str, Any]:
    """transactions/sync — one page. Returns {added, modified, removed,
    next_cursor, has_more}. Cursor None/"" = full-history bootstrap."""
    body: dict[str, Any] = {"access_token": access_token, "count": count}
    if cursor:
        body["cursor"] = cursor
    return _post("/transactions/sync", body)


def get_institution(institution_id: str) -> dict[str, Any]:
    """institutions/get_by_id → {institution: {name, ...}}."""
    return _post(
        "/institutions/get_by_id",
        {"institution_id": institution_id, "country_codes": ["US"]},
    )
