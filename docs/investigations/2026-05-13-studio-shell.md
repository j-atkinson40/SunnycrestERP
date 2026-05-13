# Bridgeable Studio shell — investigation findings

Read-only investigation. No code changed; no migrations applied; no
routes modified. Findings inform the Studio shell arc scoping decision
and surface the substrate gaps the arc will hit. Citations are file
paths + migration numbers; uncertainty surfaced explicitly where the
trail goes thin.

---

## Section 1: Runtime-aware platform editor — current state

### File locations

Primary entry point: `frontend/src/bridgeable-admin/pages/runtime-editor/RuntimeEditorShell.tsx` (~400 LOC). The shell mounts at `/runtime-editor/*` and `/bridgeable-admin/runtime-editor/*` (see `frontend/src/bridgeable-admin/BridgeableAdminApp.tsx:193,197` — both paths register the same lazy-loaded component).

Adjacent picker: `frontend/src/bridgeable-admin/pages/runtime-editor/TenantUserPicker.tsx` — the initial impersonation handshake surface, rendered as a child of the shell when impersonation params are absent (R-1.6.1 design).

Core supporting modules under `frontend/src/lib/runtime-host/`:
- `EditModeToggle.tsx` — floating toggle button, syncs `?edit=1` URL param.
- `SelectionOverlay.tsx` — capture-phase document click handler, walks up DOM to nearest `[data-component-name]` element.
- `edit-mode-context.tsx` — React context provider; holds staged `RuntimeOverride[]` and dispatches commits through `runtime-writers.ts`.
- `runtime-writers.ts` — 4-type override router (`token`, `component_prop`, `component_class`, `dashboard_layout`); writes through `adminApi` (platform-token axios instance).
- `dual-token-client.ts` — `apiClient` (tenant token, via impersonation) + `adminApi` (platform token).
- `TenantProviders.tsx`, `TenantRouteTree.tsx` — wrap tenant context inside the platform-admin shell so the tenant app renders against the impersonation token.
- `page-contexts.ts`, `use-page-context.ts` — `page_context` resolution (e.g., `"dashboard"`, `"ops_board"`) for layout writes.
- `inspector/` directory — 6 inspector tabs.

Inspector tabs (`frontend/src/lib/runtime-host/inspector/`):
1. `ThemeTab.tsx`
2. `ClassTab.tsx`
3. `PropsTab.tsx`
4. `WorkflowsTab.tsx`
5. `DocumentsTab.tsx`
6. `FocusCompositionsTab.tsx`

Plus `InspectorPanel.tsx` (tab-strip wrapper, 380px right rail) and `deep-link-state.ts` (state for "Open in full editor" deep-link to standalone editors).

### Mount strategy

Full-page surface at `/runtime-editor/*` route. The shell renders inside `BridgeableAdminApp.tsx` (admin tree). Three layered chrome elements:
1. **Admin ribbon** (h-8 bar at top) — yellow status-warning palette; shows tenant slug + impersonated user id; data-testid `runtime-editor-ribbon`.
2. **Floating toggle** (`EditModeToggle`) — bottom-right corner of viewport; toggles `?edit=1`.
3. **Inspector panel** (right rail, 380px) — shows when a component is selected; renders the 6 tabs.

The tenant route tree mounts via `<TenantRouteTree />` inside `<TenantProviders>` (the same providers tenant pages run with, but reading the impersonation token via `useAuth()`). Selection overlay walks up from any click in the tenant content region to find the nearest `data-component-name` element.

Not a modal, not an embedded panel — it occupies the full admin viewport. The tenant content is "the page being edited," not a preview thumbnail.

### Surface coverage

Editable surfaces today (via the 6 inspector tabs):
- **Themes** — design tokens (light/dark mode; per-token override).
- **Class** — component-class-level configuration (e.g., widget-class radius / shadow tokens shared across all widgets).
- **Props** — per-component prop overrides (e.g., density on a specific widget).
- **Workflows** — workflow_templates authoring (canvas + node config; same shape as standalone `/visual-editor/workflows`).
- **Documents** — document_templates authoring (Notion-shape blocks; same as standalone `/visual-editor/documents`).
- **Focus compositions** — focus_composition rows authoring (canvas placements; read-mostly when embedded in inspector per Arc 3a Q-FOCUS-1 canon).

