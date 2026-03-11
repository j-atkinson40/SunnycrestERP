from sqlalchemy.orm import Session

from app.models.employee_profile import EmployeeProfile
from app.schemas.employee_profile import EmployeeProfileAdminUpdate, EmployeeProfileUpdate
from app.services import audit_service


def get_or_create_profile(db: Session, user_id: str) -> EmployeeProfile:
    """Get existing profile or create an empty one."""
    profile = (
        db.query(EmployeeProfile)
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
        "phone", "position", "department", "hire_date",
        "address_street", "address_city", "address_state", "address_zip",
        "emergency_contact_name", "emergency_contact_phone", "notes",
    ]
    old_data = {}
    for f in all_fields:
        val = getattr(profile, f)
        # Convert date to string for JSON serialization
        old_data[f] = str(val) if val is not None and hasattr(val, "isoformat") else val

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

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

    db.commit()
    db.refresh(profile)
    return profile
