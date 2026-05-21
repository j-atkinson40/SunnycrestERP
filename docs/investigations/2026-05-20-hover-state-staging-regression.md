# Investigation — Hover-state staging regression

**Date**: 2026-05-20
**HEAD at investigation start**: `a1c10c7` (fix arc — resize-handle UX refinements)
**Scope**: Finding 1 (hover-state) only. Finding 2 (UUID leak) not yet verified at staging; out of scope.
**Mode**: Read-only. No production code touched. No test files touched.

---

## 1. Context

Fix arc `a1c10c7` shipped two changes against locks in investigation `224cc06`:

- **Finding 1**: 8 resize handles render when widget is `isHovered || selected || isDragging` (refining the Q-10 selection-only lock).
- **Finding 2**: DragOverlay UUID leak class-fix via `resolveDragLabel` pure helper.

Fix arc's gate cascade passed cleanly — vitest 350/350 across 29 focus-builder test files, including five new hover-state tests at `FreeFormPlacedWidget.test.tsx:424-543` covering the full truth table (hovered+not-selected → handles, selected+not-hovered → handles, both → handles, neither → no handles, hover-out preserves handles when selected, hover-out hides handles when not selected, touch fallback via selection-only).

After Railway deploy to staging, operator verification surfaced a regression on Finding 1 only:

> *"They don't appear upon hover."*

Selection still works (click → handles appear, per the test fixture). Finding 2 not yet operator-verified.

This investigation answers: **why did the JSDOM test suite pass while the real-browser hover failed?**

---

## 2. The diagnostic question

The five hover-state tests assert what the code's `(isHovered || selected || isDragging)` branch is supposed to render. They DID assert that, and they passed (re-verified during this investigation: `npx vitest run FreeFormPlacedWidget.test.tsx -t "hover-state refinement"` → 5 passed in 1.37s).

The tests fire `fireEvent.pointerEnter(draggable)` synthetically against the `focus-builder-freeform-placed-widget-draggable` testid wrapper at `FreeFormPlacedWidget.test.tsx:450`, `:479`, `:506`, `:507`, `:535`, `:539`. After the synthetic dispatch, the render shows 8 handles (or zero, per the negative assertions).

In a real browser at staging, the operator hovers — and nothing happens. Click still works.

The diagnostic question is therefore: **what is the test substrate proving, and what is it not proving?**

Answer (preview, expanded in §5): the tests prove that *if* `onPointerEnter` fires on the wrapper, the handler runs and the state updates and the handles render. They do NOT prove *that* `onPointerEnter` fires on the wrapper in a real browser when the operator's cursor enters the widget. That second proposition has zero coverage in the test substrate, because `fireEvent.pointerEnter` is a synthetic event dispatch that bypasses every layer of the browser's hit-testing, compositing, and event-delivery pipeline.

---

## 3. Hypotheses audited

Six hypotheses framed in the build prompt. Each audited against code evidence in the current tree (post-`a1c10c7`).

### Hypothesis A — `useDraggable` `{...attributes}` spread overwrites `onPointerEnter`/`onPointerLeave`

**Verdict: ruled out.**

Two evidence threads independently rule this out:

1. **Spread ordering is correct** per FF-4 plumbing canon. `FreeFormPlacedWidget.tsx:198-199` spreads `{...listeners}` + `{...attributes}` FIRST; `onContextMenu` follows at line 202; `onPointerEnter`/`onPointerLeave` follow at lines 206-207. Explicit handlers AFTER spread per the canon at FF-4 commit `c5d71c7` build report.

2. **`attributes` and `listeners` do not contain pointer enter/leave handlers anyway**. `frontend/node_modules/@dnd-kit/core/dist/hooks/useDraggable.d.ts:14-21` declares `DraggableAttributes` as `{ role, tabIndex, 'aria-disabled', 'aria-pressed', 'aria-roledescription', 'aria-describedby' }` — pure ARIA + role + tabIndex. `frontend/node_modules/@dnd-kit/core/dist/sensors/pointer/PointerSensor.d.ts:9-12` declares `PointerSensor.activators` as `[{ eventName: 'onPointerDown', handler: ... }]` only. KeyboardSensor contributes `onKeyDown`. There is no path by which `listeners` or `attributes` could contain `onPointerEnter` or `onPointerLeave`.

