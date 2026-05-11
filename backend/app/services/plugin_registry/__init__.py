"""Plugin Registry — R-8.y.d backend introspection.

Bridges PLUGIN_CONTRACTS.md (24 documented plugin categories) to
runtime registry state where introspectable.

For each `category_key` from the snapshot, the catalog either:
- declares an introspection callable returning (registrations, registry_size), OR
- declares `None` with a `reason` string + expected count for static-only categories.

Future migrations (R-9 workflow node registry promotion, etc.) flip
a category from None → callable without other code changes.
"""

from app.services.plugin_registry.category_catalog import (  # noqa: F401
    CATEGORY_CATALOG,
    CategoryIntrospection,
    get_category_introspection,
    list_category_keys,
)
