"""API routes for feature flag management."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.feature_flag import (
    BulkFlagSet,
    FeatureFlagCreate,
    FeatureFlagDetail,
    FeatureFlagResponse,
    FeatureFlagUpdate,
    PaginatedFlagAuditLogs,
    TenantFeatureFlagResponse,
    TenantFeatureFlagSet,
    TenantFlagMatrix,
    TenantFlagOverride,
    UserFeatureFlags,
)
from app.services import feature_flag_service

router = APIRouter()


# ---------------------------------------------------------------------------
# User-facing endpoint — returns resolved flags for the current tenant
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserFeatureFlags)
def get_my_flags(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all resolved feature flags for the current user's tenant."""
    flags = feature_flag_service.get_all_flags_for_tenant(db, current_user.company_id)
    return {"flags": flags}


# ---------------------------------------------------------------------------
# Admin endpoints — CRUD on flags + tenant overrides
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[FeatureFlagResponse])
def list_flags(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all feature flag definitions (admin only)."""
    return feature_flag_service.get_all_flags(db)


@router.post("/", response_model=FeatureFlagResponse, status_code=201)
def create_flag(
    data: FeatureFlagCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new feature flag (admin only)."""
    existing = feature_flag_service.get_flag_by_key(db, data.key)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Flag with key '{data.key}' already exists",
        )
    return feature_flag_service.create_flag(db, data.model_dump())


@router.get("/matrix", response_model=TenantFlagMatrix)
def get_matrix(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get tenant x flag toggle matrix (admin only)."""
    return feature_flag_service.get_flag_matrix(db)


@router.get("/audit-logs", response_model=PaginatedFlagAuditLogs)
def get_audit_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    flag_key: str | None = Query(None),
    tenant_id: str | None = Query(None),
    action: str | None = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get feature flag audit logs (admin only)."""
    return feature_flag_service.get_audit_logs(
        db, page=page, per_page=per_page,
        flag_key=flag_key, tenant_id=tenant_id, action=action,
    )


@router.get("/{flag_id}", response_model=FeatureFlagDetail)
def get_flag(
    flag_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get a feature flag with all tenant overrides (admin only)."""
    from app.models.company import Company
    from app.models.tenant_feature_flag import TenantFeatureFlag

    flag = db.query(feature_flag_service.FeatureFlag).filter(
        feature_flag_service.FeatureFlag.id == flag_id
    ).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")

    overrides_raw = (
        db.query(TenantFeatureFlag, Company.name)
        .join(Company, TenantFeatureFlag.tenant_id == Company.id)
        .filter(TenantFeatureFlag.flag_id == flag_id)
        .all()
    )
    overrides = [
        TenantFlagOverride(
            tenant_id=o.tenant_id,
            tenant_name=name,
            enabled=o.enabled,
            notes=o.notes,
            updated_at=o.updated_at,
        )
        for o, name in overrides_raw
    ]

    return FeatureFlagDetail(
        id=flag.id,
        key=flag.key,
        name=flag.name,
        description=flag.description,
        category=flag.category,
        default_enabled=flag.default_enabled,
        is_global=flag.is_global,
        created_at=flag.created_at,
        updated_at=flag.updated_at,
        overrides=overrides,
    )


@router.patch("/{flag_id}", response_model=FeatureFlagResponse)
def update_flag(
    flag_id: str,
    data: FeatureFlagUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a feature flag definition (admin only)."""
    updated = feature_flag_service.update_flag(
        db, flag_id, data.model_dump(exclude_unset=True)
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Flag not found")
    return updated


@router.delete("/{flag_id}", status_code=204)
def delete_flag(
    flag_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a feature flag and all overrides (admin only)."""
    if not feature_flag_service.delete_flag(db, flag_id):
        raise HTTPException(status_code=404, detail="Flag not found")


# ---------------------------------------------------------------------------
# Tenant override management
# ---------------------------------------------------------------------------


@router.put("/{flag_id}/tenants/{tenant_id}")
def set_tenant_flag(
    flag_id: str,
    tenant_id: str,
    data: TenantFeatureFlagSet,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Set a feature flag override for a specific tenant (admin only)."""
    override = feature_flag_service.set_flag_for_tenant(
        db, tenant_id, flag_id, data.enabled,
        notes=data.notes, actor_id=current_user.id,
    )
    return {
        "id": override.id,
        "tenant_id": override.tenant_id,
        "flag_id": override.flag_id,
        "enabled": override.enabled,
        "notes": override.notes,
    }


@router.delete("/{flag_id}/tenants/{tenant_id}", status_code=204)
def remove_tenant_flag(
    flag_id: str,
    tenant_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Remove a tenant's flag override (falls back to default)."""
    feature_flag_service.remove_override(
        db, tenant_id, flag_id, actor_id=current_user.id,
    )


@router.post("/{flag_id}/bulk")
def bulk_set_flag(
    flag_id: str,
    data: BulkFlagSet,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Set a flag for multiple tenants at once (admin only)."""
    count = feature_flag_service.bulk_set_flag(
        db, flag_id, data.tenant_ids, data.enabled,
        actor_id=current_user.id,
    )
    return {"updated": count}
