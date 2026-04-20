"""Bridgeable Saved Views — Phase 2 of UI/UX Arc.

Package layout:

    types.py     — OWNS the SavedView config schema. Pure dataclasses,
                   zero DB / ORM dependencies. All other modules in
                   this package depend on types; types depends on
                   nothing.
    registry.py  — Entity type registry. 7 entity types registered
                   at seed: fh_case, sales_order, invoice, contact,
                   product, document, vault_item. Mirror pattern of
                   vault.hub_registry + command_bar.registry.
    executor.py  — Query execution engine. Filters + sort + group
                   + aggregate + cross-tenant field masking. Returns
                   a SavedViewResult.
    crud.py      — Saved view lifecycle. create/get/list/update/
                   delete/duplicate. Round-trips between VaultItem
                   rows and SavedView dataclasses. The ONLY module
                   that touches `metadata_json.saved_view_config`.
    seed.py      — Role-based default seeding. Idempotent via
                   users.preferences.saved_views_seeded_for_roles.

See CLAUDE.md §3 "Saved Views — Universal Platform Primitive" for
the architecture doc.
"""

from app.services.saved_views.types import (
    Aggregation,
    CalendarConfig,
    CardConfig,
    ChartConfig,
    ChartType,
    CrossTenantFieldVisibility,
    EntityType,
    Filter,
    FilterOperator,
    Grouping,
    KanbanConfig,
    PermissionMode,
    Permissions,
    Presentation,
    PresentationMode,
    Query,
    SavedView,
    SavedViewConfig,
    SavedViewResult,
    Sort,
    SortDirection,
    StatComparison,
    StatConfig,
    TableConfig,
    Visibility,
)
from app.services.saved_views.registry import (
    EntityTypeMetadata,
    FieldMetadata,
    FieldType,
    get_entity,
    list_entities,
    register_entity,
    reset_registry,
)
from app.services.saved_views.executor import (
    MASK_SENTINEL,
    ExecutorError,
    execute,
)
from app.services.saved_views.crud import (
    SavedViewError,
    SavedViewNotFound,
    SavedViewPermissionDenied,
    create_saved_view,
    delete_saved_view,
    duplicate_saved_view,
    get_saved_view,
    list_saved_views_for_user,
    update_saved_view,
)
from app.services.saved_views.seed import (
    SEED_TEMPLATES,
    SeedTemplate,
    seed_for_user,
)

__all__ = [
    # types
    "Aggregation",
    "CalendarConfig",
    "CardConfig",
    "ChartConfig",
    "ChartType",
    "CrossTenantFieldVisibility",
    "EntityType",
    "Filter",
    "FilterOperator",
    "Grouping",
    "KanbanConfig",
    "PermissionMode",
    "Permissions",
    "Presentation",
    "PresentationMode",
    "Query",
    "SavedView",
    "SavedViewConfig",
    "SavedViewResult",
    "Sort",
    "SortDirection",
    "StatComparison",
    "StatConfig",
    "TableConfig",
    "Visibility",
    # registry
    "EntityTypeMetadata",
    "FieldMetadata",
    "FieldType",
    "get_entity",
    "list_entities",
    "register_entity",
    "reset_registry",
    # executor
    "MASK_SENTINEL",
    "ExecutorError",
    "execute",
    # crud
    "SavedViewError",
    "SavedViewNotFound",
    "SavedViewPermissionDenied",
    "create_saved_view",
    "delete_saved_view",
    "duplicate_saved_view",
    "get_saved_view",
    "list_saved_views_for_user",
    "update_saved_view",
    # seed
    "SEED_TEMPLATES",
    "SeedTemplate",
    "seed_for_user",
]
