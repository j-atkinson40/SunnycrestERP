from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TenantOverview(BaseModel):
    id: str
    name: str
    slug: str
    is_active: bool
    user_count: int
    created_at: datetime
    subscription_status: str | None = None
    plan_name: str | None = None
    last_sync_at: datetime | None = None
    sync_status: str | None = None  # green, yellow, red


class SystemHealth(BaseModel):
    total_tenants: int
    active_tenants: int
    inactive_tenants: int
    total_users: int
    active_users: int
    total_jobs_24h: int
    failed_jobs_24h: int
    redis_connected: bool
    db_connected: bool


class SuperDashboard(BaseModel):
    system_health: SystemHealth
    tenants: list[TenantOverview]
    billing_mrr: Decimal
    billing_active: int
    billing_past_due: int
