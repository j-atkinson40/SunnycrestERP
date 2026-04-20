"""Command Bar Platform Layer — Phase 1 API route.

POST /api/v1/command-bar/query

This is the contract surface for the command bar. Frontend callers
depend on the response shape defined here; it maps 1:1 to the
`QueryResponse` dataclass in
`app.services.command_bar.retrieval`.

See also:
  - /api/v1/ai-command/* — legacy endpoints. See CLAUDE.md §4
    "Command Bar Migration Tracking" for the deprecation plan.
    Kept alive during the frontend migration period.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.command_bar import (
    QueryContext,
    query as command_bar_query,
)

router = APIRouter()


# ── Request / response schemas ───────────────────────────────────────


class _QueryContextBody(BaseModel):
    current_page: str | None = Field(
        default=None, description="Path of the page the user is on"
    )
    current_entity_type: str | None = Field(
        default=None,
        description="Entity type of the current record, if any",
    )
    current_entity_id: str | None = Field(
        default=None,
        description="ID of the current record, if any",
    )
    # Phase 3 — Spaces. Frontend reads this from SpaceContext and
    # sends it on every query. Server-side: (a) boosts pinned
    # targets, (b) synthesizes space-switch results on name match.
    active_space_id: str | None = Field(
        default=None,
        description=(
            "Currently-active space id (pn_...) if the user has one "
            "selected. Phase 3."
        ),
    )


class QueryRequest(BaseModel):
    query: str = Field(..., description="Raw user input")
    max_results: int = Field(
        default=10, ge=1, le=50, description="Cap on results returned"
    )
    context: _QueryContextBody | None = None


class _ResultItemResponse(BaseModel):
    id: str
    type: Literal[
        "navigate",
        "create",
        "search_result",
        "action",
        "saved_view",  # Phase 2 — frontend adapter maps to VIEW rank
    ]
    entity_type: str | None = None
    primary_label: str
    secondary_context: str | None = None
    icon: str
    url: str | None = None
    action_id: str | None = None
    score: float


class QueryResponseBody(BaseModel):
    intent: Literal["navigate", "search", "create", "action", "empty"]
    results: list[_ResultItemResponse]
    total: int


# ── Route ────────────────────────────────────────────────────────────


@router.post("/query", response_model=QueryResponseBody)
def query_command_bar(
    body: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QueryResponseBody:
    """Run a command-bar query.

    Classifies intent, matches actions from the registry, fuzzy-
    searches vault entities, merges + ranks results, returns the
    top N.

    Performance budget: p50 < 100 ms, p99 < 300 ms. See the
    performance test suite at
    `backend/tests/perf/test_command_bar_latency.py`.

    Tenant isolation: every query filters by `current_user.company_id`.
    Permission gates on individual registry entries are enforced in
    the orchestrator.
    """
    import time as _t_time
    from app.services import arc_telemetry as _arc_t
    _t0 = _t_time.perf_counter()
    _errored = False

    ctx_body = body.context
    context = (
        QueryContext(
            current_page=ctx_body.current_page,
            current_entity_type=ctx_body.current_entity_type,
            current_entity_id=ctx_body.current_entity_id,
            active_space_id=ctx_body.active_space_id,
        )
        if ctx_body is not None
        else None
    )

    try:
        response = command_bar_query(
            db,
            query_text=body.query,
            user=current_user,
            max_results=body.max_results,
            context=context,
        )
    except Exception:
        _errored = True
        raise
    finally:
        _arc_t.record(
            "command_bar_query",
            (_t_time.perf_counter() - _t0) * 1000.0,
            errored=_errored,
        )

    return QueryResponseBody(
        intent=response.intent,
        results=[
            _ResultItemResponse(
                id=r.id,
                type=r.type,
                entity_type=r.entity_type or r.result_entity_type,
                primary_label=r.primary_label,
                secondary_context=r.secondary_context,
                icon=r.icon,
                url=r.url,
                action_id=r.action_id,
                score=r.score,
            )
            for r in response.results
        ],
        total=response.total,
    )
