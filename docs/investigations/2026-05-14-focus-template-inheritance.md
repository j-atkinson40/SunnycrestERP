# Focus Template Three-Tier Inheritance — Investigation

Date: 2026-05-14
Author: investigation by Sonnet (Studio shell arc next-arc scoping)
Status: investigation only; no code, no migrations, no canon edits
Closes question: how should three-tier Focus inheritance ship (Focus Core → Focus Template → Focus), mirroring (or diverging from) the workflow template pattern?

The locked decisions from 2026-05-13 stand and are not relitigated:
1. Tier 3 has full edit power below the core; the core is immutable in identity at Tier 3 (movable/resizable only).
2. Live cascade for v1; versioned cascade Option B close behind. Schema must include `inherits_from_template_id` AND `inherits_from_template_version` from day one — Option B must be additive.
3. One Studio rail section ("Focus Templates"), tier toggle inside.
4. Naming: Tier 1 = Focus Core, Tier 2 = Focus Template, Tier 3 = Focus.
5. In-place Tier 3 editor — tenants edit Focuses from within the Focus itself (runtime-aware editor pattern).
6. No migration. Greenfield. Existing `focus_compositions` rows can be wiped.

---

## Section 1 — Workflow inheritance pattern survey

Two tables back the workflow three-tier model. Files: `backend/app/models/workflow_template.py`, `backend/app/services/workflow_templates/template_service.py:316-462`.

**Table 1: `workflow_templates`** (`r82_workflow_templates`)
- `id` (uuid PK), `scope` ∈ {`platform_default`, `vertical_default`}, `vertical` (nullable; required iff vertical_default), `workflow_type` (slug), `display_name`, `description`, `canvas_state` JSONB, `version` int, `is_active` bool, `created_at/by`, `updated_at/by`.
- CHECK constraints enforce scope ↔ vertical correlation.
- Versioning: every save deactivates the prior active row and inserts a fresh active row at `version+1`. Partial unique on `is_active=true` ensures one active row per `(scope, vertical, workflow_type)` tuple. Older versions accumulate as an audit trail.
- Tenants do **not** get a row in this table. Tier 1 and Tier 2 share the same table, differentiated by `scope`.

**Table 2: `tenant_workflow_forks`**
- `id`, `tenant_id` (FK companies CASCADE), `workflow_type`, `forked_from_template_id` (FK workflow_templates SET NULL), `forked_from_template_version` int (called `forked_from_version`), `canvas_state` JSONB (full graph, not delta), `pending_merge_available` bool, `pending_merge_template_id` (FK SET NULL), `version`, `is_active`, audit cols.
- One active fork per `(tenant_id, workflow_type)` — the service raises if a second fork attempt arrives.

**Resolver** (`template_service.resolve_workflow`, sketched in service): walks tenant fork → vertical_default → platform_default. **First match wins; no overlay merge** ("locked-to-fork"). The rationale lives in the module docstring (`template_service.py:8-16`): canvas_state is a graph, and merging two graphs at read time has no canonical answer. So the tenant fork *replaces* upstream until the tenant explicitly accepts a merge.

**Fork lifecycle**:
- `fork_for_tenant(tenant_id, workflow_type, source_template_id)` clones source's full `canvas_state` into a new TenantWorkflowFork row (`template_service.py:316-362`).
- `mark_pending_merge(workflow_type, vertical, new_template_id)` flips `pending_merge_available=true` on every fork whose `forked_from_template_id` is any *prior* version at the same `(vertical, workflow_type)` (`template_service.py:393-440`). Called automatically on `create_template`/`update_template` at vertical_default scope.
- `accept_merge(tenant_id, workflow_type)` replaces fork's `canvas_state` with the new template's, clears pending flags, bumps fork version.

**Editor surface per tier**:
- Tier 1 + Tier 2: `/studio/workflows` (admin platform) authors workflow_templates rows. Tier-toggle in left rail.
- Tier 3: no dedicated tenant editor today. Phase 4 of the visual editor explicitly punted "tenant Workshop UI for accept/reject" to "Phase 5+" (`template_service.py:455-458`).

