"""Pydantic schemas for the canonical Document model (Phase D-1).

Schemas for `app.models.canonical_document.Document` + DocumentVersion.
Lives in a separate module from `app.schemas.document` (which holds the
legacy Document schema) so route files can import whichever they need
without aliasing.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    version_number: int
    storage_key: str
    mime_type: str
    file_size_bytes: int | None
    rendered_at: datetime
    rendered_by_user_id: str | None
    rendering_context_hash: str | None
    render_reason: str | None
    is_current: bool


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    document_type: str
    title: str
    description: str | None
    storage_key: str
    mime_type: str
    file_size_bytes: int | None
    status: str
    template_key: str | None
    template_version: int | None
    rendered_at: datetime | None
    rendered_by_user_id: str | None
    rendering_duration_ms: int | None
    rendering_context_hash: str | None

    # Polymorphic entity linkage
    entity_type: str | None
    entity_id: str | None

    # Specialty linkage
    sales_order_id: str | None
    fh_case_id: str | None
    disinterment_case_id: str | None
    invoice_id: str | None
    customer_statement_id: str | None
    price_list_version_id: str | None
    safety_program_generation_id: str | None

    # Source linkage
    caller_module: str | None
    caller_workflow_run_id: str | None
    caller_workflow_step_id: str | None
    intelligence_execution_id: str | None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class DocumentDetailResponse(DocumentResponse):
    """Detail response — includes full version history."""
    versions: list[DocumentVersionResponse] = Field(default_factory=list)


class DocumentListItem(BaseModel):
    """Slimmed-down shape for list pages."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    document_type: str
    title: str
    status: str
    mime_type: str
    file_size_bytes: int | None
    entity_type: str | None
    entity_id: str | None
    template_key: str | None
    rendered_at: datetime | None
    created_at: datetime


class DocumentRegenerateRequest(BaseModel):
    reason: str = Field("manual_regenerate", min_length=1, max_length=255)
    context_override: dict[str, Any] | None = None


class DocumentDownloadResponse(BaseModel):
    """Returned by the download endpoint when a JSON response is preferred
    over a 307 redirect (programmatic callers)."""

    document_id: str
    version_id: str
    version_number: int
    storage_key: str
    presigned_url: str
    expires_at: datetime
