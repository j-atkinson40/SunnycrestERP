from datetime import datetime

from pydantic import BaseModel


class ImpersonateRequest(BaseModel):
    tenant_id: str
    user_id: str | None = None  # If None, impersonates the tenant's first admin
    reason: str | None = None


class ImpersonateResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_slug: str
    tenant_name: str
    impersonated_user_id: str
    impersonated_user_name: str
    expires_in_minutes: int = 30
    session_id: str


class EndImpersonationRequest(BaseModel):
    session_id: str


class ImpersonationSessionResponse(BaseModel):
    id: str
    platform_user_id: str
    platform_user_name: str | None = None
    tenant_id: str
    tenant_name: str | None = None
    impersonated_user_id: str | None = None
    impersonated_user_name: str | None = None
    ip_address: str | None = None
    actions_performed: int
    reason: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
