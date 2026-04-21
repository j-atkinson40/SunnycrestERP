"""Peek service types — follow-up 4 of the UI/UX arc.

Peek returns a slim per-entity-type summary designed for hover +
click previews. Not a replacement for detail GETs (which still
serve the record pages); peek is the cross-cutting preview shape
used by the four trigger surfaces listed in CLAUDE.md § UI/UX Arc
Peek Panels.

The response shape is intentionally entity-specific (not a generic
key-value bag) so renderers can type-check per-field formatting. A
caller supplies `entity_type`; the builder produces the
corresponding typed payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# Six entity types ship in follow-up 4. Expansion is post-arc (spaces,
# users, documents, etc.) — each addition = new builder in
# `PEEK_BUILDERS` + new renderer in the frontend. No schema impact.
PeekEntityType = Literal[
    "fh_case",
    "invoice",
    "sales_order",
    "task",
    "contact",
    "saved_view",
]


@dataclass
class PeekResponse:
    """Envelope returned by the /peek endpoint + per-entity builder.

    `entity_type` + `entity_id` echo so the client can cache-key off
    them without re-parsing the request. `peek` is the per-entity
    shape (kept as `dict[str, Any]` at the envelope level so adding
    a new entity type doesn't force a union widening; the builder
    guarantees shape).

    `navigate_url` is the "Open full detail →" destination. Produced
    by the builder so the client doesn't hard-code routes.

    `display_label` is the short label the frontend shows in the
    peek header (e.g. "SO-00143" for a sales order). Distinct from
    the fields inside `peek` because the header label can be
    different from any single field (e.g., a case's header shows
    "{deceased_name} — Case #{number}" composed from two fields).
    """

    entity_type: str
    entity_id: str
    display_label: str
    navigate_url: str
    peek: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "display_label": self.display_label,
            "navigate_url": self.navigate_url,
            "peek": self.peek,
        }


# ── Error types ─────────────────────────────────────────────────────


class PeekError(Exception):
    http_status: int = 400


class UnknownEntityType(PeekError):
    http_status = 400


class EntityNotFound(PeekError):
    http_status = 404


class PeekPermissionDenied(PeekError):
    http_status = 403


__all__ = [
    "PeekEntityType",
    "PeekResponse",
    "PeekError",
    "UnknownEntityType",
    "EntityNotFound",
    "PeekPermissionDenied",
]
