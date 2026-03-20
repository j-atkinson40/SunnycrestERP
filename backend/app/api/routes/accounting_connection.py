"""Accounting connection onboarding & management endpoints.

Handles the three-stage accounting connection flow:
  Stage 1 — Select software (or skip / send to accountant)
  Stage 2 — Connect (QBO OAuth, QBD Web Connector, Sage 100)
  Stage 3 — Configure sync settings & account mappings
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models.accounting_connection import AccountingConnection
from app.models.company import Company
from app.models.user import User
from app.services.onboarding_service import check_completion

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas (inline — small set, co-located with routes)
# ---------------------------------------------------------------------------


class ConnectionStatusResponse(BaseModel):
    id: str | None = None
    provider: str | None = None
    status: str  # not_started | connecting | connected | error | disconnected | skipped
    setup_stage: str | None = None
    qbo_company_name: str | None = None
    sage_version: str | None = None
    sage_connection_method: str | None = None
    sage_csv_schedule: str | None = None
    last_sync_at: str | None = None
    last_sync_status: str | None = None
    last_sync_error: str | None = None
    accountant_email: str | None = None
    accountant_name: str | None = None
    skip_count: int = 0
    skipped_at: str | None = None
    sync_config: dict | None = None
    account_mappings: dict | None = None


class SelectProviderRequest(BaseModel):
    provider: str  # quickbooks_online | quickbooks_desktop | sage_100


class SkipRequest(BaseModel):
    pass  # empty body — just POST to skip


class SendToAccountantRequest(BaseModel):
    email: str
    name: str | None = None
    message: str | None = None


class SageConfigRequest(BaseModel):
    version: str | None = None
    connection_method: str  # api | csv
    api_endpoint: str | None = None
    csv_schedule: str | None = None  # manual | daily | weekly


class SyncConfigRequest(BaseModel):
    sync_customers: bool = True
    sync_invoices: bool = True
    sync_payments: bool = True
    sync_inventory: bool = False


class AccountMappingsRequest(BaseModel):
    mappings: dict  # { internal_key: provider_account_id }


class CompleteSetupRequest(BaseModel):
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_or_create_connection(
    db: Session, company_id: str
) -> AccountingConnection:
    """Get existing connection or create a new one."""
    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == company_id)
        .first()
    )
    if not conn:
        conn = AccountingConnection(
            id=str(uuid.uuid4()),
            company_id=company_id,
            provider="",
            status="not_started",
            setup_stage="select_software",
        )
        db.add(conn)
        db.flush()
    return conn


def _to_response(conn: AccountingConnection) -> ConnectionStatusResponse:
    return ConnectionStatusResponse(
        id=conn.id,
        provider=conn.provider or None,
        status=conn.status,
        setup_stage=conn.setup_stage,
        qbo_company_name=conn.qbo_company_name,
        sage_version=conn.sage_version,
        sage_connection_method=conn.sage_connection_method,
        sage_csv_schedule=conn.sage_csv_schedule,
        last_sync_at=conn.last_sync_at.isoformat() if conn.last_sync_at else None,
        last_sync_status=conn.last_sync_status,
        last_sync_error=conn.last_sync_error,
        accountant_email=conn.accountant_email,
        accountant_name=conn.accountant_name,
        skip_count=conn.skip_count,
        skipped_at=conn.skipped_at.isoformat() if conn.skipped_at else None,
        sync_config=conn.sync_config,
        account_mappings=conn.account_mappings,
    )


# ---------------------------------------------------------------------------
# GET status
# ---------------------------------------------------------------------------


@router.get("/status", response_model=ConnectionStatusResponse)
def get_connection_status(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get the current accounting connection status."""
    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == current_user.company_id)
        .first()
    )
    if not conn:
        return ConnectionStatusResponse(status="not_started")
    return _to_response(conn)


# ---------------------------------------------------------------------------
# Stage 1 — Select provider
# ---------------------------------------------------------------------------


