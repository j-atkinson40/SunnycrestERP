from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.equipment import Equipment
from app.schemas.equipment import EquipmentCreate, EquipmentUpdate


def get_equipment_list(
    db: Session, company_id: str, assigned_to: str | None = None
) -> list[Equipment]:
    query = db.query(Equipment).filter(Equipment.company_id == company_id)
    if assigned_to:
        query = query.filter(Equipment.assigned_to == assigned_to)
    return query.order_by(Equipment.created_at.desc()).all()


def get_equipment(
    db: Session, equipment_id: str, company_id: str
) -> Equipment:
    equip = (
        db.query(Equipment)
        .filter(Equipment.id == equipment_id, Equipment.company_id == company_id)
        .first()
    )
    if not equip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment not found",
        )
    return equip


def create_equipment(
    db: Session, data: EquipmentCreate, company_id: str
) -> Equipment:
    equip = Equipment(
        company_id=company_id,
        name=data.name,
        serial_number=data.serial_number,
        type=data.type,
        description=data.description,
    )
    db.add(equip)
    db.commit()
    db.refresh(equip)
    return equip


def update_equipment(
    db: Session,
    equipment_id: str,
    data: EquipmentUpdate,
    company_id: str,
) -> Equipment:
    equip = get_equipment(db, equipment_id, company_id)
    for field in ("name", "serial_number", "type", "description", "status"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(equip, field, val)
    db.commit()
    db.refresh(equip)
    return equip


def assign_equipment(
    db: Session,
    equipment_id: str,
    assigned_to: str | None,
    company_id: str,
    assigned_date: date | None = None,
) -> Equipment:
    equip = get_equipment(db, equipment_id, company_id)
    equip.assigned_to = assigned_to
    equip.assigned_date = assigned_date
    if assigned_to:
        equip.status = "assigned"
    else:
        equip.status = "available"
    db.commit()
    db.refresh(equip)
    return equip


def delete_equipment(
    db: Session, equipment_id: str, company_id: str
) -> None:
    equip = get_equipment(db, equipment_id, company_id)
    db.delete(equip)
    db.commit()
