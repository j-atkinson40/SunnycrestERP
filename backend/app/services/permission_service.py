"""Permission service — resolution, custom permissions, seeding."""

import logging
import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import (
    PERMISSION_DISPLAY_NAMES,
    get_all_permission_keys,
    get_permissions_by_category,
)
from app.models.custom_permission import CustomPermission
from app.models.permission_catalog import PermissionCatalog
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User
from app.models.user_permission_override import UserPermissionOverride

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Permission resolution
# ---------------------------------------------------------------------------


def get_user_permissions(user: User, db: Session) -> set[str]:
    """
    Resolve effective permissions for a user.

    Algorithm:
      1. If user's role is system admin → return ALL permissions (wildcard)
      2. Get all permission_keys from role_permissions for user's role
      3. Apply user overrides: add grants, remove revokes
      4. Return final set
    """
    role = db.query(Role).filter(Role.id == user.role_id).first()

    # Admin shortcut — system admin role gets everything
    if role and role.is_system and role.slug == "admin":
        all_perms = set(get_all_permission_keys())
        # Also include any custom permissions granted explicitly
        custom_grants = (
            db.query(UserPermissionOverride.permission_key)
            .filter(
                UserPermissionOverride.user_id == user.id,
                UserPermissionOverride.granted.is_(True),
                UserPermissionOverride.permission_key.like("custom.%"),
            )
            .all()
        )
        for cg in custom_grants:
            all_perms.add(cg.permission_key)
        return all_perms

    # Get role's base permissions
    role_perms = (
        db.query(RolePermission.permission_key)
        .filter(RolePermission.role_id == user.role_id)
        .all()
    )
    effective = {rp.permission_key for rp in role_perms}

    # Apply user-level overrides
    overrides = (
        db.query(UserPermissionOverride)
        .filter(UserPermissionOverride.user_id == user.id)
        .all()
    )
    for override in overrides:
        if override.granted:
            effective.add(override.permission_key)
        else:
            effective.discard(override.permission_key)

    return effective


def user_has_permission(user: User, db: Session, permission_key: str) -> bool:
    """Check if a user has a specific permission."""
    # Quick admin check to avoid extra DB queries
    role = db.query(Role).filter(Role.id == user.role_id).first()
    if role and role.is_system and role.slug == "admin":
        return True

    permissions = get_user_permissions(user, db)
    return permission_key in permissions


def get_user_permission_details(user: User, db: Session) -> dict:
    """Return full permission breakdown for a user."""
    role = db.query(Role).filter(Role.id == user.role_id).first()

    role_perms = (
        db.query(RolePermission.permission_key)
        .filter(RolePermission.role_id == user.role_id)
        .all()
    )
    role_permission_set = {rp.permission_key for rp in role_perms}

    overrides = (
        db.query(UserPermissionOverride)
        .filter(UserPermissionOverride.user_id == user.id)
        .all()
    )

    explicit_grants = []
    explicit_revokes = []
    for o in overrides:
        entry = {
            "permission_key": o.permission_key,
            "granted_by_user_id": o.granted_by_user_id,
            "notes": o.notes,
            "granted_at": o.created_at.isoformat() if o.created_at else None,
        }
        if o.granted:
            explicit_grants.append(entry)
        else:
            explicit_revokes.append(entry)

    effective = get_user_permissions(user, db)

    is_admin = role and role.is_system and role.slug == "admin"

    return {
        "role_slug": role.slug if role else None,
        "role_name": role.name if role else None,
        "is_admin": is_admin,
        "role_permissions": sorted(role_permission_set),
        "explicit_grants": explicit_grants,
        "explicit_revokes": explicit_revokes,
        "effective_permissions": sorted(effective),
    }


# ---------------------------------------------------------------------------
# User permission grant / revoke
# ---------------------------------------------------------------------------


