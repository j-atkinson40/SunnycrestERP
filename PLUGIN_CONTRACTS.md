# PLUGIN_CONTRACTS.md — Canonical Plugin Category Contracts

**Established**: 2026-05-11 (Phase R-8.y.a — first of four R-8.y documentation sub-arcs)
**Scope**: Bridgeable's explicit plugin categories — input/output contracts, guarantees, failure modes, configuration shape, registration mechanism, current implementations.

---

## Purpose

This document is the canonical contract reference for Bridgeable's plugin categories. A "plugin category" is a substrate that admits multiple implementations behind a stable contract — adding a new implementation is registration, not engine surgery.

**Who reads this:**
- Developers adding a new implementation to an existing category (read the section for that category)
- Developers proposing a new plugin category (read the cross-category patterns appendix; new categories follow the same 8-section structure)
- Sonnet sessions building against an existing substrate (cite the relevant section to ground architectural choices in the canonical contract)
- The Plugin Registry Browser (R-8.y.d) — surfaces these contracts in the admin UI; the document precedes the surface

**Relationship to other canonical specs:**
- `CLAUDE.md §4` describes each category's architectural role; this document specifies the contract. CLAUDE.md is the *why*; this document is the *what*.
- `BRIDGEABLE_MASTER.md` describes platform vision and primitive design; this document compiles the substrate contracts that vision rests on.
- `PLATFORM_DESIGN_THESIS.md` / `PLATFORM_QUALITY_BAR.md` / `DESIGN_LANGUAGE.md` describe design canon; this document is structural canon.

**When to update:**
- When a new plugin category emerges (add a section here BEFORE shipping the implementation; the contract is the design surface)
- When a category's contract changes (canonical contract change requires same-commit update here + in the source files)
- When R-8.y.b / R-8.y.c ship (partial + implicit contract documentation extends this document)
- When R-9 promotes the workflow node type if/elif chain to a registry (it joins this document at that time)

---

## Table of Contents

