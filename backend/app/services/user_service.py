from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

import secrets
from datetime import datetime, timezone

from app.core.security import decrypt_pin, encrypt_pin, hash_password
from app.models.employee_profile import EmployeeProfile
from app.models.role import Role
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services import audit_service, notification_service


# Workflow Arc Phase 8a — role decoupling.
# When False (the Phase 8a default), role changes stop auto-re-seeding
# saved views + briefing preferences. Roles become permission grants
# only; UX content is preserved. Flip to True to restore the UI/UX Arc
# Phase 3 behavior (useful for migration utilities or feature-parity
# tests). Documented in CLAUDE.md § Roles.
#
# Spaces seed STILL runs on role change because its role-tuple
# seeding is idempotent AND the Phase-8a _apply_system_spaces pass
# checks live admin permission for the Settings system space —
# promotion-to-admin should surface Settings in the dot nav.
ROLE_CHANGE_RESEED_ENABLED: bool = False


def reapply_role_defaults_for_user(db: Session, user: User) -> dict[str, int]:
    """Opt-in re-apply of role-based defaults across Phase 2 (saved
    views), Phase 3 (spaces), Phase 6 (briefing preferences).

    Returns counts per domain: `{saved_views, spaces, briefings}`.

    Phase 8a ships this as a public function callable from a future
    UI (Phase 8e) or from migration utilities. It's NOT called on
    role change by default — role change is permission-only. This
    gives users an explicit "start over from role defaults" action.
    """
    counts = {"saved_views": 0, "spaces": 0, "briefings": 0}
    try:
        from app.services.saved_views.seed import (
            seed_for_user as _seed_saved_views,
        )
        counts["saved_views"] = _seed_saved_views(db, user=user) or 0
    except Exception:  # pragma: no cover — best-effort
        import logging
        logging.getLogger(__name__).exception(
            "reapply_role_defaults: saved_views failed for user %s", user.id
        )
    try:
        from app.services.spaces.seed import (
            seed_for_user as _seed_spaces,
        )
        counts["spaces"] = _seed_spaces(db, user=user) or 0
    except Exception:  # pragma: no cover — best-effort
        import logging
        logging.getLogger(__name__).exception(
            "reapply_role_defaults: spaces failed for user %s", user.id
        )
    try:
        from app.services.briefings.preferences import (
            seed_preferences_for_user as _seed_briefings,
        )
        _seed_briefings(db, user)
        counts["briefings"] = 1
    except Exception:  # pragma: no cover — best-effort
        import logging
        logging.getLogger(__name__).exception(
            "reapply_role_defaults: briefings failed for user %s", user.id
        )
    return counts


def _get_default_employee_role(db: Session, company_id: str) -> Role:
    """Look up the system employee role for a company."""
    role = (
        db.query(Role)
        .filter(
            Role.company_id == company_id,
            Role.slug == "employee",
            Role.is_system == True,  # noqa: E712
        )
        .first()
    )
    if not role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default employee role not found",
        )
    return role


def _validate_role_id(db: Session, role_id: str, company_id: str) -> None:
    """Ensure the role belongs to the same company."""
    role = (
        db.query(Role)
        .filter(Role.id == role_id, Role.company_id == company_id)
        .first()
    )
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role for this company",
        )


def get_users(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
) -> dict:
    query = (
        db.query(User)
        .options(
            joinedload(User.profile).joinedload(EmployeeProfile.department_obj)
        )
        .filter(User.company_id == company_id)
    )
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            User.email.ilike(pattern)
            | User.first_name.ilike(pattern)
            | User.last_name.ilike(pattern)
        )

    total = query.count()
    users = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": users, "total": total, "page": page, "per_page": per_page}