NOT editable from the inspector today:
- Pulse compositions (Pulse home `/home` renders via `getWidgetRenderer` + `user_widget_layouts`; no inspector path).
- Dashboard layouts (the `dashboard_layouts` table is writable via `runtime-writers.ts` → `dashboardLayoutsService`, but **no inspector tab** exposes layout authoring — the standalone editor at `/visual-editor/widgets` mode=layouts is the only authoring path).
- Spaces (no spaces substrate touched at all; see Section 2).
- Saved views (no authoring surface in the runtime editor).
- Edge panels (separate substrate `focus_compositions.kind = "edge_panel"`, edited via standalone `/visual-editor/edge-panels` only).

### Tenant context mechanism

URL-parameter-driven impersonation. The shell reads:
- `?tenant=<slug>` — tenant company slug
- `?user=<user_id>` — user to impersonate within that tenant

When either is missing, `RuntimeEditorShell.tsx:341-361` renders `<TenantUserPicker />` as a child, which drives the impersonation handshake (POST against the platform impersonation API; obtains tenant JWT; persists to localStorage; calls `navigate("/runtime-editor/?tenant=...&user=...")`).

Auth gate (`RuntimeEditorShell.tsx:308-311`): super_admin OR platform_admin OR support. Mirrors the impersonation API's role gate.

No dropdown / persistent picker for switching tenants mid-session — to switch, the operator must strip query params and re-pick.

### Editing affordances

Implemented:
- **Click-to-select** — capture-phase document handler at `SelectionOverlay.tsx:90+` walks up from `event.target` to the nearest `[data-component-name]` element; sets that as the selected component.
- **Brass border on selected element** — selection overlay applies CSS to draw the border.
- **Hover affordance** — `[data-runtime-editor-mode="edit"] [data-component-name]:hover` rule (injected once) gives a subtle highlight.
- **Inspector tabs** — 6 tabs, each handling its own substrate (see surface coverage).
- **Theme controls** — Theme tab provides token-by-token override authoring with live preview against the impersonated tenant render.
- **`?edit=1` URL persistence** — edit mode is bookmarkable / shareable.
- **Cross-realm boundary** — tenant content fetches use the impersonation token; inspector writes use the platform-admin token via `adminApi`. Strict no-fallback discipline in `dual-token-client.ts`.
- **"Open in full editor" deep-link** — Workflows / Documents / FocusCompositions inspector tabs each surface a button that opens the standalone editor at `/visual-editor/<editor>` with `?return_to=<current path>` query param so the operator can navigate back (Arc-3.x-deep-link-retrofit).

NOT implemented:
- Drag-to-canvas authoring (palette → canvas).
- Saved-view drag-to-canvas authoring.
- Multi-select on canvas.
- Inspector tab for dashboard composition authoring (per B-4a2-1 resolution from Arc 4a.2 investigation: deferred indefinitely; standalone DashboardLayoutsEditor is sole surface).
- Inspector tab for Spaces authoring.
- Inspector tab for Pulse composition authoring.

### Palette state

**Not built.** Canon (per Studio thesis) describes "categorized widget and saved-view palette supports drag-to-canvas authoring." The runtime editor today has NO palette. The closest precedent is `FocusCompositionsTab.tsx:921-1504` which has an inline "palette" (canvas-placeable components list) for adding placements to a Focus composition — that's a per-composition affordance, not a global widget palette and not a saved-view palette.

The standalone editors with palette/library left panes are:
- `FocusEditorPage.tsx` — `HierarchicalEditorBrowser` of Focus types + templates.
- `DocumentsEditorPage.tsx` — `HierarchicalEditorBrowser` of document types + templates.
- `WidgetEditorPage.tsx` — flat widget browser with search + thumbnails.

None of these are "drag-to-canvas" palettes; they're "click-to-select-then-edit-the-selected-item" browsers.

### Saved-view authoring

