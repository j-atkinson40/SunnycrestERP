from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: str
    company_id: str
    entity_type: str
    entity_id: str
    file_name: str
    file_size: int
    mime_type: str
    document_type: str | None = None
    r2_key: str | None = None
    metadata_json: dict | None = None
    uploaded_by: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
