# Edge-panel substrate as separate primitive — Investigation (Sub-arc B-1.5)

Date: 2026-05-14
Author: investigation by Sonnet (Focus Template Inheritance arc, post-B-1 / pre-B-2 halt)
Status: investigation only; no code, no migrations, no canon edits
Closes question: how should edge-panel substrate be rehoused once sub-arc A dropped the legacy single-table `focus_compositions`, given that B-2 halted on the gap?

The locked decisions from the build-report halt stand and are not relitigated:
1. **Separate primitive.** Two new tables: `edge_panel_templates` (Tier 2) + `edge_panel_compositions` (Tier 3 lazy fork). NOT extension of `focus_templates`.
2. **Two tiers, not three.** No Tier-1 core — edge-panels are pure composition; no code-rendered core analogous to `SchedulingKanbanCore`.
3. **User-level overrides preserved as fourth layer.** R-5.0's `User.preferences.edge_panel_overrides[panel_key]` stays untouched. Resolver composes Tier 2 → Tier 3 → User overrides.
4. **Single build dispatch.** B-1.5 ships schema + services + resolver + admin API + seed + tests in one arc.
5. **B-2 re-dispatches after B-1.5.**

---

## Section 1 — R-5.0 edge-panel substrate survey

### Old table shape (pre-sub-arc-A drop)

R-5.0 layered edge-panel storage onto the legacy single-table `focus_compositions` via migration **`r91_compositions_kind_and_pages`** (`backend/alembic/versions/r91_compositions_kind_and_pages.py:83-124`). Two columns added:

- `kind` `VARCHAR(32) NOT NULL DEFAULT 'focus'` with CHECK `kind IN ('focus','edge_panel')`. Discriminator between the two coexisting composition shapes.
- `pages` `JSONB NULL` — populated when `kind='edge_panel'`; null when `kind='focus'`.

The migration replaced the partial unique index `uq_focus_compositions_active` with `uq_focus_compositions_active_v2` on `(scope, vertical, tenant_id, focus_type, kind) WHERE is_active=true` — so a tenant could carry an active `focus:scheduling` AND an active `edge_panel:default` simultaneously without conflict (`r91_compositions_kind_and_pages.py:118-124`).

The `focus_type` column did double duty: for `kind='edge_panel'` rows it carried the **panel slug** (e.g. `"default"`, `"dispatch"`), not a Focus type. The migration docstring explicitly accepts this ("The column-name reads slightly off for kind=edge_panel; documented in the model docstring + accepted as lighter churn than a full rename" — `r91_compositions_kind_and_pages.py:23-25`).

**Columns used by edge-panels**: `id`, `scope`, `vertical`, `tenant_id`, `focus_type` (as panel_key), `kind` (=edge_panel), `pages` (the multi-page JSONB), `canvas_config` (cosmetic; per-composition top-level config), `version`, `is_active`, audit cols.

**Columns ignored by edge-panels**: `rows` (always `[]` for `kind='edge_panel'`).

When sub-arc A landed `r96_focus_template_inheritance`, it dropped `focus_compositions` and recreated it greenfield against the Tier 3 inheritance shape with no `kind`, no `pages`, no `focus_type`. Edge-panels were homeless.

### Page shape inside `pages` JSONB

Each page record carries (verified via `composition_service._validate_pages` at `composition_service.py:346-406` + `seed_edge_panel._quick_actions_page` at `backend/scripts/seed_edge_panel.py:99-115`):

```
{
  "page_id":      str,         // non-empty, unique within pages array
  "name":         str,         // human-readable label
  "rows":         list[Row],   // same Row shape as kind=focus rows
  "canvas_config": dict        // optional, defaults {}
}
```

Where each Row is the same R-3.0 rows-shape used by Focus compositions:

```
{
  "row_id":       str (UUID),
  "column_count": int (1-12),
  "row_height":   str | int,
  "column_widths": list[int] | None,
  "nested_rows":  None,                  // forward-compat
  "placements":   list[Placement]
}
```

And each Placement:

```
{
  "placement_id":  str,
  "component_kind": str,                 // "button" | "edge-panel-label" | etc.
  "component_name": str,
  "starting_column": int (0..11),
  "column_span":     int (1..12),
  "prop_overrides":  dict,
  "display_config":  dict,
  "nested_rows":     None
}
```

The R-5.0 seed (`seed_edge_panel.py`) populates the platform default with two pages — `quick-actions` (3 rows: label, navigate button, open-focus button) and `dispatch` (2 rows: label, trigger-workflow button). Recursively, edge-panel rows + placements look structurally identical to Focus rows + placements; only the wrapping `pages` array distinguishes the two shapes.

### Override vocabulary at User-preference layer

R-5.0 + R-5.1 expanded `User.preferences.edge_panel_overrides[panel_key]` into a recursive page-keyed delta blob. Vocabulary inventoried from `composition_service.resolve_edge_panel` (`composition_service.py:879-1010`):

**Top-level keys (R-5.1):**
- `page_overrides: { <page_id>: PageOverride, ... }` — per-page overrides
- `additional_pages: list[Page]` — user's personal pages appended after tenant pages; collisions with tenant page_id silently drop the personal page
- `hidden_page_ids: list[str]` — pages dropped from final list
- `page_order_override: list[page_id]` — reorder final page list

**Per-page `PageOverride` shape:**
- `rows`: full-replace escape hatch (R-5.0 — if set, per-placement fields ignored for this page)
- `hidden_placement_ids: list[str]` — drop matching placements within page; orphan IDs silently logged
- `additional_placements: list[Placement]` — each carries optional `row_index` (clamped to last row; if rows empty, synthesize new row)
- `placement_order: list[str]` — reorder placements within each row; orphan IDs dropped
- `canvas_config`: full-replace if present

`_apply_placement_overrides` (`composition_service.py:789-876`) is the helper that walks hide → add → reorder for a single page's rows.

This recursive shape (page-level deltas → per-page placement-level deltas) is **already in production** and battle-tested via `test_edge_panel_user_override.py` (923 LOC).

### `User.preferences.edge_panel_overrides[panel_key]` location + shape

Location: `User.preferences` JSONB column, key `edge_panel_overrides`, dict keyed by `panel_key`. Read at `edge_panel.py::_user_overrides_for` (`backend/app/api/routes/edge_panel.py:81-89`).

Example shape for a single panel_key entry:

```json
{
  "page_overrides": {
    "quick-actions": {
      "hidden_placement_ids": ["btn-pulse"],
      "additional_placements": [
        { "placement_id": "btn-custom",
          "component_kind": "button",
          "component_name": "open-my-saved-view",
          "starting_column": 0,
          "column_span": 12,
          "row_index": 0,
          "prop_overrides": {}, "display_config": {} }
      ],
      "placement_order": ["btn-custom", "btn-scheduling"]
    }
  },
  "additional_pages": [
    { "page_id": "my-personal", "name": "My Stuff", "rows": [...] }
  ],
  "hidden_page_ids": ["dispatch"],
  "page_order_override": ["quick-actions", "my-personal"]
}
```

### Runtime path

How an edge-panel reaches screen today:

1. Frontend opens the edge panel → calls `GET /api/v1/edge-panel/resolve?panel_key=default`
2. Route handler at `backend/app/api/routes/edge_panel.py:92-135` reads JWT → resolves caller's `company.vertical` + `company.id` → reads `User.preferences.edge_panel_overrides[panel_key]` → calls `resolve_edge_panel(db, panel_key, vertical, tenant_id, user_overrides)`
3. Service walks Tier 1 (platform_default) → Tier 2 (vertical_default) → Tier 3 (tenant_override) for `kind='edge_panel'`, first-match-wins (NOT delta — locked-to-fork pre-B-1.5 because edge-panels never had a true inheritance model; "Tier 3 tenant_override" was a full-replace row, parallel to Focus pre-sub-arc-A)
4. After resolving a base `pages` blob, layers user_overrides via `_user_overrides_for(...)` apply: per-page → additional_pages → hidden_pages → page_order
5. Returns `_ResolveResponse` with `pages: list[dict]`, `canvas_config: dict`, `source`, `source_id`, `source_version`

