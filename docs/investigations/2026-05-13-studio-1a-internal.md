# Bridgeable Studio 1a — internal investigation findings

Read-only second-pass investigation. Builds on `/tmp/studio_shell_investigation_findings.md` (the outer Studio shell arc findings); does not re-investigate what's settled there. Focus is the internal decomposition of Studio 1a — URL state, rail substrate, overview surface, Live mode wrap mechanics, verticals-lite precursor, and the cut between Studio 1a and 1b/1c.

---

## Section 1: Studio routing and URL state model

### URL scheme recommendation (path-segment-canonical)

| Surface | URL |
|---|---|
| Studio landing, Platform scope | `/studio` |
| Studio landing, Wastewater scope | `/studio/wastewater` |
| Edit mode, specific editor (Themes) at Platform scope | `/studio/themes` |
| Edit mode, specific editor (Themes) at vertical scope | `/studio/wastewater/themes` |
| Edit mode, Focus editor with template deep-link | `/studio/wastewater/focuses?template=funeral-scheduling&category=decision` |
| Live mode pre-impersonation (picker) | `/studio/live` |
| Live mode pre-impersonation, vertical-pre-filtered picker | `/studio/live/wastewater` |
| Live mode active, specific tenant+user | `/studio/live/wastewater?tenant=hopkins-fh&user=director1` |
| Live mode, click-selected component on a specific page | `/studio/live/wastewater/dashboard?tenant=...&user=...&edit=1&selected=delivery-card` |

The path-segment carries everything that fundamentally changes the shell's render shape (Edit vs Live, Platform vs vertical, which editor). Query parameters carry editor-internal deep-link state (`?template=...&category=...`), impersonation context (`?tenant=...&user=...`), and edit-mode-within-Live state (`?edit=1&selected=...`).

### Mode (Edit/Live) as path segment

Mode lives in the path: `live` is a reserved first-position segment that means "Live mode." Anything else in first position is a vertical slug (or omitted for Platform scope).

Rationale:
- Mode determines fundamentally different shell shape — Edit mode mounts editor panes; Live mode mounts the impersonated tenant route tree under TenantProviders. These can't render simultaneously.
- Path-segment mode makes redirects deterministic at the React-router level: one `<Route>` entry per mode without query-param resolution logic.
- Bookmark + back-button semantics are cleaner: an operator's URL bar reflects which mode they're in without inspecting query params.
- Path-segment matches existing precedent: `/runtime-editor/*` (Live-like) and `/visual-editor/*` (Edit-like) are already path-segment-distinguished today.

Alternative considered: `?mode=edit|live` query param. Rejected because route-level distinction is more legible and avoids `useSearchParams` + suspense gymnastics inside the shell.

### Scope (Platform / vertical) as path segment

Scope is the first non-mode path segment. `vertical` slug strings (`manufacturing`, `funeral_home`, `cemetery`, `crematory`, plus future verticals) sit in this position. Absence = Platform scope.

Edge cases:
- `/studio/themes` is ambiguous IF a vertical slug happens to equal an editor key. Today none do (verticals are noun-singular like `wastewater`; editors are noun-plural-or-name like `themes`, `focuses`, `widgets`, `documents`, `classes`, `workflows`, `edge-panels`, `registry`, `plugin-registry`). Defensive measure: reserve the 8 editor keys + `live` + `admin` as forbidden vertical slugs in the `verticals` seed and validate at the API + admin-create-vertical layer. Estimated guard work: ~20 LOC.
- "Remember last vertical" — Studio rail's vertical selector defaults to whatever path the URL carries. If the operator navigates to `/studio/themes` (no vertical), the rail shows Platform scope. Rail persists last-used-vertical to `localStorage` (key: `studio.lastVertical`) and applies it when the operator clicks an editor link from the Platform-scope overview (interpretation: "click Themes from Wastewater overview → land on `/studio/wastewater/themes`; click Themes from Platform overview → land on `/studio/themes`"). LocalStorage chosen over PlatformUser preferences because `PlatformUser` has no `preferences` JSONB column today (confirmed via `backend/app/models/platform_user.py`); adding one is out of scope for Studio 1a.

### Redirect translation table (10 standalone routes)

