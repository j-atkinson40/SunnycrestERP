from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.core.roles import Role


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    first_name: str
    last_name: str
    role: Role
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    role: Role = Role.EMPLOYEE


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    first_name: str | None = None
    last_name: str | None = None
    role: Role | None = None
    is_active: bool | None = None