Two ancillary routes also exist:
- `GET/PATCH /api/v1/edge-panel/preferences` — reads/writes the user's own `edge_panel_overrides` blob
- `GET /api/v1/edge-panel/tenant-config` — reads `Company.settings_json` for `edge_panel_enabled` + `edge_panel_width`

Frontend client lives in `frontend/src/lib/runtime-host/` (per arc context) — verified through grep; concrete consumer call sites are out-of-scope for this investigation (B-1.5 doesn't touch frontend).

### Seed

Identified edge-panel rows in seed today by `panel_key` discriminator:

- `backend/scripts/seed_edge_panel.py` seeds **one** row: `scope='platform_default'`, `kind='edge_panel'`, `focus_type='default'`, two pages (`quick-actions`, `dispatch`). Production guard via `ENVIRONMENT=production` refuses to run; idempotency via content-equality short-circuit (`seed_edge_panel.py:182-208`).

No vertical_default or tenant_override edge-panel rows are seeded in dev/staging today. The R-5.0 build deferred per-vertical edge-panel authoring to "the visual editor (R-5.1+)" (`seed_edge_panel.py:22-23`).

**Implication for B-1.5 seed**: a single Tier 2 `platform_default` row mirrors the existing seed. Whether to seed any `vertical_default` rows is a separate question (§7).

---

## Section 2 — Schema design

Two new tables. Mirror B-1's `focus_templates` + `focus_compositions` structurally where possible; diverge where edge-panel-specific semantics demand it.

### `edge_panel_templates` (Tier 2 equivalent)

```sql
CREATE TABLE edge_panel_templates (
    id              VARCHAR(36) PRIMARY KEY,
    scope           VARCHAR(32) NOT NULL
                       CHECK (scope IN ('platform_default','vertical_default')),
    vertical        VARCHAR(32) REFERENCES verticals(slug),
    panel_key       VARCHAR(96) NOT NULL,        -- e.g. "default", "dispatch"
    display_name    VARCHAR(160) NOT NULL,
    description     TEXT,
    -- The canonical multi-page composition. Non-empty per CHECK at
    -- service layer (DB-level CHECK on JSONB shape is impractical).
    pages           JSONB NOT NULL DEFAULT '[]',
    canvas_config   JSONB NOT NULL DEFAULT '{}',
    version         INT NOT NULL DEFAULT 1,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    created_by VARCHAR(36),
    updated_at TIMESTAMPTZ NOT NULL,
    updated_by VARCHAR(36),
    CHECK (
        (scope='platform_default' AND vertical IS NULL)
        OR (scope='vertical_default' AND vertical IS NOT NULL)
    )
);

CREATE UNIQUE INDEX ix_edge_panel_templates_active
    ON edge_panel_templates (scope, vertical, panel_key)
    WHERE is_active = TRUE;

CREATE INDEX ix_edge_panel_templates_lookup
    ON edge_panel_templates (panel_key, scope, vertical)
    WHERE is_active = TRUE;
```

Mirror of B-1's `focus_templates` minus the `inherits_from_core_*` columns (no Tier 1). The `pages` column replaces `rows` + accommodates the multi-page shape edge-panels require. Audit cols follow sub-arc A's convention — no FK to users (audit attribution gap accepted platform-wide per CLAUDE.md §4 "Audit attribution limitation").

**Forward-compat note**: deliberately NO `inherits_from_*` columns here. Edge-panels are two-tier; if a future Tier 1 ever lands (e.g. "edge-panel shells" with shared chrome), it's a new migration. Keeping the schema honest now is cheaper than dragging vestigial NULLable FKs forward.

### `edge_panel_compositions` (Tier 3 lazy fork)

```sql
CREATE TABLE edge_panel_compositions (
    id              VARCHAR(36) PRIMARY KEY,
    tenant_id       VARCHAR(36) NOT NULL
                       REFERENCES companies(id) ON DELETE CASCADE,
    inherits_from_template_id      VARCHAR(36) NOT NULL
                       REFERENCES edge_panel_templates(id) ON DELETE RESTRICT,
    inherits_from_template_version INT NOT NULL,  -- forward-compat Option B; v1 ignored
    deltas                  JSONB NOT NULL DEFAULT '{}',
    canvas_config_overrides JSONB NOT NULL DEFAULT '{}',
    version         INT NOT NULL DEFAULT 1,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    created_by VARCHAR(36),
    updated_at TIMESTAMPTZ NOT NULL,
    updated_by VARCHAR(36)
);

CREATE UNIQUE INDEX ix_edge_panel_compositions_active
    ON edge_panel_compositions (tenant_id, inherits_from_template_id)
    WHERE is_active = TRUE;
```

Identical in shape to B-1's `focus_compositions` minus the synthetic-core-injection concern. The CASCADE on tenant deletion + RESTRICT on template deletion mirror B-1 verbatim — same rationale.

**`inherits_from_template_version`** ships from day one per Option B forward-compat (mirroring B-1 + the original Focus inheritance investigation §3). v1 resolver always picks the active template row; v2 can pin to the version stored here. Service-layer-only change.

### Migration

Single migration `r97_edge_panel_substrate` (chained off `r96_focus_template_inheritance` — verified head). Greenfield: no rows to migrate. The R-5.0 seed re-runs via `seed_edge_panel.py` rewrites against new tables (see §7).

---

## Section 3 — Tier 3 delta vocabulary

Edge-panel Tier 3 deltas are **page-keyed**, recursively containing placement-level deltas inside per-page records. This is the single biggest architectural divergence from B-1's Focus deltas (which are placement-keyed at the top level because Focus is single-page).

Recommended structure — directly carries the R-5.0 + R-5.1 User-preference vocabulary up into the Tier 3 substrate (zero new vocabulary to invent, full reuse of the production-tested override engine):

```json
{
  "hidden_page_ids": ["dispatch"],
  "additional_pages": [
    { "page_id": "tenant-custom-page",
      "name": "Custom",
      "rows": [...],
      "canvas_config": {} }
  ],
  "page_order": ["quick-actions", "tenant-custom-page"],
  "page_overrides": {
    "quick-actions": {
      "hidden_placement_ids": ["btn-pulse"],
      "additional_placements": [
        { "placement_id": "btn-tenant-extra",
          "component_kind": "button",
          "component_name": "open-tenant-saved-view",
          "starting_column": 0,
          "column_span": 12,
          "row_index": 1,
          "prop_overrides": {} }
      ],
      "placement_geometry_overrides": {
        "btn-scheduling": { "starting_column": 0, "column_span": 6 }
      },
      "placement_order": ["btn-tenant-extra", "btn-scheduling"]
    }
  }
}
```

**Vocabulary verdict**: recursive (page-level outer, placement-level inner). Two reasons to reuse vs. flatten:

1. **R-5.0 + R-5.1 already shipped this exact shape** at the User-override layer (`composition_service.resolve_edge_panel`). The Tier 3 resolver can literally invoke the existing `_apply_placement_overrides` helper for per-page placement deltas + the existing top-level page-key logic for page-level deltas. Zero new merge code.
2. **Flattening (single page-id-qualified key list) loses structural locality**: a Tier 3 delta blob with `hidden_placement_ids: ["quick-actions::btn-pulse", "dispatch::btn-cement"]` is harder for the admin UI to render + harder for the resolver to walk. The nested form maps 1:1 to "edit this page" mental model.

**Divergence note vs. R-5.0 User overrides**: I'm adding `placement_geometry_overrides` to the per-page shape (B-1 Focus has it at the top level). The R-5.0 vocabulary doesn't carry geometry override per-placement — it carries the full-replace `rows` escape hatch as a last resort. For Tier 3 we want per-placement geometry without falling back to full-replace, mirroring B-1's `placement_geometry_overrides`. The R-5.0 User-override path can adopt this in a follow-up (see §6).

**Orphan-handling**: drop silently at debug log level. Mirrors B-1's resolver (`backend/app/services/focus_template_inheritance/resolver.py:303-310`) + R-5.0's `_apply_placement_overrides` (`composition_service.py:818-823`). Three orphan classes:

- Tier 3 references a `page_id` that template no longer has → drop page-override silently
- Tier 3 `hidden_placement_ids` references missing placement → no-op
- Tier 3 `placement_geometry_overrides` references missing placement → debug-log, drop

---

## Section 4 — Resolver design

Public signature:

```python
def resolve_edge_panel(
    db: Session,
    *,
    panel_key: str,
    vertical: str | None,
    tenant_id: str | None,
    user_id: str | None,
) -> ResolvedEdgePanel
```

**Note fourth argument** `user_id`. User-level overrides (R-5.0's `User.preferences.edge_panel_overrides[panel_key]`) compose on top of tenant composition. The resolver itself reads `User.preferences` rather than accepting `user_overrides` as a kwarg — keeps the boundary clean (caller passes user identity; resolver owns the read).

### Composition order

1. **Tier 2 lookup**: try `(vertical_default, vertical, panel_key) active` → fall back to `(platform_default, None, panel_key) active`. Raise `EdgePanelTemplateNotFound` on miss. Mirrors B-1 `_find_active_template`.
2. **Tier 3 composition** by `(tenant_id, template.id) active`. Zero-or-one row. None means lazy-pre-edit; tenant uses raw Tier 2 + user overrides only.
3. **User overrides** via `User.preferences.edge_panel_overrides[panel_key]`. Zero-or-one. Reuses R-5.0's existing read path.
4. **Compose**:
   - Start with `template.pages` deep-copied
   - Apply Tier 3 deltas: hide pages → add pages → reorder pages → per-page placement deltas (hide → add → geometry → reorder, reusing `_apply_placement_overrides`)
   - Apply User overrides last: same vocabulary as Tier 3 (composes via the SAME helpers in the SAME order)
5. Compose `canvas_config`: template's config + tenant's `canvas_config_overrides` + user overrides' top-level `canvas_config` (if R-5.x ever adds one — currently not in the User shape).

### `ResolvedEdgePanel` shape

```python
class ResolvedEdgePanel(BaseModel):
    panel_key: str
    template_id: str
    template_version: int
    template_scope: str             # 'platform_default' | 'vertical_default'
    template_vertical: str | None
    pages: list[dict[str, Any]]
    canvas_config: dict[str, Any]
    sources: dict[str, Any]
```

`sources` provenance (mirrors B-1):

```python
{
  "template": {"id": str, "version": int, "scope": str, "vertical": str | None},
  "composition": {"tenant_id": str, "composition_id": str, "version": int} | None,
  "user_override": {"applied": bool}    # boolean for v1; could carry diff later
}
```

### Performance

Three indexed lookups + one dict access on `User.preferences`. Mirrors B-1's resolver profile (single-digit-ms expected). v1 no caching.

### Edge cases

- **Page added by Tier 3, User overrides hides it** → User wins (later compose). Same as R-5.0 today.
- **Tier 2 removes a page that Tier 3 references in `page_overrides`** → orphan, drop silently.
- **User overrides reference page_ids that don't exist post-Tier-3-compose** → orphan, drop silently (matches R-5.0 today).
- **`canvas_config` merge order**: template → tenant → user. User-layer canvas_config currently not part of R-5.0 top-level vocabulary, but the resolver should anticipate it (low-cost — one `dict.update` call).
- **Tenant's `inherits_from_template_id` points at a version whose template is now inactive but no newer active version exists for the (scope, vertical, panel_key) tuple** → effectively the template was deleted; `ON DELETE RESTRICT` should prevent this state from ever existing, but if it does (data corruption), raise `EdgePanelTemplateNotFound`.

---

## Section 5 — Service layer + admin API surface

Three service modules under `backend/app/services/edge_panel_inheritance/` (mirroring B-1's package layout at `backend/app/services/focus_template_inheritance/`):

- **`edge_panel_templates_service.py`** — Tier 2 CRUD + version bump on update. Mirrors `focus_templates_service.py` (470 LOC) minus the `inherits_from_core_*` handling. Estimated ~350 LOC.
  - Public: `create_template`, `update_template`, `get_template`, `list_templates`, `template_usage` (count of dependent Tier 3 compositions).
- **`edge_panel_compositions_service.py`** — Tier 3 lazy fork + reset operations. Mirrors `focus_compositions_service.py` (476 LOC) one-for-one. Estimated ~400 LOC.
  - Public: `upsert_composition` (creates row on first call; replaces deltas on subsequent), `reset_composition` (deactivates active row entirely), `reset_page` (NEW — removes a single `page_overrides[<page_id>]` entry), `reset_placement` (removes a single placement-key entry; mirrors B-1's `reset_placement`).
- **`resolver.py`** — `resolve_edge_panel` per §4. Estimated ~250 LOC (smaller than B-1's 439 because no core-injection logic).

Public signatures match B-1 structurally. Documented divergences:

- B-1 has `focus_cores_service.py` (Tier 1 CRUD) — **absent here** by design.
- Composition service adds `reset_page` operation (no B-1 analogue — Focus is single-page).

### Admin API surface

Routes at `/api/platform/admin/edge-panel-inheritance/*` (mirroring `/api/platform/admin/focus-template-inheritance/*`). Estimated ~500 LOC, similar to B-1's 605.

- `GET /templates?scope=&vertical=` — list with filters
- `GET /templates/{id}` — single row
- `POST /templates` — create (versions a prior row at same tuple if exists)
- `PUT /templates/{id}` — update (bumps version + deactivates prior)
- `GET /templates/{id}/usage` — count of dependent Tier 3 compositions
- `GET /compositions/by-tenant-template?tenant_id=&template_id=` — single zero-or-one lookup
- `POST /compositions` — upsert (create or replace deltas)
- `POST /compositions/{id}/reset` — full reset (deactivate active row)
- `POST /compositions/{id}/reset-page/{page_id}` — **NEW: per-page reset** (removes one entry from `deltas.page_overrides`). Page-level granular reset is meaningful for edge-panels because deltas are page-keyed; this is the equivalent of B-1's `reset-placement` adapted for the page-keyed delta vocabulary.
- `POST /compositions/{id}/reset-placement/{page_id}/{placement_id}` — additional granular reset for within-page placement deltas
- `GET /resolve?panel_key=&vertical=&tenant_id=&user_id=` — full inheritance walk; admin debugging

**Auth model** mirrors B-1 (verified via `backend/app/api/routes/admin/focus_template_inheritance.py:110-184`): platform-admin on Tier 2 ops; hybrid (platform admin OR matching tenant) on Tier 3 ops + resolve.

---

## Section 6 — User override layer scope question

**Locked decision**: R-5.0 User overrides on `User.preferences.edge_panel_overrides[panel_key]` stay untouched by B-1.5. The resolver MUST consume them; the WRITE path stays on existing tenant-realm endpoints.

### Concrete scope

- **Does B-1.5 add admin API for managing user overrides?** No. Users manage their own via existing tenant-realm `PATCH /api/v1/edge-panel/preferences`. Platform admins debugging a specific user's resolved edge panel use the new admin `/resolve?panel_key=&...&user_id=` route which reads the user's preferences read-only.

- **Does existing tenant-realm `/api/v1/edge-panel/*` need rewriting?** Recommend **no** — leave as-is. The tenant-realm endpoint reads `User.preferences` + calls `resolve_edge_panel` (the new B-1.5 one, swapped in). The User-preference write path (`PATCH /preferences`) is unchanged — still writes the same JSONB blob shape. B-2's scope on the tenant-realm rewrite is minimal: swap the import from `from app.services.focus_compositions import resolve_edge_panel` to `from app.services.edge_panel_inheritance import resolve_edge_panel`. ~5 LOC of routing change.

- **Vocabulary alignment between Tier 3 and User-override layer**: §3 recommended adding `placement_geometry_overrides` to Tier 3 deltas — a vocabulary element NOT currently in R-5.0's User-override schema. The two layers can stay slightly divergent in v1 (Tier 3 supports geometry overrides; User layer doesn't). Aligning the User layer is a follow-up (R-5.2 territory) and out of B-1.5 scope.

### B-2 implications

B-2's edge-panel consumer rewrites become smaller than originally scoped:

- `edge_panel.py` (tenant-realm route): swap the `resolve_edge_panel` import + adjust kwarg names if the new signature differs (passing `user_id` instead of `user_overrides`). Minimal.
- Test files `test_edge_panel_r50.py` + `test_edge_panel_user_override.py` need adapter shims — they assert against the old `composition_service.resolve_edge_panel` return shape. New resolver returns a Pydantic model (B-1 precedent); old tests built dicts directly. Estimated ~100 LOC of test-only refactor.

---

## Section 7 — Seed

**Recommended seed scope for B-1.5**:

1. **One Tier 2 `platform_default` template** at `panel_key='default'` with the two pages currently in `seed_edge_panel.py` (`quick-actions` + `dispatch`). Migrates the R-5.0 seed verbatim into the new substrate.
2. **No vertical_default rows** in B-1.5 seed. The R-5.0 ship deferred per-vertical authoring to the visual editor; B-1.5 preserves that. Future per-vertical edge-panels land via admin authoring.
3. **No tenant_override rows** seeded — Tier 3 is lazy-fork by design.

### Open question: is the current edge-panel conceptually tenant-default or platform-default?

The R-5.0 seed authored it as `platform_default` — applies to every tenant regardless of vertical. The content (button slugs `open-funeral-scheduling-focus`, `trigger-cement-order-workflow`, `navigate-to-pulse`) cross vertical lines: scheduling Focus is FH-specific, cement-order workflow is manufacturing-specific. A platform_default with cross-vertical button references "works" because the buttons themselves resolve through their own (R-4.0) registry which silently no-ops when the underlying action target is missing for the caller's tenant. Acceptable for v1; gives every tenant *something* on first open. Promote to vertical-specific in a follow-up.

**Seed implementation**: idempotent via content-equality short-circuit (carry over `_pages_content_equal` from R-5.0 verbatim — `seed_edge_panel.py:134-179`). Production guard via `ENVIRONMENT=production` refusal mirrors existing seed scripts.

The existing `seed_edge_panel.py` gets rewritten against the new substrate (~250 LOC mostly preserved; only the table target + create call shape changes).

---

## Section 8 — Sub-arc B-2 re-scoping

Post-B-1.5, B-2 looks like:

**Focus consumer rewrites** (unchanged from pre-halt B-2 plan):
- `composition_service.py` — Focus-relevant resolver paths consolidated; edge-panel paths deleted (handed off to B-1.5's new module)
- `visual_editor_compositions.py` (route) — Focus-only admin endpoints retained; edge-panel admin removed
- `vertical_inventory.py` — focuses count rewires; edge-panel count rewires to point at new tables
- `test_focus_compositions.py`, `test_vertical_inventory.py` — test rewrites

**Edge-panel consumer rewrites** (now MUCH smaller):
- `edge_panel.py` (tenant-realm route) — single-line import swap + kwarg adjustment to new resolver signature
- `vertical_inventory.py` — edge-panels count source-table swap
- `test_edge_panel_r50.py`, `test_edge_panel_user_override.py` — adapter to new resolver return shape (~100 LOC each)

**Shim removal** in `focus_composition.py` (the import-compat shim B-1 left for the legacy single-table layout).

### B-2 LOC estimate post-B-1.5

| Component | LOC |
|---|---|
| Focus consumer rewrites | ~700 |
| Edge-panel consumer rewrites | ~300 |
| Shim removal + integration plumbing | ~100 |
| **Total** | **~1,100** |

Down from the original B-2 estimate of ~1,800 because the substrate gap accounted for most of the LOC blow-up. Within original budget.

---

## Section 9 — Architectural risks + open questions

**R1 — User-override vocabulary alignment with new Tier 3 schema.** R-5.0's User-override layer already supports the recursive page → placement vocabulary at top-level + per-page granularity. Tier 3 reuses the same vocabulary except for `placement_geometry_overrides` (NEW in Tier 3; absent at User layer). Open question: do we let them diverge in v1 or backfill the User layer simultaneously? **Recommendation**: diverge in v1. Adding `placement_geometry_overrides` to the User layer is a service-layer-only follow-up; landing both in B-1.5 swells scope unnecessarily.

**R2 — Edge-panel author-time UX surface.** Where does the platform admin author Tier 2 `edge_panel_templates` rows? The R-5.0 ship deferred this to "R-5.1+ visual editor." If B-1.5 ships the substrate without an authoring UI, admin authoring happens via raw SQL / direct API calls until a Studio rail entry lands. **Recommendation**: ship B-1.5 substrate-only. Editor UX is a sub-arc C-equivalent that mirrors the Focus Tier 2 editor pattern but renders a multi-page UI (page tabs + per-page canvas). Defer to its own arc. The Focus Tier 1+2 editor at `/visual-editor/focus-templates` could grow an "Edge Panels" sibling tab; that's a future Studio decision.

**R3 — Does `edge_panel_templates` need a Tier 1 "shared shell" / "base" for cross-vertical reuse?** Per locked decision 2, no Tier 1. Open question: when multiple verticals want the same chrome (header bar, footer, default button set) but different inside content, is the missing Tier 1 painful? **Recommendation**: stay two-tier. If pain emerges, add Tier 1 in a future arc. Two-table inheritance is the right starting shape; premature Tier 1 generalization (the "decision/generation/kanban core_shape" question that R2 from the B-1 investigation raised) is worth deferring.

**R4 — Migration label.** Chain head is `r96_focus_template_inheritance` (verified via `git log` + `ls backend/alembic/versions/r9*`). B-1.5 ships `r97_edge_panel_substrate`. Confirm head at dispatch time + adjust if any other arc lands between now and B-1.5.

**R5 — Tier 2 deletion when Tier 3 forks exist.** `ON DELETE RESTRICT` mirrors B-1. Tier 2 deletion is admin-triggered + low-frequency; surface migration tooling in a follow-up.

**R6 — Composition row's `inherits_from_template_id` becoming stale after template re-author.** Live cascade (locked decision per Focus arc) — Tier 3 resolver always picks the active template row, ignoring `inherits_from_template_version`. v2 Option B versioned cascade lands additively at the service layer. Same model as B-1; no extra surface area.

**R7 — `nested_rows` / hierarchical placement support.** Existing R-5.0 placement shape carries `nested_rows: None` as forward-compat (`_validate_pages` + `_apply_placement_overrides` ignore it). B-1.5 preserves the forward-compat field but doesn't act on it. Same posture as B-1.

**R8 — Page-level `canvas_config` vs top-level `canvas_config_overrides`.** Edge-panel templates carry both top-level `canvas_config` (the JSONB column) AND per-page `canvas_config` (inside each page record). The resolver should compose both: top-level template → top-level tenant overrides → page-level template → page-level tenant overrides (via `page_overrides[pid].canvas_config`). Two distinct merge paths in different layers. Document explicitly in the service code.

---

## Closing notes

Investigation surfaces no surprises that should re-litigate locked decisions. The recommendations:

- **Two-table schema** mirroring B-1's `focus_templates` + `focus_compositions` minus Tier 1.
- **Recursive page-keyed Tier 3 delta vocabulary** matching the R-5.0 + R-5.1 User-preference shape verbatim plus an added `placement_geometry_overrides` per page.
- **Resolver composes Tier 2 → Tier 3 → User overrides** in that order; resolver reads User overrides itself from `User.preferences` rather than accepting them as a kwarg.
- **Seed**: one `platform_default` row reproducing the R-5.0 default panel.
- **Admin API**: parallel structure to B-1's admin namespace; adds `reset-page/{page_id}` operation; tenant-realm endpoints untouched until B-2 swap.

LOC estimate for B-1.5: **~1,500-1,800** ±15% (schema ~150, services ~1,000, admin API ~500, seed ~250, tests ~600). Within single-dispatch budget.

The largest sequencing risk is R2 (no authoring UX); ship substrate-only + plan the editor as a separate sub-arc that fits the Studio canon.
