# Resize handle UX refinements — read-only investigation

**Date:** 2026-05-20
**Arc:** read-only investigation; ZERO code changes
**Pre-flight HEAD:** `9e47a3e` (focus-template free-form migration arc)
**Substrate under investigation:** FF-4 (resize handles) at commit `c5d71c7`
**Filed for:** next-on-queue fix arc — `resize-handle-ux-fixes`
**Investigation file:** this document
**Status:** decisions LOCKED below; fix arc pending dispatch

---

## 1. Context

The FF-series (FF-1 through FF-7) shipped the free-form Focus Builder canvas substrate over a two-week sprint culminating 2026-05-20. FF-4 (commit `c5d71c7`) added eight resize handles per free-form widget (4 corners + 4 edges) so operators can resize widgets with the mouse or keyboard, composing on top of FF-3's whole-widget drag and FF-2's absolute positioning.

During staging verification of the assembled FF substrate, two operator-experience concerns surfaced that the FF-4 investigation's Q-10 lock and FF-4's plumbing-time decisions could not have predicted from first principles:

1. **Handle visibility on hover** — operator feedback verbatim: *"I would like it to work on hover without clicking the widget if that is possible."* The Q-10 investigation-time lock chose "visible only when selected" per Figma / Sketch precedent. Real operator feel says discoverability is hurt by requiring a click before the affordance appears.

2. **UUID text glitch during active resize** — during a resize drag, a string matching `<placement-uuid>-handle-<position>` (e.g., `ca8a4f8-...-handle-se`) renders as visible text adjacent to the dragged widget. The text disappears on pointer-release. Operators shouldn't see internal id strings as part of the manipulation UX.

This investigation locks the root cause of (2), proposes a fix shape with an LOC estimate, and refines the Q-10 hover-vs-select decision for (1). It does NOT propose canon-doc revisions. It does NOT touch code. A separate fix arc dispatches against locked decisions.

---

## 2. Finding 1 — Handle visibility on hover

### 2.1 Current Q-10 lock (verbatim)

From `docs/investigations/2026-05-20-free-form-focus-canvas.md` Q-10:

> **8 resize handles** on-selection-only with Shift for aspect-ratio preservation.

From `FreeFormPlacedWidget.tsx:225`:

```tsx
{/* FF-4 — resize handles as a SIBLING of PlacedWidgetCore.
    Rendered only when the widget is selected (canonical
    Figma/Sketch UX). The overlay positions 8 handles relative
    to the FreeFormPlacedWidget wrapper's bounding box. */}
{selected ? <ResizeHandleOverlay placementId={placement.id} /> : null}
```

The condition is a pure boolean on `selected: boolean` (declared at `FreeFormPlacedWidget.tsx:71`), itself sourced from `FocusBuilderSelectionContext` consumed two layers up at `WidgetFreeFormLayer` and passed down.

### 2.2 Operator feedback

Operator staging-verification feedback verbatim (per dispatch prompt): *"I would like it to work on hover without clicking the widget if that is possible."*

This is asking for discoverability via hover, not replacement of selection-based visibility. The operator wants to see manipulation affordances appear as the pointer moves over a widget, before committing to a selection click.

### 2.3 Options considered

- **(a) Hover OR selection** — handles visible when either condition true (Figma / Sketch precedent for hover-reveal; selection-persistence for active manipulation)
- **(b) Hover only** — handles disappear on hover-out regardless of selection (would defeat the active-manipulation case: hover off the widget mid-task and your handles vanish)
- **(c) Selection only (current Q-10 lock)** — preserve current behavior; reject operator feedback

### 2.4 Locked decision

**Option (a) — Hover OR selection.**

