"""Tenant-facing Extension Catalog API."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.services import extension_service

router = APIRouter()


@router.get("/")
def list_catalog(
    category: str | None = Query(None),
    vertical: str | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Full catalog with tenant's current install status merged in."""
    return extension_service.list_catalog(
        db,
        tenant_id=current_user.company_id,
        category=category,
        vertical=vertical,
        status=status,
        search=search,
    )


@router.get("/installed")
def list_installed(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Only extensions this tenant has active."""
    return extension_service.get_installed_extensions(db, current_user.company_id)


@router.get("/{extension_key}")
def get_extension_detail(
    extension_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Single extension detail with tenant install status."""
    detail = extension_service.get_extension_detail(db, extension_key, current_user.company_id)
    if not detail:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Extension not found")
    return detail


@router.post("/{extension_key}/install")
def install_extension(
    extension_key: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Enable extension for tenant. Returns setup_config_schema if setup required."""
    return extension_service.install_extension(
        db,
        tenant_id=current_user.company_id,
        extension_key=extension_key,
        actor_id=current_user.id,
    )


@router.post("/{extension_key}/configure")
def configure_extension(
    extension_key: str,
    data: dict,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Submit configuration for a pending_setup extension."""
    configuration = data.get("configuration", data)
    return extension_service.configure_extension(
        db,
        tenant_id=current_user.company_id,
        extension_key=extension_key,
        configuration=configuration,
        actor_id=current_user.id,
    )


@router.post("/{extension_key}/disable")
def disable_extension(
    extension_key: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Disable extension (preserves config, sets status to disabled)."""
    success = extension_service.disable_extension(
        db,
        tenant_id=current_user.company_id,
        extension_key=extension_key,
        actor_id=current_user.id,
    )
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Extension not installed")
    return {"detail": "Extension disabled"}


@router.post("/{extension_key}/notify")
def notify_me(
    extension_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register notify-me interest on a coming_soon extension."""
    return extension_service.register_notify_interest(
        db,
        tenant_id=current_user.company_id,
        extension_key=extension_key,
        employee_id=current_user.id,
    )
