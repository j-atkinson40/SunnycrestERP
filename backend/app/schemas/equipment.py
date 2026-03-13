from datetime import date, datetime

from pydantic import BaseModel


class EquipmentCreate(BaseModel):
    name: str
    serial_number: str | None = None
    type: str | None = None
    description: str | None = None


class EquipmentUpdate(BaseModel):
    name: str | None = None
    serial_number: str | None = None
    type: str | None = None
    description: str | None = None
    status: str | None = None


class EquipmentAssign(BaseModel):
    assigned_to: str | None = None  # user_id or None to unassign
    assigned_date: date | None = None


class EquipmentResponse(BaseModel):
    id: str
    company_id: str
    name: str
    serial_number: str | None = None
    type: str | None = None
    description: str | None = None
    status: str
    assigned_to: str | None = None
    assigned_date: date | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
