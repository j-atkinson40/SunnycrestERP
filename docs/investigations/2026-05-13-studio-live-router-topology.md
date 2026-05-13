# Studio Live mode router topology — investigation findings

Read-only investigation. Builds on `docs/investigations/2026-05-13-studio-shell.md`, `docs/investigations/2026-05-13-studio-1a-internal.md`, and follow-up #2's deferred-Part-1 framing in commit `5659e3b`. Surfaces the architectural decision the Part 1 STOP triggered: how does Studio dispatch internally so Live mode's deep tenant paths match the tenant route tree the way `/runtime-editor/*` did pre-Studio?

Investigation only. No source edits, no test edits, no migrations. Conclusions feed the build prompt that follows.

---

## Section 1: Recap of failure modes

### How the routing currently lays out

Outer router (`frontend/src/bridgeable-admin/BridgeableAdminApp.tsx:206,209`):

```
<Route path="/bridgeable-admin/studio/*" element={studioRoute} />
<Route path="/studio/*"                   element={studioRoute} />
```

Inside `studioRoute`, `<StudioShell />` mounts. StudioShell does NOT declare any nested `<Routes>` / `<Route>` — it dispatches by calling `parseStudioPath(location.pathname)` and rendering one of three children directly (`StudioOverviewPage`, an editor page from `EDITOR_PAGES`, or `StudioLiveModeWrap`). See `StudioShell.tsx:69-72,157-165`.

For a URL like `/bridgeable-admin/studio/live/wastewater/dispatch/funeral-schedule?tenant=testco&user=...`:

1. Outer `<Route path="/bridgeable-admin/studio/*">` matches; outer router consumes `/bridgeable-admin/studio`. The splat segment captures `live/wastewater/dispatch/funeral-schedule`.
2. StudioShell mounts. `parseStudioPath` (in `studio-routes.ts:403-462`) reads `location.pathname` directly — it does NOT consume any path. It returns `{ isLive: true, vertical: "wastewater", editor: null }`. Note that `parseStudioPath` looks only at the first two segments after `/studio/`: it does NOT signal that there is a deeper tail (`dispatch/funeral-schedule`) the shell should be aware of.
3. StudioShell dispatches `isLive` → `<StudioLiveModeWrap vertical="wastewater" />` (`StudioShell.tsx:158-159`).
4. `StudioLiveModeWrap` (`StudioLiveModeWrap.tsx:52-76`) renders `<Suspense>` → `<RuntimeEditorShell studioContext verticalFilter="wastewater" />`. No path segments are consumed at this level — there is no `<Route>` declaration in the wrap.
5. `RuntimeEditorShell.tsx:421-435` mounts `<TenantProviders>` → `<ShellWithTenantContext>` → `<TenantRouteTree />` (`RuntimeEditorShell.tsx:210-212`).
6. `TenantRouteTree.tsx:49-53` renders `<Routes>{renderTenantSlugRoutes({ excludeRootRedirect: true })}</Routes>`. The nested `<Routes>` element is the second `<Routes>` in the render tree (the first is in BridgeableAdminApp at the top level).

React Router v7's nested-`<Routes>` semantics: a nested `<Routes>` matches against `location.pathname` **minus the segments that ancestor matched `<Route>` declarations have already consumed**. The only ancestor matched-and-consuming `<Route>` between the URL bar and `TenantRouteTree` is `<Route path="/bridgeable-admin/studio/*" element={studioRoute} />`, which consumes `/bridgeable-admin/studio`. Everything to the right of that — `/live/wastewater/dispatch/funeral-schedule` — is "unconsumed."

The tenant route declarations from `renderTenantSlugRoutes` are relative paths (`App.tsx:542-1914`): `<Route path="dashboard">`, `<Route path="home">`, `<Route path="dispatch/funeral-schedule">`, etc. A relative `<Route path="dispatch/funeral-schedule">` inside the nested `<Routes>` is asked to match against the unconsumed remainder. It only matches if the remainder is exactly `dispatch/funeral-schedule` — but the actual remainder is `live/wastewater/dispatch/funeral-schedule`. No match.

