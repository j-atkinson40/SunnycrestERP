# Studio Nav — Widget Builder Entry Substrate

**Date:** 2026-05-25
**Type:** Read-only investigation
**Scope:** Operator-validation finding from staging — Bridgeable Studio sidebar at `admin.getbridgeable.com` shows "Focus Builder" rail entry with "New" badge but no analogous "Widget Builder" entry. WB-4a..WB-8 substrate cycle shipped operator-ready end-to-end, but sidebar discoverability of the new authoring surface appears never registered.
**Working HEAD:** `5df25a1` (WB-8 build report — WB substrate cycle structurally complete)
**Constraint:** Zero production code changes. Zero test changes. Investigation + STATE.md only.

---

## 1. Context

The Widget Builder substrate shipped through eight sub-arcs (WB-1 through WB-8, May 21–24, 2026) — schema, runtime, canvas authoring (WB-4a), per-atom inspectors + composition validation + list view (WB-4b), canvas preview (WB-5), saved-view binding picker (WB-6), button action dispatch (WB-7), and variant authoring (WB-8). Per the WB-8 build report (STATE.md current Recent-build entry), the cycle is "structurally complete — end-to-end operator-ready stack: visually authored (WB-4a/4b) + bound (WB-6) + previewed (WB-5) + actions (WB-7) + variants (WB-8)."

Operator validation on staging (admin.getbridgeable.com) surfaced a missing rail entry: the persistent left rail in `StudioShell` shows a dismissible "Focus Builder" entry with a "New" badge (shipped in sub-arc F-1.1 on May 18, 2026) pointing at `/studio/builder/focuses`, but no analogous entry pointing at `/studio/widget-builder` or visually announcing the Widget Builder. From the operator's perspective, the Focus Builder is the only "builder" substrate present in Studio chrome.

This investigation audits the substrate to determine: (a) whether a rail entry is genuinely missing, (b) whether the existing "Widgets" rail entry already covers the surface and the operator's perception was confused by absence of a "New" badge, (c) whether the Studio overview page should also be carrying a builder card, and (d) what the minimal fix scope is. The investigation is bounded to ~30 minutes / ~3,500 words per the dispatch — narrower than WB sub-arc investigations because the substrate audit converges quickly on a small set of options.

The Focus Builder rail entry's shipping pattern (commit `7456b57`, sub-arc F-1.1) is the canonical precedent. The investigation explicitly mirrors against it for shape parity.

---

## 2. Area 1 — Studio Sidebar Nav Substrate Audit

The Studio rail is mounted at `frontend/src/bridgeable-admin/components/studio/StudioRail.tsx` and consumed by `StudioShell` (`frontend/src/bridgeable-admin/pages/studio/StudioShell.tsx:218-224`). The rail renders in two modes (expanded ~240px / collapsed ~48px icon strip) per the rail-collapses-not-replaces canon (DECISIONS.md 2026-05-13 entry; cited in `StudioRail.tsx:8-15`).

**Rail entry registration location:** `frontend/src/bridgeable-admin/components/studio/StudioRail.tsx:81-103` — single module-scoped `RAIL_ENTRIES: RailEntry[]` array. Order of array elements is display order in both render modes. The current array has 11 entries (Overview + Themes + Focuses + Focus Builder + Widgets + Documents + Classes + Workflows + Edge Panels + Registry + Plugin Registry) plus a Spaces "Coming soon" stub rendered separately at the bottom (`StudioRail.tsx:356-367`).

**Rail entry shape** (the `RailEntry` interface at `StudioRail.tsx:48-67`):

```ts
interface RailEntry {
  editor: StudioEditorKey | null      // null = Overview OR override-href entry
  label: string                       // Display label
  icon: LucideIcon                    // Lucide icon component
  disabled?: boolean                  // Dimmed + non-clickable
  badge?: string                      // Trailing badge (e.g. "Coming soon")
  overrideHref?: string               // F-1.1 addition — non-editor URL target
  newAffordanceId?: string            // F-1.1 addition — dismissible "New" badge key
}
```

