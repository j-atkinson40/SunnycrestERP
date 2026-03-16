"""Platform admin — cross-tenant feature flag management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_platform_role
from app.database import get_db
from app.models.platform_user import PlatformUser

router = APIRouter()


@router.get("/")
def list_all_flags(
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
):
    """List all feature flags with per-tenant overrides (matrix view)."""
    from app.models.company import Company
    from app.models.feature_flag import FeatureFlag
    from app.models.tenant_feature_flag import TenantFeatureFlag

    flags = db.query(FeatureFlag).order_by(FeatureFlag.key).all()
    companies = db.query(Company).filter(Company.is_active.is_(True)).order_by(Company.name).all()
    overrides = db.query(TenantFeatureFlag).all()

    # Build a lookup: (company_id, flag_id) -> enabled
    override_map = {}
    for o in overrides:
        override_map[(o.company_id, o.flag_id)] = o.enabled

    result = []
    for flag in flags:
        tenants = []
        for c in companies:
            key = (c.id, flag.id)
            if key in override_map:
                tenant_enabled = override_map[key]
            else:
                tenant_enabled = flag.enabled_by_default
            tenants.append({
                "tenant_id": c.id,
                "tenant_name": c.name,
                "enabled": tenant_enabled,
                "has_override": key in override_map,
            })
        result.append({
            "id": flag.id,
            "key": flag.key,
            "description": flag.description,
            "enabled_by_default": flag.enabled_by_default,
            "tenants": tenants,
        })

    return result


@router.put("/{flag_id}/tenants/{tenant_id}")
def set_tenant_flag(
    flag_id: str,
    tenant_id: str,
    data: dict,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Set a feature flag for a specific tenant."""
    from app.models.feature_flag import FeatureFlag
    from app.models.tenant_feature_flag import TenantFeatureFlag

    flag = db.query(FeatureFlag).filter(FeatureFlag.id == flag_id).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")

    enabled = data.get("enabled")
    if enabled is None:
        raise HTTPException(status_code=422, detail="'enabled' field required")

    override = (
        db.query(TenantFeatureFlag)
        .filter(
            TenantFeatureFlag.flag_id == flag_id,
            TenantFeatureFlag.company_id == tenant_id,
        )
        .first()
    )

    if override:
        override.enabled = enabled
    else:
        override = TenantFeatureFlag(
            flag_id=flag_id,
            company_id=tenant_id,
            enabled=enabled,
        )
        db.add(override)

    db.commit()
    return {"flag_id": flag_id, "tenant_id": tenant_id, "enabled": enabled}


@router.delete("/{flag_id}/tenants/{tenant_id}")
def remove_tenant_flag_override(
    flag_id: str,
    tenant_id: str,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Remove a tenant-specific override so the flag falls back to the default."""
    from app.models.tenant_feature_flag import TenantFeatureFlag

    override = (
        db.query(TenantFeatureFlag)
        .filter(
            TenantFeatureFlag.flag_id == flag_id,
            TenantFeatureFlag.company_id == tenant_id,
        )
        .first()
    )
    if not override:
        raise HTTPException(status_code=404, detail="Override not found")

    db.delete(override)
    db.commit()
    return {"detail": "Override removed"}
