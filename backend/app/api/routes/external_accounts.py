"""External Accounts API — store and manage encrypted credentials for
third-party services used by Playwright workflow automations.

All credential values are encrypted at rest (Fernet). This API never
returns raw credential values — only metadata (which fields are saved,
last verification timestamp, etc.).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services import credential_service
from app.services.playwright_scripts import list_scripts

router = APIRouter()


# ─────────────────────────────────────────────────────────── Schemas

class StoreCredentialsRequest(BaseModel):
    service_name: str          # Human-readable, e.g. "Uline"
    service_key: str           # Machine key, e.g. "uline"
    credentials: dict[str, str]  # e.g. {"username": "me@co.com", "password": "s3cret"}


class UpdateCredentialsRequest(BaseModel):
    credentials: dict[str, str]


# ─────────────────────────────────────────────────────────── Endpoints

@router.get("", response_model=list[dict[str, Any]])
def list_external_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all configured external accounts for this tenant (no credential values)."""
    accounts = credential_service.list_accounts(db, company_id=current_user.company_id)
    return [credential_service.serialize(a) for a in accounts]


@router.get("/available-scripts", response_model=list[dict])
def available_scripts(
    current_user: User = Depends(get_current_user),
):
    """Return metadata for all registered Playwright scripts (for UI dropdowns)."""
    return list_scripts()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def store_credentials(
    body: StoreCredentialsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update encrypted credentials for a service.

    Existing credentials for the same (company, service_key) pair are
    overwritten. The ``last_verified_at`` timestamp is cleared on update.
    """
    if not body.credentials:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="credentials dict must not be empty",
        )
    account = credential_service.store_credentials(
        db,
        company_id=current_user.company_id,
        service_key=body.service_key,
        service_name=body.service_name,
        credentials=body.credentials,
        created_by_user_id=current_user.id,
    )
    return credential_service.serialize(account)


@router.post("/{account_id}/verify", response_model=dict[str, Any])
def verify_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark an account as verified (stamps last_verified_at = now).

    Full credential verification against the live service is done by the
    Playwright script itself — this endpoint just stamps the timestamp
    so the UI can show when it was last confirmed working.
    """
    from app.models.tenant_external_account import TenantExternalAccount

    account = (
        db.query(TenantExternalAccount)
        .filter(
            TenantExternalAccount.id == account_id,
            TenantExternalAccount.company_id == current_user.company_id,
            TenantExternalAccount.is_active.is_(True),
        )
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    ok = credential_service.mark_verified(
        db, company_id=current_user.company_id, service_key=account.service_key
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Account not found")
    db.refresh(account)
    return credential_service.serialize(account)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-delete an external account (credentials remain encrypted but inactive)."""
    from app.models.tenant_external_account import TenantExternalAccount

    account = (
        db.query(TenantExternalAccount)
        .filter(
            TenantExternalAccount.id == account_id,
            TenantExternalAccount.company_id == current_user.company_id,
            TenantExternalAccount.is_active.is_(True),
        )
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    credential_service.soft_delete(db, account=account)