| Source | Target |
|---|---|
| `/visual-editor` (index) | `/studio` |
| `/visual-editor/themes` | `/studio/themes` (Platform scope default) OR `/studio/{lastVertical}/themes` if localStorage carries one |
| `/visual-editor/focuses` (+ `?focus_type=X&template_id=Y`) | `/studio/{lastVertical||platform}/focuses?template=Y&category=X` |
| `/visual-editor/widgets` (+ `?mode=individual\|class\|layouts`) | `/studio/{scope}/widgets?mode=X` (mode is a Widget Editor-internal concern, stays as query param) |
| `/visual-editor/documents` (+ `?template_id=...`) | `/studio/{scope}/documents?template=...` |
| `/visual-editor/classes` | `/studio/classes` (Platform-only — `component_class_configurations` has no vertical scope per `r83_component_class_configurations`) |
| `/visual-editor/workflows` (+ `?workflow_type=X&scope=...`) | `/studio/{scope}/workflows?workflow_type=X` |
| `/visual-editor/edge-panels` | `/studio/{scope}/edge-panels` |
| `/visual-editor/registry` | `/studio/registry` (Platform-only) |
| `/visual-editor/plugin-registry` | `/studio/plugin-registry` (Platform-only) |
| `/runtime-editor` (picker) | `/studio/live` |
| `/runtime-editor/?tenant=X&user=Y` | `/studio/live?tenant=X&user=Y` — Studio Live-mode shell resolves `Company.vertical` from tenant slug post-mount and canonicalizes URL to `/studio/live/{vertical}?tenant=X&user=Y` via `<Navigate replace>` |
| `/runtime-editor/dashboard?tenant=X&user=Y&edit=1` | `/studio/live/dashboard?tenant=X&user=Y&edit=1` (the path segment after `live` is the tenant route path; Studio Live shell resolves vertical post-mount and canonicalizes) |

Query parameters carry through verbatim. `return_to` parameters (inspector deep-link "Open in full editor" buttons per Arc-3.x-deep-link-retrofit) translate from old URLs to new URLs via a small in-app translator helper (~30 LOC). Inspector tab code at `frontend/src/lib/runtime-host/inspector/FocusCompositionsTab.tsx:240`, `DocumentsTab.tsx:175`, `WorkflowsTab.tsx:146` updates to construct `/studio/{vertical}/{editor}` URLs directly rather than `/visual-editor/{editor}` URLs.

Redirect implementation: React-router `<Navigate>` elements at each old route, NOT 301 server-side redirects. Rationale recorded in previous findings Section 4. Estimated redirect-layer LOC: ~80-120 LOC (10 redirect routes + URL-translator helper for query-param preservation + vertical resolver for the runtime-editor → studio/live mapping).

### Impersonation handshake URL interaction

Live mode requires tenant + user. Three reachable URL shapes during a Live session:

1. `/studio/live` — no impersonation; Studio mounts `<TenantUserPicker />` (existing component at `frontend/src/bridgeable-admin/pages/runtime-editor/TenantUserPicker.tsx`).
2. `/studio/live/{vertical}` — Studio mounts the same picker but pre-filters tenant list to that vertical's tenants. Picker accepts a new optional `verticalFilter` prop (~10 LOC addition to TenantPicker).
3. `/studio/live/{vertical}?tenant=...&user=...` — canonical Live URL with active impersonation. Studio shell mounts the runtime editor inside.

When a tenant+user is selected, Studio sees `Company.vertical` from the impersonation API response (existing field per `TenantUserPicker.tsx:36-43`) and constructs the canonical URL. If the operator initially landed at `/studio/live` (no vertical) and picks a tenant whose vertical is `wastewater`, Studio navigates to `/studio/live/wastewater?tenant=...&user=...` via `useNavigate({ replace: true })` post-impersonation.

### Inspector deep-link "Open in full editor" — Studio-context-aware

Inspector tabs use `adminPath("/visual-editor/...")` today (FocusCompositionsTab.tsx:240, DocumentsTab.tsx:175, WorkflowsTab.tsx:146). Each carries a `return_to` query param so the standalone editor offers a "Back to runtime editor" banner.

Inside Studio (where runtime editor is wrapped at `/studio/live/...`), inspector deep-links should construct Studio URLs:
- Source: inspector in Live mode at `/studio/live/wastewater/dashboard?...`
- Click "Open in full editor" on Focus compositions
- Target: `/studio/wastewater/focuses?return_to=<encoded source URL>`

The redirect layer handles this transparently IF the deep-link uses the new path. But the existing inspector code constructs the old `/visual-editor/` path; that path's redirect would also work but creates a double-navigation (visual-editor → studio). Cleaner: update the 3 inspector deep-link constructors to construct `/studio/{vertical}/{editor}` URLs directly when in Studio context, falling back to `/visual-editor/{editor}` when standalone-mounted.

Detection: inspector reads `location.pathname.startsWith("/studio/live/")` to know it's inside Studio. ~15 LOC across 3 files.

Recommendation: do the direct construction update in Studio 1a (avoid redirect chain). The cleanup is small + improves the back-banner URL preservation.

---

## Section 2: Studio rail substrate

### Existing precedent inspection

Two layouts exist in the admin tree:

- **`AdminLayout`** (`frontend/src/bridgeable-admin/components/AdminLayout.tsx`, 28 LOC) — slate-chrome wrapper for operational admin pages (Health Dashboard, Tenants Kanban, etc.). Header + main, NO left rail.
- **`VisualEditorLayout`** (`frontend/src/bridgeable-admin/components/VisualEditorLayout.tsx`, 154 LOC) — warm-tokens wrapper for the 9 visual editor pages. Header with top nav-tab strip + scope-indicator banner below + main. NO left rail.