Even if spread ordering were reversed, the spread does not carry pointer enter/leave handlers to overwrite with. Hypothesis A is doubly ruled out.

### Hypothesis B — child element absorbs pointer events (stopPropagation / pointer-events:none)

**Verdict: ruled out.**

`PlacedWidgetCore.tsx:117-167` renders one outer `<div>` with `onClick` (calls `stopPropagation` at line 126) and `onKeyDown` (calls `stopPropagation` at line 136). No pointer enter/leave/over/out handlers. No `stopPropagation` in pointer-event handlers (there are none). No inline `pointer-events: none` on the outer or inner div (lines 140-155 inline style enumerated; nothing matching).

Grep across `frontend/src/bridgeable-admin/components/focus-builder/*.tsx` for `pointerEvents` / `pointer-events` returns hits only in `MarqueeOverlay`, `SnapLineOverlay`, `ResizeHandleOverlay` (overlay-shell `none` + handle `auto`), and `AlignmentGuideOverlay` — all expected by the platform pointer-events contract; none would absorb a pointerenter on the FreeFormPlacedWidget wrapper.

`pointerenter` per W3C spec fires on the wrapper when the pointer enters its bounding region regardless of which descendant is the topmost hit target. A child rendering on top of the wrapper does not block the wrapper's `pointerenter`.

### Hypothesis C — JSDOM test target mismatch / pointer event semantics

**Verdict: this is the load-bearing finding, but in a refined form. See §5 for the full framing.**