**Ordering substrate:** array-position-canonical, no separate `position` field. Display order in expanded mode (`StudioRail.tsx:266-355`) matches collapsed icon-strip order (`StudioRail.tsx:197-229`) by iterating the same `RAIL_ENTRIES` array. The header comment at line 80 calls out "Order = display order in the rail. Mirrors VisualEditorIndex card order" — display-order intent is single-canonical at the array level.

**Badge substrate:** two badge surfaces present in the rail.

1. **Platform-only badge** (`StudioRail.tsx:327-331`) — surfaces "Platform" trailing pill for entries whose `editor` key is in the `PLATFORM_ONLY_EDITORS` set (`classes`, `registry`, `plugin-registry` per `studio-routes.ts:58-62`). Always-shown; not dismissible. Visual treatment: `bg-surface-base` muted pill, font-plex-mono.

2. **Dismissible "New" badge** (`StudioRail.tsx:332-352`) — surfaces when `entry.newAffordanceId` is set AND the operator hasn't dismissed it via `localStorage[entry.newAffordanceId] === "1"`. Visual treatment: `bg-accent-subtle text-accent` with X dismiss button. The localStorage key pattern is `bridgeable.<feature>.studio-rail-banner-dismissed` (the Focus Builder instance is exported as `FOCUS_BUILDER_RAIL_BANNER_KEY` at `StudioRail.tsx:76-77`).

A "Coming soon" badge style also exists via the explicit `badge` field (`StudioRail.tsx:299-303`) — used today only by the disabled Spaces stub.

**Section grouping:** none today. The rail is a flat list; the only visual separation is the disabled Spaces stub rendered after a `border-t` separator (`StudioRail.tsx:356-367`). The F-1.1 commit message describes the Focus Builder entry as "separate Focus Builder entry alongside existing Focuses" — alongside, not nested-under. The current authored model is flat-list with sibling-adjacency conveying relationship.

**Collapse state:** persisted at `localStorage[STUDIO_RAIL_EXPANDED_KEY]` (key constant `"studio.railExpanded"` at `studio-routes.ts:270`). Initial state precedence (per `StudioShell.tsx:110-127`): localStorage value if set → otherwise route-based default via `computeInitialRailExpanded(pathname)` (overview routes default expanded, editor + Live routes default collapsed). The Overview entry uniquely does NOT collapse the rail on click (`StudioRail.tsx:175-177`).

**Maturity:** the rail substrate is mature. The `overrideHref` + `newAffordanceId` extensions added by F-1.1 are a small additive primitive (per the F-1.1 commit message: "small primitive addition future Page Builder / Document Builder / Workflow Builder rail entries consume"). The substrate is sized for incremental adoption.

---

## 3. Area 2 — Focus Builder Precedent

The Focus Builder rail entry shipped in commit `7456b57` (May 18, 2026) under sub-arc F-1.1. The commit message at `git show 7456b57` is explicit about the precedent shape: "Focus Builder wasn't reachable from Studio rail — operators had to type `/studio/builder/focuses` manually. Per investigation Q-41 lock, the rail needed a navigation affordance pointing at the new route."

**Diff shape (file: `StudioRail.tsx`):**

1. **Added `overrideHref` + `newAffordanceId` fields to the `RailEntry` interface.** Two optional fields. `overrideHref` carries an absolute URL that bypasses the `studioPath()` builder (used for non-editor-key URLs like `/studio/builder/focuses`); `newAffordanceId` carries the localStorage key for the dismissible "New" badge.

2. **Added one `RailEntry` to the `RAIL_ENTRIES` array** at position 3 (between Focuses and Widgets):

   ```ts
   {
     editor: null,
     label: "Focus Builder",
     icon: Sparkles,
     overrideHref: "/studio/builder/focuses",
     newAffordanceId: FOCUS_BUILDER_RAIL_BANNER_KEY,
   }
   ```

3. **Exported `FOCUS_BUILDER_RAIL_BANNER_KEY` constant** as `"bridgeable.focus-builder.studio-rail-banner-dismissed"`.

