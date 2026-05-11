# PLUGIN_CONTRACTS.md — Canonical Plugin Category Contracts

**Established**: 2026-05-11 (Phase R-8.y.a — first of four R-8.y documentation sub-arcs)
**Last updated**: 2026-05-11 (Phase R-8.y.c Phase 2a — 2 reclassifications + 4 descriptive sections + 3 cross-reference head-notes)
**Total contract count**: 23 (13 ✓ canonical + 10 ~ partial/implicit)
**Scope**: Bridgeable's explicit plugin categories + implicit category contracts surfaced by R-8 audit Section 2 — input/output contracts, guarantees, failure modes, configuration shape, registration mechanism, current implementations.

**Phase 2b note**: §23 Customer classification rules pending B-CLASSIFY-1/2/3 direction settlement; ships separately as Phase 2b.

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
2. [Intake adapters](#1-intake-adapters) `[✓ canonical]`
3. [Focus composition kinds](#2-focus-composition-kinds) `[✓ canonical]`
4. [Widget kinds](#3-widget-kinds) `[✓ canonical]`
5. [Document blocks](#4-document-blocks) `[✓ canonical]`
6. [Theme tokens](#5-theme-tokens) `[✓ canonical]`
7. [Workshop template types](#6-workshop-template-types) `[✓ canonical]`
8. [Composition action types](#7-composition-action-types) `[✓ canonical]`
9. [Accounting providers](#8-accounting-providers) `[✓ canonical]`
10. [Email providers](#9-email-providers) `[✓ canonical]`
11. [Playwright scripts](#10-playwright-scripts) `[✓ canonical]`
12. [Calendar providers](#11-calendar-providers) `[✓ canonical — reclassified R-8.y.b investigation]`
13. [Workflow node types](#12-workflow-node-types) `[~ partial — see Current Divergences]`
14. [Intelligence providers](#13-intelligence-providers) `[~ partial — see Current Divergences]`
15. [Delivery channels](#14-delivery-channels) `[~ partial — see Current Divergences]`
16. [Triage queue configs](#15-triage-queue-configs) `[~ partial — see Current Divergences]`
17. [Agent kinds](#16-agent-kinds) `[~ partial — see Current Divergences]`
18. [Button kinds](#17-button-kinds) `[~ partial — see Current Divergences]`
19. [Intake match-condition operators](#18-intake-match-condition-operators) `[~ implicit pattern]`
20. [Notification categories](#19-notification-categories) `[✓ canonical — reclassified R-8.y.c investigation]`
21. [Activity log event types](#20-activity-log-event-types) `[✓ canonical — reclassified R-8.y.c investigation]`
22. [PDF generator callers](#21-pdf-generator-callers) `[~ implicit pattern]`
23. [Page contexts](#22-page-contexts) `[~ implicit pattern]`
24. [Customer classification rules](#23-customer-classification-rules) `[RESERVED — Phase 2b after B-CLASSIFY-1/2/3 direction]`
25. [Intent classifiers](#24-intent-classifiers) `[~ implicit pattern]`
26. [Cross-category patterns appendix](#cross-category-patterns-appendix)

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

## 11. Calendar providers

**Maturity**: `[✓ canonical — reclassified R-8.y.b investigation]`

### Purpose

Calendar providers abstract over external calendar systems for Bridgeable's Calendar primitive — Google Calendar OAuth, Microsoft 365 OAuth (MS Graph), and Bridgeable-native local storage (no external transport). Each provider implements a uniform connect/sync/fetch/freebusy/send surface per §3.26.16.4 canon.

The category exists so the Calendar primitive's substrate doesn't branch on provider. Adding a future native CalDAV provider (or any new transport — Apple iCloud, Zoho, FastMail) registers under the same contract; Calendar primitive code doesn't change. The local provider is canonical first-class — Bridgeable owns calendar state directly via the `calendar_events` table, with provider abstraction handling external transport only (per CLAUDE.md §14 Session 3 integrate-now-make-native-later commitment).

This section was originally graded `~ partial` in the R-8 audit on the basis "Local provider only at September; Google + MS Graph + CalDAV documented as future." Runtime verification at `backend/app/services/calendar/providers/__init__.py:42-44` showed 3 providers registered today via the canonical `register_provider` + ABC + `PROVIDER_REGISTRY` pattern matching §9 Email providers verbatim. Google + MSGraph are stub-shaped at this commit (Step 2 wires real OAuth); the registration mechanism, ABC, and result dataclasses are canonical regardless. Reclassified ✓ canonical in R-8.y.b investigation.

### Input Contract

`CalendarProvider` ABC at `backend/app/services/calendar/providers/base.py:145`. Required methods (7 abstractmethods):
- `connect(oauth_redirect_payload?) → ProviderConnectResult` — establish connection (OAuth or no-op for local)
- `disconnect() → None` — tear down subscriptions / watches (idempotent)
- `sync_initial(*, backfill_window_days=90, lookahead_window_days=365) → ProviderSyncResult` — initial backfill of recent + upcoming events per §3.26.16.4 default window
- `subscribe_realtime() → bool` — establish realtime subscription if supported (Google watch, MS Graph subscription); returns False for local
- `fetch_event(provider_event_id) → ProviderFetchedEvent` — fetch full event payload
- `fetch_attendee_responses(provider_event_id) → list[ProviderAttendeeRef]` — refresh attendee response state between full syncs
- `fetch_freebusy(*, calendar_id?, time_range_start, time_range_end) → ProviderFreeBusyResult` — query free/busy windows over a time range

One non-abstract method (Step 3 outbound, default raises `NotImplementedError`):
- `send_event(*, vcalendar_text, method='REQUEST') → ProviderSendEventResult` — send outbound event via provider API per §3.26.16.5

Class attributes:
- `provider_type: str` (matches `CalendarAccount.provider_type` + `PROVIDER_REGISTRY` key)
- `display_label: str` — UI provider picker label
- `supports_inbound: bool` — whether the provider supports inbound sync (local is storage-only, False)
- `supports_realtime: bool` — whether the provider supports realtime subscription callbacks
- `supports_freebusy: bool` — whether the provider supports cross-account free/busy queries

Constructor: `__init__(self, account_config: dict, *, db_session=None, account_id=None)` — receives `CalendarAccount.provider_config` JSONB. Per Step 2 Q1 Path A architectural decision, providers receive optional `db_session` + `account_id` so the canonical state surface (the `calendar_events` table for local provider's freebusy; CalendarAccount row for sync engine) is reachable without deliberate-injection hacks. OAuth providers generally don't need the db handle; local provider uses both.

### Output Contract

Each method returns a typed dataclass (defined in `base.py:35-138`):
- `ProviderConnectResult(success, provider_account_id?, error_message?, config_to_persist)` — line 40
- `ProviderSyncResult(success, events_synced=0, last_sync_at?, last_sync_token?, error_message?)` — line 52
- `ProviderEventRef(provider_event_id, provider_calendar_id?, updated_at?)` — line 63 (lightweight reference from realtime callbacks)
- `ProviderFetchedEvent(provider_event_id, provider_calendar_id, subject, description_text?, description_html?, location?, start_at?, end_at?, is_all_day, event_timezone?, recurrence_rule?, status, transparency, organizer_email?, organizer_name?, attendees, raw_payload)` — line 72 (full-fidelity event payload)
- `ProviderAttendeeRef(email_address, display_name?, role, response_status, responded_at?, comment?)` — line 95
- `ProviderFreeBusyWindow(start_at, end_at, status)` — line 107 (status: "busy" | "tentative" | "out_of_office")
- `ProviderFreeBusyResult(success, windows, last_sync_at?, error_message?)` — line 116
- `ProviderSendEventResult(success, provider_event_id?, provider_calendar_id?, error_message?, error_retryable=False)` — line 126 (mirrors Email primitive's `ProviderSendResult` shape)

### Guarantees

- **Per-account instantiation**: each provider is instantiated per-account when needed. The `account_config` dict is the persisted `CalendarAccount.provider_config`; each provider interprets its slice differently (Google expects `credentials_json`, MSGraph expects `tenant_id` + `client_id`, local expects nothing — it has no transport).
- **`supports_inbound` + `supports_realtime` + `supports_freebusy` class attributes** govern caller behavior — local skips inbound sync; Google/MSGraph use realtime subscriptions; freebusy resolution checks `supports_freebusy` before calling the provider.
- **`ProviderSendEventResult.error_retryable`** signals to caller whether to retry; classification belongs to provider, not consumer (parallel to Email's `ProviderSendResult.error_retryable`).
- **`disconnect` idempotency** required so CalendarAccount disable/delete is safe to retry.
- **Step 1 stubs raise `NotImplementedError`** with step-2-pointer messages so missed calls fail loud rather than silently — defensive discipline preserved per the integrate-now-make-native-later framework. Local provider ships functional at Step 1 (canonical-native storage).
- **Recurrence canon ownership**: RRULE-as-source-of-truth per §3.26.16.4 — Bridgeable owns recurrence engine; providers bridge to external transports. Free/busy queries prefer canonical resolution from `calendar_events` rows after Step 2 ships the engine; fall back to provider only when canonical state is stale.

### Failure Modes

- `ProviderConnectResult.success=False` with `error_message` for OAuth failures
- `NotImplementedError` from Step 1 stubs for operations awaiting Step 2 wiring (OAuth providers); local provider raises `NotImplementedError` from `fetch_event` / `fetch_attendee_responses` because local events are Bridgeable-native and accessed via canonical CalendarEvent queries directly (no separate transport)
- Provider-internal exceptions propagate; consumer (Calendar primitive substrate) classifies + logs
- `send_event` default raises `NotImplementedError` for providers that don't implement outbound (none at Step 3 — all 3 implement)

### Configuration Shape

Per-account configuration on `calendar_accounts` table:
- `provider_type` — must be a registered key
- `provider_config` JSONB — provider-specific (Google expects `credentials_json`, MSGraph expects `tenant_id` + `client_id`, local expects nothing)
- Account-state columns (last sync timestamp, sync tokens, OAuth refresh state, subscription/watch ids returned from realtime registration)

OAuth state persisted via `config_to_persist` from `ProviderConnectResult` (Google watch `resource_id`; MSGraph `subscription_id`).

**No multi-scope cascade** — providers are platform-coded; per-tenant variation is per-account configuration (each tenant connects their own Google/MSGraph accounts).

### Registration Mechanism

`register_provider(provider_type, provider_class)` at `backend/app/services/calendar/providers/base.py:340` + `PROVIDER_REGISTRY: dict[str, type[CalendarProvider]]` at line 337.

**Side-effect import**: `backend/app/services/calendar/providers/__init__.py:42-44` calls `register_provider` for all 3 providers at package import. Future native CalDAV provider registers via the same single-line call. Re-registering an existing key replaces (last-wins).

`get_provider_class(provider_type)` at line 351 resolves; raises `KeyError` for unknown. Callers MUST validate `provider_type` against the canonical provider type set before calling.

### Current Implementations

Three providers registered at package import:
- **`google_calendar`** → `GoogleCalendarProvider` (`google_calendar.py`) — `supports_inbound=True`, `supports_realtime=True`, `supports_freebusy=True`. Stub-shaped at this commit; Step 2 wires real OAuth + Google Calendar API integration (`events.insert` with `sendUpdates=all` for iTIP server-side propagation).
- **`msgraph`** → `MicrosoftGraphCalendarProvider` (`msgraph.py`) — `supports_inbound=True`, `supports_realtime=True`, `supports_freebusy=True`. Stub-shaped at this commit; Step 2 wires real OAuth + MS Graph API integration (`POST /me/events` with `Prefer: outlook.sendNotifications=true` for iTIP server-side propagation).
- **`local`** → `LocalCalendarProvider` (`local.py`) — `supports_inbound=False`, `supports_realtime=False`, `supports_freebusy=True`. **Canonical-native first-class implementation** functional at Step 1. Bridgeable owns calendar state directly via `calendar_events`; this provider answers freebusy from canonical rows, no external transport.

Step 1 ships ABC + result dataclasses + registration + 3 implementations (1 functional, 2 stub-shaped for Step 2 wiring). The native CalDAV provider lands as the 4th provider behind the same contract when concrete signal warrants per §3.26.16.21 strategic vision deferral catalog.

### Cross-References

- **Pattern mirrors §9 Email providers verbatim** — same `register_provider` + `PROVIDER_REGISTRY` + ABC + side-effect-import structure; same result-dataclass shape (`ProviderConnectResult` / `ProviderSyncResult` / `ProviderFetchedEvent` parallels Email's `ProviderConnectResult` / `ProviderSyncResult` / `ProviderFetchedMessage`); same `supports_*` class-attribute discipline; same Step 1 stub vs Step 2 wiring cadence.
- **CLAUDE.md §14 Session 3 (Calendar Primitive Canon)** — canonical architectural framing + integrate-now-make-native-later commitment + RRULE-as-source-of-truth canon at §3.26.16.4
- **BRIDGEABLE_MASTER.md §3.26.16** — Calendar Primitive canon (25 subsections including §3.26.16.4 entity model + §3.26.16.5 outbound + §3.26.16.21 strategic vision deferral catalog)
- **Email providers (§9 above)** — direct sibling; Calendar providers are second canonical communication-primitive provider category sharing structural canon
- **Calendar Step 4 actions** (§3.26.16.17 / CLAUDE.md R-6.0+ context) — operational-action affordances built on top of provider substrate
- **R-8.y.b investigation report** (`/tmp/r8_y_b_normative_contracts_findings.md`) — reclassification rationale + file:line evidence

---

## 12. Workflow node types

**Maturity**: `[~ partial — see Current Divergences]`

> **Phase R-8.y.c cross-reference**: this category was implicit category #1 in R-8 audit Section 2 (workflow `action_type` dispatch); canonical documentation lives in this section. Source bindings (implicit category #3 in the same audit) are likewise covered by this section's B-WORK-3 deferral and require no separate section.

### Purpose

Workflow node types are the substrate the workflow engine dispatches on at runtime. Each `WorkflowStep.action_type` (`create_record`, `send_notification`, `playwright_action`, `invoke_generation_focus`, etc.) routes to a handler that executes the step's side effects + returns an outcome the engine consumes to drive `WorkflowRun` state.

The category exists so workflow templates can be authored as data: a tenant adopts a template referencing well-known action types, the engine knows how to execute each step without per-tenant branching. R-9 promotes the current if/elif dispatch chain to a registry; this section is the canonical contract R-9 implements against.

This is the **highest-stakes contract in R-8.y.b** — every action_type has live tenants invoking it through deployed workflow templates; R-9 migration parity must be tight (per Phase 8b cash_receipts BLOCKING parity precedent).

### Input Contract

**Canonical uniform handler signature** (B-WORK-1):

```python
def handler(
    db: Session,
    config: dict,
    run: WorkflowRun,
    ctx: WorkflowActionContext,
) -> WorkflowActionResult
```

`WorkflowActionContext` is a frozen dataclass carrying optional ambient values: `run_step_id`, `current_company`, `current_user`, `trigger_context`. Adding a new ambient value extends the dataclass; handler signatures don't churn.

Source bindings are resolved BEFORE handler invocation via the variable resolver (`workflow_engine.resolve_variables`) — handler receives a `config` dict with `{var.path}` references already substituted. Available source prefixes: `input.`, `output.`, `current_user.`, `current_company.`, `current_record.`, `incoming_email.`, `incoming_transcription.`, `vault_item.`, `incoming_form_submission.`, `incoming_file.`, `workflow_input.` (11 prefixes today, hardcoded at `workflow_engine.py:47-182`). Source bindings are a parallel registry concern (B-WORK-3) — separate sub-arc, not coupled to action types.

### Output Contract

**Canonical uniform output shape** (B-WORK-2):

```python
@dataclass(frozen=True)
class WorkflowActionResult:
    status: Literal["applied", "errored", "skipped", "awaiting_review", "awaiting_approval"]
    data: dict[str, Any]
    error_message: str | None = None
    error_code: str | None = None
```

`status` is the canonical discriminator field — eliminates the current `status`-vs-`type` inconsistency (`invoke_review_focus` returns `{"type": "awaiting_review", ...}` at `workflow_engine.py:813-818`; `invoke_generation_focus` returns `{"status": "applied", ...}` at `workflow_engine.py:754-758`).

`data` carries per-action-type payload — downstream steps reference `{output.<step_key>.<field>}` against this dict. Handler-specific output shape lives inside `data`; engine treats it opaquely.

Engine pattern-matches on `status` to drive `WorkflowRun` state: `applied` advances; `errored` marks step failed; `awaiting_review`/`awaiting_approval` flips run to paused state; `skipped` advances without state mutation.

### Guarantees

- **Fire-and-forget transactional semantics** (B-WORK-4). Per-step commit on success; mark step failed on exception. Cross-step transactionality is NOT provided — compensation is workflow-level explicit rollback steps. Aligns with the Phase 8b `call_service_method` adapter pattern where handlers explicitly delegate to service-level commit semantics.
- **Tenant isolation**: handlers receive `WorkflowRun.tenant_id` via `run` argument; queries against tenant-scoped tables filter by it. Per-action-type review during R-9 migration verifies each handler honors the boundary.
- **Step idempotency**: not guaranteed by engine. Each handler implements idempotency per its action_type semantics (e.g. `create_record` may use `source_entity_id` deduplication; `send_email` is fire-once with DocumentDelivery row creation before dispatch).
- **No silent fall-through**: unknown `action_type` returns `WorkflowActionResult(status="errored", error_code="unknown_action_type")` — eliminates the current silent `{"status": "unknown_action_type", ...}` fall-through at `workflow_engine.py:679` that doesn't mark the step failed.

### Failure Modes

- Handler raises exception → engine catches, marks step failed, sets `WorkflowActionResult(status="errored", error_message=str(exc), error_code=type(exc).__name__)`, calls `_fail_run`.
- Handler returns `status="errored"` explicitly → engine marks step failed (same path as exception, no exception captured).
- Unknown `action_type` → `errored` with `error_code="unknown_action_type"`.
- `awaiting_review` / `awaiting_approval` → flips `WorkflowRun.status` to paused; resume via `workflow_review_adapter.commit_decision` (R-6.0a canonical path) or via approval webhook.

### Configuration Shape

Workflow steps live as JSONB inside `workflow_templates.canvas_state.nodes` (admin-authored) and `workflows.steps` (tenant-instantiated). Each step carries:
- `id`: stable step identifier
- `type` / `action_type`: registered action_type key
- `config`: action-type-specific JSONB (validated against `WorkflowActionDescriptor.expected_config_keys` at adopt time)
- `next`: ID of next step on success / branching descriptor

**Three-scope cascade** for workflow templates per Pattern 1: `platform_default → vertical_default → tenant_override` (fork-on-customize per CLAUDE.md §4 Workflow Canvas). Action types themselves are platform-only data — registrations are code, never per-tenant — per Pattern 5 (configuration is data, code is substrate).

### Registration Mechanism

**Canonical**: Tier R1 — `register_workflow_action_type(WorkflowActionDescriptor)` API + module-level `_REGISTRY` singleton + side-effect-import seed pattern. Mirrors §7 Composition action types verbatim.

```python
@dataclass(frozen=True)
class WorkflowActionDescriptor:
    action_type: str
    display_name: str
    handler: Callable[[Session, dict, WorkflowRun, WorkflowActionContext], WorkflowActionResult]
    expected_config_keys: list[str]
    state_mutating: bool  # documented; not enforced by engine
    # Future extensibility (not v1):
    # input_schema, output_schema, side_effect_audit_tags, ...
```

**Validator derivation** (B-WORK-5): Full derivation. Backend canvas validator imports the registry; `VALID_NODE_TYPES` derives from `_REGISTRY.keys()`. Frontend mirror reads a committed JSON snapshot generated at build time from the registry; CI verifies snapshot matches registry (pattern parallels `class-registrations.test.ts` cross-language metadata snapshot canon). Three parallel allowlists (engine if/elif, backend `canvas_validator.py:62-105`, frontend `canvas-validator.ts:18-56`) collapse to one source of truth.

### Current Implementations

13 action_types dispatched by the if/elif chain at `backend/app/services/workflow_engine.py:628-679`:

| action_type | Handler | Notes |
|---|---|---|
| `create_record` | `_handle_create_record` | State-mutating; creates polymorphic vault items |
| `update_record` | `_handle_update_record` | State-mutating |
| `open_slide_over` | inline pass-through | Client-side action; engine emits config |
| `show_confirmation` | inline | UI-only |
| `send_notification` | `_handle_send_notification` | State-mutating; writes Notification rows |
| `send_email` | inline pass-through | State-mutating via DeliveryService; current implementation is thin stub |
| `log_vault_item` | `_handle_log_vault_item` | State-mutating |
| `generate_document` | `_handle_generate_document` | State-mutating; creates Document via D-1 substrate |
| `playwright_action` | `_handle_playwright_action` | External side effect |
| `call_service_method` | `_handle_call_service_method` | Adapter pattern (Phase 8b); whitelisted dispatch via `_SERVICE_METHOD_REGISTRY` at `workflow_engine.py:986-1028` |
| `invoke_generation_focus` | `_handle_invoke_generation_focus` | Pause-and-wait; returns `status="applied"` for synchronous Focus invocations |
| `invoke_review_focus` | `_handle_invoke_review_focus` | Pause-and-wait; returns `type="awaiting_review"` (B-WORK-2 divergence — discriminator field is `type`, not `status`) |
| (fall-through) | inline | Returns `{"status": "unknown_action_type"}` without marking step failed (B-WORK-2 divergence — silent no-op) |

### Current Divergences from Canonical

R-9 is the migration arc that resolves these. Estimated scope: ~900 LOC total (backend ~600 + tests ~200 + frontend ~50 + Playwright regression).

1. **Engine dispatch is if/elif chain, not registry** (`workflow_engine.py:628-679`). Primary R-9 migration target. ~150 LOC engine rewrite to `_REGISTRY[action_type](db, config, run, ctx)` dispatch.
2. **Per-handler signature variance** — `_handle_create_record(db, config, run)` vs `_handle_invoke_review_focus(db, config, run, *, run_step_id)`. ~30 LOC per handler migration to uniform `(db, config, run, ctx)` signature; ~390 LOC across 13 handlers.
3. **Per-handler output shape variance + inconsistent discriminator field** — `status` vs `type` (`workflow_engine.py:813-818` invoke_review_focus uses `type` key). Migration to `WorkflowActionResult` dataclass uniformizes; eliminates silent fall-through at line 679.
4. **Canvas validator allowlist drift surface** — 3 parallel allowlists (`workflow_engine.py:628-679` dispatch, `canvas_validator.py:62-105` backend allowlist, `canvas-validator.ts:18-56` frontend mirror). R-9 collapses to single registry-derived source.
5. **`_SERVICE_METHOD_REGISTRY` is a sub-registry inside `call_service_method` action** (`workflow_engine.py:986-1028`, 7 entries today). R-9 preserves as a separate concern — action types register `call_service_method` as one entry; the method registry stays as the dispatch surface for service-layer adapters introduced by workflow-arc Phases 8b-8f.
6. **Source bindings hardcoded 11-prefix table** at `workflow_engine.py:47-182`. Separate sub-arc per B-WORK-3 recommendation (NOT coupled to R-9). Future ~400 LOC promotion to `register_source_binding(prefix, resolver)` registry when concrete signal warrants.

### Cross-References

- **§7 Composition action types** — canonical reference pattern. Workflow node types adopt the same `register_action_type(ActionTypeDescriptor)` + side-effect-import shape.
- **§17 Button kinds** — client-side parallel. Both are extensible-dispatch categories; deliberately parallel catalogs (B-BTN-1) because client-side React-bound dispatch is fundamentally different from server-side SQLAlchemy-bound dispatch. See Meta-Pattern 3 sub-pattern: category-clusters.
- **CLAUDE.md §4 Workflow Canvas** — workflow_templates substrate (R-9 builds on this); three-scope cascade canon.
- **CLAUDE.md §14 R-9 entry** (future) — migration session that consumes this section.
- **R-8 audit Section 2 #3 (Source bindings)** — separate sub-arc, ~400 LOC.

---

## 13. Intelligence providers

**Maturity**: `[~ partial — see Current Divergences]`

> **Phase R-8.y.c cross-reference**: implicit category #7 (AI prompt categories per R-8 audit) is a sub-pattern of this contract — `prompt_key` namespace conventions (`scribe.*`, `briefing.*`, `classification.*`, `nl_creation.*`, `workshop.*`, `accounting.*`, `vision.*`, etc.) are documented in CLAUDE.md §4 Bridgeable Intelligence; no separate registry layer.

### Purpose

Bridgeable Intelligence is the unified AI layer — every AI call in the platform routes through `intelligence_service.execute(prompt_key=..., variables=..., company_id=..., caller_module=..., caller_entity_*=...)`. The Intelligence provider category abstracts over LLM transport (Anthropic today; OpenAI / Google / native models as deferred future).

The category exists so prompts are managed configuration (versioned, scope-cascaded, admin-customizable) and provider switching can happen without touching the 80+ callers across the codebase. CLAUDE.md §3 Bridgeable Intelligence canon describes the architectural role; this section specifies the contract.

### Input Contract

`intelligence_service.execute()` at `backend/app/services/intelligence/intelligence_service.py:268`. Public callable signature:

```python
def execute(
    *,
    prompt_key: str,
    variables: dict[str, Any] | None = None,
    company_id: str,
    caller_module: str,
    caller_entity_type: str | None = None,
    caller_entity_id: str | None = None,
    content_blocks: list[ContentBlock] | None = None,
    force_json: bool | None = None,
    response_schema: dict | None = None,
    model_override: str | None = None,
    ...
) -> IntelligenceResult
```

- `prompt_key` resolves a managed prompt via the two-tier registry (platform_default → tenant_override on `(company_id, prompt_key)`); `prompt_registry.get_prompt` at `prompt_registry.py:36-63`.
- `variables` is a flat dict for Jinja rendering; per-key validation against `PromptVersion.variable_schema` at execute-time.
- `caller_module` + `caller_entity_*` populate audit linkage on the `intelligence_executions` row.
- `content_blocks` carries multimodal payload (vision: image/document base64); raw base64 redacted from audit row's `rendered_user_prompt` (sha256 + bytes_len only).

### Output Contract

`IntelligenceResult` dataclass with structured response + audit metadata:

```python
@dataclass
class IntelligenceResult:
    text: str | None
    json_payload: dict | None
    status: Literal["success", "fallback_used", "rate_limited", "api_error", "parse_error", "all_models_failed"]
    model_used: str
    prompt_id: str
    prompt_version: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    latency_ms: int
    execution_id: str
    error_code: str | None  # canonical IntelligenceError code
    error_message: str | None
```

Every call produces an `intelligence_executions` audit row regardless of success/failure (full audit trail; never silently dropped).

### Guarantees

- **Single canonical AI surface**: every AI call routes here; direct `anthropic` SDK imports outside `app/services/intelligence/` are forbidden (Ruff TID251 + pytest lint gate).
- **Tenant isolation**: `company_id` required on every call; surfaces in audit row; prompt resolution respects tenant_override scope.
- **Cost accounting**: `cost_usd` computed from token counts × per-model rates on `intelligence_model_routes`; every call attributable to a caller via `caller_module` + `caller_entity_*` linkage.
- **Per-prompt model routing via `intelligence_model_routes` table** (`backend/app/models/intelligence.py:104-127`) — routes carry `route_key`, `primary_model`, `fallback_model`, `provider` (column defaults `"anthropic"`), cost rates, max_tokens, temperature, is_active.
- **Fallback dispatch via `model_router.route_with_fallback`** (`model_router.py:103-138`): on retryable exception, retry on `fallback_model`; non-retryable propagates; both-failed raises `AllModelsFailedError`. Retryable classification via `_RETRYABLE_EXC_NAMES` frozenset at `model_router.py:70-78` (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError, ServiceUnavailableError, OverloadedError).

### Failure Modes

**Hybrid failure taxonomy** (B-INTEL-2). Binary at dispatch level (retryable / non-retryable via `_RETRYABLE_EXC_NAMES` frozenset) + closed-vocabulary `IntelligenceError` codes surfaced in `IntelligenceResult.status` + `error_code`:

| status / error_code | Meaning |
|---|---|
| `success` | Normal response from primary model |
| `fallback_used` | Primary failed retryable; fallback succeeded |
| `rate_limited` | Provider rate limit; non-retryable for this call (post-fallback) |
| `api_error` | Provider returned 4xx/5xx not classified as retryable |
| `parse_error` | force_json=True but response was unparsable JSON |
| `all_models_failed` | Both primary + fallback exhausted retries |

Closed-vocabulary platform-owned (Tier R2). Callers introspect `error_code` for finer signal without parsing message text.

### Configuration Shape

**Prompts as platform-global configuration data** (Tier R2 + Pattern 5):
- `intelligence_prompts` table — `prompt_key` (unique within `company_id` scope), `company_id` (null = platform-global), `display_name`, `description`, ...
- `intelligence_prompt_versions` table — `version`, `system_prompt`, `user_prompt_template`, `variable_schema` (JSONB), `is_active`, `created_at`. Versioning is append-only; activation flips `is_active` flag.
- `intelligence_model_routes` table — per `route_key`, the primary + fallback model + cost rates.

**Two-tier scope cascade** (B-INTEL-3): `platform_global → tenant_override` on `(company_id, prompt_key)`. Vertical-variance is canonically handled by Jinja-branching inside platform-global prompts (per `test_briefing_vertical_terminology.py` precedent — VERTICAL-APPROPRIATE TERMINOLOGY blocks gate output by `{{ vertical }}` variable). Three-scope cascade would be substantial migration with little operational gain over the established Jinja-branch pattern.

### Registration Mechanism

**Provider registration**: Tier R3 — deferred. Currently `_get_client()` at `intelligence_service.py:253-258` hardcodes `anthropic.Anthropic`. The `IntelligenceModelRoute.provider` column is forward-compat scaffold.

**Prompt registration**: Pattern 5 (configuration is data). Prompts seeded via idempotent seed scripts (`scripts/seed_intelligence_*.py`); no code-side `register_prompt` API. Adding a new prompt is a seed-script edit + activation.

### Current Implementations

**Single provider canonical** (Anthropic): `intelligence_service.py:29` imports `anthropic`; `_get_client()` returns `anthropic.Anthropic(api_key=...)`. 73+ active platform-global prompts covering Scribe, accounting agents, briefings, command bar, NL Overlay, urn pipeline, safety, CRM, KB, onboarding, training, compose, workflows, vision (check-image + PDF extraction).

### Current Divergences from Canonical

1. **`_get_client()` hardcodes `anthropic.Anthropic`** (`intelligence_service.py:253-258`). Deferred per B-INTEL-1 — no concrete signal warrants multi-provider integration yet; ABC design defers until 2nd provider in production OR Anthropic SDK breaking-change pressure OR cost/availability driver requiring per-request multi-provider failover. The `provider` column on `intelligence_model_routes` is the documented-but-unactivated scaffold.
2. **`model_router._RETRYABLE_EXC_NAMES` opaque to callers** (`model_router.py:70-78`). Canonical `IntelligenceError` vocabulary on `IntelligenceResult.error_code` IS the stable surface (B-INTEL-2); frozenset stays as internal classifier.

### Cross-References

- **CLAUDE.md §3 Bridgeable Intelligence canon** — architectural framing + 73-prompt inventory + caller migration history.
- **§9 Email providers** — canonical multi-provider reference (Tier R1 + ABC). When B-INTEL-1 activates, Intelligence providers ABC adopts that shape.
- **§14 Delivery channels** — canonical hybrid Protocol + closed-vocabulary error taxonomy. B-INTEL-2 follows the same hybrid discipline.
- **Briefings precedent** (CLAUDE.md §14 Session 6 entry) — Jinja-branch vertical-variance pattern.
- **R-8 audit §6 Tier 1 item R-8.3** — 2 escaped Claude system prompts (call_extraction_service + obituary_service) bypass the Intelligence registry; DEBT.md migration target.

---

## 14. Delivery channels

**Maturity**: `[~ partial — see Current Divergences]`

### Purpose

Delivery channels abstract over outbound message transport — Email (Resend today; native SMTP deferred), SMS (stub `NOT_IMPLEMENTED`; native carrier integration deferred), future webhook / push / in-app. The DeliveryService orchestrator at `backend/app/services/delivery/delivery_service.py:189-330` resolves content + recipient, creates the `document_deliveries` row, then dispatches to the registered channel.

The category exists so DeliveryService callers (10 email callers today: signing, statement, collections, invoice, alert digest, accountant invitation, etc.) don't branch on transport — they pass `channel="email"` or `channel="sms"` and let the substrate handle dispatch + retry + audit.

### Input Contract

**Protocol-based contract surface** (B-DELIV-1) — Tier R1 registration + Protocol-typed contract. Honors the stateless-dispatch nature of channels (see Meta-Pattern 3 sub-pattern: stateless-dispatch vs stateful-lifecycle).

`DeliveryChannel(Protocol)` at `backend/app/services/delivery/channels/base.py:67-78`. `@runtime_checkable`. Required surface:

```python
@runtime_checkable
class DeliveryChannel(Protocol):
    channel_type: str  # class attr — "email" | "sms" | future
    provider: str      # class attr — "resend" | "stub" | future
    supports_attachments: bool  # capability flag
    supports_html_body: bool    # capability flag

    def send(self, request: ChannelSendRequest) -> ChannelSendResult: ...
```

`ChannelSendRequest` carries the resolved message: recipients (list of `Recipient(email, phone, name)`), subject, body_text, body_html, attachments (list of `Attachment(filename, content_type, content_bytes)`), provider-specific overrides (reply_to, headers).

### Output Contract

`ChannelSendResult` dataclass at `base.py:36-63`:

```python
@dataclass
class ChannelSendResult:
    success: bool
    provider: str
    provider_message_id: str | None = None
    error_message: str | None = None
    error_code: str | None = None  # canonical error class name (Tier R2)
    retryable: bool = False
    provider_response: dict[str, Any] | None = None
```

`retryable: bool` is the canonical retry-signal carrier consumed by DeliveryService's inline-retry loop. Channel classifies; consumer decides retry policy.

### Guarantees

- **Stateless**: channel instances are singletons; `_CHANNELS` dict at `__init__.py:35` holds one per type. No per-call state.
- **Caller owns idempotency**: DeliveryService creates `DocumentDelivery` row with `status=pending` BEFORE dispatch; on success → `sent`; on failure post-retry → `failed`. Channel is fire-and-forget within a single call; re-dispatch creates a new row.
- **`success=False + retryable=False`**: canonical clean-failure shape (used by SMS stub; future webhook 4xx auth failures). Engine marks delivery `failed`/`rejected` without retry.
- **Inline retry**: DeliveryService loops up to `max_retries` (default 3) when `retryable=True`; raises after exhaustion.

### Failure Modes

**Closed-vocabulary exception class hierarchy** (B-DELIV-2) — Tier R2. Channels MAP provider-specific exceptions to canonical classes at the wrap boundary:

```python
class ChannelSendError(Exception):
    """Base — never raised directly."""

class RetryableChannelError(ChannelSendError):
    """Network / timeout / transient — caller retries."""

class PermanentChannelError(ChannelSendError):
    """Validation / 4xx — caller does NOT retry."""

class RateLimitedChannelError(RetryableChannelError):
    """429 — retryable with backoff."""

class AuthFailureChannelError(PermanentChannelError):
    """401/403 from provider — config issue, not transient."""

class BadRequestChannelError(PermanentChannelError):
    """400 from provider — recipient/payload invalid."""
```

Channels CAN return `ChannelSendResult(success=False, retryable=...)` instead of raising — the result shape carries the same canonical `error_code` vocabulary. Raising is canonical for downstream observability + structured logging integration.

### Configuration Shape

**No multi-scope cascade** — channels are platform-coded; per-tenant variation is per-account configuration (e.g. tenant's own Resend domain; future tenant SMTP overrides).

DeliveryService caller-side configuration: `channel_type`, `template_key` (resolves managed Workshop template per §6), `recipient_resolution_strategy`, `max_retries`. Per Pattern 5 (configuration is data).

### Registration Mechanism

**Canonical Tier R1**: `register_channel(channel_type, implementation)` at `backend/app/services/delivery/__init__.py:55-61` + `_CHANNELS: dict[str, DeliveryChannel]` singleton at line 35. Side-effect-import discipline: implementations registered at `delivery/__init__.py:35-38` (line `_CHANNELS = {"email": EmailChannel(), "sms": SMSChannel()}`).

Future native-SMTP / native-SMS implementations swap in via `register_channel("email", NativeSmtpChannel())` without caller changes.

**Canonical `NOT_IMPLEMENTED` reservation** (B-DELIV-3) — Tier R2 stable error_code value. Stub channels register fully, implement Protocol surface, return canonical not-implemented result rather than crashing:

```python
ChannelSendResult(
    success=False,
    provider=self.provider,
    error_code="NOT_IMPLEMENTED",
    retryable=False,
    error_message="Channel registered but transport awaiting implementation",
)
```

Used by SMS today (`sms_channel.py:30-45`); reserved for future webhook/push/in-app deferrals. Discipline: stub never raises; implements full Protocol surface; has tracked implementation arc.

### Current Implementations

| channel_type | Implementation | Provider | Status |
|---|---|---|---|
| `email` | `EmailChannel` (`email_channel.py`) | `resend` | Functional. Supports attachments + html_body. |
| `sms` | `SMSChannel` (`sms_channel.py`) | `stub` | `NOT_IMPLEMENTED` per canonical stub pattern. |

### Current Divergences from Canonical

1. **EmailChannel retryable-classification via substring matching** (`email_channel.py:121-124`). Message-substring heuristic — fragile to Resend's error text changes. Migration target: ~30 LOC to wrap `resend` exceptions in canonical exception-class hierarchy per B-DELIV-2. Bounded sub-arc; high reliability gain.
2. **No webhook / push / in-app channels registered** — divergence is "category is single-implementation today" not contract violation. Registry is ready for additions.

### Cross-References

- **§9 Email providers** — canonical multi-provider ABC pattern. Delivery channels are sibling category-cluster: providers are stateful-lifecycle (connect/sync/disconnect), channels are stateless-dispatch. Both canonical for their use cases (Meta-Pattern 3).
- **§6 Workshop template types** — `template_key` resolution for caller-side content; DeliveryService renders template before channel dispatch.
- **D-7 Delivery Abstraction** (CLAUDE.md §14) — architectural framing + integrate-now-make-native-later commitment.
- **Future native-SMS implementation arc** — tracked at `sms_channel.py:1-9` comments; separate workstream.

---

## 15. Triage queue configs

**Maturity**: `[~ partial — see Current Divergences]`

### Purpose

Triage queue configs are the substrate the triage workspace (Phase 5 UI/UX arc) dispatches on at runtime. Each `TriageQueueConfig` declares item source + action palette + context panels + permission/vertical gating + workflow integration. The triage engine resolves configs at session start, surfaces items via direct query or saved-view registry, dispatches per-item actions through the action handlers dict.

The category exists so triage queues are configuration data — adding a new queue is a `register_platform_config(...)` call from the platform_defaults seed plus action handler entries; new tenant-customized queues are vault_items with `item_type="triage_queue_config"`.

### Input Contract

`TriageQueueConfig` Pydantic model at `backend/app/services/triage/types.py:203-266` with `extra="forbid"` + `schema_version="1.0"`. Required fields:

- `queue_id: str` — stable identifier
- `display_name: str` + `description: str`
- `item_entity_type: str` (e.g. `task`, `social_service_certificate`, `safety_program_generation`)
- 7 nested component configs: `ItemDisplayConfig`, `ActionConfig` (list), `ContextPanelConfig` (list), `EmbeddedActionConfig` (list), `FlowControlsConfig`, `CollaborationConfig`, `IntelligenceConfig`
- `permissions: list[str]`, `required_vertical: list[str]`, `required_extension: list[str]` — gating

**Source discriminator** (B-TRIAGE-3 canonical target — Pydantic v2 discriminated union):

```python
class DirectQuerySourceConfig(BaseModel):
    source_type: Literal["direct_query"]
    source_direct_query_key: str

class SavedViewSourceConfig(BaseModel):
    source_type: Literal["saved_view"]
    source_saved_view_id: str

class InlineSourceConfig(BaseModel):
    source_type: Literal["inline"]
    source_inline_config: dict[str, Any]

TriageSourceConfig = Annotated[
    DirectQuerySourceConfig | SavedViewSourceConfig | InlineSourceConfig,
    Field(discriminator="source_type"),
]
```

`source_inline_config` flagged transitional — future removal when Phase 2 saved-view registry coverage complete.

### Output Contract

Each `ActionConfig.handler` references a key in the global `HANDLERS` dict at `backend/app/services/triage/action_handlers.py:1088`. Handler signature:

```python
HandlerFn = Callable[[Session, TriageActionContext], TriageActionResult]
```

Returns:
- Outcome status (`approved`, `rejected`, `deferred`, `escalated`)
- Side-effect summary (vault_items created, workflow_runs started, etc.)
- Next-item-advance signal (engine auto-advances on success unless workflow paused)

### Guarantees

- **Tenant isolation**: queue configs gated by `permissions` + `required_vertical` + `required_extension` at `list_queues_for_user` (`registry.py:143-183`); items filtered to caller tenant at source dispatch.
- **Action atomicity**: each action handler runs in a single DB transaction; commit on success, rollback on exception. Engine state-machine transitions are part of the same transaction.
- **Resumable sessions**: `triage_sessions` rows persist current item + queue position; reload restores state.
- **Permission gates fire BEFORE handler invocation**: handler only sees actions it's permitted to dispatch.

### Failure Modes

- `TriageQueueConfig` validation rejects malformed configs at `register_platform_config` time (Pydantic `extra="forbid"` + per-field validators).
- Unknown handler key → handler-missing error at config load (validation at `register_platform_config` cross-references `HANDLERS` dict).
- Action handler raises → transaction rollback + 500 to caller; action stays uncommitted.
- Cross-tenant `item_id` → 404 (existence-hiding, not 403).

### Configuration Shape

**Three-scope cascade** canonical (B-TRIAGE-1) per Pattern 1: `platform_default → vertical_default → tenant_override`. Current implementation is two-scope (platform_default + tenant_override only) — divergence + migration target.

**Tenant overrides** persist as vault_items with `item_type="triage_queue_config"` + JSONB body matching `TriageQueueConfig` shape. `list_all_configs` at `registry.py:117-128` merges atop platform_defaults by `queue_id` (last-write-wins on key collision).

### Registration Mechanism

**Canonical**: Tier R1 — `register_platform_config(config: TriageQueueConfig)` at `backend/app/services/triage/registry.py:60-63` + `_PLATFORM_CONFIGS` module-level singleton + side-effect-import seed from `platform_defaults.py:1066-1159` (11 platform queues registered at first import).

**Action handlers dict** (B-TRIAGE-2): flat `HANDLERS: dict[str, HandlerFn]` at `action_handlers.py:1088` — Tier R2 closed-vocabulary platform-owned. **`<entity>.<action>` naming convention** canonical (lowercase, dot-separated): `task.complete`, `ss_cert.approve`, `cash_receipts.approve`, `safety_program.approve`, ~34+ entries today. Validation enforced at config load (cross-references `ActionConfig.handler` against dict keys); naming enforced by code review.

Kept as flat dict rather than promoting to per-primitive `register_triage_handler` registry — handler keys are stable (workflow arc Phase 8b/8c/8d added new keys without churning existing ones); 34 entries today + ~50 at saturation is manageable.

### Current Implementations

11 platform queues registered at September scope: `task_triage`, `ss_cert_triage`, `cash_receipts_matching_triage`, `month_end_close_triage`, `ar_collections_triage`, `expense_categorization_triage`, `aftercare_triage`, `catalog_fetch_triage`, `safety_program_triage`, `email_unclassified_triage`, `workflow_review_triage`.

### Current Divergences from Canonical

1. **Missing `vertical_default` scope** (B-TRIAGE-1). Current cascade is two-scope (platform_default + tenant_override). Migration target ~200 LOC + data migration adding the middle layer. Per R-8 audit Tier 2 §8.
2. **Three-optional-fields source pattern** (B-TRIAGE-3). Current `types.py:233-235` carries `source_direct_query_key`, `source_saved_view_id`, `source_inline_config` as three Optional fields with "Exactly one of..." comment + runtime validator. Migration target ~50 LOC to Pydantic v2 discriminated union.
3. **`source_inline_config` transitional**. Workaround for entities not in Phase 2 saved-view registry yet; sunset target once registry coverage complete.

### Cross-References

- **§7 Composition action types** — canonical reference pattern; same `register_*` + singleton + side-effect-import shape.
- **Phase 5 Triage Workspace** (CLAUDE.md §14) — architectural framing + canonical 7-component config shape.
- **§16 Agent kinds** — workflow arc Phase 8b/8c/8d migrations route agent approvals through triage queues; handler-dispatch dict is the integration seam.
- **Pattern 1 (three-scope inheritance)** — divergence target.

---

## 16. Agent kinds

**Maturity**: `[~ partial — see Current Divergences]`

### Purpose

Accounting agents are the substrate Bridgeable's nightly + weekly + monthly + annual accounting automation runs on. Each agent kind (month_end_close, ar_collections, cash_receipts_matching, 12 total at September scope) extends `BaseAgent` ABC + registers against an `AgentJobType` enum value + runs through the canonical AgentRunner orchestrator.

The category exists so accounting automation is configuration-driven: per-tenant `agent_schedules` rows fire registered agent kinds on cron; runners execute steps; anomalies surface; approval gate or triage queue routes operator action; financial writes occur post-approval.

### Input Contract

`BaseAgent` ABC at `backend/app/services/agents/base_agent.py:53`. Required class attributes + abstractmethod:

```python
class BaseAgent(ABC):
    STEPS: list[str]  # ordered step names
    APPROVAL_FLOW: ApprovalFlow  # canonical metadata (B-AGENT-3 target)

    @abstractmethod
    def run_step(self, step_name: str) -> StepResult: ...
```

Each agent declares an `AgentJobType` enum value (closed-vocabulary discriminator per B-AGENT-2) + registers via `register_agent(job_type, agent_class)` (B-AGENT-1 target). Constructor receives `job: AgentJob` + `db: Session`.

`ApprovalFlow` enum (B-AGENT-3 target):

```python
class ApprovalFlow(str, Enum):
    FULL = "full"             # period lock + statement run (month_end_close, year_end_close)
    SIMPLE = "simple"         # no period lock (weekly agents, 1099_prep, annual_budget, tax_package)
    TRIAGE_MIGRATED = "triage_migrated"  # routes through triage queue, no approval gate
```

Canonical metadata on agent class; replaces `SIMPLE_APPROVAL_TYPES` set-based discriminator at `approval_gate.py:198-209`.

### Output Contract

`StepResult` dataclass — per-step outcome:
- `status`: `success | warning | error`
- `message`: human-readable summary
- `data`: step-specific payload (JSONB)
- `anomalies`: list of `AgentAnomaly` records created during step

Per-job aggregate written to `agent_jobs.report_payload` JSONB — final HTML/PDF report served via approval-gate email or triage queue context panel.

### Guarantees

- **Tenant isolation**: every agent receives `job.tenant_id`; queries filter by it; financial writes hit `Company.id == tenant_id` only.
- **Dry-run safety**: `guard_write()` on BaseAgent raises `DryRunGuardError` if dry_run + handler tries to write. Period-pre-flight runs in dry_run; commit runs in non-dry-run after approval.
- **Per-step transactionality**: each `run_step` is one transaction; failures don't corrupt prior step state.
- **Anomaly schema canonical**: `AgentAnomaly` rows with `severity: AnomalySeverity` enum (CRITICAL, WARNING, INFO); operator triage routes through severity-ordered queues.
- **Approval gate canonical**: financial writes blocked until `agent_jobs.status == "approved"` (FULL or SIMPLE paths) OR triage action handler invokes the agent's commit path (TRIAGE_MIGRATED path).

### Failure Modes

- Step raises exception → caught by AgentRunner, marked `errored`, anomaly captured with stack trace, job status `failed`.
- Period-lock violation (financial write into locked period) → `PeriodLockedError` (HTTP 409) at `sales_service` / `journal_entry_service` boundary.
- Approval token expired → 410 at approval-gate endpoint; admin must retrigger job.
- Cross-tenant `job_id` → 404 (existence-hiding).

### Configuration Shape

**Per-tenant scheduling**: `agent_schedules` table — `tenant_id`, `job_type` (FK to `AgentJobType` enum value), `cron`, `enabled`, `dry_run_default`. Pattern 5 (configuration is data).

**`AgentJob` row state machine**: `pending → running → awaiting_approval → approved → complete` (or `rejected` / `failed`). Triage-migrated agents skip `awaiting_approval` state; commit on operator action.

**No multi-scope cascade**: agent classes are platform-coded; per-tenant variation is via scheduling + per-tenant data + approval flow choice.

### Registration Mechanism

**Two-tier classification** (B-AGENT-2 canonical pattern — multiple closed-vocabulary discriminators within a single category; Meta-Pattern 3 sub-pattern):

- **`AgentJobType` enum**: Tier R2 closed-vocabulary at `app.schemas.agent`. Describes WHAT agent states exist. Adding a new agent kind requires enum extension first (coordinated migration). Caller-facing surface (API endpoints, `agent_schedules.job_type` FK, `agent_jobs.job_type` column) depends on enum stability.
- **`AGENT_REGISTRY` extensible dict**: Tier R1 target — `register_agent(job_type, agent_class)` + side-effect-import seed from `app/services/agents/__init__.py`. Describes HOW handlers register.

This pattern (closed-vocabulary discriminator + extensible registry) is canonical for categories where the operator-facing surface needs enumeration stability but the implementation registry is open.

### Current Implementations

12 agents registered today (per `agent_runner.py:31-54` lazy-load list): `month_end_close`, `ar_collections`, `unbilled_orders`, `cash_receipts_matching`, `expense_categorization`, `estimated_tax_prep`, `inventory_reconciliation`, `budget_vs_actual`, `1099_prep`, `annual_budget`, `year_end_close`, `tax_package`.

Approval flow distribution per `SIMPLE_APPROVAL_TYPES` (`approval_gate.py:198-209`): FULL (month_end_close, year_end_close); SIMPLE (10 others); TRIAGE_MIGRATED (workflow arc Phase 8b cash_receipts_matching + Phase 8c month_end_close, ar_collections, expense_categorization — coexistence: legacy approval path still works for forensic re-runs, triage is canonical for routine processing).

### Current Divergences from Canonical

1. **Lazy `_ensure_registry()` pattern** at `agent_runner.py:26-54` instead of side-effect-import. Imports happen inside the method to avoid circular imports. Migration target ~30 LOC per B-AGENT-1: move 12 imports + 12 registrations into `app/services/agents/__init__.py`; drop `_ensure_registry`; add import-time integration test verifying registry has expected 12 entries. Circular-import concern from Phase 1 has been resolved by workflow-arc import reorganization.
2. **`SIMPLE_APPROVAL_TYPES` set-based discriminator** at `approval_gate.py:198-209` instead of `ApprovalFlow` enum class attribute. Migration target ~80 LOC per B-AGENT-3: promote to enum + class attribute on each agent. Triage-migrated workflow arc agents would land as `ApprovalFlow.TRIAGE_MIGRATED` cleanly.

### Cross-References

- **§9 Email providers** — canonical Tier R1 register_provider pattern. B-AGENT-1 migration adopts this shape.
- **§15 Triage queue configs** — workflow arc Phase 8b/8c/8d migrations route agent approvals through triage. Handler-dispatch dict is the integration seam.
- **Phase 1 Accounting Agent Infrastructure** (CLAUDE.md §14) — architectural framing + 12-agent inventory.
- **Workflow arc Phase 8b cash_receipts** — first agent-to-workflow migration; established the parity-test discipline R-9 inherits.

---

## 17. Button kinds

**Maturity**: `[~ partial — see Current Divergences]`

### Purpose

Button kinds are the client-side dispatch substrate for R-4 buttons in the runtime editor + Pulse home + spaces. Each button registration declares an action type (navigate, open_focus, trigger_workflow, etc.) + per-button parameter bindings + success behavior. The dispatch resolves bindings against React context (auth, route params, focus) + invokes the handler.

The category exists so admins compose buttons as data (a saved-view trigger button, a workflow-firing button on a kanban card) without React code per button. R-4.0 shipped the substrate; this section documents the contract.

### Input Contract

`R4ButtonContract` at `frontend/src/lib/runtime-host/buttons/types.ts:103-121`:

```typescript
type R4ButtonContract = {
  actionType: R4ActionType;  // closed type-union discriminator
  actionConfig: ActionConfig;  // per-action-type config dict
  parameterBindings: ParameterBinding[];  // up to 7 sources
  successBehavior?: SuccessBehavior;  // toast, navigate, refresh, none
};
```

`R4ActionType` type-union at `types.ts:37-42` (B-BTN-2 canonical surface — TypeScript equivalent of Tier R2 closed-vocabulary):

```typescript
type R4ActionType =
  | "navigate"
  | "open_focus"
  | "trigger_workflow"
  | "create_vault_item"
  | "run_playwright_workflow";
```

### Output Contract

`Handler` signature:

```typescript
type Handler = (
  config: ActionConfig,
  bindings: ResolvedBindings,
  deps: HandlerDeps,
) => Promise<ActionResult>;

type ActionResult = {
  success: boolean;
  errorMessage?: string;
  navigateTo?: string;  // routes via deps.navigate if set
};
```

`deps` carries React-bound capabilities: `deps.navigate` (react-router useNavigate), `deps.openFocus` (focus context openFocus), `deps.apiClient` (axios). Handler returns `ActionResult` for the dispatch caller to drive UI feedback (toast, navigate).

### Guarantees

- **Stateless**: handlers are pure functions; no per-button state. Side effects are entirely via `deps` (navigate, API calls, focus opening).
- **Type-safe dispatch**: TypeScript exhaustive-check on `Record<R4ActionType, Handler>` at compile time — forgotten action type fails compile.
- **Tree-shakeable**: bundle includes only registered handlers (compile-time `Record` literal, not runtime registry).
- **Client-side only**: buttons fire in browser context; server-side equivalent is §12 Workflow node types (deliberately parallel — see Meta-Pattern 3 sub-pattern: category-clusters).

### Failure Modes

- Handler returns `{success: false, errorMessage: "..."}` → dispatch surfaces toast.
- Handler throws → dispatch catches, treats as failure, surfaces generic error toast.
- Missing required binding → dispatch returns failure result without invoking handler.
- Unknown `actionType` at runtime → TypeScript prevents (compile error); not reachable in deployed code.

### Configuration Shape

Per-button `R4ButtonContract` lives on button registration metadata (the registry described in CLAUDE.md §4 Component Registry). Per Pattern 5 (configuration is data).

**Platform-only**: button registrations are code (not per-tenant); per-tenant variation is via the per-user edge-panel substrate (R-5.1) layering user overrides over platform-default registrations.

### Registration Mechanism

**Canonical Tier R2**: `DISPATCH_HANDLERS: Record<R4ActionType, Handler>` at `frontend/src/lib/runtime-host/buttons/action-dispatch.ts:225-233` — TypeScript Record-literal as dispatch surface; type-union as discriminator surface.

```typescript
export const DISPATCH_HANDLERS: Readonly<Record<R4ActionType, Handler>> = {
  navigate: handleNavigate,
  open_focus: handleOpenFocus,
  trigger_workflow: handleTriggerWorkflow,
  create_vault_item: handleCreateVaultItem,
  run_playwright_workflow: handleRunPlaywrightWorkflow,
};
```

Adding a new action type is an explicit type-union extension (B-BTN-2). Compile-time exhaustive checking forces every dispatch consumer to acknowledge it; no runtime registration needed; bundle stays tree-shakeable.

**Parameter binding sources** (B-BTN-3) — Tier R4 hardcoded resolver branches at `parameter-resolver.ts` (7 sources: literal, current_user, current_tenant, current_date, current_route_param, current_query_param, current_focus_id). Parallel to server-side workflow parameter bindings (11 prefixes at `workflow_engine.py:47-182`). Two parallel categories — see Meta-Pattern 3 sub-pattern: category-clusters. Future Tier R1 promotion deferred until concrete signal warrants.

### Current Implementations

5 action types registered today: `navigate`, `open_focus`, `trigger_workflow`, `create_vault_item`, `run_playwright_workflow`. Adding a 6th is a type-union extension + Record entry + new handler module (3-step recipe documented in CLAUDE.md §14 Phase R-4.0 entry).

### Current Divergences from Canonical

None substantive at Button kinds proper. The `~ partial` grade was based on "no vertical/tenant scope on button registrations" — but button registrations are intentionally platform-only per Pattern 5 + R-5.1 user-override substrate handling per-tenant variation. Canonical-by-shape at registration + dispatch level.

The two flagged items (B-BTN-3 hardcoded parameter binding resolver branches; parallel client/server source binding registries) are canonical category-clusters per Meta-Pattern 3 — separate sections cross-referenced rather than forced structural unification.

### Cross-References

- **§12 Workflow node types** — server-side parallel; deliberately parallel catalogs (B-BTN-1) because client-side React-bound dispatch fundamentally differs from server-side SQLAlchemy-bound dispatch. Same authoring conventions (action_type discriminator + Record/dict dispatch); different runtime contexts.
- **R-4.0 Buttons as composable components** (CLAUDE.md §14) — substrate framing + 5-action-type catalog + parameter binding canon.
- **R-5.0 Edge panel substrate** (CLAUDE.md §14) — first concrete consumer of R-4 buttons inside another registered component.
- **CLAUDE.md §4 Component Registry** — overall composable-component registration substrate; buttons join via `extensions.r4` field on registration metadata.

---

## 18. Intake match-condition operators

**Maturity**: `[~ implicit pattern]`

### Purpose

Intake match-condition operators are the closed-vocabulary discriminators Tier 1 deterministic rules evaluate against canonical records produced by intake adapters (§1). Each adapter type (email / form / file) declares its own operator catalog tuned to the source's candidate fields. Rules combine operators via AND-within-rule + OR-within-operator semantics so tenants compose precise routing decisions without engine changes.

The category exists so admin-authored Tier 1 rules (`tenant_workflow_email_rules.match_email / match_form / match_file`) route inbound traffic deterministically before LLM cascade fallback (Tier 2 taxonomy + Tier 3 registry). Adapter-specific operator catalogs preserve clarity over speculative cross-source unification per R-6.2a signal-driven canon.

### Input Contract

Each operator catalog is a closed vocabulary of operator keys evaluated against the canonical adapter record. Operator evaluation at `backend/app/services/classification/tier_1_rules.py:11-31` (module docstring enumerates all three catalogs):

- **Email operators** (5): `sender_email_in`, `sender_domain_in`, `subject_contains_any`, `body_contains_any` (first 4KB), `thread_label_in` — evaluated by `match_email_message` at `tier_1_rules.py:85`.
- **Form operators** (5): `form_slug_equals`, `field_value_equals`, `field_value_contains`, `submitter_email_in`, `submitter_domain_in` — evaluated by `match_form` at `tier_1_rules.py:155`.
- **File operators** (5): `file_adapter_slug_equals`, `content_type_in`, `filename_contains_any`, `uploader_email_in`, `uploader_domain_in` — evaluated by `match_file` at `tier_1_rules.py:255`.

Operator config is a dict keyed by operator name with value-shape determined by operator semantics (list of strings for `*_in` operators, single string for `*_equals`, etc.).

### Output Contract

Each operator evaluator returns `bool`. Match function returns `bool` indicating whether the full rule's operator set matched.

### Guarantees

- **AND-within-rule + OR-within-operator** semantics: a rule with `{sender_domain_in: [...], subject_contains_any: [...]}` matches when BOTH operators match; each operator matches if ANY of its values match.
- **Closed vocabulary per adapter**: invalid operator key in rule config rejected at evaluation time (KeyError surfaced).
- **No silent fall-through**: operators evaluated exhaustively; missing required candidate fields → operator returns False rather than crash.
- **Pure-function evaluation**: each operator is stateless; no DB queries, no side effects.

### Failure Modes

- Invalid operator key → KeyError at `_evaluate_operator` dispatch
- Malformed operator config (wrong value shape) → TypeError surfaced verbatim
- Missing candidate field on source record → operator returns False (treated as non-match, not error)

### Configuration Shape

Match conditions stored as JSONB inside `tenant_workflow_email_rules.match_email / match_form / match_file` columns. Rule rows are tenant-owned (created via admin Tier 1 rule authoring UI). Per-adapter columns enforce adapter-type discriminator: a rule targeting email cannot accidentally match form/file traffic.

### Registration Mechanism

**Tier R3 partial**. Closed vocabulary frozen in code; no `register_operator` API. Adding a new operator to an existing adapter = source edit + frontend mirror update (no migration). Adding cross-source operators deferred per R-6.2a canon ("Cross-source operator unification is signal-driven, not speculative").

### Current Implementations + Cross-References

- Backend evaluators at `tier_1_rules.py:85` (email), `:155` (form), `:255` (file)
- Frontend mirror at `frontend/src/components/email-classification/MatchConditionsEditor.tsx` + `RulesTable.tsx:56-58` (operator-key dispatch) + `AuthorRuleFromEmailWizard.tsx:132,135` (heuristic emits operator keys)
- CLAUDE.md §14 R-6.1a + R-6.2a — Tier 1 rule substrate + cross-source canon
- §1 Intake adapters — operators consume canonical adapter records

### Current Divergences from Canonical

1. **Cross-source operator unification deferred** (CLAUDE.md §14 R-6.2a canon): single operator vocabulary across email + form + file would conflate canonical adapter-specific candidate fields. Deferred until concrete cross-adapter rule pattern emerges from production tenant authoring.
2. **Frontend-backend symmetry not lint-enforced**: MatchConditionsEditor + RulesTable + AuthorRuleFromEmailWizard hardcode operator-key dispatch; drift detectable via test gate (deferred per R-8.2 precedent unless drift surfaces).

---

## 19. Notification categories

**Maturity**: `[✓ canonical — reclassified R-8.y.c investigation]`

### Purpose

Notification categories are the closed-vocabulary classification keys carried on `notifications.category` (`backend/app/services/notifications/category_types.py`). Each category corresponds to a distinct platform notification source (delivery_failed, share_granted, signature_requested, compliance_expiry, account_at_risk, calendar_*, etc.); category drives default icon + color rendering hints + admin notification preferences (future).

The category exists so notification routing + filtering + per-user preferences (deferred) operate against a stable enumeration rather than ad-hoc strings sprinkled across caller modules. R-8.1 shipped the registry post-audit, replacing the ~18 implicit category strings called out in R-8 audit Section 2 item 4.

**Reclassification context**: R-8 audit graded this category `×` ("Should be a category catalog"). R-8.1 shipped the registry at `category_types.py` between audit and this documentation pass; R-8.y.c reclassifies as ✓ canonical via the delta-update pattern established by R-8.y.b Calendar reclassification.

### Input Contract

Callers pass a `category: str` key when creating notifications:

```python
notification_service.create_notification(
    db,
    user_id=...,
    company_id=...,
    type="info" | "success" | "warning" | "error",  # tone discriminator
    category="share_granted",                        # category discriminator (validated)
    title=...,
    body=...,
    severity=...,           # optional alert-flavor field
    source_reference_type=..., source_reference_id=...,  # optional linkage
)
```

`category` validated at create-time via `assert_valid_notification_category(category)` (`category_types.py:173`).

### Output Contract

`NOTIFICATION_CATEGORY_REGISTRY` exposes per-key metadata:

```python
{
    "category": str,                  # canonical key
    "description": str,               # operator-facing
    "default_icon": str,              # Lucide icon name
    "default_color_token": str,       # DESIGN_LANGUAGE token
}
```

`NOTIFICATION_CATEGORIES` frozenset exposes the full enumeration for validation + iteration.

### Guarantees

- **Closed vocabulary**: 18 canonical entries at `NOTIFICATION_CATEGORY_REGISTRY` (`category_types.py:43`); unknown category at create-time raises `UnknownNotificationCategoryError` (typed exception at `:151`).
- **Pure-function validation**: `validate_notification_category(category)` + `assert_valid_notification_category(category)` at `:160,173` are stateless; no DB queries.
- **Tenant isolation**: category is platform-global metadata; per-tenant notifications carry `company_id` on the Notification row; category itself is not scoped.
- **Frozen set discipline**: frontend dispatches on `Notification.type` (info/success/warning/error tone) NOT category — module docstring at `:23-28` documents this explicitly; no frontend-backend symmetry contract required.

### Failure Modes

- Unknown category → `UnknownNotificationCategoryError` (typed; translatable to HTTP 400 at caller boundary)
- Type mismatch (non-string category) → TypeError at validation helper

### Configuration Shape

N/A — category catalog is code-defined; no per-instance configuration. Per-notification rows carry category as a string column on `notifications`; registry validates write-time only.

### Registration Mechanism

**Tier R1 — canonical**. Closed-vocabulary frozenset + typed validation + caller boundary enforcement. Adding a new category = single-line addition to `NOTIFICATION_CATEGORY_REGISTRY` dict; frozenset rebuilds automatically. R-8.1 module docstring at `:1-33` explicitly cites R-8 audit Section 2 item 4 + R-6.1 DEBT flag closure.

### Current Implementations + Cross-References

- Registry: `backend/app/services/notifications/category_types.py` (191 LOC)
- 18 canonical categories: `share_granted`, `delivery_failed`, `signature_requested`, `compliance_expiry`, `account_at_risk`, `calendar_attendee_responded`, `calendar_consent_upgrade_request`, `calendar_consent_upgrade_accepted`, `calendar_consent_revoked`, `employee_*`, `system_*`, etc.
- Caller integration: `notification_service.create_notification` at `notifications/service.py` + `notify_tenant_admins` fan-out helper
- CLAUDE.md §14 R-8.1 entry — post-audit registry shipment record
- §20 Activity log event types — sibling reclassification (R-8.2)

---

## 20. Activity log event types

**Maturity**: `[✓ canonical — reclassified R-8.y.c investigation]`

### Purpose

Activity log event types are the closed-vocabulary classification keys carried on `activity_logs.activity_type` (`backend/app/services/crm/activity_log_types.py`). Each type corresponds to a distinct V-1c CRM activity feed event source (email, calendar, manual note, call, document, follow_up, status_change, delivery, invoice, order, payment, proof, case, legacy_proof); type drives the activity-feed verb rendered in `RecentActivityWidget.activityVerb` map.

The category exists so V-1c activity feed rendering + filtering operates against a stable enumeration rather than ad-hoc strings duplicated between backend write paths + frontend render dispatch. R-8.2 shipped the registry post-audit, replacing the implicit activity_type strings called out in R-8 audit Section 2 item 5.

**Reclassification context**: R-8 audit graded this category `~` (verb-resolution duplicated between backend + frontend). R-8.2 shipped the registry at `activity_log_types.py` between audit and this documentation pass; R-8.y.c reclassifies as ✓ canonical via the delta-update pattern.

### Input Contract

Callers pass an `activity_type: str` key when writing activity log rows:

```python
activity_log_service.log_event(
    db,
    company_id=...,
    company_entity_id=...,
    activity_type="email",          # validated
    actor_user_id=...,
    title=..., body=...,
)
```

`activity_type` validated via `assert_valid_activity_type(activity_type)` (`activity_log_types.py:116`).

### Output Contract

`ACTIVITY_TYPE_REGISTRY` exposes per-key metadata:

```python
{
    "activity_type": str,    # canonical key
    "display_label": str,    # admin-facing
    "description": str,      # operator-facing
}
```

`ACTIVITY_TYPES` frozenset exposes full enumeration.

### Guarantees

- **Closed vocabulary**: 15 canonical entries at `ACTIVITY_TYPE_REGISTRY` (`activity_log_types.py:28`); unknown type raises `UnknownActivityTypeError` (typed at `:99`).
- **Pure-function validation**: `validate_activity_type` + `assert_valid_activity_type` at `:108,116` stateless; no DB queries.
- **Tenant isolation**: activity rows carry `company_id`; type catalog is platform-global metadata.
- **Append-only**: activity_logs rows immutable post-write per V-1c canon; type strings on existing rows never change retroactively.

### Failure Modes

- Unknown activity_type → `UnknownActivityTypeError` (typed; HTTP 400 at caller boundary)
- Type mismatch → TypeError at validation helper

### Configuration Shape

N/A — type catalog is code-defined; no per-instance configuration. `activity_logs.activity_type` column carries the validated string.

### Frontend-backend symmetry contract

**Canonical invariant (R-8.2 documented at module docstring `activity_log_types.py:14-17`)**: every registry key MUST have a corresponding entry in the frontend `activityVerb` map at `RecentActivityWidget.tsx`. Cross-tier vocabulary parity is the canonical interface — drift between backend write paths + frontend render dispatch produces silent rendering gaps (unknown type → "logged an activity" fallback verb).

**Symmetry enforcement**: lint-or-test enforcement deferred unless drift surfaces. Module docstring documents the expectation; future R-8.x sub-arc can promote to a Vitest cross-reference test (registry keys parity-match `activityVerb` dispatch) when concrete drift emerges. This is R-8.y.b Meta-Pattern 2 applied to cross-tier vocabulary: document honesty now, migrate fragility when needed.

This is the **first contract in PLUGIN_CONTRACTS.md to declare an explicit cross-tier vocabulary parity invariant**. Future cross-tier closed-vocabulary categories (e.g. §18 intake operators frontend mirror) follow this pattern when symmetry warrants explicit documentation.

### Registration Mechanism

**Tier R1 — canonical**. Closed-vocabulary frozenset + typed validation + frontend-symmetry contract documented. Adding a new activity_type = single-line addition to `ACTIVITY_TYPE_REGISTRY` dict + corresponding `activityVerb` entry in frontend mirror.

### Current Implementations + Cross-References

- Registry: `backend/app/services/crm/activity_log_types.py` (129 LOC)
- 15 canonical types: `note`, `call`, `email`, `calendar`, `meeting`, `document`, `follow_up`, `status_change`, `delivery`, `invoice`, `order`, `payment`, `proof`, `case`, `legacy_proof`
- Caller integration: `activity_log_service.log_event` + V-1c migration callers (delivery, calendar, email, etc.)
- Frontend dispatch: `frontend/src/components/widgets/RecentActivityWidget.tsx::activityVerb` map
- CLAUDE.md §14 R-8.2 entry — post-audit registry shipment record
- §19 Notification categories — sibling reclassification (R-8.1)

---

## 21. PDF generator callers

**Maturity**: `[~ implicit pattern]`

### Purpose

PDF generator callers are the substrate caller modules that emit PDF documents via the unified `document_renderer.render()` entry path. Each generator (statement, disinterment, price_list, invoice-preview, wilbert engraving form) consumes managed templates from the document template registry + produces canonical `Document` + `DocumentVersion` rows via the Phase D-1 backbone.

The category exists so PDF generation routes through a single canonical surface (`document_renderer.render(template_key=...)`) rather than direct WeasyPrint calls scattered across the codebase. The canonical entry path enables template versioning, R2 archival, tenant template overrides, and unified rendering audit per Phase D-2/D-3.

### Input Contract

Canonical entry: `document_renderer.render(template_key, context, *, company_id, entity_type, entity_id, caller_module, ...)` at `backend/app/services/documents/document_renderer.py`. Each generator wraps this with domain-specific context resolution + entity linkage.

5 canonical generators today:
- `statement_pdf_service.py:30,193` — `template_key="statement.*"` (per-vertical variants)
- `disinterment_pdf_service.py:30,85,116,125` — `template_key="disinterment.release_form"` + download_bytes fallback
- `price_list_pdf_service.py:207,232,257,261,268` — `template_key="price_list.*"`
- `pdf_generation_service.py:400-430` — invoice preview path via `render_html` (admin tool)
- `wilbert_utils.render_form_pdf` — `template_key="urn.wilbert_engraving_form"` (D-9 migration)

### Output Contract

Each call produces canonical `Document` + `DocumentVersion` rows + writes PDF bytes to R2 at `tenants/{company_id}/documents/{document_id}/v{n}.pdf`. Generators return the Document handle for caller-side linkage; legacy bytes-returning APIs preserved as thin wrappers calling `download_bytes(doc)`.

### Guarantees

- **Single canonical entry path**: every PDF emit routes through `document_renderer.render` (verified by D-2 lint test `test_documents_d2_lint.py::test_weasyprint_import_forbidden_outside_documents`)
- **Tenant isolation**: `company_id` required on every render; surfaces in Document row + R2 storage key
- **Template versioning**: each render captures the active `DocumentTemplateVersion` at write time; re-render after template update produces new version
- **Audit linkage**: `caller_module` + `caller_entity_*` populate Document linkage fields
- **R2 archival**: rendered bytes uploaded to R2 with presigned download URLs (1h TTL)

### Failure Modes

- Unknown `template_key` → `TemplateNotFound` (404 at API boundary)
- WeasyPrint rendering exception → `RenderError` with template + context details
- R2 upload failure → `StorageError`; Document row not created (atomic)

### Configuration Shape

Per-tenant template overrides flow through the document template registry (`document_templates` + `document_template_versions` tables, three-scope cascade per Pattern 1). Generator code is the substrate; templates are the configuration.

### Registration Mechanism

**Tier R2 partial**. Caller surface honestly documented; no `register_pdf_generator` API. Adding a new generator = create the wrapper module + register its templates in the document template registry + call `document_renderer.render` from the wrapper. The 5 transitional WeasyPrint sites permanently allowlisted per D-2 lint test invariant are the only generators NOT routing through `document_renderer.render` today; lint test fails if a 6th appears.

### Current Implementations + Cross-References

- 5 canonical generators routing through `document_renderer.render` (listed above)
- 3 transitional WeasyPrint allowlist entries (`pdf_generation_service.generate_template_preview_pdf`, `quote_service.generate_quote_pdf`, `wilbert_utils` legacy path) — D-9 closes these
- CLAUDE.md §14 Phase D-1/D-2/D-9 — Document backbone + template registry + WeasyPrint migration arc
- §4 Document blocks — block-level composition substrate (upstream of PDF rendering)
- D-2 lint gate: `backend/tests/test_documents_d2_lint.py`

### Current Divergences from Canonical

1. **3 transitional WeasyPrint allowlist entries** preserved at D-2 lint test invariant; each documented for D-9 migration consideration. The lint test prevents new direct WeasyPrint usage; existing entries migrate as templates land in the registry.

---

## 22. Page contexts

**Maturity**: `[~ implicit pattern]`

### Purpose

Page contexts are the substrate the runtime editor (R-1) dispatches against to resolve a route's editing context. Each page in the tenant app maps to a `pageContext` key + display `label` via `PAGE_CONTEXT_MAP` at `frontend/src/lib/runtime-host/page-contexts.ts:21-30`. Runtime editor uses the context to scope edits, surface contextual affordances, and gate per-page customization.

The category exists so the runtime editor operates against a stable route → context registry rather than per-page hardcoded logic. Page contexts are a flat data registry consumed by R-1 runtime editor dispatch.

### Input Contract

`resolvePageContext(pathname: string): {pageContext, label, mapped}` at `page-contexts.ts`. Pattern matching supports `:param` segments (e.g. `/cases/:id`) and `*` wildcards; first-match-wins from the ordered `PAGE_CONTEXT_MAP` array.

`PageContextEntry`:
```typescript
interface PageContextEntry {
  pattern: string;       // route pattern with :param + * support
  pageContext: string;   // canonical context key
  label: string;         // operator-facing label
}
```

### Output Contract

```typescript
{
  pageContext: string;   // matched context OR "unmapped:{path}" fallback
  label: string;
  mapped: boolean;       // true if a pattern matched
}
```

### Guarantees

- **First-match-wins**: pattern order in `PAGE_CONTEXT_MAP` determines resolution
- **Pure-function lookup**: route → context is stateless; no DB queries
- **Graceful fallback**: unmapped routes return `pageContext: "unmapped:{path}"` allowing R-1 to surface a warning without crashing
- **Closed vocabulary at September scope**: 20 canonical routes today; expansion is a code edit

### Failure Modes

- No pattern matches → `mapped: false` + `pageContext: "unmapped:{path}"`; runtime editor surfaces an "unmapped route" warning indicator

### Configuration Shape

N/A — frozen `PAGE_CONTEXT_MAP` array in code; no per-tenant configuration. Pattern is the runtime editor's single source of truth.

### Registration Mechanism

**Tier R3 partial**. Frozen table; no `register_page_context` API. Adding a new route = source edit appending to `PAGE_CONTEXT_MAP`. R-8 audit Tier 3 §10 explicitly defers refactoring threshold until ≥50 routes; at 20 routes today, frozen-table pattern suits the scale.

### Current Implementations + Cross-References

- Registry: `frontend/src/lib/runtime-host/page-contexts.ts:1-31` (introductory comment documents extension path)
- 20 canonical routes mapped today (dashboard, cases, scheduling, orders, deliveries, accounting, etc.)
- CLAUDE.md §14 R-1 entry — runtime editor canon + page context registry reference
- §3 Widget kinds — sibling flat-data registry pattern at backend (page contexts are the frontend parallel for route → context resolution)

### Current Divergences from Canonical

1. **Refactoring threshold deferred** per R-8 audit Tier 3 §10: promote to `register_page_context(entry)` API when route count exceeds ~50 OR when per-vertical page context overrides emerge. At September scope (20 routes), frozen table is appropriate.

---

## 23. Customer classification rules

**Maturity**: `[RESERVED — Phase 2b after B-CLASSIFY-1/2/3 direction]`

Phase R-8.y.c Phase 2a defers this section to Phase 2b pending direction on three Type B calls surfaced by the investigation (B-CLASSIFY-1: vertical-plug-in classifiers vs module-level regex; B-CLASSIFY-2: tenant-overridable thresholds; B-CLASSIFY-3: standalone section vs CRM substrate parent). Investigation report at `/tmp/r8_y_c_implicit_contracts_findings.md` §9. Phase 2b ships the full 8-section contract once direction settles.

---

## 24. Intent classifiers

**Maturity**: `[~ implicit pattern]`

### Purpose

Intent classifiers are the substrate the command bar + NL Creation overlay dispatch against to resolve user query intent. Backend `command_bar/intent.py` classifies queries into a closed 5-value vocabulary; frontend `detectNLIntent.ts` mirrors the classification for NL Creation overlay activation. The category exists so intent dispatch operates against a stable enumeration + dispatchable handlers rather than ad-hoc string matching per consumer.

### Input Contract

**Backend** (`backend/app/services/command_bar/intent.py:42`):
- `Intent = Literal[...]` — 5-value closed vocabulary
- `_CREATE_VERBS` at `:56` + `_NAVIGATE_VERBS` at `:60` — hand-maintained verb arrays
- `_RECORD_NUMBER_RX` at `:71` — record-number regex (prefix+numeric shape)
- `classify(query: str) → Intent` at `:80` — pure-function dispatch

**Frontend** (`frontend/src/components/nl-creation/detectNLIntent.ts:88`):
- `detectNLIntent(query: string)` — derives patterns from `getActionsSupportingNLCreation()` at runtime per Phase 5 actionRegistry reshape canon (supersedes hand-maintained ENTITY_PATTERNS table per comment header at `:4`)

### Output Contract

Backend: `Intent` literal value (one of the 5 vocabulary entries) — drives command bar action filtering.

Frontend: NL creation entity type + extracted natural language tail — drives overlay activation.

### Guarantees

- **Closed vocabulary at backend**: 5-value Intent literal; unknown queries default to a fall-through intent (no crash)
- **Pure-function classification**: stateless; no DB queries
- **Frontend dynamic dispatch**: patterns derived from action registry at runtime per Phase 5 reshape — adding a new entity with `supports_nl_creation: true` extends the frontend classifier without code edit

### Failure Modes

- Backend: unrecognized verb → fall-through intent (caller handles)
- Frontend: no pattern match → returns null (overlay does not activate)

### Configuration Shape

N/A at backend — closed vocabulary + hand-maintained verb arrays in code. Frontend derives from action registry; entities opt in via `supports_nl_creation: true` field on their registry entry.

### Registration Mechanism

**Tier R3 partial**. Frontend reshape complete (Phase 5 actionRegistry → action-registry-derived patterns; R2-ish). Backend hand-maintained verbs at `_CREATE_VERBS` + `_NAVIGATE_VERBS` (R3). Adding a new intent vocabulary value = source edit to `Intent` literal + dispatch table.

### Current Implementations + Cross-References

- Backend dispatch: `backend/app/services/command_bar/intent.py:42,80,137,173,210`
- Frontend mirror: `frontend/src/components/nl-creation/detectNLIntent.ts:4,88`
- CLAUDE.md §4 Command Bar Platform Layer — overall substrate
- §7 Composition action types — sibling registry (action registry consumed by both command bar dispatch + NL detection)
- CLAUDE.md §14 Phase 5 — actionRegistry reshape canon

### Current Divergences from Canonical

1. **Backend hand-maintained verbs vs frontend action-registry-derived patterns**: asymmetry by design. Frontend has render-time action registry available; backend dispatches pre-action-resolution. Documented honestly per Meta-Pattern 2 (working code that suits its category; no migration needed).
2. **Record-number regex assumes Bridgeable record-number shape** (numeric + prefix): future verticals with non-numeric record IDs would need regex extension. Bounded scope; flagged for any vertical-expansion arc that introduces alternative record-number formats.

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

### Registration Pattern Tiers (added R-8.y.b Phase 2)

Cross-category nomenclature for registration mechanisms. **Tiers describe patterns, NOT rank.** Tier R2 is canonical for closed-vocabulary platform-owned registries — it is NOT a lesser version of R1. Each tier suits its category; promotion between tiers is appropriate only when concrete signal warrants.

| Tier | Pattern | Canonical for | Categories using this tier |
|---|---|---|---|
| **R1** | Side-effect-import + `register_*` API + ABC/Protocol contract | Extensible plugins where implementations register from their own packages | §1 Intake adapters, §4 Document blocks, §6 Workshop template types, §7 Composition action types, §8 Accounting providers, §9 Email providers, §11 Calendar providers, §14 Delivery channels, §12 Workflow node types (target — currently R4), §16 Agent kinds (target — currently R3) |
| **R2** | Frozen dict / frozenset / type-union constant + validation helpers | Closed-vocabulary platform-owned registries (where vocabulary stability is the canonical interface) | §15 Triage queue configs `HANDLERS` dict, §16 `AgentJobType` enum + `ApprovalFlow` enum, §17 Button kinds `R4ActionType` type-union + `DISPATCH_HANDLERS` Record, §13 Intelligence `IntelligenceError` codes |
| **R3** | Lazy registry (deferred imports inside method; circular-import workaround) | Migration target where promotion to R1 warrants | §16 Agent kinds `AGENT_REGISTRY` lazy `_ensure_registry()` — divergence, R1 target |
| **R4** | If/elif dispatch chain | Migration target where promotion to R1 warrants | §12 Workflow node types `_execute_action` chain — divergence, R-9 target. §17 parameter binding resolver branches — divergence-by-pragmatism, R1 promotion deferred per category-cluster pattern (Meta-Pattern 3) |

**R2 vs R1 is not a hierarchy.** R2 is canonical when the enumeration IS the operator-facing surface (e.g. `AgentJobType` is referenced by `agent_schedules.job_type` FK + API endpoint params; promoting to runtime string-keyed registry would dissolve the canonical interface). R1 is canonical when implementations register from their own packages (e.g. Email providers; each provider package owns its `register_provider` call). Choose tier per category's natural shape; "lower tier number" does not mean "more correct."

### Meta-Pattern 1: Document what is, not what would be uniform

Canonical contracts honor real distinctions between categories rather than forcing speculative uniformity. R-8.y.b investigation surfaced 23 architectural calls; collaborative deliberation settled them by asking "what does this category ACTUALLY look like at runtime?" rather than "how can we force this to match category X?"

Examples:
- **Per-category output shapes** (Cross-Type-B-1 — option (c) hybrid). Workflow node types, Triage queue configs, Delivery channels have meaningfully different output shapes. Common fields canonicalized; category-specific data stays nested. NO forced cross-category unified `PlatformActionResult` dataclass.
- **Delivery channels Protocol vs Email providers ABC** (B-DELIV-1). Both canonical for their use cases (stateless-dispatch vs stateful-lifecycle). NOT forced into single ABC pattern.
- **Workflow node types vs Button kinds parallel catalogs** (B-BTN-1). Server-side SQLAlchemy-bound vs client-side React-bound. NOT forced into unified action-type registry.

### Meta-Pattern 2: Migrate fragility, document honesty

Two grades of divergences exist; treat them differently.

- **Fragile patterns** (substring-matching error classification, three-optional-fields with runtime validator, silent fall-through that masks bugs) get **canonical-target framing + migration flag**. The current code works but breaks in unobserved ways under stress; document the canonical replacement + estimate migration scope. Examples: EmailChannel retryable substring match (B-DELIV-2, ~30 LOC); TriageQueueConfig three-source pattern (B-TRIAGE-3, ~50 LOC); workflow_engine.py:679 silent `unknown_action_type` fall-through (B-WORK-2, part of R-9).
- **Honest patterns** (per-category output shapes; Protocol-based stateless dispatch; flat HANDLERS dict where keys are stable) get **documented as-is**. Working code that suits its category; no migration needed. Examples: Triage HANDLERS flat dict (B-TRIAGE-2 keep); Button kinds Record-literal (B-BTN-2 keep); Intelligence provider single-implementation state (B-INTEL-1 defer).

The discipline: read the code, decide which grade applies, document accordingly. Don't migrate honest patterns for aesthetic uniformity; don't preserve fragile patterns by calling them honest.

### Meta-Pattern 3: Canonical contracts describe what implementations ARE

Canonical contracts describe what implementations ARE at runtime, not what they SHOULD LOOK LIKE for uniformity. R-8.y.b investigation surfaced four canonical sub-distinctions:

**Sub-pattern: Content-variance vs structural-variance scope cascade.** Some categories vary in CONTENT per scope (a tenant overrides specific theme tokens atop platform defaults — only deltas merge; the full token catalog stays canonical). Other categories vary in STRUCTURE per scope (a tenant forks a workflow template — entire definition replaces). Pattern 1's three-scope cascade applies to both, but the merge semantics differ. Examples: theme tokens (content-variance, merge); workflow templates (structural-variance, first-match-wins fork).

**Sub-pattern: Stateless-dispatch vs stateful-lifecycle contract surfaces.** Protocol is canonical for stateless-dispatch (channels send + return; no per-instance state). ABC is canonical for stateful-lifecycle (providers connect / sync / disconnect; instances carry session + token state). Both canonical; choose per category's runtime shape. Examples: Delivery channels (Protocol); Email + Calendar + Accounting providers (ABC).

**Sub-pattern: Category-clusters — parallel sections for related-but-different runtime contexts.** Some categories have client-side AND server-side parallel surfaces with deliberately separate contracts because runtime contexts differ enough that forcing structural unification would force awkward abstraction. Canonical example: Button kinds (client-side, React-bound, useNavigate hooks) + Workflow node types (server-side, SQLAlchemy-bound, DB session). Both are extensible-dispatch categories with discriminator + handler shape; deliberately documented as parallel sections with cross-references rather than unified. Parameter binding sources are a future category-cluster candidate: 7 client-side button bindings + 11 server-side workflow bindings — same conceptual shape, different runtime contexts.

**Sub-pattern: Multiple closed-vocabulary discriminators within a single category.** Some categories have TWO closed-vocabulary discriminators serving different purposes. Canonical example: Agent kinds. `AgentJobType` enum (Tier R2) describes WHAT agent states exist (operator-facing surface; enum stability is the canonical interface). `ApprovalFlow` enum (Tier R2 target) describes HOW agents route through approval. Both Tier R2; serve orthogonal concerns. `AGENT_REGISTRY` extensible dict (Tier R1) is third-tier on top — describes WHICH handler class implements each enum value.

### Divergence-watching list (R-8.y.a + R-8.y.b)

Implementations flagged in current sections that diverge from canonical contract:

**R-8.y.a divergences (canonical sections):**

1. **Accounting providers** registration via factory if/elif chain instead of `register_provider` API (canonical reference: §9 Email providers' `PROVIDER_REGISTRY`). Future migration arc could lift; bounded ~50 LOC.
2. **Playwright scripts** registration via dict literal instead of `register_*` API (canonical reference: §4 Document blocks' `register_block_kind`). Future migration arc when script count exceeds ~3-4; bounded ~30 LOC.

**R-8.y.b divergences (partial sections — migration targets surfaced):**

3. **Workflow node types**: if/elif dispatch chain (R4 → R1). R-9 design surface. **~900 LOC** (backend ~600 + tests ~200 + frontend ~50 + Playwright regression). Per B-WORK-1 through B-WORK-5.
4. **EmailChannel retryable classification**: substring-matching (Meta-Pattern 2 fragility) → exception class hierarchy. **~30 LOC** R-8.x sub-arc per B-DELIV-2.
5. **Triage queue configs `vertical_default` scope**: two-scope → three-scope cascade. **~200 LOC** R-8.x sub-arc per B-TRIAGE-1.
6. **TriageQueueConfig source discriminator**: three-optional-fields → Pydantic v2 discriminated union. **~50 LOC** R-8.x sub-arc per B-TRIAGE-3.
7. **AGENT_REGISTRY side-effect-import**: lazy `_ensure_registry()` (R3 → R1). **~30 LOC** R-8.x sub-arc per B-AGENT-1.
8. **ApprovalFlow enum on agent classes**: set-based discriminator → typed enum class attribute. **~80 LOC** R-8.x sub-arc per B-AGENT-3.
9. **Source bindings registries** (parallel sections): hardcoded resolver branches (R4 → R1). Two parallel registries — server-side workflow source bindings (~11 prefixes) + client-side button parameter bindings (~7 sources). **~400 LOC** future sub-arc when concrete signal warrants per B-WORK-3 + B-BTN-3 category-cluster pattern.

R-9 is the primary downstream migration arc consuming this document; the 5 R-8.x sub-arcs sequence after R-9 as bounded individual cleanup arcs. R-8.y documents the canonical contract + the divergences; resolving is future migration work.

---

**Document version**: 1.2 (R-8.y.c Phase 2a, 2026-05-11)
**Total contract count**: 23 (13 ✓ canonical + 10 ~ partial/implicit)
**Canonical contract count**: 13 (10 R-8.y.a ✓ + 1 R-8.y.b Calendar reclassification ✓ + 2 R-8.y.c reclassifications ✓: Notification categories §19 + Activity log event types §20)
**Partial/implicit contract count**: 10 (6 R-8.y.b ~ partial + 4 R-8.y.c ~ implicit: §18 Match operators, §21 PDF generators, §22 Page contexts, §24 Intent classifiers)
**Phase 2b reservation**: §23 Customer classification rules pending B-CLASSIFY-1/2/3 direction; ships separately.
**Maintenance**: This document is canonical. Updates land alongside source changes — never in a separate commit. CLAUDE.md §14 Recent Changes entries link back here when categories evolve.
