from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.equipment import (
    EquipmentAssign,
    EquipmentCreate,
    EquipmentResponse,
    EquipmentUpdate,
)
from app.services.equipment_service import (
    assign_equipment,
    create_equipment,
    delete_equipment,
    get_equipment,
    get_equipment_list,
    update_equipment,
)

router = APIRouter()


@router.get("", response_model=list[EquipmentResponse])
def list_equipment(
    assigned_to: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.view")),
):
    return get_equipment_list(db, current_user.company_id, assigned_to)


@router.get("/{equipment_id}", response_model=EquipmentResponse)
def read_equipment(
    equipment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.view")),
):
    return get_equipment(db, equipment_id, current_user.company_id)


@router.post("", status_code=201, response_model=EquipmentResponse)
def create(
    data: EquipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.edit")),
):
    return create_equipment(db, data, current_user.company_id)


@router.patch("/{equipment_id}", response_model=EquipmentResponse)
def update(
    equipment_id: str,
    data: EquipmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.edit")),
):
    return update_equipment(db, equipment_id, data, current_user.company_id)


@router.post("/{equipment_id}/assign", response_model=EquipmentResponse)
def assign(
    equipment_id: str,
    data: EquipmentAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.edit")),
):
    return assign_equipment(
        db,
        equipment_id,
        data.assigned_to,
        current_user.company_id,
        data.assigned_date,
    )


@router.delete("/{equipment_id}")
def remove(
    equipment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.edit")),
):
    delete_equipment(db, equipment_id, current_user.company_id)
    return {"detail": "Equipment deleted"}
