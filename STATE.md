# Bridgeable — Current State

Single source of truth for what is true RIGHT NOW. Updated by Sonnet at the end of every build session. Canon lives elsewhere — see read order in CLAUDE.md.

## Production

- Live tenant: Sunnycrest Precast at `sunnycrest.getbridgeable.com` (first tenant: James Atkinson)
- Go-live date: April 7, 2026
- Migration head: `r95_verticals_table`

## Build status

| Metric | Count |
|--------|-------|
| Database tables | ~258 |
| ORM model files | 165+ |
| ORM model exports (`__init__.py`) | 178+ |
| API route files | 105+ |
| API endpoints | 955+ |
| Route modules registered in v1.py | 95+ |
| Frontend routes | 150+ |
| Backend service files | 117+ |
| Migration files | 133 |
| Documents test suite (D-1 → D-9) | 224 passing |
| Agent jobs (scheduled) | 14 |
| Accounting agents (registered) | 12/12 (complete) |
| Accounting agent tests | 105 passing |
| Urn Sales E2E tests | 39/39 passing |
| Safety Program Generation E2E tests | 12/12 passing |
| Agent jobs (not yet built) | ~30 |
| TypeScript errors | 0 |
| Backend import errors | 0 |
| Migration chain | Single head, no broken links |

## Active arc

- Arc name: Studio shell precursors → Bridgeable Studio shell arc (consolidating 7 visual editors + runtime-aware editor under `/studio`)
- Current phase: Studio 1a-i.B next — editor adaptation pass (9 editors accept `studioRailExpanded` signal so their left panes hide while Studio rail is expanded; rail-collapses-not-replaces canon). Studio 1a-ii (overview inventory) follows B.
- Last shipped: Studio test maintenance (`<commit-pending>`, 2026-05-13) — between-arcs cleanup after Studio 1a-i.A2. Restored lazy boundary on `RuntimeEditorShell` inside `StudioLiveModeWrap` (chunk size 112.87 kB now properly excluded from main bundle); reconciled two E2E tests against the `/visual-editor → /studio` redirect surface (`28-edge-panel-editor-page` second test migrated `ve-card-edge-panels` → `studio-overview-card-edge-panels`; `runtime-host-r0.spec.ts` URL assertion accepts either form). Bundle-baseline gap (7.5% over R-2.1 baseline) confirmed pre-existing, accumulated across Arcs 4a-4d before Studio shell shipped — A2 itself contributed 0 bytes to main bundle, lazy fix only recovers the chunk-split that should have been there from the start.

## Active deferred items

- **Data Migration Tool** — waiting on Sage CSV exports from Sunnycrest accountant (invoice history, customer list, cash receipts)
- **Studio 1a-i.B** — editor adaptation pass: 9 editors accept `studioRailExpanded` signal so their left panes hide while Studio rail is expanded (rail-collapses-not-replaces canon). **Studio 1a-ii** — overview surface implementation with inventory service (counts + recent edits, replaces the A1 static placeholder). **Spaces substrate arc** — locked as immediate post-Studio-shell priority per DECISIONS.md 2026-05-13.
- **Arc 4a.2b** — vault cluster Path 1 wrap (9 widgets) + dashboard_layouts seed script; sibling of Arc 4a.2a (committed `8affc8f`); estimated ~1,300-1,800 LOC
- **revenue_summary + ar_summary** — declared in backend WIDGET_DEFINITIONS but no frontend React component; documented in widget-renderer-parity.test.ts `KNOWN_DEFERRED_VAULT`; hygiene arc TBD
- **13 simpler agent jobs** — `STALE_DRAFT_MONITOR`, `REVERSAL_RUNNER`, `PO_DELIVERY_MONITOR`, `RECONCILIATION_MONITOR`, `ABANDONED_RECONCILIATION_MONITOR`, `STATEMENT_RUN_MONITOR`, `FINANCE_CHARGE_REMINDER`, `EXEMPTION_EXPIRY_MONITOR`, `1099_MONITOR`, `DELIVERY_WEEKLY_REVIEW`, `FINANCE_CHARGE_INSIGHT_JOB`, `DISCOUNT_UPTAKE_JOB`, `OUTCOME_CLOSURE_JOB`
- **NPCA Audit Prep feature** — placeholder UI at `/npca`; full feature not yet built (compliance score engine, gap analysis, audit package ZIP)
- **Performance optimization** for report generation
- **FastAPI `@app.on_event` → lifespan migration** — deprecated pattern; mechanical migration deferred to FastAPI version-bump arc
- **R-9 workflow node registry promotion** — ~900 LOC + BLOCKING parity test
- **R-classify customer classification refactor** — ~600 LOC + BLOCKING parity test
- **R-8.x cleanup arcs** — 5 bounded items (EmailChannel exception classes, Triage vertical_default scope, TriageQueueConfig discriminated union, AGENT_REGISTRY side-effect-import, ApprovalFlow enum)
- **R-8.y+1** — per-tenant configuration browser extending R-8.y.d
- **Bounded sub-arcs (trigger-driven)**: Arc-3.x-page-context-substrate, Arc-3.x-hybrid-filter, Arc-3.x-mount-gate, Arc-4a.x-IconPicker-rollout, Arc-4b.x-nesting-ui, Arc-4b.x-mention-hover-preview, Arc-4.x-approval-gate

