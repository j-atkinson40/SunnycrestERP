"""Admin feature flag endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services.admin import feature_flag_service

router = APIRouter()


class SetDefaultRequest(BaseModel):
    default_enabled: bool


class SetOverrideRequest(BaseModel):
    company_id: str
    is_enabled: bool


@router.get("")
def list_flags(
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    return feature_flag_service.list_flags(db)


@router.patch("/{flag_key}")
def set_default(
    flag_key: str,
    data: SetDefaultRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    try:
        flag = feature_flag_service.set_default(db, flag_key, data.default_enabled)
        return {"flag_key": flag.flag_key, "default_enabled": flag.default_enabled}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{flag_key}/overrides")
def set_override(
    flag_key: str,
    data: SetOverrideRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    try:
        override = feature_flag_service.set_override(
            db, flag_key, data.company_id, data.is_enabled, admin.id
        )
        return {
            "id": override.id,
            "flag_key": override.flag_key,
            "company_id": override.company_id,
            "is_enabled": override.is_enabled,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{flag_key}/overrides/{company_id}")
def remove_override(
    flag_key: str,
    company_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    removed = feature_flag_service.remove_override(db, flag_key, company_id)
    return {"removed": removed}
