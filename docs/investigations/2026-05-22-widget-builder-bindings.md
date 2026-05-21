# Widget Builder Bindings — Read-Only Investigation

**Date:** 2026-05-21 (filename retains scheduled date `2026-05-22` per prompt direction).
**Arc:** `2026-05-22-widget-builder-bindings`. Establishes substrate shape for WB-6 (binding picker activation + field_path resolution + iteration substrate). Zero production code changes.
**Pre-flight:** HEAD verified at `3d39598` (WB-4b shipped; WB-4 cycle complete). 114 stale Playwright screenshot deletions in working tree left untouched per prompt.
**DECISIONS.md canon entry count:** 42 (unchanged this investigation).
**Read-only:** new investigation doc + STATE.md update only.

---

## 1. Context

WB-1/2/3/4a/4b shipped the widget-builder substrate as Phase 1 placeholders for bindings:

- **WB-1** (`7eb1280`) — `BindingRef` Pydantic schema + TypeScript mirror at `backend/app/schemas/widget_composition.py:101-122` and `frontend/src/lib/widget-builder/types/composition-blob.ts:61-72`. Discriminated by `binding_type ∈ {literal, field_path}` with `iteration_mode ∈ {per_row, single_summary, single_record}`. `expression` deferred per investigation Q-7 to WB-7.
- **WB-2** (`95ddd16`) — `resolveBinding` runtime helper at `frontend/src/lib/widget-builder/runtime/resolveBinding.ts`. `literal` returns verbatim; `field_path` returns placeholder string `[bound:${field_path}]`. `dataContext` parameter declared but unused. Per file header: "WB-6 makes this real (saved-view query execution + row-shape projection + iteration_mode handling)."
- **WB-3** (`4b6b173`) — `repeater_atom` architectural primitive at `AtomRenderer.tsx:186-228`. Iterates with 1 mock row, threading `{__row: true, __index: i}` into `dataContext` so the per-row resolution branch in `resolveBinding` (lines 37-44) surfaces `[bound:row.${field_path}#${idx}]`. Per inline comment: "WB-6 swaps the mock data for real saved-view row projection."
- **WB-4a/4b** (`3680950`, `3d39598`) — Builder shell + per-atom inspectors. `BindingPlaceholderField` at `frontend/src/bridgeable-admin/components/widget-builder/inspectors/inspector-primitives.tsx:184-203` renders "Binding picker activates in WB-6" disabled-but-visible UX. Three call sites at `AtomInspectorDispatch.tsx:404, 731, 854`. WB-4b composition validator at `backend/app/services/widget_definitions/validators.py:170-217` enforces repeater_atom binding shape (`binding_type='field_path'` + `iteration_mode='per_row'`) but does NOT enforce saved_view_id resolves to a real saved view, nor field_path resolves to a real field on that view's entity.

WB-5 (canvas preview wiring to real data) is sequenced AFTER WB-6 per `docs/investigations/2026-05-21-widget-builder-canvas.md:484` ("WB-6 (saved-view substrate) reordered before WB-5 (binding) in the sequence"). This investigation clarifies the WB-6/WB-5 seam at Area 8; it does NOT design WB-5.

The original widget-builder investigation (`5771fc0`, `docs/investigations/2026-05-21-widget-builder.md`) did NOT audit saved-view substrate. Area 1 below corrects that omission per the WB-2/WB-4b canon candidate (audit-first phase before locking decisions).

---

## 2. Area 1 — Saved-view substrate audit (LOAD-BEARING)

### 2.1 Audit findings

**Saved-view substrate EXISTS and is MATURE.** Verified extent:

| Layer | File / location | LOC | Status |
|---|---|---|---|
| Pydantic types | `backend/app/services/saved_views/types.py` | 547 | Mature — 4-level visibility, 7 presentation modes, cross-tenant masking schema |
| CRUD service | `backend/app/services/saved_views/crud.py` | 458 | Visibility + role + cross-tenant gating; 4-level visibility model |
| Executor | `backend/app/services/saved_views/executor.py` | 449 | Query execution + filter + sort + grouping + aggregation + cross-tenant field masking |
| Entity registry | `backend/app/services/saved_views/registry.py` | 717 | 8 entity types registered (fh_case, sales_order, invoice, contact, product, document, vault_item, delivery); `allowed_verticals` per entity |
| Seed templates | `backend/app/services/saved_views/seed.py` | 753 | 25+ `SeedTemplate` records keyed by `(vertical_slug, role_slug)`; idempotent via `saved_view_seed:<role>:<key>` |
| API routes | `backend/app/api/routes/saved_views.py` | 453 | 8 endpoints (list / get / create / update / delete / duplicate / preview / execute) + entity-types catalog |
| Frontend client | `frontend/src/services/saved-views-service.ts` | (full client) | All 8 endpoints wrapped; `executeSavedView`, `getSavedView`, `listEntityTypes` already used by `SavedViewWidget` |
| Migrations | `r32_saved_view_indexes`, `r62_cleanup_cross_vertical_saved_views` | — | Indexes shipped; cross-vertical cleanup landed |
| Frontend renderers | `frontend/src/components/saved-views/` | 7 renderers + builder | List, Table, Kanban, Calendar, Cards, Chart, Stat — all 7 presentation modes |
| Hub embed | `frontend/src/components/saved-views/SavedViewWidget.tsx` | full | One-component-per-view-id embed used by hubs |

**Storage:** `vault_items.metadata_json.saved_view_config` is canonical per `crud.py` line 8. Saved views ARE VaultItems with `item_type = 'saved_view'`. Tenant-scoped via `vault_items.company_id`.

**Result shape from executor** (`SavedViewResult` at `types.py:513`): `total_count: int`, `rows: list[dict]`, `groups: dict[str, list[dict]] | None`, `aggregations: dict | None`, `permission_mode: "full" | "cross_tenant_masked"`, `masked_fields: list[str]`.

- **List / table / cards / calendar** modes: `rows` populated; one flat dict per row.
- **Kanban**: `rows` AND `groups` both populated.
- **Chart**: `aggregations.buckets: [{x, y}, ...]`.
- **Stat**: `aggregations.value: float` + optional `comparison_value` + `comparison_delta` (Phase 2 stub at `executor.py:386-394`).

**Per-row field shape**: each `row` dict's keys are whatever the entity's `row_serializer` emits — narrowly defined per entity at `registry.py`. Examples: an `invoice` row has `id`, `number`, `status`, `total`, `invoice_date`, `due_date`, etc.

**Cross-tenant scope (HIDDEN COMPLEXITY worth surfacing):**

The substrate has a **fully-built cross-tenant masking path** that is UI-unexposed:

- `Permissions.shared_with_tenants: list[str]` (`types.py:404`)
- `Permissions.cross_tenant_field_visibility.per_tenant_fields: dict[tenant_id, list[field_name]]` (`types.py:374`)
- Executor masking at `executor.py:148-169`: when `caller_company_id != owner_company_id`, fields not in the whitelist are replaced with `__MASKED__` sentinel.
- CRUD gating at `crud.py:112-113`: cross-tenant access permitted ONLY when `user.company_id in perms.shared_with_tenants`.

Per `crud.py:19-21`: "Cross-tenant sharing is UI-unexposed; `shared_with_tenants` list lives in the config for the backend masking path. crud doesn't grant cross-tenant access — that's a separate future workflow."

**Vertical-scope inheritance (load-bearing for WB-6):**

