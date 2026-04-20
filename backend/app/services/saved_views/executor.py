"""Saved View query execution — Phase 2.

Takes a SavedViewConfig + caller context, runs the query, applies
the presentation grouping/aggregation, returns a SavedViewResult.

Responsibilities (in order of application):

  1. Tenant isolation — enforced by the entity's query_builder
     (cannot be overridden; defense in depth with the filter layer).
  2. Permission filtering — only the view OWNER'S vault-item
     visibility permissions gate access to the view row itself;
     crud.get_saved_view handles that. The executor trusts the
     view came via that gate.
  3. Filter application — every operator in the FilterOperator union.
  4. Sort application — config sort overrides entity default_sort.
  5. Limit — applied AFTER sort; default caps at 1000 rows unless
     the aggregation mode (chart / stat) needs the full count.
  6. Grouping — for kanban presentation. Rows grouped by the
     configured field.
  7. Aggregation — for chart / stat modes. Runs a second SQL
     aggregation query; row list stays populated for drill-through.
  8. Cross-tenant field masking — applied AT THE END over
     `row_serializer` output dicts when caller's tenant != owner.

Performance notes:

  - Blocking CI latency gate at test_saved_view_execute_latency
    asserts p50 < 150ms, p99 < 500ms on a 1000-row seeded dataset.
  - The executor doesn't paginate — Phase 2 callers that render
    visible rows cap at limit=1000 (a practical UX ceiling). Phase 3
    will add streaming for larger views.
  - No caching. Saved-view results are live-queried every time.
    This is the user-approved behavior (item #6 of the refinements).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, asc, desc, func, or_
from sqlalchemy.orm import Session

from app.services.saved_views import registry as registry_mod
from app.services.saved_views.types import (
    Aggregation,
    EntityType,
    Filter,
    FilterOperator,
    PermissionMode,
    Presentation,
    Query,
    SavedViewConfig,
    SavedViewResult,
    Sort,
)


logger = logging.getLogger(__name__)


# ── Config ───────────────────────────────────────────────────────────


# Default row cap when the config doesn't set `limit`. Protects
# the API from runaway queries on unbounded views. Individual views
# can go higher by setting config.query.limit; the API enforces
# `max(config_limit, HARD_CEILING)`.
DEFAULT_LIMIT: int = 500
HARD_CEILING: int = 5000


class ExecutorError(Exception):
    """Raised on malformed config or unsupported operation.

    API layer translates to HTTP 400. Programmer errors (bad
    operator for field type, unknown field) surface here rather
    than in SQL, so errors are legible.
    """


# ── Public entry point ───────────────────────────────────────────────


def execute(
    db: Session,
    *,
    config: SavedViewConfig,
    caller_company_id: str,
    owner_company_id: str,
) -> SavedViewResult:
    """Execute a saved view.

    Args:
        db: active DB session.
        config: the view config (typed — NOT a raw dict).
        caller_company_id: tenant of the user making the request.
        owner_company_id: tenant that owns the saved view.

    If caller_company_id != owner_company_id, cross-tenant masking
    kicks in. Fields not in the view's
    `permissions.cross_tenant_field_visibility.per_tenant_fields[caller]`
    whitelist are replaced with MASK_SENTINEL in the result.
    permission_mode flips to "cross_tenant_masked".

    Returns a SavedViewResult envelope.

    Raises ExecutorError on malformed config.
    """
    # Entity lookup — registry does the work.
    entity_meta = registry_mod.get_entity(config.query.entity_type)
    if entity_meta is None:
        raise ExecutorError(
            f"Unknown entity_type {config.query.entity_type!r} — "
            f"register it via saved_views.registry.register_entity()"
        )

    # 1. Base query. Query builder already scopes to owner tenant.
    # The caller's tenant may be different — masking at serialize
    # time handles that, NOT the query builder.
    base_query = entity_meta.query_builder(db, owner_company_id)

    # 2. Filters
    base_query = _apply_filters(base_query, config.query.filters, entity_meta)

    # 3. Sort
    sort_list = config.query.sort or [
        Sort(field=s["field"], direction=s.get("direction", "asc"))
        for s in entity_meta.default_sort
    ]
    base_query = _apply_sort(base_query, sort_list, entity_meta)

    # 4. Limit
    limit = config.query.limit if config.query.limit is not None else DEFAULT_LIMIT
    limit = min(max(limit, 1), HARD_CEILING)

    # 5. Total count — cheap count before limit for UI metadata
    total_count = base_query.count()

    # 6. Fetch rows up to limit
    rows_orm = base_query.limit(limit).all()

    # 7. Serialize to dicts
    rows = [entity_meta.row_serializer(r) for r in rows_orm]

    # 8. Cross-tenant masking
    permission_mode: PermissionMode = "full"
    masked_fields: list[str] = []
    if caller_company_id != owner_company_id:
        permission_mode = "cross_tenant_masked"
        allowed_fields = set(
            config.permissions.cross_tenant_field_visibility
            .per_tenant_fields
            .get(caller_company_id, [])
        )
        if not allowed_fields:
            # No whitelist for this tenant → everything masked.
            # Caller shouldn't have access at all; let executor mask
            # (defense in depth) — the crud layer SHOULD have
            # blocked this. Mask everything except id + a placeholder.
            allowed_fields = {"id"}
        if rows:
            first_row_keys = set(rows[0].keys())
            masked_fields = sorted(first_row_keys - allowed_fields)
            rows = [
                _mask_row(r, allowed_fields=allowed_fields)
                for r in rows
            ]

    # 9. Grouping (for kanban)
    groups: dict[str, list[dict]] | None = None
    if config.query.grouping is not None:
        groups = _group_rows(rows, group_field=config.query.grouping.field)

    # 10. Aggregation (for chart / stat modes)
    aggregations: dict | None = None
    if config.presentation.mode == "chart":
        aggregations = _aggregate_for_chart(
            db, config, entity_meta, owner_company_id
        )
    elif config.presentation.mode == "stat":
        aggregations = _aggregate_for_stat(
            db, config, entity_meta, owner_company_id
        )

    return SavedViewResult(
        total_count=total_count,
        rows=rows,
        groups=groups,
        aggregations=aggregations,
        permission_mode=permission_mode,
        masked_fields=masked_fields,
    )


# ── Filter application ───────────────────────────────────────────────


def _apply_filters(q, filters: list[Filter], entity_meta):
    """Each filter becomes a WHERE clause. Unknown or non-filterable
    fields raise ExecutorError — don't silently drop filters."""
    if not filters:
        return q

    model = _model_from_query(q)

    clauses = []
    for f in filters:
        field_meta = entity_meta.field_by_name(f.field)
        if field_meta is None:
            raise ExecutorError(f"Unknown field: {f.field}")
        if not field_meta.filterable:
            raise ExecutorError(f"Field not filterable: {f.field}")
        col = getattr(model, f.field, None)
        if col is None:
            # Field declared in metadata but not present on model —
            # likely a bug in registry wiring.
            raise ExecutorError(
                f"Field {f.field!r} declared in registry but missing on "
                f"{model.__name__ if model is not None else 'model'}"
            )
        clauses.append(_filter_to_clause(col, f, field_meta))
    return q.filter(and_(*clauses))


