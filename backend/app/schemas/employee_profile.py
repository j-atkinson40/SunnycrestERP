from datetime import date, datetime

from pydantic import BaseModel


class EmployeeProfileResponse(BaseModel):
    """Full profile response."""

    id: str
    user_id: str
    phone: str | None = None
    position: str | None = None
    department_id: str | None = None
    department_name: str | None = None
    hire_date: date | None = None
    address_street: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    notes: str | None = None
    functional_areas: list[str] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EmployeeProfileUpdate(BaseModel):
    """Fields an employee can update about themselves."""

    phone: str | None = None
    address_street: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None


class EmployeeProfileAdminUpdate(EmployeeProfileUpdate):
    """Extended fields only admins can set."""

    position: str | None = None
    department_id: str | None = None
    hire_date: date | None = None
    notes: str | None = None
    functional_areas: list[str] | None = None
