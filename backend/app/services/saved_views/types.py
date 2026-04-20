"""Saved Views type system — Phase 2.

OWNS the SavedView config schema. This is the canonical Python
representation of what lives at `vault_items.metadata_json.saved_view_config`.
Frontend TypeScript types in `frontend/src/components/saved-views/types.ts`
mirror these; bumping either side is a coordinated change.

Design principles:

  - Pure data classes. No ORM, no DB access, no business logic.
    crud.py + executor.py depend on these; the dependency does NOT
    go the other way.
  - Every field has a type. Optional fields default to None or
    empty collections so `from_dict` never KeyErrors on partial
    configs.
  - `to_dict` / `from_dict` are explicit. Don't use dataclasses.asdict
    — we want stable field order for DB storage + deterministic
    JSON serialization for equality checks.
  - Visibility enum is explicit per the approved 4-level model:
    private, role_shared, user_shared, tenant_public.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# ── Enums / Literals ─────────────────────────────────────────────────


EntityType = Literal[
    "fh_case",
    "sales_order",
    "invoice",
    "contact",
    "product",
    "document",
    "vault_item",
]

FilterOperator = Literal[
    "eq",           # equals
    "ne",           # not equals
    "contains",     # case-insensitive substring (text fields)
    "in",           # value is in list (enum fields)
    "not_in",       # value is NOT in list
    "gt",           # >
    "lt",           # <
    "gte",          # >=
    "lte",          # <=
    "between",      # between [lo, hi] — value must be 2-tuple
    "is_null",      # column IS NULL — value ignored
    "is_not_null",  # column IS NOT NULL — value ignored
]

SortDirection = Literal["asc", "desc"]

PresentationMode = Literal[
    "list",
    "table",
    "kanban",
    "calendar",
    "cards",
    "chart",
    "stat",
]

ChartType = Literal["bar", "line", "pie", "area"]

Aggregation = Literal["count", "sum", "avg", "min", "max"]

StatComparison = Literal["prev_period", "prev_year"]

# 4-level visibility per the approved architecture.
#   private       — owner only
#   role_shared   — owner + shared_with_roles (list of role slugs)
#   user_shared   — owner + shared_with_users (list of user IDs)
#   tenant_public — every user in the tenant who has the entity-type permission
Visibility = Literal[
    "private",
    "role_shared",
    "user_shared",
    "tenant_public",
]


# ── Query config ─────────────────────────────────────────────────────


@dataclass
class Filter:
    """One filter row in the view's WHERE clause equivalent."""

    field: str
    operator: FilterOperator
    # Value type depends on operator — a list for in/not_in/between;
    # scalar for eq/ne/gt/etc.; ignored for is_null/is_not_null. We
    # accept Any and validate in executor.py.
    value: Any = None

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "operator": self.operator,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Filter":
        return cls(
            field=d["field"],
            operator=d["operator"],
            value=d.get("value"),
        )


@dataclass
class Sort:
    field: str
    direction: SortDirection = "asc"

    def to_dict(self) -> dict:
        return {"field": self.field, "direction": self.direction}

    @classmethod
    def from_dict(cls, d: dict) -> "Sort":
        return cls(field=d["field"], direction=d.get("direction", "asc"))


@dataclass
class Grouping:
    field: str

    def to_dict(self) -> dict:
        return {"field": self.field}

    @classmethod
    def from_dict(cls, d: dict) -> "Grouping":
        return cls(field=d["field"])


@dataclass
class Query:
    """The query half of a saved view.

    `entity_type` is required — everything else has sensible defaults
    so a minimal config just picks an entity type and renders all
    visible rows.
    """

    entity_type: EntityType
    filters: list[Filter] = field(default_factory=list)
    sort: list[Sort] = field(default_factory=list)
    grouping: Grouping | None = None
    limit: int | None = None

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "filters": [f.to_dict() for f in self.filters],
            "sort": [s.to_dict() for s in self.sort],
            "grouping": self.grouping.to_dict() if self.grouping else None,
            "limit": self.limit,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Query":
        return cls(
            entity_type=d["entity_type"],
            filters=[Filter.from_dict(x) for x in d.get("filters", [])],
            sort=[Sort.from_dict(x) for x in d.get("sort", [])],
            grouping=Grouping.from_dict(d["grouping"]) if d.get("grouping") else None,
            limit=d.get("limit"),
        )


# ── Presentation config ──────────────────────────────────────────────


@dataclass
class TableConfig:
    """Column visibility for table mode. An empty `columns` means
    "render the entity's default column set" (executor resolves from
    the entity registry)."""

    columns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"columns": list(self.columns)}

    @classmethod
    def from_dict(cls, d: dict) -> "TableConfig":
        return cls(columns=list(d.get("columns", [])))


@dataclass
class CardConfig:
    title_field: str | None = None
    subtitle_field: str | None = None
    meta_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title_field": self.title_field,
            "subtitle_field": self.subtitle_field,
            "meta_fields": list(self.meta_fields),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CardConfig":
        return cls(
            title_field=d.get("title_field"),
            subtitle_field=d.get("subtitle_field"),
            meta_fields=list(d.get("meta_fields", [])),
        )