**Not built.** There is no saved-view drag-to-canvas surface. Saved views live in `vault_items` with `item_type="saved_view"` (Phase 2 of UI/UX Arc, per CLAUDE.md §14 historic entry). They're authored at `/saved-views` (a tenant-side page, not in the visual editor). The runtime editor has zero saved-view authoring path — neither read nor write.

### Persistence

Inspector edits → `runtime-writers.ts` → 4 platform endpoints, all via `adminApi` (PlatformUser-token):

| Override type | Endpoint | Backend table |
|---|---|---|
| `token` | `/api/platform/admin/visual-editor/themes/*` | `platform_themes` (r79) |
| `component_prop` | `/api/platform/admin/visual-editor/components/*` | `component_configurations` (r81) |
| `component_class` | `/api/platform/admin/visual-editor/classes/*` | `component_class_configurations` (r83) |
| `dashboard_layout` | `/api/platform/admin/visual-editor/dashboard-layouts/*` | `dashboard_layouts` (r87) |

Workflows, Documents, Focus compositions inspector tabs write through their own service clients (`workflow-templates-service`, `documents-v2 admin endpoints`, `focus-compositions-service`) — also platform endpoints, also via `adminApi`. Substrate is **the same tables** the 7 standalone editors write to. There is **no separate runtime authoring path**; runtime and standalone editors share substrate.

Scope discipline (per `runtime-writers.ts:11-22`): theme + component_prop + component_class writes default to `vertical_default` for the impersonated tenant's vertical. `dashboard_layout` writes also default to `vertical_default`. Tenant-default or platform-default scope is not accessible from the runtime editor today — the operator picks tenant via impersonation, and all writes target that vertical's vertical_default tier.

---

## Section 2: Spaces substrate state

### Spaces table

**No `spaces` table exists.** Confirmed by:
- `ls backend/app/models/ | grep -i space` returns only `user_space_affinity.py` (the affinity-tracking table from Phase 8e.1, not a spaces-canonical table).
- `backend/app/services/spaces/types.py:6` explicitly states: "Stores per-user spaces in `User.preferences.spaces` (a JSONB array). No new table."
- `backend/app/services/spaces/crud.py:81-110` reads/writes `user.preferences["spaces"]` via `flag_modified(user, "preferences")`.

Each space is a `SpaceConfig` dataclass (`backend/app/services/spaces/types.py:170+`) serialized to JSONB. Per-user, per-vertical seeded at user registration (Phase 3 + Phase 8a).

### Spaces authoring API

15 endpoints at `/api/v1/spaces/*` (`backend/app/api/routes/spaces.py`):

- `GET /` — list user's spaces
- `POST /` — create space
- `POST /reorder` — reorder user's spaces
- `GET /{space_id}`, `PATCH /{space_id}`, `DELETE /{space_id}`
- `POST /{space_id}/activate` — set active space
- `POST /{space_id}/pins`, `DELETE /{space_id}/pins/{pin_id}`
- `POST /{space_id}/pins/reorder`
- `POST /reapply-defaults`
- Plus affinity endpoints (`POST /affinity/visit`, `GET /affinity/count`, `DELETE /affinity/clear`)

**Every endpoint is tenant-token authenticated and per-user scoped.** There is no platform-admin endpoint for editing vertical-default Spaces. Spaces are entirely user-owned today.

### Does the runtime editor edit Spaces?

No. Verified by grepping `frontend/src/lib/runtime-host/` for `spaces`-related symbols — only the affinity tracker is referenced (recorded as user behavior, not as authoring target). `RuntimeOverrideType` (`edit-mode-context.tsx:88-92`) has 4 values: `token | component_prop | component_class | dashboard_layout`. No `space` type.

### Pulse composition substrate distinct from focus_compositions?

The `focus_compositions` table (r84) carries both `kind = "focus"` (Focus accessory rails) and `kind = "edge_panel"` (edge panels, r91). Pulse home (`/home`) does NOT use `focus_compositions` at all — Pulse renders via:
- `getWidgetRenderer(widget_id)` registry-based dispatch (`frontend/src/components/focus/canvas/widget-renderers.ts`) for per-widget render.
- `user_widget_layouts` per-user persistence (per-user widget grid arrangement).
- `dashboard_layouts` (r87) for the 3-tier scope inheritance below per-user layout (platform_default → vertical_default → tenant_default → user_widget_layouts override).

