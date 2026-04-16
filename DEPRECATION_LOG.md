# DEPRECATION_LOG.md — Extension Library → Product Lines

**Date:** April 16, 2026
**Related build:** Bridgeable Super Admin Portal Redesign, Part 11

---

## Context

The "extension library" concept modeled per-tenant opt-in add-ons (Urn Sales, Wastewater, Redi-Rock, Rosetta Hardscapes, NPCA Audit Prep). In practice these aren't installable modules — they're **product lines** a business sells. Every tenant has at least one product line; the distinction between "core" and "extension" was artificial.

## Replacement

**New:** `tenant_product_lines` table + `ProductLineService` (`backend/app/services/product_line_service.py`) + `/product-lines` API + Settings → Product Lines page.

- `product_line_service.has_line(db, company_id, line_key)` replaces `has_extension(company_id, ext)` and `hasModule("urn_sales")`.
- Product lines have `display_name`, `is_enabled`, `sort_order`, `config` (JSONB) — more structured than extension toggles.
- Every existing company was seeded with `burial_vaults` as its default product line via the `admin_01_super_admin_tables` migration.

## Kept (non-breaking)

- Existing extension records in the DB are untouched. Old code paths continue to work.
- This deprecation **adds** the product lines layer alongside the extension system. No code has been deleted yet.
- The `urn_sales` extension check still gates all Urn Sales routes in `backend/app/api/routes/urn_*.py`. Sunnycrest's nav items remain visible.

## Removed

_Nothing yet._ Per the BUILD PROMPT instruction "Do not delete anything until you understand what it does," this commit only adds the replacement layer. Extension removal is queued for a follow-up commit after all `has_extension` / `hasModule` call sites have been migrated to `has_line`.

## Migration path for downstream code

Old pattern:
```python
from app.services.extension_service import has_extension
if has_extension(company_id, "urn_sales"):
    ...
```

New pattern:
```python
from app.services import product_line_service
if product_line_service.has_line(db, company_id, "urns"):
    ...
```

Old frontend pattern:
```tsx
const { hasModule } = useExtensions()
if (hasModule("urn_sales")) { ... }
```

New frontend pattern (after product line hook is built in a follow-up):
```tsx
const { hasLine } = useProductLines()
if (hasLine("urns")) { ... }
```

## Catalog of product lines

Defined in `AVAILABLE_PRODUCT_LINES` in `product_line_service.py`:

| Line key | Display name | Replaces extension |
|----------|--------------|--------------------|
| `burial_vaults` | Burial Vaults | (core) |
| `urns` | Urns & Memorial Products | `urn_sales` |
| `wastewater` | Wastewater / Septic | `wastewater` |
| `redi_rock` | Redi-Rock Retaining Walls | `redi_rock` |
| `rosetta_hardscapes` | Rosetta Hardscapes | `rosetta_hardscapes` |
| `funeral_services` | Funeral Services | (core for FH vertical) |
| `cemetery_services` | Cemetery Services | (core for cemetery vertical) |
| `cremation_services` | Cremation Services | (core for crematory vertical) |

## Sunnycrest protection

Verified after this change:
- Backend tests: 124/124 passing (43 existing + 80 audit + 10 new admin + 1 skipped/xfailed baseline)
- Frontend TypeScript: 0 errors
- Sunnycrest's Urn Sales nav items continue to render via existing `urn_sales` extension check
- No existing routes or pages were removed
