from sqlalchemy.orm import Session

from app.core.permissions import get_all_permission_keys
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User
from app.models.user_permission_override import UserPermissionOverride


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
        return set(get_all_permission_keys())

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