4. **Extended `handleEntryClick`** to detect `overrideHref` and navigate to the absolute URL instead of routing through `studioPath()` (`StudioRail.tsx:160-166`). Override entries collapse the rail on click, mirroring editor-open behavior.

5. **Extended both render modes** (collapsed icon strip + expanded list) to compute a stable `testIdSuffix` for `overrideHref` entries (`"focus-builder"` literal) since they lack an `editor` key. Stable testids preserve Playwright targeting.

6. **Added per-render-mode "New" badge rendering** in expanded mode only (`StudioRail.tsx:332-352`). Icon-strip mode does NOT render the New badge — operators see it only when the rail is expanded. This is a deliberate compactness choice; the icon strip is meant to be visually quiet.

7. **Added `dismissedAffordances` state** (`StudioRail.tsx:133-154`) — read once on mount from localStorage, mutated by the dismiss button.

8. **Created-new route reachability:** the Focus Builder route at `/studio/builder/focuses` is the entry point. There is no separate "/studio/builder/focuses/new" — clicking the rail entry lands on `FocusBuilderPage` which itself surfaces the create-new affordance.

**Lock pattern for Widget Builder mirror:** the shape parallels almost exactly. A new `RailEntry` with `editor: null`, `overrideHref: "/studio/widget-builder"` (the existing route per `StudioShell.tsx:269-276`), `newAffordanceId: WIDGET_BUILDER_RAIL_BANNER_KEY`, an appropriate Lucide icon (candidate: `Sparkles` to match Focus Builder, OR `LayoutDashboard` to match the existing Widgets editor, OR a distinct icon like `Grid` / `Frame` / `Wrench` to differentiate). Position: array index 5 (between Widgets and Documents), mirroring the Focus Builder placement adjacent to Focuses.

---

## 4. Area 3 — Widget Builder Route Audit

The Widget Builder routes are registered in `StudioShell.tsx:259-281` inside the studio shell's nested `<Routes>` block. Three relevant routes:

1. **`/studio/widget-builder/:slug`** (`StudioShell.tsx:269-272`) — editor surface mounted on `WidgetBuilderPage`. Opens an existing widget definition by slug.

2. **`/studio/widget-builder`** (slug-optional, `StudioShell.tsx:273-276`) — same component, no slug. Per the inline comment "no slug shows the create landing card" — operator sees a create-new affordance on the same component.

3. **`/studio/widgets`** (`StudioShell.tsx:281`) — list view via `WidgetListPage`. WB-4b's rewire: "widget list view replaces the legacy `WidgetEditorPage` at `/studio/widgets`. The legacy editor remains on disk for the class-config sub-flow until widget-class authoring migrates." The rail's existing "Widgets" entry (with `editor: "widgets"`) routes through `studioPath({editor: "widgets"})` → `/studio/widgets` → `WidgetListPage`.

**Operator workflow today:**

- Operator clicks "Widgets" in the rail → lands on `/studio/widgets` → sees `WidgetListPage` with "+ New Widget" button (`WidgetListPage.tsx:88-96`) + filter chips for All/Platform/Vertical (`WidgetListPage.tsx:68-86`) + a list of existing composed widget definitions.
- Clicking "+ New Widget" calls `widgetBuilderService.create({ title: "Untitled widget", tier_scope: "vertical" })` and navigates to `/studio/widget-builder/<widget_id>` (`WidgetListPage.tsx:42-55`).
- Clicking any existing widget in the list navigates to the same `/studio/widget-builder/:slug` editor surface.

**Reservation:** the route segments `widget-builder` and `builder` are both registered in `RESERVED_FIRST_SEGMENTS` (`studio-routes.ts:49-55`) so `parseStudioPath` does not mis-classify them as vertical slugs. This was added in WB-4a (per the inline comment at `studio-routes.ts:45-48`).

**Substrate maturity:** end-to-end operator-ready. `WidgetListPage` provides discovery; `WidgetBuilderPage` provides authoring; the "+ New Widget" affordance closes the create-new loop. The substrate functions correctly when the operator knows to click "Widgets" in the rail.