def grant_permission(
    db: Session,
    user_id: str,
    permission_slug: str,
    tenant_id: str,
    granted_by: str | None = None,
    notes: str | None = None,
) -> UserPermissionOverride:
    """Explicitly grant a permission to a user."""
    _validate_user_tenant(db, user_id, tenant_id)
    _validate_permission_slug(db, permission_slug, tenant_id)

    existing = (
        db.query(UserPermissionOverride)
        .filter(
            UserPermissionOverride.user_id == user_id,
            UserPermissionOverride.permission_key == permission_slug,
        )
        .first()
    )
    if existing:
        existing.granted = True
        existing.granted_by_user_id = granted_by
        existing.notes = notes
        existing.created_at = datetime.now(timezone.utc)
    else:
        existing = UserPermissionOverride(
            user_id=user_id,
            permission_key=permission_slug,
            granted=True,
            granted_by_user_id=granted_by,
            notes=notes,
        )
        db.add(existing)

    db.commit()
    db.refresh(existing)
    return existing


def revoke_permission(
    db: Session,
    user_id: str,
    permission_slug: str,
    tenant_id: str,
    granted_by: str | None = None,
    notes: str | None = None,
) -> UserPermissionOverride:
    """Explicitly revoke a permission from a user."""
    _validate_user_tenant(db, user_id, tenant_id)
    _validate_permission_slug(db, permission_slug, tenant_id)

    existing = (
        db.query(UserPermissionOverride)
        .filter(
            UserPermissionOverride.user_id == user_id,
            UserPermissionOverride.permission_key == permission_slug,
        )
        .first()
    )
    if existing:
        existing.granted = False
        existing.granted_by_user_id = granted_by
        existing.notes = notes
        existing.created_at = datetime.now(timezone.utc)
    else:
        existing = UserPermissionOverride(
            user_id=user_id,
            permission_key=permission_slug,
            granted=False,
            granted_by_user_id=granted_by,
            notes=notes,
        )
        db.add(existing)

    db.commit()
    db.refresh(existing)
    return existing


def reset_permission(
    db: Session, user_id: str, permission_slug: str, tenant_id: str
) -> bool:
    """Remove explicit grant/revoke, returning to role default."""
    _validate_user_tenant(db, user_id, tenant_id)

    deleted = (
        db.query(UserPermissionOverride)
        .filter(
            UserPermissionOverride.user_id == user_id,
            UserPermissionOverride.permission_key == permission_slug,
        )
        .delete()
    )
    db.commit()
    return deleted > 0


def _validate_user_tenant(db: Session, user_id: str, tenant_id: str) -> User:
    user = (
        db.query(User)
        .filter(User.id == user_id, User.company_id == tenant_id)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


def _validate_permission_slug(db: Session, slug: str, tenant_id: str) -> None:
    """Validate that the permission slug is either a system permission or a custom one for this tenant."""
    all_system = set(get_all_permission_keys())
    if slug in all_system:
        return

    if slug.startswith("custom."):
        custom = (
            db.query(CustomPermission)
            .filter(CustomPermission.tenant_id == tenant_id, CustomPermission.slug == slug)
            .first()
        )
        if custom:
            return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid permission slug: {slug}",
    )


# ---------------------------------------------------------------------------
# Custom permissions CRUD
# ---------------------------------------------------------------------------


