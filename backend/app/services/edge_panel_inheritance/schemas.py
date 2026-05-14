"""Pydantic shapes for the Edge Panel Inheritance admin API.

Pure request/response shapes — service-layer types (ResolvedEdgePanel)
live alongside the resolver itself. These are the wire shapes consumed
by `app/api/routes/admin/edge_panel_inheritance.py`.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Scope = Literal["platform_default", "vertical_default"]


# ─── Tier 2: templates ──────────────────────────────────────────


class EdgePanelTemplateCreateRequest(BaseModel):
    scope: Scope
    vertical: str | None = None
    panel_key: str = Field(min_length=1, max_length=96)
    display_name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    pages: list[dict[str, Any]] = Field(default_factory=list)
    canvas_config: dict[str, Any] = Field(default_factory=dict)


class EdgePanelTemplateUpdateRequest(BaseModel):
    # panel_key + scope + vertical intentionally absent — service
    # rejects updates to identity fields.
    display_name: str | None = Field(default=None, max_length=160)
    description: str | None = None
    pages: list[dict[str, Any]] | None = None
    canvas_config: dict[str, Any] | None = None


class EdgePanelTemplateResponse(BaseModel):
    id: str
    scope: Scope
    vertical: str | None
    panel_key: str
    display_name: str
    description: str | None
    pages: list[dict[str, Any]]
    canvas_config: dict[str, Any]
    version: int
    is_active: bool
    created_at: str
    updated_at: str


class EdgePanelTemplateUsageResponse(BaseModel):
    compositions_count: int


# ─── Tier 3: compositions ───────────────────────────────────────


class EdgePanelCompositionUpsertRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=36)
    template_id: str = Field(min_length=1, max_length=36)
    deltas: dict[str, Any] | None = None
    canvas_config_overrides: dict[str, Any] = Field(default_factory=dict)


class EdgePanelCompositionResponse(BaseModel):
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


class EdgePanelResolveResponse(BaseModel):
    panel_key: str
    template_id: str
    template_version: int
    template_scope: str
    template_vertical: str | None
    pages: list[dict[str, Any]]
    canvas_config: dict[str, Any]
    sources: dict[str, Any]