def _filter_to_clause(col, f: Filter, field_meta):
    """Translate one Filter to a SQLAlchemy expression."""
    op: FilterOperator = f.operator
    v = f.value

    # is_null / is_not_null — value is ignored by design.
    if op == "is_null":
        return col.is_(None)
    if op == "is_not_null":
        return col.is_not(None)

    # Collection operators
    if op == "in":
        _require_list(v, op, f.field)
        return col.in_(v)
    if op == "not_in":
        _require_list(v, op, f.field)
        return col.notin_(v)

    # Between
    if op == "between":
        _require_list(v, op, f.field, length=2)
        return col.between(v[0], v[1])

    # contains — substring for text (case-insensitive), ILIKE
    if op == "contains":
        if field_meta.field_type != "text":
            raise ExecutorError(
                f"'contains' requires text field; got {field_meta.field_type}"
            )
        return col.ilike(f"%{v}%")

    # Scalar comparisons — eq / ne / gt / lt / gte / lte
    scalar_ops = {
        "eq": col.__eq__,
        "ne": col.__ne__,
        "gt": col.__gt__,
        "lt": col.__lt__,
        "gte": col.__ge__,
        "lte": col.__le__,
    }
    if op in scalar_ops:
        return scalar_ops[op](v)

    raise ExecutorError(f"Unsupported operator: {op}")


def _require_list(v, op, field, length: int | None = None) -> None:
    if not isinstance(v, (list, tuple)):
        raise ExecutorError(f"Operator {op!r} on field {field!r} requires a list value")
    if length is not None and len(v) != length:
        raise ExecutorError(
            f"Operator {op!r} on field {field!r} requires list of length {length}"
        )


# ── Sort application ─────────────────────────────────────────────────


def _apply_sort(q, sorts: list[Sort], entity_meta):
    if not sorts:
        return q
    model = _model_from_query(q)
    order_by = []
    for s in sorts:
        fm = entity_meta.field_by_name(s.field)
        if fm is None:
            raise ExecutorError(f"Unknown sort field: {s.field}")
        if not fm.sortable:
            raise ExecutorError(f"Field not sortable: {s.field}")
        col = getattr(model, s.field, None)
        if col is None:
            raise ExecutorError(f"Sort field {s.field!r} missing on model")
        order_by.append(desc(col) if s.direction == "desc" else asc(col))
    return q.order_by(*order_by)


