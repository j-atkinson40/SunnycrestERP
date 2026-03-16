"""Platform admin — extension management."""

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


@router.get("/definitions")
def list_extension_definitions(
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
):
    exts = extension_service.list_extensions(db)
    return [
        {
            "extension_key": e.extension_key,
            "module_key": e.module_key,
            "display_name": e.display_name,
            "description": e.description,
            "config_schema": e.schema_dict,
            "version": e.version,
        }
        for e in exts
    ]


@router.get("/tenants/{tenant_id}")
def get_tenant_extensions(
    tenant_id: str,
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
):
    return extension_service.get_tenant_extensions(db, tenant_id)


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