So **there are TWO distinct dashboard-shaped substrates**: `focus_compositions` (for Focus accessory rails + edge panels) and `dashboard_layouts` (for Pulse + Ops Board + Vault Overview). The two are NOT unified; the canon-canonical decision (per Arc 4d substrate-asymmetry-is-canon-faithful) is that they STAY distinct.

### Gap: "Spaces editable as a first-class Studio section"

What exists:
- Per-user spaces with full CRUD.
- Role-seeded templates per `(vertical, role_slug)` in `backend/app/services/spaces/registry.py` (e.g., `("funeral_home", "director")` template seeds Arrangement / Administrative / Ownership spaces with canonical pins).

What's missing for vertical-scoped Spaces authoring:
1. **No `space_templates` or vertical-default spaces table.** The seed templates live in Python code (`registry.py`), not in DB. Editing a template today means editing Python.
2. **No platform-admin Spaces API.** The 15 endpoints are user-scoped. A platform admin cannot "edit the canonical funeral_home director's Arrangement space."
3. **No Studio-side substrate to write to.** Even if the runtime editor wanted to expose Spaces authoring, there's no `dashboard_layouts`-shaped substrate (3-tier scope, write-side versioning, READ-time resolution) for spaces. Adding one is an arc unto itself.
4. **No Pulse composition substrate.** Pulse home renders via the dashboard_layouts path, not a spaces-composition table. If "Spaces" in Studio is supposed to subsume Pulse home authoring, that's a different substrate question than per-space pin lists.

**Estimated gap to first-class Spaces section**: 1,500-2,500 LOC for spaces substrate alone (table + service + API + frontend service + admin authoring path), parallel to dashboard_layouts shape. This is a substrate arc, not a Studio shell arc.

---

## Section 3: Editor left-pane refactor surface area

Each editor's current left pane content, retention boundary, and refactor LOC estimate:

### Themes (`frontend/src/bridgeable-admin/pages/visual-editor/themes/ThemeEditorPage.tsx:391-545`)

- 280px left pane: scope selector (3 buttons: platform_default / vertical_default / tenant_override), vertical/tenant_id input, mode toggle (light/dark), preview vertical filter.
- **Subsumable by Studio rail**: scope selector + vertical/tenant_id input + preview vertical filter (these are cross-editor concerns the Studio rail handles).
- **Editor-specific (retain inside editor frame)**: mode toggle (Themes-only concern), preview-vertical-filter (only Themes uses this).
- **Refactor LOC**: ~80-120 LOC (extract scope-selector + vertical/tenant_id input into Studio-context-aware code path; keep mode toggle + preview filter inline).

### Focus Editor (`FocusEditorPage.tsx:478-606`)

- 320px left pane: `HierarchicalEditorBrowser` (5 Focus types as categories, each with N templates underneath; search box; category-level help text).
- **Subsumable by Studio rail**: the entire HierarchicalEditorBrowser (Studio rail provides a similar tree-shaped selector).
- **Editor-specific**: nothing.
- **Refactor LOC**: ~50-80 LOC (conditional rendering: when `studioContext` prop is passed, omit the left aside; the existing browser callbacks accept selection from a parent — those signatures need to lift to Studio rail).

### Widget Editor (`WidgetEditorPage.tsx:338-401`)

- 320px left pane: flat widget browser with search + thumbnails. Differs per mode (individual vs class vs layouts) — only "individual" has the left browser; "class" and "layouts" use different layouts.
- **Subsumable by Studio rail**: the individual mode's flat browser.
- **Editor-specific**: mode toggle (Edit Individual Widgets / Edit Widgets as Class / Dashboard Layouts) at the top; the three modes have heterogeneous layouts.
- **Refactor LOC**: ~150-200 LOC — modes complicate. Per mode, conditional left-pane drop; the class mode's preview already has no separate left rail (it's single-pane with controls left + preview right). Layouts mode has its own pane structure entirely (DashboardLayoutsEditor at WidgetEditorPage.tsx:969).