@dataclass
class KanbanConfig:
    # Field to group-by (becomes Kanban columns). Must be present in
    # both this config AND the Query.grouping — they should agree;
    # executor enforces grouping=KanbanConfig.group_by_field.
    group_by_field: str
    card_title_field: str | None = None
    card_meta_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "group_by_field": self.group_by_field,
            "card_title_field": self.card_title_field,
            "card_meta_fields": list(self.card_meta_fields),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "KanbanConfig":
        return cls(
            group_by_field=d["group_by_field"],
            card_title_field=d.get("card_title_field"),
            card_meta_fields=list(d.get("card_meta_fields", [])),
        )


@dataclass
class CalendarConfig:
    date_field: str               # required
    end_date_field: str | None = None   # for ranged events
    label_field: str | None = None
    color_field: str | None = None

    def to_dict(self) -> dict:
        return {
            "date_field": self.date_field,
            "end_date_field": self.end_date_field,
            "label_field": self.label_field,
            "color_field": self.color_field,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CalendarConfig":
        return cls(
            date_field=d["date_field"],
            end_date_field=d.get("end_date_field"),
            label_field=d.get("label_field"),
            color_field=d.get("color_field"),
        )


@dataclass
class ChartConfig:
    chart_type: ChartType
    x_field: str
    y_field: str | None = None   # None when aggregation == "count"
    aggregation: Aggregation = "count"

    def to_dict(self) -> dict:
        return {
            "chart_type": self.chart_type,
            "x_field": self.x_field,
            "y_field": self.y_field,
            "aggregation": self.aggregation,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ChartConfig":
        return cls(
            chart_type=d["chart_type"],
            x_field=d["x_field"],
            y_field=d.get("y_field"),
            aggregation=d.get("aggregation", "count"),
        )


@dataclass
class StatConfig:
    metric_field: str | None = None   # None when aggregation == "count"
    aggregation: Aggregation = "count"
    comparison: StatComparison | None = None

    def to_dict(self) -> dict:
        return {
            "metric_field": self.metric_field,
            "aggregation": self.aggregation,
            "comparison": self.comparison,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StatConfig":
        return cls(
            metric_field=d.get("metric_field"),
            aggregation=d.get("aggregation", "count"),
            comparison=d.get("comparison"),
        )


@dataclass
class Presentation:
    """The 'how to render' half of a saved view."""

    mode: PresentationMode
    # Only one of these should be non-null per mode. A view stored
    # with multiple populated is valid — the executor uses only the
    # one matching `mode`.
    table_config: TableConfig | None = None
    card_config: CardConfig | None = None
    kanban_config: KanbanConfig | None = None
    calendar_config: CalendarConfig | None = None
    chart_config: ChartConfig | None = None
    stat_config: StatConfig | None = None

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "table_config": self.table_config.to_dict() if self.table_config else None,
            "card_config": self.card_config.to_dict() if self.card_config else None,
            "kanban_config": self.kanban_config.to_dict() if self.kanban_config else None,
            "calendar_config": self.calendar_config.to_dict() if self.calendar_config else None,
            "chart_config": self.chart_config.to_dict() if self.chart_config else None,
            "stat_config": self.stat_config.to_dict() if self.stat_config else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Presentation":
        return cls(
            mode=d["mode"],
            table_config=TableConfig.from_dict(d["table_config"]) if d.get("table_config") else None,
            card_config=CardConfig.from_dict(d["card_config"]) if d.get("card_config") else None,
            kanban_config=KanbanConfig.from_dict(d["kanban_config"]) if d.get("kanban_config") else None,
            calendar_config=CalendarConfig.from_dict(d["calendar_config"]) if d.get("calendar_config") else None,
            chart_config=ChartConfig.from_dict(d["chart_config"]) if d.get("chart_config") else None,
            stat_config=StatConfig.from_dict(d["stat_config"]) if d.get("stat_config") else None,
        )


# ── Permissions config ───────────────────────────────────────────────


@dataclass
class CrossTenantFieldVisibility:
    """Per-tenant field whitelist for cross-tenant view execution.

    Keyed by recipient tenant_id → list of field names visible to
    that tenant. Fields NOT in the list are MASKED in results when
    executor detects the caller's tenant ≠ the view owner's tenant.

    Phase 2 builds the logic but UI is unexposed. Tests validate
    masking end-to-end.
    """

    per_tenant_fields: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"per_tenant_fields": dict(self.per_tenant_fields)}

    @classmethod
    def from_dict(cls, d: dict) -> "CrossTenantFieldVisibility":
        raw = d.get("per_tenant_fields", {}) or {}
        return cls(per_tenant_fields={k: list(v) for k, v in raw.items()})


@dataclass
class Permissions:
    """4-level visibility + cross-tenant (unexposed UI).

    Semantics:
      - visibility='private'        → only owner_user_id can see/execute
      - visibility='role_shared'    → owner + any user with a role in shared_with_roles
      - visibility='user_shared'    → owner + any user in shared_with_users
      - visibility='tenant_public'  → every user in owner's tenant who
                                      has the entity's view permission

    Cross-tenant fields are built but UI unreachable in Phase 2.
    """

    owner_user_id: str
    visibility: Visibility = "private"
    shared_with_users: list[str] = field(default_factory=list)
    shared_with_roles: list[str] = field(default_factory=list)
    # Cross-tenant — built, not exposed in Phase 2
    shared_with_tenants: list[str] = field(default_factory=list)
    cross_tenant_field_visibility: CrossTenantFieldVisibility = field(
        default_factory=CrossTenantFieldVisibility
    )

    def to_dict(self) -> dict:
        return {
            "owner_user_id": self.owner_user_id,
            "visibility": self.visibility,
            "shared_with_users": list(self.shared_with_users),
            "shared_with_roles": list(self.shared_with_roles),
            "shared_with_tenants": list(self.shared_with_tenants),
            "cross_tenant_field_visibility": self.cross_tenant_field_visibility.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Permissions":
        return cls(
            owner_user_id=d["owner_user_id"],
            visibility=d.get("visibility", "private"),
            shared_with_users=list(d.get("shared_with_users", [])),
            shared_with_roles=list(d.get("shared_with_roles", [])),
            shared_with_tenants=list(d.get("shared_with_tenants", [])),
            cross_tenant_field_visibility=CrossTenantFieldVisibility.from_dict(
                d.get("cross_tenant_field_visibility", {}) or {}
            ),
        )


# ── Top-level config ─────────────────────────────────────────────────


@dataclass
class SavedViewConfig:
    """The full saved-view config. Stored at
    `vault_items.metadata_json.saved_view_config`.

    `crud.py` is the only module that round-trips this to/from the
    DB. Elsewhere, code takes a `SavedViewConfig` and trusts it.
    """

    query: Query
    presentation: Presentation
    permissions: Permissions
    # Free-form dict for mode-specific or future expansion. Not part
    # of the query/presentation/permissions core but still persisted.
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "query": self.query.to_dict(),
            "presentation": self.presentation.to_dict(),
            "permissions": self.permissions.to_dict(),
            "extras": dict(self.extras),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SavedViewConfig":
        return cls(
            query=Query.from_dict(d["query"]),
            presentation=Presentation.from_dict(d["presentation"]),
            permissions=Permissions.from_dict(d["permissions"]),
            extras=dict(d.get("extras", {})),
        )


@dataclass
class SavedView:
    """Canonical Python representation of a saved view after loading
    from the DB. crud.py returns these — callers don't see VaultItem
    directly.

    Round-trip shape:
      VaultItem (DB)  →  crud.get_saved_view()  →  SavedView
      SavedView       →  crud.update_saved_view()  →  VaultItem (DB)
    """

    # VaultItem identity
    id: str
    company_id: str
    title: str
    description: str | None
    created_by: str | None
    created_at: Any  # datetime — avoid importing it here for module purity
    updated_at: Any  # datetime

    # Config
    config: SavedViewConfig

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "title": self.title,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if hasattr(self.created_at, "isoformat") else self.created_at,
            "updated_at": self.updated_at.isoformat() if hasattr(self.updated_at, "isoformat") else self.updated_at,
            "config": self.config.to_dict(),
        }


# ── Result envelope ──────────────────────────────────────────────────


PermissionMode = Literal["full", "cross_tenant_masked"]


@dataclass
class SavedViewResult:
    """What executor.execute() returns. Normalized across all 7
    presentation modes — UI branches on the mode from the source
    SavedViewConfig."""

    total_count: int
    # For list/table/cards/calendar: a flat list of row dicts.
    # For kanban: dict keyed by the group value → list of row dicts
    #   (when rendered via executor, the `rows` field is still set
    #    with all rows; the `groups` dict is an additional convenience).
    # For chart: aggregated buckets (see aggregations).
    # For stat: a single-row aggregation.
    rows: list[dict]
    groups: dict[str, list[dict]] | None = None
    # chart / stat aggregation results. Example for bar chart:
    #   {"buckets": [{"x": "draft", "y": 12}, {"x": "sent", "y": 34}]}
    # Example for stat with comparison:
    #   {"value": 42, "comparison_value": 35, "comparison_delta": 7}
    aggregations: dict | None = None
    # Set when executor masked fields because the caller's tenant
    # differs from the view owner's tenant. Renderer uses this to
    # show "locked" placeholders for missing fields.
    permission_mode: PermissionMode = "full"
    # Fields that were masked (empty when permission_mode == "full").
    masked_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_count": self.total_count,
            "rows": self.rows,
            "groups": self.groups,
            "aggregations": self.aggregations,
            "permission_mode": self.permission_mode,
            "masked_fields": list(self.masked_fields),
        }
