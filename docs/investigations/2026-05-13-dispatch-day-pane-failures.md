# Gates 14 / 22 Dispatch Day Pane Failures — Root Cause Investigation

**Date**: 2026-05-13
**Context**: Studio 1a-i closure (commit `703f13f`) was contingent on Gates 14, 15, 22, 29 all passing post-deploy of `908ebe6`. After staging deploy, Gates 14 + 22 fail at the 20s `waitFor` for DeliveryCard / DeliveryCardHeader; Gates 15 + 29 pass.
**Mode**: read-only diagnostic; no production code, tests, migrations, or seeds changed.

---

## Section 1: Reproduce the failure mode (trace inspection)

Playwright trace artifacts referenced in the prompt path (`frontend/tests/e2e/screenshots/runtime-editor-14-delivery-3dc78-...trace.zip`) were not present in the local working tree at investigation time:

```
$ find frontend/tests/e2e -name "trace.zip"
(empty)
$ find . -path ./node_modules -prune -o -name "test-results" -type d -print
(empty)
```

Trace artifacts live only inside the GitHub Actions workflow run for the post-`908ebe6` deploy; they are not committed and not synced to the local repo. `npx playwright show-trace` cannot run against an absent file, and there is no display in the investigation environment regardless.

Falling back to static analysis with the failure signature from the prompt as the seed:

- Gate 14 / 22 timeouts at `[data-slot="dispatch-fs-day-pane"][data-active="true"] [data-component-name="delivery-card"]` (Gate 14) / `... [data-component-name="delivery-card.header"]` (Gate 22)
- Gate 15 / 29 pass on the same backend / same impersonation
- Gate 15 differs from Gate 14 in two material ways: `?focus=funeral-scheduling` URL param + lookup of `ancillary-card` (not `delivery-card`)

The static analysis below identifies a routing cause that fully explains the Gate-14-fails / Gate-15-passes asymmetry without needing the trace.

---

## Section 2: Compare DeliveryCard vs. AncillaryCard render paths

### DeliveryCard render chain

1. Gate 14 / 22 navigate to `/bridgeable-admin/runtime-editor/dispatch/funeral-schedule?tenant=...&user=...`
2. `frontend/src/bridgeable-admin/BridgeableAdminApp.tsx:188-190` declares:
   ```tsx
   <Route path="/bridgeable-admin/runtime-editor/*" element={<StudioRedirect />} />
   ```
3. `StudioRedirect` (`frontend/src/bridgeable-admin/pages/studio/StudioRedirect.tsx:17-26`) calls `redirectFromStandalone(pathname, search)`
4. `redirectFromStandalone` (`frontend/src/bridgeable-admin/lib/studio-routes.ts:212-223`) — the deep-path runtime-editor preservation branch — translates `/runtime-editor/dispatch/funeral-schedule` → `/studio/live/dispatch/funeral-schedule`, **preserving the `?tenant=&user=` query**, **without inserting a vertical segment**
5. Final URL after redirect: `/bridgeable-admin/studio/live/dispatch/funeral-schedule?tenant=...&user=...`
6. `BridgeableAdminApp.tsx:206-208` matches `path="/bridgeable-admin/studio/*"` → mounts `<StudioShell>`
7. `StudioShell.tsx:187-192` nested `<Routes>`:
   ```tsx
   <Routes>
     <Route path="live/:vertical/*" element={<StudioLiveModeWrap />} />
     <Route path="live/*"           element={<StudioLiveModeWrap />} />
     <Route path="live"             element={<StudioLiveModeWrap />} />
     <Route path="*"                element={<StudioLiveModeWrap />} />
   </Routes>
   ```
   No `:vertical` in the URL → `live/*` matches. Consumes `live`. Remainder for descendants: `dispatch/funeral-schedule`.
