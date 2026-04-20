"""Triage — core types + Pydantic schema (v1.0).

Phase 5 of the UI/UX arc. A Triage Queue is a named session pattern
for processing a stream of pending items. Each queue composes seven
pluggable components (per the architectural principle); each queue's
config is stored as a vault item with `metadata_json.triage_queue_config`.

Schema versioning:
  - top-level `schema_version: str = "1.0"` on every config
  - registry validates on load; unknown version → skip + log warning
  - future schema evolutions bump version, run a migration over
    existing vault items, or gate with a version-aware adapter

Design discipline:
  - Pydantic models for validation + typed access + JSON round-trip
  - EVERYTHING that lives in metadata_json is defined in a Pydantic
    model here — no stringly-typed access anywhere in the code
  - Where Phase 2/3/4 used dataclasses, Phase 5 uses Pydantic because
    the config comes from user-editable vault items + untrusted JSON
    (validation is critical)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ── Schema version ──────────────────────────────────────────────────

TRIAGE_CONFIG_SCHEMA_VERSION: str = "1.0"


# ── Component-level configs ─────────────────────────────────────────


class ItemDisplayConfig(BaseModel):
    """How the current item is rendered at the top of the workspace.

    `title_field` / `subtitle_field` pull from the underlying entity
    (task.title, certificate.certificate_number, etc). Frontend
    fetches the entity via the queue's saved-view source + renders
    per its entity-specific display component.
    """

    model_config = ConfigDict(extra="forbid")

    title_field: str
    subtitle_field: str | None = None
    body_fields: list[str] = Field(default_factory=list)
    # Entity-specific React component key the frontend maps to.
    # Known: "task" | "social_service_certificate" | "generic".
    display_component: str = "generic"


class ActionType(str, Enum):
    """The semantic category of an action — drives styling +
    side-effect rules."""

    APPROVE = "approve"
    REJECT = "reject"
    SKIP = "skip"
    SNOOZE = "snooze"
    ESCALATE = "escalate"
    REASSIGN = "reassign"
    CUSTOM = "custom"


class ActionConfig(BaseModel):
    """One decision button in the action palette."""

    model_config = ConfigDict(extra="forbid")

    action_id: str
    label: str
    action_type: ActionType
    # Single key ("Enter", "d", "s") OR chord ("shift+d"). Lower-case
    # for letters; special keys use their JavaScript KeyboardEvent.key
    # names.
    keyboard_shortcut: str | None = None
    icon: str = "Circle"
    requires_reason: bool = False
    # Structured reason enum (if present, UI shows a dropdown).
    reason_options: list[str] | None = None
    confirmation_required: bool = False
    # Backend handler key — resolved to a callable in action_handlers.py.
    # Must exist in the handler registry at load time or the queue
    # config is rejected.
    handler: str
    # Optional: fire a PlaywrightScript after the handler succeeds.
    # `playwright_step_id` is a key in `playwright_scripts.PLAYWRIGHT_SCRIPTS`.
    playwright_step_id: str | None = None
    # Optional: trigger a workflow after the handler succeeds.
    workflow_id: str | None = None
    # Optional: required permission (admin override if user lacks it).
    required_permission: str | None = None


class ContextPanelType(str, Enum):
    SAVED_VIEW = "saved_view"
    DOCUMENT_PREVIEW = "document_preview"
    COMMUNICATION_THREAD = "communication_thread"
    RELATED_ENTITIES = "related_entities"
    AI_SUMMARY = "ai_summary"
    # Interactive Q&A panel — user types a question, Claude answers
    # grounded in the item + related-entity context. Follow-up 2 of
    # the UI/UX arc wires this. See
    # `backend/app/services/triage/ai_question.py`.
    AI_QUESTION = "ai_question"


class ContextPanelConfig(BaseModel):
    """A supporting panel rendered alongside the item."""

    model_config = ConfigDict(extra="forbid")

    panel_type: ContextPanelType
    title: str
    display_order: int = 0
    default_collapsed: bool = False
    # Panel-type-specific fields — each optional, keyed by which
    # panel_type uses it. Flat model (no discriminated union) keeps
    # the Pydantic parse simple; unused fields stay None per panel.
    saved_view_id: str | None = None
    document_field: str | None = None  # e.g. "pdf_url" for ss_certificates
    related_entity_type: str | None = None  # for RELATED_ENTITIES
    # Intelligence prompt key — shared by AI_SUMMARY (passive render)
    # + AI_QUESTION (interactive Q&A). Per-queue specialization lives
    # at the prompt level; each panel cites its own key.
    ai_prompt_key: str | None = None
    # AI_QUESTION panel — starter prompts rendered as clickable chips
    # to populate the question input. Optional; empty list = no chips.
    suggested_questions: list[str] = Field(default_factory=list)
    # AI_QUESTION panel — server-enforced upper bound on question
    # length. UI mirrors as a character counter.
    max_question_length: int = 500


class EmbeddedActionConfig(BaseModel):
    """Reusable action available from within the item workspace —
    not a decision, but an assistive action (generate a draft, open
    a related tool, etc). Phase 5 framework stub; actual usage TBD."""

    model_config = ConfigDict(extra="forbid")

    action_id: str
    label: str
    icon: str = "Zap"
    playwright_step_id: str | None = None
    workflow_id: str | None = None
    creates_entity_type: str | None = None


class SnoozePreset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    offset_hours: int = 24


class FlowControlsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snooze_enabled: bool = True
    snooze_presets: list[SnoozePreset] = Field(
        default_factory=lambda: [
            SnoozePreset(label="Tomorrow", offset_hours=24),
            SnoozePreset(label="Next week", offset_hours=24 * 7),
        ]
    )
    # Ordered list of role slugs. Empty = no chain (single approver).
    approval_chain: list[str] = Field(default_factory=list)
    bulk_actions_enabled: bool = False
    rules_enabled: bool = False


class CollaborationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    multi_user_enabled: bool = False
    presence_enabled: bool = False
    audit_replay_enabled: bool = False


class IntelligenceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ai_questions_enabled: bool = False
    # Scaffolded in Phase 5; actual learning loop is post-arc.
    learning_enabled: bool = False
    anomaly_detection_enabled: bool = False
    prioritization_enabled: bool = False
    # Managed Intelligence prompt key for AI question feature.
    prompt_key: str | None = None


# ── Top-level queue config ───────────────────────────────────────────


class TriageQueueConfig(BaseModel):
    """The full shape stored in `vault_items.metadata_json.triage_queue_config`."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = TRIAGE_CONFIG_SCHEMA_VERSION
    queue_id: str
    queue_name: str
    description: str = ""
    # Lucide icon name used for space pins + sidebar badges. Default
    # is a generic triage icon; platform-default queues set specific
    # icons (e.g. task_triage="CheckSquare", ss_cert_triage="FileCheck").
    # Tenant-customized queues can override via vault_item metadata.
    # Frontend consumers must ensure the icon is in
    # `PinnedSection.ICON_MAP` or the pin falls back to `Layers`.
    icon: str = "ListChecks"
    # Item stream source — exactly one of the following three must
    # be set:
    #   source_saved_view_id    — concrete Phase 2 saved view row
    #                             (per-tenant custom queues)
    #   source_inline_config    — embedded SavedViewConfig dict
    #                             (platform-default queues against
    #                             entities in Phase 2's registry)
    #   source_direct_query_key — registered direct-query builder
    #                             (platform-default queues against
    #                             entities NOT in Phase 2's registry
    #                             today; e.g. `task`,
    #                             `social_service_certificate`)
    # Direct queries live in `engine._DIRECT_QUERIES` — a small
    # dispatch table mapping key → callable(db, user) → rows.
    source_saved_view_id: str | None = None
    source_inline_config: dict[str, Any] | None = None
    source_direct_query_key: str | None = None
    # The entity type items in this queue represent.
    item_entity_type: str

    item_display: ItemDisplayConfig
    action_palette: list[ActionConfig] = Field(default_factory=list)
    context_panels: list[ContextPanelConfig] = Field(default_factory=list)
    embedded_actions: list[EmbeddedActionConfig] = Field(default_factory=list)
    flow_controls: FlowControlsConfig = Field(default_factory=FlowControlsConfig)
    collaboration: CollaborationConfig = Field(default_factory=CollaborationConfig)
    intelligence: IntelligenceConfig = Field(default_factory=IntelligenceConfig)

    # Metadata
    permissions: list[str] = Field(default_factory=list)
    audit_level: Literal["full", "summary", "minimal"] = "summary"
    enabled: bool = True
    display_order: int = 100
    # Optional: restrict to tenants matching a vertical / extension
    required_vertical: str | None = None
    required_extension: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TriageQueueConfig":
        """Parse a raw dict (from metadata_json) into a typed config.

        Raises ValidationError on unknown keys or missing required
        fields — registry catches + logs + skips the row.
        """
        return cls.model_validate(data)


