from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import (
    ACCOUNTANT_DEFAULT_PERMISSIONS,
    ACCOUNTANT_FULL_PERMISSIONS,
    ACCOUNTING_DEFAULT_PERMISSIONS,
    DISPATCHER_DEFAULT_PERMISSIONS,
    DRIVER_DEFAULT_PERMISSIONS,
    EMPLOYEE_DEFAULT_PERMISSIONS,
    LEGACY_DESIGNER_DEFAULT_PERMISSIONS,
    MANAGER_DEFAULT_PERMISSIONS,
    OFFICE_STAFF_DEFAULT_PERMISSIONS,
    PAYROLL_DEFAULT_PERMISSIONS,
    PRODUCTION_DEFAULT_PERMISSIONS,
    get_all_permission_keys,
)
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User
from app.models.user_permission_override import UserPermissionOverride
from app.schemas.role import RoleCreate, RoleUpdate
from app.services import audit_service


# ── Role → Functional Area mapping ──────────────────────────────────────────

ROLE_FUNCTIONAL_AREAS: dict[str, list[str]] = {
    "admin": ["full_admin"],
    "manager": ["full_admin"],
    "office_staff": ["customer_management", "funeral_scheduling", "invoicing_ar"],
    # R-1.6.3: 'office' (no _staff suffix) is the canonical slug used
    # by saved_views/seed.py + spaces/registry.py for FH office roles.
    # Functionally identical to office_staff at September scope.
    "office": ["customer_management", "funeral_scheduling", "invoicing_ar"],
    "dispatcher": ["delivery_dispatch", "driver_management"],
    "driver": [],
    "production": ["production_log", "safety_compliance"],
    # R-1.6.3: 'director' is the canonical FH role slug used by Phase 8e
    # space templates ((funeral_home, 'director') in spaces/registry.py)
    # and saved_views seed templates. Pre-R-1.6.3 the slug was referenced
    # by Phase 8e but never seeded canonically — Hopkins FH director users
    # had no role to bind to. Permissions match manager (broad operational
    # + customer + financial access; FH directors run the funeral home).
    "director": ["full_admin"],
    "legacy_designer": ["customer_management"],
    "accounting": ["invoicing_ar", "customer_management"],
    "employee": [],
}

# ── System role definitions ─────────────────────────────────────────────────