Reasoning:
- Discoverability via hover (operator sees affordance without committing to selection) addresses the operator's stated request.
- Selection-state visibility preserves the active-manipulation case: once the operator clicks to select, handles stay visible even if their pointer drifts off the widget (e.g., they're reading the inspector mid-resize).
- The hover-to-selection transition is smooth — handles were already shown via hover, the click just commits selection without re-showing already-visible handles.
- Touch / pointer-coarse devices degrade naturally: `onPointerEnter` doesn't fire reliably on touch, but touch users naturally tap-to-select, which preserves selection-based visibility. No special-case code needed.
- Figma and Sketch both ship this exact pattern (hover OR select shows handles; only the selected object shows persistent selection chrome).

### 2.5 Implementation surface

Approach:

1. Add local `isHovered: boolean` state to `FreeFormPlacedWidget`.
2. Add `onPointerEnter` / `onPointerLeave` handlers on the existing draggable wrapper (`FreeFormPlacedWidget.tsx:170-206`), setting `isHovered` true / false respectively.
3. Change the conditional render at `FreeFormPlacedWidget.tsx:225` from `selected ? ... : null` to `(isHovered || selected) ? ... : null`.

**Edge cases to enumerate** (for the fix arc):

- **Hover during active drag** — handles should remain visible (pointer is over the widget during whole-widget drag). `onPointerLeave` should NOT fire during a whole-widget drag because the cursor stays inside the widget's bounding box. Verify with a unit test.
- **Hover during active resize** — during resize, the widget grows / shrinks under the cursor; `onPointerLeave` may fire if the widget shrinks faster than the cursor follows. Acceptable: selection is already committed by the time resize starts (resize uses the selection-conditional currently; with hover OR select, hover-out during shrink falls back to the selection branch). Verify with an integration test.
- **Hover transitioning to selection** — smooth (no flicker; handles were already rendered via hover; selection just commits).
- **Hover-out after selection** — handles remain visible via selection branch.
- **Multiple widgets simultaneously hovered** — each widget independently tracks its own `isHovered`. A pointer can only be over one widget at a time, so at most one hovered widget plus zero-or-more selected widgets show handles concurrently.
- **Touch / pointer-coarse devices** — `onPointerEnter` may not fire on touch; touch operators tap-to-select; selection-based visibility owns the path. Falls back gracefully.
- **Synthetic event during drag-end** — `@dnd-kit`'s pointer-up handler may interfere with `onPointerLeave` timing. Verify via Playwright at fix-arc-time; unit-level coverage may not catch it (JSDOM pointer-events are unreliable per Q-40).

**LOC estimate** for Finding 1 implementation: **~30-60 LOC** (1 useState, 2 handler refs, 1 condition change in `FreeFormPlacedWidget.tsx`; +2 unit tests for hover-on / hover-off behavior in `FreeFormPlacedWidget.test.tsx`).

---

## 3. Finding 2 — UUID text glitch during resize drag

### 3.1 Observed behavior

Per dispatch prompt: during an active resize drag, a string matching the `<placement-uuid>-handle-<position>` pattern (example: `ca8a4f8-...-handle-se`) renders as visible text adjacent to the widget's right edge. The text disappears on pointer-release.

### 3.2 Investigation findings

**Step 1 — selection-conditional render.** `FreeFormPlacedWidget.tsx:225` renders `ResizeHandleOverlay` only when `selected === true`. The overlay's parent is the FF-3 draggable wrapper at `FreeFormPlacedWidget.tsx:169-227`.

**Step 2 — ResizeHandleOverlay render contract.** `ResizeHandleOverlay.tsx:202-222` renders a wrapper `<div>` with `pointer-events: none` and `inset: 0`, containing eight `<ResizeHandle>` instances. Each `<ResizeHandle>` (`ResizeHandleOverlay.tsx:148-189`) renders an empty `<div>` — **no text content of any kind**. Confirmed by reading every line of the component: no `{handle.id}`, no `{placementId}`, no `{position}` in any JSX text position. The handle id is exposed only via data-attributes (`data-handle-position={position}` at line 165, `data-placement-id={placementId}` at line 166) which are NOT rendered as visible text.

**Conclusion:** the UUID is not coming from FF-4's ResizeHandleOverlay substrate.

**Step 3 — DndContext + DragOverlay audit.** `FocusBuilderPage.tsx:1302-1315`:

```tsx
<DragOverlay>
  {activeDragLabel ? (
    <div
      data-testid="focus-builder-drag-overlay"
      className="rounded-md border border-[color:var(--accent)] bg-surface-elevated px-3 py-1.5 text-[12px] shadow-lg"
      style={{
        fontFamily: "var(--font-plex-sans)",
        color: "var(--content-strong)",
      }}
    >
      {activeDragLabel}
    </div>
  ) : null}
</DragOverlay>
```

The DragOverlay renders `{activeDragLabel}` as visible text content. `activeDragLabel` is React state declared at `FocusBuilderPage.tsx:447-449` and assigned by `handleDragStart` at `FocusBuilderPage.tsx:789-793`:

```tsx
const handleDragStart = React.useCallback((e: DragStartEvent) => {
  const id = String(e.active.id ?? "")
  const slug = paletteItemIdToSlug(id)
  setActiveDragLabel(slug ?? id)
}, [])
```

`paletteItemIdToSlug` is defined at `FocusBuilderPalette.tsx:39` and returns `null` for any id that does NOT begin with `palette-widget:`. Verified by the unit test at `FocusBuilderPalette.test.tsx:48`:

```ts
expect(paletteItemIdToSlug("not-a-palette-id")).toBeNull()
```

For the four drag-id shapes the DndContext sees:

| Drag id shape | paletteItemIdToSlug result | activeDragLabel | Visible in DragOverlay |
|---|---|---|---|
| `palette-widget:<slug>` (palette → canvas drop) | `<slug>` | `<slug>` (e.g., `today-pin-widget`) | clean text |
| `free-form-placed-widget:<uuid>` (whole-widget drag) | `null` | `free-form-placed-widget:<uuid>` | **UUID leak** |
| `<uuid>-handle-<position>` (resize handle) | `null` | `<uuid>-handle-<position>` | **UUID leak (this is the operator-reported case)** |
| Future drag ids | likely `null` | raw id | **UUID leak by default** |

### 3.3 Locked source candidate

**Option C — `DragOverlay` renders the active id (via `activeDragLabel`) as fallback content when no palette slug resolves.**

Evidence:
- `FocusBuilderPage.tsx:792` — `setActiveDragLabel(slug ?? id)` — explicit fallback to raw id.
- `FocusBuilderPage.tsx:1312` — `{activeDragLabel}` — rendered as visible text content inside the DragOverlay child.
- `FocusBuilderPalette.tsx:39-50` (referenced in tests at `FocusBuilderPalette.test.tsx:44-49`) — `paletteItemIdToSlug` returns `null` for non-palette ids.
- `ResizeHandleOverlay.tsx:160-188` — handle div has NO text content; confirmed not the source.
- `FreeFormPlacedWidget.tsx:111-228` — wrapper has NO text content; confirmed not the source.

The text appearing "outside the widget's right edge" matches @dnd-kit's DragOverlay rendering behavior: the overlay element follows the cursor, offset by the overlay's own dimensions and the cursor's grab-point. For a resize-SE-handle drag where the cursor is at the bottom-right corner of the widget, the overlay element renders adjacent to that corner, appearing as "text outside the widget's right edge."

The bug surfaced visibly in FF-4 (resize) more than in FF-3 (whole-widget drag) because:
- FF-3 whole-widget drag uses id `free-form-placed-widget:<uuid>` — the `free-form-placed-widget:` prefix made the leak look like a label, not a raw UUID, and operators may have read it as "label text" rather than "UUID text."
- FF-4 resize-handle drag uses id `<uuid>-handle-<position>` — the UUID leads, making the leak read as a raw UUID immediately.

Both cases are the same bug. FF-4 just made it operator-noticeable.

### 3.4 Locked fix shape

**Approach: route every drag-id shape through a label resolver that returns either a human-readable label OR null (suppressing the DragOverlay entirely).**

Specifically:

1. Add a label-resolver helper near `handleDragStart` (or extract to `commandBarQueryAdapter.ts`-style sibling helper file): inspect the drag-id prefix, return:
   - `palette-widget:<slug>` → `<slug>` (preserves current behavior)
   - `free-form-placed-widget:<uuid>` → return `null` (suppress overlay for whole-widget drag; the widget itself is already visually following the cursor via `transform: translate3d(...)` at `FreeFormPlacedWidget.tsx:149-151`, so the overlay is redundant)
   - `<uuid>-handle-<position>` → return `null` (suppress overlay for resize drags entirely; the widget edge itself moves under the cursor during resize, no label needed)
   - Unrecognized id shapes → return `null` (safe default; no UUID leak by accident)

2. Modify `handleDragStart` (`FocusBuilderPage.tsx:789-793`) to call the resolver instead of inlining the `slug ?? id` fallback.

3. The DragOverlay child guard at `FocusBuilderPage.tsx:1303` (`activeDragLabel ? ... : null`) already handles the null case correctly — passing `null` collapses the overlay to nothing.

**Alternative considered + rejected:** keep the DragOverlay rendering for whole-widget + resize cases but render a friendlier label (e.g., "Today pin" instead of UUID). Rejected because:
- During a whole-widget drag, the widget itself follows the cursor (via FF-3's `transform: translate3d`). A second floating label is visual noise.
- During a resize drag, the widget edge moves under the cursor. A floating label adjacent to the cursor adds nothing operationally.
- The DragOverlay is genuinely useful for palette-drag (where the source widget palette icon is far from the cursor's drop position); for in-canvas manipulation, the source IS the cursor's target.

**LOC estimate** for Finding 2 implementation: **~40-80 LOC** (1 new pure helper `resolveDragLabel(id: string): string | null` ~15 LOC; ~5 LOC change in `handleDragStart`; +6-10 unit tests for label resolution covering all four id-shape cases ~50 LOC; +1 integration test in `FocusBuilderPage.test.tsx` asserting DragOverlay is absent during a resize-handle drag ~20 LOC).

### 3.5 Diagnostic step deferred (none required)

Step 4 evidence was conclusive — the source is locked at `FocusBuilderPage.tsx:792 + 1312` with direct file:line evidence. The fix arc does NOT need a live-DOM DevTools inspection as a first action; it can dispatch directly against the locked source candidate.

---

## 4. Q-10 refinement note

The Q-10 lock in `docs/investigations/2026-05-20-free-form-focus-canvas.md` was:

> **8 resize handles** on-selection-only with Shift for aspect-ratio preservation.

This investigation refines that lock with operator-experience data: handles should also appear on hover. Q-10's investigation-time decision was not wrong at the time — it was made before operator hands ever touched the substrate. Now operator hands have touched it, and the refinement is: **hover OR selection**, not selection-only.

**Canon-update arc consideration: YES, file AFTER the fix arc lands.** Reasoning:

- The substrate has new operator-experience-derived knowledge about handle visibility.
- The canonical record (Q-10 in the FF investigation) should reflect the shipped reality, not the investigation-time guess.
- A canon-update entry framed as "Q-10 refined by operator experience: hover OR selection" preserves both the original reasoning and the refinement chain for future arcs.
- The pattern itself (investigation-time UX locks refined by operator feedback) is a discovered process canon that may merit a `DECISIONS.md` entry of its own.

**This investigation does NOT propose canon revisions.** Filing happens in a separate canon-update arc dispatched AFTER the fix arc commits the implementation. The implementation locks the new behavior; the canon update records the new behavior; both reference each other.

---

## 5. Fix arc scope

**Proposed fix arc:** `resize-handle-ux-fixes` (single dispatch, both findings combined).

**Sequencing recommendation: single combined dispatch.** Reasoning:
- Both findings touch `FreeFormPlacedWidget.tsx` (Finding 1 directly; Finding 2 indirectly via `FocusBuilderPage.tsx` which renders FreeFormPlacedWidget instances).
- Both findings exercise the same FF-4 substrate.
- Both findings have small LOC footprints (~30-60 + ~40-80 = ~70-140 LOC combined source; +~70-130 LOC tests).
- Both findings ship-verify via the same Playwright staging gate (FF-7's `focus-builder-freeform.spec.ts`, currently `.skip` pending staging seed).
- No architectural dependency between the two — Finding 1 changes the render gate; Finding 2 changes the DragOverlay label source. They compose cleanly.

**Combined fix arc LOC estimate: ~140-270 LOC total** (source + tests). Within a small-arc scope; should ship in a single session.

**Pre-flight discipline for fix arc:** verify HEAD; read `docs/investigations/2026-05-20-resize-handle-ux-refinements.md` (this document) + `docs/investigations/2026-05-20-free-form-focus-canvas.md` (referenced parent investigation) before drafting code.

**Test discipline for fix arc:**
- Finding 1: unit tests for hover-on / hover-off render gate on `FreeFormPlacedWidget`; integration test on `FocusBuilderPage` driving pointer-enter on a widget and asserting handle render WITHOUT click.
- Finding 2: pure-helper unit tests covering all four id-shape cases for `resolveDragLabel`; integration test on `FocusBuilderPage` driving a resize-handle drag-start and asserting DragOverlay content is absent (no UUID text in DOM).

Both findings honor the 2026-05-19 late-evening operator-observable canon: assert against rendered DOM (data-testid presence/absence for handles; text-content absence for the DragOverlay) at the specific rendered element.

---

## 6. Architectural surprises during investigation

1. **The same bug class affects ALL drag-id shapes, not just resize handles.** The whole-widget drag id (`free-form-placed-widget:<uuid>`) leaks via the same mechanism but wasn't operator-reported because the prefix made it look like a label rather than a UUID. Fix Finding 2 once and the whole-widget case fixes too, for free.

2. **`paletteItemIdToSlug` was never designed as a universal label resolver.** It was authored at FF-2 / FF-3 time when palette-drag was the only drag shape with a meaningful label. The `slug ?? id` fallback at `FocusBuilderPage.tsx:792` was a load-bearing safety net for an as-yet-unwritten future. FF-4's resize handles arrived and the fallback started leaking visibly. The proper fix is a dedicated `resolveDragLabel` resolver that knows about all id shapes — not extending `paletteItemIdToSlug` to know about non-palette ids (which would confuse the function's name and the related test contract at `FocusBuilderPalette.test.tsx`).

3. **`ResizeHandleOverlay` is genuinely innocent.** First instinct was that FF-4's substrate was the source of the leak (resize handles are the operator-visible new thing). Reading every line of `ResizeHandleOverlay.tsx` confirmed no text rendering anywhere. Discipline: read both the proposed source AND adjacent suspects before locking the candidate.

4. **The Q-10 lock predates operator hands.** It was the right answer for the investigation-time question ("what does Figma do?") but the wrong answer for the operator-time question ("what feels right when manipulating?"). The discovered process canon (investigation-time UX locks may need operator-experience refinement) is itself a candidate for canon entry post-fix.

5. **The DragOverlay is genuinely useful for one shape (palette drag) and net-negative for two shapes (whole-widget drag, resize drag).** Suppressing it for the latter two via `null` return is correct; the overlay shape stays in the codebase ready for future drag-id shapes that genuinely need a floating label.

---

## 7. References

- `docs/investigations/2026-05-20-free-form-focus-canvas.md` — parent FF-series investigation; Q-10 lock at §Q-10.
- `frontend/src/bridgeable-admin/components/focus-builder/FreeFormPlacedWidget.tsx:225` — current selection-conditional render of ResizeHandleOverlay.
- `frontend/src/bridgeable-admin/components/focus-builder/ResizeHandleOverlay.tsx:148-189` — handle render (confirmed no text content).
- `frontend/src/bridgeable-admin/components/focus-builder/FocusBuilderPage.tsx:789-793` — `handleDragStart` with the `slug ?? id` fallback.
- `frontend/src/bridgeable-admin/components/focus-builder/FocusBuilderPage.tsx:1302-1315` — DragOverlay rendering `activeDragLabel` as visible text.
- `frontend/src/bridgeable-admin/components/focus-builder/FocusBuilderPalette.tsx:39` — `paletteItemIdToSlug` definition (returns null for non-palette ids).
- `frontend/src/bridgeable-admin/components/focus-builder/FocusBuilderPalette.test.tsx:44-49` — unit-test evidence of null return.
- `frontend/package.json:@dnd-kit/core` — `^6.3.1` (default DragOverlay behavior renders provided children at cursor position).
- `DECISIONS.md:280` — 2026-05-19 late-evening operator-observable canon (asserts against rendered DOM at the specific element).
- `STATE.md:15` — FF-4 substrate entry (commit `c5d71c7`, ResizeHandleOverlay introduction).

---

## 8. Locked decisions summary

| Concern | Decision | LOC est | Source candidate |
|---|---|---|---|
| Finding 1 — handle visibility | **(a) Hover OR selection** | ~30-60 | `FreeFormPlacedWidget.tsx:225` render gate |
| Finding 2 — UUID text glitch | **Suppress DragOverlay for non-palette ids via `resolveDragLabel`** | ~40-80 | `FocusBuilderPage.tsx:792` (label assignment) + `:1312` (render) |
| Q-10 refinement canon | **File AFTER fix arc lands** | n/a | new `DECISIONS.md` entry |
| Fix arc shape | **Single combined dispatch** | ~140-270 total | new arc `resize-handle-ux-fixes` |

Ready for fix-arc dispatch.
