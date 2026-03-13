from datetime import datetime

from pydantic import BaseModel, Field


class SageExportConfigResponse(BaseModel):
    id: str
    company_id: str
    warehouse_code: str
    export_directory: str | None = None
    column_mapping: str | None = None
    is_active: bool
    last_export_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SageExportConfigUpdate(BaseModel):
    warehouse_code: str | None = None
    export_directory: str | None = None


class SageExportRequest(BaseModel):
    date_from: datetime = Field(..., description="Start of export date range")
    date_to: datetime = Field(..., description="End of export date range")


class SageExportResponse(BaseModel):
    csv_data: str
    record_count: int
    sync_log_id: str