**Mutability**: Tier 1+2 mutated only via platform_admin endpoints; Tier 3 fork mutated only via tenant scope (planned). Schema enforces scope ↔ key correlation, not write authority — write authority is route-level (`Depends(get_current_platform_user)` vs tenant `Depends(get_current_user)`).

**Reusability verdict for Focus**: the table-shape pattern is directly reusable. Two divergences are required:

1. **Three-table form, not two.** Workflows fold Tier 1 + Tier 2 into one `workflow_templates` table differentiated by `scope`. Focuses have a stronger distinction — the **Core** is conceptually a registered code component (operational React), while a Template is a per-vertical accessory composition over a chosen Core. A Core has identity (slug, registered React mount, default placement geometry); a Template is a row of accessory placements + inherits-from-core reference. Conflating them in one row with a scope discriminator works but obscures the distinction. **Recommend: three tables** (`focus_cores`, `focus_templates`, `focus_compositions`) or alternatively two tables (`focus_templates` for Tier 1+2 like workflows, `focus_compositions` for Tier 3). See §3.
2. **Delta vs full-replace at Tier 3.** Workflows replace upstream because canvas_state is a graph. Focus accessory layouts are flatter (rows of placements over a 12-column grid; the rows-shape introduced in R-3.0). Delta semantics are tractable here, and the platform's existing edge-panel resolver (`composition_service._apply_placement_overrides`, `composition_service.py:789-876`) already implements add/hide/reorder deltas at the placement level. **Recommend: Focus Tier 3 uses delta semantics**, not locked-to-fork replace. This is the single biggest architectural divergence from workflow and is justified by the simpler underlying shape + the existing edge-panel precedent.

---

## Section 2 — Current Focus model + gaps

**Current table: `focus_compositions`** (`backend/app/models/focus_composition.py`, migrations `r84_focus_compositions` → `r88_focus_compositions_rows` → `r90_drop_legacy_composition_columns` → `r91_compositions_kind_and_pages`):

- `id`, `scope` ∈ {`platform_default`, `vertical_default`, `tenant_override`}, `vertical` nullable, `tenant_id` nullable, `focus_type` (96-char slug), `rows` JSONB (rows-shape per R-3.0), `canvas_config` JSONB (cosmetic), `kind` ∈ {`focus`, `edge_panel`} (R-5.0), `pages` JSONB nullable (R-5.0; edge-panel multi-page), `version`, `is_active`, audit cols.
- CHECK enforces scope ↔ vertical ↔ tenant_id correlation. Versioning identical to workflow templates.
- Partial unique on `is_active=true` per `(scope, vertical, tenant_id, focus_type)`.

**Current scope semantics**: three scopes, single table — first-match-wins resolver (`composition_service.resolve_composition`, `composition_service.py:704-786`) walks tenant_override → vertical_default → platform_default. **Tier 3 already exists today**, but as full-replace at the rows level. There is no inherits-from reference; a tenant_override row is structurally a complete composition. That's the explicit gap.

**Placement model**: `rows` JSONB. Each row carries `column_count` (1-12), `row_height`, `column_widths`, `placements: [{placement_id, component_kind, component_name, starting_column, column_span, prop_overrides, display_config}]`. Nested-rows fields exist as forward-compat (ignored in R-3.0).

**Core vs accessory distinction today**: There is **no schema distinction**. The May 2026 core-plus-accessories canon (CLAUDE.md §"Focus Composition Layer") is enforced by **convention**, not by schema: cores are rendered by code (`SchedulingKanbanCore.tsx`, 1714 LOC), composition rows declare only accessory widgets. `ComposedFocus` (`frontend/src/lib/visual-editor/compositions/ComposedFocus.tsx`) wraps the code-rendered Focus with a CompositionRenderer for the accessory layer; the core itself is not a placement. This is a structural gap for the new model: locked decision 1 requires that the core appear as a fixed-but-visible placement on the canvas, movable/resizable but undeletable. That requires either a schema-level `is_core: bool` field on placements or a separate Tier 1 table that declares the canonical core placement.

**Current authoring surface**: `frontend/src/bridgeable-admin/pages/visual-editor/FocusEditorPage.tsx` (1716 LOC). Authors `focus_compositions` rows directly. Tier toggle exists for scope (platform/vertical/tenant) but no concept of "Focus Core" as a separately authored artifact.