Neither layout has a persistent left rail. **Studio rail is net-new substrate.** No "adapt existing rail" path available.

The inspector panel (`frontend/src/lib/runtime-host/inspector/InspectorPanel.tsx`) is a right-rail at 380px width with tab strip + content. It's not a precedent for a Studio left rail because it's component-selection-driven (mounts only when a component is selected in Live mode), not page-level navigation. Different mental model.

### Component architecture — one component, two render modes

Single `<StudioRail />` component with `expanded` boolean state:
- `expanded = true` → renders full ~240px column with section list + scope indicator + nested editor browser when an editor is open.
- `expanded = false` → renders ~48px icon-strip column with vertical stack of icons + collapsed scope indicator.

The two render modes share state (current section, current scope, scope indicator). Toggling expand/collapse is a CSS class flip + width animation. Two-components-with-shared-state was considered and rejected: state synchronization across two siblings adds ~30 LOC of effect/reducer plumbing for zero functional benefit.

### Coexistence with editor's own left pane

The prompt explicitly says: "Collapse to an icon strip when an editor's own left rail is in use / Expand back from icon-strip click."

This contradicts the previous findings (`/tmp/studio_shell_investigation_findings.md` Section 3), which recommended editors DROP their left pane when in Studio context. **The current prompt's framing is correct; the previous findings' recommendation was wrong on this point.**

Canonical interaction model per this prompt:
- When Studio rail is **expanded**: shows Studio sections (Overview, Themes, Focuses, Widgets, Documents, Classes, Workflows, Edge Panels, Registry, Plugin Registry, Live mode link). Editor's own left pane is **hidden** while Studio rail occupies the left area. Editor's center pane uses the freed horizontal space.
- When Studio rail is **collapsed** (icon strip): shows ~10 section icons in a 48px column. Editor's own left pane renders to the right of the icon strip. Two left areas: 48px Studio icons + ~320px editor browser.

Toggle:
- Click icon strip → expand Studio rail, hide editor's left pane.
- Click expand-button on Studio rail header → collapse to icon strip, show editor's left pane.

This is materially different from the previous findings' "drop the left pane" recommendation. **It's a much lighter editor refactor.** Editors don't drop their left panes; they accept a `studioRailExpanded` prop (or read it from a context) and hide their left pane when Studio rail is expanded.

Per-editor refactor LOC under this model: ~30-60 LOC each (conditional `display: none` on the left pane when context says Studio rail is expanded). The Workflows editor's complicated metadata + dependent-forks panes remain in place; they just hide when Studio rail expands. **This collapses the previous findings' ~880-1,490 LOC editor refactor to ~300-500 LOC of mostly mechanical work.**

### Rail state location

Two pieces of rail state:
- **Expanded/collapsed**: transient UI state. Persist to `localStorage` (key `studio.railExpanded`, default `true`). PlatformUser preferences would be ideal cross-device but PlatformUser has no preferences JSONB column today — see Section 5 for the precursor work that would unlock cross-device preference storage but is itself out of scope.
- **Current section**: derived from URL pathname. No separate state needed.
- **Scope indicator** (Platform / vertical): also derived from URL.

Out-of-scope for Studio 1a:
- Rail rearrangement (operator reorders sections).
- Rail customization per platform user.
- Section grouping or collapsible section groups beyond the icon-strip-vs-expanded distinction.

### Smallest viable rail for Studio 1a

The minimum viable rail:
- Fixed list of sections, derived at render time from the active vertical's available editors (Platform scope: Themes, Classes, Registry, Plugin Registry, Live mode link, Admin sub-section for verticals management; Vertical scope: Themes, Focus Editor, Widget Editor, Documents, Workflows, Edge Panels, Live mode link).
- Expand/collapse toggle.
- Active-section highlight (URL-driven).
- Scope picker integrated at the top of the rail (Platform / list-of-verticals selectbox).

Estimated rail component LOC: ~250-400 LOC for the substrate + icon-strip mode.

---

## Section 3: Studio overview surface

### Backend query shape for "all artifacts for vertical X"

Six substrate tables carry `vertical` columns + `updated_at` columns (verified via `grep updated_at` across the model files):

| Table | Vertical column? | updated_at? | Versioned? |
|---|---|---|---|
| `platform_themes` (r79) | ✅ String(32) nullable | ✅ | Write-side versioned (`is_active` partial unique) |
| `focus_compositions` (r84) | ✅ String(32) nullable | ✅ | Write-side versioned |
| `workflow_templates` (r82) | ✅ String(32) nullable | ✅ | Write-side versioned |
| `document_templates` (r86 added vertical) | ✅ String(32) nullable | ✅ | Versioned via `document_template_versions` join |
| `component_configurations` (r81) | ✅ String(32) nullable | ✅ | Write-side versioned |
| `dashboard_layouts` (r87) | ✅ String(32) nullable | ✅ | Write-side versioned |
| `component_class_configurations` (r83) | ❌ (class_default scope only) | ✅ | Versioned |