**Discoverability gap:** the rail label "Widgets" reads as the legacy widget editor (it was authored when the rail was first scaffolded in commit `8ee347f`, May 13, 2026, before WB-4a existed). An operator familiar with the pre-WB Studio chrome would expect "Widgets" to open the class-style component editor — and indeed that was the legacy behavior before WB-4b rewired the route. The operator-validation finding surfaces this gap: the substrate is present but the label + absence-of-"New"-badge fails to signal that the surface behind it changed.

---

## 5. Area 4 — Widgets List-View Audit

`WidgetListPage` at `frontend/src/bridgeable-admin/components/widget-builder/WidgetListPage.tsx` is a 100-line surface (read for this investigation):

**Surface shape:** header bar with title "Widgets" + tier filter chips + "+ New Widget" primary button; below, a scrollable main region renders the widget list (lines beyond 100 not read but the header at lines 1-13 establishes the shape: "Lists every composed widget for the tenant (rows that carry a `composition_blob`). Filter by tier_scope (All / Platform / Vertical). '+ New Widget' creates a new draft via the existing `widgetBuilderService.create` + navigates to the editor.").

**Per-widget click destination:** `/studio/widget-builder/<widget_id>` (the editor — `WidgetListPage.tsx:49` for create path; click navigation for existing rows lives beyond line 100 but follows the same pattern per the file's header comment).

**Create-new affordance state:** mature. The "+ New Widget" button (lines 87-96) calls `widgetBuilderService.create({ title: "Untitled widget", tier_scope: "vertical" })` synchronously, navigates to the editor on success, and recovers via `refresh()` on error.

**Phase 1 scope** (per the file header at lines 11-13): "no delete, no duplicate, no bulk ops, no search, no per-tenant filtering. Bounded surface; later phases add affordances as operator signal warrants." The list view is intentionally minimal — the substrate prioritizes editor work, defers list-view polish.

**Operator-perceived shape:** an operator landing on `/studio/widgets` today sees a functional list + create surface. The substrate is operator-ready. What's missing is the navigational signal that this surface exists and is new.

---

## 6. Area 5 — Sidebar Nav Substrate Completeness

Beyond the Widget Builder discoverability gap, the rail has additional asymmetries worth surfacing:

1. **Documents:** the `documents` editor key routes to `DocumentsEditorPage`, which per its own header is the "block-based document template authoring (Phase D-10 + D-11, June 2026)" surface — operator-ready substrate parallel to Widget Builder. The rail's "Documents" label does NOT carry a "New" badge despite the editor having shipped substantial new authoring substrate. If Widget Builder gets a "New" badge, Documents arguably warrants one too on the same logic. Symmetry consideration, not a fix-blocking gap.

2. **Edge Panels:** the `edge-panels` editor key routes to `EdgePanelEditorPage`. Investigation `docs/investigations/2026-05-14-edge-panel-substrate.md` establishes this as substrate work. The rail entry exists but no signal of newness. Same symmetry consideration as Documents.

3. **Plugin Registry vs Registry:** two distinct entries (`registry` + `plugin-registry`) per `STUDIO_EDITOR_KEYS` at `studio-routes.ts:36-38`. Both are platform-only. The distinction surfaces in the rail as two adjacent "Registry"-shaped labels — Registry (in-memory component registry inspector) and Plugin Registry (PLUGIN_CONTRACTS-derived browser). This is canonical per the canon registry but operator-disambiguation may need polish; not a fix-blocking gap.

4. **Spaces stub:** rendered at the bottom of the rail with `Soon` badge (`StudioRail.tsx:356-367`). Canonical per the May 2026 reorganization. Stays as-is.

5. **Studio Overview page:** the `StudioOverviewPage` (rendered at `/studio` and `/studio/:vertical` per `StudioShell.tsx:86-98`) is the platform/vertical overview. The investigation did NOT read its full surface — beyond grep'ing for "Widget Builder" hits (none). If the overview page surfaces editor cards parallel to the rail, those cards would need symmetric updates. This is a candidate scope expansion the dispatch deliberately bounded out of; flagged as out-of-arc-scope discovery.

**Conclusion:** Widget Builder is the sharpest gap (operator-surfaced from staging). Documents + Edge Panels are softer parallel gaps inherited from the same "rail entries don't track substrate maturity transitions" class of bug. Studio Overview is a separate audit. The Widget Builder fix is independently mergeable.

---

## 7. Area 6 — Fix Scope Determination

Three candidate fix scopes:

**Option A — Minimal (single rail entry, ~25-35 LOC).** Add one `RailEntry` to `RAIL_ENTRIES` mirroring the Focus Builder shape. New exported localStorage key constant. Position: array index 5 (between Widgets and Documents). Icon: open question — `Sparkles` matches Focus Builder visually (which would emphasize "builder family" cohesion) but conflicts with the icon already used by Focus Builder; alternatives include `LayoutDashboard` (current Widgets icon — would conflict), `Grid`, `Frame`, `Wand2`, `Wrench`. Lock at dispatch time. Test surface: vitest extension to `StudioRail.test.tsx` (assert new entry renders + click navigates + New badge dismisses). LOC estimate: ~25-35 production + ~30-40 test. **Closes the operator-surfaced gap with no other changes.**

**Option B — Minimal + label rationalization (~40-60 LOC).** Option A + rename the existing "Widgets" entry to "Widget Library" or "Widgets" → "Widget Editor" (legacy) vs "Widget Builder" (new) clarification. Risk: the existing "Widgets" rail entry now points at `WidgetListPage` (the list view backing the Widget Builder), so renaming it to "Widget Library" creates the cleanest mental model (Widget Library = list; Widget Builder = editor). However, this changes existing operator habits and may surprise operators who've adopted the current labeling. Open question for dispatch.

**Option C — Minimal + Documents + Edge Panels symmetric badges (~80-120 LOC).** Option A + analogous "New" badges on Documents + Edge Panels entries (since both shipped substantial substrate after the rail was authored). Larger scope; defensible on symmetry grounds. Extends the fix beyond the operator-surfaced gap.

**Option D — Studio Overview parity (~150+ LOC, possibly multi-arc).** Add a Widget Builder card to `StudioOverviewPage` alongside whatever editor cards exist there. Requires reading + extending the overview page substrate. The dispatch explicitly excludes this — out-of-arc.

**LOCK: Option A.** Rationale: (1) operator-surfaced gap is specific — "no Widget Builder entry" — and Option A closes it directly; (2) Focus Builder precedent is a near-exact shape match and was itself sized as a tight follow-up arc; (3) label rationalization (Option B) and parallel badges (Option C) are defensible follow-ups but lack operator-surfaced signal today; (4) substrate addition is risk-bounded — `overrideHref` + `newAffordanceId` primitives are mature and tested.

Open sub-questions for dispatch lock:

- **Q-A1:** Icon choice — `Sparkles` (Focus Builder match — "builder family"), `Wand2` (similar magical-tool affordance), `Frame` (suggests canvas/composition), `LayoutDashboard` (matches existing Widgets editor — but creates ambiguity), or other. Recommend `Sparkles` for builder-family cohesion; if Sparkles is reserved for Focus Builder specifically, recommend `Wand2`.
- **Q-A2:** Position in `RAIL_ENTRIES` — array index 5 (between Widgets and Documents, mirroring Focus Builder's position 3 between Focuses and Widgets) is the canonical mirror. Alternative: position 4 (immediately after Widgets, even more tightly bonded). Recommend index 5 (between Widgets and Documents) for parallel cadence with Focus Builder.
- **Q-A3:** localStorage key — `"bridgeable.widget-builder.studio-rail-banner-dismissed"` mirrors the Focus Builder constant string. Per-operator dismissal independent of Focus Builder dismissal. Lock as proposed.
- **Q-A4:** `overrideHref` value — `/studio/widget-builder` (slug-optional landing) or `/studio/widgets` (list view)? Focus Builder routes to `/studio/builder/focuses` which is the FocusBuilderPage canvas, not a list view. Mirror would route to `/studio/widget-builder` (the WidgetBuilderPage create-landing). However, an operator clicking the new rail entry probably benefits from seeing the list first to understand the substrate before authoring. Open. Recommend `/studio/widgets` (list view) because: (a) it surfaces both existing widgets AND the "+ New Widget" affordance, (b) it's the canonical Phase 1 substrate per WB-4b. The Focus Builder routes directly to the canvas because Focus Builder ships without a list view today; the substrate shapes differ.

---

## 8. Area 7 — Canon Candidates (NOT Filed)

Two candidates surfaced for the canon-update arc to file (not filed inline per dispatch constraint):

1. **Operator-facing substrate must include entry-point wiring as a substrate deliverable, not a follow-up.** WB-4a..WB-8 shipped the Widget Builder substrate end-to-end without registering a rail entry. Focus Builder F-1 had the same gap, closed in F-1.1 as a tight follow-up. Both arcs were technically substrate-complete without rail entries — operators could reach the surface by typing the URL. But operator-validation surfaced both gaps as operator-perceived absence: "the substrate isn't here because I can't find it." The canon refinement: any sub-arc shipping operator-facing substrate MUST include rail entry registration (or analogous discoverability wiring) as a deliverable, not as a follow-up arc. Cross-references: F-1.1 commit `7456b57`'s commit message ("Focus Builder wasn't reachable from Studio rail — operators had to type `/studio/builder/focuses` manually"); WB-1..WB-8 collective omission of rail entry registration.

2. **Operator-validation surfaces entry-point gaps that substrate cycles miss; investigation-first arcs should explicitly model discoverability as a substrate dimension.** Investigation dispatches for substrate work tend to enumerate Areas covering schema, runtime, services, components, and tests — but rarely call out "discoverability / navigation entry-point wiring" as a substrate Area. When the substrate ships without an entry-point, operator-validation against staging catches the gap. The canon refinement: future substrate-cycle investigations include an explicit Area for navigation entry-point auditing. The substrate isn't operator-ready until it's discoverable; discoverability auditing belongs at investigation time, not at operator-validation time. Cross-references: same as candidate 1; the WB cycle's 6 investigations (canvas / bindings / canvas-preview / button-actions / variants) collectively did not audit rail navigation entries.

---

## 9. Proposed Fix Execution Plan

**Scope:** Option A locked.

**File targets:**

1. `frontend/src/bridgeable-admin/components/studio/StudioRail.tsx` — add `WIDGET_BUILDER_RAIL_BANNER_KEY` exported constant; add one `RailEntry` to `RAIL_ENTRIES` at array index 5; extend `dismissedAffordances` initialization to read the new key; existing render logic already handles `overrideHref` + `newAffordanceId` generically — no logic changes required.

2. `frontend/src/bridgeable-admin/components/studio/StudioRail.test.tsx` — extend existing tests to assert the new entry renders in both modes; assert click navigates to `/studio/widgets` (or `/studio/widget-builder` per Q-A4 lock); assert New badge surfaces; assert dismiss button updates localStorage; assert dismissed state persists across re-renders.

**Estimated LOC:**

- Production: ~25-35 lines (one RailEntry literal ~7 lines + one exported constant ~3 lines + one initialState read ~5 lines + ~5-10 lines for testid-suffix branch extension if not already generic).
- Tests: ~30-50 lines (mirror the Focus Builder test pattern — 1 render assertion + 1 click navigation assertion + 1 New badge + 1 dismiss + 1 persistence).

**Total estimated LOC:** ~55-85 lines (production + test). Single file each, single-commit changeset, no migration, no backend.

**Dispatch dependencies:** Q-A1 (icon) + Q-A4 (overrideHref target) must lock before dispatch. Q-A2 (position) + Q-A3 (localStorage key) have recommended defaults; dispatch can confirm or override.

**Out-of-scope explicitly (per investigation Area 5):** Documents + Edge Panels symmetric badges (Option C), label rationalization for existing Widgets entry (Option B), Studio Overview page additions (Option D), Plugin Registry / Registry disambiguation polish. Each is a separate operator-validation pass.

**Test discipline:** the existing `StudioRail.test.tsx` already tests the Focus Builder entry's render + click + dismiss path. Mirror that shape. The substrate is mature; no new test-substrate primitives required.

---

## 10. Architectural Surprises During Investigation

1. **WB-4b rewired `/studio/widgets` to the new WidgetListPage but did not update the rail label.** The rail's "Widgets" entry (`StudioRail.tsx:96`) was authored in commit `8ee347f` (Studio 1a-i.A1, May 13, 2026) pointing at the legacy `WidgetEditorPage`. WB-4b's route rewire (commit `3d39598`, May 21, 2026 at `StudioShell.tsx:281`) silently inherited the rail label. The substrate behind the label changed without the label changing — exactly the operator-perception gap that surfaced from staging. This is a class of bug worth canonicalizing: route-target changes without companion navigation-entry updates produce silent operator-perception drift.

2. **Focus Builder shipped with its rail entry as a tight follow-up arc (F-1.1), not as part of F-1.** The F-1 substrate cycle shipped without rail entry registration; F-1.1 added it. The WB cycle has not yet shipped its analogous follow-up — this investigation is positioned to dispatch that follow-up. The pattern is symmetric: substrate work consistently under-scopes entry-point wiring.

3. **The `overrideHref` primitive shipped in F-1.1 was authored with explicit future-arc consumption in mind.** Per the F-1.1 commit message: "RailEntry primitive extended with optional overrideHref field bypassing studioPath() for non-editor URLs — small primitive addition future Page Builder / Document Builder / Workflow Builder rail entries consume." Widget Builder was not enumerated in that list (the WB cycle had not yet been dispatched on May 18, 2026), but the primitive's design assumed exactly this pattern of future-builder additions. The substrate is ready; the fix is a literal `overrideHref` consumer.

4. **The Spaces "Coming soon" stub uses a different badge surface than the F-1.1 "New" badge.** Spaces uses the inline `badge: "Coming soon"` field (renders gray, undismissible); F-1.1 added a parallel render path for `newAffordanceId` (renders accent, dismissible). The rail thus has three distinct badge surfaces: Platform (platform-only editor pill), Coming soon (disabled stub label), and New (dismissible feature announcement). All three coexist in the rail. The canonical decision tree for which badge to use isn't documented inline; lives in the F-1.1 commit message and this investigation. Worth surfacing as a canon candidate if the rail accumulates more badge variants.

5. **WidgetListPage's "+ New Widget" creates a draft with a hard-coded title `"Untitled widget"` and `tier_scope: "vertical"`.** Operators reaching the create-new path lose vertical context if the current Studio scope is Platform; the new widget defaults to vertical-scope regardless. This is a separate, smaller operator-experience gap surfaced incidentally during this investigation. Out of arc scope; flag for follow-up.

---

**End of investigation.**

Cross-references:
- WB substrate cycle build reports: `docs/investigations/2026-05-21-widget-builder.md`, `docs/investigations/2026-05-21-widget-builder-canvas.md`, `docs/investigations/2026-05-22-widget-builder-bindings.md`, `docs/investigations/2026-05-23-widget-builder-canvas-preview.md`, `docs/investigations/2026-05-24-widget-builder-button-actions.md`, `docs/investigations/2026-05-24-widget-builder-variants.md`.
- Focus Builder precedent commit: `7456b57` (sub-arc F-1.1, 2026-05-18) — Studio rail navigation entry + seed corrections.
- Studio shell substrate: `docs/investigations/2026-05-13-studio-shell.md`, commit `8ee347f` (Studio 1a-i.A1).
- WB substrate cycle commits: `3680950` (WB-4a), `3d39598` (WB-4b), `5df25a1` (WB-8).
- Rail file: `frontend/src/bridgeable-admin/components/studio/StudioRail.tsx`.
- Routes file: `frontend/src/bridgeable-admin/lib/studio-routes.ts`.
- Shell file: `frontend/src/bridgeable-admin/pages/studio/StudioShell.tsx`.
- List view file: `frontend/src/bridgeable-admin/components/widget-builder/WidgetListPage.tsx`.
