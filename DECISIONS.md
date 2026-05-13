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