# ── Grouping (kanban) ────────────────────────────────────────────────


def _group_rows(rows: list[dict], *, group_field: str) -> dict[str, list[dict]]:
    """Bucket serialized rows by a field value.

    Missing values bucket as empty-string "" rather than None so
    JSON keys stay strings. Frontend renders unknown/unset as
    "(unset)" per the Kanban renderer.
    """
    out: dict[str, list[dict]] = {}
    for row in rows:
        key = row.get(group_field)
        key_s = "" if key is None else str(key)
        out.setdefault(key_s, []).append(row)
    return out


# ── Aggregation (chart / stat) ───────────────────────────────────────


def _aggregate_for_chart(
    db, config: SavedViewConfig, entity_meta, owner_company_id: str
) -> dict:
    """Run a GROUP BY query for chart mode.

    Example — chart_config = { chart_type: bar, x_field: status,
    aggregation: count }:
        SELECT status AS x, COUNT(*) AS y
        FROM invoices
        WHERE company_id = :co
        GROUP BY status
    """
    if config.presentation.chart_config is None:
        raise ExecutorError("chart mode requires chart_config")
    cfg = config.presentation.chart_config

    model = _model_from_query(
        entity_meta.query_builder(db, owner_company_id)
    )
    x_col = getattr(model, cfg.x_field, None)
    if x_col is None:
        raise ExecutorError(f"Unknown x_field {cfg.x_field!r}")

    agg_expr = _aggregation_expr(cfg.aggregation, model, cfg.y_field)

    base = entity_meta.query_builder(db, owner_company_id)
    base = _apply_filters(base, config.query.filters, entity_meta)

    rows = (
        base.with_entities(x_col.label("x"), agg_expr.label("y"))
        .group_by(x_col)
        .order_by(x_col)
        .all()
    )
    buckets = [
        {"x": r.x, "y": float(r.y) if r.y is not None else 0}
        for r in rows
    ]
    return {"buckets": buckets}


def _aggregate_for_stat(
    db, config: SavedViewConfig, entity_meta, owner_company_id: str
) -> dict:
    """Single aggregated value. Optional comparison to prior period."""
    if config.presentation.stat_config is None:
        raise ExecutorError("stat mode requires stat_config")
    cfg = config.presentation.stat_config

    model = _model_from_query(
        entity_meta.query_builder(db, owner_company_id)
    )
    agg_expr = _aggregation_expr(cfg.aggregation, model, cfg.metric_field)

    base = entity_meta.query_builder(db, owner_company_id)
    base = _apply_filters(base, config.query.filters, entity_meta)
    value_row = base.with_entities(agg_expr.label("v")).first()
    value = float(value_row.v) if value_row and value_row.v is not None else 0

    out: dict[str, Any] = {"value": value}

    # Comparison left as a placeholder for Phase 2 — full prev-period
    # math requires a date field hint we don't enforce in the config
    # yet. Stat comparison ships as a number + delta in Phase 6
    # briefings. For now, return value only.
    if cfg.comparison:
        out["comparison"] = cfg.comparison
        out["comparison_value"] = None
        out["comparison_delta"] = None

    return out


def _aggregation_expr(agg: Aggregation, model, field_name: str | None):
    """Build the SQLAlchemy aggregation expression."""
    if agg == "count":
        return func.count()
    if field_name is None:
        raise ExecutorError(f"{agg!r} requires a metric_field / y_field")
    col = getattr(model, field_name, None)
    if col is None:
        raise ExecutorError(f"Unknown field {field_name!r} for aggregation")
    if agg == "sum":
        return func.sum(col)
    if agg == "avg":
        return func.avg(col)
    if agg == "min":
        return func.min(col)
    if agg == "max":
        return func.max(col)
    raise ExecutorError(f"Unsupported aggregation: {agg}")


# ── Cross-tenant masking ─────────────────────────────────────────────


MASK_SENTINEL: str = "__MASKED__"


def _mask_row(row: dict, *, allowed_fields: set[str]) -> dict:
    """Return a copy of `row` with fields NOT in `allowed_fields`
    replaced by MASK_SENTINEL.

    The sentinel is a well-known constant rather than None so
    downstream code (and the test suite) can distinguish "field
    masked for this viewer" from "field legitimately null".
    """
    masked = {}
    for k, v in row.items():
        masked[k] = v if k in allowed_fields else MASK_SENTINEL
    return masked


# ── Helpers ──────────────────────────────────────────────────────────


def _model_from_query(q) -> type:
    """Extract the primary mapped class from a SQLAlchemy Query."""
    descriptions = q.column_descriptions
    if not descriptions:
        raise ExecutorError("Could not resolve model from query")
    model = descriptions[0].get("entity") or descriptions[0].get("type")
    if model is None:
        raise ExecutorError("Query missing entity description")
    return model