Per W-4a Step 3 / BRIDGEABLE_MASTER §3.25 amendment, each entity has `allowed_verticals: list[str]` (`registry.py:151`). `["*"]` = cross-vertical; `["funeral_home"]` = single-vertical. Helper `is_entity_compatible_with_vertical()` at `registry.py:199` is the canonical permission-vs-vertical check.

Saved views themselves do NOT have a Tier-1 (Bridgeable platform) / Tier-2 (vertical default) / Tier-3 (tenant) inheritance shape at the table level. They live on `vault_items` and are tenant-scoped via `company_id`. **Cross-tenant sharing is per-saved-view, not per-tier.** Bridgeable-canonical templates are seeded into each tenant via `seed.py:seed_for_user()`; there is no central "platform" saved view that every tenant inherits.

### 2.2 Implications for WB-6

- WB-6 **consumes** existing substrate. No prerequisite work on the saved-view side itself is required.
- The **executor + cross-tenant masking + visibility gating** all already produce a row shape suitable for binding resolution.
- Field-path enumeration data is **already exposed** via `GET /api/v1/saved-views/entity-types`, which returns the per-entity `available_fields` list (`registry.py:140`). Each `FieldMetadata` carries `field_name`, `display_name`, `field_type`, `filterable`, `sortable`, `groupable`, `enum_values`, `relation_entity`. The field picker has its data source.
- **The `vault_item` entity type is a generic fallback** containing `event_type`, `item_type`, `status`, etc. Many of the Phase 1 seeded templates use `vault_item` with filters (e.g., production board kanban: `item_type=production_record`). Field-path resolution against `vault_item` rows needs to traverse `metadata_json` for entity-specific fields. **This is the largest hidden complexity in WB-6.** Risk surfaced in §11.

### 2.3 Alternative interpretations considered

- **(a) Treat saved-view substrate as missing / partial** → **REJECTED.** Audit shows mature, well-tested, in-production substrate.
- **(b) Build a parallel "widget query" substrate** → **REJECTED.** Duplicates work. BRIDGEABLE_MASTER §9.4 ("widgets are Vault views with chrome") is the canonical thesis. Original WB investigation Q-11 LOCK reinforces: "(a) for WB-Phase-1. Operator picks a Vault saved view."
- **(c) Consume existing saved-view substrate** → **LOCKED.** WB-6 is consumption + glue, not substrate creation.

---

## 3. Area 2 — BindingRef symmetry audit

### 3.1 Triad enumeration

Per WB-2 / WB-4b canon candidate (runtime ↔ Pydantic ↔ TypeScript symmetry at substrate boundaries):

**Pydantic** (`backend/app/schemas/widget_composition.py:101-122`):
```
BindingRef:
  binding_id: str
  binding_type: Literal["literal", "field_path"]
  literal_value: Optional[Any] = None
  saved_view_id: Optional[str] = None
  field_path: Optional[str] = None
  iteration_mode: Optional[Literal["per_row", "single_summary", "single_record"]] = None
```

**TypeScript** (`frontend/src/lib/widget-builder/types/composition-blob.ts:61-72`):
```
interface BindingRef {
  binding_id: string;
  binding_type: "literal" | "field_path";
  literal_value?: unknown;
  saved_view_id?: string;
  field_path?: string;
  iteration_mode?: "per_row" | "single_summary" | "single_record";
}
```

**Runtime (resolveBinding)** (`frontend/src/lib/widget-builder/runtime/resolveBinding.ts`):
- Reads: `binding_type`, `literal_value`, `field_path`.
- Does NOT read: `saved_view_id`, `iteration_mode` (Phase 1 placeholder).
- Reads via `dataContext`: `__row: boolean`, `__index: number`.

### 3.2 Symmetry verdict

**Field-name + enum-value parity: SYMMETRIC.** All 6 BindingRef fields + both literals + 3 iteration modes match across Pydantic / TypeScript.

**Optional/required discipline: SYMMETRIC.** `binding_id` + `binding_type` required on both sides; all other fields optional with sensible defaults.

**Runtime asymmetry vs schema: EXPECTED.** Per Phase 1 design, `saved_view_id` + `iteration_mode` are present in the schema but UNUSED in resolveBinding. This is the WB-6 wiring scope.

**Pydantic discriminator semantics: SEMI-STRICT.** Pydantic uses `Optional[Any]` for `literal_value` rather than a `Field(discriminator='binding_type')` union. Per the schema docstring (lines 107-112): "Conditionally-required fields (literal_value / saved_view_id / field_path) are validated at the service layer; Pydantic only enforces the field-type contract." The semantic discrimination (e.g., "field_path bindings MUST have saved_view_id + field_path") is enforced at `validators.py` for repeater_atom. **Validator coverage extension is a WB-6 scope item** (§7.4 below).

**Backward-compat aliases: NONE for BindingRef** (unlike the per-atom Config classes which carry WB-4b legacy fields). BindingRef stayed clean.

### 3.3 Symmetry verdict

**No drift.** WB-6 build dispatches against verified-symmetric substrate. The asymmetry between schema (full vocabulary) and runtime (literal + field_path placeholder) IS the WB-6 work surface.

---

## 4. Area 3 — field_path resolution semantics (LOAD-BEARING)

### 4.1 Options

**Dot-notation traversal:**
- (a) `a.b.c` only (no array indexing) — simple; pure-object access.
- (b) `a.b.c` + `items.0.name` (numeric segment = array index) — handles Phase 2 nested arrays.
- (c) `a.b.c` + `items[0].name` bracket syntax — JSONPath-lite.

**Null safety + missing path:**
- (a) Return `null` / `undefined` on any failed traversal. Atom renderers handle as missing data.
- (b) Throw `BindingResolutionError` on missing path. Atom renderers catch + render placeholder.
- (c) Return a sentinel `{__missing: true, path: "a.b.c"}`.

**Per-row vs top-level context:**
- (a) `dataContext.__row === true` → resolve against current row dict (the existing WB-3 stub semantic).
- (b) Resolve against `dataContext` always; per-row context IS the row dict.
- (c) Two field-path syntaxes: `row.a.b.c` vs `summary.a.b.c` for explicit disambiguation.

**Aggregates:**
- (a) Aggregates carry their own `iteration_mode='single_summary'` + the field_path encodes the aggregation (`items.count`, `items.sum.total`).
- (b) Aggregates are a separate binding kind altogether (post-Phase 2; deferred).
- (c) `iteration_mode='single_summary'` + field_path is the aggregation key into `SavedViewResult.aggregations` dict.

### 4.2 Locks

**LOCKED 4a: Dot-notation with numeric-segment array indexing (option b).**

`a.b.c` walks objects. `items.0.name` walks an array. JSONPath bracket syntax (option c) is unnecessary complexity for Phase 1; row dicts from the executor are already flat. The numeric-segment extension covers the one realistic case: a row carrying a nested list (e.g., `line_items.0.total`).

**Reasoning:** `SavedViewResult.rows` already flat-dicts per the registry's `row_serializer`. Nested arrays are rare. The dot-notation parser is ~15 LOC pure function — a `BindingResolutionError` type + traversal with safe-property access.

**LOCKED 4b: Return `null` on missing path; throw on malformed `field_path` syntax (mixed a + b).**

Missing data (path traversal fails on a `null` intermediate) is a *runtime* condition — operator-authored views and tenant-data state both vary; failing soft preserves the atom-level placeholder UX from Q-13 lock. Malformed syntax (e.g., empty string, leading `.`, trailing `.`) is a *programmer error* (author-time, validator-catchable) — throw at resolve time as defense-in-depth.

