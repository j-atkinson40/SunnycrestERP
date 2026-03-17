"""Platform admin routes for tenant onboarding oversight.

Provides analytics, white-glove import management, and checklist
overview across all tenants.
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_platform_role
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services import tenant_onboarding_service

router = APIRouter()


@router.get("/analytics")
def get_analytics(
    platform_user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Get platform-wide onboarding analytics."""
    return tenant_onboarding_service.get_analytics(db)


@router.get("/imports")
def list_white_glove_imports(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    platform_user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """List all white-glove import requests across tenants."""
    return tenant_onboarding_service.list_white_glove_imports(
        db, status=status, limit=limit, offset=offset
    )


@router.get("/imports/{import_id}")
def get_white_glove_import(
    import_id: str,
    platform_user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Get details of a white-glove import request."""
    result = tenant_onboarding_service.get_white_glove_import(db, import_id)
    if not result:
        raise HTTPException(status_code=404, detail="White-glove import not found")
    return result


@router.patch("/imports/{import_id}")
def update_white_glove_import(
    import_id: str,
    status: str = Body(...),
    notes: str | None = Body(None),
    platform_user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Update white-glove import status."""
    result = tenant_onboarding_service.update_white_glove_import(
        db, import_id, status=status, notes=notes
    )
    if not result:
        raise HTTPException(status_code=404, detail="White-glove import not found")
    return result


@router.get("/checklists")
def list_all_checklists(
    preset: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    platform_user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """List onboarding checklists across all tenants (admin overview)."""
    return tenant_onboarding_service.list_all_checklists(
        db, preset=preset, limit=limit, offset=offset
    )