The nested `<Routes>` falls through to `<Route path="*" element={<HomePage />} />` (the runtime-editor branch's catch-all from `App.tsx:1907`). HomePage renders. The tenant page the URL pointed at never mounts.

### Pre-Studio: why this worked

Pre-Studio, BridgeableAdminApp registered `<Route path="/bridgeable-admin/runtime-editor/*" element={runtimeEditorRoute}>` (now retired, redirected to StudioRedirect, see `BridgeableAdminApp.tsx:185-199`). For a URL `/bridgeable-admin/runtime-editor/dispatch/funeral-schedule?tenant=...`:

1. Outer `<Route path="/bridgeable-admin/runtime-editor/*">` matched; consumed `/bridgeable-admin/runtime-editor`. Splat captured `dispatch/funeral-schedule`.
2. RuntimeEditorShell mounted directly under this outer route.
3. TenantRouteTree's nested `<Routes>` saw remainder = `dispatch/funeral-schedule` (one ancestor `<Route>` already consumed everything before it).
4. Relative `<Route path="dispatch/funeral-schedule">` matched cleanly. DispatchFuneralSchedulePage rendered.

The key architectural difference: pre-Studio had **two consuming `<Route>` declarations** on the path from URL bar to TenantRouteTree (BridgeableAdminApp's outer `/runtime-editor/*` + ABOVE-the-line `/bridgeable-admin` consumption — actually just one `<Route>`, consuming the editor prefix in one match). The unconsumed remainder was the literal tenant route path. Post-Studio there is still only **one consuming `<Route>`** (the outer `/studio/*`) but the remainder now contains additional Studio-shape prefix segments (`live/<vertical>/`) that tenant routes don't know how to consume.

### Tenant route inventory pre-Studio bookmarks could carry

Tenant routes declared in `renderTenantSlugRoutes` (`App.tsx:535-1917`). Each was reachable pre-Studio via `/bridgeable-admin/runtime-editor/<path>?tenant=...&user=...`. Inventory by category (not exhaustive — see `App.tsx` for full list):

- Dashboards: `dashboard`, `home`, `dev/focus-test`
- Dispatch: `dispatch/funeral-schedule` (Gates 14, 15, 22)
- Hubs: `financials`, `production-hub`, `compliance`, `inbox`
- Funeral home: `cases`, `cases/:id`, `cases/new`, `case-templates/...`
- Personalization Studio: `personalization-studio/...`, `personalization-studio/family-approval/:token`
- Saved views: `saved-views`, `saved-views/new`, `saved-views/:viewId`, `saved-views/:viewId/edit`
- Tasks: `tasks`, `tasks/new`, `tasks/:taskId`
- Triage: `triage`, `triage/:queueId`
- Briefings: `briefing`, `briefing/:id`
- Urns / resale: `urns/catalog`, `urns/orders`, `urns/orders/new`, `urns/proof-review/:orderId`, `resale`, `resale/catalog`, `resale/orders`, `resale/inventory`
- Operations: `order-station`, `transfers`, `alerts`, `journal-entries`, `social-service-certificates`, `financials/board`, `agents`, `agents/:jobId/review`, `ar/collections/:sequenceId/review`
- Settings: `settings/tax`, `settings/ai-intelligence`, `settings/saved-orders`, `settings/external-accounts`, plus per-feature sub-routes (`settings/spaces`, `settings/portal-branding`, etc.)
- Admin: `admin/company-classification`, `admin/data-quality`
- Manufacturing-specific: `bom`, `bom/:bomId`, `projects`, `projects/:projectId`, `qc`
- Reports: `reports`

Approximately **80+ relative tenant route paths** in `renderTenantSlugRoutes`. All are reachable pre-Studio via `/bridgeable-admin/runtime-editor/<tail>`; all are broken post-Studio at `/bridgeable-admin/studio/live/<vertical>/<tail>`.

### Per-failing-test concrete URLs

| Test | URL navigated | Tail TenantRouteTree's `<Routes>` sees | Match? |
|---|---|---|---|
| Gate 14 (`14-delivery-card-click-to-edit.spec.ts:37-38`) | `/bridgeable-admin/runtime-editor/dispatch/funeral-schedule?tenant=testco&user=...` → `StudioRedirect` → `/bridgeable-admin/studio/live?tenant=testco&user=...` (loses `/dispatch/funeral-schedule`) | empty / `live` | No — falls through to `*` → HomePage |
| Gate 15 (`15-ancillary-card-click-to-edit.spec.ts:80-82`) | same pre-redirect path; `+?focus=funeral-scheduling&edit=1` | same as Gate 14 plus `?focus=` query | Same as Gate 14 |
| Gate 22 (`22-delivery-card-subsection.spec.ts:37-38`) | `/bridgeable-admin/runtime-editor/dispatch/funeral-schedule?tenant=...` | same as Gate 14 | Same as Gate 14 |
| Gate 29 (`29-edge-panel-mode-mutex.spec.ts:25-26`) | `/bridgeable-admin/runtime-editor/home?tenant=...` | After redirect: `/studio/live` (loses `/home`) | No — falls through to `*` → HomePage |

There are **two layered failures stacked here**. First failure: `redirectFromStandalone` (`studio-routes.ts:191-230`) only looks up the exact `pathname` (stripped of trailing slashes) in `STANDALONE_TO_STUDIO_PATH`. The `pathname` `/runtime-editor/dispatch/funeral-schedule` is not a key in the table (only `/runtime-editor` is), so the table lookup misses and the function falls through to `targetBase = "/studio"` (line 197 of studio-routes.ts) — the deep tail is dropped at redirect time. Second failure: even if the redirect preserved the tail (e.g., `/studio/live/wastewater/dispatch/funeral-schedule`), the nested-`<Routes>` mismatch described above means the tenant route still wouldn't render.

This is why follow-up #2 STOPPED: the deep-path redirect can be patched in `redirectFromStandalone` to preserve the tail, but the underlying router-topology bug means even a tail-preserving redirect renders HomePage. The architectural question — how does Studio internally dispatch the unconsumed tail to TenantRouteTree — is the load-bearing decision. Until that answer is locked, fixing the redirect is paving cowpaths.

Gate 14 + 22 are equivalent (`dispatch/funeral-schedule` mount). Gate 15 adds the Focus URL state on top, also gated on the tail mounting. Gate 29 needs `home` to mount inside the editor shell.

---

## Section 2: Option enumeration

### Option A — Add nested `<Routes>` for Live mode only

**Implementation sketch**: In StudioShell, replace the current direct-dispatch render block (`StudioShell.tsx:157-209`) for the Live mode branch with an explicit nested `<Routes>` declaration. Edit-mode and overview dispatch stays direct-dispatch as today.

```tsx
// Inside StudioShell — replace the existing dispatch
return (
  <StudioRailContext.Provider value={{ railExpanded, inStudioContext: true }}>
    <div className="..." data-studio-shell="true" /* ... */>
      <StudioTopBar /* ... */ />
      <div className="flex">
        <StudioRail /* ... */ />
        <main /* ... */>
          <Suspense fallback={...}>
            <Routes>
              {/* Live mode — declared so the `:vertical/*` segments are
                  consumed by an ancestor <Route>, leaving the deep
                  tail (e.g. `dispatch/funeral-schedule`) as the
                  splat content TenantRouteTree's <Routes> sees. */}
              <Route
                path="live/:vertical/*"
                element={<StudioLiveModeWrap />}
              />
              <Route path="live" element={<StudioLiveModeWrap />} />

              {/* Edit-mode + overview — fall through to the existing
                  direct-dispatch by mounting a wrapper component that
                  calls parseStudioPath and renders the matching
                  editor / overview. */}
              <Route path="*" element={<EditModeDispatcher parsed={parsed} />} />
            </Routes>
          </Suspense>
        </main>
      </div>
    </div>
  </StudioRailContext.Provider>
)
```

`StudioLiveModeWrap` would drop the `vertical` prop and read it from `useParams()` instead. RuntimeEditorShell stays unchanged. TenantRouteTree stays unchanged. The mechanism that makes it work: the `<Route path="live/:vertical/*">` declaration consumes `live/<vertical>` from the unconsumed remainder, leaving exactly the deep tenant tail (`dispatch/funeral-schedule`) for TenantRouteTree's `<Routes>` to match against.

**Cited files + diff shape**:
- `StudioShell.tsx`: ~30-40 LOC of render-block refactor. The `parseStudioPath` call stays but moves into the `EditModeDispatcher` helper for the Edit + overview path; the Live mode branches become declarative routes.
- `StudioLiveModeWrap.tsx`: ~5-8 LOC. Replace prop with `useParams<{ vertical?: string }>()`.
- `studio-routes.ts::redirectFromStandalone`: still needs deep-path tail preservation (~15-25 LOC) so `/runtime-editor/dispatch/funeral-schedule` translates to `/studio/live/<lastVertical>/dispatch/funeral-schedule` (or `/studio/live/dispatch/funeral-schedule` if the vertical resolution isn't yet known — RuntimeEditorShell on mount post-impersonation can canonicalize URL via `<Navigate replace>`).
- No StudioRedirect changes beyond what `redirectFromStandalone` returns.

**Test impact**: Existing vitest StudioShell tests assert on direct-render shape (no nested `<Routes>` in test setup). The Live mode tests in `StudioShell.test.tsx` use `<MemoryRouter initialEntries={["/studio/live"]}>` with `<StudioShell />` as the only routed component — but StudioShell's outer mount is also a `<Route>` (see `BridgeableAdminApp.tsx:209`). The vitest tests already render StudioShell inside `<Routes><Route path="/studio/*" element={...} /></Routes>` (verifiable in `StudioShell.test.tsx`). Adding the inner Routes declaration means tests that asserted "URL `/studio/live/wastewater` mounts StudioLiveModeWrap" still pass because the nested `<Route path="live/:vertical/*">` matches at the inner level. **Estimated test churn: 0-3 test files**; the nested-Routes-mount pattern is closer to canonical react-router than the parseStudioPath-from-pathname pattern, so existing test setups are likely already compatible.

The 4 failing Playwright specs (14, 15, 22, 29) would be unblocked by this change combined with the redirect-tail-preservation fix.

**Cascading effects on Edit mode**: minimal. The `EditModeDispatcher` helper is a thin wrapper calling `parseStudioPath` once and rendering the matched editor / overview. Identical render output to today. Editor adaptation pass (Studio 1a-i.B) is untouched.

**Cascading effects on Studio admin pages** (`/studio/admin/*`): minimal. The Edit-mode dispatcher's `parseStudioPath` already handles `/studio/admin` (returns Platform overview today per `studio-routes.ts:424-427`). When real admin sub-pages land in a future arc they'd register as additional nested routes inside the Edit-mode `<Routes>` if they need to consume tail segments — same pattern. Conventional.

**Cascading effects on other Studio modes** (hypothetical future preview / scope-cascade-visualizer modes): if they also need tail consumption (e.g. a preview mode that mounts the tenant tree), they add their own nested `<Route path="<mode>/.../*">` declaration alongside `live`. Pattern repeats. **Pattern is forward-compatible.**

**Risk**: Two non-obvious gotchas. (1) `parseStudioPath` is also called from `redirectFromStandalone` and `toggleMode` (`studio-routes.ts:368-377`). Both depend on the pathname-parsing semantics, NOT on a `<Route>` having matched. So keeping `parseStudioPath` is fine — it's still useful as a pathname-classifier even when StudioShell internally dispatches via Routes. (2) The Edit-mode-dispatcher approach mounts the editor inside a `<Route path="*">`, which means `useParams()` inside the editors would return the splat segment, not vertical / editor params. Editors don't currently consume `useParams()` from the Studio level, so this should be moot; verify before build.

**LOC estimate (R-7-α applied)**:
- Midpoint: ~80-100 LOC core change + ~30-40 LOC for redirect-tail-preservation + ~30-60 LOC for tests = **~140-200 LOC** total.
- Worst case (+30-130% above upper bound per R-7-α): **~260-460 LOC**.

Comfortably within the >50 LOC threshold that triggered the STOP in follow-up #2 (the threshold was a flag, not a ceiling). Well within the sub-agent execution ceiling.

### Option B — Refactor Studio dispatch to nested Routes throughout

**Implementation sketch**: Replace `parseStudioPath`-based direct dispatch with declarative `<Route>` elements for every Studio URL shape. The StudioShell becomes the layout-only component; dispatch happens via `<Outlet />` and child `<Route>` matching.

```tsx
// In BridgeableAdminApp — flatten the StudioShell mount
<Route path="/studio" element={<StudioShellLayout />}>
  <Route index element={<StudioOverviewPage />} />
  <Route path="live" element={<StudioLiveModeWrap />} />
  <Route path="live/:vertical/*" element={<StudioLiveModeWrap />} />
  <Route path=":maybeVerticalOrEditor" element={<StudioEitherVerticalOrEditor />} />
  <Route path=":vertical/:editor" element={<StudioVerticalEditor />} />
  <Route path="admin/*" element={<StudioAdminRoutes />} />
</Route>
```

Or alternatively keep StudioShell as the outer mount and put a `<Routes>` block at its top:

```tsx
return (
  <StudioRailContext.Provider value={...}>
    <div ...>
      <StudioTopBar /> <StudioRail /> 
      <main>
        <Routes>
          <Route index element={<StudioOverviewPage activeVertical={null} />} />
          <Route path="live" element={<StudioLiveModeWrap vertical={null} />} />
          <Route path="live/:vertical/*" element={<StudioLiveModeWrap />} />
          <Route path=":vertical">
            <Route index element={<StudioOverviewPage />} />
            <Route path=":editor" element={<StudioEditorDispatch />} />
          </Route>
          {STUDIO_EDITOR_KEYS.map((key) => (
            <Route key={key} path={key} element={<EDITOR_PAGES[key] />} />
          ))}
          <Route path="admin/*" element={<StudioAdminPlaceholder />} />
        </Routes>
      </main>
    </div>
  </StudioRailContext.Provider>
)
```

The ambiguity between `:vertical` (a vertical slug) and an editor key (`themes`, `focuses`, etc.) is resolved by declaring the editor keys as their own explicit `<Route path="themes">`, `<Route path="focuses">`, etc. — React Router scores explicit static segments higher than dynamic params, so `/studio/themes` matches the explicit `themes` route and `/studio/manufacturing` matches the `:vertical` route.

**Cited files + diff shape**:
- `StudioShell.tsx`: ~80-120 LOC refactor. Most of the body becomes the `<Routes>` block + small per-editor render adapters that read `useParams()` for vertical.
- `StudioRail.tsx`, `StudioTopBar.tsx`: probably unchanged — they take props from the shell.
- `StudioLiveModeWrap.tsx`: prop API change to read from `useParams` instead of receiving prop.
- All editor components (`ThemeEditorPage`, `FocusEditorPage`, ...) — if they need vertical scope, they read `useParams` now. **At least 9 editor files touched** for this. Estimated +5-15 LOC each.
- `studio-routes.ts::parseStudioPath` becomes obsolete inside StudioShell but still used by `redirectFromStandalone` and `toggleMode`. Stays.
- `redirectFromStandalone` still needs deep-path tail preservation (~15-25 LOC) for the runtime-editor leg.
- Internal navigation calls — anything constructing URLs would already use `studioPath` / `studioLivePath` (canonical). Should be unaffected.

**Test impact**: Larger. Every test that asserts on StudioShell rendering a specific child for a specific URL needs to reconcile with the route declarations. Vitest tests using `<MemoryRouter initialEntries={["/studio/themes"]}>` would still work, BUT the test setup needs to be inside the outer `/studio/*` `<Route>` ancestor — currently most tests mount StudioShell directly without that ancestor route. Estimated **3-7 test files need adjustments**, mostly mechanical (wrap test render in `<Routes><Route path="/studio/*" element={...} /></Routes>`).

The 4 failing Playwright specs would be unblocked, identical mechanism to Option A — the `live/:vertical/*` route consumes the prefix, tail flows through.

**Cascading effects on Edit mode**: nontrivial. Every editor now mounts from a `<Route element={...}>` rather than a direct render. Adapters needed where editors expect vertical / editor props (currently passed from StudioShell). Either lift to `useParams` (touches all 9 editors) or wrap each in a `StudioEditorMountAdapter` (single new component, but every editor route uses it).

**Cascading effects on Studio admin pages**: a real benefit. Admin sub-pages declare their own nested `<Route>` children, no `parseStudioPath` extension required.

**Cascading effects on other Studio modes**: the canonical pattern. Each future mode (preview, scope-cascade-visualizer) gets its own `<Route path="<mode>/...">` declaration. Fully idiomatic.

**Risk**: (1) The largest blast radius — touching 9+ editor mounts when only 4 tests need fixing is "Big Refactor To Fix Small Bug" energy. (2) The route-precedence rules between explicit segments (`themes`) and dynamic params (`:vertical`) are subtle; tests need to verify e.g. `/studio/wastewater/themes` matches `:vertical/:editor` not `themes` even though `themes` is more specific (it should be fine — react-router scores prefix-match correctly — but warrants explicit tests). (3) The editor adaptation pass (Studio 1a-i.B) already shipped (`523c1c2`, `0d4d9a8`) under the assumption that editors are direct-render children of StudioShell. Refactoring to declarative routes touches the same files the adaptation pass touched, risking churn-on-churn collisions.

**LOC estimate (R-7-α applied)**:
- Midpoint: ~200-400 LOC core change + editor adapter updates × 9 editors + redirect fix + tests = **~500-700 LOC**.
- Worst case: **~900-1,400 LOC**.

Higher than Option A by ~3-5×. Approaches the "consider splitting" zone for a single sub-arc.

### Option C — Add a basename prop to TenantRouteTree

**Implementation sketch**: Teach TenantRouteTree to strip a prefix from `location.pathname` before its inner `<Routes>` runs. React Router exposes `<Routes basename="...">`? — no, basename is a `<Router>`-level prop, not a `<Routes>`-level prop. Workaround approaches:

(a) Wrap the inner tenant route tree in a sub-`<Router>` (BrowserRouter or MemoryRouter with `basename`). Doesn't compose — you'd have two BrowserRouters nested, which react-router prohibits.

(b) Use `<Routes basename>`? Not supported in v6+.

(c) Manually adjust `location.pathname` via a wrapping component that reads `useLocation`, computes the trimmed pathname, and supplies it via... what mechanism? `<Routes location={...}>` exists — `<Routes>` accepts a `location` prop. A wrapper can synthesize a stripped-pathname `Location` object and pass it down.

```tsx
// TenantRouteTree.tsx — add optional basename prop
export function TenantRouteTree({ basename = "" }: { basename?: string }) {
  const location = useLocation()
  const trimmedPathname = basename && location.pathname.startsWith(basename)
    ? location.pathname.slice(basename.length) || "/"
    : location.pathname
  const trimmedLocation = useMemo(
    () => ({ ...location, pathname: trimmedPathname }),
    [location, trimmedPathname],
  )
  return (
    <Routes location={trimmedLocation}>
      {renderTenantSlugRoutes({ excludeRootRedirect: true })}
    </Routes>
  )
}
```

Then RuntimeEditorShell (called from StudioLiveModeWrap with `studioContext`) passes down a basename. The basename needs to be computed: from URL `/bridgeable-admin/studio/live/wastewater/dispatch/funeral-schedule`, the basename for TenantRouteTree is `/bridgeable-admin/studio/live/wastewater`. The Studio shell knows this prefix; needs to pass it through StudioLiveModeWrap → RuntimeEditorShell → ShellWithTenantContext → TenantRouteTree.

**Cited files + diff shape**:
- `TenantRouteTree.tsx`: ~20-30 LOC (add prop, synthesize trimmed location, pass to `<Routes location={...}>`).
- `RuntimeEditorShell.tsx`: ~5-10 LOC (accept optional `routeTreeBasename` prop, pass to TenantRouteTree mount at line 211).
- `StudioLiveModeWrap.tsx`: ~10-15 LOC (compute basename from `useLocation()` — strip out everything before and through `/live/<vertical>`, pass to RuntimeEditorShell).
- `studio-routes.ts::redirectFromStandalone`: still needs deep-path tail preservation (~15-25 LOC).
- Tests: a few existing TenantRouteTree tests need basename pass-through verification. `RuntimeEditorShell` tests need basename-null and basename-set parameterization. Estimated 3-5 test files.

The 4 failing Playwright specs would be unblocked.

**Cascading effects on Edit mode**: zero. The basename mechanism only fires when TenantRouteTree is the consumer — Edit mode doesn't mount TenantRouteTree.

**Cascading effects on Studio admin pages**: zero. Same reason.

**Cascading effects on other Studio modes**: any future mode that mounts TenantRouteTree (preview-mode style) reuses the basename mechanism. Other modes that don't mount tenant routes are unaffected.

**Cascading effects on standalone runtime-editor consumers**: zero. Pre-Studio's `RuntimeHostTestPage` (still mounted at `/_runtime-host-test/*` per `BridgeableAdminApp.tsx:169,174`) doesn't pass basename → behavior unchanged.

**Risk**: (1) `<Routes location={trimmedLocation}>` is a less-traveled react-router API. The docs say it works (used for animation transitions and similar); verify it actually does relative-path matching against the supplied location vs. the actual URL. There's no obvious reason it shouldn't, but it's an unusual production usage. (2) The basename must be kept in sync with the Studio URL shape — if Studio later adds another path segment (e.g. `/studio/v2/live/<vertical>/...`), the basename computation in StudioLiveModeWrap needs updating. Two sources of truth (Studio URL spec and basename computation). (3) The trimmed `Location` object propagates through `useLocation` for descendants of `TenantRouteTree`? `useLocation` reads from `Router`'s context — which is the OUTER router. Components inside TenantRouteTree calling `useLocation` would see the un-trimmed pathname. That's the desired behavior for cross-tree navigation (we want `useNavigate("/financials")` to navigate to `/bridgeable-admin/studio/live/wastewater/financials` — verify this works as expected). Net: subtle but probably fine; needs explicit test coverage.

**LOC estimate (R-7-α applied)**:
- Midpoint: ~60-90 LOC core + redirect fix + tests = **~120-180 LOC**.
- Worst case: **~250-380 LOC**.

Smallest blast radius of the three. ~70% of Option A.

### Option D — Anything else

One additional shape surfaced during investigation: **change `parseStudioPath` to surface a "tenantTail" remainder, and have StudioLiveModeWrap explicitly tell RuntimeEditorShell where to navigate post-mount via `useNavigate(tenantTail, { replace: true })`**. The mount sequence would be: URL `/studio/live/wastewater/dispatch/funeral-schedule` → Studio dispatches Live mode wrap (no tail awareness) → wrap mounts RuntimeEditorShell → ShellWithTenantContext mounts TenantProviders + TenantRouteTree → on first render of TenantRouteTree, an effect calls `useNavigate("/dispatch/funeral-schedule")` to jump the inner router state.

**Rejected because**:
- Forces a render-then-redirect double-render pattern (HomePage flashes briefly).
- Requires storing the tenant tail outside React Router's URL state, in a side channel (prop or context).
- Doesn't compose cleanly with `useParams` or back-button semantics.
- Worst of all worlds: complicates the data flow and still requires Option A or C's basename trick to make `useLocation` consistent.

Not recommended. Flagged for completeness.

---

## Section 3: Forward-compatibility analysis

### Future Studio modes needing tail consumption

The DECISIONS.md 2026-05-13 entry on Studio shell decomposition explicitly leaves room for additional modes beyond Edit and Live. Plausible future modes:

- **Preview mode**: read-only render of a tenant runtime for QA / regression-checking. Would mount TenantRouteTree under impersonation, same as Live mode. NEEDS tail consumption.
- **Scope-cascade visualizer**: per Arc 4d substrate-asymmetry-is-canon, surfaces the resolution chain for a specific entity on a specific page. Would mount the tenant page being inspected. NEEDS tail consumption.
- **Diff mode**: hypothetical — view-mode that shows a tenant page with changed-tokens highlighted. Same need.

| Option | Handling new tail-consuming mode |
|---|---|
| A | Add `<Route path="<mode>/.../*">` declaration alongside `live`. Trivial. |
| B | Same as A but in the StudioShell-as-layout pattern. Trivial. |
| C | Each mode that mounts TenantRouteTree computes its own basename and passes it through. ~10 LOC per mode. Trivial. |

All three options accommodate future modes; Options A + B do so through declarative route declarations (canonical); Option C does so through imperative basename computation per mode (slightly less idiomatic but works).

### Interaction with Spaces substrate arc

Per DECISIONS.md 2026-05-13, Spaces substrate is next-on-queue after Studio shell. Spaces will mount inside Studio as a section ("Spaces" in the rail). The Spaces section will have its own internal navigation — e.g. `/studio/spaces`, `/studio/spaces/templates/<id>`, `/studio/<vertical>/spaces`, `/studio/<vertical>/spaces/templates/<id>`. Spaces is an editor-shaped section (lives in the rail, ships an authoring surface), NOT a mode (doesn't replace the shell's render shape like Live does). So:

| Option | Spaces interaction |
|---|---|
| A | Spaces declared as a new editor key in `STUDIO_EDITOR_KEYS` + `EDITOR_PAGES`. Editor renders inside the current direct-dispatch block. Spaces' internal navigation handles via `parseStudioPath` extension or via a nested `<Routes>` inside the Spaces editor itself. Pattern symmetric with existing editors. |
| B | Spaces declared as a new `<Route path="spaces">` + `<Route path=":vertical/spaces">` declaration. Spaces' own sub-routes nest as children. Pattern symmetric with existing editors as declarative routes. |
| C | Spaces interaction unaffected (Spaces doesn't mount TenantRouteTree). Spaces' sub-routes handled however the existing editors handle theirs (currently via internal-state, not router). |

No option meaningfully constrains Spaces. The Spaces arc will solve its own internal-navigation question regardless of which option lands here.

### Interaction with Studio 1a-ii (overview inventory)

Studio 1a-ii ships the inventory service backing the overview surface — counts + recent-edits. No URL surface changes; the existing `/studio` and `/studio/<vertical>` overviews already render via `StudioOverviewPage` (a direct-rendered child of StudioShell). 1a-ii swaps the placeholder content for live data fetched from a new backend endpoint. Pure data-layer + UI-content change. **No interaction with any of the three options.** Confirmed by reading StudioOverviewPage's surface shape per existing arc.

### Does any option foreclose future architectural choices?

Option A: keeps StudioShell's parseStudioPath-driven Edit-mode dispatch as the canonical pattern, while introducing nested routes for mode branches. This is a hybrid: parseStudioPath continues to be useful for shells that want to render-by-classification rather than render-by-route. If future work migrates Edit mode dispatch to nested routes too (becoming Option B), the migration is incremental — done one mode at a time. **Does not foreclose Option B as a future migration.**

Option B: commits Studio fully to the declarative-routes pattern. parseStudioPath becomes a vestigial pathname classifier used only by `redirectFromStandalone` + `toggleMode`. Future arcs that want to add modes do so by adding routes (canonical). **Slight foreclosure: a future arc that wants to add a "mode that doesn't mount as a route" (e.g. a transient overlay mode that doesn't change URL) would feel like swimming upstream.** But that's a probably-undesirable mode anyway — Studio's contract is URL-canonical.

Option C: keeps the parseStudioPath-driven dispatch entirely and adds a "manually consume the tail" mechanism. Pattern is less canonical, more imperative. If Option B is ever revisited, the basename mechanism becomes dead code. **No foreclosure**, but creates a small amount of stylistic debt — future readers see a less-idiomatic pattern and either learn it or refactor it away.

---

## Section 4: Recommendation

**Recommendation: Option A — Add nested Routes for Live mode only.**

### Justification against the three constraints

**(a) Closes Gates 14, 15, 22, 29 with minimum blast radius.** Option A's mechanism — declare `<Route path="live/:vertical/*">` so the prefix is consumed by an ancestor `<Route>`, leaving TenantRouteTree's nested `<Routes>` to match against the canonical deep tail — is the most direct fix that aligns with how React Router intends nested-Routes consumption to work. ~140-200 LOC midpoint vs. Option B's ~500-700 and Option C's ~120-180. (Option C is slightly smaller but at the cost of a less-canonical pattern.)

**(b) Preserves Studio's current internal dispatch model where it works.** Edit-mode dispatch via parseStudioPath continues to function — the mental model "Studio shell looks at the URL pathname and renders one of N children based on shape" stays correct for the routes that don't need tail consumption (overview + editor mounts + admin). Only Live mode (which has the tail-consumption requirement) gains the additional layer of declarative routing. The mixed model is **defensible** — Edit and Live have meaningfully different shell-shape requirements (Edit dispatches by URL classification, Live dispatches by route segment matching). Mixing reflects that.

**(c) Sets right precedent for future modes.** Future modes that need tail consumption (preview, scope-cascade-visualizer, diff-mode) add their own `<Route path="<mode>/.../*">` declarations alongside `live`. The pattern is local, declarative, and idiomatic. Future modes that do NOT need tail consumption (overlay modes, transient modes) stay in the parseStudioPath-driven block — same as Edit mode is today. Studio's shell pattern accommodates both shapes naturally.

Option B (full refactor) is the "more idiomatic" long-term answer but would touch ~9 editor files for no functional benefit to those editors. The cost-to-value ratio in the current arc is unfavorable. If a future arc has compelling reasons to migrate Edit mode dispatch to declarative routes (e.g. admin sub-pages or Spaces sub-routes start requiring tail consumption), the migration is incremental — Option A doesn't block it.

Option C (basename mechanism on TenantRouteTree) is the smallest-LOC fix but trades a small line count for a less-traveled API (`<Routes location={trimmedLocation}>`) plus an imperative basename computation in StudioLiveModeWrap. Future Studio modes that mount tenant routes each compute their own basename — fine for one mode, increasingly clunky for many. Option A scales better via declarative pattern.

### Estimated build prompt scope under Option A

**Single sub-arc.** Estimated build size: ~140-200 LOC midpoint, ~260-460 LOC worst case (R-7-α). Comfortably within sub-agent execution ceiling.

Build pieces (sequenced for review coherence):
1. Refactor `StudioShell.tsx` render block to add nested `<Routes>` declaration for Live mode + an `EditModeDispatcher` wrapper for the existing direct-dispatch path. Move the parseStudioPath call to the dispatcher. (~80-100 LOC)
2. Update `StudioLiveModeWrap.tsx` to read `vertical` from `useParams()` rather than receiving as prop. (~5-10 LOC)
3. Extend `redirectFromStandalone` in `studio-routes.ts` to preserve deep tails for `/runtime-editor/<tail>` → `/studio/live/<lastVertical?>/<tail>` translations. (~20-30 LOC)
4. Update or add vitest coverage in `StudioShell.test.tsx` + `studio-routes.test.ts`: assert nested-Route dispatch for Live mode URLs, assert deep-tail preservation, assert tenant route mount under Studio chrome. (~30-60 LOC)

Gates 14, 15, 22, 29 should pass without spec edits once the change deploys to staging and Playwright runs against it. Gate 14 + 22 verify `dispatch/funeral-schedule` mounts. Gate 15 verifies the same plus URL-driven Focus open. Gate 29 verifies `home` mounts.

### Open questions needing chat-side discussion before drafting the build prompt

1. **Deep-path redirect — last-vertical handling.** When `redirectFromStandalone` translates `/runtime-editor/dispatch/funeral-schedule` (no vertical context in the source URL), what target should it produce? Three plausible answers:
   - `/studio/live/dispatch/funeral-schedule` (no vertical; tenant picker on first mount selects vertical, then RuntimeEditorShell canonicalizes the URL to insert `<vertical>` between `live/` and `dispatch/`).
   - `/studio/live/<readLastVertical()>/dispatch/funeral-schedule` (using localStorage's last-vertical if available; falling back to no-vertical otherwise).
   - `/studio/live?dest=/dispatch/funeral-schedule` (encode destination as a query param to defer the canonicalization).

   Recommendation: the second (last-vertical-with-fallback) — same shape as the existing redirect helper's `lastVertical` parameter. But Option A's `<Route path="live/:vertical/*">` requires a vertical in the path, so the no-vertical fallback case needs additional handling: either a sibling `<Route path="live/*">` declaration (different render — no `:vertical` param) OR a synthesized intermediate URL `/studio/live` that the picker post-flow then upgrades to `/studio/live/<resolved-vertical>/<dest>` once impersonation completes. **Needs design call.**

2. **Tenant URL canonicalization on impersonation handshake.** When the operator enters Studio Live via `/studio/live` (no vertical, no tenant) and selects a tenant whose `Company.vertical=manufacturing`, RuntimeEditorShell's `TenantUserPicker` calls `navigate(...)` to install impersonation params. Today that lands at `/studio/live/manufacturing?tenant=...&user=...` (no tenant-page path). If the operator had been deep-linked to `/studio/live/dispatch/funeral-schedule` (the recommendation from question 1), the picker's post-handshake navigate needs to preserve the destination tail. **Needs clarification of the picker's navigation contract under Option A.**

3. **Vitest tests for the nested-Routes pattern.** A few existing tests render StudioShell without an ancestor `<Route path="/studio/*">` — they use `<MemoryRouter initialEntries={["/studio/themes"]}>` directly. Under Option A, the nested `<Routes>` inside StudioShell needs to see the URL pathname `/studio/themes` correctly. **Verify before build that the inner `<Routes>` matches against the full pathname (not a parent-consumed remainder) when no ancestor `<Route>` has consumed segments.** If it doesn't, tests need wrapping in a `<Routes><Route path="/studio/*" element={...} /></Routes>` outer to simulate BridgeableAdminApp's mount. Add a single test-helper if widespread.

---

## Section 5: Out-of-scope items surfaced (track, don't address)

- **R-1.6.9 `excludeRootRedirect` interaction**: TenantRouteTree's `excludeRootRedirect: true` (`TenantRouteTree.tsx:49-53`, `App.tsx:1904-1914`) is the mechanism that prevents an empty unconsumed tail from triggering `<RootRedirect>`'s `<Navigate to="/home" replace />` which would absolute-navigate out of the runtime-editor parent route. Under Option A, the unconsumed tail under TenantRouteTree is the deep tenant path (e.g. `dispatch/funeral-schedule`) — not empty — so `<RootRedirect>` wouldn't have fired anyway. The mechanism remains useful for the case where the tail IS empty (operator at `/studio/live/<vertical>` with no deep page). **No changes required to TenantRouteTree or `excludeRootRedirect`.** Flag for verification, no action.

- **Cross-realm boundary at `dual-token-client.ts`**: Studio Live mode uses the impersonation token (tenant realm) for tenant content fetches and the platform-admin token (`adminApi`) for inspector writes. None of the three options touch that boundary. Routing topology change does not affect realm boundaries. **No impact.**

- **`StudioRedirect` simplification opportunity**: Once Option A's deep-path tail preservation lands in `redirectFromStandalone`, the StudioRedirect component becomes adequate as-is for both legacy `/runtime-editor` and `/runtime-editor/<tail>` URLs. Some redundant `<Route>` declarations in BridgeableAdminApp may become deletable (`BridgeableAdminApp.tsx:184-199` registers `/runtime-editor` + `/runtime-editor/*` separately; both point to StudioRedirect; pre-Option A both were needed because the deep-path case was broken — under Option A, the `:tail` form alone would suffice). Pure hygiene; not blocking.

- **Future migration to Option B**: leaving as a strategic option, not a current arc. If a future arc surfaces a strong driver (Spaces sub-routes wanting declarative dispatch, admin sub-pages wanting URL-driven mount, etc.), Option A's hybrid model permits incremental migration. Flag for future arc planning.

- **Studio admin sub-pages**: `/studio/admin/*` is reserved per `RESERVED_FIRST_SEGMENTS` (`studio-routes.ts:43-48`) and currently parses to Platform overview (`studio-routes.ts:424-427`). When real admin sub-pages land, they'll need a dispatch mechanism. Under Option A, the natural pattern is to add `<Route path="admin/*">` to the StudioShell `<Routes>` block. Flag for future arc.

- **Studio overview surface dispatch by vertical**: `StudioOverviewPage` receives `activeVertical` as a prop today (`StudioShell.tsx:161`). Under Option A's introduction of nested routes for Live mode, the overview still renders direct from StudioShell's render block — its `activeVertical` prop continues to be derived from `parseStudioPath`. **No behavioral change.**

- **`parseStudioPath` as a pathname classifier**: continues to be used by `redirectFromStandalone` (transient URLs from the old `/visual-editor` mount paths), `toggleMode` (Edit ↔ Live URL translation), and `isOverviewRoute` (rail-default-by-route classifier, `studio-routes.ts:272-285`). Under Option A, these callers continue to work — `parseStudioPath` is a pure-function classifier that doesn't depend on which routes have matched. Its semantics are preserved.

---

[end findings — read-only investigation; no validation gates apply]