Atom renderers consume the `null` return as missing data and render placeholder per the per-atom Config `placeholder` field (e.g., `ValueDisplayConfig.placeholder` already exists). No new atom-renderer changes needed.

**LOCKED 4c: Per-row context resolution uses `dataContext` as the row dict directly (refined option b).**

`AtomRenderer.tsx:196` already passes `rowContext = { __row: true, __index: i }`. **WB-6 replaces this with `rowContext = { __row: true, __index: i, ...rowDict }`** — spreading the actual row fields into the context. The `__row` marker stays as a discriminator; `__index` stays for position-aware atoms; the row's fields become directly accessible at the top level of `dataContext`.

`resolveBinding` for `field_path` then:
1. If `dataContext.__row === true`, traverse `field_path` against `dataContext` (the row).
2. Otherwise, the binding is summary-scope; per Area 4 lock 4d below, return the summary value from the top-level result.

The two-syntax option (c) was considered + rejected — operator UX cost of teaching `row.foo` vs `summary.foo` outweighs disambiguation benefit. The discriminator lives in `iteration_mode` + dataContext shape, not in field_path string syntax.

**LOCKED 4d: Aggregates resolve via `iteration_mode='single_summary'` + result.aggregations dict (option c).**

When `iteration_mode='single_summary'`:
- For `presentation.mode='stat'`: `field_path='value'` → returns `aggregations.value`. `field_path='comparison_delta'` → returns `aggregations.comparison_delta`. (Phase 2 stub already provides the shape.)
- For `presentation.mode='chart'`: `field_path='buckets'` → returns the bucket list (rarely useful at atom level; chart widget would consume directly via SavedViewWidget). `field_path='buckets.0.y'` → first bucket's Y value (numeric-segment array indexing per lock 4a).

For non-aggregating presentation modes (list/table/cards/kanban/calendar), `iteration_mode='single_summary'` resolves to `total_count` — the row count of the result set. `field_path='count'` returns `result.total_count`.

**LOCKED 4e: Computed paths deferred to Phase 2 per original WB Q-7.**

Confirmed — no Phase 1 computed paths. Expressions (`row.subtotal + row.tax`) are WB-7+.

### 4.3 Alternatives considered

- **Backend resolution (return resolved values from API)** — REJECTED. Adds round-trip + couples binding semantics across the boundary. Frontend resolves; backend supplies rows.
- **JSONPath-full** — REJECTED. Excessive vocabulary for Phase 1.
- **Two field-path syntaxes** — REJECTED above.

---

## 5. Area 4 — iteration_mode runtime semantics (LOAD-BEARING)

### 5.1 Options

**Per-row data shape:**
- (a) Array of objects (the rows list directly).
- (b) Array of primitives (only one field at a time).
- (c) Mixed allowed at runtime.

**single_summary computation:**
- (a) Backend computes (existing — `executor._aggregate_for_stat`).
- (b) Frontend computes from rows.
- (c) Hybrid — backend for chart/stat modes (already happens); frontend derives `total_count`-style summaries.

**single_record selection:**
- (a) First row of result.
- (b) Operator-configured row picker.
- (c) Last-updated row.

**iteration_mode mismatch handling:**
- (a) Hard error at render time (throw).
- (b) Soft fallback (render placeholder).
- (c) Validator-rejected at Publish time (block ship).

**Compatibility validation extension (WB-4b validator):**
- (a) Extend `validators.py` to enforce per-atom `iteration_mode` consistency.
- (b) Defer to runtime tolerance.
- (c) Hybrid (validator rejects obvious mismatch, runtime handles ambiguous).

### 5.2 Locks

**LOCKED 5a: per_row data is the row dict from SavedViewResult.rows (option a + refinement).**

