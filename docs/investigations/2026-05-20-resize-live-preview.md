# Resize Live Preview — Read-Only Investigation

**Arc**: `2026-05-20-resize-live-preview`
**HEAD at investigation**: `d9ffd90` (hover-state staging-regression fix)
**Scope**: Investigation-only. Zero production / test changes. Output is this document + a STATE.md entry. Fix arc dispatches separately.

---

## 1. Context

Operator completed staging verification of hover-fix arc `d9ffd90`:
- Hover-state handle reveal: working (pointerover/pointerout via bubbling semantics; display:contents cascade workaround holding).
- UUID-leak suppression at DragOverlay: holding.
- pointerout `relatedTarget` contains-check edge case: working.

While exercising resize during the same staging verification, the operator surfaced a new finding: **resize handles do not preview during drag**. Operator drags a resize handle (e.g., south-east corner from 320×180 toward 420×280). For the entire duration of the drag, the widget remains rendered at its original 320×180 dimensions. Only at pointer-release does the widget update to its final dimensions. The transition reads as a "snap" rather than a smooth manipulation.

Compare to FF-3 (drag-to-move shipped at `63ecd7b`): when an operator drags a widget body, the widget glides under the cursor in real time — the visual position updates continuously throughout the gesture.

The narrow question: **why does drag-to-move preview and drag-resize not? What's the locked fix shape to add live resize preview?**

---

## 2. FF-3 vs FF-4 Substrate Comparison

### 2.1 FF-3 drag-to-move: free preview via @dnd-kit CSS `transform`

`FreeFormPlacedWidget.tsx` calls `useDraggable` at line 134-143 and destructures `transform` from the return:

```
const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({...})
```

At line 199-201:

```
const translate = transform
  ? `translate3d(${transform.x}px, ${transform.y}px, 0)`
  : undefined
```

That `translate` is consumed at line 250 in the wrapper's inline `style.transform`:

```
transform: translate,
```

`@dnd-kit/core`'s `useDraggable` updates the `transform` object on every pointer-move tick. React re-renders the FreeFormPlacedWidget — but the re-render only changes `style.transform`. The widget's `left` / `top` (from `placement.x` / `placement.y`) stay untouched at lines 246-247. The OS compositor moves the widget via the GPU-accelerated `translate3d`. No state mutation in `rowsDraft`. No save queue churn. No other widgets re-render. **The preview is free** — `useDraggable` does the work, the widget consumes the `transform` it returns, the visual position glides under the cursor.

At drag-end, `handleDragEnd` in `FocusBuilderPage.tsx` (line 822-1080) parses the drag id, resolves the active placement, and calls `templateHook.updateWidget(id, { x: nextX, y: nextY })`. The next render flips `placement.x` / `placement.y` to their final values and `transform` resets to null (drag is over). Visually seamless — the widget was already painted at the final position via the GPU translate; the React state catches up at the same frame.

### 2.2 FF-4 drag-resize: no preview because `transform` is unused, and dimensions are state-controlled

`ResizeHandleOverlay.tsx` line 148-157 calls `useDraggable` per handle:

```
const { attributes, listeners, setNodeRef } = useDraggable({
  id, data: { kind: "free-form-resize-handle", placementId, position },
})
```

**Critical**: `transform` is NOT destructured. Even if it were, applying `translate3d` to a single 8×8 handle would only move the handle itself — the WIDGET it conceptually resizes has no awareness of the handle's drag transform.

The widget's dimensions at `FreeFormPlacedWidget.tsx` line 247-248:

```
width: `${width}px`,
height: `${height}px`,
```

derive from `placement.width` / `placement.height` (lines 122-129). Those are state fields in `rowsDraft`. The only way to change them visually is to commit a state mutation that bumps the React render with new `placement.width` / `placement.height` values.

The page-level `handleDragMove` at `FocusBuilderPage.tsx` line 1114-1182 is the only callback wired into `DndContext`'s `onDragMove` (line 1194). Its body:

- Line 1117: `parseFreeFormDraggableId(String(e.active.id))` — only matches `free-form-placed-widget:<id>`.
- Line 1118: `if (placementId === null) return` — for resize-handle drags (`<placementId>-handle-<position>`), `parseFreeFormDraggableId` returns null. **The handler early-exits.**
- Lines 1166-1179: computes `snapLines` for drag-to-move only.

There is NO `parseResizeHandleId` branch in `handleDragMove`. The resize commit (`parseResizeHandleId` branch in `handleDragEnd` at line 836-881) fires only at drag-end.

**Net result during a resize drag**: the handle's @dnd-kit transform moves the handle div visually (translate3d on the handle itself), the widget's width/height never changes because no state mutation fires, and `onDragMove` is a no-op for the resize-handle id shape.

### 2.3 The architectural difference, summarized

| Surface | Visual control | Update path during drag |
|---|---|---|
| FF-3 drag-to-move | `style.transform: translate3d(x,y,0)` on widget wrapper, fed by @dnd-kit's `transform` | Free — `useDraggable` updates transform per tick; React re-renders consume it; no state mutation |
| FF-4 drag-resize | `style.width / height` on widget wrapper, fed by `placement.width / placement.height` state | Absent — `useDraggable` runs but `transform` is unused; state never mutates; no preview |

The difference is fundamental: **CSS translate handles position cheaply; CSS width/height changes require state mutation in the placement record**. @dnd-kit's transform model only works for translation. Dimensions need a different mechanism.

---

## 3. Fix Options Enumerated

### Option A — Commit-on-tick: `handleDragMove` dispatches `updateWidget` during resize

Add a resize-handle branch in `handleDragMove`. Parse `parseResizeHandleId`; on match, compute the same `computeResizeCommit` as drag-end, dispatch `templateHook.updateWidget(id, { x, y, width, height })` per tick.

**Substrate cost**:
- Per-tick state mutation in `rowsDraft` (functional setter at `useFocusTemplateDraft.ts` line 773-794). Each call clones every row + every placement. For a typical canvas (5-15 widgets) this is cheap.
- Each tick triggers a re-render of every widget on the canvas (rowsDraft change → WidgetFreeFormLayer re-renders → all placements re-render). React's reconciliation with stable `placement.id` keys keeps DOM ops minimal, but every placed widget's component function runs.
- Each tick triggers `queueSave()` (line 799). Q-26's debounced save pipeline coalesces; the boundary save is no-op for unchanged state. Network churn is bounded.
- FF-7 hook race fix (functional setRowsDraft, line 773): tolerates rapid successive calls — the pattern was introduced specifically to handle multi-update races. Per-tick resize commits compose cleanly with this discipline.

