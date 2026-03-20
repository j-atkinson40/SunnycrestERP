"""Platform admin — extension registry management."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_platform_role
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services import extension_service

router = APIRouter()


class EnableExtensionRequest(BaseModel):
    extension_key: str
    config: dict | None = None


class UpdateConfigRequest(BaseModel):
    config: dict


# ── Legacy tenant management endpoints ──


@router.get("/definitions")
def list_extension_definitions(
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
):
    """Full registry management — all extensions including inactive."""
    exts = extension_service.admin_list_extensions(db)
    return [
        {
            "id": e.id,
            "extension_key": e.extension_key,
            "module_key": e.module_key,
            "display_name": e.display_name,
            "tagline": e.tagline,
            "description": e.description,
            "section": e.section,
            "category": e.category,
            "publisher": e.publisher,
            "applicable_verticals": e.applicable_verticals_list,
            "default_enabled_for": e.default_enabled_for_list,
            "access_model": e.access_model,
            "status": e.status,
            "version": e.version,
            "feature_bullets": e.feature_bullets_list,
            "setup_required": e.setup_required,
            "is_customer_requested": e.is_customer_requested,
            "notify_me_count": e.notify_me_count or 0,
            "sort_order": e.sort_order,
            "config_schema": e.schema_dict,
            "is_active": e.is_active,
            "created_at": e.created_at,
            "updated_at": e.updated_at,
        }
        for e in exts
    ]


@router.post("/")
def create_extension(
    data: dict,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Create a new extension in the registry."""
    ext = extension_service.admin_create_extension(db, data)
    return {"id": ext.id, "extension_key": ext.extension_key, "display_name": ext.display_name}


@router.put("/{extension_id}")
def update_extension(
    extension_id: str,
    data: dict,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Update extension metadata, status, version."""
    ext = extension_service.admin_update_extension(db, extension_id, data)
    return {"id": ext.id, "extension_key": ext.extension_key, "display_name": ext.display_name, "status": ext.status}


@router.get("/{extension_key}/tenants")
def get_extension_tenants(
    extension_key: str,
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
):
    """Which tenants have this extension installed."""
    return extension_service.admin_get_extension_tenants(db, extension_key)


@router.get("/notify-requests/demand")
def get_demand_signals(
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
):
    """Demand signal dashboard — notify_me_count per coming_soon extension."""
    return extension_service.admin_get_demand_signals(db)


# ── Legacy per-tenant management ──


@router.get("/tenants/{tenant_id}")
def get_tenant_extensions(
    tenant_id: str,
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
):
    return extension_service.get_tenant_extensions_list(db, tenant_id)


@router.post("/tenants/{tenant_id}/enable")
def enable_extension(
    tenant_id: str,
    data: EnableExtensionRequest,
    user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    te = extension_service.enable_extension(
        db, tenant_id, data.extension_key, config=data.config, actor_id=user.id
    )
    return {"tenant_id": tenant_id, "extension_key": te.extension_key, "enabled": te.enabled}


@router.post("/tenants/{tenant_id}/{extension_key}/disable")
def disable_extension(
    tenant_id: str,
    extension_key: str,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    extension_service.disable_extension(db, tenant_id, extension_key)
    return {"detail": "Extension disabled"}


@router.put("/tenants/{tenant_id}/{extension_key}/config")
def update_config(
    tenant_id: str,
    extension_key: str,
    data: UpdateConfigRequest,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    te = extension_service.update_extension_config(db, tenant_id, extension_key, data.config)
    return {"extension_key": te.extension_key, "config": te.config_dict}