1. [Document conventions](#document-conventions)
2. [Intake adapters](#1-intake-adapters)
3. [Focus composition kinds](#2-focus-composition-kinds)
4. [Widget kinds](#3-widget-kinds)
5. [Document blocks](#4-document-blocks)
6. [Theme tokens](#5-theme-tokens)
7. [Workshop template types](#6-workshop-template-types)
8. [Composition action types](#7-composition-action-types)
9. [Accounting providers](#8-accounting-providers)
10. [Email providers](#9-email-providers)
11. [Playwright scripts](#10-playwright-scripts)
12. [Cross-category patterns appendix](#cross-category-patterns-appendix)

---

## Document conventions

**The 8-section contract structure.** Each plugin category gets the same 8 sub-sections in the same order. This is canonical — every new category added to this document follows the structure verbatim.

| Sub-section | What it documents |
|---|---|
| **Purpose** | What kind of plugin, what problem it solves, why factored as a category rather than hard-coded behavior. 1-2 paragraphs. |
| **Input Contract** | The shape consumers pass in. Pydantic class, dataclass, dict schema, or method signature. Required vs optional fields. File:line citations to the canonical type definition. |
| **Output Contract** | The shape implementations return. Same precision as input. Downstream callers depend on this shape; changes are coordinated, not unilateral. |
| **Guarantees** | Idempotency. Transactional behavior. Tenant isolation. Concurrency. Timeout. Retry policy. Whether failures propagate or get swallowed. |
| **Failure Modes** | Canonical exception types. Whether they're translated to HTTP status. Retryable vs non-retryable. Best-effort wrappers vs hard failures. |
| **Configuration Shape** | If applicable: the table/column structure or JSONB shape carrying per-instance config. Scope cascade applicability (`platform_default` / `vertical_default` / `tenant_override`). Validation patterns. Some categories have N/A here — the contract is fully code-defined with no per-instance configuration. |
| **Registration Mechanism** | How a new implementation enters the registry. `register_*` API, class subclass, module-level dict, side-effect import, etc. Where the registry lives. Whether registration is idempotent. |
| **Current Implementations** | Each registered plugin: name + file:line + brief description. Implementations that diverge from the canonical contract get flagged with a divergence note tracking the future migration. |
| **Cross-References** | Related categories. Patterns inherited from. CLAUDE.md sections that describe the architectural role. Future migration arcs that touch this category. |

**Divergence-tracking convention.** When an implementation's actual code diverges from what the canonical contract says it should be, the divergence is flagged in **Current Implementations** with a brief note. R-8.y.a documents contracts as-they-should-be; resolving divergences is future migration work (separate arcs). The contract is the target; the divergence note is the gap.

**File:line citations.** Every contract point that names a type, function, or invariant should cite `path/to/file.py:line` where the canonical definition lives. Documentation that drifts from source is a defect; citations make drift detectable.

---

## 1. Intake adapters

### Purpose

Intake adapters ingest external messages, form submissions, and file uploads into Bridgeable's canonical entity model + classification cascade. Email, form, and file are the three canonical adapter types at September 2026 scope. Future adapters (SMS-ingest, phone-call-completion, native mobile capture) extend the same canonical contract — `adapter.ingest(db, *, tenant_config, source_payload) → canonical_record` — without engine changes.

The category exists so the **classification cascade is source-agnostic**: Tier 1 deterministic rules + Tier 2 LLM taxonomy + Tier 3 LLM registry selection all operate on the canonical record produced by any adapter, regardless of source mechanism. Adding a new intake source registers an adapter; the cascade absorbs it.

### Input Contract

Each adapter declares a typed source-payload dataclass:

- **Email**: `ProviderFetchedMessage` at `backend/app/services/email/providers/base.py:63` — sender + recipients + subject + body_html + body_text + attachments + raw_payload
- **Form**: `FormSubmissionPayload` at `backend/app/services/intake/form_adapter.py:42` — submitter metadata + submitted_data dict matching `IntakeFormConfiguration.form_schema`
- **File**: `FileUploadPayload` (in `backend/app/services/intake/file_adapter.py`) — uploader metadata + R2 storage key + content_type + size_bytes

Tenant context is resolved separately via `intake/resolver.py::resolve_form_config` / `resolve_file_config` walking the three-scope chain before adapter dispatch.

### Output Contract

Adapter ingest produces a canonical record persisted in the adapter's record table:
- Email: `EmailMessage` row in `email_messages`
- Form: `IntakeFormSubmission` row in `intake_form_submissions`
- File: `IntakeFileUpload` row in `intake_file_uploads`

Per-row denormalized classification outcome (R-6.2a decision): each record table carries `classification_tier` + `classification_workflow_id` + `classification_workflow_run_id` + `classification_is_suppressed` + `classification_payload` columns; cross-source audit unification deferred to R-6.x hygiene.

### Guarantees

- **Tenant isolation enforced from tenant_config**: every adapter resolves tenant identity from configuration; no implicit tenant inference from payload alone.
- **Idempotency via natural key**: email by `provider_message_id`; form by `submission_id`; file by `r2_storage_key`. Re-ingest of the same payload no-ops at the natural-key boundary.
- **Cascade is best-effort post-persist**: classification failure NEVER blocks record persistence. The record is recorded; classification is replayable via admin endpoint.
- **Synchronous classification within ingest** (Phase 8b cash_receipts precedent): R-6.1a's three-tier cascade runs synchronously in the ingest call; <2s p95 acceptable.

### Failure Modes

- `IntakeConfigNotFound` (`intake/resolver.py:36`) → HTTP 404. Slug not resolvable for tenant.
- `IntakeValidationError` (`intake/resolver.py:43`) → HTTP 400 with `details` dict. Field-level validation failure (missing required, malformed email, etc.).
- Classification cascade failure → logged, never raised. Record persists; cascade returns `unclassified` outcome surfaced in `email_unclassified_triage` queue.
- R2 upload failure on file adapter → degraded with logged warning; runtime callers retain hard-error contract per CLAUDE.md §14 R-6.2a.1.

### Configuration Shape

Per-adapter configuration tables (R-6.2a architectural call — not a unified god-table):

- `email_accounts` (provider OAuth state + sync state)
- `intake_form_configurations` (`form_schema` JSONB + 7 field types: text, textarea, email, phone, date, select, checkbox)
- `intake_file_configurations` (`allowed_content_types` JSONB + `max_file_size_bytes` + `r2_key_prefix_template`)

**Three-scope inheritance at READ time** for all three: `tenant_override → vertical_default → platform_default`. First match wins. Per `app/services/intake/resolver.py:61` for forms + `:129` for files. Migration: `r94_intake_adapter_configurations`.

### Registration Mechanism

Adapters are registered indirectly via:
- The classification cascade's `adapter_type` discriminator (`'email' | 'form' | 'file'`) on `tenant_workflow_email_rules` (CHECK constraint enumerates the canonical 3 values upfront so downstream cascade extensions inherit substrate without CHECK migration)
- Service-layer entry points (`form_adapter.submit_form`, `file_adapter.complete_file_upload`, email ingestion `Step 12 hook`)
- Tier 1 / Tier 2 / Tier 3 LLM prompts renamed `intake.classify_into_*` (post-R-6.2a) parameterized by `adapter_type` template variable

There is no `register_adapter(...)` API today — adding a new adapter is a substrate extension across model + service + dispatch + prompt-template variable. The canonical contract is the canonical extension surface.

### Current Implementations

- **Email** (`app/services/classification/`) — R-6.1a; full three-tier cascade; classification synchronous on ingest Step 12 hook in `app/services/email/ingestion.py`
- **Form** (`app/services/intake/form_adapter.py:99`) — `submit_form(db, *, config, submitted_data, submitter_metadata, tenant_id)`; validates 7 field types; cascade fires via `classify_and_fire_form`
- **File** (`app/services/intake/file_adapter.py`) — `presign_file_upload` + `complete_file_upload` with R2-direct PUT; cascade fires via `classify_and_fire_file`

### Cross-References

- **CLAUDE.md §4 "Intake Adapter Contract (R-6.2a)"** — canonical architectural role
- **CLAUDE.md §14 R-6.2a entry** — substrate canon + 65 tests + path-based portal hosting
- **CLAUDE.md §14 R-6.1a entry** — three-tier classification cascade canon
- **Document Blocks (§4 below)** — parallel "registry as canonical extension point" pattern
- **Workshop template types (§6 below)** — parallel "configuration-as-data, code-as-substrate" discipline
- **Future**: phone-call-completion + SMS-ingest cascade extension per CLAUDE.md §3.26.18 + §3.26.17 canon

---

## 2. Focus composition kinds

### Purpose

Focus compositions specify what's on a Focus canvas — placements of widgets / sub-Focuses / panels arranged on a 12-column grid. The `kind` discriminator (`focus` | `edge_panel`) extends compositions to surfaces beyond the standalone Focus primitive: a tenant's edge panel is the same composition substrate, kind-discriminated for shape.

Adding a new `kind` value is the canonical extension mechanism for new composition-driven surfaces. Per R-5.0 (May 2026), the substrate proved at depth — `edge_panel` reuses the entire composition resolver + write-side-versioning + scope-cascade infrastructure with no parallel architecture.

### Input Contract

`FocusComposition` ORM at `backend/app/models/focus_composition.py:62`:
- `kind: str` — `'focus'` | `'edge_panel'` (CHECK-constrained; r91 extends with new values via CHECK migration)
- `focus_type: str` — discriminator within kind (e.g. `'scheduling'`, `'default'` for edge panels)
- `scope` + `vertical` + `tenant_id` — three-scope inheritance position
- `rows: list[Row]` (R-3.0 shape, JSONB) — sequence of rows where each row declares its own `column_count` (1-12) and carries its `placements`
- `pages: list[Page] | null` — multi-page composition for `kind='edge_panel'`; null for `kind='focus'`
- `canvas_config: dict` — cosmetic settings (`gap_size`, `background_treatment`, `padding`)
- `version` + `is_active` — write-side versioning

### Output Contract

`resolve_composition(db, *, focus_type, vertical, tenant_id, kind)` at `backend/app/services/focus_compositions/composition_service.py` returns `ResolvedComposition`:
- `focus_type` + `vertical` + `tenant_id` + `kind`
- `source: "platform_default" | "vertical_default" | "tenant_override" | None`
- `source_id` + `source_version`
- `rows: list[Row]` (or `pages` for edge panels)
- `canvas_config`

`None` source signals fall-through (no composition at any scope; render hard-coded layout).

### Guarantees

- **First match wins at READ time** — a composition is a complete layout, not a partial overlay. Per CLAUDE.md §4 "Focus Composition Layer" canonical merge semantics.
- **Write-side versioning** — every save deactivates the prior active row at the same canonical tuple + inserts a new row with `version + 1`. Partial unique on `is_active=true` enforces "at most one active per tuple."
- **`kind` validation at substrate**: `_validate_kind` rejects unknown values; r91 CHECK constraint enforces at DB layer.
- **Empty `pages: null` for `kind='focus'`** + **non-empty `pages` for `kind='edge_panel'`** — `_validate_pages` raises on mismatch.

### Failure Modes

- `composition_service` raises typed errors translated to HTTP 400 at the admin API boundary. Service-layer validation rejects malformed placements, out-of-bounds grid, duplicate `placement_id`s, kind/pages mismatches.
- Resolution falls through cleanly when no composition exists — returns `source=None` rather than 404.

### Configuration Shape

`focus_compositions` table per migration `r84_focus_compositions` extended by `r91_compositions_kind_and_pages` (May 2026). One row per `(scope, vertical?, tenant_id?, kind, focus_type, version)`. Active rows enforced unique via partial index on `is_active=true`.

**Three-scope cascade** ✓ canonical (CLAUDE.md §4 reference). New `kind` values extend the CHECK constraint via migration; current canonical values: `'focus'`, `'edge_panel'`.

### Registration Mechanism

`kind` is a string discriminator with DB CHECK enumeration — not a `register_kind(...)` API. Adding a new kind requires (a) migration extending the CHECK constraint, (b) `_validate_kind` extension in `composition_service`, (c) frontend renderer support per surface. The canonical pattern is documented in CLAUDE.md §4 "Focus Composition Layer" + R-5.0 entry showing the `edge_panel` extension path.

### Current Implementations

- **`kind='focus'`** — standalone Focus primitive (scheduling, arrangement_scribe, triage_decision Focuses); rows-based; `pages` always null
- **`kind='edge_panel'`** — multi-page tenant edge panel substrate (R-5.0); `pages` non-empty array; `rows` array empty at top level

### Cross-References

- **CLAUDE.md §4 "Focus Composition Layer"** — canonical architectural role + accessory-layer pattern
- **CLAUDE.md §14 R-3.0 entry** — rows-shape data model
- **CLAUDE.md §14 R-5.0 entry** — edge panel substrate emerging via `kind` discriminator
- **Widget kinds (§3 below)** — composition consumes widget definitions via `placement.component_kind='widget' + component_name`
- **Theme tokens (§5 below)** — composition's `prop_overrides.tokenReference` props bind to theme tokens

---

## 3. Widget kinds

### Purpose

Widgets are the platform's canonical rendering primitive for compact entity surfaces — kanban cards, dashboard cards, briefing summaries, Pulse pieces, peek panels. Every widget declares variants (Glance / Brief / Detail / Deep), supported surfaces (`spaces_pin`, `dashboard_grid`, `pulse_grid`, `peek_inline`, `focus_canvas`), and the 5-axis visibility filter (permission + module + extension + vertical + product_line).

The category exists so a single widget definition surfaces uniformly across every consuming surface, with per-surface presentation chrome handled at the canvas/renderer layer.

### Input Contract

Each widget definition is a dict entry in `WIDGET_DEFINITIONS` at `backend/app/services/widgets/widget_registry.py:17`. Required keys:
- `widget_id: str` — globally unique (e.g. `"todays_services"`, `"vault_schedule"`)
- `title` + `description` — operator-facing
- `page_contexts: list[str]` — surfaces this widget can mount (e.g. `["ops_board", "home"]`)
- `default_size: str` + `min_size` + `supported_sizes: list[str]` — grid dimensions
- `category` + `icon` + `default_enabled` + `default_position`
- `variants: list[Variant]` (W-1 extension) — per W-3a variant declarations
- `default_variant_id` + `supported_surfaces` + `default_surfaces`
- `required_vertical: list[str] | "*"` — axis 4 (Phase W-1)
- `required_product_line: list[str] | "*"` — axis 5 (Phase W-3a)
- `required_permission` + `required_module` + `required_extension` — axes 1-3

### Output Contract

Backend `widget_service.get_available_widgets(db, tenant_id, user, page_context)` at `backend/app/services/widgets/widget_service.py` returns the filtered list of definitions visible to the caller. Frontend widget renderer consumes the definition + per-instance config; output is the rendered surface chrome.

Per-widget data services (e.g. `today_widget_service.py`, `vault_schedule_service.py`, `anomalies_widget_service.py`) provide the runtime data payload separately; the widget definition is metadata, not data.

### Guarantees

- **5-axis AND-wise filter**: a widget renders only if every axis passes. Per W-3a CLAUDE.md §14 entry.
- **`required_vertical: ["*"]`** = cross-vertical (matches every tenant).
- **`required_product_line: ["*"]`** = cross-line (matches regardless of activated TenantProductLine rows).
- **Tenant isolation** at the data-service level: each widget data service explicitly filters by tenant; widget definitions are platform-global metadata.

### Failure Modes

- Unknown widget_id at render time → graceful fallback (renderer logs + skips); never raises to the consuming surface
- Missing data service → widget renders empty state (`EmptyState` primitive per Phase 7 polish)
- Permission gate failure → widget filtered out at `get_available_widgets` boundary; caller never sees the definition

### Configuration Shape

`widget_definitions` table (43 rows as of Phase W-3d + Communications Layer extensions). Per-user customization via `user_widget_layouts` table (per-user widget arrangement persistence). Tenant-level customization is via the canonical 5-axis filter (data-driven), not per-tenant widget config overlay.

**No multi-scope cascade** — widget definitions are platform-only; per-tenant variation is filter-driven, not override-driven.

### Registration Mechanism

`WIDGET_DEFINITIONS` is a module-level list in `widget_registry.py`. New widgets append to the list + ship a data service + ship a frontend renderer. Seeding via `seed_widget_definitions(db)` on startup uses `INSERT ... ON CONFLICT DO UPDATE` on system-owned columns (so adding `page_contexts=["home", "ops_board"]` to an existing widget definition propagates to all tenants on next deploy without a migration).

No `register_widget(...)` API — registration is data append. The pattern works because widget count (~50) is small enough that a list is canonical.

### Current Implementations

43+ widgets across categories (count as of R-8.y.a):
- **Operations Board**: `todays_services`, `legacy_queue`, `driver_status`, `production_status`, `open_orders`, `inventory_levels`, `briefing_summary`, etc.
- **Foundation (cross-vertical)**: `today`, `operator_profile`, `recent_activity`, `anomalies` (W-3a)
- **Manufacturing per-line**: `vault_schedule`, `line_status`, `urn_catalog_status` (W-3d)
- **Cross-surface infrastructure**: `saved_view`, `briefing` (W-3b)
- **Vault hub**: `documents_status`, `intelligence_summary`, `crm_activity_feed`, etc.
- **Communications Layer**: `calendar_glance`, `email_glance`, `calendar_consent_pending` (Calendar Step 5 + 5.1)

### Cross-References

- **CLAUDE.md §10 + §14 Phase W-1/W-3a/W-3b/W-3d entries** — canonical Widget Library Architecture
- **DESIGN_LANGUAGE.md §12** — canonical Widget Library spec (variants, surfaces, density tiers, chrome)
- **Focus composition kinds (§2 above)** — compositions consume widgets via `component_kind='widget'`
- **Theme tokens (§5 below)** — widget chrome consumes Pattern 2 surface tokens

---

## 4. Document blocks

### Purpose

Document blocks are the composable primitives that block-authored document templates compose into Jinja-rendered output. Six canonical block kinds at v1: header, body_section, line_items, totals, signature, conditional_wrapper. Adding a new kind is purely additive — register via `register_block_kind`; no schema migration.

The category exists so document authoring is data, not code. Tenant admins compose blocks; the composer emits Jinja; the renderer produces PDF/HTML/text. Phase D-10 substrate replaces monolithic Jinja templates with block sequences while keeping the existing render pipeline.

### Input Contract

`BlockKindRegistration` dataclass at `backend/app/services/documents/block_registry.py:32`:
- `kind: str` — stable identifier matching `document_template_blocks.block_kind`
- `display_name: str` + `description: str` — operator-facing
- `config_schema: dict[str, Any]` — JSON-schema-shape dict for per-instance validation + editor controls
- `compile_to_jinja: CompileFn` — `(config: dict, children_jinja: str) → str`; emits a Jinja fragment
- `declared_variables: DeclareVarsFn` — `(config: dict) → list[str]`; variables this block declares it uses
- `accepts_children: bool = False` — whether this kind wraps child blocks (`conditional_wrapper`)

### Output Contract

`compile_to_jinja(config, children_jinja)` returns a Jinja fragment as a string. The block composer at `backend/app/services/documents/block_composer.py::compose_blocks_to_jinja` walks blocks ordered by position, calls each kind's `compile_to_jinja`, concatenates fragments into a complete Jinja template body, and writes the composed body back to `document_template_versions.body_template`.

`declared_variables(config)` returns a list of variable names; the template version's `variable_schema` is aggregated from each block's declared variables.

### Guarantees

- **Composer recursion via explicit DB query** for `conditional_wrapper` children, NOT via SA relationship cache (cache returns stale empty lists when children are added in the same session — documented in CLAUDE.md §14 D-10 entry)
- **Render pipeline unchanged**: blocks → composed Jinja → existing `document_renderer.render()`. Both paths (legacy monolithic Jinja + new block-authored) coexist.
- **Idempotent registration**: re-registering the same kind replaces the existing entry (useful for hot-reload + tests).
- **Activation immutability**: blocks can be mutated on `draft` template versions; `active` versions are immutable. Mutation attempts return 409 per CLAUDE.md §14 D-10.

### Failure Modes

- `get_block_kind(kind)` raises `KeyError` for unknown kinds; callers handle as 400 at API boundary
- Composer failure for malformed config → propagated as 400 (config validation runs before compile)
- Conditional wrapper with no children → composer emits empty `{% if %}{% endif %}` block; renderer skips at runtime

### Configuration Shape

`document_template_blocks` table per migration `r85_document_template_blocks`:
- `id` + `template_version_id` FK + `block_kind` + `position` (composite index `(template_version_id, position)`)
- `config` JSONB — per-block instance config; validated against the kind's `config_schema`
- `condition` Jinja expression (NULL for unconditional blocks; set for `conditional_wrapper`)
- `parent_block_id` self-FK (children of `conditional_wrapper`)

**No multi-scope cascade on block kinds** — kinds are platform-only; per-template config is the data layer. Three-scope cascade applies at the *template* layer (D-11), not the block kind.

### Registration Mechanism

`register_block_kind(BlockKindRegistration(...))` at `backend/app/services/documents/block_registry.py:50`. Module-level singleton `_REGISTRY: dict[str, BlockKindRegistration]`. Seeded via `_seed_registry()` at module import time (side-effect import). Test isolation via `_REGISTRY.clear() + _seed_registry()`.

### Current Implementations

Six canonical kinds seeded at `block_registry.py:_seed_registry()`:

1. **`header`** — logo + title + subtitle + accent + date
2. **`body_section`** — heading + rich body
3. **`line_items`** — table iterating over a variable list with configurable columns
4. **`totals`** — rows of label + variable + emphasis flag
5. **`signature`** — signature collection area with `.sig-anchor` markers (compatible with Phase D-5 PyMuPDF anchor overlay)
6. **`conditional_wrapper`** (`accepts_children=True`) — wraps child blocks in Jinja `{% if condition %}{% endif %}`

### Cross-References

- **CLAUDE.md §14 Phase D-10 entry** — substrate canonicalization
- **CLAUDE.md §14 Phase D-11 entry** — vertical tier extension to document templates (block kinds inherit)
- **`block_composer.py`** — render pipeline integration
- **Focus composition kinds (§2 above)** — parallel "kind discriminator + composer-per-kind" pattern, different substrate

---

## 5. Theme tokens

### Purpose

Theme tokens are the design-language primitives (colors, shadows, radii, typography sizes, motion durations) consumed by every UI primitive on the platform. The token catalog declares ~80 tokens across 17 categories; tenants override via the `platform_themes` table with three-scope inheritance.

The category exists so visual customization is data, not code. Edit `--accent` at vertical_default scope → every consuming component re-renders at the new value without rebuild. Phase 2 visual editor establishes the pattern; future categories follow.

### Input Contract

Token catalog at `frontend/src/lib/visual-editor/themes/token-catalog.ts` declares each token:
- `name: string` — CSS variable name without `--` (e.g. `accent`, `surface-elevated`)
- `category: TokenCategory` — one of 17 (surface, content, border, accent, status, shadow-color, shadow-elevation, focus-ring, typography-family, typography-size, radius, motion-duration, motion-easing, max-width, z-index, transform, transition-curve)
- `valueType: ValueType` — one of 8 (`oklch`, `oklch-with-alpha`, `rgba`, `alpha`, `rem`, `px`, `ms`, `cubic-bezier`, `font-family`, `shadow-composition`, `transform`, `integer`)
- `defaults: { light: string, dark: string }` — per-mode default
- `bounds?` + `derivedFrom?` + `editable?: false`

Override storage shape on `platform_themes.token_overrides` JSONB: `{[tokenName]: value}` — only the deltas, not full token set.

### Output Contract

`theme_service.resolve_theme(db, *, mode, vertical?, tenant_id?)` at `backend/app/services/platform_themes/theme_service.py` returns:
- `tokens: dict[str, str]` — fully-resolved token map (catalog defaults + scope overlays)
- `sources: dict[str, dict]` — per-token provenance (which scope contributed, what version)
- `mode` + `vertical` + `tenant_id`

Frontend mirror at `frontend/src/lib/visual-editor/themes/theme-resolver.ts::composeEffective(mode, stack)` produces the same resolution shape for the editor's draft preview. Backend and frontend resolvers MUST agree on merge order — drift between them is a defect.

### Guarantees

- **Inheritance order**: `platform_default(mode) + vertical_default(vertical, mode) overrides + tenant_override(tenant_id, mode) overrides`. Deeper scope wins.
- **READ-time resolution**: a change at vertical_default propagates immediately to every tenant in that vertical that hasn't overridden the affected tokens. No migration, no batch job, no cache invalidation.
- **Mode is part of identity**: light + dark are independent records. Editing light's `--accent` does not affect dark's `--accent`.
- **Write-side versioning**: every save deactivates the prior active row at the same `(scope, vertical, tenant_id, mode)` tuple + inserts a new active row with `version + 1`. Partial unique on `is_active=true` enforces "at most one active per tuple."
- **Override semantics — only the deltas**: a vertical-default row with `token_overrides: {"accent": "..."}` says "this vertical overrides accent + inherits everything else from platform default."

### Failure Modes

- `ThemeNotFound` → HTTP 404 (admin API translation)
- `InvalidThemeShape` / `ThemeScopeMismatch` → HTTP 400 with detail
- Catalog mismatch (DB carries token name not in current catalog) → silently dropped from `tokens` map; logged warning; surfaced in `orphaned_keys` field (parallel to component config orphan pattern)

### Configuration Shape

`platform_themes` table per migration `r79_platform_themes`:
- `(scope, vertical?, tenant_id?, mode)` canonical tuple
- `token_overrides` JSONB — only the deltas
- `version` + `is_active` (write-side versioning)
- Standard audit + create/update timestamps

**Three-scope cascade** ✓ canonical. Mode is part of identity, NOT part of scope (mode-specific tokens use per-mode default in catalog).

### Registration Mechanism

Token catalog is a frontend constant (TypeScript at `frontend/src/lib/visual-editor/themes/token-catalog.ts`). Adding a new token requires (a) catalog entry, (b) `tokens.css` CSS variable definition (DESIGN_LANGUAGE.md §3 / §9 must stay synchronized in same commit per CLAUDE.md §14 "Tokens.css is a mirror" canon), (c) frontend visual-editor catalog cross-reference test ensures every `--name` in `tokens.css` is represented.

No backend `register_token(...)` API — backend reads token names dynamically from the override JSONB; the catalog is purely frontend authoring + write-time validation.

### Current Implementations

80 tokens across 17 categories cataloged at `token-catalog.ts`. Active scope rows per `platform_themes` table — currently platform_default rows for both modes seeded; vertical_default rows added as tenants opt in.

### Cross-References

- **CLAUDE.md §14 Phase 2 visual editor entry** — canonical introduction
- **DESIGN_LANGUAGE.md §3 + §9** — canonical token list + values (mirror discipline with `tokens.css`)
- **DESIGN_LANGUAGE.md §0** — three-layer design thesis framing
- **Component configurations** (R-8.y.b candidate) — same three-scope architecture; component-prop overrides bind to token references via `tokenReference` prop type
- **Focus composition kinds (§2 above)** — compositions consume tokens via `prop_overrides.tokenReference`
- **CLAUDE.md §14 Tier-4 Measurement-Based Correction entry** — methodology canon for token-value-vs-reference calibration

---

## 6. Workshop template types

### Purpose

Workshop template types are the canonical authoring surface for tenant-customizable platform features — currently Generation Focus templates (Personalization Studio canonical category). Each registered template type carries a discriminator string matching `GenerationFocusInstance.template_type` + a vocabulary of Tune-mode dimensions exposed for per-tenant configuration.

The category exists so tenant authoring is data-driven across operator-facing primitives. Operators see a Workshop browser showing every registered template type; tenant config sits in per-instance JSONB matching the type's declared schema. Adding a new template type registers an entry; the Workshop browser surfaces it; the Generation Focus runtime dispatches against the discriminator.

### Input Contract

`TemplateTypeDescriptor` dataclass at `backend/app/services/workshop/registry.py:52`:
- `template_type: str` — discriminator (e.g. `"burial_vault_personalization_studio"`)
- `display_name` + `description` — operator-facing
- `applicable_verticals: list[str]` — `["*"]` = cross-vertical; otherwise list of `Company.vertical` values
- `applicable_authoring_contexts: list[str]` — subset of canonical 3 (`funeral_home_with_family`, `manufacturer_without_family`, `manufacturer_from_fh_share`); empty = all permitted
- `empty_canvas_state_factory_key: str` — opaque key resolved by consumer to construct fresh canvas state
- `tune_mode_dimensions: list[str]` — Tune-mode dimension keys (e.g. `display_labels`, `emblem_catalog`, `font_catalog`, `legacy_print_catalog`)
- `sort_order: int = 100`

### Output Contract

`list_template_types(*, vertical?)` returns descriptors ordered by `(sort_order, template_type)`. Optional vertical filter excludes descriptors whose `applicable_verticals` doesn't match. `get_template_type(template_type)` returns the descriptor or None.

Workshop consumers (Generation Focus runtime, Tune-mode editor, Compose-mode editor) read descriptors to drive UI + dispatch logic. The descriptor is metadata; per-instance template config sits in `GenerationFocusInstance` rows.

### Guarantees

- **Idempotent registration via replacement**: re-registering the same `template_type` replaces the existing descriptor (matches `vault.hub_registry` + `triage.platform_defaults` pattern — useful for extensions + test isolation).
- **`applicable_authoring_contexts` validation at registration**: unknown context values raise `ValueError` with anti-pattern-guard message. Per §3.26.11.12.19.3 Q3 substrate canon.
- **Lazy seeding**: `_ensure_seeded()` runs `_seed_default_template_types()` on first access; idempotent re-seed safe.
- **Test isolation**: `reset_registry()` clears registry + marks unseeded.

### Failure Modes

- `ValueError` on registration with unknown authoring context — registry-substrate anti-pattern guard
- `get_template_type` returns None for unknown discriminator (consumers handle as 404 at API)
- No exceptions raised at the listing API — drift surfaces as missing entries, not errors

### Configuration Shape

In-code module-level singleton — no database table for template types themselves. Per-tenant configuration of an enrolled template type sits in:
- Tenant-customization config (`tenant_workshop_configurations` per-tenant rows; see CLAUDE.md §14 Personalization Studio Phase 1A-1G entries)
- Per-instance state (`generation_focus_instances` rows with `template_type` discriminator + per-instance `canvas_state` JSONB)

**No three-scope cascade on the descriptor** — descriptors are platform-only; per-tenant variation is Tune-mode config + Compose-mode forking (separate substrate layers).

### Registration Mechanism

`register_template_type(descriptor)` at `backend/app/services/workshop/registry.py:108`. Module-level `_registry: dict[str, TemplateTypeDescriptor]`. Default seed in `_seed_default_template_types()` runs on first access (lazy). Pattern parallels `vault.hub_registry` + `command_bar.registry` + `triage.platform_defaults` + `platform.action_registry`.

Future template types (Wall Designer, Drawing Takeoff, Mix Design, Audit Prep generator, healthcare templates per BRIDGEABLE_MASTER §3.26.11.12 strategic vision) call `register_template_type` from their own seed paths with zero changes to the registry module.

### Current Implementations

Two registered at September 2026 scope:

1. **`burial_vault_personalization_studio`** (sort_order=10) — Generation Focus template for burial vault cover personalization. Verticals: `["funeral_home", "manufacturing"]`. All 3 authoring contexts. Tune dimensions: display_labels + emblem_catalog + font_catalog + legacy_print_catalog (canonical 4-options vocabulary per §3.26.11.12.19.2).
2. **`urn_vault_personalization_studio`** (sort_order=20) — Step 2 substrate-consumption-follower; inherits Phase 1A-1G patterns via discriminator differentiation. Same verticals + contexts + Tune dimensions.

### Cross-References

- **CLAUDE.md §4 Workshop primitive (Session 1.5 canon)** — architectural role
- **CLAUDE.md §14 Phase 1A-1G + Step 2 entries** — pattern-establisher + substrate-consumption-follower discipline
- **BRIDGEABLE_MASTER.md §3.26.14 Workshop primitive canon** + **§3.26.11.12 Generation Focus canon** — vision-level framing
- **Composition action types (§7 below)** — parallel "central registry singleton + side-effect import" pattern

---

## 7. Composition action types

### Purpose

Composition action types (R-6.2a "platform action substrate") are the canonical action_type registry for actions funneled through `platform_action_tokens` — Email's quote_approval, Calendar's service_date_acceptance / delivery_date_acceptance / joint_event_acceptance / recurring_meeting_proposal / event_reschedule_proposal, future SMS Step 4 + Phone Step 4 entries, future Generation Focus family-approval entries.

The category exists so tokens carry a single substrate across primitives: the DB-level CHECK is on `linked_entity_type` (4-value enum locked at r70 + extended at r77 for `generation_focus`), and the action_type itself validates against the central registry rather than a per-primitive ACTION_TYPES tuple. Adding a new action_type registers an entry; the substrate accommodates it.

### Input Contract

`ActionTypeDescriptor` frozen dataclass at `backend/app/services/platform/action_registry.py:87`:
- `action_type: str` — globally unique action identifier (e.g. `"quote_approval"`)
- `primitive: PrimitiveType` — `"email" | "calendar" | "sms" | "phone" | "generation_focus"` (the owning primitive; drives `linked_entity_type` compatibility check)
- `target_entity_type: str` — canonical `action_target_type` per §3.26.15.17 + §3.26.16.17 etc. (e.g. `"quote"`, `"fh_case"`, `"sales_order"`, `"cross_tenant_event"`, `"calendar_event"`)
- `outcomes: tuple[str, ...]` — legal outcomes (e.g. `("approve", "reject", "request_changes")` for quote_approval; `("accept", "decline", "counter_propose")` for calendar action types)
- `terminal_outcomes: tuple[str, ...]` — subset of outcomes that put the action in a terminal state
- `commit_handler: Callable` — handler invoked by `commit_action` after validation + state transition; signature `handler(db, *, action, outcome, completion_metadata, ...) → None`
- `requires_completion_note: tuple[str, ...] = ()` — subset of outcomes requiring a completion_note at commit (e.g. `("request_changes",)` for quote_approval)

### Output Contract

`get_action_type(action_type)` returns the registered descriptor or raises `ActionRegistryError`. `list_action_types_for_primitive(primitive)` returns all descriptors for one primitive. `expected_linked_entity_type(action_type)` resolves the canonical `linked_entity_type` for substrate validation.

`commit_action` (in `app/services/platform/action_service.py`) consumes the descriptor — validates outcome is legal, validates completion_note is supplied when required, validates linked_entity_type matches the action_type's primitive, then invokes `commit_handler`.

### Guarantees

- **`action_type` global uniqueness** — registry enforces no duplicates; re-registering with a different descriptor logs WARNING + replaces (last-wins semantics like the triage registry).
- **Idempotent re-registration** with identical descriptor is no-op (matches dev reload + test fixture re-import semantics).
- **Cross-primitive token isolation**: `quote_approval` token can never be issued against `linked_entity_type='calendar_event'` even by accident — `expected_linked_entity_type` enforces at the substrate layer.
- **Validation discipline**: `ACTION_TYPE_REGISTRY` IS the validation surface. No database CHECK on `action_type` — that would require a migration every time a primitive registers a new action_type (anti-pattern). The DB-level CHECK is on `linked_entity_type` only (5-value enum locked at r70 + r77).

### Failure Modes

- `ActionRegistryError` (`action_registry.py:78`) on unknown action_type lookup → HTTP 400 at the platform action service boundary
- Outcome not in `outcomes` tuple → 400 with allowed-outcomes list in detail
- Missing completion_note when `requires_completion_note` matches outcome → 400
- linked_entity_type mismatch with action_type's primitive → 400 (`CrossPrimitiveTokenMismatch`-style)

### Configuration Shape

In-code module-level singleton — no database table for action type descriptors themselves. Per-token state sits in `platform_action_tokens` (r70 substrate consolidation):
- `linked_entity_type` + `linked_entity_id` polymorphic columns
- `action_type` (validated against registry, not CHECK-constrained)
- Token state machine (`pending` → `consumed` / `revoked` / `expired`)

**No multi-scope cascade** — descriptors are platform-only; per-tenant variation is per-token state.

### Registration Mechanism

`register_action_type(descriptor)` at `backend/app/services/platform/action_registry.py:144`. Module-level `_REGISTRY: dict[str, ActionTypeDescriptor]`.

**Side-effect-import discipline**: each primitive's package init imports its registrations module so the registry is populated by the first import. Email package init imports `email_action_service` which calls `register_action_type` for `quote_approval`. Future Calendar Step 4 + SMS Step 4 + Phone Step 4 + Generation Focus family approval follow the same pattern.

### Current Implementations

September 2026 scope:
- **Email**: `quote_approval` (`email_action_service.py`) — outcomes: `approve` / `reject` / `request_changes`; `request_changes` requires completion_note
- **Calendar** (Step 4 ships subsequent): `service_date_acceptance` / `delivery_date_acceptance` / `joint_event_acceptance` / `recurring_meeting_proposal` / `event_reschedule_proposal` (5 action_types per §3.26.16.17)

Test-only reset hook `_reset_registry_for_tests()` clears the registry. Production callers MUST NOT use it.

### Cross-References

- **CLAUDE.md §14 R-6.2a entry** — Calendar Step 1 discovery + substrate consolidation canon
- **CLAUDE.md §14 R-6.2a r70 + r77 migration entries** — `platform_action_tokens` polymorphic substrate
- **BRIDGEABLE_MASTER.md §3.26.15.17 + §3.26.16.17 + §3.26.17.18 + §3.26.18.20** — per-primitive action_type canon (each primitive's canonical action_target_type semantics drive the descriptor's `target_entity_type`)
- **Workshop template types (§6 above)** — parallel "central registry singleton + side-effect-import + frozen-dataclass-descriptor" pattern
- **Document blocks (§4 above)** — parallel `register_*` API canon

---

## 8. Accounting providers

### Purpose

Accounting providers abstract over external accounting system integrations (QuickBooks Online, Sage 100 via CSV, future systems). Each provider implements a uniform sync surface (customers, invoices, payments, bills, bill payments, inventory transactions, chart of accounts, account mappings). The factory resolves the correct provider per tenant based on `Company.accounting_provider`.

The category exists so platform code (invoice service, payment service, etc.) doesn't branch on accounting backend. Adding a new accounting system (Xero, Wave, Quicken) implements the ABC + extends the factory; nothing else changes.

### Input Contract

`AccountingProvider` ABC at `backend/app/services/accounting/base.py:52`. Required methods:
- `get_connection_status() → ConnectionStatus`
- `test_connection() → ConnectionStatus`
- `sync_customers(direction="push") → SyncResult` (`"push"` | `"pull"` | `"bidirectional"`)
- `sync_invoices(date_from?, date_to?) → SyncResult`
- `sync_payments(date_from?, date_to?) → SyncResult`
- `sync_bills(date_from?, date_to?) → SyncResult`
- `sync_bill_payments(date_from?, date_to?) → SyncResult`
- `sync_inventory_transactions(date_from?, date_to?) → SyncResult`
- `get_chart_of_accounts() → list[ProviderAccount]`
- `get_account_mappings() → list[AccountMapping]`
- `set_account_mapping(internal_id, provider_id) → AccountMapping`

Class attribute: `provider_name: str` (e.g. `"quickbooks_online"`, `"sage_csv"`).

Constructor signature (per `factory.py`): `__init__(self, db, company_id, actor_id?)`.

### Output Contract

Each method returns a typed dataclass (defined in `base.py`):
- `SyncResult(success, records_synced, records_failed, sync_log_id?, error_message?, details?)`
- `ConnectionStatus(connected, provider, last_sync_at?, error?, details)`
- `ProviderAccount(id, name, account_type, number?, is_active)`
- `AccountMapping(internal_id, internal_name, provider_id?, provider_name?)`

### Guarantees

- **Per-tenant connection**: each provider instance is scoped to one `(db, company_id, actor_id)` tuple. Cross-tenant operations are explicit (no implicit tenant inference).
- **`sync_log_id` in SyncResult** ties every sync operation to a `SyncLog` row for audit + reconciliation.
- **Idempotency** depends on provider implementation; canonical contract doesn't enforce. Caller (sync orchestrator) is responsible.
- **Tenant isolation** enforced at construction; provider's internal queries filter by `self.company_id`.

### Failure Modes

- `SyncResult.success=False` with `error_message` for recoverable failures (network blip, API rate limit)
- Connection-level failures surface via `ConnectionStatus.connected=False`
- Provider-internal exceptions propagate to caller as-is (no canonical exception hierarchy mandated by ABC)

### Configuration Shape

`Company.accounting_provider` field carries the provider key (`"quickbooks_online"` | `"sage_csv"` | `"none"`). Per-tenant connection state on `accounting_connections` table (OAuth tokens for QBO, CSV export paths for Sage).

**No multi-scope cascade** — provider selection is per-tenant via `Company.accounting_provider`; provider behavior is platform-coded per ABC.

### Registration Mechanism

**Divergence from canonical**: registration is hardcoded in `factory.get_provider(db, company_id, actor_id?)` at `backend/app/services/accounting/factory.py` via if/elif branches keyed on `Company.accounting_provider`:

```python
if provider_key == "quickbooks_online":
    return QuickBooksOnlineProvider(db, company_id, actor_id)
# Default to Sage CSV
return SageCSVProvider(db, company_id, actor_id)
```

There is no `register_provider(...)` API today. Adding a new provider requires (a) ABC subclass implementation, (b) factory if/elif branch, (c) entry in `get_available_providers()`. The pattern works because provider count is small (3 today including `"none"`), but contrasts with the cleaner registry pattern in Email providers (§9) and Composition action types (§7).

**Divergence note**: registration mechanism does not match Email providers' canonical `register_provider` + `PROVIDER_REGISTRY` pattern. Future migration arc could lift accounting to the same shape; no concrete migration window scoped today. Tracked in R-8.y.a investigation report as a divergence flagged for future cleanup.

### Current Implementations

- **`QuickBooksOnlineProvider`** at `backend/app/services/accounting/qbo_provider.py` — bidirectional sync via QBO OAuth API
- **`SageCSVProvider`** at `backend/app/services/accounting/sage_provider.py` — CSV export only (Sage 100); `supports_sync=False`
- **`"none"`** — sentinel for tenants with no accounting integration; factory returns SageCSVProvider as default but provider-key check at consumer layer skips sync

### Cross-References

- **CLAUDE.md §2 + §9** — Sage CSV + QBO integration context
- **CLAUDE.md §17 — Top Priority "Data Migration Tool"** — Sage CSV data migration scope
- **`accounting_connection.py`** + **`tenant_accounting_import_staging`** — per-tenant connection state model
- **Email providers (§9 below)** — parallel ABC pattern; Email has clean `register_provider` API that accounting lacks

---

## 9. Email providers

### Purpose

Email providers abstract over external email systems for Bridgeable's Email primitive — Gmail Workspace OAuth, Microsoft 365 OAuth (MS Graph), generic IMAP+SMTP fallback, transactional send-only (wraps existing DeliveryService for state-changes-generate-communications outbound flows). Each provider implements a uniform connect/sync/fetch/send surface.

The category exists so the Email primitive's substrate doesn't branch on provider. Adding a future native-transport provider (`NativeProvider` with SMTP/IMAP/POP3 + DKIM/SPF/DMARC + deliverability infrastructure per §3.26.15.1) registers under the same contract — Email primitive code doesn't change.

### Input Contract

`EmailProvider` ABC at `backend/app/services/email/providers/base.py:112`. Required methods:
- `connect(oauth_redirect_payload?) → ProviderConnectResult` — establish connection (OAuth or IMAP credentials or no-op for transactional)
- `disconnect() → None` — tear down subscriptions / watches (idempotent)
- `sync_initial(*, max_messages=1000) → ProviderSyncResult` — initial backfill
- `subscribe_realtime() → bool` — establish realtime subscription if supported (Gmail watch, MS Graph subscription); returns False for IMAP
- `fetch_message(provider_message_id) → ProviderFetchedMessage` — fetch full payload
- `fetch_attachment(provider_message_id, provider_attachment_id) → bytes`
- `send_message(*, from_address, to, cc?, bcc?, subject, body_html?, body_text?, in_reply_to_provider_id?, attachments?) → ProviderSendResult`

Class attributes:
- `provider_type: str` (matches `EmailAccount.provider_type` + `PROVIDER_REGISTRY` key)
- `display_label: str` — UI provider picker label
- `supports_inbound: bool`
- `supports_realtime: bool`

Constructor: `__init__(self, account_config: dict)` — receives `EmailAccount.provider_config` JSONB.

### Output Contract

Each method returns a typed dataclass (defined in `base.py`):
- `ProviderConnectResult(success, provider_account_id?, error_message?, config_to_persist)`
- `ProviderSyncResult(success, messages_synced, threads_synced, last_sync_at?, last_history_id?, last_delta_token?, last_uid?, error_message?)`
- `ProviderMessageRef(provider_message_id, provider_thread_id?, received_at?)`
- `ProviderFetchedMessage(...)` — full message payload + attachments
- `ProviderAttachment(provider_attachment_id, filename, content_type?, size_bytes?, content_id?, is_inline)`
- `ProviderSendResult(success, provider_message_id?, provider_thread_id?, error_message?, error_retryable)`

### Guarantees

- **Per-account instantiation**: each provider is instantiated per-account when needed. The `account_config` dict is the persisted `EmailAccount.provider_config`; each provider interprets its slice differently.
- **`supports_inbound` + `supports_realtime` class attributes** govern caller behavior — transactional skips inbound sync; IMAP polls; Gmail/MSGraph use realtime subscriptions.
- **`ProviderSendResult.error_retryable`** signals to caller whether to retry; classification belongs to provider, not consumer.
- **`disconnect` idempotency** required so EmailAccount disable/delete is safe to retry.
- **Step 1 stubs raise `NotImplementedError`** with step-2-pointer messages so missed calls fail loud rather than silently — defensive discipline preserved per the integrate-now-make-native-later framework.

### Failure Modes

- `ProviderConnectResult.success=False` with `error_message` for OAuth/IMAP failures
- `NotImplementedError` from Step 1 stubs for operations awaiting Step 2 wiring
- Provider-internal exceptions propagate; consumer (Email primitive substrate) classifies + logs

### Configuration Shape

Per-account configuration on `email_accounts` table:
- `provider_type` — must be a registered key
- `provider_config` JSONB — provider-specific (Gmail expects `credentials_json`, MSGraph expects `tenant_id` + `client_id`, IMAP expects `server` + `port` + `username`, transactional expects nothing)
- Account-state columns (last sync timestamp, delta tokens, OAuth refresh state)

**No multi-scope cascade** — providers are platform-coded; per-tenant variation is per-account configuration.

### Registration Mechanism

`register_provider(provider_type, provider_class)` at `backend/app/services/email/providers/base.py:241` + `PROVIDER_REGISTRY: dict[str, type[EmailProvider]]`.

**Side-effect import**: `backend/app/services/email/providers/__init__.py` calls `register_provider` for all 4 stub providers at package import. Future native provider registers via the same single-line call. Re-registering an existing key replaces (last-wins).

`get_provider_class(provider_type)` resolves; raises `KeyError` for unknown. Callers MUST validate `provider_type` against `app.models.email_primitive.PROVIDER_TYPES` before calling.

### Current Implementations

Four Step 1 stubs registered at package import:
- **`gmail`** → `GmailAPIProvider` (`gmail.py`) — `supports_inbound=True`, `supports_realtime=True`
- **`msgraph`** → `MicrosoftGraphProvider` (`msgraph.py`) — `supports_inbound=True`, `supports_realtime=True`
- **`imap`** → `IMAPProvider` (`imap.py`) — `supports_inbound=True`, `supports_realtime=False`
- **`transactional`** → `TransactionalSendOnlyProvider` (`transactional.py`) — `supports_inbound=False`, `supports_realtime=False`

Step 1 ships ABC + stubs; Step 2 implements real OAuth + sync atop. The native-transport provider lands as the 5th provider behind the same contract when SMTP/IMAP/POP3 infrastructure matures per CLAUDE.md §14 Session 2 canon.

### Cross-References

- **CLAUDE.md §14 Session 2 (Email Primitive Canon)** — canonical architectural framing + integrate-now-make-native-later commitment
- **BRIDGEABLE_MASTER.md §3.26.15** — Email Primitive canon
- **Accounting providers (§8 above)** — parallel ABC pattern; Email's `register_provider` is the cleaner canonical reference accounting could adopt
- **Delivery channels** (R-8.y.b candidate — currently graded ~ in R-8 audit) — Phase D-7 `DeliveryChannel` Protocol parallels EmailProvider ABC at transport level

---

## 10. Playwright scripts

### Purpose

Playwright scripts are stateless browser-automation primitives invoked by the workflow engine and triage embedded-actions runner. Each script declares its inputs, outputs, and credential service-key requirements; the runtime decrypts credentials, invokes `script.execute(inputs, credentials)` in an isolated event loop, and consumes the return dict.

The category exists so external-system actions that lack APIs (or have hostile APIs) are first-class platform primitives. Scripts compose into workflow steps via `action_type='playwright_action'` and into triage embedded-actions via `run_playwright_action` per CLAUDE.md §14 R-6.0 substrate.

### Input Contract

`PlaywrightScript` ABC at `backend/app/services/playwright_scripts/base.py:35`:
- Class attributes (instance-level, accessed via `cls.name` etc.):
  - `name: str` — globally unique script identifier (matches `PLAYWRIGHT_SCRIPTS` key + workflow step's `script_name` config)
  - `service_key: str` — credential service key (e.g. `"uline"`, `"staples"`) resolved by `credential_service`
  - `required_inputs: list[str]` — input dict keys the script requires
  - `outputs: list[str]` — output dict keys the script produces
- `async execute(inputs: dict, credentials: dict[str, str]) → dict` — primary method; runs in isolated event loop
- `validate_inputs(inputs)` — pre-flight check raising `PlaywrightScriptError` on missing required inputs

Helper: `_take_screenshot(page, prefix='error') → str | None` — best-effort screenshot to `/tmp` for debugging.

### Output Contract

Return dict whose keys match `self.outputs`. Each entry's type is script-specific (typically order numbers, confirmation IDs, status flags). On failure: raises `PlaywrightScriptError(message, screenshot_path?, step?)`.

### Guarantees

- **Stateless**: scripts have no instance state across `execute` calls. Each invocation gets a fresh class instance.
- **No DB access**: the script never touches the database. Credentials are decrypted by the caller and passed as a plain dict.
- **Isolated event loop**: workflow engine calls `script.execute(...)` in an isolated event loop per CLAUDE.md §14 R-6.0 substrate.
- **Input validation pre-flight** via `validate_inputs(inputs)` — missing required inputs raise before any browser work begins.
- **Failure carries screenshot path** when possible (`_take_screenshot` is best-effort).

### Failure Modes

- `PlaywrightScriptError(message, screenshot_path?, step?)` — single canonical exception type carrying message + optional screenshot path + optional step name for debugging
- Network/browser-level failures surface as `PlaywrightScriptError` with provider-specific message
- Authentication failures (credentials reject) surface as `PlaywrightScriptError` with `step='login'`-like markers

### Configuration Shape

In-code frozen dict `PLAYWRIGHT_SCRIPTS: dict[str, type[PlaywrightScript]]` at `backend/app/services/playwright_scripts/__init__.py:12`. No database table for script registrations. Per-invocation inputs sit in workflow step config (`workflow_step.config.inputs`) or triage embedded-action config.

Per-tenant credential storage via `credential_service` + `tenant_credentials` table — script resolves credentials by `service_key` at invocation.

**No multi-scope cascade** — scripts are platform-coded; per-tenant variation is per-tenant credential storage.

### Registration Mechanism

**Divergence from canonical**: registration is a frozen dict literal in `__init__.py`:

```python
PLAYWRIGHT_SCRIPTS: dict[str, type[PlaywrightScript]] = {
    "uline_place_order": UlineOrderScript,
    # Future:
    # "staples_place_order": StaplesOrderScript,
    # ...
}
```

There is no `register_script(...)` API today. Adding a new script requires (a) ABC subclass implementation, (b) dict entry append. The pattern works because script count is small (1 today; commented-out scaffolding for 4 future additions), but contrasts with the cleaner `register_action_type` + `register_block_kind` + `register_template_type` patterns elsewhere.

**Divergence note**: registration mechanism is dict literal, not `register_*` API. Only 1 implementation today (`uline_place_order`). When script count exceeds ~3-4 or extensions need to register scripts dynamically, future migration could lift to canonical `register_script` shape matching Document blocks (§4). No concrete migration window scoped today. Tracked in R-8.y.a investigation report.

### Current Implementations

1. **`uline_place_order`** → `UlineOrderScript` at `backend/app/services/playwright_scripts/uline_order.py:29` — automated order placement on Uline.com via tenant Uline credentials

Commented-out scaffolding for future scripts in `__init__.py`:
- `staples_place_order` (StaplesOrderScript)
- `grainger_place_order` (GraingerOrderScript)
- `ss_certificate_submit` (SSCertificateScript)
- `insurance_assignment` (InsuranceAssignmentScript)

### Cross-References

- **CLAUDE.md §14 R-6.0 entry** — Generation Focus + headless invocation substrate; triage embedded-actions consume Playwright scripts via `run_playwright_action`
- **Workflow engine action_types** (R-8.y.b / R-9 candidate) — `playwright_action` action type consumes script via `script_name` config field
- **`credential_service`** + **`tenant_credentials`** table — per-tenant credential storage; scripts resolve via `service_key`
- **Document blocks (§4 above)** — cleaner `register_*` API canon Playwright scripts could adopt if registration mechanism warrants lift

---

## Cross-category patterns appendix

Architectural patterns that span multiple categories. Documenting them once here keeps the per-category sections focused on substrate while making the cross-cutting discipline visible.

### Pattern 1: Three-scope inheritance at READ time

Categories: **Intake adapters** (form/file configs), **Focus composition kinds**, **Theme tokens** (+ R-8.y.b candidates: component configurations, workflow templates, dashboard layouts, document templates).

Canonical cascade: `tenant_override → vertical_default → platform_default`. First match wins (focus compositions, intake configs, workflow templates) OR overrides merge (theme tokens, component configurations — only the deltas merge atop platform defaults).

Why this is canonical (not parallel architectures): substrate work compounds. The visual editor's theme resolver (`theme-resolver.ts`) + composition service (`composition_service.py`) + intake resolver (`resolver.py`) share architectural shape; a developer reading one understands the other. Migration windows are bounded — adding a new three-scope category extends the established pattern rather than inventing one.

**Substrate rules consistent across categories:**
- Active rows enforced unique via partial index on `is_active=true`
- Write-side versioning: every save deactivates prior + inserts new active row with `version + 1`
- Empty `overrides: {}` is valid (= "inherit fully from parent")
- Resolution returns `source` field reporting which scope contributed
- Mode (where applicable, e.g. theme tokens light/dark) is part of identity, NOT scope

### Pattern 2: Registry as singleton + side-effect import

Categories: **Document blocks** (`register_block_kind` + `_seed_registry()`), **Workshop template types** (`register_template_type` + `_seed_default_template_types()`), **Composition action types** (`register_action_type` + side-effect imports per primitive), **Email providers** (`register_provider` + side-effect register in `providers/__init__.py`).

Canonical pattern: module-level singleton dict + `register_*` API + side-effect-import seed. Adding a new implementation = single-line registration call from the appropriate package init.

**Discipline**:
- Idempotent re-registration (replace existing entry by key) supports hot-reload + test isolation
- `reset_registry_for_tests()` or `reset_registry()` helper for fixture cleanup
- Side-effect import discipline: package init imports the module that calls `register_*` so registry is populated by first import
- Lookup raises typed exception (e.g. `KeyError`, `ActionRegistryError`, `BlockKindRegistration` lookup) translated to HTTP 400 at API boundary

**Anti-pattern guard**: re-registering with different descriptor logs WARNING + replaces (last-wins). Production paths should never hit this branch since descriptors are module-level constants; the warning catches drift early.

### Pattern 3: Frozen-dataclass descriptor

Categories: **Document blocks** (`BlockKindRegistration`), **Workshop template types** (`TemplateTypeDescriptor`), **Composition action types** (`ActionTypeDescriptor`).

Descriptors are `@dataclass(frozen=True)` (where supported) with typed fields. Immutability prevents accidental mutation at runtime; explicit fields constrain what registrations declare.

**Common descriptor shape:**
- Stable string `kind` / `template_type` / `action_type` identifier
- Operator-facing `display_name` + `description`
- Schema-shape config (`config_schema`, `tune_mode_dimensions`, etc.)
- Behavior callable(s) — `compile_to_jinja`, `commit_handler`, factory keys
- Optional behavior flags (`accepts_children`, `terminal_outcomes`, etc.)

### Pattern 4: ABC + protocol contract

Categories: **Accounting providers** (`AccountingProvider` ABC), **Email providers** (`EmailProvider` ABC + `EmailProvider.provider_type` class attr), **Playwright scripts** (`PlaywrightScript` ABC), **Delivery channels** (`DeliveryChannel` Protocol — R-8.y.b candidate; not strictly ABC but same contract shape).

ABC defines the canonical input/output contract via abstractmethod signatures + result dataclasses. Subclasses inherit method signatures + must implement each abstractmethod.

**Discipline**: result dataclasses are defined alongside the ABC (`base.py` file) so consumers + providers share the same vocabulary. Class-level attributes (`provider_name`, `provider_type`, `name`, `service_key`) carry identity for registry-key lookup.

### Pattern 5: Configuration is data, code is substrate

Across every category: per-instance configuration sits in tables (`platform_themes.token_overrides`, `intake_form_configurations.form_schema`, `widget_definitions.required_vertical`, `document_template_blocks.config`, etc.); code is the substrate that consumes the data.

**Anti-pattern guard documented in §2.4.4 + §3.26.11.12.16 + §2.5.4 canon**: vertical-specific code creep is structurally avoided when `applicable_verticals` is a data field, not a code branch. Adding a new vertical surfaces as data — not code edits across N services.

This is the **canonical-substrate-extension canon** that R-8's audit grade ✓ verified across the 10 categories documented here. R-8.y.b extends documentation to ~ partial categories (where the substrate is canonical but some dimension — usually scope cascade or registration mechanism — is partial). R-8.y.c extends to implicit categories (working patterns missing only formal contract documentation). R-8.y.d ships the plugin registry browser consuming all three documentation tiers.

### Divergence-watching list (per R-8.y.a investigation)

Implementations flagged in current sections that diverge from canonical contract:

1. **Accounting providers** registration via factory if/elif chain instead of `register_provider` API (canonical reference: §9 Email providers' `PROVIDER_REGISTRY`). Future migration arc could lift; bounded ~50 LOC.
2. **Playwright scripts** registration via dict literal instead of `register_*` API (canonical reference: §4 Document blocks' `register_block_kind`). Future migration arc when script count exceeds ~3-4; bounded ~30 LOC.

Both flagged for future cleanup arcs. R-8.y.a documents canonical contract + the divergence; resolving is out of scope (per R-8.y.a discipline — documentation arc, not migration arc).

---

**Document version**: 1.0 (R-8.y.a, 2026-05-11)
**Maintenance**: This document is canonical. Updates land alongside source changes — never in a separate commit. CLAUDE.md §14 Recent Changes entries link back here when categories evolve.
