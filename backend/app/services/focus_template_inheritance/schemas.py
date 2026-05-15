"""Pydantic shapes for the Focus Template Inheritance admin API.

Pure request/response shapes — service-layer types live alongside
the services themselves (e.g. `resolver.ResolvedFocus`). These are
the wire shapes consumed by `app/api/routes/admin/focus_template_inheritance.py`.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ─── Chrome (sub-arc B-3.5 — v2 preset-driven vocabulary) ───────


class ChromeBlob(BaseModel):
    """Chrome v2 shape used at all three tiers. Each field is
    independently nullable and optional — absent keys inherit from
    the parent tier, explicit None overrides the parent (key-presence
    check). The resolver expands `preset` into its canonical defaults
    before cross-tier cascade.
    """

    preset: (
        Literal[
            "card", "modal", "dropdown", "toast", "floating", "frosted", "custom"
        ]
        | None
    ) = None
    elevation: int | None = Field(default=None, ge=0, le=100)
    corner_radius: int | None = Field(default=None, ge=0, le=100)
    backdrop_blur: int | None = Field(default=None, ge=0, le=100)
    background_token: str | None = Field(default=None, min_length=1)
    border_token: str | None = Field(default=None, min_length=1)
    padding_token: str | None = Field(default=None, min_length=1)

    model_config = {"extra": "forbid"}


# ─── Substrate (sub-arc B-4 — page-background vocabulary) ────────


class SubstrateBlob(BaseModel):
    """Substrate v1 shape used at Tier 2 (template default) + Tier 3
    (composition override). Each field is independently nullable and
    optional — absent keys inherit from Tier 2, explicit None
    overrides Tier 2 (key-presence check). The resolver expands
    `preset` into its canonical defaults before cross-tier cascade.

    Tier 1 cores are substrate-free by design — substrate is a
    Focus-level atmospheric backdrop, not a core composition concern.
    """

    preset: (
        Literal[
            "morning-warm",
            "morning-cool",
            "evening-lounge",
            "neutral",
            "custom",
        ]
        | None
    ) = None
    intensity: int | None = Field(default=None, ge=0, le=100)
    base_token: str | None = Field(default=None, min_length=1)
    accent_token_1: str | None = Field(default=None, min_length=1)
    accent_token_2: str | None = Field(default=None, min_length=1)

    model_config = {"extra": "forbid"}


# ─── Typography (sub-arc B-5 — type-treatment vocabulary) ───────


class TypographyBlob(BaseModel):
    """Typography v1 shape used at Tier 2 (template default) + Tier 3
    (composition override). Each field is independently nullable and
    optional — absent keys inherit from Tier 2, explicit None
    overrides Tier 2 (key-presence check). The resolver expands
    `preset` into its canonical defaults before cross-tier cascade.

    Tier 1 cores are typography-free by design — typography is a
    Focus-level concern, not a core composition concern.

    Vocabulary scope: weight + color only. Family / line-height /
    letter-spacing / size are platform-canonical concerns owned by
    DESIGN_LANGUAGE §4 and are NOT part of this v1 vocabulary.
    """

    preset: (
        Literal["card-text", "frosted-text", "headline", "custom"]
        | None
    ) = None
    heading_weight: int | None = Field(default=None, ge=400, le=900)
    heading_color_token: str | None = Field(default=None, min_length=1)
    body_weight: int | None = Field(default=None, ge=400, le=900)
    body_color_token: str | None = Field(default=None, min_length=1)

    model_config = {"extra": "forbid"}


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
    chrome: dict[str, Any] = Field(default_factory=dict)


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
    chrome: dict[str, Any] | None = None


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
    chrome: dict[str, Any]
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
    chrome_overrides: dict[str, Any] = Field(default_factory=dict)
    # Sub-arc B-4: Tier 2 page-background substrate default.
    substrate: dict[str, Any] = Field(default_factory=dict)
    # Sub-arc B-5: Tier 2 typography default.
    typography: dict[str, Any] = Field(default_factory=dict)


class TemplateUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=160)
    description: str | None = None
    rows: list[dict[str, Any]] | None = None
    canvas_config: dict[str, Any] | None = None
    chrome_overrides: dict[str, Any] | None = None
    # Sub-arc B-4: omit to preserve prior substrate on version-bump.
    substrate: dict[str, Any] | None = None
    # Sub-arc B-5: omit to preserve prior typography on version-bump.
    typography: dict[str, Any] | None = None


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
    chrome_overrides: dict[str, Any]
    # Sub-arc B-4: stored substrate blob (pre-cascade).
    substrate: dict[str, Any]
    # Sub-arc B-5: stored typography blob (pre-cascade).
    typography: dict[str, Any]
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
    # Sub-arc B-3: resolved chrome (None when every chrome field
    # resolves to None across all tiers — saves consumers rendering
    # an empty wrapper).
    resolved_chrome: dict[str, Any] | None = None
    # Sub-arc B-4: resolved page-background substrate (None when
    # every substrate field resolves to None across Tier 2 + Tier 3 —
    # cores stay substrate-free by design).
    resolved_substrate: dict[str, Any] | None = None
    # Sub-arc B-5: resolved typography (None when every typography
    # field resolves to None across Tier 2 + Tier 3 — cores stay
    # typography-free by design).
    resolved_typography: dict[str, Any] | None = None
    sources: dict[str, Any]
