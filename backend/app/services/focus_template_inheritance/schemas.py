"""Pydantic shapes for the Focus Template Inheritance admin API.

Pure request/response shapes — service-layer types live alongside
the services themselves (e.g. `resolver.ResolvedFocus`). These are
the wire shapes consumed by `app/api/routes/admin/focus_template_inheritance.py`.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ─── Tier 1: cores ──────────────────────────────────────────────


class CoreCreateRequest(BaseModel):
    core_slug: str = Field(min_length=1, max_length=96)
    display_name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    registered_component_kind: str = Field(min_length=1, max_length=32)
    registered_component_name: str = Field(min_length=1, max_length=96)
    default_starting_column: int = 0
    default_column_span: int = 12
    default_row_index: int = 0
    min_column_span: int = 6
    max_column_span: int = 12
    canvas_config: dict[str, Any] = Field(default_factory=dict)


class CoreUpdateRequest(BaseModel):
    # core_slug intentionally absent — service rejects updates to slug.
    display_name: str | None = Field(default=None, max_length=160)
    description: str | None = None
    registered_component_kind: str | None = Field(default=None, max_length=32)
    registered_component_name: str | None = Field(default=None, max_length=96)
    default_starting_column: int | None = None
    default_column_span: int | None = None
    default_row_index: int | None = None
    min_column_span: int | None = None
    max_column_span: int | None = None
    canvas_config: dict[str, Any] | None = None


class CoreResponse(BaseModel):
    id: str
    core_slug: str
    display_name: str
    description: str | None
    registered_component_kind: str
    registered_component_name: str
    default_starting_column: int
    default_column_span: int
    default_row_index: int
    min_column_span: int
    max_column_span: int
    canvas_config: dict[str, Any]
    version: int
    is_active: bool
    created_at: str
    updated_at: str


class CoreUsageResponse(BaseModel):
    templates_count: int
    templates: list[dict[str, Any]]


# ─── Tier 2: templates ──────────────────────────────────────────


Scope = Literal["platform_default", "vertical_default"]


class TemplateCreateRequest(BaseModel):
    scope: Scope
    vertical: str | None = None
    template_slug: str = Field(min_length=1, max_length=96)
    display_name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    inherits_from_core_id: str = Field(min_length=1, max_length=36)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    canvas_config: dict[str, Any] = Field(default_factory=dict)


class TemplateUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=160)
    description: str | None = None
    rows: list[dict[str, Any]] | None = None
    canvas_config: dict[str, Any] | None = None


class TemplateResponse(BaseModel):
    id: str
    scope: Scope
    vertical: str | None
    template_slug: str
    display_name: str
    description: str | None
    inherits_from_core_id: str
    inherits_from_core_version: int
    rows: list[dict[str, Any]]
    canvas_config: dict[str, Any]
    version: int
    is_active: bool
    created_at: str
    updated_at: str


class TemplateUsageResponse(BaseModel):
    compositions_count: int


# ─── Tier 3: compositions ───────────────────────────────────────


class CompositionUpsertRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=36)
    template_id: str = Field(min_length=1, max_length=36)
    deltas: dict[str, Any] | None = None
    canvas_config_overrides: dict[str, Any] = Field(default_factory=dict)


class CompositionResponse(BaseModel):
    id: str
    tenant_id: str
    inherits_from_template_id: str
    inherits_from_template_version: int
    deltas: dict[str, Any]
    canvas_config_overrides: dict[str, Any]
    version: int
    is_active: bool
    created_at: str
    updated_at: str


# ─── Resolver ───────────────────────────────────────────────────


class ResolveResponse(BaseModel):
    template_id: str
    template_slug: str
    template_version: int
    template_scope: str
    template_vertical: str | None
    core_id: str
    core_slug: str
    core_version: int
    core_registered_component: dict[str, str]
    rows: list[dict[str, Any]]
    canvas_config: dict[str, Any]
    sources: dict[str, Any]