Recommended pattern: `app/services/vertical_inventory/inventory_service.py` with `get_inventory(db, *, vertical)` and `get_inventory(db, *, platform=True)` overloads. One service module, fan-outs 6 small queries (each filtering by `is_active = True AND vertical = <X>`, counting rows + selecting most recent 5 by `updated_at`).

Implementation shape (~150-250 LOC service-layer):
```python
def get_inventory(db: Session, *, vertical: str | None) -> InventoryReport:
    """Return artifact counts + recent edits for a vertical, or for
    Platform scope (vertical=None means platform_default rows only).
    """
    return InventoryReport(
        themes=_count_and_recent(db, PlatformTheme, vertical=vertical),
        focus_compositions=_count_and_recent(db, FocusComposition, vertical=vertical),
        workflow_templates=_count_and_recent(db, WorkflowTemplate, vertical=vertical),
        document_templates=_count_and_recent(db, DocumentTemplate, vertical=vertical),
        component_configurations=_count_and_recent(db, ComponentConfiguration, vertical=vertical),
        dashboard_layouts=_count_and_recent(db, DashboardLayout, vertical=vertical),
        # component_class_configurations is class_default-only;
        # only surfaces in Platform scope, exposed as a separate count.
        component_class_configurations=(
            _count_and_recent_class_default(db) if vertical is None else None
        ),
    )
```

`_count_and_recent` is a generic helper: `SELECT COUNT(*), <recent rows>` filtered by scope + active. ~30-50 LOC.

### Recent-edits feed query shape

Union over 6 tables of `(updated_at, type, id, version, scope)`. No audit-log join needed — the substrate tables themselves have `updated_at` columns + `version` columns (verified). Six small queries each returning last 20 rows ordered `updated_at DESC`; in-Python merge sort + truncate to 20.

```python
def get_recent_edits(db: Session, *, vertical: str | None, limit: int = 20) -> list[RecentEdit]:
    edits: list[RecentEdit] = []
    for cls, type_label in [
        (PlatformTheme, "theme"),
        (FocusComposition, "focus_composition"),
        # ...
    ]:
        rows = db.query(cls).filter(_scope_filter(cls, vertical=vertical)).order_by(cls.updated_at.desc()).limit(limit).all()
        edits.extend(_to_recent_edit(r, type_label) for r in rows)
    edits.sort(key=lambda e: e.updated_at, reverse=True)
    return edits[:limit]
```

~80-120 LOC for the union helper.

### API surface

Single endpoint per scope:
- `GET /api/platform/admin/studio/inventory?vertical={slug}` (vertical=null implies Platform scope)
- `GET /api/platform/admin/studio/inventory/recent?vertical={slug}&limit={N}`

PlatformUser auth. Pydantic response models match the `InventoryReport` + `RecentEdit` dataclasses. ~80-120 LOC.

### Holes detection (v1+1 scope; deferred from v1)

Detectable from substrate inspection alone (no operator intent inference):

| Hole shape | Detection query | v1 | v1+1 |
|---|---|---|---|
| Focus template registered in code but no composition row at vertical scope | `getAllRegistered("focus-template")` on frontend; cross-reference with `focus_compositions` query filtered by vertical | — | ✅ |
| Document type with no templates at vertical scope | Document type catalog from D-10 vs `document_templates` filtered by vertical + type | — | ✅ |
| Vertical with no themes overridden | `platform_themes WHERE vertical = <X> AND is_active = True` returns 0 rows | — | ✅ |
| Workflow type with no template at vertical scope | Hardcoded workflow type catalog vs `workflow_templates` filtered by vertical + type | — | ✅ |
| Widget declared in WIDGET_DEFINITIONS but no `dashboard_layouts` row referencing it at vertical scope | WIDGET_DEFINITIONS list vs `dashboard_layouts.layout_config` JSONB scan (more expensive — defer) | — | ✅ (deferred) |

**Recommendation: v1 ships counts + recent-edits feed only.** Holes detection is a separate `holes_service.detect(vertical)` aggregator that lands v1+1 (~200-300 LOC for the 5 holes above, defensible as a follow-on once operator signal confirms holes are the right framing).

### Frontend component shape

Reuse the existing card-grid pattern from `frontend/src/bridgeable-admin/pages/visual-editor/VisualEditorIndex.tsx:90-160` (9 `EditorCard` entries in a 2-col grid). Adapt:
- Per-artifact-type card showing count + most recent edit timestamp.
- Click navigates into the editor at the relevant scope.
- Recent edits feed below the card grid (chronological list of last 20 edits with type icon + scope badge + relative timestamp).

