# Bridgeable — Architectural Decisions Log

> Append-only. Opus-only. Each entry: date, decision, one-paragraph rationale. New chats read this when they need to understand WHY something is the way it is.

> Format: each entry has date, decision title, and rationale paragraph. Superseding entries reference the prior entry's date and state the reason. Earlier entries are never edited.
---

## 2026-05-13 — Separate canon, state, and decisions log

Canon documents (PLATFORM_ARCHITECTURE, DESIGN_LANGUAGE, BRIDGEABLE_MASTER, FUNERAL_HOME_VERTICAL, VISION, CLAUDE.md) were being edited on every commit, conflating slow-changing architectural canon with fast-changing session state. New model: canon stays canon (Opus-only, batched, deliberate). STATE.md holds current truth and is the only doc Sonnet writes. DECISIONS.md is append-only and records why architectural choices were made. New chats read STATE.md first, then canon as needed.

---

## 2026-05-13 — Bridgeable Studio as consolidated visual authoring environment

The platform's visual authoring surfaces are consolidated into a single environment called the Bridgeable Studio, located at `/studio`. Single-app metaphor (Figma-comparable). All non-code visual work — themes, component classes, focuses, widgets, documents, workflows, edge panels, registry inspection, and runtime-aware editing — happens inside the Studio. Two modalities: Edit mode (form-driven authoring against substrate) and Live mode (click-on-runtime authoring against the same substrate). Both modalities ship from Studio launch; neither is aspirational. Scope-as-mode via top-bar picker: Platform or specific vertical. Standalone editor routes redirect into Studio deep links and are deprecated for one release before deletion. The Studio is admin-only, PlatformUser-authenticated.

---

## 2026-05-13 — Verticals as first-class entity ships as a small precursor arc

A `verticals` table with metadata for the four canonical slugs (manufacturing, funeral_home, cemetery, crematory) ships as a precursor to the Studio shell. Slug strings remain the value used by existing `vertical` columns across 16+ configuration tables; no FK migration is part of this arc. The precursor exists so the Studio rail can title itself and the scope picker has rows to enumerate. Slugs are immutable at the service layer — `update_vertical` does not accept a slug parameter. A CLAUDE.md convention is added: all future migrations introducing a `vertical` column must reference `verticals.slug` as an FK from inception, so the existing String-not-FK pattern stops being perpetuated by default.

---

## 2026-05-13 — Studio shell arc decomposition

The Studio shell ships in three arcs: (1) verticals-lite precursor — `verticals` table, three endpoints, admin page; (2) Studio 1a-i — routing, redirect layer, Studio rail with icon-strip + expanded modes, editor adaptation pass, Live mode wrap with placeholder overview surface; (3) Studio 1a-ii — overview surface implementation with inventory service, counts, and recent-edits feed. Live mode ships in 1a-i, not deferred. The Studio rail collapses to a 48px icon strip when an editor's own left pane is in use; editors retain their own left panes (model: rail-collapses-not-replaces). Per-editor refactor is a lightweight adaptation pass (~30-60 LOC per editor accepting a `studioRailExpanded` context value), folded into 1a-i. This decomposition supersedes the earlier four-sub-arc proposal (1a/1b/1c/1d) that assumed editors would drop their left panes; the rail-collapses model makes that refactor unnecessary.

---

## 2026-05-13 — Focus cores are picked, not composed

