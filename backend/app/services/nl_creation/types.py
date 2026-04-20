"""NL Creation — core types.

Phase 4 of the UI/UX arc. Natural Language Creation with Live Overlay.

Shape glossary:

  ExtractionRequest   — what the client sends for each keystroke
  FieldExtraction     — one extracted field with value + confidence +
                        source (parser / resolver / ai) + optional
                        resolved-entity linkage
  ExtractionResult    — the full response: extractions + missing-required
                        list + raw input echo + latency for telemetry
  NLEntityConfig      — registry entry per entity type; owns field
                        definitions, AI prompt key, and space defaults
  FieldExtractor      — per-field definition (label, type, deterministic
                        parser, resolver config, required-ness)

Design principle: keep types plain dataclasses + TypedDicts for JSON-
round-trip ergonomics. Pydantic models live at the API boundary only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

# ── Enums / literals ─────────────────────────────────────────────────

EntityType = Literal["case", "sales_order", "event", "contact", "task"]

FieldType = Literal[
    "text",          # free text
    "name",          # first/middle/last name component
    "date",          # ISO date string
    "time",          # HH:MM 24-hour
    "datetime",      # ISO datetime
    "phone",         # E.164
    "email",         # lowercased string
    "entity",        # reference to a vault entity (CRM, contact, case)
    "enum",          # one of a fixed set
    "currency",      # decimal number
    "quantity",      # {value, unit?}
    "boolean",       # true/false
]

ExtractionSource = Literal[
    "structured_parser",   # deterministic <5ms parser
    "entity_resolver",     # fuzzy match against vault (company_entity, contact, ...)
    "ai_extraction",       # Intelligence-backed fallback
    "space_default",       # defaulted from active space config
]

# ── Field-level extraction ───────────────────────────────────────────


@dataclass
class FieldExtraction:
    """One extracted field as returned by the orchestrator.

    `extracted_value` is the typed Python value to be persisted.
    `display_value` is the user-facing string shown in the overlay
    (e.g. "Today (2026-04-20)" instead of "2026-04-20"). Both are
    present so the client can render without re-formatting.

    `resolved_entity_id` + `resolved_entity_type` are populated ONLY
    when `source == "entity_resolver"` and the resolver produced a
    confident match. When they're set, the client renders the field
    as a pill + knows to link to that entity on click.
    """

    field_key: str
    field_label: str
    extracted_value: Any
    display_value: str
    confidence: float
    source: ExtractionSource
    resolved_entity_id: str | None = None
    resolved_entity_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_key": self.field_key,
            "field_label": self.field_label,
            "extracted_value": self.extracted_value,
            "display_value": self.display_value,
            "confidence": self.confidence,
            "source": self.source,
            "resolved_entity_id": self.resolved_entity_id,
            "resolved_entity_type": self.resolved_entity_type,
        }


# ── Request / result envelopes ───────────────────────────────────────


@dataclass
class ExtractionRequest:
    """Client → server shape for `POST /api/v1/nl-creation/extract`.

    `prior_extractions` lets clients preserve high-confidence
    extractions across keystrokes when they've been manually edited
    by the user. The AI caller adds an "already extracted" block so
    the model doesn't revert user edits.
    """

    entity_type: EntityType
    natural_language: str
    tenant_id: str
    user_id: str
    active_space_id: str | None = None
    prior_extractions: list[FieldExtraction] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Server → client shape.

    Ordered for stable overlay rendering: structured_parser hits
    first (low-latency, deterministic), then entity_resolver pills,
    then ai_extraction. `missing_required` lists field_keys that are
    marked required in the entity config but have no extraction.
    """

    entity_type: EntityType
    extractions: list[FieldExtraction]
    missing_required: list[str]
    raw_input: str
    extraction_ms: int
    # Raw execution telemetry from the Intelligence call (when it
    # ran). Lets the client surface cost/latency debug info; NOT
    # shown to end-users.
    ai_execution_id: str | None = None
    ai_latency_ms: int | None = None
    # Space-default entries the user didn't override — tracked for
    # telemetry + UI hint ("Inherited from Arrangement space").
    space_default_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "extractions": [e.to_dict() for e in self.extractions],
            "missing_required": list(self.missing_required),
            "raw_input": self.raw_input,
            "extraction_ms": self.extraction_ms,
            "ai_execution_id": self.ai_execution_id,
            "ai_latency_ms": self.ai_latency_ms,
            "space_default_fields": list(self.space_default_fields),
        }


