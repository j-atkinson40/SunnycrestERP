"""Accounting integration endpoints.

Unified accounting provider management — provider selection, connection status,
sync operations, chart of accounts, and account mapping.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.accounting import (
    AccountingConfigResponse,
    AccountingProviderInfo,
    AccountingProviderUpdate,
    AccountMappingResponse,
    AccountMappingUpdate,
    ProviderAccountResponse,
    SyncRequest,
    SyncResultResponse,
)
from app.services.accounting.factory import get_available_providers, get_provider

router = APIRouter()


# ---------------------------------------------------------------------------
# Provider management
# ---------------------------------------------------------------------------


@router.get("/providers", response_model=list[AccountingProviderInfo])
def list_providers(
    _current_user: User = Depends(require_admin),
):
    """List all available accounting providers."""
    return get_available_providers()


@router.get("/status", response_model=AccountingConfigResponse)
def get_status(
    current_user: User = Depends(require_permission("company.view")),
    db: Session = Depends(get_db),
):
    """Get current accounting provider status and connection health."""
    provider = get_provider(db, current_user.company_id, current_user.id)
    status = provider.get_connection_status()
    return AccountingConfigResponse(
        provider=status.provider,
        connected=status.connected,
        last_sync_at=status.last_sync_at,
        error=status.error,
        details=status.details,
    )


@router.post("/test", response_model=AccountingConfigResponse)
def test_connection(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Actively test the accounting provider connection."""
    provider = get_provider(db, current_user.company_id, current_user.id)
    status = provider.test_connection()
    return AccountingConfigResponse(
        provider=status.provider,
        connected=status.connected,
        last_sync_at=status.last_sync_at,
        error=status.error,
        details=status.details,
    )


@router.patch("/provider", response_model=AccountingConfigResponse)
def set_provider(
    body: AccountingProviderUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Switch the accounting provider for the current tenant."""
    from app.models.company import Company

    valid_providers = [p["key"] for p in get_available_providers()]
    if body.provider not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider. Must be one of: {', '.join(valid_providers)}",
        )

    company = (
        db.query(Company).filter(Company.id == current_user.company_id).first()
    )
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    company.accounting_provider = body.provider
    db.commit()

    provider = get_provider(db, current_user.company_id, current_user.id)
    status = provider.get_connection_status()
    return AccountingConfigResponse(
        provider=status.provider,
        connected=status.connected,
        last_sync_at=status.last_sync_at,
        error=status.error,
        details=status.details,
    )


# ---------------------------------------------------------------------------
# Sync operations
# ---------------------------------------------------------------------------


@router.post("/sync", response_model=SyncResultResponse)
def run_sync(
    body: SyncRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Run a sync operation with the configured accounting provider."""
    provider = get_provider(db, current_user.company_id, current_user.id)

    sync_map = {
        "customers": lambda: provider.sync_customers(direction=body.direction),
        "invoices": lambda: provider.sync_invoices(body.date_from, body.date_to),
        "payments": lambda: provider.sync_payments(body.date_from, body.date_to),
        "bills": lambda: provider.sync_bills(body.date_from, body.date_to),
        "bill_payments": lambda: provider.sync_bill_payments(body.date_from, body.date_to),
        "inventory": lambda: provider.sync_inventory_transactions(body.date_from, body.date_to),
    }

    sync_fn = sync_map.get(body.sync_type)
    if not sync_fn:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sync_type. Must be one of: {', '.join(sync_map.keys())}",
        )

    result = sync_fn()
    return SyncResultResponse(
        success=result.success,
        records_synced=result.records_synced,
        records_failed=result.records_failed,
        sync_log_id=result.sync_log_id,
        error_message=result.error_message,
        details=result.details,
    )


# ---------------------------------------------------------------------------
# Chart of accounts & mappings
# ---------------------------------------------------------------------------


@router.get("/chart-of-accounts", response_model=list[ProviderAccountResponse])
def get_chart_of_accounts(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Fetch chart of accounts from the provider."""
    provider = get_provider(db, current_user.company_id, current_user.id)
    accounts = provider.get_chart_of_accounts()
    return [
        ProviderAccountResponse(
            id=a.id, name=a.name, account_type=a.account_type,
            number=a.number, is_active=a.is_active,
        )
        for a in accounts
    ]


@router.get("/mappings", response_model=list[AccountMappingResponse])
def get_mappings(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get account mappings between internal and provider accounts."""
    provider = get_provider(db, current_user.company_id, current_user.id)
    mappings = provider.get_account_mappings()
    return [
        AccountMappingResponse(
            internal_id=m.internal_id, internal_name=m.internal_name,
            provider_id=m.provider_id, provider_name=m.provider_name,
        )
        for m in mappings
    ]


@router.put("/mappings", response_model=AccountMappingResponse)
def set_mapping(
    body: AccountMappingUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Set an account mapping."""
    provider = get_provider(db, current_user.company_id, current_user.id)
    mapping = provider.set_account_mapping(body.internal_id, body.provider_id)
    return AccountMappingResponse(
        internal_id=mapping.internal_id,
        internal_name=mapping.internal_name,
        provider_id=mapping.provider_id,
        provider_name=mapping.provider_name,
    )


# ---------------------------------------------------------------------------
# QuickBooks Online OAuth flow — RETIRED (the QBO decommission, 2026-07-18)
#
# The oauth service + provider are DELETED and r134 purged the plaintext
# credentials from accounting_config. These endpoints answer honestly
# rather than erroring into a void; Intuit-side revocation is the
# operator's parallel step.
# ---------------------------------------------------------------------------

RETIRED_QBO = "QBO integration is retired — Bridgeable is the accounting system."


@router.post("/qbo/connect")
def qbo_connect(current_user: User = Depends(require_admin)):
    """RETIRED — the QBO decommission."""
    raise HTTPException(status_code=410, detail=RETIRED_QBO)


@router.get("/qbo/callback")
def qbo_callback():
    """RETIRED — the QBO decommission."""
    raise HTTPException(status_code=410, detail=RETIRED_QBO)


@router.post("/qbo/disconnect")
def qbo_disconnect(current_user: User = Depends(require_admin)):
    """RETIRED — tokens were purged by r134; nothing remains to revoke
    platform-side."""
    raise HTTPException(status_code=410, detail=RETIRED_QBO)
