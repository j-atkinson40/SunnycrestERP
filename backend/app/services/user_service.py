from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.security import hash_password
from app.models.employee_profile import EmployeeProfile
from app.models.role import Role
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services import audit_service, notification_service


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

    audit_service.log_action(
        db,
        company_id,
        "created",
        "user",
        user.id,
        user_id=actor_id,
        changes={
            "email": data.email,
            "first_name": data.first_name,
            "last_name": data.last_name,
            "role_id": role_id,
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
        link="/profile",
        actor_id=actor_id,
    )

    db.commit()
    db.refresh(user)
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

        # Notify user if their role was changed
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
