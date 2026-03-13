from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import ACCOUNTING_DEFAULT_PERMISSIONS, EMPLOYEE_DEFAULT_PERMISSIONS, get_all_permission_keys
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User
from app.models.user_permission_override import UserPermissionOverride
from app.schemas.role import RoleCreate, RoleUpdate
from app.services import audit_service


def seed_default_roles(db: Session, company_id: str) -> tuple[Role, Role]:
    """Create Admin, Employee, and Accounting system roles for a new company."""
    admin_role = Role(
        company_id=company_id,
        name="Admin",
        slug="admin",
        description="Full system access",
        is_system=True,
    )
    employee_role = Role(
        company_id=company_id,
        name="Employee",
        slug="employee",
        description="Basic employee access",
        is_system=True,
    )
    accounting_role = Role(
        company_id=company_id,
        name="Accounting",
        slug="accounting",
        description="Read access to financial and operational data",
        is_system=True,
    )
    db.add_all([admin_role, employee_role, accounting_role])
    db.flush()

    # Employee gets default permissions
    for perm_key in EMPLOYEE_DEFAULT_PERMISSIONS:
        db.add(RolePermission(role_id=employee_role.id, permission_key=perm_key))

    # Accounting gets broad read access
    for perm_key in ACCOUNTING_DEFAULT_PERMISSIONS:
        db.add(RolePermission(role_id=accounting_role.id, permission_key=perm_key))

    # Admin doesn't need explicit permissions — handled by wildcard logic

    db.flush()
    return admin_role, employee_role


def get_roles(db: Session, company_id: str) -> list[Role]:
    return (
        db.query(Role)
        .filter(Role.company_id == company_id)
        .order_by(Role.is_system.desc(), Role.name)
        .all()
    )


def get_role(db: Session, role_id: str, company_id: str) -> Role:
    role = (
        db.query(Role)
        .filter(Role.id == role_id, Role.company_id == company_id)
        .first()
    )
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    return role


def create_role(
    db: Session, data: RoleCreate, company_id: str, actor_id: str | None = None
) -> Role:
    # Validate permission keys
    valid_keys = set(get_all_permission_keys())
    invalid = set(data.permission_keys) - valid_keys
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid permission keys: {', '.join(sorted(invalid))}",
        )

    # Check slug uniqueness within company
    existing = (
        db.query(Role)
        .filter(Role.slug == data.slug, Role.company_id == company_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role slug already exists in this company",
        )

    role = Role(
        company_id=company_id,
        name=data.name,
        slug=data.slug,
        description=data.description,
        is_system=False,
    )
    db.add(role)
    db.flush()

    # Add permissions
    for perm_key in data.permission_keys:
        db.add(RolePermission(role_id=role.id, permission_key=perm_key))

    audit_service.log_action(
        db, company_id, "created", "role", role.id,
        user_id=actor_id,
        changes={"name": data.name, "slug": data.slug,
                 "permission_keys": data.permission_keys},
    )

    db.commit()
    db.refresh(role)
    return role


def update_role(
    db: Session,
    role_id: str,
    data: RoleUpdate,
    company_id: str,
    actor_id: str | None = None,
) -> Role:
    role = get_role(db, role_id, company_id)

    old_data = {"name": role.name, "description": role.description, "is_active": role.is_active}

    if data.name is not None:
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.is_active is not None:
        if role.is_system and not data.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate system roles",
            )
        role.is_active = data.is_active

    new_data = {"name": role.name, "description": role.description, "is_active": role.is_active}
    changes = audit_service.compute_changes(old_data, new_data)
    if changes:
        audit_service.log_action(
            db, company_id, "updated", "role", role.id,
            user_id=actor_id, changes=changes,
        )

    db.commit()
    db.refresh(role)
    return role


def delete_role(
    db: Session, role_id: str, company_id: str, actor_id: str | None = None
) -> None:
    role = get_role(db, role_id, company_id)

    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete system roles",
        )

    # Check if any users are assigned to this role
    user_count = (
        db.query(User).filter(User.role_id == role_id).count()
    )
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete role with {user_count} assigned user(s). Reassign them first.",
        )

    audit_service.log_action(
        db, company_id, "deleted", "role", role.id,
        user_id=actor_id,
        changes={"name": role.name, "slug": role.slug},
    )

    db.delete(role)
    db.commit()


def set_role_permissions(
    db: Session,
    role_id: str,
    permission_keys: list[str],
    company_id: str,
    actor_id: str | None = None,
) -> Role:
    role = get_role(db, role_id, company_id)

    if role.is_system and role.slug == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify admin role permissions (admin has all permissions automatically)",
        )

    # Validate permission keys
    valid_keys = set(get_all_permission_keys())
    invalid = set(permission_keys) - valid_keys
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid permission keys: {', '.join(sorted(invalid))}",
        )

    old_keys = sorted([rp.permission_key for rp in role.permissions])

    # Replace all role permissions
    db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
    for perm_key in permission_keys:
        db.add(RolePermission(role_id=role_id, permission_key=perm_key))

    new_keys = sorted(permission_keys)
    if old_keys != new_keys:
        audit_service.log_action(
            db, company_id, "updated", "role", role.id,
            user_id=actor_id,
            changes={"permission_keys": {"old": old_keys, "new": new_keys}},
        )

    db.commit()
    db.refresh(role)
    return role


def get_user_permission_overrides(
    db: Session, user_id: str
) -> list[UserPermissionOverride]:
    return (
        db.query(UserPermissionOverride)
        .filter(UserPermissionOverride.user_id == user_id)
        .all()
    )


def set_user_permission_overrides(
    db: Session,
    user_id: str,
    overrides: list[dict],
    company_id: str,
) -> None:
    # Verify user belongs to company
    user = (
        db.query(User)
        .filter(User.id == user_id, User.company_id == company_id)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Validate permission keys
    valid_keys = set(get_all_permission_keys())
    for override in overrides:
        if override["permission_key"] not in valid_keys:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid permission key: {override['permission_key']}",
            )

    # Replace all overrides
    db.query(UserPermissionOverride).filter(
        UserPermissionOverride.user_id == user_id
    ).delete()
    for override in overrides:
        db.add(
            UserPermissionOverride(
                user_id=user_id,
                permission_key=override["permission_key"],
                granted=override["granted"],
            )
        )

    db.commit()
