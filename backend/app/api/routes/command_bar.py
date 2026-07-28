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

from decimal import Decimal
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


# ── S-1 — Entity portal hydration (§4.2) ─────────────────────────────
# Second-call hydration: fired on result HIGHLIGHT (frontend debounces
# ~150ms + aborts in-flight on highlight move). Deliberately a
# SEPARATE endpoint so /query's BLOCKING latency gate is untouched.
# Own BLOCKING gate: tests/test_command_bar_portal_latency.py
# (p50 < 150 ms / p99 < 400 ms).


class PortalResponseBody(BaseModel):
    entity_type: str
    entity_id: str
    display_label: str
    navigate_url: str
    portal: dict
    pivots: list[dict] = Field(default_factory=list)
    actions: list[dict] = Field(default_factory=list)
    omitted_sections: list[str] = Field(default_factory=list)


@router.get("/portal/{entity_type}/{entity_id}", response_model=PortalResponseBody)
def get_entity_portal(
    entity_type: str,
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Hydrate one entity-portal card. Tenant-scoped; permission-gated
    sections are quietly omitted (listed in `omitted_sections`)."""
    from fastapi import HTTPException

    from app.services.command_bar.portal import build_portal
    from app.services.peek.types import EntityNotFound, UnknownEntityType

    try:
        resp = build_portal(db, current_user, entity_type, entity_id)
    except UnknownEntityType as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except EntityNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return PortalResponseBody(
        entity_type=resp.entity_type,
        entity_id=resp.entity_id,
        display_label=resp.display_label,
        navigate_url=resp.navigate_url,
        portal=resp.portal,
        pivots=resp.pivots,
        actions=resp.actions,
        omitted_sections=resp.omitted_sections,
    )


# ── S-2 — Floating contextual surfaces (§4.3) ────────────────────────
# Param-keyed (NOT entity-id-keyed) hydration for the quote-preview +
# price-list-reference surfaces summoned while the user composes a
# quote. Separate endpoints so /query's BLOCKING latency gate is
# untouched; own BLOCKING gate at tests/test_quote_preview_latency.py.


class _PreviewLineBody(BaseModel):
    product_ref: str = Field(
        ..., description="Product name (or sku) from the in-flight extraction"
    )
    product_id: str | None = Field(
        default=None, description="Already-resolved product id, if any"
    )
    quantity: float = Field(default=1, description="Line quantity")
    # S-3b — manual per-line price override (director re-prices off catalog).
    unit_price_override: float | None = Field(default=None)


class QuotePreviewRequest(BaseModel):
    customer_id: str | None = None
    customer_name: str | None = None
    lines: list[_PreviewLineBody] = Field(default_factory=list)


class _AmbiguousRefBody(BaseModel):
    product_ref: str
    candidates: list[str] = Field(default_factory=list)


class _PreviewLineOut(BaseModel):
    # S-3b structured per-line breakdown — 1:1 with input lines, in order,
    # so the editable core renders + merges editable rows.
    product_ref: str
    status: str  # resolved | call_office | ambiguous | unresolved
    quantity: float
    product_id: str | None = None
    description: str = ""
    unit_price: str | None = None  # numeric decimal string (editable input)
    unit_price_formatted: str = "—"
    line_total: str | None = None
    line_total_formatted: str = "—"
    candidates: list[str] = Field(default_factory=list)
    price_overridden: bool = False


class QuotePreviewResponseBody(BaseModel):
    html: str
    subtotal_formatted: str
    # None when tax did not resolve mid-draft — the widget renders
    # "calculated at order" rather than a fabricated total.
    total_formatted: str | None = None
    tax_resolved: bool
    has_call_office: bool
    unresolved_products: list[str] = Field(default_factory=list)
    # Refs that matched MULTIPLE catalog products — the preview refuses to
    # guess a price; the widget asks the user which one they meant.
    ambiguous_products: list[_AmbiguousRefBody] = Field(default_factory=list)
    line_count: int
    # S-3b — per-input-line structured breakdown for the editable core.
    lines: list[_PreviewLineOut] = Field(default_factory=list)


@router.post("/quote-preview", response_model=QuotePreviewResponseBody)
def quote_preview(
    body: QuotePreviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuotePreviewResponseBody:
    """Render the in-flight quote as the REAL quote document with the
    price the order will actually charge. Tenant-scoped; no persistence."""
    import time as _t_time

    from app.services import arc_telemetry as _arc_t
    from app.services.command_bar.quote_preview import (
        DraftLine,
        assemble_quote_preview,
    )

    _t0 = _t_time.perf_counter()
    _errored = False
    try:
        result = assemble_quote_preview(
            db,
            current_user.company_id,
            customer_id=body.customer_id,
            customer_name=body.customer_name,
            lines=[
                DraftLine(
                    product_ref=ln.product_ref,
                    quantity=ln.quantity,
                    product_id=ln.product_id,
                    unit_price_override=(
                        Decimal(str(ln.unit_price_override))
                        if ln.unit_price_override is not None
                        else None
                    ),
                )
                for ln in body.lines
            ],
        )
    except Exception:
        _errored = True
        raise
    finally:
        _arc_t.record(
            "quote_preview",
            (_t_time.perf_counter() - _t0) * 1000.0,
            errored=_errored,
        )

    return QuotePreviewResponseBody(
        html=result.html,
        subtotal_formatted=result.subtotal_formatted,
        total_formatted=result.total_formatted,
        tax_resolved=result.tax_resolved,
        has_call_office=result.has_call_office,
        unresolved_products=result.unresolved_products,
        ambiguous_products=[
            _AmbiguousRefBody(
                product_ref=a.product_ref, candidates=a.candidates
            )
            for a in result.ambiguous_products
        ],
        line_count=result.line_count,
        lines=[
            _PreviewLineOut(
                product_ref=ln.product_ref,
                status=ln.status,
                quantity=ln.quantity,
                product_id=ln.product_id,
                description=ln.description,
                unit_price=ln.unit_price,
                unit_price_formatted=ln.unit_price_formatted,
                line_total=ln.line_total,
                line_total_formatted=ln.line_total_formatted,
                candidates=ln.candidates,
                price_overridden=ln.price_overridden,
            )
            for ln in result.lines
        ],
    )


class PriceListReferenceRequest(BaseModel):
    products: list[str] = Field(default_factory=list)
    customer_id: str | None = None


class _PriceListRow(BaseModel):
    product_name: str
    on_list: bool
    standard_price_formatted: str
    contractor_price_formatted: str
    homeowner_price_formatted: str
    unit: str


class PriceListReferenceResponseBody(BaseModel):
    version_label: str | None = None
    rows: list[_PriceListRow] = Field(default_factory=list)


@router.post(
    "/price-list-reference", response_model=PriceListReferenceResponseBody
)
def price_list_reference(
    body: PriceListReferenceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PriceListReferenceResponseBody:
    """Return the tenant's PUBLISHED tiered price list for the quoted
    products (the reference display — tiered columns are correct here)."""
    from app.services.command_bar.price_list_reference import (
        build_price_list_reference,
    )

    data = build_price_list_reference(
        db,
        current_user.company_id,
        product_refs=body.products,
        customer_id=body.customer_id,
    )
    return PriceListReferenceResponseBody(
        version_label=data["version_label"],
        rows=[_PriceListRow(**r) for r in data["rows"]],
    )