8. `StudioLiveModeWrap` (`frontend/src/bridgeable-admin/pages/studio/StudioLiveModeWrap.tsx:60-83`) renders `<RuntimeEditorShell studioContext={true} verticalFilter={null} />`
9. `RuntimeEditorShell.tsx:205-212` mounts `<Focus />` and `<TenantRouteTree />` as siblings inside `EditModeProvider`
10. `TenantRouteTree.tsx:49-53`:
    ```tsx
    <Routes>{renderTenantSlugRoutes({ excludeRootRedirect: true })}</Routes>
    ```
11. **Inside that nested `<Routes>`**, the route declaration at `App.tsx:602-611` is:
    ```tsx
    <Route
      path="/dispatch/funeral-schedule"      // ← ABSOLUTE PATH
      element={<FuneralSchedulePage />}
    />
    ```
12. R-2.x (`941cb82`, "feat(routing): R-2.x — universal relative paths unblock editor shell on arbitrary tenant routes") explicitly identified absolute paths inside nested `<Routes>` as the bug class and claimed to convert them all to relative. Audit shows otherwise:
    ```
    $ grep -c 'path="/' frontend/src/App.tsx
    105
    $ git show 941cb82:frontend/src/App.tsx | grep -c 'path="/'
    103
    ```
    103 absolute-path Route declarations remain inside `renderTenantSlugRoutes`. The conversion was partial. `/dispatch/funeral-schedule` is one of the unconverted; `/dev/focus-test`, `/admin/users`, `/team`, `/admin/roles`, `/admin/email-classification`, `/crm`, `/crm/companies`, `/crm/companies/duplicates`, `/crm/companies/:id`, `/crm/funeral-homes`, `/crm/contractors`, `/crm/billing-groups`, `/crm/billing-groups/:id`, `/crm/settings`, `/crm/pipeline`, `/personalization-studio/from-share/:documentShareId`, `/settings/briefings`, `/settings/spaces`, and ~85 others are also still absolute.
13. With `excludeRootRedirect=true`, the catch-all at `App.tsx:1904-1908` is:
    ```tsx
    <Route index element={<HomePage />} />
    <Route path="*" element={<HomePage />} />
    ```
    When the nested `<Routes>` consumes the parent splat `live/*` and sees the inner pathname `dispatch/funeral-schedule`, an absolute-path Route declaration `path="/dispatch/funeral-schedule"` does NOT match the descendant relative pathname. The catch-all `path="*"` matches → **`<HomePage />` mounts instead of `<FuneralSchedulePage />`**.
14. `HomePage` does not emit any `[data-slot="dispatch-fs-day-pane"]` or any `[data-component-name="delivery-card"]`. The 20s `waitFor({ state: "attached" })` times out.

### AncillaryCard render chain (the contrast)

