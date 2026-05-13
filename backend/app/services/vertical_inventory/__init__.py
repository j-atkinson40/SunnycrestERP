"""Vertical Inventory service — Studio 1a-ii.

Backs the `/studio` + `/studio/:vertical` overview page with:
  - per-section row counts (live, scope-aware), and
  - a UNION-ed "recent edits" feed across the seven editor tables
    that carry an `updated_at` column.

Recent-edits source pivoted from `audit_logs` to per-table
`updated_at` per the Studio 1a-ii STOP+surface finding (audit
substrate write-side instrumentation is not wired across the seven
editor services + admin routes — deferred to a dedicated arc).

Public API:
    get_inventory(db, vertical_slug=None) -> InventoryResponse

See docs/investigations/2026-05-13-studio-1a-internal.md for the
section list + the table mapping audit.
"""

from app.services.vertical_inventory.schemas import (  # noqa: F401
    InventoryResponse,
    RecentEditEntry,
    SectionInventoryEntry,
)
from app.services.vertical_inventory.service import (  # noqa: F401
    get_inventory,
)
