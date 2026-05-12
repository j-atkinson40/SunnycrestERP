"""Pydantic schemas for the D-2 template registry + observability API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ── Template responses ──────────────────────────────────────────────────


class DocumentTemplateVersionResponse(BaseModel):
    """Single version of a template — read-only in D-2."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    template_id: str
    version_number: int
    status: str

    body_template: str
    subject_template: str | None = None
    variable_schema: dict[str, Any] | None = None
    sample_context: dict[str, Any] | None = None
    css_variables: dict[str, Any] | None = None
    changelog: str | None = None

    activated_at: datetime | None = None
    activated_by_user_id: str | None = None
    created_at: datetime


class DocumentTemplateVersionSummary(BaseModel):
    """Lightweight version summary for list views (no body)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    version_number: int
    status: str
    changelog: str | None = None
    activated_at: datetime | None = None
    created_at: datetime


class DocumentTemplateListItem(BaseModel):
    """One row in the template library list."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str | None = None  # NULL = platform-global
    template_key: str
    document_type: str
    output_format: str
    description: str | None = None
    supports_variants: bool
    is_active: bool
    current_version_number: int | None = None
    current_version_activated_at: datetime | None = None
    scope: str = Field(description="'platform' or 'tenant'")
    has_draft: bool = False
    created_at: datetime
    updated_at: datetime


class DocumentTemplateDetailResponse(BaseModel):
    """Detail for a single template — includes the active version content."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str | None = None
    template_key: str
    document_type: str
    output_format: str
    description: str | None = None
    supports_variants: bool
    is_active: bool
    scope: str
    created_at: datetime
    updated_at: datetime

    current_version: DocumentTemplateVersionResponse | None = None
    version_summaries: list[DocumentTemplateVersionSummary] = Field(default_factory=list)


class DocumentTemplateFilterResponse(BaseModel):
    """Paginated envelope for the template list endpoint."""

    items: list[DocumentTemplateListItem]
    total: int
    limit: int
    offset: int


# ── Extended document observability schemas ────────────────────────────


class DocumentLogItem(BaseModel):
    """One row in the Document Log table — includes template + intelligence
    linkage metadata the D-1 list response didn't surface."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    document_type: str
    title: str
    status: str
    file_size_bytes: int | None = None
    template_key: str | None = None
    template_version: int | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    intelligence_execution_id: str | None = None
    caller_workflow_run_id: str | None = None
    caller_module: str | None = None
    is_test_render: bool = False
    rendered_at: datetime | None = None
    created_at: datetime


# ── Phase D-3 editing + audit ──────────────────────────────────────────


class TemplateEditPermissionResponse(BaseModel):
    """Result of the pre-flight permission check. UI uses this to decide
    whether to show the Edit button + Fork button."""

    can_edit: bool
    reason: str | None = None
    requires_super_admin: bool = False
    requires_confirmation_text: bool = False
    can_fork: bool = False


class ValidationIssueResponse(BaseModel):
    severity: str  # "error" | "warning"
    issue_type: str
    message: str
    variable_name: str | None = None


class DraftCreateRequest(BaseModel):
    base_version_id: str | None = None
    changelog: str | None = None


class DraftUpdateRequest(BaseModel):
    body_template: str | None = None
    subject_template: str | None = None
    variable_schema: dict[str, Any] | None = None
    css_variables: dict[str, Any] | None = None
    changelog: str | None = None


class TemplateActivateRequest(BaseModel):
    changelog: str = Field(..., min_length=1)
    confirmation_text: str | None = None


class TemplateRollbackRequest(BaseModel):
    changelog: str = Field(..., min_length=1)
    confirmation_text: str | None = None


class TemplateForkRequest(BaseModel):
    target_company_id: str = Field(...)


