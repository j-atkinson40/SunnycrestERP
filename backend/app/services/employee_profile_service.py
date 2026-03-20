from sqlalchemy.orm import Session, joinedload

from app.models.employee_profile import EmployeeProfile
from app.schemas.employee_profile import EmployeeProfileAdminUpdate, EmployeeProfileUpdate
from app.services import audit_service, notification_service


def get_or_create_profile(db: Session, user_id: str) -> EmployeeProfile:
    """Get existing profile or create an empty one."""
    profile = (
        db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.department_obj))
        .filter(EmployeeProfile.user_id == user_id)
        .first()
    )
    if not profile:
        profile = EmployeeProfile(user_id=user_id)
        db.add(profile)
        db.flush()
        db.commit()
        db.refresh(profile)
    return profile


def get_profile(db: Session, user_id: str) -> EmployeeProfile | None:
    """Get profile for a user, or None."""
    return (
        db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.department_obj))
        .filter(EmployeeProfile.user_id == user_id)
        .first()
    )


def update_profile(
    db: Session,
    user_id: str,
    data: EmployeeProfileUpdate | EmployeeProfileAdminUpdate,
    actor_id: str | None = None,
    company_id: str | None = None,
) -> EmployeeProfile:
    """Update employee profile. Creates profile if it doesn't exist."""
    profile = get_or_create_profile(db, user_id)

    all_fields = [
        "phone", "position", "department_id", "hire_date",
        "address_street", "address_city", "address_state", "address_zip",
        "emergency_contact_name", "emergency_contact_phone", "notes",
        "functional_areas",
    ]
    old_data = {}
    for f in all_fields:
        val = getattr(profile, f)
        # Convert date to string for JSON serialization
        old_data[f] = str(val) if val is not None and hasattr(val, "isoformat") else val

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)
    profile.modified_by = actor_id

    new_data = {}
    for f in all_fields:
        val = getattr(profile, f)
        new_data[f] = str(val) if val is not None and hasattr(val, "isoformat") else val

    changes = audit_service.compute_changes(old_data, new_data)
    if changes and company_id:
        audit_service.log_action(
            db, company_id, "updated", "employee_profile", user_id,
            user_id=actor_id, changes=changes,
        )

        # Notify user when an admin updates their profile (not self-edit)
        if actor_id and actor_id != user_id:
            from app.models.user import User

            actor = db.query(User).filter(User.id == actor_id).first()
            actor_name = (
                f"{actor.first_name} {actor.last_name}" if actor else "An administrator"
            )
            notification_service.create_notification(
                db,
                company_id,
                user_id,
                title="Profile Updated",
                message=f"Your employee profile was updated by {actor_name}.",
                type="info",
                category="employee",
                link="/profile",
                actor_id=actor_id,
            )

    db.commit()
    db.refresh(profile)
    return profile