Estimated frontend LOC: ~300-500 LOC across `StudioOverview.tsx` + `RecentEditsFeed.tsx` + `inventory-service.ts` (the axios client wrapping the new endpoints).

---

## Section 4: Live mode wrap in Studio 1a

### Wrap meaning: mount the existing RuntimeEditorShell as a child

Concretely: Studio renders `<RuntimeEditorShell />` (existing component at `frontend/src/bridgeable-admin/pages/runtime-editor/RuntimeEditorShell.tsx`, ~400 LOC) as the child of the `/studio/live/{vertical}/*` route. Do **not** replicate the shell's constituent parts (TenantProviders, TenantRouteTree, SelectionOverlay, InspectorPanel, EditModeToggle, Focus modal).

Rationale:
- RuntimeEditorShell already handles: auth gate (super_admin / platform_admin / support), missing-params (TenantUserPicker as child), loading + error + forbidden states, Suspense fallback, admin ribbon, Focus modal mount (R-2.0.4), theme resolve+apply effect on mount (R-1.6.14), 10s loading-timeout recovery affordance (R-7-α), and the whole TenantProviders + TenantRouteTree wiring.
- Replicating that loses ~400 LOC of battle-tested behavior + ships a known-good runtime editor inside Studio with minimal risk.

Wrap pattern:
```tsx
// frontend/src/bridgeable-admin/pages/studio/StudioLiveModeWrap.tsx
import RuntimeEditorShell from "../runtime-editor/RuntimeEditorShell"

export default function StudioLiveModeWrap() {
  // Studio top bar already rendered by StudioShell ancestor.
  // We just mount the runtime editor; it handles everything else.
  return <RuntimeEditorShell studioContext />
}
```

Pass `studioContext` prop (~3-5 LOC addition to RuntimeEditorShell) so it knows to suppress its own admin ribbon (Studio top bar is providing the equivalent). The floating EditModeToggle, InspectorPanel, SelectionOverlay, and Focus modal all stay — they are component-selection-and-interaction surfaces, not page-chrome.

### Admin chrome coexistence inventory

| Element | Source | Conflict? | Resolution |
|---|---|---|---|
| Admin ribbon (h-8 yellow bar showing tenant slug + impersonated user id) | RuntimeEditorShell.tsx:368-380 | ✅ Conflicts with Studio top bar | Suppress when `studioContext` prop is true; Studio top bar shows equivalent info |
| Floating EditModeToggle (bottom-right corner) | `frontend/src/lib/runtime-host/EditModeToggle.tsx` | No | Stays floating; orthogonal to Studio top bar |
| InspectorPanel (right rail, 380px) | `frontend/src/lib/runtime-host/inspector/InspectorPanel.tsx` | No | Stays as-is; Studio rail is left side, no overlap |
| SelectionOverlay (invisible full-page click handler) | `frontend/src/lib/runtime-host/SelectionOverlay.tsx` | No | Stays as-is; invisible interaction layer |
| Focus modal mount | RuntimeEditorShell.tsx:205 | No | Stays as-is; mounted inside the editor's TenantProviders subtree |
| Studio rail (icon strip when editor is open OR expanded) | Studio shell | No | Studio's left side; no overlap with runtime editor's right-side InspectorPanel |
| Studio top bar (scope, tenant indicator, mode toggle) | Studio shell | ✅ Conflicts with admin ribbon | Studio top bar wins; admin ribbon hides via prop |

The cleanest resolution is **one top bar (Studio's), one left rail (Studio's), one right rail (runtime editor's InspectorPanel), one floating toggle (EditModeToggle), one invisible click handler (SelectionOverlay)**. No element duplication. Cross-cutting state (impersonated tenant slug, user id) appears in Studio's top bar; runtime editor reads its own URL params for the rest.

### Scope picker × tenant impersonation interaction

Recommendation: **Live mode replaces scope-picker semantics — scope in Live means "this tenant's vertical."**

In Edit mode, the scope picker selects the authoring tier (Platform / Vertical). In Live mode, scope is determined by the impersonated tenant's `Company.vertical`, which is implicit in the tenant selection. The scope picker in Live mode is therefore informational (read-only display showing "Wastewater — via tenant Hopkins FH"), not interactive.

This avoids forcing the operator to pick vertical THEN pick tenant when tenant determines vertical anyway. The reverse pick (vertical first → tenant within vertical) is the canonical entry flow described in Section 1 (`/studio/live/wastewater` → picker pre-filtered).

The alternative recommendation (separate scope picker + tenant+user picker in Live mode) is rejected because it duplicates the vertical selection at two layers — the vertical is already encoded in the tenant's metadata.

Forward path: if operators want to author at vertical_default scope WHILE seeing a specific tenant's runtime — that's a mode that doesn't exist today (the runtime editor authoring scope is always vertical_default for the impersonated tenant's vertical, per `runtime-writers.ts:11-22`). Studio 1a preserves this. Tenant_override scope authoring is a separate UX arc.