A `repeater_atom` with `binding_id` → BindingRef with `iteration_mode='per_row'` iterates over `SavedViewResult.rows`. Each row is a dict (per the executor's `row_serializer`). The repeater renders its children once per row with `dataContext = { __row: true, __index: i, ...row }` per lock 4c.

Phase 1 nesting cap (per WB-3): a `repeater_atom` MAY contain `conditional_container` but NOT another `repeater_atom`. Already enforced at `validators.py:218-242`.

**LOCKED 5b: single_summary uses backend aggregations + frontend-derived `total_count` (option c).**

For `presentation.mode ∈ {chart, stat}`, the backend already produces `aggregations` (per `executor.py:178-185`). WB-6 frontend reads `result.aggregations` and resolves field_paths against it.

For `presentation.mode ∈ {list, table, cards, kanban, calendar}`, the frontend derives `total_count` from `result.total_count` as the canonical single_summary value. No backend changes needed.

**LOCKED 5c: single_record selects the first row of result (option a).**

`iteration_mode='single_record'` → `dataContext = { __row: true, __index: 0, ...rows[0] }` (or empty/`null` if no rows). Operator can sort the saved view to control which record is "first." Operator-configured row picker (option b) deferred — not needed for Phase 1.

This unifies `single_record` with `per_row[0]` at the resolution layer: same row-dict shape, single iteration only.

**LOCKED 5d: iteration_mode mismatch is validator-rejected at Publish, runtime-tolerant otherwise (option c).**

WB-4b validator already enforces repeater_atom binding has `iteration_mode='per_row'` (`validators.py:200-206`). WB-6 extends:

- A non-repeater atom referencing a BindingRef with `iteration_mode='per_row'` is rejected at Publish (per_row bindings must be consumed by a repeater).
- A repeater_atom referencing a BindingRef with `iteration_mode != 'per_row'` is already rejected.
- A BindingRef with `binding_type='field_path'` that has no `iteration_mode` set is rejected at Publish (Phase 1 every field_path binding MUST declare its mode).

Runtime is forgiving: if validation is bypassed (e.g., test scenario), resolveBinding returns `null` for unsupported combinations + AtomRenderer renders placeholder. Logs a `console.warn` for visibility. No throws.

**LOCKED 5e: Compatibility validation extension at WB-6 scope (option a refined).**

`validators.py` gets extended in WB-6 with:
- "Every field_path BindingRef MUST set iteration_mode."
- "Every field_path BindingRef MUST set saved_view_id."
- "field_path MUST be non-empty string."
- "Per-row bindings MUST be consumed by a repeater_atom (transitive parent walk)."
- "single_record bindings MAY be consumed by any atom (no parent constraint)."
- "single_summary bindings MAY be consumed by any atom."

Saved_view_id existence (referenced saved view actually exists in the tenant) is a *resolution-time* check, not Publish-time. Saved views can be deleted post-Publish; runtime gracefully degrades to placeholder + logged warning.

### 5.3 Alternatives considered

- **Hard backend gate (deny Publish if referenced saved view doesn't exist)** — REJECTED. Couples widget definition lifecycle to saved view lifecycle awkwardly; tenant deletes a view → every widget using it becomes un-publishable forever. Runtime tolerance handles this gracefully.
- **Frontend always re-derives summaries** — REJECTED. Doubles work; backend already aggregates.

---

## 6. Area 5 — Binding picker UX

### 6.1 Options enumerated

**Picker affordance for saved-view selection:**
- (a) Simple dropdown — flat list of all saved views in tenant, alphabetical.
- (b) Filtered combobox — searchable; surfaces entity type + visibility.
- (c) Tree navigator — group by entity_type → owner → view.
- (d) Two-step modal — Step 1: pick entity_type; Step 2: pick saved view of that entity_type.

**Discoverability:**
- (a) Show every saved view the operator can see (per saved-view visibility model).
- (b) Filter to saved views matching widget's declared `target_surface`.
- (c) Filter to saved views compatible with the atom requesting binding (e.g., repeater needs `per_row` shape).

**Field path picker:**
- (a) Separate from saved-view picker (two distinct controls).
- (b) Combined chooser (picker yields `{saved_view_id, field_path}` together).
- (c) Cascading — saved-view picker first; field-path picker activates once a view is picked.

**iteration_mode picker:**
- (a) Separate explicit control.
- (b) Inferred from atom type (repeater_atom → per_row; everything else → single_record or single_summary).
- (c) Inferred from saved-view shape (list-mode views → per_row; chart/stat views → single_summary).

**Error states:**
- (a) "Saved view deleted" + clear binding.
- (b) "Saved view deleted" + keep binding + render placeholder.
- (c) "Field path invalid" + grayed.

**Empty state:**
- (a) "No saved views yet. Create one →" with inline link.
- (b) Inline saved-view-creator modal (per original WB Q-11 friction mitigation).
- (c) Block widget creation until a saved view exists.

### 6.2 Locks

**LOCKED 6a: Filtered combobox with shape-compatibility filter (options b + c hybrid).**

The picker is a single combobox (similar in spirit to entity-card / pin pickers across the platform) with:
- Search text input.
- Per-row chrome: view title (primary) + entity_type badge (secondary) + visibility badge (tertiary). Owner name as tertiary tooltip.
- **Shape-compatibility filter**: when invoked from a repeater_atom binding picker, only saved views whose **presentation.mode ∈ {list, table, kanban, cards}** are surfaced (these produce per-row rows). When invoked from a non-repeater atom, all views surface. This implements option (c) discoverability filter at the picker layer.
- **Operator-as-platform-builder reframe** per prompt: the picker assumes a sophisticated authoring user, not an end operator. Search + shape-filter are sufficient; no walkthrough chrome.

Tree navigator (option c) and two-step modal (option d) rejected — tree depth in Phase 1 is shallow (single tenant, 7 entity types) so a flat searchable list is faster. Modal flow doubles clicks for a frequent operation.

**LOCKED 6b: Saved-view scope is "every saved view the authoring user can see" (option a refined).**

The picker queries `GET /api/v1/saved-views` (no extra filter) — backend already enforces the 4-level visibility model. Operator sees every view their auth allows: own + role-shared + user-shared + tenant-public.

This punts cross-tenant binding scope to Area 6 (load-bearing decision below).

**LOCKED 6c: Field-path picker cascades from saved-view picker (option c).**

Two distinct controls in the inspector:

1. **Saved view** (combobox) — opens the picker described in 6a.
2. **Field path** (cascading combobox) — disabled until a saved view is picked. Once picked, populates from `GET /api/v1/saved-views/entity-types` → the chosen view's entity_type → `available_fields`. Field name + `display_name` + `field_type` rendered. Search-filterable.

`available_fields` from the entity registry IS the field-path data source. Already exposed; no new endpoint needed.

**Phase 1 limitation**: field_path picker only surfaces top-level fields from `available_fields`. Nested paths (`items.0.name`) are typeable in a text input fallback but not picker-driven. Operator entering an invalid path sees the resolveBinding null fallback + atom placeholder. **Note: vault_item rows carry `metadata_json` containing entity-specific fields not enumerated in registry.available_fields. Picker discoverability is bounded by registry coverage. Risk surfaced at §11.**

**LOCKED 6d: iteration_mode is auto-inferred from atom type + saved-view shape (options b + c hybrid).**

- repeater_atom binding picker auto-sets `iteration_mode='per_row'` (no operator control).
- Non-repeater atom binding picker against a list/table/kanban/cards/calendar view: defaults to `iteration_mode='single_record'`. Operator can switch to `single_summary` to bind to `total_count` (count of rows). Picker control: small toggle "Per-record / Summary" beneath the field-path picker.
- Non-repeater atom binding picker against a chart/stat view: auto-sets `iteration_mode='single_summary'`. The single_record concept doesn't apply.

This makes the iteration_mode field semantically derived from the picker's UX state and rarely operator-touched — but always declared in the persisted BindingRef per Lock 5e.

**LOCKED 6e: Error states render placeholder + flag in validation panel (option b for runtime + flag for authoring).**

Runtime: deleted saved view → resolveBinding returns null → atom renders placeholder. No automatic binding clear (binding survives a transient deletion + restoration).

Authoring: WB-4b's validation surfacing chrome (validation panel pattern) gets extended in WB-6 — "Binding references deleted saved view (id: xxx)" error surfaces in the validation panel + the binding-picker combobox renders the saved_view_id as a strikethrough text + "Re-bind →" affordance.

**LOCKED 6f: Empty-state opens inline saved-view-creator (option b).**

When the picker opens and the tenant has zero saved views the operator can access, an inline "No saved views yet — create one" affordance opens the existing saved-view creator at `/saved-views/new` in a modal/slide-over. Already a frontend route. Reuses the canonical creator.

### 6.3 Alternatives considered

- **Tree navigator** — REJECTED above; over-engineered for Phase 1 cardinality.
- **Block widget creation until a saved view exists** — REJECTED; operator may want to author a widget shell before binding (already supported via literal-only binding).

### 6.4 Operator-validation-sensitive tag

UX decisions 6a (combobox vs tree) and 6c (cascading field picker) are **TAGGED for operator validation post-staging** per DECISIONS entry 35. Authoring throughput on staging may reveal:
- Combobox too dense → tree navigator post-WB-6.
- Field-path picker insufficient for nested-path operators → JSONPath text input post-WB-6.

These are not currently load-bearing; revisit if friction surfaces.

---

## 7. Area 6 — Cross-tenant binding scope (LOAD-BEARING)

### 7.1 Audit findings

Cross-tenant saved-view substrate is **built but UI-unexposed** per §2.1 audit. Cross-tenant binding scope for widgets is a NEW question:

- Can a widget bind to a saved view in a different tenant?
- If the widget is shipped as a Bridgeable-platform template + activated in tenant Y, does it bind to tenant Y's saved view or to a Bridgeable-canonical one?
- The cross-tenant memory reference (Sunnycrest ↔ Hopkins) introduces a third question: cross-tenant Spaces.

### 7.2 Options

**Phase 1 binding scope at authoring time:**
- (a) Bindings only to saved views in the authoring user's tenant.
- (b) Bindings to saved views the authoring user can see, including cross-tenant (via `shared_with_tenants`).
- (c) Bindings declared symbolically (by name/key); resolved per-tenant at render time.

**Render-time scope:**
- (a) Bindings resolved against the rendering user's tenant only.
- (b) Bindings carry tenant_id at the BindingRef level; resolved against that tenant (with cross-tenant masking applied).
- (c) Symbolic binding resolution: render-time mapping table per tenant.

**Bridgeable-canonical-widget binding (Tier-1-style):**
- (a) Bridgeable-canonical widgets carry per-tenant binding overrides.
- (b) Bridgeable-canonical widgets cannot bind to saved views (only literals); per-tenant widgets bind to per-tenant views.
- (c) Bridgeable-canonical widgets bind symbolically; resolved at activation.

### 7.3 Locks

**LOCKED 7a: Phase 1 bindings are tenant-scoped to the authoring user's tenant (option a).**

The BindingRef stores `saved_view_id` — a UUID. UUIDs are tenant-resolvable but not tenant-portable. The widget definition itself is shipped in a particular scope (platform / vertical / tenant per WB-1 substrate); Phase 1 ALL bindings must reference saved views in the same scope or rendering will fail.

For Phase 1, **all widget authoring occurs at the tenant scope** (per WB-4 investigation). Bridgeable-canonical widgets per the W-4 inheritance pattern are NOT yet authored via the widget builder — they ship via seed data with bindings declared manually by Bridgeable engineering.

This avoids the symbolic-binding rabbit hole at Phase 1.

**LOCKED 7b: Render-time resolution against rendering user's tenant only (option a).**

`resolveBinding` calls `executeSavedView(saved_view_id)`. The backend executor enforces tenant scope via the saved-view's own permissions model. If the rendering user's tenant doesn't own the view AND isn't in `shared_with_tenants`, the executor returns 403 → frontend renders placeholder.

This means: a widget bound to a saved view in tenant X, rendered for a user in tenant Y, will fail unless the view explicitly cross-tenant-shares with tenant Y. This IS the intended behavior — cross-tenant data flow stays gated through saved-view sharing, not implicit through widget binding.

**LOCKED 7c: Tier-1/Tier-2 inheritance for widgets is OUT OF SCOPE for WB-6.**

Per W-4 investigation, widget definitions DO have Tier-1 (platform) / Tier-2 (vertical) / Tier-3 (tenant) inheritance via the `scope` field. But Phase 1 widget *authoring* is tenant-scope-only (WB-4 Q-RISK acceptance). Cross-tier binding portability (a tenant-shipped widget being elevated to platform-canonical) is **DEFERRED** to a post-Phase-1 arc.

**LOCKED 7d: Cross-tenant Spaces consume saved-view sharing transparently (no new substrate).**

Per memory reference (Sunnycrest ↔ Hopkins cross-tenant Spaces): when a Space is shared across tenants, widgets embedded in that Space render via the rendering user's tenant context. The saved view those widgets bind to must explicitly share to the rendering tenant via `shared_with_tenants` OR be in the rendering tenant.

Phase 1 explicit non-goal: no automatic propagation of saved-view shares when a Space is cross-tenant-shared. Operator must explicitly share both the Space AND the underlying saved views. Friction acknowledged; revisit post-Phase-1.

### 7.4 Operator-validation-sensitive tag

Lock 7d (manual saved-view sharing in cross-tenant Spaces) is **TAGGED for operator validation** — first cross-tenant Space deployment may reveal that the friction blocks adoption. Mitigation candidate: a "share dependencies" affordance at the Space level that surfaces every saved view referenced by embedded widgets + offers single-click share-all. Tracked, not built.

### 7.5 Alternatives considered

- **Symbolic bindings** (option c above for both authoring + render time) — REJECTED for Phase 1. Symbolic indirection (e.g., `binding_key = "outstanding_invoices"` resolved per-tenant) requires a registry of canonical binding keys + per-tenant mapping rows + governance. Substrate to design later if cross-tier binding becomes a frequent operator pattern.
- **Per-BindingRef tenant_id** — REJECTED for Phase 1. Encoding tenant_id in the BindingRef makes the binding non-portable across tenants. Saved_view_id IS the tenant scope (via the view's `company_id`). Adding explicit tenant_id is redundant + tempts cross-tenant binding without sharing controls.

---

## 8. Area 7 — Backend substrate boundary

### 8.1 Audit

`/api/v1/saved-views/*` (existing — 8 endpoints at `routes/saved_views.py`):

| Endpoint | Verb | Path | Purpose | WB-6 reuse |
|---|---|---|---|---|
| List | GET | `/saved-views` | List views user can see; optional `?entity_type=` filter | Saved-view picker data source |
| Get | GET | `/saved-views/{id}` | Single view (verifies visibility) | Validation panel "view exists?" check |
| Create | POST | `/saved-views` | New view | Empty-state inline-creator path |
| Update | PATCH | `/saved-views/{id}` | Edit | (not WB-6) |
| Delete | DELETE | `/saved-views/{id}` | Soft-delete | (not WB-6) |
| Duplicate | POST | `/saved-views/{id}/duplicate` | Clone | (not WB-6) |
| Preview | POST | `/saved-views/preview` | Execute unsaved config | (not WB-6 — WB-5 candidate) |
| Execute | POST | `/saved-views/{id}/execute` | Execute saved view | **Binding resolution data source** |
| Entity types | GET | `/saved-views/entity-types` | Registry catalog (entities + fields) | **Field-path picker data source** |

### 8.2 Options

**Resolver service:**
- (a) Pure frontend resolver (TS) — fetch via existing endpoints, walk field_paths client-side.
- (b) Backend resolver service — accept BindingRef → return resolved value(s). New endpoint.
- (c) Frontend resolver for field_path; backend service for batch resolution (one call per widget, N atoms).

**Caching strategy:**
- (a) No caching (per saved-view executor canon: "saved-view results are live-queried every time" — `executor.py:31-33`).
- (b) Frontend session-scope cache keyed by saved_view_id (5-minute TTL).
- (c) Backend cache for read-heavy widget rendering paths.

**New endpoints:**
- (a) None — reuse existing.
- (b) `POST /api/v1/widget-runtime/resolve-bindings` — batch BindingRef resolution.
- (c) `GET /api/v1/saved-views/{id}/schema` — explicit field-path discovery endpoint distinct from entity-types catalog.

**Tenant scoping at resolver layer:**
- (a) Reuse existing executor layer (tenant scope baked in).
- (b) New endpoint enforces redundantly.

### 8.3 Locks

**LOCKED 8a: Pure frontend resolver consuming existing endpoints (option a).**

WB-6 adds zero new backend endpoints. The frontend:

1. `ComposedWidget` consumes BindingRef catalog from `composition_blob`.
2. For each unique `saved_view_id` referenced by `binding_type='field_path'` BindingRefs, calls `executeSavedView(saved_view_id)` once.
3. Resolves field_paths against `SavedViewResult` per Area 4 locks.

This is the minimum-change path. Backend executor's existing 150ms-p50 / 500ms-p99 BLOCKING gate covers performance.

**LOCKED 8b: No new caching layer for WB-6 (option a).**

`saved_views/executor.py:32-33` explicitly states "No caching. Saved-view results are live-queried every time." This is canonical. WB-6 preserves the canon.

Per-render-cycle de-duplication IS appropriate: if 3 atoms in the same widget reference the same saved_view_id, `executeSavedView` should be called once and the result memoized for that render. This is **component-local memoization, not session-level cache** — `useMemo` + AbortController, no LocalStorage. WB-5 may extend.

**LOCKED 8c: Reuse `/api/v1/saved-views/entity-types` as field-path discovery source (option a — no new endpoint).**

Per §2.1 audit, the existing `entity-types` endpoint already exposes per-entity `available_fields` with `field_name`, `display_name`, `field_type`, `enum_values`. Field-path picker queries this once on mount, filters to the chosen view's entity_type, populates the cascading combobox.

Reusing the existing endpoint avoids parallel paths + keeps the entity registry as single source of truth.

**LOCKED 8d: Tenant scoping enforced by existing executor (option a).**

The backend executor already enforces tenant scoping (`executor.py:88-118` + `crud.py` cross-tenant gating). WB-6 doesn't redundantly enforce; trusts the existing boundary.

### 8.4 Alternatives considered

- **Batch resolution endpoint** — REJECTED for Phase 1. Component-local memoization handles the duplicate-binding case. Batch endpoint becomes interesting when widgets become bandwidth-heavy (10+ saved-view-bound widgets on one page); not Phase 1.
- **Explicit `/schema` endpoint** — REJECTED. Entity-types catalog already provides field metadata; a dedicated /schema endpoint would duplicate.

---

## 9. Area 8 — WB-6 vs WB-5 substrate seam

### 9.1 Audit

Per `docs/investigations/2026-05-21-widget-builder-canvas.md:484`: "WB-4 ships before WB-5 (binding) which ships before WB-6 (saved-view substrate) — revised ordering: actually WB-6 (saved-view substrate) before WB-5 (binding)."

But the original WB investigation `5771fc0` sub-arc decomposition (§ Sub-arc decomposition at lines 795+) describes:
- WB-5 = "Atom binding + behavior + permissions"
- WB-6 = "Variant authoring + variant-driven atom visibility + surface availability"

These are inconsistent. The canvas investigation re-sequenced after the original. Per the prompt + current state, the WB-6 / WB-5 seam is:

**WB-6 (this investigation):**
- Binding picker UI in inspectors (replaces `BindingPlaceholderField`).
- field_path resolution runtime (replaces resolveBinding placeholder).
- iteration_mode runtime (replaces 1-mock-row in AtomRenderer).
- Backend API: NO new endpoints (per Lock 8a).
- Cross-tenant binding scope: Phase 1 = tenant-scope-only (per Lock 7a).
- Validation extensions in validators.py for binding shape (per Lock 5e).

**WB-5 (subsequent, gets own investigation):**
- Canvas preview wiring — composing widget builder renders real data from chosen saved view.
- Tenant context propagation in preview (operator authoring on their tenant; render uses tenant scope).
- Per-row iteration in preview (sample data shown).
- Error / loading states in preview canvas.
- Sample record selection per original WB Q-16 lock (`(c) primary + (b) fallback`).

**Original WB-5 scope items now redistributed:**
- "Atom binding" → split between WB-6 (the binding substrate + picker UI) and WB-5 (preview wiring).
- "Atom behavior" (action_kind invocation for buttons) → WB-7.
- "Permissions" (per-atom `required_permission`) → WB-7.

### 9.2 Seam clarification

| Concern | WB-6 | WB-5 |
|---|---|---|
| BindingRef shape | ✅ already exists | — |
| Binding picker UI in inspectors | ✅ | — |
| field_path resolution runtime | ✅ | — |
| iteration_mode runtime (per_row / single_summary / single_record) | ✅ | — |
| Mock 1-row repeater removal | ✅ | — |
| Canvas preview using real data | — | ✅ |
| Sample record selection in preview | — | ✅ |
| Error / loading states in preview canvas | — | ✅ |
| Validation extensions | ✅ | — |
| Empty saved-view-creator inline modal | ✅ | — |
| Tenant context in preview | — | ✅ |
| New backend endpoints | ❌ none | possibly preview-related |

### 9.3 Risk of leak

The risk: WB-6 ships binding picker UX but the canvas STILL renders mock data (since WB-5 wires preview). Operators authoring in WB-6 set up bindings but can't yet see them resolve in the canvas — only at render time when the widget is embedded in a Space.

**Mitigation:** WB-6's binding picker UX includes a small "Preview value" inline display in the inspector — when a BindingRef is set, the picker fetches the saved-view first row + shows the resolved value as a tooltip / inline preview. This is component-local + doesn't require WB-5 canvas changes. Substrate-level: the resolveBinding runtime is fully operational in WB-6; the canvas just doesn't consume it yet.

This is acceptable risk per the canvas investigation's locked sub-arc ordering. WB-5 is the immediate next sub-arc.

---

## 10. Area 9 — Phase 1 scope boundaries

### 10.1 Ships in WB-6

1. **Binding picker UI** — combobox in inspector primitives, replacing `BindingPlaceholderField`. Cascading saved-view → field-path → iteration-mode (auto-inferred). 4 atom inspectors get the picker wired (text_label, value_display, status_badge, image, plus the existing repeater_atom).
2. **field_path resolution runtime** — dot-notation + numeric-segment array indexing, per Area 3 locks. Replaces resolveBinding placeholder string at `frontend/src/lib/widget-builder/runtime/resolveBinding.ts`.
3. **iteration_mode runtime** — `AtomRenderer.tsx` repeater_atom branch swapped from 1-mock-row to real saved-view row iteration.
4. **Validation extensions** — `backend/app/services/widget_definitions/validators.py` extended per Lock 5e.
5. **Inline saved-view-creator** — empty-state affordance per Lock 6f.
6. **Component-local memoization** — `useMemo` + AbortController for the per-render `executeSavedView` calls.
7. **Validation panel surfacing** — extended chrome for "Binding references deleted saved view" + "iteration_mode mismatch" + "field_path missing" errors.
8. **In-inspector preview value tooltip** — per §9.3 mitigation.
9. **Telemetry signal** — count of saved-view-bound widgets per tenant (for post-staging operator-validation tagged decisions).

### 10.2 Defers to WB-5

- Canvas preview wiring to live data.
- Sample record selection.
- Error / loading states in preview canvas.
- Per-row preview rendering.

### 10.3 Defers to WB-7+ / Phase 2

- Expression bindings (`row.subtotal + row.tax`) — confirmed deferred per original WB Q-7.
- Computed fields — deferred per Lock 4e.
- Real-time data updates (WebSocket-driven refresh; refresh_interval_seconds polling stays per Q-15) — Phase 2.
- Variant-specific binding overrides — Phase 2 (out-of-scope per original WB).
- Multi-binding atoms (one atom referencing 2+ bindings) — Phase 2.
- Cross-tier binding portability (Tier-1 platform widget binding to tenant view) — deferred per Lock 7c.
- Action invocation for buttons (action_kind wiring) — WB-7.

### 10.4 Explicit non-goals

- New backend endpoints for binding resolution.
- Frontend session-scope caching.
- Cross-tenant symbolic bindings.
- Saved-view substrate modifications (registry, executor, schemas).

---

## 11. Area 10 — Architectural risks + mitigations

### Risk 1 — vault_item metadata_json field-path discoverability gap

`vault_item` is the most-used entity_type in seeded views (per `seed.py` audit — production board, events, calendar). Its rows carry `metadata_json` containing entity-specific fields that are NOT enumerated in `registry.available_fields`. Field-path picker can't surface them.

**Severity:** HIGH for Phase 1. Many Phase 1 widgets WILL want to bind to vault_item fields stored in metadata_json.

**Mitigations (ranked):**
- (a) Best-effort introspection — frontend samples first row of saved-view result, enumerates keys, offers them in the picker beneath the registered fields. Phase 1 viable. Risk: schema variation across rows.
- (b) Backend extension to registry — vault_item entity's `available_fields` extended to include common metadata_json paths per `item_type`. Higher cost; saved-view-registry edit.
- (c) Free-text fallback alongside picker — operator types path manually if picker doesn't surface it. Phase 1 simplest.

**LOCKED MITIGATION: (c) primary + (a) future improvement.** Phase 1 ships free-text field-path fallback with validation against the saved-view's first-row sample at picker time. WB-6 build includes a small "Type a custom field path" affordance beneath the picker. Path validation against actual data happens at resolution time; placeholder rendered on miss. Risk acknowledged + bounded.

### Risk 2 — Saved view shape change breaks bindings post-Publish

Operator publishes widget bound to `invoice.total`. Tenant admin edits the saved view, removes `total` from columns. Widget continues binding to `total`. Either (a) value still resolves (because executor returns all entity fields regardless of column config — VERIFIED at `executor.py:142-145`); or (b) value disappears.

**Audit verification:** `executor.py:144` `rows = [entity_meta.row_serializer(r) for r in rows_orm]`. The row_serializer emits the entity's full canonical field set, NOT the saved-view-config column subset. **Saved-view column-config affects PRESENTATION (which columns to display in table mode), NOT data emission.** Binding to `invoice.total` survives a column-config edit.

**Risk REDUCED.** Saved-view shape changes that DO affect bindings:
- Entity registry changes (a field removed from `registry.available_fields`).
- Saved-view filters narrowing the visible rows.
- Saved-view DELETE.

**Mitigation:** validation panel surfaces these at authoring time. Runtime renders placeholder. Acceptable risk for Phase 1.

### Risk 3 — Cross-tenant binding silent failure

Widget authored in tenant A bound to saved view in tenant A. Widget embedded in cross-tenant Space + rendered for tenant B user. Saved view not shared → executor returns 403 → resolveBinding returns null → atom renders placeholder.

**Severity:** MEDIUM. Confusing for operators who shared the Space but forgot the underlying views.

**Mitigation:** per Lock 7d operator-validation-sensitive tag. WB-6 logs a console.warn + telemetry signal at runtime when this happens. Frontend renders placeholder with a hovercard "Binding unavailable: view not shared with this tenant." Substrate-level remediation (Space-level share-dependencies affordance) deferred.

### Risk 4 — iteration_mode mismatch silent failure post-Publish

Operator publishes widget where a non-repeater atom references a per_row binding. WB-4b validator currently doesn't catch this (only the repeater→per_row direction is enforced). Operator can author + publish + widget renders empty/broken.

**Severity:** MEDIUM for Phase 1.

**Mitigation:** Lock 5e extends validators.py with bidirectional checks. Build dispatch verifies extension lands in WB-6 commit.

### Risk 5 — Picker UX cardinality blow-up

A tenant with 100+ saved views could overwhelm the combobox.

**Severity:** LOW for Phase 1. Tenant cardinality is empirically <50 saved views per tenant (seed templates + a handful of user-created).

**Mitigation:** combobox already filterable. Pagination not needed for Phase 1. Revisit at 100+ view cardinality.

### Risk 6 — Frontend bundle-size increase from inline saved-view-creator

Empty-state inline-creator (Lock 6f) opens existing `/saved-views/new` route in a modal/slide-over — IF that route component is lazily loaded, no bundle increase. IF eagerly imported, +X KB to admin bundle.

**Severity:** LOW. Mitigation: ensure dynamic import. Build dispatch verifies.

### Risk 7 — saved-view-id deletion creates orphaned BindingRef catalog entries

Saved view DELETED → BindingRef still references the id → catalog drift. Per current schema there's no FK constraint between widget_definitions and vault_items.

**Severity:** LOW. Acceptable — runtime renders placeholder; operator can re-bind.

**Mitigation:** none required Phase 1. Future cleanup could enumerate orphaned BindingRefs as a tenant-admin diagnostic.

---

## 12. WB-6 sub-arc execution plan

### Proposed scope

WB-6 = "binding substrate activation" = the 9 deliverables in §10.1.

### Files touched (estimate)

**Frontend (~9 files; ~700 LOC):**
- `frontend/src/lib/widget-builder/runtime/resolveBinding.ts` — REWRITE (placeholder string → real resolution). +120 LOC net.
- `frontend/src/lib/widget-builder/runtime/AtomRenderer.tsx` — modify repeater branch + data fetch wiring. +60 LOC net.
- `frontend/src/lib/widget-builder/runtime/ComposedWidget.tsx` (audit + likely modify) — `executeSavedView` calls + memoization. +80 LOC net.
- `frontend/src/lib/widget-builder/runtime/useBindingData.ts` (NEW) — hook for component-local memoized fetch. +90 LOC.
- `frontend/src/bridgeable-admin/components/widget-builder/inspectors/inspector-primitives.tsx` — REMOVE `BindingPlaceholderField` placeholder, ADD `BindingPicker` combobox primitive. +150 LOC net.
- `frontend/src/bridgeable-admin/components/widget-builder/inspectors/BindingPicker.tsx` (NEW) — combobox + cascading field picker + iteration_mode auto-inference. +180 LOC.
- `frontend/src/bridgeable-admin/components/widget-builder/inspectors/AtomInspectorDispatch.tsx` — swap 3 placeholder call sites → BindingPicker. +30 LOC net.
- `frontend/src/lib/widget-builder/validation/` — frontend mirror of validator extensions (if extant pattern). +50 LOC.
- 1-2 test files for resolveBinding + BindingPicker. +120 LOC.

**Backend (~3 files; ~150 LOC):**
- `backend/app/services/widget_definitions/validators.py` — add 5 binding-shape checks per Lock 5e. +80 LOC net.
- `backend/tests/test_widget_composition_validator.py` (or equivalent) — coverage for new checks. +60 LOC.
- No new endpoints, no new migrations, no new service files.

**Total estimate:** ~850 LOC; 12 files touched (5 new, 7 modified).

### Sub-arc steps

1. **Step 1 — Backend validator extensions.** Pure additive checks; safe-to-ship without frontend changes.
2. **Step 2 — Frontend useBindingData hook + resolveBinding rewrite.** Runtime substrate.
3. **Step 3 — BindingPicker primitive.** Authoring UI substrate.
4. **Step 4 — AtomInspectorDispatch wiring.** Swap placeholders for real picker.
5. **Step 5 — ComposedWidget + AtomRenderer iteration wiring.** Removes 1-mock-row stub.
6. **Step 6 — Validation panel chrome extensions** per Lock 6e.
7. **Step 7 — Inline saved-view-creator empty-state** per Lock 6f.
8. **Step 8 — Per-binding in-inspector preview tooltip** per §9.3 mitigation.
9. **Step 9 — Tests + Playwright smoke** for picker + resolution end-to-end.

Single sub-arc; no further splits proposed. Build dispatch can sequence 1-9 sequentially.

### Test substrate

Per FF-series canonical 3-layer pattern:
- **JSDOM behavioral**: BindingPicker open + select + cascade. resolveBinding dot-notation. iteration_mode auto-inference logic.
- **Playwright pointer-event**: complete authoring flow — open widget builder → add atom → bind to saved view → field path → publish → embed in space → verify renders real data.
- **Source-shape regression gate**: assertion that `BindingPlaceholderField` no longer in code paths; assertion that `[bound:` placeholder strings no longer surface at runtime.

### Migration head

Unchanged at `r106_widget_definitions_published_blob`. WB-6 is purely additive at the schema level.

### Canon state

Unchanged at 42. WB-6 may surface canon candidates during build; not filed in this investigation.

---

## 13. Operator-validation-sensitive locks tagged

Per DECISIONS entry 35 (Investigation-time UX locks can be refined by operator experience):

| Lock | Concern | Trigger for revisit |
|---|---|---|
| 6a — Combobox picker | UX density at 50+ views | Operator authoring throughput on staging |
| 6c — Cascading field picker | Nested-path operators may want JSONPath | Free-text fallback (Risk 1) adoption rate |
| 6f — Inline saved-view-creator empty state | Operator may want to "abandon widget, go to saved-view-creator first" rather than modal | Operator feedback post-staging |
| 7d — Manual saved-view sharing in cross-tenant Spaces | First cross-tenant Space deployment friction | Sunnycrest ↔ Hopkins pilot |

These are not load-bearing; revisit if friction surfaces.

---

## 14. Process canon candidates surfaced (NOT filed)

Per investigation methodology, candidates surfaced for future canon-update arc — NOT filed here:

1. **Substrate audits should enumerate cross-tier inheritance shape EVEN WHEN audit confirms substrate exists.** This investigation surfaced that saved-view substrate is mature BUT does NOT have its own Tier-1/Tier-2 inheritance shape (vs. widget_definitions which does). Distinct from "substrate exists / doesn't exist." Audits should answer both.
2. **UI-unexposed-but-functional substrate is a third state.** Cross-tenant masking is fully-built but UI-unexposed (per `crud.py:19-21`). Investigations should flag this state explicitly — neither "built" nor "missing" — because it changes what's downstream-consumable. Candidate name: "Built-but-dormant substrate."
3. **Sub-arc ordering revision in mid-arc-investigation should update the investigation it inverted.** The canvas investigation (`docs/investigations/2026-05-21-widget-builder-canvas.md:484`) re-sequenced WB-5/WB-6 ordering from the original WB investigation but didn't update the original's §Sub-arc decomposition. Future investigations should annotate the prior investigation in-tree OR include a "supersedes line X-Y in prior investigation Z" note.
4. **Phase 1 scope-bounding decisions that defer cross-tier portability should be load-bearing-flagged.** Lock 7c (Tier-1/Tier-2 inheritance for widgets OUT OF SCOPE) was easy to LOCK because Bridgeable engineering hand-authors Tier-1 widgets via seed data today. But once a tenant promotes a tenant-scoped widget to vertical-default or platform-canonical, the substrate gap surfaces. Canon could capture "Phase-1 OUT-OF-SCOPE decisions that require substrate work to ever ship" as a distinct category.

---

## 15. Architectural surprises during investigation

1. **Saved-view substrate is significantly more mature than the original WB investigation acknowledged.** 3,235 LOC of service layer, 8 endpoints, 8 entity types, 25+ seeded templates per role, cross-tenant masking already built. The original WB investigation `5771fc0` referenced "saved views" without auditing actual state. This investigation closes that gap.
2. **Cross-tenant masking is built-but-dormant.** Per §2.1 audit, `Permissions.cross_tenant_field_visibility.per_tenant_fields` is full backend infrastructure with executor + tests, but no UI surfaces it. This is a "Built-but-dormant substrate" state worth flagging as canon candidate (§14.2).
3. **BindingRef symmetry is clean (no drift).** Unlike per-atom Config classes (8 of 9 atom kinds had drift discovered in WB-4b), BindingRef stayed clean across all three layers. WB-4b canon candidate ("symmetry audit at substrate boundaries") could be elevated to formal canon after one more clean audit.
4. **`vault_item` field-path discoverability gap (Risk 1) is the largest hidden complexity.** `vault_item` is the most-used entity in seeded views, and its `metadata_json` field-shape is NOT enumerated in entity registry. WB-6 mitigates via free-text fallback (Lock; §11).
5. **Saved-view-config column subset affects PRESENTATION, NOT data emission.** Audit revealed `executor.row_serializer` emits the full entity field set regardless of `TableConfig.columns`. This DE-RISKS Risk 2 (saved-view shape change post-Publish) significantly.
6. **Tier-1/Tier-2 saved-view inheritance doesn't exist as a substrate shape.** Saved views are tenant-scoped only; Bridgeable-canonical templates ship via per-user seeding, not via a platform-level row that tenants inherit from. Distinct from widget_definitions which DO have a Tier-1 scope field. The asymmetry is intentional + load-bearing for Lock 7c.

---

## 16. Closing summary

WB-6 substrate is ready to dispatch. Saved-view substrate (Area 1) is mature; BindingRef triad (Area 2) is symmetric; field_path semantics (Area 3) + iteration_mode runtime (Area 4) + binding picker UX (Area 5) + cross-tenant scope (Area 6) + backend boundary (Area 7) all locked with clear reasoning + enumerated alternatives. WB-6 vs WB-5 seam (Area 8) cleanly delineated. Phase 1 scope (Area 9) bounded. Risks (Area 10) characterized with locked mitigations.

WB-6 build dispatches against ~850 LOC across ~12 files. Single sub-arc, 9 sequential steps, migration head unchanged, canon state unchanged. Backend zero-new-endpoints. No prerequisite substrate work required before dispatch.

Operator-validation-sensitive tags filed for staging revisits (§13). Process canon candidates surfaced for future filing (§14). Architectural surprises documented (§15).

---

## Appendix — file references cited

**Backend substrate:**
- `backend/app/schemas/widget_composition.py:101-122` (BindingRef + IterationMode Pydantic)
- `backend/app/services/saved_views/types.py:1-547` (SavedViewConfig, SavedView, SavedViewResult, Permissions, CrossTenantFieldVisibility)
- `backend/app/services/saved_views/executor.py:1-449` (execute, masking, aggregation)
- `backend/app/services/saved_views/crud.py:1-458` (CRUD + visibility gating)
- `backend/app/services/saved_views/registry.py:1-717` (8 entity types + FieldMetadata + allowed_verticals)
- `backend/app/services/saved_views/seed.py:1-753` (SeedTemplate, SEED_TEMPLATES dict, _basic_list/_basic_table/_basic_kanban factories)
- `backend/app/api/routes/saved_views.py:1-453` (8 endpoints)
- `backend/app/services/widget_definitions/validators.py:149-250` (binding validation)
- `backend/app/models/vault_item.py:22-100` (storage)
- `backend/alembic/versions/r32_saved_view_indexes.py`, `r62_cleanup_cross_vertical_saved_views.py`, `r106_widget_definitions_published_blob.py`

**Frontend substrate:**
- `frontend/src/lib/widget-builder/types/composition-blob.ts:61-72` (BindingRef + IterationMode TS)
- `frontend/src/lib/widget-builder/runtime/resolveBinding.ts:1-55` (Phase 1 placeholder)
- `frontend/src/lib/widget-builder/runtime/AtomRenderer.tsx:186-228` (repeater iteration scaffolding)
- `frontend/src/bridgeable-admin/components/widget-builder/inspectors/inspector-primitives.tsx:178-203` (BindingPlaceholderField)
- `frontend/src/bridgeable-admin/components/widget-builder/inspectors/AtomInspectorDispatch.tsx:404,731,854` (3 placeholder call sites)
- `frontend/src/components/saved-views/SavedViewWidget.tsx` (hub embed; reference for ComposedWidget pattern)
- `frontend/src/services/saved-views-service.ts` (client; reused, not modified)

**Canon + investigation references:**
- DECISIONS.md entry 22 (Monitor vs Decide), entry 26 (operator-validation gates), entry 35 (UX locks refinable post-staging)
- `docs/investigations/2026-05-21-widget-builder.md` (original investigation, Q-7 / Q-11 / Q-12 / Q-13 / Q-14 / Q-15 / Q-16 locks)
- `docs/investigations/2026-05-21-widget-builder-canvas.md:484` (WB-5 / WB-6 sequence revision)
- BRIDGEABLE_MASTER §3 (Three primitives), §9.4 (widgets are Vault views with chrome), §3.25 (saved-view vertical-scope inheritance amendment)

**Recent commits:**
- `3d39598` WB-4b (HEAD)
- `3680950` WB-4a
- `7b9e19a` WB-4 investigation
- `4b6b173` WB-3
- `95ddd16` WB-2
- `7eb1280` WB-1
- `5771fc0` WB original investigation
