from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.services import audit_service


def get_departments(
    db: Session, company_id: str, include_inactive: bool = False
) -> list[Department]:
    query = db.query(Department).filter(Department.company_id == company_id)
    if not include_inactive:
        query = query.filter(Department.is_active == True)  # noqa: E712
    return query.order_by(Department.name).all()


def get_department(db: Session, department_id: str, company_id: str) -> Department:
    dept = (
        db.query(Department)
        .filter(Department.id == department_id, Department.company_id == company_id)
        .first()
    )
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Department not found"
        )
    return dept


def create_department(
    db: Session,
    data: DepartmentCreate,
    company_id: str,
    actor_id: str | None = None,
) -> Department:
    existing = (
        db.query(Department)
        .filter(Department.name == data.name, Department.company_id == company_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A department with this name already exists",
        )

    dept = Department(
        company_id=company_id,
        name=data.name,
        description=data.description,
    )
    db.add(dept)
    db.flush()

    audit_service.log_action(
        db,
        company_id,
        "created",
        "department",
        dept.id,
        user_id=actor_id,
        changes={"name": data.name},
    )

    db.commit()
    db.refresh(dept)
    return dept


def update_department(
    db: Session,
    department_id: str,
    data: DepartmentUpdate,
    company_id: str,
    actor_id: str | None = None,
) -> Department:
    dept = get_department(db, department_id, company_id)

    old_data = {"name": dept.name, "description": dept.description, "is_active": dept.is_active}

    update_data = data.model_dump(exclude_unset=True)

    # Check name uniqueness if changing name
    if "name" in update_data and update_data["name"] != dept.name:
        existing = (
            db.query(Department)
            .filter(
                Department.name == update_data["name"],
                Department.company_id == company_id,
                Department.id != department_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A department with this name already exists",
            )

    for field, value in update_data.items():
        setattr(dept, field, value)

    new_data = {"name": dept.name, "description": dept.description, "is_active": dept.is_active}
    changes = audit_service.compute_changes(old_data, new_data)
    if changes:
        audit_service.log_action(
            db,
            company_id,
            "updated",
            "department",
            dept.id,
            user_id=actor_id,
            changes=changes,
        )

    db.commit()
    db.refresh(dept)
    return dept


def delete_department(
    db: Session,
    department_id: str,
    company_id: str,
    actor_id: str | None = None,
) -> None:
    dept = get_department(db, department_id, company_id)

    # Soft-delete: set is_active = False
    dept.is_active = False

    audit_service.log_action(
        db,
        company_id,
        "deleted",
        "department",
        dept.id,
        user_id=actor_id,
        changes={"is_active": {"old": True, "new": False}},
    )

    db.commit()
