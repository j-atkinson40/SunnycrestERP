"""Admin staging tenant creator endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services.admin import staging_tenant_service

router = APIRouter()


class CreateStagingRequest(BaseModel):
    vertical: str
    preset: str
    company_name: str | None = None


@router.get("/presets")
def list_presets(admin: PlatformUser = Depends(get_current_platform_user)):
    return staging_tenant_service.list_presets()


@router.post("")
def create(
    data: CreateStagingRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    try:
        return staging_tenant_service.create_staging_tenant(
            db=db,
            admin=admin,
            vertical=data.vertical,
            preset=data.preset,
            company_name=data.company_name,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
def list_tenants(
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    rows = staging_tenant_service.list_staging_tenants(db)
    return [
        {
            "id": r.id,
            "company_id": r.company_id,
            "vertical": r.vertical,
            "preset": r.preset,
            "temp_admin_email": r.temp_admin_email,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.patch("/{staging_id}/archive")
def archive(
    staging_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    try:
        rec = staging_tenant_service.archive_staging_tenant(db, staging_id)
        return {"id": rec.id, "is_archived": rec.is_archived}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