def get_user(db: Session, user_id: str, company_id: str) -> User:
    user = (
        db.query(User)
        .filter(User.id == user_id, User.company_id == company_id)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


def create_user(
    db: Session, data: UserCreate, company_id: str, actor_id: str | None = None
) -> User:
    is_production = data.track == "production_delivery"

    if is_production:
        # Check username uniqueness within tenant
        existing = (
            db.query(User)
            .filter(User.username == data.username, User.company_id == company_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )
    else:
        # Check email uniqueness within tenant
        existing = (
            db.query(User)
            .filter(User.email == data.email, User.company_id == company_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

    # Resolve role_id: use provided or default to employee
    role_id = data.role_id
    if not role_id:
        role_id = _get_default_employee_role(db, company_id).id
    else:
        _validate_role_id(db, role_id, company_id)

    if is_production:
        # Production track: username + PIN, sentinel email/password
        sentinel_email = f"{data.username}@noemail.internal"
        user = User(
            email=sentinel_email,
            hashed_password=hash_password(secrets.token_hex(16)),
            first_name=data.first_name,
            last_name=data.last_name,
            role_id=role_id,
            company_id=company_id,
            created_by=actor_id,
            track="production_delivery",
            username=data.username,
            pin_encrypted=encrypt_pin(data.pin),
            pin_set_at=datetime.now(timezone.utc),
            console_access=data.console_access or [],
            idle_timeout_minutes=data.idle_timeout_minutes or 30,
        )
    else:
        # Office track: email + password (existing behavior)
        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            role_id=role_id,
            company_id=company_id,
            created_by=actor_id,
        )

    db.add(user)
    db.flush()

    # Sync functional areas based on role
    from app.services.role_service import sync_functional_areas_for_role

    role_obj = db.query(Role).filter(Role.id == role_id).first()
    if role_obj:
        sync_functional_areas_for_role(db, user.id, role_obj.slug)

    audit_service.log_action(
        db,
        company_id,
        "created",
        "user",
        user.id,
        user_id=actor_id,
        changes={
            "email": data.email if not is_production else None,
            "username": data.username if is_production else None,
            "first_name": data.first_name,
            "last_name": data.last_name,
            "role_id": role_id,
            "track": data.track,
        },
    )

    # Look up company name for the welcome notification
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == company_id).first()
    company_name = company.name if company else "the company"
    notification_service.create_notification(
        db,
        company_id,
        user.id,
        title="Welcome!",
        message=f"Welcome to {company_name}! Your account has been created.",
        type="success",
        category="user",
        link="/profile" if not is_production else "/console",
        actor_id=actor_id,
    )

    db.commit()
    db.refresh(user)

    # Phase 8e.2.2 Space Invariant Enforcement — seed role-based
    # default spaces for the admin-provisioned user. Mirrors the
    # existing seed call in `auth_service.register_user`. Best-effort
    # — a seed failure logs structured warning but doesn't break
    # the admin's user-creation flow.
    from app.services.spaces.seed import seed_spaces_best_effort

    seed_spaces_best_effort(db, user, call_site="user_service.create_user")

    return user


def update_user(
    db: Session,
    user_id: str,
    data: UserUpdate,
    company_id: str,
    actor_id: str | None = None,
) -> User:
    user = get_user(db, user_id, company_id)

    # Capture old values before update
    old_data = {
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role_id": user.role_id,
        "is_active": user.is_active,
    }

    update_data = data.model_dump(exclude_unset=True)
    if "email" in update_data:
        existing = (
            db.query(User)
            .filter(
                User.email == update_data["email"],
                User.company_id == company_id,
                User.id != user_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already in use",
            )

    if "role_id" in update_data and update_data["role_id"]:
        _validate_role_id(db, update_data["role_id"], company_id)

    for field, value in update_data.items():
        setattr(user, field, value)
    user.modified_by = actor_id

    new_data = {
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role_id": user.role_id,
        "is_active": user.is_active,
    }
    changes = audit_service.compute_changes(old_data, new_data)
    if changes:
        audit_service.log_action(
            db, company_id, "updated", "user", user.id,
            user_id=actor_id, changes=changes,
        )

        # Notify user if their role was changed and sync functional areas
        if "role_id" in changes:
            new_role = (
                db.query(Role).filter(Role.id == user.role_id).first()
            )
            role_name = new_role.name if new_role else "a new role"
            notification_service.create_notification(
                db,
                company_id,
                user.id,
                title="Role Updated",
                message=f"Your role has been updated to {role_name}.",
                type="info",
                category="user",
                actor_id=actor_id,
            )
            # Sync functional areas to match new role
            if new_role:
                from app.services.role_service import sync_functional_areas_for_role
                sync_functional_areas_for_role(db, user.id, new_role.slug)

                # Workflow Arc Phase 8a — role decoupling.
                # Roles are permission grants only. UX content (saved
                # views, briefing prefs) is NOT force-re-seeded. User's
                # existing content stays theirs. Opt-in re-apply is
                # available via reapply_role_defaults_for_user().
                #
                # Spaces seed STILL runs — it's idempotent per role and
                # the Phase-8a _apply_system_spaces pass checks live
                # admin permission (Settings appears on promotion-to-
                # admin, disappears on demotion at resolve time).
                if ROLE_CHANGE_RESEED_ENABLED:
                    try:
                        from app.services.saved_views.seed import (
                            seed_for_user as _seed_saved_views,
                        )
                        _seed_saved_views(db, user=user)
                    except Exception:  # pragma: no cover — best-effort
                        import logging
                        logging.getLogger(__name__).exception(
                            "Saved views re-seed on role change failed "
                            "for user %s (non-fatal)", user.id,
                        )
                    try:
                        from app.services.briefings.preferences import (
                            seed_preferences_for_user as _seed_briefings,
                        )
                        _seed_briefings(db, user)
                    except Exception:  # pragma: no cover — best-effort
                        import logging
                        logging.getLogger(__name__).exception(
                            "Briefing preferences re-seed on role change "
                            "failed for user %s (non-fatal)", user.id,
                        )
                # Spaces seed runs unconditionally — idempotent per role
                # + system-space permission check needs to run on every
                # role change (admin grant/revoke → Settings appears/hides).
                try:
                    from app.services.spaces.seed import (
                        seed_for_user as _seed_spaces,
                    )
                    _seed_spaces(db, user=user)
                except Exception:  # pragma: no cover — best-effort
                    import logging
                    logging.getLogger(__name__).exception(
                        "Spaces seed on role change failed for "
                        "user %s (non-fatal)", user.id,
                    )

        # Notify user if their account was reactivated
        if "is_active" in changes and changes["is_active"]["new"] is True:
            notification_service.create_notification(
                db,
                company_id,
                user.id,
                title="Account Reactivated",
                message="Your account has been reactivated.",
                type="success",
                category="user",
                actor_id=actor_id,
            )

    db.commit()
    db.refresh(user)
    return user


def deactivate_user(
    db: Session, user_id: str, company_id: str, actor_id: str | None = None
) -> User:
    user = get_user(db, user_id, company_id)
    user.is_active = False

    audit_service.log_action(
        db, company_id, "deactivated", "user", user.id,
        user_id=actor_id,
        changes={"is_active": {"old": True, "new": False}},
    )

    notification_service.create_notification(
        db,
        company_id,
        user.id,
        title="Account Deactivated",
        message="Your account has been deactivated.",
        type="warning",
        category="user",
        actor_id=actor_id,
    )

    db.commit()
    db.refresh(user)
    return user


def create_users_bulk(
    db: Session, users: list[UserCreate], company_id: str, actor_id: str | None = None
) -> dict:
    """Create multiple users at once. Returns partial success — errors don't block others.

    Note (Phase 8e.2.2 Space Invariant Enforcement): each iteration
    delegates to `create_user`, which now runs the Phase-3 Spaces seed
    per user. Don't add a second seed call here — it would be
    idempotent but pure write I/O for no benefit.
    """
    created: list[UserResponse] = []
    errors: list[dict] = []

    for i, data in enumerate(users):
        try:
            user = create_user(db, data, company_id, actor_id=actor_id)
            db.refresh(user)
            created.append(UserResponse.model_validate(user))
        except HTTPException as exc:
            errors.append({
                "index": i,
                "identifier": data.email or data.username,
                "detail": exc.detail,
            })
        except Exception as exc:
            errors.append({
                "index": i,
                "identifier": data.email or data.username,
                "detail": str(exc),
            })

    return {"created": created, "errors": errors}


def reset_user_password(
    db: Session,
    user_id: str,
    new_password: str,
    company_id: str,
    actor_id: str | None = None,
) -> None:
    """Admin reset of another user's password."""
    user = get_user(db, user_id, company_id)
    user.hashed_password = hash_password(new_password)

    audit_service.log_action(
        db,
        company_id,
        "password_reset",
        "user",
        user.id,
        user_id=actor_id,
    )

    notification_service.create_notification(
        db,
        company_id,
        user.id,
        title="Password Reset",
        message="Your password has been reset by an administrator.",
        type="warning",
        category="user",
        link="/profile",
        actor_id=actor_id,
    )

    db.commit()


def reset_user_pin(
    db: Session,
    user_id: str,
    new_pin: str,
    company_id: str,
    actor_id: str | None = None,
) -> None:
    """Admin reset of a production user's PIN."""
    user = get_user(db, user_id, company_id)
    if user.track != "production_delivery":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PIN reset is only for production/delivery users",
        )
    user.pin_encrypted = encrypt_pin(new_pin)
    user.pin_set_at = datetime.now(timezone.utc)

    audit_service.log_action(
        db,
        company_id,
        "pin_reset",
        "user",
        user.id,
        user_id=actor_id,
    )

    notification_service.create_notification(
        db,
        company_id,
        user.id,
        title="PIN Reset",
        message="Your PIN has been reset by an administrator.",
        type="warning",
        category="user",
        actor_id=actor_id,
    )

    db.commit()


def get_user_pin(
    db: Session, user_id: str, company_id: str
) -> str:
    """Admin retrieval of a production user's plaintext PIN."""
    user = get_user(db, user_id, company_id)
    if user.track != "production_delivery" or not user.pin_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No PIN set for this user",
        )
    return decrypt_pin(user.pin_encrypted)


def suggest_username(
    db: Session, first_name: str, last_name: str, company_id: str
) -> str:
    """Suggest an available username for a production user within a tenant."""
    first = first_name.strip().lower().replace(" ", "")
    last = last_name.strip().lower().replace(" ", "")

    if not first:
        first = "user"

    # Try firstname.lastinitial, then firstname.lastname, then firstname.lastinitialN
    candidates = [f"{first}.{last[0]}" if last else first]
    if last:
        candidates.append(f"{first}.{last}")

    for candidate in candidates:
        exists = (
            db.query(User)
            .filter(User.username == candidate, User.company_id == company_id)
            .first()
        )
        if not exists:
            return candidate

    # Append incrementing number
    base = f"{first}.{last[0]}" if last else first
    n = 2
    while True:
        candidate = f"{base}{n}"
        exists = (
            db.query(User)
            .filter(User.username == candidate, User.company_id == company_id)
            .first()
        )
        if not exists:
            return candidate
        n += 1