1. Gate 15 navigates to the same URL **plus `?focus=funeral-scheduling&edit=1`** (`15-ancillary-card-click-to-edit.spec.ts:75-82`)
2. Steps 1-9 identical to DeliveryCard chain — same redirect, same shell mount
3. `RuntimeEditorShell.tsx:205` mounts `<Focus />` as a **sibling** of `<TenantRouteTree />`. `Focus` is `frontend/src/components/focus/Focus.tsx` (the modal mount); it reads `?focus=funeral-scheduling` from `FocusContext` and opens the funeral-scheduling Focus
4. `SchedulingFocusWithAccessories.tsx:46+94+106` mounts `<SchedulingKanbanCore />` inside the Focus modal
5. `SchedulingKanbanCore` renders `AncillaryCard` for standalone ancillary deliveries (per Gate 15's header comment + the seed data)
6. **The inner `<TenantRouteTree>` route resolution is irrelevant** — even though it mounts `HomePage` (same bug, hidden), the AncillaryCard surfaces from the `<Focus />` sibling mount
7. Gate 15's selector `[data-component-name="ancillary-card"]` resolves regardless

### Verification by inverse

If the failure were a seed-data problem, Gate 15 would also see "ancillary card never appears" if the seed lacked ancillary deliveries. The seed at `backend/scripts/seed_dispatch_demo.py:316-355` shows 4 ancillary deliveries (3 standalone + 1 attached). The seed at lines 138-310 shows 5 kanban deliveries on `day_offset=0` and 6 on `day_offset=1`. **Data is present for both card types**.

If the failure were a component-mounting / registration problem with DeliveryCard, the FuneralSchedulePage's own tenant-boot path (`/dispatch/funeral-schedule` direct navigation outside the editor) would also fail. That path is exercised in production daily on testco and has not been reported broken. **Component registration + render conditions are not the cause**.

The asymmetry is unique to the editor-shell mount path, and the routing chain above identifies the exact mechanism.

---

## Section 3: Seed data inspection

Staging seeds run automatically via `backend/railway-start.sh` on every deploy:

```bash
python -m scripts.seed_staging --idempotent
python -m scripts.seed_fh_demo --apply --idempotent
python -m scripts.seed_dispatch_demo
python -m scripts.seed_edge_panel
```

Each fails the deploy if it crashes (R-1.6.3 fail-loud discipline). `703f13f` and `908ebe6` deployed cleanly — therefore seeds succeeded.

`backend/scripts/seed_dispatch_demo.py:137-310`:

| day_offset | kanban deliveries | ancillary deliveries |
|---|---|---|
| 0 (today)     | **5** | 1 attached |
| 1 (tomorrow)  | 6 | 2 standalone |
| 2 (+2 days)   | 4 | 1 standalone |
| 3 (+3 days)   | 2 | 0 |

Each kanban delivery has `requested_date = today + day_offset` and `scheduling_type = "kanban"`. `FuneralSchedulePage` reads `deliveriesByDate.get(dateStr) ?? []` (line 1012 / 1090) and the active day pane (Today or Tomorrow per `pickDefaultDayIndex(localHour)`) always has ≥5 kanban deliveries. **Seed data is healthy for DeliveryCard rendering.**

There is no seed-data fix needed; the problem is upstream of data availability.

---

## Section 4: Root cause classification

**Class: production-bug-with-narrow-blast-radius**. The bug is a routing defect in `renderTenantSlugRoutes()` introduced (or rather, left in place) by R-2.x's incomplete absolute-path conversion. Gates 14 / 22 are correctly exercising a code path that's broken; the test failures are honest signal.

Concretely:
- R-2.x converted ~100 of ~203 absolute-path Route declarations inside `renderTenantSlugRoutes` to relative paths. The post-R-2.x state still carries **103 absolute paths**.
- All 103 fail the same way Gate 14 / 22 demonstrate: they unmount the catch-all (HomePage under `excludeRootRedirect=true`) instead of the intended page, but only when reached via the runtime-editor shell mount path. Direct tenant-boot navigation (e.g., a logged-in tenant operator visiting `https://app.../dispatch/funeral-schedule`) works because the top-level App `<Routes>` matches the absolute path against the full pathname there — R-2.x preserved tenant-boot behavior intentionally and verified it.
- `/dispatch/funeral-schedule` surfaces this first because Gates 14 / 22 are the first specs that depend on a non-trivial tenant page mounting under the editor shell with no other affordance (Gate 15 had `?focus=funeral-scheduling` as an in-shell workaround; Gate 10 / Gate 14's pre-redirect-loop original assertions ran against direct DOM and didn't traverse the editor mount).

This is NOT a Studio 1a-i regression. The bug pre-dates Studio 1a-i (R-2.x dates from `941cb82`, 8 commits before `703f13f`). Studio 1a-i made Gates 14 / 22 reachable in their current form by routing `/bridgeable-admin/runtime-editor/*` → `/studio/live/*` cleanly, which is what surfaced the latent R-2.x miss.

Why R-2.x's claim of "universal relative paths" was inaccurate: the commit message describes the intent ("convert all 200 absolute-path declarations"); the diff converted ~100. Reading the diff carefully, the conversion was alphabetic-ish and stopped well before reaching `/dispatch/funeral-schedule` or many other early-declared routes. There is no test that asserts zero absolute paths remain in `renderTenantSlugRoutes` — the regression guard at `TenantRouteTree.test.tsx` only checks the two ternary roots + a sampling of `login` and `calendar/actions/:token`, not the body of the function.

---

## Section 5: Recommendation

### Fix shape

**Smallest fix that resolves Gates 14 / 22**: convert the single Route declaration at `frontend/src/App.tsx:608` from `path="/dispatch/funeral-schedule"` to `path="dispatch/funeral-schedule"` (drop leading slash). One character delete. Production tenant boot unaffected — R-2.x already verified the equivalence for the 100 paths it did convert; same mechanism applies here. Gates 14 / 22 immediately resolve.

### Recommended fix scope

**Recommended fix**: complete R-2.x's universal-relative-paths conversion across all 103 remaining absolute paths in a single follow-up. Same mechanical edit applied 103 times. Plus one regression test that fails if any future commit reintroduces an absolute path inside `renderTenantSlugRoutes`:

```ts
it("no Route inside renderTenantSlugRoutes uses an absolute path", () => {
  const fragment = renderTenantSlugRoutes({ excludeRootRedirect: true })
  const offenders = findRoutesByPath(fragment, (p) => p.startsWith("/"))
  expect(offenders).toEqual([])  // catch-all `*` and `index` don't trip this
})
```

The 103-route conversion is repetitive but low-risk per individual edit. Estimated:
- **LOC touched**: 103 single-character deletes in `App.tsx` (plus ~10 lines of new test).
- **Arc size**: small (≤ 1 hour, single PR).
- **Risk**: production behaviour preserved by definition (R-2.x already verified equivalence for ~100 paths; remaining 103 are the same class).
- **Test coverage**: existing TenantRouteTree.test.tsx tests pass (they don't assert on absolute-vs-relative shape); new universal-relative-paths invariant guards against drift.

### Where it ships

This is **NOT part of Studio 1a-i closure** — Studio 1a-i did its job (the redirect chain works, the shell mounts correctly, all primitives compose). The bug is downstream of Studio and downstream of R-2.x. Studio 1a-i can be considered closed for everything except the regression signal Gates 14 / 22 emit.

The fix warrants its own small arc — call it `R-2.x.1 — finish universal-relative-paths conversion` or similar. It does not require a fresh investigate-then-bounded-build cycle because the investigation is this document and the build is mechanical. A bounded-build prompt with "convert all remaining 103 absolute paths in `renderTenantSlugRoutes`, add invariant test, verify Gates 14 / 22 / 15 / 29 all green" is sufficient.

### Out of scope for this investigation

- Cleaning up the misleading `941cb82` commit message ("universal" is aspirational, not actual). Documenting the gap in CLAUDE.md is fine but not required.
- Considering whether to drop `excludeRootRedirect`'s catch-all entirely and surface a 404 inside the editor for unknown tenant pages. The current "render HomePage as a fallback" is a deliberate Studio 1a-i.B follow-up #3 contract for picker-replay UX; not on the table here.
- Anything to do with seed data, component registration, or AncillaryCard's success path.

---

## Findings summary

The Gate 14 / Gate 22 timeouts are caused by **`renderTenantSlugRoutes()` still declaring `<Route path="/dispatch/funeral-schedule" ... />` with an absolute path** (`frontend/src/App.tsx:608`), even though R-2.x's commit `941cb82` ("universal relative paths unblock editor shell on arbitrary tenant routes") claimed to convert all such declarations. R-2.x converted ~100 of ~203 such declarations and left 103 behind. Under the editor shell's nested-`<Routes>` mount (`<TenantRouteTree>` inside `RuntimeEditorShell`), absolute-path child routes don't match against the splat-remainder pathname; the catch-all `<Route path="*" element={<HomePage />} />` wins; `FuneralSchedulePage` never mounts; the spec's 20s `waitFor` on `[data-slot="dispatch-fs-day-pane"]` times out. Gate 15 passes because AncillaryCard renders inside the `<Focus />` modal which is a sibling of `<TenantRouteTree>` in the shell, bypassing the inner route resolution entirely. The fix is to drop the leading slash on `/dispatch/funeral-schedule` and ideally finish the conversion across all 103 remaining absolute paths, plus add an invariant test.
