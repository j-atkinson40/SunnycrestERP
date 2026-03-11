from datetime import datetime

from pydantic import BaseModel


class RoleCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    permission_keys: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class RoleResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    is_system: bool
    is_active: bool
    permission_keys: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class RolePermissionUpdate(BaseModel):
    permission_keys: list[str]


class UserPermissionOverrideRequest(BaseModel):
    permission_key: str
    granted: bool


class UserPermissionOverridesResponse(BaseModel):
    effective_permissions: list[str]
    overrides: list[dict]