Operators select Focus cores from a registry of pre-built core templates. Cores appear as fixed-but-visible placements on the Focus composition canvas: movable and resizable, but not deletable and not decomposable. The Focus composition canvas authors only arrangement (which accessory widgets/buttons appear around the core, where they're positioned). The core itself remains code, per the May 2026 core-plus-accessories canon. This decision formalizes the unified-placement model in operator-facing terms: every Focus canvas element is a placement, with the core distinguished by its fixed-but-visible status.

---

## 2026-05-13 — Widget authoring is data-source-first

No widget can be authored in the Studio without first selecting a Vault data source (Vault saved view, Vault item type filter, or ad-hoc query). This prevents the decorative-widget anti-pattern where widgets exist without reactive data backing. Two entry points to widget authoring — Vault-initiated ("make widget from this view") and canvas-initiated ("blank canvas, pick a source") — converge in the same authoring surface and produce the same widget record. The authoring surface is three-pane: data source picker (left), live preview (center), visualization shape picker plus shape-specific config (right).

---

## 2026-05-13 — Spaces substrate is the next-on-queue arc after Studio shell

Investigation (`docs/investigations/2026-05-13-studio-shell.md` §2) confirmed there is no platform-tier Spaces substrate today: spaces are per-user JSONB in `user.preferences`, the 15 endpoints are tenant-token + per-user scoped, role-seeded templates live in Python code. The absence of platform-tier Spaces substrate is a strategic gap on the vertical-launch flow, not just a Studio-scoping question; per-user-JSONB-only constrains every future vertical launch. Spaces substrate arc — `space_templates` table with 3-tier scope inheritance, platform-admin API, service-layer resolver — is locked as the immediate post-Studio-shell priority, estimated ~1,500-2,500 LOC before any Studio integration. The Studio rail in 1a-i shows a "Spaces" entry as disabled with "Coming soon" affordance.

---

## 2026-05-13 — Live mode is vertical-or-tenant-tier authoring; platform-tier changes happen in Edit mode

In Studio Live mode, the scope picker is informational and read-only — scope is determined by the impersonated tenant's `Company.vertical`. Operators cannot author platform-tier changes from inside Live mode. Platform-tier authoring (changes affecting every tenant) happens exclusively in Edit mode at Platform scope. This is a deliberate constraint, not a limitation pending future work: authoring platform-tier changes while looking at one specific tenant's runtime would design against that tenant's data without surfacing the platform-wide blast radius. The constraint will eventually need surfacing in the Studio's chrome (Live mode top bar shows "Editing vertical_default for Wastewater — via tenant Hopkins FH"). Future tenant_override scope authoring inside Live mode is a separate UX arc.
---

## 2026-05-13 (PM) — Studio 1a-i sub-arc refinement

Supersedes 2026-05-13 (Studio shell arc decomposition) on the question of how Studio 1a-i is dispatched. Investigation at `docs/investigations/2026-05-13-studio-1a-i-scoping.md` applied R-7-α floor analysis (verticals-lite shipped at 2.3x estimate) to Studio 1a-i and found the bundled scope at ~4,000-4,500 LOC midpoint exceeds the sub-agent execution ceiling. The bundle splits into three sub-arcs: 1a-i.A1 (routing + rail + redirect + placeholder overview + smoke tests, ~2,300 worst case); 1a-i.A2 (Live mode wrap + impersonation handshake + mode-toggle URL helper + Live mode tests, ~1,900 worst case); 1a-i.B (editor adaptation pass + comprehensive tests, ~1,840 worst case). Each fits the ~2,000-2,500 ceiling at worst case.

The 2026-05-13 commitment "Live mode ships in 1a-i, not deferred" is honored by sequencing A2 immediately after A1 with no other arcs interleaved. The brief window between A1 and A2 ships where Studio is operator-visible without Live mode is treated as transitional sub-arc sequencing, not deferral. A2 dispatches as the next arc after A1 lands; B dispatches after A2.
---

## 2026-05-13 (PM) — Studio test maintenance lazy-boundary canon

The Studio shell's Live mode wrap consumes `RuntimeEditorShell`, the largest non-chart chunk in the admin tree (~113 kB minified, 26 kB gzip). Eager import — even one level deep through `StudioLiveModeWrap` — makes that chunk part of the main admin bundle on every admin page load. The runtime editor is only relevant when an operator is editing a tenant's environment via Live mode (a deliberate-activation flow with its own loading affordance, not a passive nav target). Lazy boundary belongs at the wrap, not above it.

Canon: any Studio child that pulls in tenant-tree machinery (TenantProviders, TenantRouteTree, impersonation chain, inspector substrate) loads via `React.lazy()` + a `Suspense` fallback shaped like the rest of the admin tree's lazy boundaries. The Studio shell itself and the overview surface are eager; tenant-tree-consuming children are lazy. Pattern reference: `BridgeableAdminApp.tsx::studioRoute` + `RuntimeHostTestPage` lazy mount. Future Studio Live-mode siblings (e.g., a hypothetical preview-only mode, a hypothetical scope-cascade visualizer over tenant data) follow the same boundary.

---

## 2026-05-13 (PM) — E2E test maintenance pattern under Studio migration

The Studio shell migration (1a-i.A1) installed a redirect from `/visual-editor/*` and `/runtime-editor` to `/studio/*` and `/studio/live`. The redirect preserves intent for most E2E tests — pages that `goto()` a legacy route and assert on editor body content pass unchanged because the redirect lands on the same editor mount.

Two test shapes break:
1. **URL assertions against the legacy path.** `expect(url).toContain("/visual-editor/widgets")` fails post-redirect. Broaden to `expect(url).toMatch(/\/(visual-editor|studio)\/widgets/)` — both forms remain accepted during the migration window. Eventually the legacy half drops when the redirect retires.
2. **Test-ids tied to the legacy index page structure.** `ve-card-*` test-ids on the legacy `/visual-editor` index were superseded by `studio-overview-card-*` test-ids on the Studio overview. Tests migrate to the new test-ids when the intent ("editor reachable from index surface") still applies; tests are deleted when the intent is purely tied to the legacy structure.

Going forward, new E2E tests should assert on Studio-canonical paths (`/studio/...`) and Studio-canonical test-ids. The legacy redirect is a back-compat affordance, not a primary surface.

---

## 2026-05-13 (PM) — Studio mode-specific auth gate delegation

Each Studio mode handles its own auth gate. StudioShell's top-level auth check redirects to `/login` for Edit-mode routes (`/studio`, `/studio/:vertical`, `/studio/:editor`, `/studio/:vertical/:editor`, `/studio/admin/*`) but delegates auth-failure rendering to the child component when the route is Live mode (`/studio/live/*`).

Rationale: the recovery affordance is mode-specific. An operator trying to enter Live mode unauthenticated has a specific intent (edit a tenant's runtime); the recovery surface should reflect that intent rather than bouncing through a generic Studio-level unauth. More structurally: every Studio mode may have different auth requirements (Edit mode allows ops-admin and platform-admin; Live mode requires platform-admin per `RuntimeEditorShell.tsx:308-311`). Centralizing all auth gates in StudioShell would require StudioShell to know about every mode's permissions, which couples the shell to every child's auth model. Delegation keeps auth-requirements knowledge co-located with the component that enforces them.

Pattern for future Studio modes: if a future mode needs auth handling different from the Studio default, it owns its own auth gate; StudioShell delegates by detecting the mode's path prefix and skipping the top-level redirect.
---

## 2026-05-13 (PM) — Studio 1a-i closure: hybrid dispatch model canon

Studio 1a-i ships in three core sub-arcs (A1, A2, B) plus three follow-ups (test maintenance, auth gate delegation, Live mode router topology) and supporting maintenance (test sweep, bundle baseline refresh). The shell's internal dispatch is a hybrid: nested Routes for Live mode (Route declarations consume `live/:vertical/*` and `live/*` so TenantRouteTree's inner Routes match against the canonical deep tail), and parseStudioPath-based direct dispatch for Edit mode (classify-and-render by URL shape).

Rationale: Edit mode is genuinely a classify-and-render shape — overview, editors, admin sub-pages don't need tail consumption. Live mode is genuinely a route-segment-match shape because it mounts a tenant route tree that needs the URL tail. Mixing reflects the real shape difference rather than forcing uniformity. Investigation findings at `docs/investigations/2026-05-13-studio-live-router-topology.md` evaluated full migration to declarative routes (Option B) and a TenantRouteTree basename mechanism (Option C); the hybrid model (Option A) was selected for minimum blast radius and forward-compatibility.

Future Studio modes that need tail consumption (preview, scope-cascade-visualizer, diff-mode) add their own `<Route path="<mode>/.../*">` declaration alongside `live`. Modes that don't stay in the parseStudioPath dispatch. Pattern accommodates both shapes naturally.

This entry closes Studio 1a-i. Of the four originally-failing Playwright gates that motivated the closure verification, eight tests pass post-deploy (Gates 1, 1a, 15, 28, 29, 33, 37 across its three sub-tests). Gates 14 and 22 remain red, but investigation at `docs/investigations/2026-05-13-dispatch-day-pane-failures.md` identified the cause as a pre-existing R-2.x defect (~103 absolute-path Route declarations remaining in `renderTenantSlugRoutes` after R-2.x's partial conversion). The defect is downstream of Studio — Studio 1a-i made it reachable by routing the editor shell correctly; the actual bug lives in the tenant route tree. R-2.x.1 (next arc) finishes R-2.x's universal-relative-paths conversion and adds an invariant test guarding against regression.

Next-on-queue arcs per DECISIONS.md sequencing: R-2.x.1 (interstitial bug fix), then Spaces substrate or Studio 1a-ii pending sequencing discussion.
---

## 2026-05-13 (PM) — Studio 1a-i closure (with tracked known issue: Gates 14/22)

Studio 1a-i is declared closed pending resolution of Gates 14 and 22 (deep-tenant-route mount under Live mode). The Studio shell substrate is genuinely working: A1 + A2 + B sub-arcs plus six follow-ups (test maintenance, auth gate delegation, router topology, R-2.x.1 universal-relative-paths, verticals-disambiguation, and supporting maintenance) ship the canonical hybrid dispatch model documented in the prior closure entry. Of the 56 Playwright gates against this surface, 53 pass post-deploy of commit `0623ed3`. The redirect chain works, the picker pickup-and-replay preserves tails, auth gate delegation lets Live mode handle its own recovery, the editor adaptation pass honors the rail-collapses-not-replaces canon, and the bundle baseline is documented.

Gates 14 and 22 remain red. The symptom is captured in STATE.md's active deferred items: under impersonation at `/bridgeable-admin/studio/live/dispatch/funeral-schedule`, the Studio top bar renders "Vertical: dispatch" and the Pulse overview displays instead of `FuneralSchedulePage`. Six successive fixes have shipped against this symptom, each with a plausible static-analysis diagnosis that the deploy revealed to be incomplete. The accumulated evidence is that static analysis from chat is not the right tool for this class of bug — the diagnostic loop is too slow and the false-positive rate too high. Resolution requires hands-on DevTools debugging on staging, walking the React component tree to find the actual rendering path, then fixing in one shot with evidence.

Lesson codified for future arcs: when a fix lands cleanly (unit tests pass, code review confirms intent) and the integration-test symptom does not change, do not draft another fix from static analysis. Stop, get manual evidence from the deployed surface, then act. Three iterations of "almost certainly this" is a sign that the diagnosis lacks evidence, not that the codebase has more layers than expected.

Studio 1a-i closing with this issue tracked is the right discipline. The Studio shell platform thesis is implemented and usable; Gates 14/22 are downstream functionality that a single hands-on session should resolve. Filing the bug as tracked rather than continuing to chase fixes preserves the integrity of "closed" as a meaningful signal.

Next-on-queue arcs per DECISIONS.md sequencing: Spaces substrate (immediate post-Studio-shell priority), Studio 1a-ii (overview inventory), or a small hands-on Gates 14/22 resolution session. Decision deferred to next working session with fresh eyes.

---

## 2026-05-18 — Discovered canon: Cores are canonical-shared-across-verticals

Surfaced during F-1 build verification (Focus Builder sub-arc 1). `focus_cores` has no `vertical` field — cores are canonical shapes (Kanban, Triage Queue, Coordination Focus, etc.) that any vertical can use. A core's vertical attribution in operator-facing surfaces (e.g., the Focus Builder tree at `/studio/builder/focuses`) is derived from its inheriting templates: `vertical_default` templates pin the core to their vertical; `platform_default` templates make the core cross-vertical (visible under every published vertical's tree); cores with zero templates land in the "Unclassified" pseudo-vertical at the bottom of the tree.

The same core can correctly appear under multiple verticals in the tree. Example: `scheduling-kanban-core` inherited by both a manufacturing-vertical template (Funeral Scheduling) and a funeral-home-vertical template (none exist yet) would appear under both verticals' subtrees. The core is the same; the templates that variant it for each vertical's context differ. This is correct modeling, not duplication — cores express canonical shapes; verticals express operator contexts; templates bind shape to context.

Implication for future arcs: Page Builder, Document Builder, Workflow Builder all consume the `VerticalGroupedTree` primitive and will exhibit the same pattern — their canonical shapes (pages, documents, workflows) shared across verticals; vertical attribution from instances. Future builder UIs must derive vertical placement from inheriting templates, not from a (non-existent) field on the core itself. Future schema additions to `focus_cores` must not add a vertical column; doing so would mis-model the design and break the canonical-shape-shared semantics.

---

## 2026-05-18 — Discovered canon: Template vertical is design-time-permanent

Surfaced during F-1.1 build verification (Focus Builder sub-arc 1.1). `focus_templates.vertical` is treated as immutable by `update_template`. Templates cannot migrate between verticals via the update path. Cross-vertical template migration requires a two-step pattern: (1) pre-lookup at the OLD vertical; if found active, deactivate the record; (2) lookup at the NEW vertical; `create_template` builds a fresh row with the new vertical stamp. The pattern is idempotent on subsequent runs (already-deactivated old plus already-exists-active new are both no-ops).

Architectural rationale: template vertical is part of identity for tree placement (per the F-1 discovered-canon entry above — templates carry the vertical attribution that surfaces cores under verticals), for scope semantics (`vertical_default` applies to the vertical the template was authored for), for inheritance version pins (templates pin to a specific core version; cross-vertical migration would invalidate the pin's vertical-scoped audit context), and for audit trails (who-authored-this-template-in-which-vertical history). Mutability would invalidate cached resolutions, break inheritance pins, and corrupt audit history.

Implication for future arcs: seed migrations that change a template's vertical (rare; surfaced once in F-1.1 when `scheduling-fh` was reclassified from `funeral_home` to `manufacturing`) follow the two-step pattern. Operator-initiated cross-vertical template migration (not currently exposed in any UI; would be a future feature) follows the same shape — deactivate at old vertical, create new at target vertical, not edit-vertical-on-existing-record. Future UI surfaces (Focus Builder, Page Builder, etc.) must not expose "change vertical" as an inline edit on a template; the operation is structurally a "create new in target + deactivate old" workflow. Reference implementation: F-1.1's seed migration code at `backend/scripts/seed_focus_template_inheritance.py` (search for the `scheduling-fh` vertical reclassification helper).

---

## 2026-05-19 — Discovered canon: Multi-hook-mount pattern for builder UIs surfacing heterogeneous subjects

Surfaced during F-2 build (Focus Builder sub-arc 2). When a builder page renders one of N heterogeneous subject types (e.g., Focus Builder's `?subject=core:<id>` vs `?subject=template:<id>`), all N draft hooks must mount unconditionally — each receiving its real subject id when active, `null` when inactive. The component reads downstream operations from whichever hook is bound to the active subject (`activeHook`). Conditional mount based on subject kind would violate React's rules-of-hooks (hooks must run in the same order on every render); the unconditional-mount-with-nullable-id pattern is the canonically-correct React shape.

Architectural implications: draft hooks designed for builder consumption MUST accept `null | id` as their subject parameter and short-circuit cleanly when `null`. No-op behavior includes: no fetch, no subscriptions, no debounced save timers, returning sensible empty defaults for `draft` / `isDirty` / `lastSavedAt` / etc. Hook authors should test the null case explicitly — a hook that throws or burns CPU when given `null` breaks the multi-hook-mount convention. The pattern looks wasteful at first glance (mounting hooks that no-op) but is the canonically-correct React shape; any future agent attempting to "fix" the unconditional mount by introducing conditional branching would violate rules-of-hooks. The pattern is intentional.

Reference implementation: F-2's `FocusBuilderPage` at `frontend/src/bridgeable-admin/components/focus-builder/FocusBuilderPage.tsx` mounts both `useFocusCoreDraft` and `useFocusTemplateDraft` unconditionally, passing the parsed subject id to whichever matches and `null` to the other. The component then resolves `activeHook` from subject kind for downstream wiring.

Implication for future arcs: F-3 (widget palette + accessory editing) may add a third draft hook for widget editing OR extend `useFocusTemplateDraft` with widget-update helpers — either path respects the convention. F-4 and F-5 are unlikely to add new draft hooks; the convention as-established holds. Page Builder, Document Builder, Workflow Builder will each surface their own subject-type taxonomy from their navigation trees; each adheres to the convention. Future draft hook authoring (for any builder UI) must handle `null` subject gracefully — graceful-null is a load-bearing contract requirement, not an optional convenience.

---

## 2026-05-19 — Discovered canon: Core placement position is structurally immutable in Focus Builder canvas

Surfaced during F-3 build (Focus Builder sub-arc 3, widget palette + drag-to-canvas). In the current Focus Builder canvas (shipped in F-2 + F-3), the inherited core placement renders ABOVE the widget rows in a flex-col layout, NOT interleaved into the rows-grid. Widgets occupy rows BELOW the core. This is structural, not policy — the canvas's layout makes core-widget overlap impossible by construction.

As a consequence: the F-3 investigation's Q-25 / Q-26 / Q-27 conflict-resolution model (snap-to-grid drop + slide-to-nearest-non-overlapping-cell on conflict with core's row) is NOT exercised in F-3's drop pipeline — there's nothing for conflict-resolution helpers to detect because conflicts can't happen at the layout level. Operators can currently place widgets only below the inherited core; the canonical mockup HTML's day-strip-above-kanban-cards layout is NOT achievable in the current Focus Builder canvas. Most Focus layouts have a primary decision-triage core with supplementary widgets below or around it, so this constraint is acceptable for the F-series, but it is a real shape-constraint worth knowing about.

Implication for future arcs: future arcs MUST NOT add overlap-detection helpers or slide-to-adjacent logic preemptively — the structural immutability is the canonical pattern, and adding overlap logic without exercising the underlying drop model is premature substrate. F-4 (theme picker) and F-5 (breadcrumb + polish) have no impact here; both are right-rail and top-bar work, not canvas layout. Future widget palette extensions continue dropping into rows below the core; expanded categories or richer drag-drop don't change this. If/when widgets-above-core becomes a real operator demand (e.g., to match the canonical mockup's day-strip placement exactly, or for other layouts requiring widgets above the primary core), the canvas layout needs to change first — likely shifting from flex-col to a unified grid where core and widgets occupy interleaved rows. The slide-to-adjacent conflict-resolution from Q-27 then becomes meaningful and ships as part of that refactor. Filed as a known shape-constraint, not a bug. Reference implementation showing the structural immutability: F-3's `FocusBuilderCanvas` component at `frontend/src/bridgeable-admin/components/focus-builder/FocusBuilderCanvas.tsx`.

---

## 2026-05-19 — Discovered canon: Component registry requires ≥3 configurableProps per registration

Surfaced during F-3 build. The component registry's test suite (`component-config.test.ts`) enforces a minimum of 3 `configurableProps` per registered widget. Initial F-3 widget seeds (Day Strip / Today Pin / Map Placeholder) used 1 placeholder prop each, sufficient to demonstrate the inspector pattern. The full test suite failed; the seeds were widened to 3 realistic props each (Day Strip: `daysVisible` / `highlightToday` / `weekStartsOn`; Today Pin: `showCount` / `compact` / `label`; Map: `zoom` / `showLegend` / `aspect`).

The constraint is not currently surfaced in canon documentation. Future widget authors (or future agents extending the registry) may hit this as a test-suite surprise without knowing why. The constraint's rationale is plausibly to encourage real configurability rather than placeholder widgets — but the rule lives in test code rather than documented requirement, and it is strict (≥3, not "at least 1 prop"). Whether the constraint should be relaxed to ≥1 prop is a future question; for now, document the rule.

Implication for future arcs and contributors: new widget registrations MUST include at least 3 meaningful `configurableProps` from initial seed to pass the test suite. Authors should aim for 3 props that represent real configuration axes operators would tune (e.g., a Map widget's `zoom` + `showLegend` + `aspect` are all plausible operator-tunable knobs), NOT placeholder fill. If a widget genuinely has fewer than 3 meaningful props (a single-axis widget), the test suite must be updated alongside the registration; the current rule is documented here as canonical until that test is revised. Reference: `component-config.test.ts` is the source-of-truth for this constraint; future canon refinements should reference this canonical-rule entry plus the test file.

---

## 2026-05-19 (PM) — Discovered canon: Off-by-one column index between frontend and backend placement coordinates

Surfaced during F-3.1a build (frontend↔backend placement shape adapter). The placement coordinate system differs between frontend and backend by 1. Frontend `WidgetPlacement.column_start` is 1-indexed (column 1 is the leftmost column on a 12-column grid), aligning with operator-facing UI conventions where grid columns are labeled 1-12 visually. Backend `_validate_placement`'s `starting_column` is 0-indexed (column 0 is the leftmost), aligning with array-indexing conventions in storage and validation logic. The F-3.1a placement adapter handles the conversion: `frontendToBackendPlacement` subtracts 1 and clamps at 0 (defensively guarding against a frontend value of 0 producing backend −1, which would trip `starting_column < 0` validation); `backendToFrontendPlacement` adds 1.

This is intentional, not a bug. Both representations are correct within their domains; the adapter is the canonical resolution. The clamp is deliberate — frontend values theoretically shouldn't fall below 1, but defensive coercion at the boundary prevents silent validation failures on edge-case data.

Implication for future arcs: future code touching placement coordinates must be explicit about which side it is working with. Frontend canvas layout code uses 1-indexed; backend services, migrations, and seed code use 0-indexed. Any new code path that bypasses the adapter (a future direct backend-shape consumer in frontend, a debugging tool reading raw placement data, a future drag-drop position calculation) must apply the off-by-one conversion explicitly. Reference implementation: `frontend/src/bridgeable-admin/hooks/_placement-adapter.ts` line 102.

---

## 2026-05-19 (PM) — Discovered canon: `chrome` field on placements stores the full per-placement override surface

Surfaced during F-3.1a build. The frontend's `WidgetPlacement.chrome` field stores the complete set of per-placement overrides — both visual chrome (elevation, corner_radius, backdrop_blur, background_token, border_token, padding_token, preset) AND widget-specific configurable props (e.g., `daysVisible` on a Day Strip widget, `zoom` on a Map widget, `showLegend` on a Map widget). The backend's corresponding field is named `prop_overrides`, which reflects the broader semantics more accurately.

The frontend's naming reflects operator authoring mental model — visual properties and widget configuration are collapsed into one editable blob exposed through the inspector. The backend's naming reflects implementation reality — anything that overrides a registered component's defaults goes here. The F-3.1a placement adapter maps `chrome ↔ prop_overrides` 1:1 with no field-level translation; both views see the same data under different names.

Implication for future arcs: future agents extending placement should understand the field's actual scope. A widget's "chrome" in this codebase is not limited to visual treatment; it includes the full per-placement override surface. This affects F-3.1b's Chrome section composition (the inspector's "Chrome" section title reflects operator UX, but the underlying field also receives widget config props from the CONFIGURATION section's controls — both flow through `updateWidget(widgetId, partial)`), future widget authors (configurable props persist to the same field as chrome properties; single code path), and future inspector composition (operators don't need separate persistence paths for visual chrome vs widget config; the single chrome blob handles both). Reference: `frontend/src/bridgeable-admin/hooks/_placement-adapter.ts` lines 113-115; backend placement schema at `backend/app/services/focus_template_inheritance/focus_templates_service.py` `_validate_placement`.

---

## 2026-05-19 (PM) — Discovered canon: Ordinary template updates version-bump by default; session-aware mutate-in-place is the exception

Surfaced during F-3.1a.2 read-only investigation (versioning model audit prior to URL recovery fix). The `update_template` service function in `focus_templates_service.py` has two distinct paths. The default path (lines 638-663) deactivates the prior template row (`is_active = False`) and creates a new row with `version = prior.version + 1`, `is_active = True`, and a newly-generated id. The new row preserves `scope`, `vertical`, `template_slug`, `inherits_from_core_id`, `inherits_from_core_version` from the prior row. Every save through this path produces a new template_id; lineage is tracked via the deactivated prior row (preserved with `is_active = False`).

The exception path is session-aware mutate-in-place (lines 618-636). If the incoming save provides an `edit_session_id` AND the row's stored `last_edit_session_id` either matches the supplied token or is null AND `last_edit_session_at` is within `EDIT_SESSION_WINDOW_SECONDS`, the row is mutated in place: same id, same version, fields updated. This path preserves URL stability and operator-flow continuity for sustained authoring sessions.

Implication for future arcs: future builder UIs must design URL contracts and operator-flow assumptions around the version-bump-by-default model. Any consumer that pins to a specific template_id may find that id deactivated after the next save. Hook layers handle this via the 410-retry pattern (F-3.1a.2); URL state must update on retry to remain consistent. The session-aware fast path is sensitive to data state — if a row's stored `last_edit_session_id` was stamped by a prior operator session whose 5-minute window hasn't expired, the current operator's first save will defeat the check and version-bump, producing the operator-visible "URL stale after first save" symptom. The F-3.1a.2 URL recovery mechanism handles this regardless of whether the fast path fires. Reference: `backend/app/services/focus_template_inheritance/focus_templates_service.py` lines 618-636 (fast path) and 638-663 (default path).

---

## 2026-05-19 (PM) — Discovered canon: URL stability for versioned entities requires slug-based addressing as long-term canonical pattern

Surfaced during F-3.1a.2 investigation. Any entity in the `focus_template_inheritance` substrate (templates today, future versioned entities) is addressable by template_id, but template_ids are inherently unstable across version-bumps per the prior canon entry. URL contracts that pin entities by template_id therefore become stale on every default-path save. F-3.1a.2 ships URL recovery on 410-retry as a symptom-level fix (the hook fires `onActiveTemplateIdChange` on retry-success; FocusBuilderPage updates the URL via `setSearchParams` with `replace: true`), but the structural answer is slug-based addressing.

The stable identity of a template is the tuple `(template_slug, scope, vertical)`. A slug-based URL contract (e.g., `?subject=template-slug:scheduling-fh`) resolves to the active template_id on every page load via `focusTemplatesService.list({slug, scope, vertical, include_inactive: false})`. The URL remains stable across version-bumps forever; bookmark and share-link semantics are preserved without retrofit.

Implication for future arcs: Page Builder, Document Builder, and Workflow Builder are likely to surface their own versioned entities. Their URL contracts should be designed slug-based from the start to avoid the F-3.1a.2 retrofit pattern. For Focus Builder specifically, the id-based URL contract continues working via F-3.1a.2's URL recovery, but a future arc may migrate to slug-based addressing for cleaner long-term semantics. The migration cost from id-based to slug-based URLs in an existing builder UI is moderate — touches URL contract, tree click handler, hook initialization, integration tests. The decision to migrate is deferred; F-3.1a.2's URL recovery is the current canonical handling.

---

## 2026-05-19 (PM) — Discovered canon: GET-on-inactive 200 + version-bump-on-every-save = silent staleness without URL discipline

Surfaced during F-3.1a.2 investigation as an interaction-canon entry referencing the two prior 2026-05-19 (PM) entries above. The backend's GET endpoint for templates returns 200 with the inactive snapshot when given an inactive template_id (per `admin_get_template` calling `get_template_by_id`, which does not filter on `is_active`). The PUT endpoint returns 410 Gone on inactive ids. This asymmetric policy is intentional — GET access on inactive records supports audit, history viewing, and lineage inspection use cases.

In isolation, neither policy is problematic. GET-on-inactive returning 200 is correct for audit semantics. PUT-on-inactive returning 410 is correct for write protection. The interaction with the version-bump-by-default model creates a subtle staleness mode: an operator's URL pins to template_id X; backend version-bumps deactivate X; refresh reads X via GET (returns 200 with snapshot predating the version-bump); operator sees stale state without any error indication. No single behavior is wrong; the interaction is the failure mode.

Implication for future arcs: builder UIs consuming versioned entities must apply URL discipline (per F-3.1a.2's pattern, or via slug-based addressing per the prior entry) to prevent the interaction failure mode. The two backend policies are correct in isolation and should not be changed; the frontend's responsibility is to maintain URL state in sync with the active record's id. Future endpoints that introduce similar versioning semantics should make their GET-on-inactive policy explicit (return 200 with snapshot vs return 410 like PUT) and document the trade-offs. The current canonical pattern is asymmetric (GET 200, PUT 410) with frontend URL discipline as the integration layer.

---

## 2026-05-19 (PM) — Discovered canon: Callback-ref pattern extends multi-hook-mount canon to consumer callbacks

Surfaced during F-3.1a.2 build. The multi-hook-mount canon (earlier 2026-05-19 entry above) established that all N draft hooks in a builder component mount unconditionally with null subject ids, with each hook's contract handling null gracefully. The pattern's underlying discipline — refs as the dominant defense against stale-closure bugs (the C-2.2b lesson) — extends to consumer-supplied callbacks.

F-3.1a.2's `onActiveTemplateIdChange` callback on `useFocusTemplateDraft` is stored in a ref (`onActiveTemplateIdChangeRef`) rather than held as a closure dep on the hook's `save` function. The save function reads from `onActiveTemplateIdChangeRef.current` when firing the callback. This pattern keeps save's deps minimal (avoiding stale-closure bugs when consumers re-render with different callbacks) and applies the same ref-as-dominant-defense discipline that internal state already uses. The C-2.1.4 + C-2.2b lesson — refs dominate, deps-array exclusion is the supporting constraint — generalizes from internal draft state to externally-supplied callbacks because both face the same closure-capture failure mode.

Implication for future arcs: future builder hooks that surface state changes to consumers via callbacks should hold those callbacks in refs, not in dependency arrays. The pattern applies to any callback the hook may invoke from a function that reads other ref-tracked state (save bodies, debounced operations, retry paths). Reference implementation: `frontend/src/bridgeable-admin/hooks/useFocusTemplateDraft.ts`'s `onActiveTemplateIdChangeRef` pattern in the 410-retry success path. Page Builder, Document Builder, and Workflow Builder hooks that surface analogous state-change callbacks to their pages should adopt the same shape from initial design.

---

## 2026-05-19 (late PM) — Discovered process canon: `git log -1 HEAD` as first diagnostic step when staging behavior contradicts expectation

Surfaced during today's F-3.1a.1 cycle. When staging behavior contradicts expected behavior, the first diagnostic step is verifying that the expected behavior is actually deployed: `git log -1 HEAD` against the prior arc's claimed commit. Build reports describe what an agent produced. Git history describes what is actually deployed. These can diverge silently when the user-and-agent commit cadence breaks — for example, when a build agent reports completion but the user dispatches the next arc before committing the prior arc's work.

Today's specific instance: F-3.1a's agent completed on a prior day and reported "ready for commit message + push." The next dispatch (F-3.1a.1) began without verifying that F-3.1a's files had actually been committed. They had not. F-3.1a.1's agent investigated, found the F-3.1a wiring "already in place" in the local working tree, and surface-and-stopped on the false premise that the diagnosis was wrong. The diagnostic loop that followed produced multiple wrong root-cause hypotheses before a read-only investigation revealed that staging was running pre-F-3.1a code (commit `8ced75a`) while the working tree contained uncommitted F-3.1a changes. A 30-second `git log -1 HEAD` at the start of F-3.1a.1's dispatch would have shown the most recent commit on main was the prior F-3 commit, not F-3.1a — surfacing the gap immediately. The compounding cost of skipping this check was several hours of wrong-diagnosis cycles.

Implication for future arcs: when staging behavior is the input to a diagnosis, runtime evidence requires deployed code as its baseline. Verify deployment state before drafting any fix prompt. The check applies to every dispatch where staging is being debugged, every build report that claims "ready for commit message + push" without an explicit confirmation that the commit actually landed, and every "diagnosed and fixed" claim from a prior arc when subsequent staging behavior suggests the fix did not take effect. The cost of the check is negligible (5-30 seconds). The cost of skipping it can be a full day of compounding wrong diagnoses.

---

## 2026-05-19 (late PM) — Discovered process canon: Read-only investigation before fix-prompt drafting when staging contradicts expectation

Surfaced as a recurring lesson across today's F-3.1 cycle. When staging behavior surfaces a problem that contradicts expected behavior — especially when initial diagnostic guesses keep producing wrong root causes — the right next step is a read-only investigation arc, not another fix prompt. The investigation arc reads code at HEAD, captures runtime evidence (network responses, console output, URL state, DB row state), and produces a verified root-cause hypothesis with code citations. The fix arc dispatches against the verified hypothesis. The investigation is usually faster than the wrong-fix-then-revert cycle it replaces.

Today's instance: three successive fix-prompt drafts produced wrong root-cause diagnoses. F-3.1's first dispatch blamed save body construction (empirically false — F-3 had wired it correctly). F-3.1a.1's first dispatch blamed auto-save trigger wiring (empirically false — F-3 had wired triggers correctly). Subsequent speculation blamed various candidates without runtime evidence. Each wrong-diagnosis cycle was caught by the next agent surface-and-stopping per the canonical scope-discipline pattern, but only after time and dispatch overhead. The cycle finally broke when read-only investigation arcs produced verified ground — F-3.1a actually-not-committed, then backend versioning model details with line citations and DevTools network capture, then the URL-staleness root cause with explicit reproduction path.

The investigation arc has a specific shape that distinguishes it from a fix arc: zero code changes, zero commits, all assertions grounded in quoted code at HEAD plus captured runtime evidence, and a single testable root-cause hypothesis as the load-bearing output. Static-analysis-only diagnoses that read source without runtime evidence are an empirical failure mode; today produced multiple confidently-wrong-but-coherent static-analysis diagnoses before the read-only discipline broke the pattern.

Implication for future arcs: when a fix arc's diagnosis turns out wrong (agent stops on a false premise; staging behavior does not match expectations after deploy), the next dispatch is a read-only investigation arc — not another fix prompt with a revised diagnostic guess. The shape applies across the F-series and into Page Builder, Document Builder, Workflow Builder, and beyond. Build reports are not authoritative when runtime behavior contradicts them; git state is. Code claims are not authoritative when runtime behavior contradicts them; captured runtime evidence is. The read-only investigation is the canonical discipline for resolving the contradiction.

---

## 2026-05-19 (late PM) — Discovered process canon: Mock-only tests verify one side of frontend↔backend contracts; cross-side contracts require integration tests with real validators or real routes

Surfaced during F-3.1 + F-3.1a investigations and confirmed by F-3.1a.2's integration test pattern. When a contract spans a frontend↔backend boundary, mock-only tests on either side verify only that side's behavior. They do not verify the contract itself. F-3's hook unit tests mocked `focusTemplatesService.update` and asserted on frontend payload shape — the mock returned success regardless of payload validity, so the tests were uniformly green while staging PUT bodies were silently 422'd by backend's `_validate_placement` due to shape mismatch. The hook tests passed; the operator-flow was broken.

F-3.1a's adapter unit tests verified the adapter's field-mapping logic. Its contract test imported real backend validation logic (`_validate_rows` + `_validate_placement`) and ran the adapter's output against it — better than mock-only on either side alone, but still not exercising the production save path that connects real hook → real adapter → real payload → real validator end-to-end. Subsequent runtime evidence showed F-3.1a's adapter was never wired into the save path at the time the contract tests ran (the work was uncommitted), demonstrating that even contract-style tests with real validation logic on one side don't catch gaps in the production wiring on the other side.

The canonical pattern for cross-side contracts is an integration test that exercises both sides via the real production code paths. For frontend hook → backend route contracts, this means a test that calls the real hook method, lets the real adapter run, sends the resulting payload through the real route (or directly through the route's validation function in a frontend test environment), and asserts on the resulting state. F-3.1a.2's integration test moved closer to this shape — exercising the full operator flow including the URL recovery callback — and demonstrably caught the regression class via the verify-against-pre-fix discipline (revert the fix; confirm the test fails; restore; confirm the test passes).

Implication for future arcs: future hook extensions and new component surfaces require integration tests that exercise the production operator-flow end-to-end, not unit tests on individual layers. This applies to any cross-side contract (frontend hook → backend route, frontend service → backend API), any operator-action → debounced-save → backend-persist → reload pipeline, and any new hook method that updates state and triggers save. The F-3 lesson is the canonical cautionary tale: adding `addWidget` + `updateWidget` + `removeWidget` + `moveWidget` without an integration test produced the entire F-3.1 cycle. The integration test's load-bearing characteristic is the verify-against-pre-fix discipline (C-2.1.4 + C-2.2a.1 + C-2.2b lineage): the test must demonstrably fail when the fix is reverted. A test that passes both before and after the fix doesn't catch the regression class. F-3.1a.2's pattern at `frontend/src/bridgeable-admin/components/focus-builder/FocusBuilderPage.test.tsx` is the current canonical shape; future arcs reference it as the integration-test template.