**Current runtime**: `ComposedFocus.tsx` resolves composition by `(focusType, vertical, tenantId)` via `useResolvedComposition`, renders via `CompositionRenderer` with `operational` props bridge. Fallback to hard-coded layout when no composition exists. No notion of inheriting from an upstream template; resolution is a flat first-match.

**Other Focus surfaces**:
- `focus_sessions` table + service (per-user layout state, 3-tier session resolver). Orthogonal to template inheritance; addresses "where you left off."
- `focus_layout_defaults` — tenant admin-configurable baselines per focus_type. Pre-dates the composition table; likely supersedable when three-tier composition lands.
- `generation_focus_instances` — distinct primitive for AI-generation Focuses; not in scope.

**Gaps for three-tier**:
- No Focus Core table or registry of canonical cores.
- No `inherits_from_template_*` columns on existing `focus_compositions`.
- No `is_core` placement flag, so the locked "core as fixed-but-visible canvas element" model has nowhere to land.
- No delta-storage for Tier 3 (current rows are full compositions).
- Editor has no concept of Tier 1 vs Tier 2 distinction.
- Runtime resolver does first-match-wins; needs to compose Tier 3 over Tier 2 over Tier 1.
- No in-place editor pattern (current editor lives only in admin Studio).

---

## Section 3 — Schema design (with Option B forward-compat)

**Recommendation: three tables.** `focus_cores` (Tier 1), `focus_templates` (Tier 2), `focus_compositions` repurposed for Tier 3. Alternative considered — fold Tier 1 + Tier 2 into a single `focus_templates` table differentiated by `scope` (the workflow pattern). Rejected because Core identity has structural meaning (a Tier 2 template *picks a core*) that an enum discriminator obscures. The three-table form makes the foreign key explicit, which simplifies the resolver and the editor.

Greenfield drop-and-recreate. `focus_compositions` rows in dev/staging can be wiped per locked decision 6.

### `focus_cores` (Tier 1)

```sql
CREATE TABLE focus_cores (
    id              VARCHAR(36) PRIMARY KEY,
    core_slug       VARCHAR(96) NOT NULL,   -- e.g. "scheduling-kanban"
    display_name    VARCHAR(160) NOT NULL,
    description     TEXT,
    -- Core registers a React mount in code; this column carries
    -- the registry id the runtime dispatches on.
    registered_component_kind   VARCHAR(32) NOT NULL,  -- "focus-core"
    registered_component_name   VARCHAR(96) NOT NULL,  -- "SchedulingKanbanCore"
    -- Default canvas geometry for the core's fixed-but-visible
    -- placement. Tier 2 / Tier 3 can move + resize within bounds.
    default_starting_column  INT NOT NULL DEFAULT 0,
    default_column_span      INT NOT NULL DEFAULT 12,
    default_row_index        INT NOT NULL DEFAULT 0,
    min_column_span          INT NOT NULL DEFAULT 6,
    max_column_span          INT NOT NULL DEFAULT 12,
    -- Tier-1-canonical defaults (cosmetic; cascades down).
    canvas_config            JSONB NOT NULL DEFAULT '{}',
    version                  INT NOT NULL DEFAULT 1,
    is_active                BOOLEAN NOT NULL DEFAULT TRUE,
    created_at, created_by, updated_at, updated_by  -- standard audit
);
CREATE UNIQUE INDEX ix_focus_cores_active_slug
    ON focus_cores (core_slug) WHERE is_active = TRUE;
```

Authored only at platform scope. No vertical column — Cores are platform-universal. Versioning identical to workflow_templates.

### `focus_templates` (Tier 2)

