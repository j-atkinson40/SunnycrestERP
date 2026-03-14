"""QuickBooks Online OAuth 2.0 flow management.

Handles authorization URL generation, callback processing, and token storage.
"""

import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.config import settings

# QBO OAuth endpoints
QBO_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
QBO_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
QBO_REVOKE_URL = "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"

# Required scopes
QBO_SCOPES = "com.intuit.quickbooks.accounting"


def _get_qbo_credentials() -> tuple[str, str, str]:
    """Get QBO client credentials from environment."""
    # These would be in .env — placeholder keys here
    client_id = getattr(settings, "QBO_CLIENT_ID", "")
    client_secret = getattr(settings, "QBO_CLIENT_SECRET", "")
    redirect_uri = getattr(settings, "QBO_REDIRECT_URI", "")
    return client_id, client_secret, redirect_uri


def generate_auth_url(company_id: str) -> tuple[str, str]:
    """Generate QBO OAuth authorization URL.

    Returns (authorization_url, state_token).
    """
    client_id, _, redirect_uri = _get_qbo_credentials()
    state = f"{company_id}:{secrets.token_urlsafe(16)}"

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": QBO_SCOPES,
        "state": state,
    }

    url = f"{QBO_AUTH_URL}?{urlencode(params)}"
    return url, state


def handle_callback(
    db: Session,
    code: str,
    state: str,
    realm_id: str,
) -> dict:
    """Exchange authorization code for tokens and store them.

    Returns dict with success status and company info.
    """
    import requests

    client_id, client_secret, redirect_uri = _get_qbo_credentials()

    # Parse company_id from state
    parts = state.split(":", 1)
    if len(parts) != 2:
        return {"success": False, "error": "Invalid state parameter"}
    company_id = parts[0]

    # Exchange code for tokens
    resp = requests.post(
        QBO_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        auth=(client_id, client_secret),
        timeout=15,
    )

    if resp.status_code != 200:
        return {"success": False, "error": f"Token exchange failed: {resp.text}"}

    token_data = resp.json()
    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(seconds=token_data.get("expires_in", 3600))
    ).isoformat()

    # Store tokens in company's accounting_config
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return {"success": False, "error": "Company not found"}

    try:
        config = json.loads(company.accounting_config or "{}")
    except (json.JSONDecodeError, TypeError):
        config = {}

    config.update({
        "qbo_client_id": client_id,
        "qbo_client_secret": client_secret,
        "qbo_realm_id": realm_id,
        "qbo_access_token": token_data["access_token"],
        "qbo_refresh_token": token_data.get("refresh_token", ""),
        "qbo_token_expires_at": expires_at,
        "qbo_environment": "production",  # Determined by realm
        "qbo_connected_at": datetime.now(timezone.utc).isoformat(),
    })

    company.accounting_provider = "quickbooks_online"
    company.accounting_config = json.dumps(config)
    db.commit()

    return {
        "success": True,
        "company_id": company_id,
        "realm_id": realm_id,
    }


def disconnect(db: Session, company_id: str) -> dict:
    """Disconnect QBO — revoke tokens and clear config."""
    import requests

    from app.models.company import Company

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return {"success": False, "error": "Company not found"}

    try:
        config = json.loads(company.accounting_config or "{}")
    except (json.JSONDecodeError, TypeError):
        config = {}

    # Attempt to revoke the token (best effort)
    refresh_token = config.get("qbo_refresh_token")
    if refresh_token:
        client_id = config.get("qbo_client_id", "")
        client_secret = config.get("qbo_client_secret", "")
        try:
            requests.post(
                QBO_REVOKE_URL,
                json={"token": refresh_token},
                auth=(client_id, client_secret),
                timeout=10,
            )
        except Exception:
            pass  # Best effort

    # Clear QBO-specific config but keep other settings
    for key in list(config.keys()):
        if key.startswith("qbo_"):
            del config[key]

    company.accounting_provider = "sage_csv"  # Revert to default
    company.accounting_config = json.dumps(config) if config else None
    db.commit()

    return {"success": True}