class TemplateTestRenderRequest(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


class TemplateTestRenderResponse(BaseModel):
    output_format: str
    rendered_content: str | None = None  # HTML/text only
    rendered_subject: str | None = None
    document_id: str | None = None  # PDF only
    download_url: str | None = None  # PDF only (relative path)
    errors: list[str] = Field(default_factory=list)


class TemplateAuditLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    template_id: str
    version_id: str | None = None
    action: str
    actor_user_id: str | None = None
    actor_email: str | None = None
    changelog_summary: str | None = None
    meta_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


# ── Phase D-6: cross-tenant sharing ─────────────────────────────────


class DocumentShareCreateRequest(BaseModel):
    target_company_id: str = Field(..., min_length=36, max_length=36)
    reason: str | None = None


class DocumentShareRevokeRequest(BaseModel):
    revoke_reason: str | None = None


class DocumentShareResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    owner_company_id: str
    target_company_id: str
    permission: str
    reason: str | None = None
    granted_by_user_id: str | None = None
    granted_at: datetime
    revoked_by_user_id: str | None = None
    revoked_at: datetime | None = None
    revoke_reason: str | None = None
    source_module: str | None = None


class DocumentShareEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    share_id: str
    document_id: str | None = None
    event_type: str
    actor_user_id: str | None = None
    actor_company_id: str | None = None
    ip_address: str | None = None
    meta_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class InboxItemResponse(BaseModel):
    """Row in the admin inbox — a shared-in document from the target
    tenant's perspective. Combines the share + the underlying Document
    metadata so the UI can render in one query."""

    model_config = ConfigDict(from_attributes=True)

    share_id: str
    document_id: str
    document_type: str
    document_title: str
    document_status: str
    owner_company_id: str
    owner_company_name: str | None = None
    granted_at: datetime
    revoked_at: datetime | None = None
    reason: str | None = None
    source_module: str | None = None
    # Phase D-8: per-user inbox read state. Computed per current user
    # by the inbox endpoint (not stored on the share row).
    is_read: bool = False
    read_at: datetime | None = None


class MarkInboxReadResponse(BaseModel):
    """Response from the mark-all-read endpoint."""

    marked_count: int


# ── Phase D-7: delivery log ─────────────────────────────────────────


class DeliveryListItem(BaseModel):
    """Row in the DeliveryLog table."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    document_id: str | None = None
    channel: str
    recipient_type: str
    recipient_value: str
    recipient_name: str | None = None
    subject: str | None = None
    template_key: str | None = None
    status: str
    provider: str | None = None
    provider_message_id: str | None = None
    retry_count: int
    sent_at: datetime | None = None
    failed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime


class DeliveryDetailResponse(BaseModel):
    """Full delivery detail with provider response + linkage."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    document_id: str | None = None
    channel: str
    recipient_type: str
    recipient_value: str
    recipient_name: str | None = None
    subject: str | None = None
    body_preview: str | None = None
    template_key: str | None = None
    status: str
    provider: str | None = None
    provider_message_id: str | None = None
    provider_response: dict[str, Any] | None = None
    error_message: str | None = None
    error_code: str | None = None
    retry_count: int
    max_retries: int
    scheduled_for: datetime | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    failed_at: datetime | None = None
    caller_module: str | None = None
    caller_workflow_run_id: str | None = None
    caller_workflow_step_id: str | None = None
    caller_intelligence_execution_id: str | None = None
    caller_signature_envelope_id: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class DeliveryAdHocSendRequest(BaseModel):
    document_id: str | None = None
    channel: str = Field(..., pattern="^(email|sms)$")
    recipient_type: str = Field(...)
    recipient_value: str = Field(..., min_length=1)
    recipient_name: str | None = None
    subject: str | None = None
    template_key: str | None = None
    template_context: dict[str, Any] | None = None
    body: str | None = None
    body_html: str | None = None
    reply_to: str | None = None


# ─── Phase D-10 — Block-based template authoring ────────────────


class TemplateBlockResponse(BaseModel):
    """One block within a template version."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    template_version_id: str
    block_kind: str
    position: int
    config: dict[str, Any]
    condition: str | None = None
    parent_block_id: str | None = None
    created_at: datetime
    updated_at: datetime


class TemplateBlockCreateRequest(BaseModel):
    block_kind: str = Field(..., min_length=1, max_length=64)
    position: int | None = None
    config: dict[str, Any] | None = None
    condition: str | None = None
    parent_block_id: str | None = None


class TemplateBlockUpdateRequest(BaseModel):
    config: dict[str, Any] | None = None
    condition: str | None = None


class TemplateBlockReorderRequest(BaseModel):
    block_id_order: list[str]
    parent_block_id: str | None = None


class BlockKindResponse(BaseModel):
    """Block kind metadata for the editor's block-kind picker."""

    kind: str
    display_name: str
    description: str
    config_schema: dict[str, Any]
    accepts_children: bool


# ─── Phase D-10 — Document type catalog ─────────────────────────


class DocumentTypeStarterBlockResponse(BaseModel):
    block_kind: str
    config: dict[str, Any]
    condition: str | None = None


class DocumentTypeResponse(BaseModel):
    type_id: str
    display_name: str
    category: str
    description: str
    starter_blocks: list[DocumentTypeStarterBlockResponse]
    recommended_variables: list[str]


class DocumentTypeCategoryResponse(BaseModel):
    category_id: str
    display_name: str


class DocumentTypeCatalogResponse(BaseModel):
    categories: list[DocumentTypeCategoryResponse]
    types: list[DocumentTypeResponse]


# ─── Arc 4b.2a — Mention picker (Q-DISPATCH-5) ─────────────────────
#
# Picker subset (Q-COUPLING-1): UI vocabulary `case` / `order` /
# `contact` / `product`. The endpoint translates to substrate vocab
# (`fh_case` / `sales_order` / `contact` / `product`) at request layer.
#
# Picker subset is enforced via Literal — out-of-subset entity_types
# (e.g. `invoice`, `document`, `task`) return 422 from FastAPI's
# request validation. The mention substrate supports all 7 entity
# types in SEARCHABLE_ENTITIES; the picker shipping subset is
# deliberately narrower at v1. Expansion trigger criteria locked at
# Arc 4b.2 investigation.


MentionEntityType = Literal["case", "order", "contact", "product"]


class MentionResolveRequest(BaseModel):
    """Request shape for the dedicated mention endpoint.

    Per per-consumer endpoint shaping canon: substrate is shared with
    the command bar (`/api/v1/command-bar/query`), but the endpoint
    shape is consumer-specific. Picker doesn't need command-bar's
    intent classifier or result merging; this endpoint returns RECORD-
    shape entity hits only.
    """

    entity_type: MentionEntityType
    query: str = Field(..., min_length=0, max_length=200)
    limit: int = Field(default=10, ge=1, le=20)


class MentionResolveResponseItem(BaseModel):
    """Single mention candidate. `entity_type` is UI vocabulary (matches
    the request)."""

    entity_type: MentionEntityType
    entity_id: str
    display_name: str
    preview_snippet: str | None = None
    """Secondary context (e.g. case number, sku, status). NOT rendered
    at v1 mention-render layer per Q-ARC4B2-2 (reference-only); the
    picker UI consumes it to help operators disambiguate matches."""


class MentionResolveResponse(BaseModel):
    """Picker response — flat list of candidates ranked by resolver."""

    results: list[MentionResolveResponseItem]
    total: int
