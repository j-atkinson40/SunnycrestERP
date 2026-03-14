from datetime import datetime

from pydantic import BaseModel, Field


class JobEnqueueRequest(BaseModel):
    job_type: str
    payload: dict | None = None
    priority: int = Field(default=5, ge=1, le=10)
    max_retries: int = Field(default=3, ge=0, le=10)
    delay_seconds: int = Field(default=0, ge=0)


class JobResponse(BaseModel):
    id: str
    company_id: str
    job_type: str
    payload: str | None
    priority: int
    status: str
    retry_count: int
    max_retries: int
    error_message: str | None
    result: str | None
    scheduled_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    created_by: str | None

    model_config = {"from_attributes": True}


class QueueStatsResponse(BaseModel):
    pending: int
    running: int
    completed: int
    failed: int
    dead: int
    redis_queue_depth: int
    redis_dlq_size: int
    redis_connected: bool


class SyncHealthTenant(BaseModel):
    company_id: str
    company_name: str
    status: str  # green, yellow, red
    last_sync_at: datetime | None
    last_sync_type: str | None
    last_sync_status: str | None
    error_message: str | None
    total_syncs_24h: int
    failed_syncs_24h: int


class SyncDashboardResponse(BaseModel):
    tenants: list[SyncHealthTenant]
    queue_stats: QueueStatsResponse