```sql
CREATE TABLE focus_templates (
    id              VARCHAR(36) PRIMARY KEY,
    scope           VARCHAR(32) NOT NULL CHECK (scope IN ('platform_default','vertical_default')),
    vertical        VARCHAR(32) REFERENCES verticals(slug),
    template_slug   VARCHAR(96) NOT NULL,    -- e.g. "scheduling-fh"
    display_name    VARCHAR(160) NOT NULL,
    description     TEXT,
    -- ARCHITECTURAL FK: a template picks a core.
    inherits_from_core_id        VARCHAR(36) NOT NULL REFERENCES focus_cores(id) ON DELETE RESTRICT,
    inherits_from_core_version   INT NOT NULL,  -- Option B forward-compat
    -- Accessory rows (same shape as today's focus_compositions.rows).
    -- The core is rendered as a special placement carried in rows
    -- with placement.is_core = TRUE; geometry mutable per Tier-1
    -- bounds.
    rows            JSONB NOT NULL DEFAULT '[]',
    canvas_config   JSONB NOT NULL DEFAULT '{}',
    version         INT NOT NULL DEFAULT 1,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at, created_by, updated_at, updated_by,
    CHECK (
        (scope='platform_default' AND vertical IS NULL)
        OR (scope='vertical_default' AND vertical IS NOT NULL)
    )
);
CREATE UNIQUE INDEX ix_focus_templates_active
    ON focus_templates (scope, vertical, template_slug)
    WHERE is_active = TRUE;
```

Authored only at platform scope (platform admin role). `inherits_from_core_version` reserved for Option B; v1 resolver ignores it (live-cascade-only) but the column is required so Option B is additive.

### `focus_compositions` (Tier 3) — repurposed greenfield

```sql
CREATE TABLE focus_compositions (
    id              VARCHAR(36) PRIMARY KEY,
    tenant_id       VARCHAR(36) NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    -- A tenant Focus picks a template (NOT a core directly).
    inherits_from_template_id        VARCHAR(36) NOT NULL REFERENCES focus_templates(id) ON DELETE RESTRICT,
    inherits_from_template_version   INT NOT NULL,
    -- Delta-storage shape (not full rows).
    deltas          JSONB NOT NULL DEFAULT '{}',
    -- Optional cosmetic overrides on top of inherited canvas_config.
    canvas_config_overrides  JSONB NOT NULL DEFAULT '{}',
    version         INT NOT NULL DEFAULT 1,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at, created_by, updated_at, updated_by
);
CREATE UNIQUE INDEX ix_focus_compositions_active_per_tenant_template
    ON focus_compositions (tenant_id, inherits_from_template_id)
    WHERE is_active = TRUE;
```

**Delta shape** (recommended; carries over the edge-panel precedent at `composition_service.py:789-876`):

```json
{
  "hidden_placement_ids": ["p_today", "p_anomalies"],
  "additional_placements": [
    { "placement_id": "p_custom_calendar",
      "component_kind": "widget",
      "component_name": "calendar",
      "row_index": 1,
      "starting_column": 6,
      "column_span": 6,
      "prop_overrides": {} }
  ],
  "placement_order": ["p_recent_activity", "p_custom_calendar"],
  "placement_geometry_overrides": {
    "p_recent_activity": { "starting_column": 0, "column_span": 6 }
  },
  "core_geometry_override": {
    "starting_column": 0, "column_span": 8, "row_index": 0
  }
}
```

`core_geometry_override` is the only way a tenant can act on the core — geometry-only, bounds-clamped by Tier 1's `min/max_column_span`. Identity, kind, name, registered component reference are unchanged at Tier 3.

**Why delta over locked-to-fork**: (1) Existing precedent — edge-panel resolver already does add/hide/reorder deltas; the resolver work is mostly a port. (2) Upstream changes can flow through without an explicit merge step in the common case (a vertical_default adds a new widget; tenant sees it unless they hid that placement). (3) Workflow's "graph merge has no canonical answer" rationale doesn't apply — rows + placements have stable identity (`placement_id`) and clear merge rules.

**Forward-compat for Option B (versioned cascade)**: `inherits_from_template_version` is present from day one. v1 resolver always picks the active row (whatever version it is); v2 resolver can pin to the version stored in the FK. Adding versioned cascade is a service-layer change only.

**Cascade-on-Tier-2-delete**: `ON DELETE RESTRICT` blocks template deletion when forks exist. Tier 2 deletion is admin-triggered + low-frequency; tenant migration to a different template lives in service-layer code, not cascade.

---

## Section 4 — Resolver design