### Documents (`DocumentsEditorPage.tsx:457-475`)

- 320px left pane: `HierarchicalEditorBrowser` (document types as categories, templates as children).
- **Subsumable by Studio rail**: the entire HierarchicalEditorBrowser.
- **Editor-specific**: nothing.
- **Refactor LOC**: ~50-80 LOC (mirrors Focus Editor refactor exactly).

### Classes (`ClassEditorPage.tsx:431-493`)

- 320px left pane: component-class browser (9 classes as flat list with metadata).
- **Subsumable by Studio rail**: the class browser.
- **Editor-specific**: nothing.
- **Refactor LOC**: ~50-80 LOC.

### Workflows (`WorkflowEditorPage.tsx:634-864`) — **THE HARDEST CASE**

- 280px left pane: scope selector + vertical selector + workflow_type selector + per-workflow metadata pane + dependent-forks list.
- **Subsumable by Studio rail**: scope selector + vertical selector + workflow_type selector (cross-editor concerns; tree shape fits Studio rail).
- **Editor-specific (retain)**: per-workflow metadata pane (version / node count / edge count / branching / terminal counts via `summarizeCanvas`) AND dependent-forks list (Workflows-only: only Workflows has the locked-to-fork merge semantics surfacing forks of a vertical_default). These are workflow-specific informational displays that don't map to other editors.
- **Refactor LOC**: ~250-350 LOC (richest left pane; the metadata + dependent-forks blocks need to relocate inside the center pane or right rail since they don't fit Studio rail). This is the largest single-editor refactor.
- **Also a SECOND aside at WorkflowEditorPage.tsx:993** — node configuration rail on the right side when a node is selected. This is editor-specific (matches FocusCompositions canvas + node config pattern) and is NOT touched by the Studio rail refactor — but the existence of two asides changes the layout grid math.

### Registry (`RegistryDebugPage.tsx`)

- No separate left rail. Single-pane filter + table.
- **Subsumable by Studio rail**: nothing — Registry is a pure inspector page, not a category-selector + detail-editor pair.
- **Editor-specific (retain)**: everything (filter row + table + detail card).
- **Refactor LOC**: ~30-50 LOC if mounted in Studio — main task is removing duplicate filter chrome that the Studio rail already provides. Or: Registry stays unchanged and Studio rail just doesn't render a browser when on the Registry tab.

### Plugin Registry Browser (`PluginRegistryBrowser.tsx`)

- Similar shape to Registry. No separate left rail.
- **Refactor LOC**: ~30-50 LOC (or zero — could remain as-is).

### Edge Panels (`EdgePanelEditorPage.tsx:531`)

- Smaller editor; per-page row authoring with scope selector + panel-key input + page list left rail (~260px).
- **Subsumable by Studio rail**: scope selector + panel-key input.
- **Editor-specific**: page list, page metadata editor, per-row canvas.
- **Refactor LOC**: ~120-180 LOC.

### Cumulative editor refactor LOC

~880-1,490 LOC across the 9 standalone editors (including Plugin Registry + Edge Panels + ComponentEditorPage which is the legacy generic component editor). Workflow editor is the hardest case at ~250-350 LOC alone; everything else is mechanical.

This estimate does NOT include the **Studio rail itself** (the unified left-pane component the Studio shell mounts above all editors), which is net-new code. Conservative estimate for Studio rail: 600-1,000 LOC (tree-shape browser + mode dispatch + edit/live mode toggle + scope picker + tenant picker if applicable).

---

## Section 4: Standalone route redirect inventory

### Routes to redirect post-Studio (10 total)

From `BridgeableAdminApp.tsx:201-207` + `App.tsx` + `VisualEditorIndex.tsx:90-160`:

1. `/visual-editor` and `/visual-editor/` — Visual Editor index landing
2. `/visual-editor/themes`
3. `/visual-editor/focuses`
4. `/visual-editor/widgets`
5. `/visual-editor/documents`
6. `/visual-editor/classes`
7. `/visual-editor/workflows`
8. `/visual-editor/edge-panels`
9. `/visual-editor/registry`
10. `/visual-editor/plugin-registry`

Plus runtime editor:
11. `/runtime-editor`
12. `/runtime-editor/*` (splat for tenant route tree under impersonation)

Both have `/bridgeable-admin/...` path-based equivalents that must redirect identically.

### Internal references catalog

**Navigation entry points**:
- `AdminHeader.tsx:42` — `to={adminPath("/visual-editor")}` (top-level nav link).
- `VisualEditorLayout.tsx:42-52` — `EDITOR_TABS` array enumerating 9 tabs explicitly (Overview + 8 editor tabs).
- `VisualEditorIndex.tsx:90-160` — 9 `EditorCard` instances with hardcoded `to="..."` props.

**Inspector "Open in full editor" deep-links** (3 sites — these become Studio deep links):
- `FocusCompositionsTab.tsx:240` — `adminPath("/visual-editor/focuses")` with `return_to` query param.
- `DocumentsTab.tsx:175` — `adminPath("/visual-editor/documents")` with `return_to`.
- `WorkflowsTab.tsx:146` — `adminPath("/visual-editor/workflows")` with `return_to`.

**Cross-editor navigation buttons** (within editor pages):
- `WidgetEditorPage.tsx:143` — `adminPath("/visual-editor/classes")` ("Cross-class editor" link in top bar).
- `FocusEditorPage.tsx:693,1697` — links to `/visual-editor/widgets` and `/visual-editor/classes`.
- `ClassEditorPage.tsx:686` — link to `/visual-editor/components`.
- `ComponentEditorPage.tsx:835` — link to `/visual-editor/classes`.
- `CompositionEditorPage.tsx:1312` — link to `/visual-editor/components`.

**Documentation references**:
- `CLAUDE.md` references `/visual-editor/*` and `/runtime-editor/*` throughout the §14 Recent Changes log (historic build records — not actionable URLs that need to redirect, but mentioned).
- `STATE.md` — no editor URLs referenced.
- Various `*.md` doc files at `backend/docs/` mention these paths in operational context.

### Redirect strategy

Recommend in-app navigation that translates old URLs to new — NOT 301 redirects at the route level. Rationale:
1. React-router-internal redirects are cheap (a `<Navigate to="...">` element at the old route).
2. Query parameters (`return_to`, `?focus=...`, etc.) need to be preserved through the translation; `<Navigate>` with a function-of-URL pattern handles this cleanly.
3. External bookmarks pointing at `/visual-editor/themes` are rare (admin users — small population), so soft redirect is acceptable.
4. Deep-link buttons in inspector tabs become Studio deep links by changing the URL the `Link` constructs; no redirect needed at the source.

Estimated redirect LOC: ~50-100 LOC for the 10 route redirects + URL-translation helper.

---

## Section 5: Verticals as first-class entity — pre-existing substrate check

### No `verticals` table

Confirmed by:
- `find backend/app/models -name "*.py" | xargs grep -l "tablename.*= .verticals."` returns nothing.
- The closest table is `vertical_presets` (`backend/app/models/vertical_preset.py`), which models **module bundles per vertical** (key + name + description + icon + sort_order + modules relationship). It is NOT a canonical vertical-identity table.

### Tables with `vertical` columns

16 tables carry a `vertical` String column (most as `String(32)` or `String(50)`, nullable):

| Table | Column | Type | Source |
|---|---|---|---|
| `admin_audit_runs` | `scope` (carries `vertical` value) | String(50) | admin_audit_run.py:17 |
| `admin_saved_prompts` | `vertical` | String(50) nullable | admin_saved_prompt.py:19 |
| `admin_staging_tenants` | `vertical` | String(50) | admin_staging_tenant.py:18 |
| `companies` | `vertical` | String(50) nullable | company.py:26 |
| `component_configurations` | `vertical` | String(32) nullable | component_configuration.py:56 |
| `configurable_item_registry` | `vertical` | String(50) | configurable_item_registry.py:23 |
| `dashboard_layouts` | `vertical` | String(32) nullable | dashboard_layout.py:68 |
| `document_templates` | `vertical` | String(32) nullable | document_template.py:68 |
| `extension_definitions` | `applicable_verticals` | Text (JSON) | extension_definition.py:29 |
| `focus_compositions` | `vertical` | String(32) nullable | focus_composition.py:99 |
| `intake_file_configurations` | `vertical` | String(50) nullable | intake_file_configuration.py:67 |
| `intake_form_configurations` | `vertical` | String(50) nullable | intake_form_configuration.py:63 |
| `platform_themes` | `vertical` | String(32) nullable | platform_theme.py:54 |
| `preset_modules` | (indirectly via `preset_id → vertical_presets.id`) | FK | preset_module.py:16 |
| `workflows` | `vertical` | String(50) nullable | workflow.py:52 |
| `workflow_templates` | `vertical` | String(32) nullable | workflow_template.py:57 |

Plus user-side: `User.preferences.spaces[].seeded_for_role` carries `(vertical, role_slug)` tuples (no separate column).

### Canonical vertical slugs

Python codebase scan (regex `"(funeral_home|manufacturing|cemetery|crematory|funeralhome|funeral-home)"` across `backend/app/`):

Slugs found: `{'cemetery', 'crematory', 'funeral_home', 'manufacturing'}`. The 4 canonical slugs. **No variants** (`funeralhome` or `funeral-home`) found. **No drift detected** — the 4 slugs are consistent across all `vertical`-typed columns and all hardcoded references in Python code.

Frontend has a similar consistency: `frontend/src/bridgeable-admin/pages/visual-editor/WidgetEditorPage.tsx:83` declares `const VERTICALS = ["funeral_home", "manufacturing", "cemetery", "crematory"] as const` — single source of truth in the admin tree.

`vertical_presets.key` likely carries the same 4 slugs (the model is data-driven; the seed populates rows whose `key` matches). Did NOT verify seed contents — flagged as a low-confidence finding.

### Backfill implications

If Studio promotes verticals to a first-class table:
- Every `vertical` column on the 14 String-column tables would need an FK migration to point at `verticals.slug` (or `verticals.id`).
- `extension_definitions.applicable_verticals` (Text JSON) would need a junction table.
- Estimated migration scope: ~600-1,000 LOC across 15+ Alembic migrations + rollbacks + tests.
- **This is NOT in the Studio shell arc scope.** Verticals-as-first-class-entity is its own arc with substantial parity-test discipline.

---

## Section 6: Recommended Studio shell arc scope

### Live mode integration: extraction arc, not wrap-and-mount

The runtime-aware editor is mature on inspector-based authoring (theme + class + props + workflows + documents + focus compositions) but is **missing the canon-aspirational drag-to-canvas palette + saved-view authoring**. Wrapping the existing runtime editor as Studio's Live mode is a small UI integration (~200-400 LOC); building the palette and saved-view affordances is a substantial arc (~1,500-3,000 LOC).

**Recommendation**: Studio shell ARC 1 wraps Live mode as-is, exposing only what the runtime editor currently does. Drag-to-canvas palette + saved-view authoring become explicit follow-on arcs (post-Studio-shell), gated on substrate-readiness signals.

### Editor refactor: single arc, no split

Editor refactor surface area (Section 3) totals ~880-1,490 LOC across 9 editors + 600-1,000 LOC for the Studio rail itself = ~1,500-2,500 LOC total. Lands within sub-agent execution ceiling (~2,000-2,500 LOC, per Arc 4b.1 → 4b.1a + 4b.1b precedent). Workflow editor is the hardest case but does not by itself exceed the floor — refactor lands as one arc unless something surfaces during build.

If during build the Workflow editor refactor surfaces unexpected complexity (e.g., the dependent-forks list + metadata pane don't relocate cleanly), the natural split is **Studio shell + 8 simple editor refactors** as 4a / **Workflow editor refactor** as 4b. Decision deferred to build-time per audit-frame-as-uniform discipline.

### Spaces section: defer to follow-up arc

Spaces section in Studio Edit mode requires:
- A `space_templates` or vertical-default spaces table (substrate doesn't exist).
- A platform-admin Spaces API (today's API is per-user only).
- Service-layer 3-tier inheritance walker (today's spaces have no scope concept beyond per-user seeded templates).

This is **~1,500-2,500 LOC of substrate work** alone, before any Studio integration. Bundling it into the Studio shell arc:
- Inflates Studio shell arc above ceiling.
- Forces premature substrate design under shell-arc time pressure.
- Couples Studio launch to a substrate decision that can ship cleanly post-Studio.

**Recommendation**: Studio shell ARC 1 ships **without** the Spaces section. The Studio rail has a "Spaces" entry that surfaces as a disabled / "Coming soon" tab. Spaces substrate arc ships separately when concrete vertical-default-Spaces signal emerges.

### Recommended Studio shell arc decomposition

| Sub-arc | Scope | LOC estimate |
|---|---|---|
| **Studio 1a — shell + rail substrate + redirect** | Studio frame at `/studio` (mounted at PlatformUser auth gate); Studio rail component (tree-shaped browser + edit/live mode toggle + scope picker); redirect 10 standalone routes; redirect runtime-editor route; update VisualEditorIndex + AdminHeader + inspector deep-link buttons. NO editor refactor in this arc — just the shell + rail substrate. | ~1,200-1,800 LOC |
| **Studio 1b — editor left-pane drops (8 simple editors)** | Refactor 8 editors (Themes / Focus / Widgets / Documents / Classes / Edge Panels / Registry / Plugin Registry) to accept Studio-context prop + drop left pane when present. Each editor remains mountable standalone (backwards compat for one release). | ~700-1,000 LOC |
| **Studio 1c — Workflow editor refactor** | Workflow editor's left pane is the hardest case (richest content: dependent-forks + metadata pane in addition to scope/vertical/type selectors). Refactor to relocate dependent-forks + metadata pane to center or right rail; drop scope/vertical/type selectors when in Studio context. | ~250-400 LOC |
| **Studio 1d — Live mode integration (wrap-and-mount)** | Mount the existing runtime editor inside Studio's Live mode as-is. No new editing affordances — the existing inspector + click-to-select continues to work. Studio rail's Live mode toggle drives URL-state to match `/runtime-editor/*` semantics (preserving impersonation context). | ~400-700 LOC |

**Total Studio shell arc**: ~2,550-3,900 LOC across 4 sub-arcs. Each sub-arc lands within the ~2,000-2,500 LOC sub-agent execution ceiling.

**Sequencing**: 1a → 1b → 1c → 1d. 1a establishes substrate; 1b and 1c are independent editor refactors that could parallelize but conventionally serialize for review coherence; 1d depends on 1a's Studio rail mode-toggle being in place.

### What's NOT in Studio shell arc scope

- Spaces section as first-class Studio tab (requires substrate arc — see Section 2 gap).
- Verticals as first-class entity (requires migration arc — see Section 5).
- Drag-to-canvas palette in Live mode (requires runtime editor expansion arc).
- Saved-view drag-to-canvas authoring (requires runtime editor + saved-view substrate work).
- Multi-tenant impersonation switcher inside Studio (today's runtime editor requires re-pick to switch tenants — Studio could improve this but it's a separate UX arc).
- Standalone editor deletion (the 10 standalone routes redirect but the underlying editor components stay mountable for one release as backwards-compat; deletion arc lands post-Studio-shell when redirect adoption is verified).

---

## Most consequential finding

**Live mode integration is a wrap-and-mount arc; Spaces section is post-shell substrate work.** The runtime editor is more mature than the audit framing implies (6 inspector tabs already authoring against the same substrate the 7 standalone editors edit), but it lacks the drag-to-canvas palette and saved-view authoring the canon describes — those are aspirational, not built. The Studio shell arc can therefore ship Live mode by wrapping the existing runtime editor verbatim (~400-700 LOC integration), deferring palette + saved-view affordances to follow-on arcs. Spaces as first-class Studio section requires net-new substrate (~1,500-2,500 LOC) before Studio integration — bundling it inflates the shell arc above sub-agent execution ceiling and couples Studio launch to substrate decisions that can ship cleanly post-shell. Recommended 4-sub-arc decomposition keeps each piece within ceiling.

---

[end findings — validation gates not applicable to read-only investigation phase]
