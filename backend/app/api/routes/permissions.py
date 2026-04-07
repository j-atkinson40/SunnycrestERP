"""Permission management API routes."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.core.permissions import get_permissions_by_category
from app.database import get_db
from app.models.user import User
from app.services import permission_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CreateCustomPermissionRequest(BaseModel):
    name: str
    description: str | None = None
    notification_routing: bool = True
    access_gating: bool = False


class UpdateCustomPermissionRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    notification_routing: bool | None = None
    access_gating: bool | None = None


class GrantPermissionRequest(BaseModel):
    permission_slug: str
    notes: str | None = None


class RevokePermissionRequest(BaseModel):
    permission_slug: str
    notes: str | None = None


# ---------------------------------------------------------------------------
# System permissions catalog
# ---------------------------------------------------------------------------


@router.get("")
def list_permissions(
    current_user: User = Depends(get_current_user),
):
    """Return all system permissions grouped by category."""
    return get_permissions_by_category()


# ---------------------------------------------------------------------------
# Custom permissions
# ---------------------------------------------------------------------------


@router.get("/custom")
def list_custom_permissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return tenant's custom permissions."""
    perms = permission_service.get_custom_permissions(db, current_user.company_id)
    return [
        {
            "id": p.id,
            "slug": p.slug,
            "name": p.name,
            "description": p.description,
            "category": p.category,
            "notification_routing": p.notification_routing,
            "access_gating": p.access_gating,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in perms
    ]


@router.post("/custom", status_code=201)
def create_custom_permission(
    body: CreateCustomPermissionRequest,
    current_user: User = Depends(require_permission("settings.permissions.manage")),
    db: Session = Depends(get_db),
):
    perm = permission_service.create_custom_permission(
        db,
        current_user.company_id,
        body.name,
        body.description,
        body.notification_routing,
        body.access_gating,
        current_user.id,
    )
    return {
        "id": perm.id,
        "slug": perm.slug,
        "name": perm.name,
        "description": perm.description,
        "notification_routing": perm.notification_routing,
        "access_gating": perm.access_gating,
    }


@router.patch("/custom/{perm_id}")
def update_custom_permission(
    perm_id: str,
    body: UpdateCustomPermissionRequest,
    current_user: User = Depends(require_permission("settings.permissions.manage")),
    db: Session = Depends(get_db),
):
    perm = permission_service.update_custom_permission(
        db,
        perm_id,
        current_user.company_id,
        body.name,
        body.description,
        body.notification_routing,
        body.access_gating,
    )
    return {
        "id": perm.id,
        "slug": perm.slug,
        "name": perm.name,
        "description": perm.description,
        "notification_routing": perm.notification_routing,
        "access_gating": perm.access_gating,
    }


@router.delete("/custom/{perm_id}", status_code=204)
def delete_custom_permission(
    perm_id: str,
    current_user: User = Depends(require_permission("settings.permissions.manage")),
    db: Session = Depends(get_db),
):
    permission_service.delete_custom_permission(db, perm_id, current_user.company_id)


# ---------------------------------------------------------------------------
# User permission management
# ---------------------------------------------------------------------------


@router.get("/users/{user_id}")
def get_user_permissions(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return full permission set for a user."""
    user = permission_service._validate_user_tenant(db, user_id, current_user.company_id)
    return permission_service.get_user_permission_details(user, db)


@router.post("/users/{user_id}/grant")
def grant_permission(
    user_id: str,
    body: GrantPermissionRequest,
    current_user: User = Depends(require_permission("settings.permissions.manage")),
    db: Session = Depends(get_db),
):
    override = permission_service.grant_permission(
        db, user_id, body.permission_slug,
        current_user.company_id, current_user.id, body.notes,
    )
    return {
        "permission_key": override.permission_key,
        "granted": override.granted,
        "status": "granted",
    }


@router.post("/users/{user_id}/revoke")
def revoke_permission(
    user_id: str,
    body: RevokePermissionRequest,
    current_user: User = Depends(require_permission("settings.permissions.manage")),
    db: Session = Depends(get_db),
):
    override = permission_service.revoke_permission(
        db, user_id, body.permission_slug,
        current_user.company_id, current_user.id, body.notes,
    )
    return {
        "permission_key": override.permission_key,
        "granted": override.granted,
        "status": "revoked",
    }


@router.delete("/users/{user_id}/{slug:path}")
def reset_permission(
    user_id: str,
    slug: str,
    current_user: User = Depends(require_permission("settings.permissions.manage")),
    db: Session = Depends(get_db),
):
    """Remove explicit grant/revoke, returning to role default."""
    removed = permission_service.reset_permission(
        db, user_id, slug, current_user.company_id,
    )
    return {"status": "reset" if removed else "no_override_found"}


@router.get("/users/{user_id}/audit-log")
def get_permission_audit(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get permission change history for a user."""
    return permission_service.get_permission_audit_log(
        db, user_id, current_user.company_id,
    )


# ---------------------------------------------------------------------------
# Roles (read-only here — full CRUD in roles.py)
# ---------------------------------------------------------------------------


@router.get("/roles")
def list_roles_with_permissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all roles with their default permissions."""
    from app.models.role import Role
    from app.models.role_permission import RolePermission

    roles = (
        db.query(Role)
        .filter(Role.company_id == current_user.company_id)
        .order_by(Role.is_system.desc(), Role.name)
        .all()
    )
    return [
        {
            "id": r.id,
            "name": r.name,
            "slug": r.slug,
            "description": r.description,
            "is_system": r.is_system,
            "default_permissions": [rp.permission_key for rp in r.permissions],
        }
        for r in roles
    ]
