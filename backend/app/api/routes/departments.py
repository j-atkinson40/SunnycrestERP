from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.department import DepartmentCreate, DepartmentResponse, DepartmentUpdate
from app.services.department_service import (
    create_department,
    delete_department,
    get_departments,
    update_department,
)

router = APIRouter()


@router.get("", response_model=list[DepartmentResponse])
def list_departments(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("departments.view")),
):
    return get_departments(db, current_user.company_id, include_inactive)


@router.post("", status_code=201, response_model=DepartmentResponse)
def create(
    data: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("departments.create")),
):
    return create_department(db, data, current_user.company_id, actor_id=current_user.id)


@router.patch("/{department_id}", response_model=DepartmentResponse)
def update(
    department_id: str,
    data: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("departments.edit")),
):
    return update_department(
        db, department_id, data, current_user.company_id, actor_id=current_user.id
    )


@router.delete("/{department_id}")
def delete(
    department_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("departments.delete")),
):
    delete_department(db, department_id, current_user.company_id, actor_id=current_user.id)
    return {"detail": "Department deactivated"}