_SYSTEM_ROLES = [
    {
        "name": "Administrator",
        "slug": "admin",
        "description": "Full access to everything",
        "permissions": [],  # Wildcard — handled by permission_service.py
    },
    {
        "name": "Manager",
        "slug": "manager",
        "description": "Full access except billing settings and user deletion",
        "permissions": MANAGER_DEFAULT_PERMISSIONS,
    },
    {
        "name": "Office Staff",
        "slug": "office_staff",
        "description": "Operations and CRM access, no financials by default",
        "permissions": OFFICE_STAFF_DEFAULT_PERMISSIONS,
    },
    {
        # R-1.6.3: canonical slug 'office' (no _staff suffix) — matches
        # the slug Phase 8e spaces/registry.py + saved_views/seed.py
        # already reference. Permissions match office_staff exactly.
        "name": "Office",
        "slug": "office",
        "description": "Operations and CRM access, no financials by default",
        "permissions": OFFICE_STAFF_DEFAULT_PERMISSIONS,
    },
    {
        # R-1.6.3: canonical FH role. Pre-R-1.6.3 Phase 8e referenced
        # (funeral_home, 'director') in space templates but the slug
        # was never seeded canonically. seed_fh_demo passed role='director'
        # as a string into User(**defaults), which crashed on TypeError
        # before R-1.6.3's _ensure_user fix. Now canonical.
        "name": "Director",
        "slug": "director",
        "description": "Funeral director — full operational + customer + financial access",
        "permissions": MANAGER_DEFAULT_PERMISSIONS,
    },
    {
        "name": "Accountant",
        "slug": "accountant",
        "description": "Full financial access, view-only on operations",
        # ⚠️ CONCATENATED HERE, NOT MERGED INTO THE SHARED LIST. The `accounting`
        # slug below uses an ALIAS of ACCOUNTANT_DEFAULT_PERMISSIONS, so adding
        # the payroll keys there granted them to `accounting` too — which the
        # old slug gate never did, and which r222 deliberately excluded.
        #
        # ⚠️ READ FROM `ACCOUNTANT_FULL_PERMISSIONS`, NOT COMPOSED HERE.
        # Composing it inline left `scripts/seed_staging.py` — a third,
        # independent producer — building an accountant with no payroll keys,
        # which took CI red with 28 failures.
        "permissions": ACCOUNTANT_FULL_PERMISSIONS,
    },
    {
        # ⚠️ THE FIRST AREA-LIMITED SYSTEM ROLE. `limited_to_areas` makes
        # `enforce_area_limit` refuse every tenant endpoint that is not tagged
        # `area:payroll`, plus the common shell set — so this role's reach is
        # the two permissions below AND nothing else, enforced on the server.
        #
        # Every other entry in this list omits `limited_to_areas`, which means
        # NULL, which means unrestricted — today's behaviour, unchanged.
        "name": "Payroll",
        "slug": "payroll",
        "description": "Weekly payroll dues review only. Sees nothing else.",
        "permissions": PAYROLL_DEFAULT_PERMISSIONS,
        "limited_to_areas": ["payroll"],
    },
    {
        "name": "Accounting",
        "slug": "accounting",
        "description": "Full financial access, view-only on operations",
        "permissions": ACCOUNTING_DEFAULT_PERMISSIONS,
    },
    {
        "name": "Legacy Designer",
        "slug": "legacy_designer",
        "description": "Full Legacy Studio access with order and customer view only",
        "permissions": LEGACY_DESIGNER_DEFAULT_PERMISSIONS,
    },
    {
        "name": "Driver",
        "slug": "driver",
        "description": "Driver console only, direct redirect on login",
        "permissions": DRIVER_DEFAULT_PERMISSIONS,
    },
    {
        "name": "Production / Plant Manager",
        "slug": "production",
        "description": "Operations board and production hub full access",
        "permissions": PRODUCTION_DEFAULT_PERMISSIONS,
    },
    {
        "name": "Dispatcher",
        "slug": "dispatcher",
        "description": "Scheduling monitor + scheduling focus; manages driver assignments, delivery schedules, and hole-dug status",
        "permissions": DISPATCHER_DEFAULT_PERMISSIONS,
    },
    {
        "name": "Employee",
        "slug": "employee",
        "description": "Basic employee access",
        "permissions": EMPLOYEE_DEFAULT_PERMISSIONS,
    },
]


def seed_default_roles(db: Session, company_id: str) -> tuple[Role, Role]:
    """Create all system roles for a new company.

    Returns (admin_role, employee_role) for backward compatibility.
    """
    admin_role = None
    employee_role = None

    for role_def in _SYSTEM_ROLES:
        # Skip if already exists for this company
        existing = (
            db.query(Role)
            .filter(Role.company_id == company_id, Role.slug == role_def["slug"])
            .first()
        )
        if existing:
            if role_def["slug"] == "admin":
                admin_role = existing
            elif role_def["slug"] == "employee":
                employee_role = existing
            continue

        role = Role(
            company_id=company_id,
            name=role_def["name"],
            slug=role_def["slug"],
            description=role_def["description"],
            is_system=True,
            # ⚠️ `.get`, DEFAULTING TO None, NOT []. An absent key means "no area
            # restriction established" and must stay NULL; `[]` would mean
            # "limited to nothing" and would lock every role out of everything.
            # The two are different values and the difference is the whole design
            # (r221, app/core/areas.py).
            limited_to_areas=role_def.get("limited_to_areas"),
        )
        db.add(role)
        db.flush()

        for perm_key in role_def["permissions"]:
            db.add(RolePermission(role_id=role.id, permission_key=perm_key))

        if role_def["slug"] == "admin":
            admin_role = role
        elif role_def["slug"] == "employee":
            employee_role = role

    db.flush()
    return admin_role, employee_role  # type: ignore[return-value]