The narrow form of Hypothesis C posed in the build prompt (`pointerEnter` non-bubbling vs `pointerOver` bubbling) does NOT cleanly explain the bug at the spec level. `pointerenter` per W3C [Pointer Events L3 §4.2.5](https://www.w3.org/TR/pointerevents3/#the-pointerenter-event) fires on each element the pointer enters, including ancestors entered via a child — the non-bubbling characteristic is about the event-dispatch model, not about whether ancestors receive the event.

The refined form *does* hold: **the test substrate (`fireEvent.pointerEnter(draggable)`) does not exercise any browser hit-testing, layout compositing, or native event-delivery path**. It directly synthesizes a React `SyntheticEvent` and dispatches it to the wrapper's `onPointerEnter` handler. This proves the handler-if-fired branch. It does NOT prove the handler-fires branch.

In a real browser, the operator's pointer entering the widget produces a chain of:

1. OS-level pointer move event
2. Browser hit-test against the layout tree (z-index, overflow, transforms, pointer-events CSS, ancestor visibility, ancestor opacity, etc.)
3. Browser native `pointerover` / `pointerenter` dispatch on hit-test target + ancestors
4. React event normalization
5. React synthetic event handler invocation

Steps 1-4 have zero JSDOM coverage. The bug is somewhere in steps 1-4. The tests pass because they jump straight to step 5.

### Hypothesis D — CSS layout (wrapper lacks hit-testable surface)

**Verdict: ruled out at the static-code-evidence level; cannot be fully ruled out without real-browser inspection.**

Inline style at `FreeFormPlacedWidget.tsx:208-228` declares `position: absolute`, `left: ${x}px`, `top: ${y}px`, `width: ${width}px`, `height: ${height}px` with `x/y` defaulting to `0` and width/height defaulting to `FREE_FORM_DEFAULT_DIMENSIONS` (typical 320×180 per registry). For the canonical Today Pin widget at the platform default `240×120`, the wrapper has a real bounding box.

`PlacedWidgetCore` fills it via `outerStyle: { width: "100%", height: "100%" }` per `FreeFormPlacedWidget.tsx:240-243`.

No `display: contents`, no `display: none`, no `visibility: hidden`, no `opacity: 0` on the wrapper or core in the static code path. Cursor is `grab` (line 217) — does not affect hit testing.

A residual unknown: whether any *parent* of the wrapper in the real-DOM tree at staging has `pointer-events: none` (e.g., a CSS class added by an ancestor library, an admin-app-level layout style, or a global stylesheet hit-test override). Static-code audit of the focus-builder canvas wrappers shows none, but the surface of "every ancestor up to `<html>`" is broader than this read-only investigation covers.

### Hypothesis E — React StrictMode / effect re-binding

**Verdict: ruled out.**

`frontend/src/main.tsx:13` wraps the app in `<StrictMode>`, but StrictMode's double-invocation behavior only affects dev mode. Production builds (Railway-deployed staging is a production Vite build) do not double-render. Even if double-render were active, it would not block `onPointerEnter` from firing — it would fire twice, not zero times.

### Hypothesis F — multiple draggables interfere (8 resize handles each wrapping `useDraggable`)

**Verdict: ruled out as the trigger; relevant only as a secondary consequence.**

When `(isHovered || selected || isDragging)` is true, ResizeHandleOverlay mounts and each of the 8 handles registers its own `useDraggable` (`ResizeHandleOverlay.tsx:148-189`). This triggers a DndContext registry update and a follow-on re-render.

But this only happens AFTER `isHovered` becomes true. It is downstream of the failing path, not upstream. The bug is that `isHovered` never becomes true on hover. Cascade from 8 draggable registrations cannot prevent a prior pointerenter handler from firing — the registrations happen on the re-render triggered by `setIsHovered(true)`, which is itself the thing that isn't firing.

---

## 4. Root cause

The static-code audit conclusively rules out Hypotheses A, B, E, F. Hypothesis D is ruled out at the focus-builder layer but cannot be ruled out across the full ancestor chain in a real-browser DOM without DevTools inspection. Hypothesis C in its narrow framing is wrong; in its refined framing it is correct — the test substrate doesn't exercise the real-browser event path.

**The root cause cannot be conclusively locked at the file:line level from this static-code audit alone.** That itself is a finding: the static-evidence path is exhausted. The next diagnostic step requires real-browser DevTools — open staging in Chrome, click an empty widget area, inspect the wrapper's computed style + event listeners + ancestor `pointer-events` chain, then move the cursor and observe whether `pointerenter` fires natively. The investigation discipline allows this honest accounting: lock what is provable from code, flag what requires live diagnostic, recommend the next step.

**Strongest remaining candidates** (in order of likelihood given static evidence):

1. **An ancestor `pointer-events: none` somewhere above the canvas** that JSDOM doesn't model because JSDOM doesn't compute layout / pointer-events. This is the highest-probability candidate because (a) the platform-wide "Focus Canvas tier-renderer pointer-events contract" documents exactly this pattern existing elsewhere in the codebase, and (b) JSDOM's lack of CSS layout means any such ancestor would silently pass JSDOM tests.

2. **A latent overlay element absolutely positioned over the canvas** that intercepts hit testing — perhaps a transparent debug overlay, the marquee overlay's mounting state, or the snap-line overlay's positioning. `MarqueeOverlay` and `SnapLineOverlay` both have `pointer-events: none` per static audit (correct), but if either rendered an unexpected box without that style at runtime, it would block real-browser hover.

3. **A React 19 batching / commit-phase issue** specific to the combination of `useState` + nested `useDraggable` hooks under a re-rendering DndContext. This is the lowest-probability candidate but cannot be ruled out without runtime verification.

The fix-arc dispatch must begin with real-browser DevTools inspection to discriminate among these three. The test-substrate gap (§5) is locked regardless of which root cause is identified live.

---

## 5. Test-substrate gap

**This finding is locked at the static-evidence level and does not depend on the root-cause diagnostic.**

The five hover-state tests at `FreeFormPlacedWidget.test.tsx:424-573` share a pattern:

```ts
const draggable = screen.getByTestId(
  "focus-builder-freeform-placed-widget-draggable",
)
fireEvent.pointerEnter(draggable)
expect(screen.getAllByTestId("focus-builder-resize-handle")).toHaveLength(8)
```

This pattern tests one proposition: *if React's `onPointerEnter` handler on the wrapper fires, the state updates and the handles render.*

It does not test:

- *That* `onPointerEnter` fires on the wrapper in a real browser when the cursor enters the widget area
- That CSS layout produces a hit-testable surface at the wrapper's bounds
- That no ancestor element has `pointer-events: none` blocking native event delivery
- That no descendant or sibling element captures the hit first via z-index / position
- That the DOM-level `pointerenter` propagation chain reaches React's synthetic event system

`@testing-library/react`'s `fireEvent.pointerEnter` synthesizes a `PointerEvent` and dispatches it to the React fiber directly. JSDOM does not run a browser layout engine, does not compute z-index stacking contexts, does not honor `pointer-events: none`, does not perform hit testing, does not simulate native pointer-event compositing. All of these are silently no-ops in JSDOM.

**The test-substrate gap is therefore class-wide, not specific to this fix arc.** Any unit test using `fireEvent.pointerEnter` (or pointerLeave / pointerOver / pointerOut / mouseEnter / mouseLeave / mouseOver / mouseOut) proves only the handler-if-fired branch. The handler-fires branch is a real-browser concern and requires Playwright (or equivalent headless-browser) coverage.

This gap is already partially documented in the codebase: `FreeFormPlacedWidget.tsx:50-52` explicitly notes "Per Q-40: integration tests drive @dnd-kit's KeyboardSensor (Space to grab, arrows to nudge, Space to drop). Pointer coverage in JSDOM is unreliable; that lands in Playwright at FF-7." The Q-40 lock applies to *drag* gestures via PointerSensor. **The hover-state addition in `a1c10c7` extended a NEW pointer-event surface (pointerenter/pointerleave) without applying the Q-40 discipline** — the new behavior was covered only by JSDOM `fireEvent` tests, with no Playwright coverage.

Playwright coverage for FF-series gestures lives at `frontend/tests/e2e/`. Adding a hover-state Playwright spec (cursor moves into widget area at staging-equivalent CSS context → handles appear) would close the gap. Per FF-7 build report, Playwright is the canonical real-browser gate for pointer-event surfaces in the focus builder.

---

## 6. Fix shape

### 6a. Root-cause fix (depends on live-DevTools diagnostic)

The fix arc must begin with a DevTools inspection step against staging:

1. Open staging Focus Builder with a free-form template loaded.
2. Open Chrome DevTools → Elements pane.
3. Select the `focus-builder-freeform-placed-widget-draggable` wrapper.
4. Inspect Computed → check `pointer-events` value. Walk up to `<html>` checking each ancestor's `pointer-events`.
5. Inspect Event Listeners pane on the wrapper. Confirm `pointerenter` is listed.
6. Move the cursor over the widget. Watch the React DevTools "Components" panel for the FreeFormPlacedWidget instance — does `isHovered` flip from `false` to `true`?

The DevTools diagnostic answers which of the three §4 candidates is real. The fix follows from the diagnosis:

- **If ancestor `pointer-events: none`**: locate the ancestor, audit whether the `none` was intentional, narrow the scope so it does not extend to the widget chrome, OR self-assert `pointer-events: auto` on the FreeFormPlacedWidget wrapper as a defensive override. Cost: 1-3 LOC; test: extend the existing test substrate to assert the wrapper's computed `pointer-events` style.

- **If overlay element intercepting**: audit MarqueeOverlay / SnapLineOverlay / DragOverlay positioning at idle. Cost: 5-20 LOC depending on root cause.

- **If React batching / DndContext interaction**: more complex. Could require moving hover state to a different lifecycle hook, using `useLayoutEffect`, or refactoring the hover handlers to use native DOM event listeners via `useEffect` instead of React's synthetic-event prop binding. Cost: 30-60 LOC.

LOC estimate (root-cause fix alone): 5-60 LOC, weighted heavily toward the low end based on the static-evidence audit pointing to candidate 1 (ancestor pointer-events).

### 6b. Test-substrate fix

The hover-state Playwright spec at `frontend/tests/e2e/` should:

1. Sign in via the staging admin path.
2. Navigate to a Focus Builder free-form template with at least one widget.
3. `page.mouse.move(x, y)` to a coordinate clearly outside the widget.
4. Assert handles NOT visible: `expect(page.locator('[data-testid="focus-builder-resize-handle"]')).toHaveCount(0)`.
5. `page.mouse.move(widgetCenterX, widgetCenterY)` to a coordinate over the widget.
6. Assert handles visible: `expect(page.locator('[data-testid="focus-builder-resize-handle"]')).toHaveCount(8)`.
7. Move pointer off again; assert handles disappear.

LOC estimate (test-substrate fix alone): ~50-100 LOC for one new spec file plus any necessary helpers + test data seeding. Fits the FF-7 Playwright pattern.

### 6c. Verify-against-pre-fix discipline

The Playwright spec, run against pre-fix HEAD, should FAIL (handles not visible on hover at staging). Run against post-fix HEAD, should PASS. This is the canonical verify-against-pre-fix step from the FF-series build canon.

### 6d. Combined estimate

Total fix-arc LOC: **~55-160**, dominated by the Playwright spec rather than the production code change.

---

## 7. Process canon candidate

**Recommend filing.**

Candidate canon entry: *"Unit tests using `fireEvent.<pointer-event>` prove handler-if-fired only; they do NOT prove handler-fires in a real browser. New pointer-event surfaces require Playwright coverage before merge, not just JSDOM unit coverage. The Q-40 lock (PointerSensor coverage lands in Playwright) extends to ALL pointer-event surfaces in the focus builder — drag, hover, leave, over, out, enter — not just drag-gesture pointer events."*

The candidate generalizes a pattern already partially codified at Q-40 but applied narrowly. The hover-state gap shows the narrow application was not enough — Q-40 mentioned drag-gesture-via-PointerSensor only, and the operator who shipped `a1c10c7` reasonably did not extend it to a hover-state addition that lives outside @dnd-kit's `listeners`.

A second candidate is the meta-lesson that *staging operator verification is the canonical real-browser gate, not vitest's JSDOM*. This generalizes beyond pointer events to any layout-dependent or CSS-dependent behavior. File alongside the first canon candidate, OR fold into a single broader entry.

Filing should happen in a post-fix canon-update arc, not in the fix arc itself.

---

## 8. Fix arc dispatch shape

**Recommend: single combined fix arc.**

Both fixes (root-cause production-code change + Playwright spec) target the same operator-observable behavior, the same substrate, and the same merge milestone. Splitting them would invite shipping the production fix without the test, recreating the exact gap that allowed `a1c10c7` to ship. The combined arc enforces the verify-against-pre-fix discipline by construction.

Sequence within the arc:

1. DevTools diagnostic step against staging (no commit; investigation-style step).
2. Write the Playwright spec FIRST. Confirm it fails against `a1c10c7` HEAD.
3. Apply the production-code fix.
4. Re-run Playwright. Confirm it passes.
5. Run vitest. Confirm no regression in the 5 JSDOM hover-state tests (they continue passing because the fix doesn't alter handler-if-fired semantics).
6. Commit.

---

## 9. Architectural surprises during investigation

1. **`useDraggable` `attributes` is purely ARIA-shaped — no pointer handlers, ever**. The FF-4 plumbing canon ("`{...attributes}` overwrites explicit props if ordered after") was specifically about ARIA / role / tabIndex overwriting. The hover-state code in `a1c10c7` correctly applied that canon, but `attributes` could not have overwritten pointer enter/leave handlers anyway — they're not in `attributes`. The discipline was correct; its applicability to this specific concern was nil. Cost: zero (no harm done). Lesson: canon-driven defensive coding is sometimes addressing a problem that doesn't exist at the new surface, which is fine — the canon's existence costs nothing when applied correctly even where unnecessary.

2. **JSDOM's lack of CSS / layout is silently undermining a whole class of UI behavior tests**. This is not new knowledge — the platform Q-40 lock acknowledges it for drag gestures. But the practical effect is broader than Q-40's narrow scope: any test that simulates a pointer event via `fireEvent` is proving only the handler-if-fired branch, regardless of whether the pointer event in question is part of a drag gesture. The fix arc canon candidate generalizes this.

3. **The five hover-state tests share an identical pattern that doesn't distinguish "the handler fired" from "the handler did the right thing when fired"**. They all assert "fire pointerEnter → expect handles." None of them assert the wrapper has a hit-testable surface, has the right CSS, or has no blocking ancestor. The Playwright equivalent would fold all five JSDOM tests into one or two end-to-end tests that prove both branches at once. The JSDOM tests can remain (handler-if-fired coverage is still useful for fast feedback during iteration), but the gate-decision-quality test for hover-state behavior is Playwright.

4. **The investigation could not lock root cause from static evidence alone**. This is the first FF-series investigation in this arc where the static-code audit was exhausted without conclusive file:line evidence for the bug. Previous investigations (Findings 1 + 2 of `224cc06`, FF-1 through FF-7 sub-arc investigations) all reached file:line conclusions from code reading. This one reaches "candidate set narrowed to three; DevTools step required to discriminate." The investigation discipline allows this honest accounting; the fix arc absorbs the live-diagnostic cost.

---

## 10. Honest evidence gaps

- **Real-browser DevTools step not performed in this investigation**. The build prompt scoped this investigation as a read-only static-code audit. A DevTools-against-staging step would have produced a definitive root-cause lock; the fix arc must perform it as its first step.

- **Ancestor pointer-events / opacity / visibility chain not audited above the focus-builder canvas**. The static audit covered `FreeFormPlacedWidget`, `PlacedWidgetCore`, `ResizeHandleOverlay`, `WidgetFreeFormLayer`, `FocusBuilderCanvas`. It did not walk further up to `FocusBuilderPage`, `BridgeableAdminApp`, the admin layout chrome, the React root, the index.html body, or any global stylesheet. A fuller ancestor audit could conceivably lock candidate 1 (ancestor `pointer-events: none`) from static evidence; this investigation chose to stop at the focus-builder layer and recommend DevTools as the next step, on the theory that DevTools is faster and more reliable than further static audit.

- **The investigation does not rule out a React-19-specific commit-phase quirk**. Such quirks are rare in production code and unlikely to be the root cause here, but the static audit cannot rule them out.

- **No Playwright reproduction was attempted in this investigation**. Per the read-only constraint.

---

## 11. Summary

| Finding | Status |
|---|---|
| Hypothesis A (spread overwrite) | Ruled out — handlers AFTER spread; spread doesn't carry pointer handlers anyway |
| Hypothesis B (child absorption) | Ruled out — no stopPropagation on pointer events; no pointer-events:none on core or overlay |
| Hypothesis C (test-substrate gap) | **CONFIRMED in refined framing** — JSDOM `fireEvent` proves handler-if-fired only |
| Hypothesis D (CSS layout) | Ruled out at focus-builder layer; cannot rule out at ancestor layer without DevTools |
| Hypothesis E (StrictMode) | Ruled out — production build doesn't double-invoke; would fire twice not zero times |
| Hypothesis F (multiple draggables) | Ruled out — cascade is downstream of the failing path |
| Root cause locked | NO — candidates narrowed to three; DevTools step required |
| Test-substrate gap locked | YES |
| Fix shape locked | Combined arc; DevTools diagnostic + Playwright spec + production-code fix |
| Process canon candidate | YES — Q-40 generalization to all pointer-event surfaces |
| Fix arc dispatch | Single combined; sequenced internally (Playwright spec first, then production fix) |

The investigation discipline honored: static evidence exhausted; live-diagnostic step recommended to the fix arc; test-substrate gap locked independent of root cause; canon candidate flagged for post-fix arc.

---

## 11. Root cause confirmed via staging diagnostic — 2026-05-20 (POST-INVESTIGATION CORRECTION)

After investigation ship, operator ran the recommended staging DevTools diagnostic. **All three narrowed candidates were ruled out.** Actual root cause was a fourth candidate the investigation did not enumerate.

### What the operator confirmed

1. Attached a native DOM listener directly on the `focus-builder-freeform-placed-widget-draggable` element at staging:
   ```js
   document.querySelector('[data-testid="focus-builder-freeform-placed-widget-draggable"]')
     .addEventListener('pointerenter', () => console.log('FIRED'))
   ```
2. Hovered the widget body 10+ times.
3. **Zero `pointerenter` events fired**. The native listener never invoked even once.

This rules out candidates 1 (ancestor pointer-events: none) and 2 (latent transparent overlay): in both cases, the native listener would still fire when the pointer entered the element through whatever path remained. It rules out candidate 3 (React 19 / DndContext batching): a batching issue would suppress the React handler but not a directly-attached native listener.

### The actual root cause

`onPointerEnter` / `onPointerLeave` use **non-bubbling** native `pointerenter` / `pointerleave` semantics (W3C Pointer Events spec). Their hit-test cascade depends on **layout-box crossing**: the events fire only when the pointer crosses the layout box of the element with the listener (and any descendant layout boxes that re-trigger the cascade).

The DOM tree between the operator's pointer and the `FreeFormPlacedWidget` draggable wrapper includes an intermediate `display: contents` div emitted by the `registerComponent` HOC at `frontend/src/lib/visual-editor/registry/register.ts:215`:

```tsx
createElement("div", {
  "data-component-name": frozenMeta.name,
  style: { display: "contents" },
}, createElement(Component, props))
```

`display: contents` removes the element from the visual formatting context — it has **no layout box**. When the pointer enters the today-pin-widget body through this wrapper, the layout-box cascade breaks: chromium walks from the inner layout-box (the widget's rendered content) upward, finds no layout box on the `display: contents` div, and the cascade fails to reach the outer draggable wrapper that owns the `pointerenter` listener.

JSDOM ignores `display: contents` entirely — it dispatches synthetic pointer events directly to the handler element identified by the testid, with no layout-box hit-test logic at all. That's why every JSDOM test passed even though the production DOM was broken.

### The fix

Replace `onPointerEnter` / `onPointerLeave` with the **bubbling** variants `onPointerOver` / `onPointerOut`. Bubbling rides DOM-tree edges (parent / child relationships) not layout-box adjacency, so it passes through `display: contents` cleanly.

A `relatedTarget` contains-check on `pointerout` is load-bearing: `pointerout` fires whenever the pointer moves to ANY child element of the widget, NOT only when leaving the widget entirely. Without the check, hovering between nested elements would flicker isHovered → false → true. With the check, the false path runs only on true widget exit.

Shipped in the same dispatch as fix arc HEAD `546aa46 + 1` (2026-05-20):
- `FreeFormPlacedWidget.tsx`: handlers + JSX attributes swapped to bubbling variants.
- `FreeFormPlacedWidget.test.tsx`: `fireEvent.pointerEnter` → `fireEvent.pointerOver`; `fireEvent.pointerLeave` → `fireEvent.pointerOut(... { relatedTarget: document.body })`. New JSDOM test covering relatedTarget contains-check via descendant pointer-move.
- `tests/e2e/focus-builder-hover-pointer-semantics.spec.ts`: Playwright spec with inline `page.setContent` fixture demonstrating the bubbling shape works in real chromium + a source-shape regression gate inspecting the production file for the bubbling event names + contains-check.

---

## 12. Process canon candidates (post-fix)

### 12.1 — Investigations of event-related bugs must enumerate by event-type semantics, not only by location

This investigation enumerated hypotheses by **location**: ancestor chain (Hypothesis A spread overwrite, Hypothesis B child absorption, Hypothesis D CSS layout, Hypothesis F multiple draggables), framework batching (Hypothesis E StrictMode), test-substrate gap (Hypothesis C). All six are location-shaped.

The actual root cause is **event-type semantic**: bubbling vs non-bubbling. The DOM tree shape (a `display: contents` intermediate element) only matters because of how the chosen event type's hit-test cascade interacts with elements lacking layout boxes. With the bubbling variant the same DOM tree works.

The canon refinement: for event-related bugs, the candidate set must include enumeration by event-type semantics — bubbling vs non-bubbling, capture vs bubble phase, passive vs active, synthetic vs native. This is a load-bearing axis orthogonal to location enumeration.

Q-40's generalization to "all pointer-event surfaces need Playwright coverage" remains valid + accepted; this is a separate, narrower axis on top.

### 12.2 — Investigation-time UX locks should be revisited by operator-experience data

(Carried forward from the original investigation §10.) Q-10's "selection-only handles" lock was refined by operator-experience to "hover OR selection." Pattern: investigation-time locks that depend on UX intuition should be re-examined post-ship against operator-experience data; when the operator's first interaction contradicts the lock, the lock was wrong, not the operator.

### 12.3 — JSDOM-vs-chromium fidelity is bounded by DOM-tree synthesis, not just event simulation

(Refinement of Q-40.) JSDOM's gap with real chromium is broader than "JSDOM can't fire pointer events reliably." JSDOM also doesn't synthesize layout for `display: contents` elements the way chromium does; doesn't run hit-tests; doesn't model pointer capture or relatedTarget propagation faithfully. Any test that depends on these mechanisms must have a chromium gate.

### 12.4 — Investigation source-candidate audit

(Carried forward.) When narrowing a candidate set, the investigation should explicitly audit whether the candidate set is COMPLETE. Three-candidate narrowing landed all three wrong; the actual cause was a fourth that wasn't enumerated. A "have we enumerated by every relevant axis?" gate before locking the candidate set would have surfaced the event-type-semantic axis.

These four candidates are flagged here for a dedicated canon-update arc per established sequencing. They are NOT filed as canon entries in the fix arc itself.