## Recently shipped (rolling, last 10)

1. **Studio test maintenance** (this commit, 2026-05-13) — between-arcs cleanup after Studio 1a-i.A2 (A2 Playwright run surfaced two gate failures). **Part 1**: `StudioLiveModeWrap` converted to `React.lazy()` + `Suspense` around `RuntimeEditorShell` import (mirrors the lazy pattern used in `BridgeableAdminApp` for `StudioShell` + `RuntimeHostTestPage`). Pre-fix, eager import made `RuntimeEditorShell` (and its `TenantProviders`/`TenantRouteTree`/inspector substrate transitively) part of the main admin bundle on every admin page load; post-fix, `RuntimeEditorShell-*.js` chunk splits cleanly at 112.87 kB (gzip 25.82 kB) and only loads when an operator enters Studio Live mode. **Part 2**: two E2E tests touched. `tests/e2e/runtime-editor/28-edge-panel-editor-page.spec.ts` second test rewritten — Phase 1 nav-card `ve-card-edge-panels` on the legacy `/visual-editor` index page no longer renders because that route redirects to `/studio` overview; the equivalent intent ("edge panels editor reachable from index surface") now asserts on `studio-overview-card-edge-panels` (the Studio overview's section card test-id). `tests/e2e/runtime-host-r0.spec.ts` URL assertion broadened from `expect(url).toContain("/visual-editor/widgets")` to `expect(url).toMatch(/\/(visual-editor|studio)\/widgets/)` because `/visual-editor/widgets` redirects to `/studio/widgets`. **Part 3**: bundle baseline verification surfaces a separate finding — the R-2.1 baseline (5,567,053 bytes, May 8) is now 7.54% under the post-A2 main bundle, but a stash-restore comparison against pre-Studio commit `9fbcab5` shows main_bundle was already 5,944,397 bytes (+6.77%) before Studio shell shipped. The 7.5% gap is accumulated growth across Arcs 4a-4d, NOT introduced by Studio 1a-i.A1 or A2. Gate 11 bundle-baseline refresh is a separate decision (out of scope for this maintenance arc) — `fixtures/bundle-baseline.json` intentionally not touched. **No production code changed outside the lazy boundary on `StudioLiveModeWrap.tsx`.** Tests: `StudioLiveModeWrap.test.tsx` (5 tests) + 2 tests in `StudioShell.test.tsx` (Live mode mounts + vertical forwards) updated to `findByTestId` for Suspense resolution; vitest 2367/2367 green, tsc clean, build 5.29s. **~90 LOC** touched across 5 files.
2. **Studio 1a-i.A2** (`a29be51`, 2026-05-13) — Live mode wrap for Bridgeable Studio. `StudioLiveModeWrap` mounts the existing `RuntimeEditorShell` inside Studio with new optional props `studioContext` (suppresses the yellow admin ribbon since Studio's own top bar replaces it) + `verticalFilter` (pre-scopes the tenant picker via `Company.vertical` client-side filter). `TenantPicker` gained `verticalFilter` prop; `TenantUserPicker` gained `studioContext` + `verticalFilter` props and now navigates to the Studio-shaped `/studio/live/:vertical?tenant=...&user=...` URL on impersonation success when in Studio context. New `toggleMode(pathname, search)` helper in `studio-routes.ts` implements the 5 canonical Edit ↔ Live translation rules (tenant params drop on Live → Edit, no trailing slash on `/studio/live` → `/studio`, tolerates `/bridgeable-admin` prefix). `StudioModeToggle` wired to use `toggleMode()` + `useLocation()`. `StudioScopeSwitcher` gained `readOnly` + `liveModeDescription` props rendering a static "Vertical: X" readout instead of the dropdown in Live mode; `StudioTopBar` passes these in. `/runtime-editor` + `/bridgeable-admin/runtime-editor` (and `/*` variants) installed as `<StudioRedirect />` routes — the A1 spec-override that kept those active is now resolved; standalone runtime editor entries forward to `/studio/live` preserving `?tenant=&user=`. `StudioLivePlaceholderPage` deleted; `StudioShell` dispatches `/studio/live[/:vertical]` to `StudioLiveModeWrap`. Tests: 5 new `StudioLiveModeWrap` smoke tests, 5 new Live-mode tests in `StudioShell.test.tsx` (mock RuntimeEditorShell stub), 8 new `toggleMode` translation tests; existing 2367 vitest tests pass. tsc clean, build clean 5.22s. Backend untouched. **~446 LOC** (well under the 1,900 LOC worst-case budget; 4× headroom).
3. **Studio 1a-i.A1** (`8ee347f`, 2026-05-13) — Bridgeable Studio shell substrate: `/studio` route tree (path-segment-canonical URL scheme with `:vertical` / `:editor` / `live` segments), persistent left rail with expanded + icon-strip modes (rail-collapses-not-replaces on editor click; localStorage-persisted), top bar with scope switcher + Edit/Live mode toggle, placeholder Platform + vertical overviews (static section cards, inventory deferred to 1a-ii), `/studio/live` Live-mode placeholder (wrap deferred to A2), 10-route redirect layer from standalone `/visual-editor/*` + `/runtime-editor` paths (query-param translation: focus_type→category, template_id→template), 3 inspector tabs (Focuses / Documents / Workflows) Studio-context-aware for deep-link construction, AdminHeader nav link renamed Visual Editor → Studio, VisualEditorIndex preserved as component-level redirect. 9 editor pages mount inside Studio shell unchanged (editor adaptation to rail-expand signal deferred to 1a-i.B). Backend untouched. 68 new vitest tests across studio-routes (URL scheme + redirect translation), StudioShell (overview / live / rail collapse), StudioScopeSwitcher (vertical list + scope-switch nav). ~2,244 LOC.
4. **Verticals-lite precursor** (`c70050f`, 2026-05-13) — `verticals` table + service + 3 admin endpoints + `/admin/verticals` page; precursor to Studio shell. Migration `r95_verticals_table` (spec named `r92` but r92-r94 already existed; renumbered per CLAUDE.md §12 Spec-Override). ~720 LOC.
5. **Arc 4a.2a** (`8affc8f`, 2026-05-13) — Ops-board cluster Path 1 wrap + 28 supported_surfaces backfills + dashboard-grid parity test branch. 17 ops-board widgets wrapped via registerComponent HOC; componentMap consumers updated; revenue_summary + ar_summary deferred (no frontend React component). ~1,624 LOC.
6. **Arc 4d** (`9fbcab5`, 2026-05-13) — Scope cascade visualization + tenth canonical shared authoring primitive (SourceBadge with letter/chip variant) + eleventh candidate co-located (ScopeDiffPopover). Documents Class C → Class B transition via `_resolve_version` extension. Sixth audit-count recalibration shape (audit-frames-as-uniform-where-substrate-architecturally-distinct). PRE-SEPTEMBER ARC 4 SEQUENCE CLOSES. ~1,565 LOC.
7. **Canon/state separation** (`c655771`, 2026-05-13) — CLAUDE.md cleanup (2537 → 1631 lines) + STATE.md + DECISIONS.md. Documentation discipline: Sonnet writes STATE.md only; canon stays canon (Opus-only, batched).
8. **Arc 4c** (`efeed99`, 2026-05-12) — Focus compositions canvas polish: AlignmentGuideOverlay + shift-marquee cumulative-select + drop-shadow drag lift + inspector Move-left/Move-right + Alt+Arrow keyboard reorder + ColumnCountPopover. ~1,747 LOC.
9. **Arc 4b.2b** (`7ff864a`, 2026-05-12) — Mention consumer UX: `@` trigger + SuggestionDropdown integration + getCaretCoordinates companion utility + 4 Jinja-aware field sites. ~1,400 LOC.
10. **Arc 4b.2a** (`66ec8c5`, 2026-05-12) — Mention substrate: Jinja `ref` filter + dedicated `/api/v1/documents-v2/admin/mentions/resolve` endpoint + per-render MentionResolutionCache. ~640 LOC.

## Open questions / blockers

- **Sage CSV exports** — blocked on Sunnycrest accountant providing invoice history, customer list, cash receipts files. Once received, Data Migration Tool can complete.
- **Pre-existing bugs** catalogued in `backend/docs/BUGS.md` (separate file) — `quote_service` calls `audit_service.log` but function is `log_action` (BUGS.md entry #7), unrelated to active arc.
