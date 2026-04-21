"""Peek service — follow-up 4 of the UI/UX arc (arc finale).

Cross-cutting entity preview. Backs the `GET /api/v1/peek/{type}/{id}`
endpoint + the four frontend peek trigger surfaces (command bar
RECORD tiles, briefing pending_decisions, saved-view title cells,
triage related-entities panel).

Public API:
    build_peek(db, user=..., entity_type=..., entity_id=...) → PeekResponse
    PEEK_BUILDERS — dispatch dict for adding new entity types
    PeekResponse, PeekError, UnknownEntityType, EntityNotFound —
        typed response + errors consumed by the API layer
"""

from app.services.peek.builders import PEEK_BUILDERS, build_peek
from app.services.peek.types import (
    EntityNotFound,
    PeekEntityType,
    PeekError,
    PeekPermissionDenied,
    PeekResponse,
    UnknownEntityType,
)

__all__ = [
    "PEEK_BUILDERS",
    "build_peek",
    "PeekEntityType",
    "PeekResponse",
    "PeekError",
    "UnknownEntityType",
    "EntityNotFound",
    "PeekPermissionDenied",
]