def _slugify(name: str) -> str:
    """Convert a human name to a slug: 'Approve Spring Burials' → 'approve_spring_burials'."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s


def get_custom_permissions(db: Session, tenant_id: str) -> list[CustomPermission]:
    return (
        db.query(CustomPermission)
        .filter(CustomPermission.tenant_id == tenant_id)
        .order_by(CustomPermission.name)
        .all()
    )


def create_custom_permission(
    db: Session,
    tenant_id: str,
    name: str,
    description: str | None,
    notification_routing: bool,
    access_gating: bool,
    created_by: str | None,
) -> CustomPermission:
    slug = f"custom.{_slugify(name)}"

    existing = (
        db.query(CustomPermission)
        .filter(CustomPermission.tenant_id == tenant_id, CustomPermission.slug == slug)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Custom permission '{slug}' already exists",
        )

    perm = CustomPermission(
        tenant_id=tenant_id,
        slug=slug,
        name=name,
        description=description,
        notification_routing=notification_routing,
        access_gating=access_gating,
        created_by_user_id=created_by,
    )
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return perm


def update_custom_permission(
    db: Session,
    perm_id: str,
    tenant_id: str,
    name: str | None = None,
    description: str | None = None,
    notification_routing: bool | None = None,
    access_gating: bool | None = None,
) -> CustomPermission:
    perm = (
        db.query(CustomPermission)
        .filter(CustomPermission.id == perm_id, CustomPermission.tenant_id == tenant_id)
        .first()
    )
    if not perm:
        raise HTTPException(status_code=404, detail="Custom permission not found")

    if name is not None:
        perm.name = name
        perm.slug = f"custom.{_slugify(name)}"
    if description is not None:
        perm.description = description
    if notification_routing is not None:
        perm.notification_routing = notification_routing
    if access_gating is not None:
        perm.access_gating = access_gating

    db.commit()
    db.refresh(perm)
    return perm


def delete_custom_permission(db: Session, perm_id: str, tenant_id: str) -> None:
    perm = (
        db.query(CustomPermission)
        .filter(CustomPermission.id == perm_id, CustomPermission.tenant_id == tenant_id)
        .first()
    )
    if not perm:
        raise HTTPException(status_code=404, detail="Custom permission not found")

    # Check if any users have this permission
    assigned = (
        db.query(UserPermissionOverride)
        .filter(UserPermissionOverride.permission_key == perm.slug)
        .count()
    )
    if assigned > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete: {assigned} user(s) have this permission assigned. Remove assignments first.",
        )

    db.delete(perm)
    db.commit()


# ---------------------------------------------------------------------------
# Permission audit log
# ---------------------------------------------------------------------------


def get_permission_audit_log(
    db: Session, user_id: str, tenant_id: str, limit: int = 50
) -> list[dict]:
    """Get recent permission changes for a user."""
    _validate_user_tenant(db, user_id, tenant_id)

    overrides = (
        db.query(UserPermissionOverride)
        .filter(UserPermissionOverride.user_id == user_id)
        .order_by(UserPermissionOverride.created_at.desc())
        .limit(limit)
        .all()
    )

    # Load granted_by user names
    grantor_ids = {o.granted_by_user_id for o in overrides if o.granted_by_user_id}
    grantors = {}
    if grantor_ids:
        users = db.query(User).filter(User.id.in_(grantor_ids)).all()
        grantors = {u.id: f"{u.first_name} {u.last_name}" for u in users}

    return [
        {
            "permission_key": o.permission_key,
            "permission_name": PERMISSION_DISPLAY_NAMES.get(o.permission_key, o.permission_key),
            "granted": o.granted,
            "change": "Granted" if o.granted else "Revoked",
            "granted_by": grantors.get(o.granted_by_user_id, "System"),
            "granted_at": o.created_at.isoformat() if o.created_at else None,
            "notes": o.notes,
        }
        for o in overrides
    ]


# ---------------------------------------------------------------------------
# Seed permission catalog
# ---------------------------------------------------------------------------


def seed_permission_catalog(db: Session) -> int:
    """Seed the permission_catalog table from the registry. Idempotent."""
    from app.core.permissions import PERMISSION_CATEGORIES, ROLE_DEFAULTS

    created = 0
    for category, modules in PERMISSION_CATEGORIES.items():
        for module, actions in modules.items():
            for action in actions:
                slug = f"{module}.{action}"
                existing = (
                    db.query(PermissionCatalog)
                    .filter(PermissionCatalog.slug == slug)
                    .first()
                )
                if existing:
                    continue

                # Determine which roles get this by default
                default_roles = []
                for role_slug, perms in ROLE_DEFAULTS.items():
                    if slug in perms:
                        default_roles.append(role_slug)

                name = PERMISSION_DISPLAY_NAMES.get(slug, slug.replace(".", " ").replace("_", " ").title())

                perm = PermissionCatalog(
                    slug=slug,
                    name=name,
                    description=None,
                    category=category,
                    is_system=True,
                    is_toggle=True,
                    default_for_roles=",".join(default_roles) if default_roles else None,
                )
                db.add(perm)
                created += 1

    if created:
        db.commit()
        logger.info(f"Seeded {created} permission catalog entries")
    return created
