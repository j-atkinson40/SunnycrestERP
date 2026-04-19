"""Pydantic schemas for the (legacy) Document model.

NOTE: `DocumentResponse` below is the schema for the legacy `Document`
class (now backed by the `documents_legacy` table). Canonical-Document
schemas for Phase D-1 live in `app.schemas.canonical_document` to avoid
import collision with routes using the legacy type name.
"""

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