@router.post("/select-provider", response_model=ConnectionStatusResponse)
def select_provider(
    body: SelectProviderRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Select the accounting software provider."""
    valid = {"quickbooks_online", "quickbooks_desktop", "sage_100"}
    if body.provider not in valid:
        raise HTTPException(400, f"Invalid provider. Must be one of: {', '.join(valid)}")

    conn = _get_or_create_connection(db, current_user.company_id)
    conn.provider = body.provider
    conn.status = "connecting"
    conn.setup_stage = "connect"
    conn.updated_at = datetime.now(UTC)

    # Also set on company for existing provider factory
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company:
        provider_map = {
            "quickbooks_online": "quickbooks_online",
            "quickbooks_desktop": "quickbooks_desktop",
            "sage_100": "sage_csv",
        }
        company.accounting_provider = provider_map.get(body.provider, body.provider)

    db.commit()
    db.refresh(conn)
    return _to_response(conn)


# ---------------------------------------------------------------------------
# Stage 1 — Skip
# ---------------------------------------------------------------------------


@router.post("/skip", response_model=ConnectionStatusResponse)
def skip_accounting(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Skip accounting setup. Increments skip counter."""
    conn = _get_or_create_connection(db, current_user.company_id)
    conn.status = "skipped"
    conn.skip_count = (conn.skip_count or 0) + 1
    conn.skipped_at = datetime.now(UTC)
    conn.updated_at = datetime.now(UTC)

    # Store in company settings for banner logic
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company:
        company.set_setting("accounting_connection_status", "skipped")
        company.set_setting("accounting_skip_count", conn.skip_count)
        company.set_setting("accounting_skipped_at", conn.skipped_at.isoformat())

    db.commit()
    db.refresh(conn)
    return _to_response(conn)


# ---------------------------------------------------------------------------
# Stage 1 — Send to accountant
# ---------------------------------------------------------------------------


@router.post("/send-to-accountant", response_model=ConnectionStatusResponse)
def send_to_accountant(
    body: SendToAccountantRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Generate a 7-day token and store accountant info."""
    conn = _get_or_create_connection(db, current_user.company_id)
    conn.accountant_email = body.email
    conn.accountant_name = body.name
    conn.accountant_token = secrets.token_urlsafe(32)
    conn.accountant_token_expires_at = datetime.now(UTC) + timedelta(days=7)
    conn.status = "connecting"
    conn.setup_stage = "connect"
    conn.updated_at = datetime.now(UTC)

    # Store in company settings for banner logic
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company:
        company.set_setting("accounting_connection_status", "pending_accountant")
        company.set_setting("accounting_accountant_email", body.email)

    db.commit()
    db.refresh(conn)

    # TODO: Send email to accountant with setup link
    # For now, the token is generated and stored

    return _to_response(conn)


# ---------------------------------------------------------------------------
# Stage 2 — QBO connect (initiates OAuth)
# ---------------------------------------------------------------------------


@router.post("/qbo/connect")
def qbo_connect(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Generate QBO OAuth authorization URL."""
    conn = _get_or_create_connection(db, current_user.company_id)
    if conn.provider != "quickbooks_online":
        raise HTTPException(400, "Provider is not QuickBooks Online")

    try:
        from app.services.accounting.qbo_oauth_service import generate_auth_url

        url, state = generate_auth_url(current_user.company_id)
        return {"authorization_url": url, "state": state}
    except ImportError:
        # QBO OAuth service not available — return placeholder
        return {
            "authorization_url": f"/api/v1/accounting/qbo/callback?mock=true&company={current_user.company_id}",
            "state": secrets.token_urlsafe(16),
        }


@router.post("/qbo/connected", response_model=ConnectionStatusResponse)
def qbo_mark_connected(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Mark QBO as connected after OAuth callback succeeds."""
    conn = _get_or_create_connection(db, current_user.company_id)
    conn.status = "connected"
    conn.setup_stage = "configure_sync"
    conn.connected_by = current_user.id
    conn.connected_at = datetime.now(UTC)
    conn.updated_at = datetime.now(UTC)

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company:
        company.set_setting("accounting_connection_status", "connected")

    db.commit()
    db.refresh(conn)
    return _to_response(conn)


# ---------------------------------------------------------------------------
# Stage 2 — Sage 100 configuration
# ---------------------------------------------------------------------------


@router.post("/sage/configure", response_model=ConnectionStatusResponse)
def sage_configure(
    body: SageConfigRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Configure Sage 100 connection details."""
    conn = _get_or_create_connection(db, current_user.company_id)
    if conn.provider != "sage_100":
        raise HTTPException(400, "Provider is not Sage 100")

    conn.sage_version = body.version
    conn.sage_connection_method = body.connection_method
    conn.sage_api_endpoint = body.api_endpoint
    conn.sage_csv_schedule = body.csv_schedule
    conn.status = "connected"
    conn.setup_stage = "configure_sync"
    conn.connected_by = current_user.id
    conn.connected_at = datetime.now(UTC)
    conn.updated_at = datetime.now(UTC)

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company:
        company.set_setting("accounting_connection_status", "connected")
        if body.connection_method == "csv":
            company.accounting_provider = "sage_csv"
        else:
            company.accounting_provider = "sage_100"

    db.commit()
    db.refresh(conn)
    return _to_response(conn)


# ---------------------------------------------------------------------------
# Stage 3 — Sync configuration
# ---------------------------------------------------------------------------


@router.post("/sync-config", response_model=ConnectionStatusResponse)
def update_sync_config(
    body: SyncConfigRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update sync configuration toggles."""
    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == current_user.company_id)
        .first()
    )
    if not conn:
        raise HTTPException(404, "No accounting connection found")

    conn.sync_config = {
        "sync_customers": body.sync_customers,
        "sync_invoices": body.sync_invoices,
        "sync_payments": body.sync_payments,
        "sync_inventory": body.sync_inventory,
    }
    conn.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(conn)
    return _to_response(conn)


@router.post("/account-mappings", response_model=ConnectionStatusResponse)
def update_account_mappings(
    body: AccountMappingsRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update account mappings."""
    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == current_user.company_id)
        .first()
    )
    if not conn:
        raise HTTPException(404, "No accounting connection found")

    conn.account_mappings = body.mappings
    conn.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(conn)
    return _to_response(conn)


# ---------------------------------------------------------------------------
# Complete setup
# ---------------------------------------------------------------------------


@router.post("/complete", response_model=ConnectionStatusResponse)
def complete_setup(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Mark accounting setup as complete."""
    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == current_user.company_id)
        .first()
    )
    if not conn:
        raise HTTPException(404, "No accounting connection found")

    conn.setup_stage = "complete"
    conn.updated_at = datetime.now(UTC)

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company:
        company.set_setting("accounting_connection_status", "connected")

    # Mark checklist item as complete
    check_completion(db, current_user.company_id, "connect_accounting")

    db.commit()
    db.refresh(conn)
    return _to_response(conn)


# ---------------------------------------------------------------------------
# Disconnect
# ---------------------------------------------------------------------------


@router.post("/disconnect", response_model=ConnectionStatusResponse)
def disconnect(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Disconnect accounting provider."""
    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == current_user.company_id)
        .first()
    )
    if not conn:
        raise HTTPException(404, "No accounting connection found")

    conn.status = "disconnected"
    conn.setup_stage = "select_software"
    # Clear sensitive data
    conn.qbo_access_token_encrypted = None
    conn.qbo_refresh_token_encrypted = None
    conn.sage_api_key_encrypted = None
    conn.updated_at = datetime.now(UTC)

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company:
        company.set_setting("accounting_connection_status", "disconnected")
        company.accounting_provider = None

    db.commit()
    db.refresh(conn)
    return _to_response(conn)


# ---------------------------------------------------------------------------
# Dismiss skip banner (session-level, stored in company settings)
# ---------------------------------------------------------------------------


@router.post("/dismiss-banner")
def dismiss_banner(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Dismiss the accounting setup reminder banner for this session."""
    # This is actually tracked on the frontend via sessionStorage
    # But we provide an endpoint in case we want server-side tracking later
    return {"dismissed": True}