### Impersonation handshake inside Studio

Today: `TenantUserPicker` is rendered as a child of `RuntimeEditorShell` when impersonation params are missing (`RuntimeEditorShell.tsx:341-361`).

Inside Studio:
- Operator clicks "Live mode" in Studio top bar OR in the rail → navigate to `/studio/live` (no params).
- If current Edit-mode scope is Wastewater, navigate to `/studio/live/wastewater` (pre-filter the picker).
- StudioLiveModeWrap mounts RuntimeEditorShell with `studioContext` prop; shell sees no tenant/user params and renders the picker as its child.
- Picker (with new optional `verticalFilter` prop) shows tenants filtered to the vertical from URL path.
- Operator picks → impersonation POST → response carries `Company.vertical` → navigate to canonical URL `/studio/live/{vertical}?tenant=...&user=...`.

If operator lands at `/studio/live` (no vertical), picker shows all tenants. On selection, Studio canonicalizes URL.

### Mode toggle Edit ↔ Live preserves scope

| Source state | Mode toggle action | Target state |
|---|---|---|
| `/studio/themes` (Platform, Edit) | → Live | `/studio/live` (picker, no vertical filter) |
| `/studio/wastewater/themes` (Wastewater, Edit) | → Live | `/studio/live/wastewater` (picker pre-filtered to Wastewater) |
| `/studio/live/wastewater?tenant=...&user=...` (Live active) | → Edit | `/studio/wastewater` (overview, scope retained) |
| `/studio/live` (Live picker, no tenant) | → Edit | `/studio` (Platform overview) |
| `/studio/live/wastewater` (Live picker pre-filtered, no tenant) | → Edit | `/studio/wastewater` (overview at scope) |

Scope is preserved across mode flips. Tenant state is preserved across Edit→Live (resumes if same tenant context exists) but lost across Live→Edit (Edit has no tenant concept).

Implementation: a single helper `function toggleMode(currentPath, toMode): newPath` does the URL translation. ~40-60 LOC.

---

## Section 5: Verticals-as-first-class (lite) substrate

### Migration shape

`r92_verticals_table` (next-available migration ID; current head is `r91_compositions_kind_and_pages`).

Columns:
- `slug` String(32) primary key (matches the existing 4 canonical slugs in `vertical` String columns across 16+ tables)
- `display_name` String(100) NOT NULL
- `description` Text nullable
- `status` String(32) NOT NULL default `'published'` — CHECK constraint enumerating `'draft' | 'published' | 'archived'`
- `icon` String(50) nullable
- `sort_order` Integer NOT NULL default 0
- `created_at`, `updated_at` DateTime(timezone=True) following the existing convention

Seed: 4 INSERT statements during upgrade for `manufacturing`, `funeral_home`, `cemetery`, `crematory` with sort_order 10, 20, 30, 40 and human-readable display names.

No FK migration of existing `vertical` String columns — those continue pointing at slug strings, which match `verticals.slug` by value.

Migration LOC estimate: ~90-130 LOC (table create + 4 seed inserts + downgrade with drop_table).

### Model

`app/models/vertical.py` — ~30-40 LOC SQLAlchemy ORM matching the migration shape. Pattern mirrors `app/models/vertical_preset.py` (which exists for module bundles, not vertical identity per previous findings Section 5).

### Service layer

`app/services/verticals_service.py` with:
- `list_verticals(db: Session, *, include_archived: bool = False) -> list[Vertical]`
- `get_vertical(db: Session, slug: str) -> Vertical` (raises `VerticalNotFound`)
- `update_vertical(db: Session, slug: str, *, display_name: str | None, description: str | None, status: str | None, icon: str | None, sort_order: int | None) -> Vertical`

