"""Command Bar entity resolver — Phase 1.

Single-SQL UNION ALL fuzzy search across six entity types:
fh_case, sales_order, invoice, contact, product, document.

Why UNION ALL over parallel queries: (1) single round-trip to
Postgres, (2) shared plan cache, (3) easier to enforce a unified
limit + ordering, (4) maps to the single GIN-backed trigram scan
per table. The cost is a wider result set (one row per hit across
all entities), but Postgres handles that efficiently with the
trigram indexes from r31.

Scoring formula (per row):

    score = trigram_sim * recency_weight

Where:
    trigram_sim      = similarity(col, :query)  -- 0..1, higher better
    recency_weight   = linear 1.0 (today) → 0.3 (180+ days ago)

The `similarity` function requires pg_trgm extension; r31 creates it.

Tenant isolation: every query filters by `company_id`. Callers MUST
provide `company_id`; the function raises if it's None. Permission
filtering beyond tenant is entity-specific (e.g. `customers.view`
gates contacts); the retrieval orchestrator applies these gates
server-side via the existing permission service.

Returned shape is a list[ResolverHit] — structured rows that
retrieval.py normalizes into the public `ResultItem` shape.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


# ── Configuration ────────────────────────────────────────────────────
# Similarity threshold. pg_trgm's default is 0.3 (30%) — tune here.
# Values below the threshold are dropped by the similarity() filter
# which lets the GIN index skip full-table scans.
_SIMILARITY_THRESHOLD: float = 0.2

# Recency decay range (days). See `_recency_weight_expr` below.
_RECENCY_HOT_DAYS: int = 0        # today → weight 1.0
_RECENCY_COLD_DAYS: int = 180     # 6 months → weight 0.3
_RECENCY_FLOOR: float = 0.3       # asymptote for very old rows


# ── Searchable entity catalog ────────────────────────────────────────
# Each entry is a per-entity SQL fragment that the resolver UNIONs.
# The entry owns its own column aliases + URL shape so that adding a
# new entity is a one-entry edit here (plus a migration for the
# trigram index).
#
# Fields:
#   entity_type:     Discriminator string returned to callers.
#   table:           Postgres table name.
#   search_column:   The column with the trigram index (see r31).
#   primary_label:   Column(s) to display as the primary result line.
#                    Use a COALESCE/concat expression for multi-col.
#   secondary:       Column(s) for sub-text under the primary line.
#   recency_col:     Column used for recency scoring. Must be non-null
#                    or wrapped in COALESCE. Use created_at as fallback.
#   id_col:          Primary key column name (almost always "id").
#   url_template:    Python-format template with one `{id}` placeholder.


@dataclass(frozen=True)
class _SearchableEntity:
    entity_type: str
    table: str
    search_column: str
    primary_label_expr: str
    secondary_expr: str
    recency_col_expr: str
    id_col: str = "id"
    url_template: str = "/{id}"


SEARCHABLE_ENTITIES: tuple[_SearchableEntity, ...] = (
    _SearchableEntity(
        entity_type="fh_case",
        table="fh_cases",
        search_column="deceased_last_name",
        # "SMITH, John" — concat surname + first for context.
        primary_label_expr=(
            "COALESCE(deceased_last_name, '') || ', ' || "
            "COALESCE(deceased_first_name, '')"
        ),
        # Case number as secondary label.
        secondary_expr="case_number",
        recency_col_expr="COALESCE(updated_at, NOW())",
        url_template="/cases/{id}",
    ),
    _SearchableEntity(
        entity_type="sales_order",
        table="sales_orders",
        search_column="number",
        primary_label_expr="number",
        secondary_expr="COALESCE(ship_to_name, status)",
        recency_col_expr="COALESCE(modified_at, created_at)",
        url_template="/orders/{id}",
    ),
    _SearchableEntity(
        entity_type="invoice",
        table="invoices",
        search_column="number",
        primary_label_expr="number",
        secondary_expr="status",
        recency_col_expr="COALESCE(modified_at, created_at)",
        url_template="/ar/invoices/{id}",
    ),
    _SearchableEntity(
        entity_type="contact",
        table="contacts",
        search_column="name",
        primary_label_expr="name",
        secondary_expr="COALESCE(title, email, '')",
        recency_col_expr="updated_at",
        url_template="/vault/crm/companies/{master_company_id}",
    ),
    _SearchableEntity(
        entity_type="product",
        table="products",
        search_column="name",
        primary_label_expr="name",
        secondary_expr="COALESCE(sku, '')",
        recency_col_expr="updated_at",
        url_template="/products/{id}",
    ),
    _SearchableEntity(
        entity_type="document",
        table="documents",
        search_column="title",
        primary_label_expr="title",
        secondary_expr="COALESCE(document_type, '')",
        recency_col_expr="updated_at",
        url_template="/vault/documents/{id}",
    ),
    # Phase 5 — Task added as a searchable entity. GIN trigram
    # index on tasks.title created in r34. Only active tasks surface
    # (status != cancelled, is_active=true) — matches user
    # expectation of "show me open tasks by name fragment".
    _SearchableEntity(
        entity_type="task",
        table="tasks",
        search_column="title",
        primary_label_expr="title",
        secondary_expr="COALESCE(status, '')",
        recency_col_expr="updated_at",
        url_template="/tasks/{id}",
    ),
)


# ── Data class ───────────────────────────────────────────────────────


@dataclass
class ResolverHit:
    """One row from the resolver. retrieval.py normalizes these into
    the public ResultItem."""

    entity_type: str
    entity_id: str
    primary_label: str
    secondary_context: str | None
    url: str
    score: float  # final score = similarity * recency_weight


# ── Query builder ────────────────────────────────────────────────────


def _recency_weight_expr(recency_col_expr: str) -> str:
    """Return a SQL fragment that evaluates to a 0.3..1.0 weight
    based on the `recency_col_expr` age.

    Shape (as SQL):
        GREATEST(0.3,
                 1.0 - 0.7 * (EXTRACT(EPOCH FROM NOW() - ts) / (180 * 86400)))

    Age 0 → 1.0; age 180 days → 0.3; age 1 year → 0.3 (clamped).
    """
    # 180 days in seconds = 15_552_000
    return (
        f"GREATEST({_RECENCY_FLOOR}, "
        f"1.0 - {1.0 - _RECENCY_FLOOR} * "
        f"(EXTRACT(EPOCH FROM NOW() - ({recency_col_expr})) / "
        f"(86400.0 * {_RECENCY_COLD_DAYS - _RECENCY_HOT_DAYS})))"
    )


def _build_union_query(
    entities: tuple[_SearchableEntity, ...],
    limit: int,
) -> tuple[str, dict[str, Any]]:
    """Build a single UNION ALL query across `entities`. Each branch
    applies tenant filter + similarity threshold + scoring.

    Returns (sql, params). Params include `:q` (query text) and
    `:company_id` shared across all branches, plus `:limit`.

    Per-entity rules:
      - Tenant isolation: WHERE company_id = :company_id
      - Similarity gate: WHERE (:q % search_column) -- uses GIN index
      - is_active filter where the model has one (contact, product)
    """
    branches: list[str] = []
    for ent in entities:
        # is_active gate for the entity types that have it. Do this
        # as a string-level check — simple + explicit.
        is_active_filter = ""
        if ent.entity_type in ("contact", "product"):
            is_active_filter = "AND is_active = TRUE"

        # Contact's URL has a non-id substitution (master_company_id).
        # We surface it as a separate selected column so retrieval.py
        # can plug the correct URL at normalization time. All other
        # entities get master_company_id = NULL.
        extra_id_col = (
            "master_company_id"
            if ent.entity_type == "contact"
            else "NULL::varchar AS master_company_id"
        )

        recency_weight = _recency_weight_expr(ent.recency_col_expr)

        branch = f"""
            SELECT
                '{ent.entity_type}'::varchar AS entity_type,
                {ent.id_col}::varchar AS entity_id,
                ({ent.primary_label_expr})::varchar AS primary_label,
                ({ent.secondary_expr})::varchar AS secondary_context,
                similarity({ent.search_column}, :q) AS sim,
                {recency_weight} AS recency_weight,
                {extra_id_col}
            FROM {ent.table}
            WHERE company_id = :company_id
              AND {ent.search_column} IS NOT NULL
              AND {ent.search_column} % :q
              AND similarity({ent.search_column}, :q) >= {_SIMILARITY_THRESHOLD}
              {is_active_filter}
        """
        branches.append(branch)

    union = "\nUNION ALL\n".join(branches)

    sql = f"""
        WITH hits AS (
            {union}
        )
        SELECT
            entity_type,
            entity_id,
            primary_label,
            secondary_context,
            (sim * recency_weight) AS score,
            master_company_id
        FROM hits
        ORDER BY score DESC
        LIMIT :limit
    """
    return sql, {}


# ── Public API ───────────────────────────────────────────────────────


def resolve(
    db: Session,
    *,
    query_text: str,
    company_id: str,
    limit: int = 10,
    entity_types: tuple[str, ...] | None = None,
) -> list[ResolverHit]:
    """Run the fuzzy entity resolver.

    Args:
        db:           Active DB session.
        query_text:   User's search text.
        company_id:   REQUIRED. Tenant isolation is enforced here.
        limit:        Max rows returned (post-ranking). Default 10.
        entity_types: Optional restriction to a subset of entity
                      types (e.g. ("sales_order", "invoice")). None
                      searches all.

    Returns a list of ResolverHit sorted by score desc.

    Raises ValueError if company_id is empty — defense in depth; the
    API layer must supply the caller's tenant.
    """
    if not company_id:
        raise ValueError("resolver.resolve requires a non-empty company_id")

    q = (query_text or "").strip()
    if not q:
        return []

    targets = SEARCHABLE_ENTITIES
    if entity_types is not None:
        valid = set(entity_types)
        targets = tuple(e for e in SEARCHABLE_ENTITIES if e.entity_type in valid)
        if not targets:
            return []

    sql, _ = _build_union_query(targets, limit)
    params = {"q": q, "company_id": company_id, "limit": limit}

    try:
        rows = db.execute(text(sql), params).fetchall()
    except Exception:
        # pg_trgm not installed, schema drift, etc. — log + return
        # empty rather than crash the whole command bar query.
        logger.exception(
            "resolver.resolve SQL failed (query=%r company_id=%s)",
            q[:80],
            company_id,
        )
        return []

    out: list[ResolverHit] = []
    for row in rows:
        ent_cfg = next(
            (e for e in SEARCHABLE_ENTITIES if e.entity_type == row.entity_type),
            None,
        )
        if ent_cfg is None:
            continue
        # URL substitution — "{id}" is the default, some entities use
        # a different substitution key (contact → master_company_id).
        if ent_cfg.entity_type == "contact":
            url = ent_cfg.url_template.format(
                master_company_id=row.master_company_id or row.entity_id
            )
        else:
            url = ent_cfg.url_template.format(id=row.entity_id)

        out.append(
            ResolverHit(
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                primary_label=(row.primary_label or "").strip(),
                secondary_context=(row.secondary_context or None),
                url=url,
                score=float(row.score),
            )
        )
    return out
