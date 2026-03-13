from datetime import datetime

from pydantic import BaseModel


class SyncLogResponse(BaseModel):
    id: str
    company_id: str
    sync_type: str
    source: str
    destination: str
    status: str
    records_processed: int
    records_failed: int
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
