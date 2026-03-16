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
        override_map[(o.tenant_id, o.flag_id)] = o.enabled

    result = []
    for flag in flags:
        tenants = []
        for c in companies:
            key = (c.id, flag.id)
            if key in override_map:
                tenant_enabled = override_map[key]
            else:
                tenant_enabled = flag.default_enabled
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
            "enabled_by_default": flag.default_enabled,
            "tenants": tenants,
        })

    return result


@router.post("/", status_code=201)
def create_flag(
    data: dict,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Create a new feature flag."""
    from app.models.feature_flag import FeatureFlag

    key = data.get("key", "").strip()
    if not key:
        raise HTTPException(status_code=422, detail="'key' is required")

    existing = db.query(FeatureFlag).filter(FeatureFlag.key == key).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Flag '{key}' already exists")

    flag = FeatureFlag(
        key=key,
        name=data.get("name", key),
        description=data.get("description", ""),
        category=data.get("category", "general"),
        default_enabled=data.get("default_enabled", False),
        is_global=data.get("is_global", False),
    )
    db.add(flag)
    db.commit()
    db.refresh(flag)
    return {
        "id": flag.id,
        "key": flag.key,
        "name": flag.name,
        "description": flag.description,
        "category": flag.category,
        "default_enabled": flag.default_enabled,
        "is_global": flag.is_global,
    }


@router.delete("/{flag_id}")
def delete_flag(
    flag_id: str,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Delete a feature flag and all its tenant overrides."""
    from app.models.feature_flag import FeatureFlag
    from app.models.tenant_feature_flag import TenantFeatureFlag

    flag = db.query(FeatureFlag).filter(FeatureFlag.id == flag_id).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")

    # Remove all tenant overrides first
    db.query(TenantFeatureFlag).filter(
        TenantFeatureFlag.flag_id == flag_id
    ).delete()
    db.delete(flag)
    db.commit()
    return {"detail": "Flag deleted"}


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
            TenantFeatureFlag.tenant_id == tenant_id,
        )
        .first()
    )

    if override:
        override.enabled = enabled
    else:
        override = TenantFeatureFlag(
            flag_id=flag_id,
            tenant_id=tenant_id,
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
            TenantFeatureFlag.tenant_id == tenant_id,
        )
        .first()
    )
    if not override:
        raise HTTPException(status_code=404, detail="Override not found")

    db.delete(override)
    db.commit()
    return {"detail": "Override removed"}
