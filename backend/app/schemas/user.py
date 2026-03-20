from datetime import datetime

from pydantic import BaseModel, EmailStr, model_validator


class UserResponse(BaseModel):
    id: str
    email: str  # may be sentinel for production users
    first_name: str
    last_name: str
    role_id: str
    role_name: str | None = None
    role_slug: str | None = None
    is_active: bool
    company_id: str
    created_at: datetime
    track: str = "office_management"
    username: str | None = None
    console_access: list[str] | None = None
    idle_timeout_minutes: int | None = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    first_name: str
    last_name: str
    track: str = "office_management"
    # Office/Management fields
    email: EmailStr | None = None
    password: str | None = None
    # Production/Delivery fields
    username: str | None = None
    pin: str | None = None
    console_access: list[str] | None = None
    idle_timeout_minutes: int | None = None
    # Common
    role_id: str | None = None  # None = default employee role

    @model_validator(mode="after")
    def validate_track_fields(self):
        if self.track == "production_delivery":
            if not self.username:
                raise ValueError("Username is required for production/delivery track")
            if not self.pin:
                raise ValueError("PIN is required for production/delivery track")
        else:
            if not self.email:
                raise ValueError("Email is required for office/management track")
            if not self.password:
                raise ValueError("Password is required for office/management track")
        return self


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    first_name: str | None = None
    last_name: str | None = None
    role_id: str | None = None
    is_active: bool | None = None
    username: str | None = None
    console_access: list[str] | None = None
    idle_timeout_minutes: int | None = None


class UserBulkCreate(BaseModel):
    users: list[UserCreate]


class UserBulkResponse(BaseModel):
    created: list[UserResponse]
    errors: list[dict]


class PinResetRequest(BaseModel):
    new_pin: str


class PinRetrieveResponse(BaseModel):
    pin: str
