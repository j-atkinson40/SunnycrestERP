from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    first_name: str
    last_name: str
    role_id: str
    role_name: str | None = None
    role_slug: str | None = None
    is_active: bool
    company_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    role_id: str | None = None  # None = default employee role


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    first_name: str | None = None
    last_name: str | None = None
    role_id: str | None = None
    is_active: bool | None = None