# ── Runtime session types ───────────────────────────────────────────


class TriageItemSummary(BaseModel):
    """Minimal item descriptor returned by `next_item` — the full
    row lives in the underlying entity table + saved-view payload.
    """

    model_config = ConfigDict(extra="allow")

    entity_type: str
    entity_id: str
    title: str
    subtitle: str | None = None
    # Arbitrary per-queue extras the frontend renders via the
    # display component.
    extras: dict[str, Any] = Field(default_factory=dict)


class TriageActionResult(BaseModel):
    """Returned from apply_action + snooze. `status="applied"` means
    the side effect committed; "skipped" means a validation no-op
    (already in target state, etc); "errored" is surfaced as 400/500
    at the API boundary."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["applied", "skipped", "errored"]
    message: str
    next_item_id: str | None = None  # convenience — API auto-advances
    audit_log_id: str | None = None
    playwright_log_id: str | None = None
    workflow_run_id: str | None = None


class TriageSessionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    queue_id: str
    user_id: str
    started_at: datetime
    ended_at: datetime | None = None
    items_processed_count: int = 0
    items_approved_count: int = 0
    items_rejected_count: int = 0
    items_snoozed_count: int = 0
    current_item_id: str | None = None


# ── Errors ───────────────────────────────────────────────────────────


class TriageError(Exception):
    http_status = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)


class QueueNotFound(TriageError):
    http_status = 404


class SessionNotFound(TriageError):
    http_status = 404


class ActionNotAllowed(TriageError):
    http_status = 403


class NoPendingItems(TriageError):
    http_status = 404


class HandlerError(TriageError):
    http_status = 500


__all__ = [
    "TRIAGE_CONFIG_SCHEMA_VERSION",
    "TriageQueueConfig",
    "ItemDisplayConfig",
    "ActionConfig",
    "ActionType",
    "ContextPanelConfig",
    "ContextPanelType",
    "EmbeddedActionConfig",
    "SnoozePreset",
    "FlowControlsConfig",
    "CollaborationConfig",
    "IntelligenceConfig",
    "TriageItemSummary",
    "TriageActionResult",
    "TriageSessionSummary",
    "TriageError",
    "QueueNotFound",
    "SessionNotFound",
    "ActionNotAllowed",
    "NoPendingItems",
    "HandlerError",
]