**Location**: `backend/app/services/focus_compositions/composition_service.py::resolve_focus` (new function, distinct from current `resolve_composition` which we'll deprecate post-cutover). Sketched signature:

```python
def resolve_focus(
    db: Session, *,
    focus_template_slug: str,
    vertical: str | None,
    tenant_id: str | None,
) -> ResolvedFocus
```

**Walk**:
1. Look up Tier 2 template: `focus_templates` where (`template_slug` == focus_template_slug) AND ((`scope=vertical_default AND vertical=vertical`) OR (`scope=platform_default`)) AND `is_active=true`. Vertical wins if both exist.
2. Resolve Tier 1 core: `focus_cores` by `template.inherits_from_core_id`, picking the active row (v1 live cascade) or the pinned version (Option B).
3. If `tenant_id` is set: look up Tier 3 composition: `focus_compositions` where `tenant_id=tenant_id AND inherits_from_template_id=template.id AND is_active=true`. Zero-or-one row.
4. Compose: start from `template.rows`; inject the core placement at the core's resolved geometry; apply Tier 3 deltas (hide / add / reorder / per-placement geometry / core geometry).

**Composition output shape**:

```python
{
  "focus_template_slug": str,
  "core_id": str,
  "core_slug": str,
  "core_registered_component": {"kind": str, "name": str},
  "rows": [...],   # composed rows including core as a placement
  "canvas_config": {...},
  "sources": {
    "template": {"id": str, "version": int, "scope": "vertical_default"|"platform_default"},
    "core":     {"id": str, "version": int},
    "tenant":   {"id": str, "version": int} | None,
  },
}
```

**Core's special status**: identity comes from Tier 1; position/size cascades — Tier 2 may override geometry within Tier 1's `min/max_column_span` bounds; Tier 3 may override geometry again within the same bounds via `core_geometry_override`. Identity (component kind/name, slug) is *never* overridable.

**Delta composition order**: hide → add → geometry-override → reorder. Orphan IDs (placement_ids no longer present in Tier 2 after an upstream change) are silently dropped at debug log level. This matches `_apply_placement_overrides` precedent (`composition_service.py:818-823`).

**Performance**: three indexed lookups (Tier 2 by slug+scope+vertical, Tier 1 by FK, Tier 3 by FK+tenant). v1 ships without caching — single-digit-ms latency expected per the existing `resolve_composition` performance profile. Add a per-request memoization layer if profiling surfaces a hot path. Edge-panel resolver currently does no caching at the service layer and meets latency budgets.

**Mirror of workflow resolver**: structurally yes (walk by scope, first-match-wins for the *template* tier). Diverges at Tier 3: workflow uses replace, Focus uses delta-compose. The delta layer is new code, modeled on the existing edge-panel `_apply_placement_overrides` helper.

---

## Section 5 — Editor surface design

### 5a. Tier 1 + Tier 2 editor (Studio)

Studio rail entry: **"Focus Templates"** (name carries per locked decision 4 — Tier 1 surfaces as a sub-toggle).

Tier toggle inside the editor (top of left rail):
- **Focus Cores** (Tier 1) — platform admin only. List of registered cores. Each card shows slug, registered component name, default geometry, version, and a "in use by N templates" count.
- **Focus Templates** (Tier 2) — platform admin only. List of templates filtered by vertical (top-of-page vertical chip selector matches existing Studio chrome). Card shows slug, picked core, accessory widget count, version.

**Tier 1 editor pane** (when a core is selected):
- Read/edit: display_name, description, registered_component_name (typeahead from registry), default geometry, min/max column_span bounds, Tier-1-canonical canvas_config.
- "Save and notify dependents" affordance — equivalent to workflow's `mark_pending_merge` but cascading to Tier 2 templates that reference this core. v1 ships informational ("3 templates inherit from this core"); merge UX deferred.

**Tier 2 editor pane** (when a template is selected):
- Picker: "Inherits from Core" — required dropdown of active Tier 1 cores. Cannot be changed after first save (changing core is structurally a new template; provide a "Clone with different core" action).
- Canvas: the **same canvas component used at Tier 3 in-place editor** (per locked decision 5). The core appears as a fixed-but-visible placement (special border, "Core" badge, undeletable). Other placements are normal accessory widgets.
- Right rail: placement palette (widgets, focus accessories per registry filtered by `canvasPlaceable`).

**"Create new template from Core: [picker]"** flow: pick core → seed template with the core's default geometry placement only → enter the canvas editor to add accessories.

### 5b. Tier 3 in-place editor (runtime-aware)

**This is the novel surface.** Decision 5 names it the pattern-establisher for in-place editing across the platform.

Modes:
- **Operator mode** (default; all tenant users): read-only canvas, decision-driving Focus behavior. Current behavior preserved.
- **Tenant-author mode** (tenant_admin or tenant role with new `focus.author` permission): placements editable, accessories addable, palette accessible.

**Mode toggle**:
- Surface: small "Customize" button in the Focus top-right header (icon: pencil/sliders, only visible to users with the permission).
- Click → toggles canvas into author mode. Visual treatment shifts (grid lines visible, accessory widget chrome shows drag handles, core shows "Core (move/resize only)" badge).
- Exit author mode: top-bar "Done" button. Auto-save on edit (debounced) — no explicit save.

**Visual distinction (inherited vs tenant-local)**:
- Inherited placements: standard chrome.
- Tenant-local additions: subtle accent ring (`--space-accent-subtle`), small "+ added by tenant" badge.
- Hidden inherited placements: rendered as ghost outline at original geometry with "Hidden — click to restore" affordance.
- Tenant-modified geometry on an inherited placement: subtle dot in corner.

**"Reset to template default"** affordance:
- Per-placement: right-click → "Reset to template default" (clears that placement's entry from `deltas.placement_geometry_overrides` + `deltas.hidden_placement_ids`).
- Whole-Focus: top-bar overflow menu → "Reset all customizations to template default" (clears the entire `deltas` blob; Tier 3 row stays for audit but becomes a no-op delta).

**Save semantics — recommend lazy fork**:
- The `focus_compositions` (Tier 3) row is created **on first edit**, not on Focus open. Pre-edit, the tenant resolves to Tier 2 directly (no Tier 3 row exists; `inherits_from_template_id` lookup finds nothing). On first edit, service-layer creates a row with the appropriate inherits_from_template FK + applies the first delta.
- Auto-save debounced 500ms (matches existing `focus_sessions` layout-state convention).

### 5c. Tenant fork lifecycle — recommend lazy

Three options were considered:

- **Eager**: every tenant gets a Tier 3 row per Focus on first open. Pros: query plan stays simple. Cons: wasteful row count (n_tenants × n_templates), most rows are no-op.
- **Lazy** (recommended): Tier 3 row only when tenant first customizes. Pros: clean DB; "did tenant customize?" is a single `EXISTS` query. Cons: resolver has a 3rd-tier lookup that often returns nothing — but that's cheap with the index.
- **Explicit**: tenant clicks "Customize this Focus"; pre-fork is read-only Tier 2. Pros: clarity. Cons: friction; pattern conflicts with the in-place editor decision (the customize flow IS the entry, not a separate step).

Lazy aligns best with the in-place editor model (decision 5) and the workflow precedent. Workflow forks are also lazy.

---

## Section 6 — Sub-arc decomposition + sequencing

Per Studio canon (R-7-α floor analysis), no sub-arc should exceed ~2,500 LOC. Target band ~1,000–2,000.

### Sub-arcs

**A — Schema substrate** (~800–1,200 LOC)
- New migrations: `focus_cores` table; `focus_templates` table; greenfield drop+recreate `focus_compositions` table.
- ORM models for the three tables.
- No service code yet (only structural validation in models).
- Tests: model + constraint tests; CHECK constraint coverage; partial-unique index coverage.
- Shippable end-to-end? Schema-only — yes (alembic upgrade head passes, ORM imports clean, regression suite passes). Not user-visible.
- Depends on: none.

**B — Resolver + service-layer CRUD** (~1,500–2,000 LOC)
- `focus_cores_service.py`, `focus_templates_service.py`, `focus_compositions_service.py` (renamed/repurposed).
- `resolve_focus` resolver, including delta composition.
- API endpoints under `/api/platform/admin/visual-editor/focus-cores`, `/focus-templates`, `/focus-compositions` (the third gets a tenant-scoped subset too).
- Seed script for one Tier 1 core (`scheduling-kanban`) + one Tier 2 template (`scheduling-fh`) to cover the existing production Focus.
- Tests: resolver under each combination of present/absent tiers; delta semantics; orphan-ID drop; core geometry override; bounds clamping.
- Shippable end-to-end? Backend-only — yes. Can serve resolved Focuses to a frontend that hasn't migrated yet (the runtime can be wired in a separate sub-arc).
- Depends on: A.

**C — Tier 1 + Tier 2 editor (Studio)** (~2,000–2,500 LOC)
- New Studio rail entry "Focus Templates" with tier toggle.
- Tier 1 list + edit pane.
- Tier 2 list + edit pane with canvas (the canvas component built here is the same one Sub-arc D consumes for Tier 3 in-place).
- "Create from Core: [picker]" flow.
- Tests: canvas behavior, core-as-fixed-but-visible placement, picker, save lifecycle.
- Shippable end-to-end? Yes. Platform admin can author Tier 1 + Tier 2 content. Tenants still ride Tier 2 directly with no Tier 3 customization yet (because no Tier 3 editor exists — they read Tier 2 via the resolver).
- Depends on: B (needs API + resolver).

**D — Tier 3 in-place editor (runtime-aware adaptation)** (~1,500–2,200 LOC)
- Mode toggle in Focus header.
- Author-mode canvas reusing C's canvas component, scoped to deltas.
- Per-placement reset, whole-Focus reset.
- Lazy-fork wiring (auto-create Tier 3 row on first edit).
- Visual distinction layer (inherited vs tenant-local vs hidden vs modified).
- Permission gate (`focus.author` permission + tenant_admin default grant).
- Tests: mode toggle, edit lifecycle, lazy fork creation, reset semantics, permission gate.
- Shippable end-to-end? Yes — closes the full three-tier loop.
- Depends on: C (consumes C's canvas component) + B (consumes resolver delta semantics).

**E — Canonical Tier 2 template authoring** (content authoring, ~minimal LOC; multi-week effort in content)
- Hand-author the Tier 2 templates for the September Wilbert demo Focuses.
- Sequencing flag: this is **content work**, not code. It can begin once Sub-arc C ships (Tier 2 editor exists). It runs in parallel with Sub-arc D from the moment C is shippable.

### Dependency graph

```
A (schema)
└── B (resolver + service + API)
    └── C (Tier 1 + 2 editor)
        ├── D (Tier 3 in-place editor)
        └── E (content authoring — parallel with D)
```

C → D is a strict dependency because D reuses the canvas component built in C. C → E is a tooling-readiness dependency, not a code one. A → B is strict (B imports models). B → C is strict (C consumes B's API).

### Recommended sequence

A → B → C → (D ∥ E). D and E run in parallel; E may even start a day or two into D since the canvas is established at C's close.

---

## Section 7 — Architectural risks + open questions

**R1 — Core-as-placement vs core-as-special-field**. Treating the core as a placement carried in `rows` with `is_core: true` is structurally clean and lets the Tier 2 canvas show the core in situ. The alternative — a separate `core_placement` JSONB column on `focus_templates` — keeps the type system honest (core has a different shape than accessories: no `prop_overrides`, narrower geometry rules). Recommendation: placement-in-rows with `is_core: true`. The shape divergence is small; the editor benefits outweigh the type-purity loss.

**R2 — Focus types in canon that don't fit core+accessories**. The locked decisions assume every Focus has a code-rendered core. Today's Focus type registrations (`frontend/src/lib/visual-editor/registry/registrations/focus-templates.ts`) include `focusType: "decision"`, `focusType: "generation"` — multiple Focus shapes. The decision-type Focus (triage decision) genuinely follows core+accessories (decision panel as core; accessory widgets around it). The generation-type Focus (arrangement scribe) is more bespoke — its UI is a multi-pane scribe surface that may not need composition at all. **Open question for §3 future planning**: does Tier 1's `focus_cores` table need a `core_shape` discriminator (`decision_core` vs `generation_core` vs `kanban_core`)? Recommend deferring — start with one core shape, generalize when a second concrete production Focus needs the table.

**R3 — Permission model for Tier 3**. The recommendation introduces a `focus.author` permission with tenant_admin as the default grant. Open question: should this also be assignable to non-admin operators (e.g., a senior funeral director who wants to customize their case-file Focus)? Recommend: yes, grant by permission, not by role. Phase 8a's permission system already supports this via `user_has_permission`.

**R4 — Studio rail placement**. The Studio rail entry "Focus Templates" surfaces both Tier 1 and Tier 2 under one node with an internal toggle. Open question: should Tier 1 live elsewhere as a more architectural surface (closer to Component Registry)? Recommend keeping under "Focus Templates" — cores are part of the Focus authoring story, and putting them in Component Registry would put them in a tab that platform admins rarely visit. The tier toggle makes the relationship explicit.

**R5 — Tier 2 deletion when Tier 3 forks exist**. Recommendation: `ON DELETE RESTRICT`. Surface migration tooling in a later phase. v1 ships with deletion blocked + a helpful error message ("3 tenants reference this template; archive instead").

**R6 — Live cascade vs versioned cascade transition timing**. The schema is forward-compat from day one. Concretely, the transition is service-layer-only: switch `_find_active_template` from "find active" to "find by version pinned in FK." Recommend planning the transition for the first time a vertical_default edit produces a regression in a tenant's customized Focus — until then, live-cascade is the simpler default.

**R7 — Tier 3 in-place editor performance under live tenants**. The mode toggle invokes the canvas editor inside the production Focus DOM tree. SchedulingKanbanCore is 1714 LOC and renders heavy DnD machinery. Open question: does mounting an editor *around* it (palette, drag handles on accessories, geometry overlay) cause perf regressions in operator mode? Recommend: the editor mounts only when mode toggles to author; operator mode renders zero editor chrome. Tests should cover the "no editor JS in operator mode" boundary.

**R8 — Migration cleanup of `focus_layout_defaults`**. This pre-composition table likely overlaps with the new Tier 2 surface. Recommend documenting at A-close whether the table is superseded; explicit deprecation in a follow-up.

---

## Section 8 — Sequencing recommendation + September arc impact

**Recommended sequence**: A (~1 day) → B (~2-3 days) → C (~3-4 days) → D and E parallel (~3-4 days D; ~2-3 weeks E content).

**Calendar projection**:
- Start mid-May (2026-05-15 or so, after Spaces substrate or whatever lands next per current state).
- A closes ~05-16. B closes ~05-19. C closes ~05-23. D closes ~05-27. Substrate complete end of May.
- Sub-arc E (template content authoring) runs late May → early August. The Wilbert demo lives or dies on the quality of this content.

**September realism call**: The substrate (A-D) finishes well before September. The work that takes calendar time is **E — authoring the Tier 2 templates that will demo**. The September Wilbert demo needs at minimum:
- Funeral home scheduling Focus (vertical_default for funeral_home) — already exists at composition level; needs re-authoring against the new Tier 2 schema.
- Manufacturing dispatch Focus (vertical_default for manufacturing) — same.
- Funeral home arrangement Focus, case-file Focus — depending on demo scope, may need new templates.

The substrate enables this work but doesn't *do* it. Sub-arc E is the September bottleneck. The recommendation: **ship A-D before end of May; commit June-August to E + iterative refinement based on the canon templates that emerge from real demo prep**.

**Faster paths considered**:
- Skip Tier 1 editor (C-Tier1), hand-author cores via SQL/seed scripts. Saves ~1 day. Recommend: don't — the editor work is small relative to the surface; cores authored only by SQL becomes a maintenance burden.
- Ship D before C. Not viable — D consumes C's canvas component.
- Parallel A + B by stubbing models. Possible but the schema is small enough that serial is fast.

**No faster path materially changes the September date.** The pacing constraint is content authoring (E), not substrate.

---

## Closing notes

Investigation surfaced one major architectural divergence from the workflow precedent: **delta-storage at Tier 3** rather than locked-to-fork replace. This is justified by the simpler underlying shape (rows + placements with stable IDs) and the existing edge-panel resolver precedent. The decision belongs to the build phase, not this investigation.

Both `inherits_from_template_id` AND `inherits_from_template_version` ship from day one per locked decision 2. Option B (versioned cascade) becomes additive at the service layer.

The novel UX is the Tier 3 in-place editor (Sub-arc D). It establishes the pattern decision 5 names — runtime-aware editing for any platform primitive that has a "where you use it = where you author it" surface. Spaces customization is the next consumer of the same pattern when its substrate arc lands.
