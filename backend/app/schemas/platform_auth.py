from datetime import datetime

from pydantic import BaseModel, EmailStr


class PlatformLoginRequest(BaseModel):
    email: EmailStr
    password: str


class PlatformTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class PlatformRefreshRequest(BaseModel):
    refresh_token: str


class PlatformUserResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    role: str
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PlatformUserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    role: str = "support"  # super_admin | support | viewer


class PlatformUserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