def sync_functional_areas_for_role(db: Session, user_id: str, role_slug: str) -> None:
    """Set employee_profiles.functional_areas based on the role's default mapping."""
    from app.models.employee_profile import EmployeeProfile

    areas = ROLE_FUNCTIONAL_AREAS.get(role_slug, [])
    profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == user_id).first()
    if profile:
        profile.functional_areas = areas
    else:
        # Create profile if it doesn't exist
        profile = EmployeeProfile(user_id=user_id, functional_areas=areas)
        db.add(profile)


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
        # Validated against KNOWN_AREAS by the schema, so an unknown key never
        # reaches here. None = not limited.
        limited_to_areas=data.limited_to_areas,
        is_system=False,
        created_by=actor_id,
    )
    db.add(role)
    db.flush()

    # Add permissions
    for perm_key in data.permission_keys:
        db.add(RolePermission(role_id=role.id, permission_key=perm_key))

    audit_service.log_action(
        db, company_id, "created", "role", role.id,
        user_id=actor_id,
        changes={
            # Identity fields are bare on CREATE: there is no prior value, and
            # {"before": None} for a name that never existed reads as a change
            # rather than a birth. Collections still use pairs so a diff against
            # a later change lines up.
            "name": data.name,
            "slug": data.slug,
            "permission_keys": {"before": [], "after": sorted(data.permission_keys)},
            # ⚠️ RECORDED BECAUSE IT IS THE SECURITY BOUNDARY (r221). A role's
            # areas decide what it can reach AT ALL — more decisive than its
            # permission list, since `enforce_area_limit` refuses everything
            # outside them. A role created limited and later widened to NULL
            # would otherwise leave no trace of the widening.
            "limited_to_areas": {"before": None, "after": role.limited_to_areas},
        },
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

    old_data = {"name": role.name, "description": role.description,
                "is_active": role.is_active,
                "limited_to_areas": role.limited_to_areas}

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

    # ⚠️ `model_fields_set`, NOT `is not None`. Omitting `limited_to_areas` means
    # "leave the areas alone"; sending it as `null` means "make this role
    # unlimited". A null check cannot distinguish those, so clearing a limit
    # would be impossible — and an area limit you can set but never lift is a
    # trap, not a control.
    if "limited_to_areas" in data.model_fields_set:
        if role.is_system and role.slug == "admin":
            # Admin holds a permission wildcard; area-limiting it would produce a
            # role that passes every permission check and is refused by the area
            # guard — incoherent, and a fast way to lock a tenant out of its own
            # settings.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The admin role cannot be limited to areas.",
            )
        role.limited_to_areas = data.limited_to_areas

    role.modified_by = actor_id

    new_data = {"name": role.name, "description": role.description,
                "is_active": role.is_active,
                "limited_to_areas": role.limited_to_areas}
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

    # ⚠️ SNAPSHOT WHAT IT HELD, BEFORE IT IS GONE. This recorded only name and
    # slug until 2026-11-03. After the delete there is nothing left to read, and
    # "a role called payroll was deleted" without its permission set and areas
    # is a note that something happened, not an audit trail.
    audit_service.log_action(
        db, company_id, "deleted", "role", role.id,
        user_id=actor_id,
        # Every field is a before/after pair, uniformly. A snapshot that mixes
        # bare values with pairs makes a reader learn which is which per field.
        changes={
            "name": {"before": role.name, "after": None},
            "slug": {"before": role.slug, "after": None},
            "permission_keys": {
                "before": sorted(rp.permission_key for rp in role.permissions),
                "after": [],
            },
            "limited_to_areas": {"before": role.limited_to_areas, "after": None},
        },
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
        # ⚠️ ACTION RENAMED "updated" -> "permissions_changed" (2026-11-03).
        # A rename and a permission grant both logged as "updated", so the one
        # change that moves a security boundary was indistinguishable from a
        # typo fix in the audit list. Safe to rename: no code reads this string
        # (checked), and the audit route exposes `action` only as a
        # caller-supplied filter.
        #
        # Deltas are recorded ALONGSIDE the full sets, not instead of them: a
        # reader wants "what was granted" without diffing two 200-item lists,
        # and wants the full sets to reconstruct the boundary as it stood.
        audit_service.log_action(
            db, company_id, "permissions_changed", "role", role.id,
            user_id=actor_id,
            changes={
                "permission_keys": {"before": old_keys, "after": new_keys},
                "granted": sorted(set(new_keys) - set(old_keys)),
                "revoked": sorted(set(old_keys) - set(new_keys)),
            },
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