No `create_vertical` or `delete_vertical` for v1 (per the build prompt's constraint — the four canonical slugs are seeded; adding a fifth is a deliberate platform decision that warrants its own migration + audit).

LOC estimate: ~80-120 LOC.

### API surface

`app/api/routes/admin/verticals.py` with:
- `GET /api/platform/admin/verticals/` → list
- `GET /api/platform/admin/verticals/{slug}` → get
- `PATCH /api/platform/admin/verticals/{slug}` → update

PlatformUser auth via `Depends(get_current_platform_user)`. Register in `app/api/platform.py`.

LOC estimate: ~100-130 LOC.

### Frontend admin page

Lives at `/studio/admin/verticals` (inside the Studio shell — once Studio 1a ships). For the precursor, it can live at `/bridgeable-admin/admin/verticals` and migrate to `/studio/admin/verticals` as part of Studio 1a's redirect work.

Page shape: simple table with 4 rows (one per seeded vertical), inline edit affordances for display_name + description + status + sort_order. Reuse existing admin form primitives.

`verticals-service.ts` typed axios client wrapping the 3 endpoints.

LOC estimate: ~200-300 LOC across the page + service client + per-row edit modal.

### Total precursor arc LOC

~500-720 LOC across: migration + model + service + API + frontend service + admin page + tests. Within sub-agent execution ceiling. Single arc.

### Lite-vs-full split subtleties

Concerns to flag:

1. **Slug immutability**: With String columns referencing `verticals.slug` by value (not FK), renaming a slug (e.g., `funeral_home` → `funeralhome`) would orphan every `vertical` column value. **Recommendation: enforce slug immutability at the service layer** — `update_vertical` does NOT accept a `slug` parameter; slug is the primary key and cannot be changed. Cross-reference: the canonical slugs are already locked across the codebase (previous findings Section 5 confirmed no slug drift), so immutability is canon-faithful.

2. **Orphan-data risk on insert**: A typo in a manual SQL insert or seed update could create a `dashboard_layouts.vertical = 'funeral-home'` (with hyphen) that doesn't match `verticals.slug = 'funeral_home'` (with underscore). No DB-level constraint catches this. **Mitigation: at the service-layer, validate every write to a `vertical`-column table against the `verticals` table's slug set.** This is a defensive guard at the read-modify-write boundary. Out of scope for the verticals-lite precursor (~50-100 LOC of writer-validation discipline across the existing services) — flag as a v1+1 candidate.

3. **Audit-trail concerns**: None. The `verticals` table itself has created_at/updated_at; the existing tables' write-side versioning preserves history.

4. **Referential-integrity concerns**: No FK is intentional. A future arc can add FKs once the platform stops admitting new String-column tables with `vertical`. Lock-in note: any new migration that adds a `vertical` column should reference `verticals.slug` as an FK from inception — establish that as a CLAUDE.md convention post-verticals-lite ship.

5. **The `vertical_preset` table coexists**: `vertical_presets` is a separate concept (module bundles per vertical) and is NOT renamed or migrated. The `verticals` table sits beside it. Future work could merge: a vertical_preset row could carry a FK to verticals.slug. Out of scope for the precursor.

---

## Section 6: Studio 1a internal decomposition recommendation

### Revised LOC estimate per the rail-keeps-editor-pane finding

The previous findings estimated Studio 1a at ~1,200-1,800 LOC and per-editor refactor (Studio 1b/1c) at ~1,500-2,500 LOC for an aggressive "drop editor left panes in Studio context" approach. **Section 2 of this investigation revises that:** the rail collapses to icon-strip when editor's left pane is in use, so editors keep their left panes. Per-editor refactor collapses to ~30-60 LOC each × 9 editors = ~300-500 LOC for the whole "editor adaptation pass."

Studio 1a's internal pieces, revised:
| Piece | LOC estimate |
|---|---|
| Studio routing + URL state model + redirect layer (Section 1) | ~250-400 |
| Studio rail component (substrate, icon-strip + expanded modes, scope picker integration) (Section 2) | ~250-400 |
| Studio overview surface — counts + recent edits (Section 3) | ~500-700 (backend + frontend) |
| Live mode wrap (Section 4) — `<StudioLiveModeWrap>` + `studioContext` prop addition to RuntimeEditorShell + chrome conflict resolution + impersonation handshake integration + mode-toggle URL helper | ~300-500 |
| Editor adaptation pass — 9 editors accept `studioRailExpanded` context + conditional left-pane hide (Section 2's revised model) | ~300-500 |
| Tests (vitest for rail + overview; backend pytest for inventory service + API; Playwright smoke for redirect chain) | ~600-900 |
| **Subtotal Studio 1a** | **~2,200-3,400 LOC** |

Lands above the ~2,000-2,500 sub-agent execution ceiling. **Recommend split.**

### Cut: Studio 1a-i + Studio 1a-ii

**Studio 1a-i — "Studio launched" minimum viable shell** (~1,100-1,600 LOC):
- Studio routing + URL state model (Section 1)
- Redirect layer for 10 standalone routes + runtime-editor redirect
- Studio rail component (icon-strip + expanded; scope picker; section list per scope)
- Editor adaptation pass (9 editors accept `studioRailExpanded` context)
- Placeholder overview surface at `/studio` and `/studio/{vertical}` (empty card grid with "No artifacts yet" or static section descriptions)
- Tests for routing, rail, editor adaptation

**Studio 1a-ii — "Studio populated + Live mode"** (~1,100-1,800 LOC):
- Overview surface implementation: `inventory_service` backend + `inventory-service.ts` frontend + StudioOverview.tsx + RecentEditsFeed.tsx
- Live mode wrap: StudioLiveModeWrap + `studioContext` prop on RuntimeEditorShell + admin-ribbon suppression + impersonation handshake integration + mode-toggle URL helper
- Tests for inventory queries, recent-edits feed, Live mode wrap chrome coexistence
- Tests for impersonation handshake inside Studio

### Defense of the cut

Studio 1a-i ships a coherent "Studio launched" experience to the operator: they can navigate to `/studio`, see the rail, click into any editor, edit at platform or vertical scope, hit redirects from old URLs. What's missing is the overview content (placeholder) and the Live mode button does nothing yet (or shows "Coming in Studio 1a-ii"). This is shippable — operator productivity is unimpaired because the existing standalone editors all redirect into Studio cleanly + remain functional via Studio rail.

Studio 1a-ii is the "Studio is now richer" follow-on: overview surface shows real counts + recent edits, Live mode reaches the runtime editor through Studio's chrome. 1a-ii depends on 1a-i (Studio rail must exist for Live mode toggle to live there) but is independent of 1b/1c.

### Sequencing within Studio 1a

Mandatory ordering:
1. **Verticals-lite precursor** (Section 5, ~500-700 LOC) — Studio rail's scope picker reads `/api/platform/admin/verticals/` for the vertical list. Without verticals-lite, scope picker hard-codes 4 slugs (acceptable but not future-proof; better to land verticals-lite first).
2. **Studio 1a-i** — shell + rail + redirect + editor adaptation. Sub-pieces serialize: routing → rail → adaptation → tests.
3. **Studio 1a-ii** — overview meat + Live mode. Sub-pieces parallelize but conventionally serialize for review coherence: inventory service backend → overview frontend → Live mode wrap → tests.

Studio 1b (per the previous findings, "editor adaptation pass") is **subsumed** into Studio 1a-i under the rail-collapses-when-editor-pane-active model. Previous findings' Studio 1b/1c → no longer separate arcs; the work folds into Studio 1a-i at lighter scope.

### Smallest viable Studio 1a

Studio 1a-i alone is the smallest viable "Studio launched" shell:
- Operator sees Studio at `/studio`.
- Rail shows sections, scope picker, editor list per scope.
- Click an editor → mounts the existing editor inside Studio shell with its own left pane.
- All 10 standalone routes redirect into Studio.
- Live mode link goes to `/studio/live` which mounts existing RuntimeEditorShell at the old URL via a placeholder redirect (or shows "Live mode coming in 1a-ii").
- Overview shows section list with static descriptions, no inventory counts yet.

Studio 1a-ii is the visible-quality-improvement follow-on.

### What can defer to 1b/1c

Per the previous findings' framing, 1b was "8 simple editor refactors" and 1c was "Workflow editor refactor." Under this investigation's rail-keeps-editor-pane model, those work items collapse into Studio 1a-i's editor adaptation pass (~300-500 LOC total across 9 editors). **There is no Studio 1b/1c in the revised decomposition.**

What COULD defer to a post-1a Studio 1b (rebranded):
- Drag-to-canvas palette in Live mode (per previous findings, this is canon-aspirational and a separate substrate concern, ~1,500-3,000 LOC).
- Saved-view authoring (separate substrate, deferred indefinitely per previous findings).
- Spaces section as a first-class Studio tab (requires Spaces substrate evolution per previous findings Section 2, ~1,500-2,500 LOC precursor).
- Holes detection (per Section 3, ~200-300 LOC follow-on).
- Tenant_override scope authoring from Studio (separate UX arc).

Each of these is a properly-scoped follow-on arc, not part of Studio 1a.

---

## Most consequential finding for Studio 1a build prompt drafting

**The rail-collapses-when-editor-pane-active model (Section 2) is materially different from the previous findings' recommendation and collapses the editor refactor scope by ~75%.** The previous findings assumed Studio rail subsumes editor left panes (forcing editors to accept a `studioContext` prop that drops their left pane). This investigation's reading of the build prompt makes the opposite design canonical: Studio rail collapses to a 48px icon strip when an editor's own left pane is in use, and the editor's left pane remains canonical. Per-editor refactor LOC drops from ~880-1,490 to ~300-500. This makes the previous Studio 1b/1c sub-arcs unnecessary — that work folds into Studio 1a-i as a single lightweight adaptation pass. The build prompt should explicitly state this model (rail-keeps-editor-pane, not rail-replaces-editor-pane) to prevent the build-time sub-agent from reverting to the more invasive earlier reading. Combined with the verticals-lite precursor (~500-700 LOC, separate arc) and the Studio 1a-i / 1a-ii cut (~1,100-1,600 LOC each), the Studio shell ships in three properly-bounded arcs (precursor + 1a-i + 1a-ii) without the editor-refactor sprawl the previous findings projected.

Findings document path: `/tmp/studio_1a_internal_investigation_findings.md`.