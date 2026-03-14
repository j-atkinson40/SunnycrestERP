"""API key management endpoints — admin only."""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.api_key import (
    AVAILABLE_SCOPES,
    ApiKeyCreate,
    ApiKeyCreatedResponse,
    ApiKeyResponse,
    ApiKeyUpdate,
    ApiKeyUsageResponse,
    ApiKeyUsageSummary,
)
from app.services import api_key_service

router = APIRouter()


def _to_response(api_key) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        scopes=json.loads(api_key.scopes) if isinstance(api_key.scopes, str) else api_key.scopes,
        rate_limit_per_minute=api_key.rate_limit_per_minute,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        is_active=api_key.is_active,
        created_by=api_key.created_by,
        created_at=api_key.created_at,
        updated_at=api_key.updated_at,
    )


@router.get("/scopes", response_model=list[str])
def list_available_scopes(
    _current_user: User = Depends(require_admin),
):
    """List all available API key scopes."""
    return AVAILABLE_SCOPES


@router.get("/", response_model=list[ApiKeyResponse])
def list_keys(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all API keys for the current tenant."""
    keys = api_key_service.list_api_keys(db, current_user.company_id)
    return [_to_response(k) for k in keys]


@router.post("/", response_model=ApiKeyCreatedResponse, status_code=201)
def create_key(
    body: ApiKeyCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new API key. The full key is only shown once."""
    # Validate scopes
    invalid = [s for s in body.scopes if s not in AVAILABLE_SCOPES and s != "*"]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scopes: {', '.join(invalid)}",
        )

    api_key, full_key = api_key_service.create_api_key(
        db=db,
        company_id=current_user.company_id,
        created_by=current_user.id,
        name=body.name,
        scopes=body.scopes,
        rate_limit_per_minute=body.rate_limit_per_minute,
        expires_at=body.expires_at,
    )

    return ApiKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        key=full_key,
        key_prefix=api_key.key_prefix,
        scopes=json.loads(api_key.scopes),
        rate_limit_per_minute=api_key.rate_limit_per_minute,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.get("/{key_id}", response_model=ApiKeyResponse)
def get_key(
    key_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get a specific API key."""
    api_key = api_key_service.get_api_key(db, key_id, current_user.company_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    return _to_response(api_key)


@router.patch("/{key_id}", response_model=ApiKeyResponse)
def update_key(
    key_id: str,
    body: ApiKeyUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update an API key (name, scopes, rate limit, expiry, active status)."""
    api_key = api_key_service.get_api_key(db, key_id, current_user.company_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    if body.scopes is not None:
        invalid = [s for s in body.scopes if s not in AVAILABLE_SCOPES and s != "*"]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid scopes: {', '.join(invalid)}",
            )

    updated = api_key_service.update_api_key(
        db=db,
        api_key=api_key,
        name=body.name,
        scopes=body.scopes,
        rate_limit_per_minute=body.rate_limit_per_minute,
        expires_at=body.expires_at,
        is_active=body.is_active,
    )
    return _to_response(updated)


@router.post("/{key_id}/revoke", response_model=ApiKeyResponse)
def revoke_key(
    key_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Revoke (deactivate) an API key."""
    api_key = api_key_service.get_api_key(db, key_id, current_user.company_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key_service.revoke_api_key(db, api_key)
    return _to_response(api_key)


@router.delete("/{key_id}", status_code=204)
def delete_key(
    key_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Permanently delete an API key and its usage history."""
    api_key = api_key_service.get_api_key(db, key_id, current_user.company_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key_service.delete_api_key(db, api_key)


@router.get("/{key_id}/usage", response_model=ApiKeyUsageSummary)
def get_key_usage(
    key_id: str,
    hours: int = 24,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get usage statistics for an API key."""
    api_key = api_key_service.get_api_key(db, key_id, current_user.company_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    usage_rows = api_key_service.get_usage_stats(db, key_id, hours)
    summary = api_key_service.get_usage_summary(db, key_id)

    return ApiKeyUsageSummary(
        api_key_id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        total_requests_24h=summary["total_requests_24h"],
        total_errors_24h=summary["total_errors_24h"],
        last_used_at=api_key.last_used_at,
        hourly=[
            ApiKeyUsageResponse(
                hour=u.hour_bucket,
                request_count=u.request_count,
                error_count=u.error_count,
            )
            for u in usage_rows
        ],
    )
