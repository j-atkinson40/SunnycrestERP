"""Tenant kanban endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services.admin import tenant_kanban_service

router = APIRouter()


@router.get("/kanban")
def kanban(
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    return tenant_kanban_service.get_kanban(db)


@router.get("/{company_id}/detail")
def tenant_detail(
    company_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    try:
        return tenant_kanban_service.get_tenant_detail(db, company_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