**Composition with FF-7 snap-to-alignment (Q-11)**: snap currently fires only for drag-to-move (line 1166-1179). To extend to resize, `computeSnapAdjustment` would need a resize-aware mode (edge being moved snaps to other widgets' edges). Substrate extension required.

**Composition with FF-6 inspector positioning fields**: bidirectional via FF-1 architecture is "free" — placement state changes propagate to inputs immediately. With per-tick commits, the W / H inputs would update live during resize (60Hz). May feel correct or may feel jittery; live-update vs commit-at-end UX call.

**Composition with FF-1 debounced save (Q-26)**: `queueSave` debounce coalesces 60Hz calls naturally. No new substrate.

**Edge cases**:
- Rapid gestures: functional setter handles in-flight reads.
- Multi-select resize: NOT supported in FF-4 today (only drag-to-move has the FF-7 multi-select branch at lines 923+). Out of scope.
- Keyboard nudge resize: NOT supported today; keyboard nudge handles position only (lines 760-784).

---

### Option B — Canvas-level ghost state during drag

Add per-drag local state in `FocusBuilderPage.tsx`: `resizeGhost: { id, x, y, width, height } | null`. `onDragMove` updates ghost; rendering layer reads ghost when present + falls back to placement. Drag-end commits ghost to `rowsDraft` + clears ghost.

**Substrate cost**:
- Localized state; only the actively-resized widget re-renders during drag (ghost lookup keyed on id).
- No rowsDraft churn during drag; no `queueSave` per tick.
- WidgetFreeFormLayer must be threaded with `resizeGhost` prop + each FreeFormPlacedWidget must check ghost before reading placement. **Cross-component prop drilling** through canvas → layer → widget.
- `ResizeHandleOverlay` agnostic — handles still useDraggable. The ghost lives in the page.

**Composition with FF-7 snap-to-alignment**: snap engine reads draft positions for nearby widgets; resize ghost would need to be the source of truth for the resizing widget during the gesture. Engine extension required regardless.

**Composition with FF-6 inspector positioning fields**: inspector reads placement state, not ghost state. **Inputs would NOT update during resize** unless threaded with ghost. Breaks the "free bidirectional sync" property — divergent from current drag-to-move shape (which also doesn't update inputs live during drag-to-move position, so consistent in that sense).

**Composition with Q-26 debounced save**: clean — only commits at drag-end, exactly like FF-3 today.

**Edge cases**:
- Cleaner separation; doesn't pollute global state during drag.
- Cancel via Escape: just clear ghost. No rollback needed.

---

### Option C — CSS inline width/height delta during drag (visual-only)

Add to `FreeFormPlacedWidget.tsx`: read @dnd-kit's drag context to detect when ANY handle for this placement is active + which handle. Compute visual delta inline. Apply directly to `style.width` / `style.height` (and offset `style.left` / `style.top` for w/n/nw/sw handles). At drag-end, page handler commits to state as today.

**Substrate cost**:
- Cheapest re-render footprint: only the active widget re-renders during drag (via context subscription).
- Requires `useDndMonitor` or `useDndContext` to observe the active drag + delta from inside FreeFormPlacedWidget.
- Per-handle math (currently in `computeResizeCommit`) duplicated or imported into the widget render path. The pure helper is suitable; reuse is feasible.

**Composition with FF-7 snap-to-alignment**: snap currently lives in page-level handleDragMove → SnapLineOverlay. To support resize-snap, the snap engine needs to know the resize-edge target position, not the position from `placement`. **Visual-only delta means the widget LOOKS resized but `placement.width` doesn't change** — snap math reading placement would lag the visual. To compose, snap must read the visual delta too. Substrate burden similar to A/B.

**Composition with FF-6 inspector positioning fields**: inputs read placement state, so they would NOT update during resize. Same property as Option B.

**Composition with Q-26**: clean.

**Edge cases**:
- Cancel handling requires care — must zero the visual delta without committing.
- Multi-select resize: harder to coordinate because each widget would need its own delta calc.

---

### Option D — Per-widget local ghost at FreeFormPlacedWidget level

Each FreeFormPlacedWidget owns its own resize-in-progress state. Use `useDndMonitor` to detect when a resize-handle drag matching THIS placement's id is active; capture handle position + cumulative delta; compute next placement via `computeResizeCommit`; render the wrapper with overridden width/height/x/y. Drag-end fires the existing page-level commit; ghost clears via the same monitor.

**Substrate cost**:
- Single-widget re-render scope during resize (same as Option C visually).
- State is local; no cross-component prop drilling.
- `useDndMonitor` subscription per widget — N widget instances = N subscriptions. For typical canvases (5-15 widgets) this is negligible. For 100+ widgets it would be measurable but Focus canvases are bounded to ~20 widgets by usability.
- Computation duplication: `computeResizeCommit` called from BOTH the widget's monitor (for visual preview) AND the page's drag-end (for state commit). The pure helper composes cleanly; same delta input, same output, idempotent.

**Composition with FF-7 snap-to-alignment**: snap engine still page-level. To compose resize-aware snap, page would need to know the resize-edge position. Either: (i) page subscribes to its own dnd-monitor for resize gestures and recomputes alongside the widget; (ii) widget bubbles the computed ghost up via a callback the page reads to feed snap. Either route reintroduces page-level work. **Snap-during-resize composition is the cross-cutting cost regardless of option chosen.**

**Composition with FF-6 inspector positioning fields**: inputs read placement state, NOT ghost. **Inputs would not update during resize.** Same property as B and C. Symmetric with current drag-to-move (inputs don't update live during whole-widget drag either).

**Composition with Q-26**: clean. State commits at drag-end; debounced save unchanged.

**Edge cases**:
- Cancel: monitor clears ghost on dragCancel. Clean.
- Stale closures: monitor callback captures placement via React state — closure capture matches the rest of the FF substrate.

---

## 4. Recommended Fix Shape

**Lock Option A — commit-on-tick.**

### Reasoning

1. **Symmetry with the inspector positioning fields argument-from-canon.** The W / H inputs in FF-6's PositionInspectorSection are the *operator-facing equivalent* of the resize gesture. When an operator types W=400 in the inspector, the widget updates instantly (FF-1's bidirectional sync). The argument that drag-resize updates instantly mirrors typing into the inspector is consistent with the operator-observable canon (Q-40 generalization). Option A is the only option that preserves this — input edits and drag edits both flow through `updateWidget`, both render via state, both feel identical. Operator mental model: "the widget's width is a number I'm changing, and the canvas reflects it in real time."

2. **Lowest implementation surface.** A single new branch in `handleDragMove` (~30 LOC), parallel-shape to the existing `handleDragEnd` resize branch. No new prop drilling, no new monitor subscriptions, no new ghost-state lifecycle. The work is one switch in the page handler.

3. **Composes cleanly with FF-7's functional setter discipline.** The pattern that fixed the multi-update race in FF-7 specifically tolerates rapid successive `updateWidget` calls. Option A's 60Hz commit rate is exactly the workload that motivated the functional setter — it's defensive-by-design for this case.

4. **Q-26 debounced save absorbs the network cost.** No network amplification because `queueSave` coalesces.

5. **Re-render scope concern is theoretical, not measured.** The "every widget re-renders per tick" concern assumes the bottleneck is React reconciliation. Empirically with Focus canvases bounded to ≤20 widgets, 60Hz reconciliation of 20 components with stable keys is well within frame budget. If this surfaces as a regression on hand-validation, the optimization path is `React.memo` + `useMemo` on placement props inside WidgetFreeFormLayer — surgical, not architectural.

6. **Snap-to-alignment-during-resize stays SEPARATE.** Locking Option A doesn't entangle the snap question. See §5 — that's a separate scope decision.

### What changes

- `FocusBuilderPage.tsx`: add a `parseResizeHandleId` branch at the top of `handleDragMove` (before the existing `parseFreeFormDraggableId` branch). Body mirrors the existing `handleDragEnd` resize branch (lines 836-880) verbatim — same `computeResizeCommit` call, same `updateWidget` dispatch.

### What does NOT change

- `ResizeHandleOverlay.tsx`: untouched. Handles continue to expose `useDraggable` with no `transform` consumption (they don't move; they're anchored to the widget's edges, which now move under them via state).
- `FreeFormPlacedWidget.tsx`: untouched.
- `computeResizeCommit.ts`: untouched (already pure).
- `useFocusTemplateDraft.ts`: untouched (functional setter already supports rapid calls).
- `handleDragEnd` resize branch: untouched. It commits the final state, redundantly but harmlessly with the last drag-move tick (same `delta` → same `computeResizeCommit` output → same `updateWidget` call → no-op merge in functional setter).

### Implementation surface estimate

- **Production LOC**: ~35 LOC added in `FocusBuilderPage.tsx::handleDragMove`. Mostly a copy-shape of the existing handleDragEnd resize branch + early-return discipline.
- **Test LOC (JSDOM)**: ~50 LOC of unit coverage in `FocusBuilderPage.test.tsx` simulating @dnd-kit KeyboardSensor gestures on a focused resize handle (Q-40 keyboard substrate; pointer in JSDOM is unreliable). Assertions: rowsDraft mutates during simulated drag-move ticks; final commit value matches.
- **Playwright LOC**: ~80 LOC in a new spec (or extending the existing FF-4/FF-7 spec) under `frontend/tests/e2e/` covering: select widget → hover SE handle → drag handle 100px right + 50px down → during drag, assert widget bounding-rect width increased proportionally + height increased proportionally → on release, assert final dimensions persist + match the cumulative delta.
- **Total estimate**: ~165 LOC across production + JSDOM + Playwright.

### Test strategy

- **JSDOM**: keyboard-driven resize via @dnd-kit's KeyboardSensor (Tab to handle, Space to grab, Arrow keys to delta-emit, Space to commit). Assert `rowsDraft` mutates per-step. Per Q-40 canon, pointer in JSDOM is unreliable; keyboard is the JSDOM-truthful gate.
- **Playwright**: pointer-driven resize against a seeded test focus template at `/visual-editor/focus-builder/...`. Inline-fixture pattern from the hover-fix arc applies. Assert widget bounding box mutates *during* the gesture, not only at release. The "during" assertion uses `page.mouse.down + page.mouse.move + page.evaluate(bbox)` between move and up; this is the canonical Playwright resize-preview shape.
- **Source-shape regression gate**: per hover-fix precedent, add a unit test that inspects `FocusBuilderPage.tsx` source for the presence of `parseResizeHandleId` inside `handleDragMove`. Pattern: read the file string at test time, regex/substring-check the handler body. Catches a future refactor that removes the resize-tick branch silently. Complements (not replaces) the Playwright integration test.

---

## 5. Snap-to-Alignment During Resize — DEFERRED

**Decision: defer to a follow-up investigation.**

### Reasoning

- Q-11 locked snap-to-alignment for drag-to-move. The existing `computeSnapAdjustment` takes a `dragPosition` + emits `snapLines` based on the moving widget's BBox vs. other widgets' edges. Extending to resize requires the math to understand "which edge is moving" (the handle being dragged), because resize-snap snaps an edge to a neighbor's edge, not a whole BBox to neighbor positions. This is meaningfully different math.
- Operator signal hasn't surfaced "resize should snap" yet. Locking Option A first gives operators live-preview to work with; downstream operator feedback can then validate whether snap-during-resize is needed before substrate is extended.
- Adding it now would entangle the fix arc with new helper logic, new SnapLineOverlay code paths, and additional Playwright coverage — expanding the fix from ~165 LOC to ~400+ LOC for an unvalidated need.
- If/when surfaced, a future investigation arc decides the math shape + composes against the locked Option A substrate without breaking it (the page-level dragMove already has every piece of state needed).

**Flagged for follow-up**: post-fix operator verification arc evaluates whether resize-snap is needed.

---

## 6. Test Substrate Strategy

### JSDOM coverage

- @dnd-kit's KeyboardSensor reliably dispatches in JSDOM (per Q-40 canon — used by every FF-series sub-arc's unit tests).
- Pattern: simulate Tab to focus a resize handle, Space to activate drag, Arrow keys to emit delta ticks, Space to commit. After each Arrow key, assert `templateHook.rowsDraft` shows the per-tick commit reflecting the cumulative delta.
- **Gap (known per Q-40)**: pointer events in JSDOM do NOT reliably reach @dnd-kit's PointerSensor. Cannot exercise the real pointer-driven path in JSDOM. This is a class-of-bug we already accept.

### Playwright coverage

- Required per Q-40 generalization — the operator path is pointer-driven.
- Test shape: navigate to focus-builder, seed a known template, hover-then-select a widget, locate the SE resize handle via `data-testid="focus-builder-resize-handle"` + `[data-handle-position="se"]`, perform `page.mouse.down + page.mouse.move(intermediate position) + assert bbox during the gesture + page.mouse.up + assert final bbox`. The intermediate-position assertion is what distinguishes "preview works" from "commit-only".
- Inline-fixture: if seeded test data is unwieldy, a source-shape unit test can complement (per the hover-fix precedent at `d9ffd90`).

### Source-shape regression gate (recommended)

- Per hover-fix precedent — unit test reads `FocusBuilderPage.tsx` source as a string + asserts the `handleDragMove` body contains a `parseResizeHandleId` branch. Cheap; catches accidental removal during future refactors. Test lives in the existing FocusBuilderPage.test.tsx.

---

## 7. Fix Arc Scope + Dispatch Shape

**Recommend: single combined fix arc** (not sequenced).

- Scope: add the `parseResizeHandleId` branch in `handleDragMove`; add JSDOM keyboard-driven test; add source-shape regression gate; add Playwright resize-preview spec.
- LOC: ~165 across production + tests.
- Dispatch shape: one arc, one commit, one staging verification cycle.
- Operator hand-validation: drag a resize handle on each of the 8 positions; widget should visually update continuously throughout the drag; final state matches release point.
- Followups (not in this arc): snap-during-resize (deferred per §5); multi-select resize gesture (not in any FF sub-arc today); keyboard-driven resize nudge (out of scope; operators use the W/H inputs for keyboard-driven sizing today).

---

## 8. Architectural Surprises

1. **`useDraggable` returns a `transform` that's wholly unused for resize handles.** The handles still get `attributes` + `listeners` + `setNodeRef` for the drag-end commit path, but the visual `transform` they could expose is ignored. There's nothing wrong with that — the handles are anchored to the widget edges and shouldn't visually translate during their own drag — but it surfaces the asymmetry: @dnd-kit's transform model is position-only by design. Anything dimensional needs state-mediated rendering.

2. **`handleDragMove` predates resize handles** (or at least was authored only with drag-to-move in mind). The early-exit at line 1118 is *correct for snap-lines* (snap math applies to whole-widget moves only) but accidentally also short-circuits the live-resize path. This is a classic case of one handler doing two jobs and only being correct for one.

3. **`handleDragEnd`'s resize branch and the Option-A `handleDragMove` resize branch would have identical bodies.** Both compute `computeResizeCommit` against the same inputs and call `updateWidget` with the same partial. The drag-end branch is the last tick of drag-move, redundantly. Acceptable: @dnd-kit guarantees a final `dragEnd` event with the final delta; the redundant commit is idempotent. Refactoring to extract a `dispatchResizeCommit` helper is a minor cleanup but not required.

4. **FF-6 bidirectional sync to W/H inputs becomes live during resize under Option A.** Operators will see the W and H number inputs in the inspector counter up in real time while dragging a corner handle. This is consistent with the existing X/Y input behavior during drag-to-move... wait — no. Drag-to-move uses CSS transform, NOT state mutation, so X/Y inputs do NOT update live during drag-to-move today. Option A would make resize *more* live than drag-to-move. This is an inconsistency the operator may or may not notice. If desired, a future symmetry arc could either (a) also commit-on-tick for drag-to-move (deliberately giving up the GPU-translate optimization), or (b) defer the resize commit to a ghost-state pattern to match drag-to-move's "inputs lag the gesture" property. **Flagging this as the one architectural inconsistency Option A introduces.** It's small; operator feedback decides whether it matters.

5. **Process canon candidate**: the asymmetry "@dnd-kit transforms position cheaply, dimensions need state" is the kind of substrate-pattern observation worth canonizing in the next canon-update arc. If a future arc adds a similar interactive surface (e.g., drag-to-rotate, drag-to-skew, drag-to-curve a connector in a workflow canvas), this same asymmetry will surface. A one-paragraph note in PLATFORM_ARCHITECTURE.md or the focus-builder section would save the next investigator a half-day. **Flagged — not pre-locked.**

---

## 9. Open Questions / Evidence Gaps

- **Operator preference between Option A's live-input-update and matching drag-to-move's lag-input behavior**: undecided without operator hand-validation. Locking Option A as the substrate; UX inconsistency surfaced for operator call post-ship.
- **60Hz re-render budget on canvases with 20+ widgets**: theoretical concern, not measured. Empirical staging verification post-fix can confirm. Mitigation path (React.memo) is surgical if needed.
- **Resize during multi-selection**: not in any sub-arc today; out of scope for this investigation.
- **Touch-device drag-resize**: untested. Pointer events should cover touch gracefully via @dnd-kit's sensor abstraction, but Playwright coverage is desktop-pointer-only.
