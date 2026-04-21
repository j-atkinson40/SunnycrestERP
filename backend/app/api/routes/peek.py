"""Peek API — follow-up 4 of the UI/UX arc (arc finale).

Single endpoint `GET /api/v1/peek/{entity_type}/{entity_id}` returns
the slim per-entity peek shape used by the four peek trigger
surfaces (command bar RECORD tiles, briefing pending_decisions,
saved-view title cells, triage related-entities panel).

Hot path + client-side hover triggers → arc_telemetry key
`peek_fetch` + BLOCKING latency gate at p50 < 100ms, p99 < 300ms
(see `tests/test_peek_latency.py`).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.peek import (
    EntityNotFound,
    PeekError,
    UnknownEntityType,
    build_peek,
)

router = APIRouter()


class _PeekResponse(BaseModel):
    entity_type: str
    entity_id: str
    display_label: str
    navigate_url: str
    peek: dict[str, Any] = Field(default_factory=dict)


def _translate(exc: PeekError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=str(exc))


@router.get("/{entity_type}/{entity_id}", response_model=_PeekResponse)
def peek_entity(
    entity_type: str,
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _PeekResponse:
    """Return a slim peek summary for one entity.

    Budget: p50 < 100 ms / p99 < 300 ms (BLOCKING CI gate). Tenant
    isolation is enforced by each builder filtering on
    `current_user.company_id`. Unknown entity_type → 400; missing
    row → 404.
    """
    import time as _t_time
    from app.services import arc_telemetry as _arc_t

    _t0 = _t_time.perf_counter()
    _errored = False
    try:
        try:
            result = build_peek(
                db,
                user=current_user,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        except (UnknownEntityType, EntityNotFound, PeekError) as exc:
            _errored = True
            raise _translate(exc) from exc
        return _PeekResponse(**result.to_dict())
    finally:
        _arc_t.record(
            "peek_fetch",
            (_t_time.perf_counter() - _t0) * 1000.0,
            errored=_errored,
        )