# ── Entity registry definitions ──────────────────────────────────────


@dataclass
class FieldExtractor:
    """Per-field extraction config.

    `structured_parser` is a pure function `(text: str) -> (value,
    confidence, display) | None`. It runs first; if it hits, AI
    extraction skips this field.

    `entity_resolver_config` is a dict describing how to resolve a
    candidate string to a vault entity. Example for
    `case.funeral_home`:

        {
            "target": "company_entity",
            "filters": {"is_funeral_home": True},
            "similarity_threshold": 0.35,
        }

    When `target == "company_entity"`, the resolver uses pg_trgm via
    `resolve_company_entity()`. Other targets route to Phase 1's
    resolver (`target in ("contact", "fh_case")`).
    """

    field_key: str
    field_label: str
    field_type: FieldType
    required: bool = False
    enum_values: list[str] | None = None
    # Pure parser; returns None on miss. Signature is intentionally
    # loose so parsers can decide their own return shape.
    structured_parser: Callable[[str], dict | None] | None = None
    entity_resolver_config: dict[str, Any] | None = None
    # Short hint shown in the AI prompt's field-list — keeps the
    # prompt compact while giving Claude just enough context.
    ai_hint: str | None = None


# A space_defaults entry is indexed by the space name (lowercase).
# Values are a dict of field_key → default_value applied when the
# user hasn't mentioned that field in their NL input.
SpaceDefaults = dict[str, dict[str, Any]]


@dataclass
class NLEntityConfig:
    """Per-entity registry entry.

    `ai_prompt_key` points at a managed Intelligence prompt (see
    `scripts/seed_intelligence.py`). Phase 4 seeds:
      - nl_creation.extract.case
      - nl_creation.extract.sales_order
      - nl_creation.extract.event
      - nl_creation.extract.contact

    `creator_callable` is the function that actually materializes
    the entity from an ExtractionResult. API `/create` endpoint
    hands the result to this callable. Signature:
    `(db, user, extractions: list[FieldExtraction], raw_input: str)
      -> {"entity_id": str, "entity_type": str, "navigate_url": str}`
    """

    entity_type: EntityType
    display_name: str
    field_extractors: list[FieldExtractor]
    ai_prompt_key: str
    creator_callable: Callable[..., dict[str, Any]]
    space_defaults: SpaceDefaults = field(default_factory=dict)
    # Post-create navigate URL template: `/cases/{entity_id}`, etc.
    navigate_url_template: str = "/{entity_id}"
    # Permission gate checked at `/create` time (mirrors the Phase 1
    # create-action `required_permission`). None bypasses.
    required_permission: str | None = None

    @property
    def required_fields(self) -> list[str]:
        return [e.field_key for e in self.field_extractors if e.required]

    def field_by_key(self, key: str) -> FieldExtractor | None:
        for e in self.field_extractors:
            if e.field_key == key:
                return e
        return None


# ── Errors ───────────────────────────────────────────────────────────


class NLCreationError(Exception):
    """Base error. `http_status` lets the API layer translate to
    HTTPException cleanly."""

    http_status = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)


class UnknownEntityType(NLCreationError):
    http_status = 404


class ExtractionFailed(NLCreationError):
    http_status = 500


class CreationValidationError(NLCreationError):
    http_status = 400
