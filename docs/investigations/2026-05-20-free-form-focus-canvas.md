# Free-Form Focus Canvas Investigation

Date: 2026-05-20
Purpose: Lock architectural decisions for the **FF-series** arc — the operator-facing **free-form Focus canvas substrate** that supersedes F-series's grid-based widget rows on Decide canvas (Focus instances) while preserving F-series's Monitor canvas (dashboards, Pulse) substrate verbatim.
Status: Investigation closed; 40 questions answered (37 locked, 3 deferred-with-reason), 3 architectural risks surfaced with mitigations, decomposition into 7 sub-arcs.
Pre-flight: HEAD verified `0fa9ce1` (Monitor-vs-Decide canon entry, 2026-05-20).
Estimated total FF-series LOC: ~8,000–11,500 across 7 sub-arcs (range; see §Sub-arc decomposition).
Recommended dispatch shape: **FF-1 → FF-2 → FF-3 → FF-4 → FF-5 → FF-6 → FF-7**, in order, no interleaving.

---

## Context

Yesterday's 2026-05-20 canon entry (`DECISIONS.md`) established a load-bearing architectural distinction: **Monitor canvas (grid model) and Decide canvas (free-form model) are architecturally distinct substrate concerns**. The three-primitive decomposition (Spaces = Monitor, Command Bar = Act, Focus = Decide) translates into distinct canvas substrates.

- **Monitor canvas** (Pulse, dashboards, anomaly surfaces, activity feeds) composes persistent context that holds across many variables — different tenants, time periods, role contexts, operational states. The grid model (12-column row-based placement with `starting_column` + `column_span` + `row_index`) is correct for Monitor canvas because **structured composability across high variability** is the load-bearing constraint. F-series established this grid substrate canonically.
- **Decide canvas** (Focus instances) composes bounded workspaces in service of closing a specific named decision. The canvas exists for the duration of the active decision; the operator actively manipulates canvas contents in service of closing that decision (drag widget to better position, resize widget for current task, dismiss widget when no longer useful). The free-form model (per-placement `x` / `y` / `width` / `height` with `z-index`) is correct for Decide canvas because **operator-driven flexibility within the decision scope** is the load-bearing constraint.

The operator motivation (from the canon entry): shift-click two funeral orders → contextual route-map widget that the operator resizes to read cemetery routes → ten minutes later, when reviewing the next order's timing, the operator dismisses the widget entirely. Grid-snapped manipulation fights this workflow; free-form serves it.

**F-series canonical decisions inherited forward:**
- **Placement structural immutability for cores** (2026-05-19 canon entry). Cores are canonical decision substrate; they remain anchored at canonical positions on Focus canvas. Free-form positioning applies to **widgets only**.
- **Unified-placement model**. Cores and widgets are placements; the core is distinguished by its fixed-but-visible status (`is_core: true` discriminator in JSONB per `_validate_placement` at `focus_templates_service.py:227-235`).
- **≥3 `configurableProps`** per registered widget (2026-05-19 canon entry).
- **F-3.1a's placement adapter pattern** (frontend chrome blob ↔ backend `prop_overrides`). The pattern itself remains canonical; FF-series extends the adapter to translate positioning fields alongside `chrome ↔ prop_overrides`.

**F-series substrate being modified:**
- `FocusBuilderCanvas.tsx` — `WidgetRowsLayer` + `PlacedWidget` render placements as CSS-grid rows BELOW the core. This substrate is replaced.
- `useFocusTemplateDraft.ts::WidgetPlacement` — currently `{ id, widget_slug, column_start, column_span, chrome }`. Shape gains positioning fields.
- `_placement-adapter.ts` — adapter pattern unchanged; field set extended.
- `_validate_placement` at `focus_templates_service.py:157-235` — validation rules extended for new fields.

**F-series substrate consumed unchanged:**
- `useFocusTemplateDraft` — debounce + save + version-bump + URL recovery pipeline (the multi-hook-mount canon + callback-ref canon hold).
- `chrome-resolver.ts` — per-placement chrome resolution is orthogonal to positioning.
- `FocusBuilderInspector.tsx` — gains positioning controls (Q-30) but the C-1 primitive composition pattern is preserved.
- `FocusBuilderSelectionContext` — selection model unchanged.

---

## Canonical UX target

The Decide canvas presents widgets as floating tablet-like surfaces the operator can summon, arrange, park, and dismiss. The interaction model invoked here is the Tony Stark / Jarvis pattern documented in `PLATFORM_INTERACTION_MODEL.md` — chips of context summoned into a workspace, freely arrangeable by the operator at the moment of decision-closure. Concretely:

```
┌─ Manufacturing › Production › Kanban dispatch › Scheduling FH evening ──┐
│  Auto-saved 12s ago                                                      │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  [Substrate atmosphere]                                                  │
│                                                                          │
│   ┌──────────────────────────────────────────┐  ┌─ TodayWidget ─┐        │
│   │ [Inherited core — anchored canonical pos]│  │ (free-form)   │        │
│   │                                          │  └───────────────┘        │
│   └──────────────────────────────────────────┘                           │
│                                                  ┌─ RouteMap ─────────┐  │
│       ┌─ AncillaryPoolPin (free-form) ─┐         │ (free-form, resize)│  │
│       └──────────────────────────────── ┘        └────────────────────┘  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

- Core anchored at canonical position (no operator manipulation of core position).
- Widgets free-form: operator drag-to-move, resize via corner handles, overlap permitted with explicit z-index.
- Background click → substrate + theme editing.
- Widget click → widget chrome + position editing.
- Selection state preserved across canvas + tree per F-2 canon.

---

## Locked decisions

### Positioning shape (Q-1 through Q-5)

#### Q-1: Positioning unit

**At stake:** What unit do `x` / `y` / `width` / `height` use? Pixels? Percentages? CSS subgrid? Rem? Logical units relative to canvas dimensions?

**Options:**
- (a) **Pixels** — `{ x: 240, y: 80, width: 320, height: 180 }`. Direct CSS values.
- (b) **Percentages** — `{ x: 25%, y: 10%, width: 40%, height: 30% }` of canvas. Resolution-independent.
- (c) **Normalized [0..1]** — same as percentages but as fractions.
- (d) **Hybrid** — pixels for size, percentages for position.

**Rationale:**
- (a) is the canonical free-form-canvas pattern (Figma, Sketch, raw SVG authoring). Operators reason in pixels when they're manually arranging.
- (b) and (c) introduce a "what's the canvas size?" coupling — if canvas dimensions vary (Q-2), a widget positioned at 50% on a 1200px canvas drifts to 50% of 1800px on a wider screen, which may NOT be what the operator wanted (they placed it next to a specific anchor).
- (d) is the worst of both — operator must reason in two units simultaneously.

Pixels couple positioning to canvas dimensions in the OTHER direction: if canvas grows, widgets stay in their absolute positions and may fall off-canvas or leave whitespace. Q-2 + Q-39 address this risk.

**LOCKED: (a) — pixels.** Aligns with operator mental model + Figma/Sketch precedent. Resolution-independence is addressed by Q-2's canvas-dimensions decision + Q-39's mitigation, not by switching positioning unit.

#### Q-2: Canvas dimensions

**At stake:** Is the canvas a fixed-size workspace, an expanding workspace, viewport-bound, or scrollable?

**Options:**
- (a) **Fixed canvas dimensions** (e.g., 1200×800) baked into the template. Operator scrolls if needed; widgets can't fall off because the canvas defines bounds.
- (b) **Viewport-bound** — canvas IS the viewport; resizing the window changes canvas dimensions. Widgets reflow.
- (c) **Expanding scrollable canvas** — operator drags widgets anywhere; canvas grows to contain them (Figma-style infinite canvas).
- (d) **Operator-configurable canvas dimensions** — each template declares its own canvas size in the inspector.

**Rationale:**
- (a) is the simplest model. Trade-off: a Focus authored on a 1920×1080 display may not fit a 1366×768 operator's screen well. Operator-side scroll/zoom handles this; the AUTHORING surface is consistent across operators.
- (b) makes positioning meaningless across operators with different display sizes. Authoring becomes per-display, which violates "share-a-Focus-with-coworker" plausibility.
- (c) is overkill for the bounded-decision use case. Focus instances are decision workspaces, not infinite-canvas creative work.
- (d) gives templates flexibility but introduces a configuration burden that doesn't pay for the bounded-decision use case.

**LOCKED: (a) fixed canvas dimensions baked per template.** Initial canvas dimensions: 1200×800 (matches F-series fixed-fit-to-viewport canvas at typical admin tooling display). The canvas dimensions live in `canvas_config` JSONB on `focus_templates` (already exists; currently empty). FF-1 stamps `canvas_config.width: 1200, canvas_config.height: 800` on new free-form templates. Per-template override possible via inspector (low priority follow-up; not in FF-1).

#### Q-3: Per-placement positioning fields shape

**At stake:** How do positioning fields appear in the JSONB placement record? Separate fields vs. blob?

**Options:**
- (a) **Separate top-level fields** — `placement = { placement_id, component_kind, component_name, x, y, width, height, z_index, prop_overrides, ... }`.
- (b) **Single positioning blob** — `placement = { ..., position: { x, y, width, height, z_index }, prop_overrides, ... }`.
- (c) **Carried in `prop_overrides`** — positioning IS a prop. Same blob.

**Rationale:**
- (a) parallels existing F-series fields (`starting_column`, `column_span` already top-level). Validator easier to write. Storage cost identical (JSONB doesn't care about nesting).
- (b) groups positioning concerns. Migration-friendly (single key to migrate from old to new shape).
- (c) is wrong — positioning is layout state, NOT a configurable prop. Conflating breaks the chrome-resolver semantics.

**LOCKED: (a) — separate top-level fields** `x`, `y`, `width`, `height`, `z_index` alongside existing `placement_id` / `component_kind` / `component_name` / `prop_overrides`. F-series's `starting_column` + `column_span` fields stay valid for Monitor canvas substrate (`column_span` is still meaningful as a sizing hint when a widget is constrained). FF placements on Decide canvas IGNORE `starting_column` + `column_span`; backend `_validate_placement` extends with conditional logic: if `x`/`y`/`width`/`height` present, the placement is free-form and grid fields are ignored. Pure-grid placements (Monitor canvas) keep their existing validation path.

#### Q-4: Default position for newly-dropped widgets

**At stake:** When a widget is dropped from the palette onto an empty canvas spot, where does it land?

**Options:**
- (a) **At the cursor's drop coordinate** — widget origin = drop point.
- (b) **Centered on the cursor's drop coordinate** — widget center = drop point.
- (c) **Cascading offset from previous drop** — each new widget offsets diagonally from the prior one (avoids stacking on a single point).
- (d) **First-available-empty-space** — collision-detect, snap to nearest empty region.

**Rationale:**
- (b) is the most natural — when an operator drops a 320×180 widget at coordinate (500, 300), the widget appears centered there, not anchored at the top-left. Matches Figma/Sketch precedent.
- (a) is anchor-at-corner which is less intuitive.
- (c) is overkill for the operator-driven workflow.
- (d) is hostile to operator intent — they meant to drop it RIGHT THERE.

**LOCKED: (b) — centered on cursor drop coordinate.** Drop event provides cursor (x, y); placement is created with `x = cursorX - defaultWidth/2`, `y = cursorY - defaultHeight/2`, clamped to canvas bounds.

#### Q-5: Default size for newly-dropped widgets

**At stake:** When a widget is dropped, what are its initial dimensions?

**Options:**
- (a) **Per-widget default declared in registry metadata** — each `RegistrationMetadata` gains optional `defaultDimensions: { width, height }`. Falls back to platform default if absent.
- (b) **Single platform default** — every widget starts at 320×180 (or similar canonical size). Operator resizes if needed.
- (c) **Per-widget aspect-ratio with platform-default width** — widget's `aspectRatio` (if declared) determines height from a fixed width.

**Rationale:**
- (a) is correct — a Map widget naturally wants 400×400 (square); a Today pin naturally wants 240×120 (compact pill). The widget author knows. Platform default fills the gap for unconfigured widgets.
- (b) wastes operator effort resizing every widget after drop.
- (c) only works for widgets with intrinsic aspect ratios; many don't have one.

**LOCKED: (a) — per-widget `defaultDimensions` in registry metadata + platform fallback** (320×180). `class-registrations.ts` already declares `canvasMetadata.defaultDimensions` for some widget classes; FF-1 backfills the fallback path. Existing F-3 widget seeds (Day Strip / Today Pin / Map) get explicit `defaultDimensions` in FF-2.

### Layering and overlap (Q-6 through Q-8)

#### Q-6: Z-index model

**At stake:** How is layer ordering established? Implicit (creation order) or explicit (per-placement `z_index` field)?

**Options:**
- (a) **Explicit per-placement `z_index` integer** — operator controls via send-to-front / send-to-back affordances. Storage: top-level field.
- (b) **Implicit creation order** — DOM order = z-stack. Last-added is topmost. Send-to-front means re-array.
- (c) **Hybrid** — implicit creation order with `z_index` override (`null` = inherit position; integer = explicit).

**Rationale:**
- (a) is the canonical Figma/Sketch model. Explicit, queryable, persistable, operator-controllable.
- (b) is brittle — re-arraying placements on send-to-front mutates positions in the rows blob, which interferes with stable placement IDs and confuses adapter round-trips.
- (c) introduces null-vs-integer ambiguity in resolution logic for negligible gain.

**LOCKED: (a) — explicit `z_index: number` per placement.** Default `z_index: 0` on creation. Send-to-front sets `z_index = max(existing) + 1`; send-to-back sets `z_index = min(existing) - 1`. CSS `z-index` applied directly. Core's placement has implicit `z_index: 0` (it can be overlapped per Q-22, but operators don't typically place widgets ON TOP of the core — see Q-22).

#### Q-7: Click-to-front behavior

**At stake:** When an operator clicks a widget, does it auto-promote to the top of the z-stack?

**Options:**
- (a) **Click promotes to front automatically.** Matches Sketch/Figma window-manager semantics.
- (b) **Click selects only; z-order changes require explicit send-to-front.**
- (c) **Click promotes only when selected widget would be visually occluded.**

**Rationale:**
- (a) matches operator intuition for stacked widgets but introduces a persistence pulse on every click (z_index change triggers save).
- (b) is cleaner — selection and z-order are independent. Operator's z-stack stays stable across selection.
- (c) is too clever — operator can't predict when promotion fires.

**LOCKED: (b) — selection does NOT promote.** Selection state and z-order are independent. Explicit affordances (inspector buttons, keyboard shortcuts `]` / `[` for forward/backward, `Shift+]` / `Shift+[` for to-front/to-back per Q-12 extension) control z-order. Save pulse fires only on explicit z-order action, not on every click. This matches the broader "selection is read state, manipulation is write state" model already established in F-2.

#### Q-8: Overlap visual treatment

**At stake:** When widgets overlap, what visual cues does the canvas provide?

**Options:**
- (a) **No special treatment** — z-stack governs, operator sees the layered result as-is.
- (b) **Subtle shadow stack** — the underneath widget gains a subtle shadow on its visible edges, indicating it's behind.
- (c) **Faded-when-occluded** — occluded portions of the underneath widget render at reduced opacity.

**Rationale:**
- (a) is honest and respects the operator's compositional intent.
- (b) is design-system territory and may conflict with existing shadow tokens.
- (c) modifies operator-authored visual; not appropriate.

**LOCKED: (a) — no special overlap treatment.** Operator-intentional overlap renders as-authored. The substrate's responsibility is to render what the operator placed; visual clarity is the operator's compositional decision. If a future operator-feedback signal demands a stacking-hint affordance, it lifts via design-system token addition, not substrate change.

### Manipulation gestures (Q-9 through Q-14)

#### Q-9: Drag-to-move initiation

**At stake:** Where does the operator grab to drag a widget? Anywhere on the widget body? A specific drag handle? Chrome-edge only?

**Options:**
- (a) **Anywhere on the widget body** — entire widget surface is drag-initiation. Click-without-drag selects.
- (b) **Dedicated drag handle** — small grip icon at top-left or top-edge.
- (c) **Chrome edge** — outer border region (5px from edge) is drag-initiation; interior is selection.

**Rationale:**
- (a) is the standard floating-tablet/window manipulation pattern. Distinguishing click from drag uses a small threshold (3px movement before drag starts).
- (b) adds visual chrome the operator must locate before manipulating.
- (c) creates a "magic invisible region" that operators don't discover.

**LOCKED: (a) — anywhere on widget body initiates drag.** Drag activation threshold: 3px movement before pointer-down resolves as drag vs. click. Click resolves to selection per F-2 canon. Widgets with interior interactive elements (buttons, inputs) get their own pointer-events scope; clicks on interior controls do NOT initiate drag. Per the established pointer-events contract documented in CLAUDE.md (Focus Canvas tier-renderer pointer-events contract), tier renderer is `pointer-events: none` and interactive descendants self-assert; widget body's draggable region is the outermost `pointer-events: auto` element.

#### Q-10: Resize handles

**At stake:** Which handles render on selected widgets? Corner only? Edge only? Both? Always-visible or on-hover?

**Options:**
- (a) **8 handles** (4 corners + 4 edges), visible only when selected.
- (b) **4 corner handles only**, visible only when selected. Edges are not directly resizable.
- (c) **8 handles** always-visible.

**Rationale:**
- (a) is canonical Figma/Sketch. Corner handles preserve aspect ratio with modifier; edges resize one dimension.
- (b) loses one-dimension resize which is common for stretching a route map wider without changing height.
- (c) clutters the canvas when many widgets present.

**LOCKED: (a) — 8 resize handles visible only when selected.** Corner handles preserve aspect ratio when `Shift` is held during drag (Figma precedent). Edge handles resize a single dimension. Handle visual: 8px square, accent-token-colored, rendered as absolutely-positioned children of the selection chrome layer.

#### Q-11: Snap-to-alignment

**At stake:** Does the canvas provide alignment helpers (snap-to-other-widgets, snap-to-canvas-center, snap-to-grid)?

**Options:**
- (a) **No snap, full free-form** — operator positions to-the-pixel without assistance.
- (b) **Figma-style invisible alignment helpers** — when a widget being dragged aligns with another widget's edge or center, a thin guide line appears and the position snaps. No persistent grid.
- (c) **Opt-in snap-to-grid** via Shift modifier or toolbar toggle.

**Rationale:**
- (b) is the gold standard for free-form-canvas alignment. Operator gets pixel-precision when needed AND snap-helpers when they aid composition.
- (a) is faithful to "pure free-form" but produces visually-unaligned widgets that look unintentional.
- (c) introduces a mode the operator must toggle — friction.

**LOCKED: (b) — Figma-style invisible alignment helpers.** Implementation: when dragging, compute proximity to other placements' edges + centers + canvas centerlines. Snap threshold: 6px (operator can override by holding Alt to disable snap during a specific drag). Guide lines render as 1px accent-token-colored overlays during the drag; disappear on release. Deferred to **FF-7 polish** rather than baseline FF-3 to ship the bare-minimum drag interaction first and add alignment polish once the gesture pipeline is proven.

#### Q-12: Keyboard nudge

**At stake:** Can the operator move widgets via arrow keys?

**Options:**
- (a) **Arrow keys nudge selected widget by 1px; Shift+arrow nudges by 10px.**
- (b) **Arrow keys not bound to widget movement; use drag only.**
- (c) **Arrow keys for nudge; Cmd+arrow for align to canvas edge.**

**Rationale:**
- (a) is canonical Figma/Sketch and aids accessibility (operators with motor difficulties can position via keyboard).
- (b) loses an a11y dimension.
- (c) adds align-edge as a discoverable affordance.

**LOCKED: (a) — arrow keys 1px, Shift+arrow 10px.** Keyboard z-order shortcuts per Q-7: `]` = forward, `[` = backward, `Shift+]` = to-front, `Shift+[` = to-back. Ships in FF-7 (alongside snap polish) rather than baseline FF-3.

#### Q-13: Minimum size constraints

**At stake:** How small can a widget be resized?

**Options:**
- (a) **Single platform minimum** — every widget bottoms out at 80×40 (or similar floor).
- (b) **Per-widget `minDimensions` in registry metadata** with platform fallback.
- (c) **Aspect-ratio-aware minimum** — derived from `defaultDimensions` * 0.25 floor.

**Rationale:**
- (b) is correct — a Map widget needs `min: 200×200` to remain legible; a Today pin can go down to `min: 100×40` and still serve. Authors know.
- (a) wastes legibility for some widgets, allows illegible others.
- (c) is heuristic-ish — author-declared is more reliable.

**LOCKED: (b) — per-widget `minDimensions` with platform fallback (80×40).** `class-registrations.ts` already supports `canvasMetadata.minDimensions`. FF-2 wires consumption + backfills for existing seeds.

#### Q-14: Maximum size constraints

**At stake:** Can a widget be resized larger than canvas dimensions?

**Options:**
- (a) **Canvas-bounded** — widget cannot exceed canvas dimensions in either axis.
- (b) **Viewport-bounded** — widget cannot exceed viewport (browser window).
- (c) **Unbounded** — widget can be any size; operator scrolls.

**Rationale:**
- Q-2 locked fixed canvas dimensions, so canvas-bounded (a) is the natural fit. Widgets larger than canvas can't render visibly anyway without scroll.
- (b) is awkward because viewport changes when admin chrome collapses/expands.
- (c) breaks the bounded-decision model.

**LOCKED: (a) — canvas-bounded.** Resize gestures clamp at canvas dimensions. Per-widget `maxDimensions` (optional) in registry metadata further constrains. No platform-default maximum beyond canvas bounds.

### Selection and multi-select (Q-15 through Q-19)

#### Q-15: Single-select model (confirmation)

**At stake:** F-2 established `FocusBuilderSelectionContext` with single-selection (`selection.kind` + `selection.id`). Confirm this carries forward to FF-series.

**LOCKED: confirmed unchanged.** Single-select model from F-2 (`FocusBuilderSelectionContext`) is preserved. FF-series does NOT add multi-select to the inspector — multi-select on canvas (Q-16) drives canvas-level operations (move, align) but NOT inspector-level multi-edit.

#### Q-16: Multi-select on canvas

**At stake:** Can operators select multiple widgets for canvas-level operations (move-together, align-together)?

**Options:**
- (a) **Shift+click adds to selection; marquee drag selects rectangle of widgets.**
- (b) **Shift+click only; no marquee.**
- (c) **No multi-select** — operator handles one widget at a time.

**Rationale:**
- Multi-select on the operator-driven workspace is genuinely useful: shift-click two related widgets (route map + today pin) and drag-move both. Marquee enables fast bulk-arrange.
- F-2 deferred multi-select because the inspector composition (mixed-prop edit) is its own UX surface. Canvas-level multi-select doesn't entail multi-edit (Q-18).
- F-series deferred this entirely; FF-series can ship it canvas-only without entering multi-edit territory.

**LOCKED: (a) — shift+click + marquee.** Multi-select state lives in `FocusBuilderSelectionContext` as a Set of ids (`selection.kind === "widgets-multi"` discriminator). Marquee drag begins on empty-canvas pointer-down + 3px threshold. Implementation deferred to **FF-7 polish** rather than FF-3 baseline — multi-select is a power-user affordance and the canvas baseline needs single-select working first.

#### Q-17: Multi-select canvas actions

**At stake:** What can the operator do with multiple widgets selected?

**Options:**
- (a) **Move together** — drag any selected widget; all move in lockstep.
- (b) **Move + align** — toolbar gains align-left/center/right/top/middle/bottom affordances applied across the selection.
- (c) **Move + align + distribute** — also even-spacing affordance.

**Rationale:** (b) is the canonical floor; (c) is polish. (a) alone is too thin to justify multi-select infrastructure.

**LOCKED: (b) — move together + align affordances (no distribute).** Align affordances surface in the inspector when multi-select is active (the inspector renders an "Align" section in place of widget-specific controls). Distribute affordance deferred post-arc.

#### Q-18: Multi-select inspector behavior

**At stake:** When multi-select is active, what does the inspector show?

**Options:**
- (a) **Align/distribute affordances only.** No prop editing.
- (b) **Mixed-state prop editor** — for props all selected widgets share, show the value (or "mixed" indicator if values differ); allow edit applies to all.
- (c) **Disabled state — "Select a single widget to edit."**

**Rationale:**
- (a) is the right scope for FF-series. Multi-edit (b) is a substantial UX surface (mixed-state rendering, batch-update semantics, partial-failure handling) that doesn't pay for the bounded-decision canvas use case.
- (b) lifts when operator demand surfaces.
- (c) is hostile.

**LOCKED: (a) — align affordances only.** Multi-edit deferred per same reasoning as F-2 Q-15.

#### Q-19: Selection across canvas + tree

**At stake:** When the operator clicks a tree leaf (e.g., switches to another template), does canvas selection clear?

**LOCKED: yes — selection clears on subject change.** Subject-change is a context shift; selection is canvas-scoped state. This mirrors F-2 behavior and stays unchanged.

### Inherited core anchoring (Q-20 through Q-22)

#### Q-20: Where does inherited core render on free-form canvas

**At stake:** The core was previously rendered ABOVE widgets in a flex-col layout (F-3 substrate). Where does it render in free-form land?

**Options:**
- (a) **Canonical anchored position** — center-top of canvas, e.g., `{ x: (canvas_width - core_width) / 2, y: 40 }`. Operator cannot move it (Q-22).
- (b) **Core declares its own anchor position** in `focus_cores.canvas_anchor: { x, y }`.
- (c) **Templates can override core position** in `canvas_config.core_anchor`.

**Rationale:**
- (a) maintains the structural-immutability canon — core position is canonical, not template-authored.
- (b) gives core authors flexibility but creates a sprawl-of-positions problem (every core picks its own).
- (c) violates structural-immutability outright.

**LOCKED: (a) — canonical anchored position.** Computed from canvas dimensions + core's `default_column_span` (re-interpreted as a width hint when on free-form canvas). Formula: `core_width = canvas_width * (default_column_span / 12)`, `core_x = (canvas_width - core_width) / 2`, `core_y = 40` (top margin). Core's `z_index` is structurally 0 (lowest); widgets can overlap (Q-22 elaborates).

#### Q-21: Core size

**At stake:** Is the core a fixed size? Operator-resizable? Per-template configurable?

**Options:**
- (a) **Computed from canvas dimensions + core's `default_column_span`** — fixed per template, derived from existing field.
- (b) **Operator-resizable** — drag core resize handles like a widget.
- (c) **Per-template configurable in inspector** but not directly draggable.

**Rationale:**
- (a) preserves structural immutability per canon. Core's size derives from data the core already declares.
- (b) violates structural immutability.
- (c) is a middle ground but lacks motivating use case.

**LOCKED: (a) — computed from `default_column_span`.** Core size is data-derived, operator-invariant.

#### Q-22: Can widgets overlap the inherited core

**At stake:** With free-form positioning, widgets COULD overlap the core. Is this permitted?

**Options:**
- (a) **Permitted** — overlap is the operator's compositional choice. Z-index governs visual stacking; core has `z_index: 0` so widgets above it render on top.
- (b) **Forbidden** — drop/move/resize that would overlap the core is rejected with snap-back.
- (c) **Permitted only when widget z-index < core z-index** — widgets can render BEHIND the core but not ON TOP.

**Rationale:**
- (a) matches the broader "operator owns canvas composition" model. If the operator wants a small contextual widget overlapping the core's corner, the substrate doesn't second-guess.
- (b) is paternalistic and conflicts with the operator-flexibility load-bearing constraint per the canon entry.
- (c) is a clever middle ground but operators don't think in z-stack ordering when overlapping.

**LOCKED: (a) — overlap permitted; z-index governs.** Core's structural immutability is about POSITION, not z-stack invariance. Operators bear responsibility for compositions they author; the substrate doesn't enforce visual-design rules.

### Persistence (Q-23 through Q-27)

#### Q-23: Backend schema migration

**At stake:** Does the placement schema gain new columns? Or are positioning fields purely JSONB additions?

**Options:**
- (a) **Pure JSONB extension** — `_validate_placement` gains conditional logic accepting `x` / `y` / `width` / `height` / `z_index`. No DDL migration.
- (b) **Augment with relational columns** for queryability (e.g., a future "find all placements at z_index > 10" query).
- (c) **Replace grid fields** — drop `starting_column` / `column_span` validation; require new fields. Breaks Monitor canvas substrate.

**Rationale:**
- (a) is correct. Placements live entirely in `focus_templates.rows` JSONB. Adding fields = updating the validator. Zero DDL. Same approach F-series took.
- (b) is premature; no query demands it.
- (c) breaks Monitor canvas substrate. Verboten per Monitor-vs-Decide canon.

**LOCKED: (a) — pure JSONB extension.** `_validate_placement` gains a conditional branch: if `x` / `y` / `width` / `height` are present, the placement is treated as free-form and validated against canvas dimensions + per-widget min/max. If grid fields (`starting_column` / `column_span`) are present without free-form fields, validation continues on the F-series path. Both shapes co-exist in the same column. FF-1's "migration" is purely a validator extension at `focus_templates_service.py:189-212` (parallel branch added; existing branch preserved for grid-shaped placements). Migration head stays at `r103_focus_templates_edit_session`.

#### Q-24: Migration of existing F-series seeded templates

**At stake:** F-series seeded `scheduling-fh` + `scheduling-mfg` templates with grid-shaped placements. Do they migrate to free-form on FF-1 ship?

**Options:**
- (a) **No migration — grid placements stay grid; new templates start free-form.** Coexistence at the data level.
- (b) **One-time migration script** translates grid placements to equivalent free-form coordinates.
- (c) **Per-template opt-in toggle** — operator picks "this template is free-form" or "grid" at template creation.

**Rationale:**
- (a) is the simplest model. The two seeded templates' grid placements stay valid because the F-series validator branch stays in place. The Focus Builder canvas adapts based on placement shape detection.
- (b) introduces a translation step that may not produce visually-equivalent results (grid columns don't map cleanly to pixel positions without canvas dimension assumptions).
- (c) introduces a template-level mode that complicates the substrate. Per the canon entry, Monitor canvas IS grid and Decide canvas IS free-form; the distinction is at the SURFACE level (which canvas substrate the template is consumed by), not a per-template toggle.

**LOCKED: (a) — no migration.** Existing grid placements stay valid; the canvas renderer (FF-2) detects placement shape per-row and renders accordingly. New templates authored in Focus Builder default to free-form (FF-2 forward). Templates intended for Monitor canvas (dashboards, Pulse) continue to use grid shape per their authoring surface (TBD per future Page Builder investigation).

#### Q-25: Adapter extension

**At stake:** F-3.1a's `_placement-adapter.ts` translates field names + index conventions. How does it extend to positioning fields?

**Options:**
- (a) **Add positioning fields to the adapter** — `frontendToBackendPlacement` includes `x` / `y` / `width` / `height` / `z_index` in the output; `backendToFrontendPlacement` reads them on input.
- (b) **Carry positioning in `chrome` blob** — positioning lives inside `chrome.position: { x, y, ... }` on the frontend, translated to `prop_overrides.position` on the backend. Same shape on both sides.
- (c) **Parallel positioning blob** — `placement.position: { x, y, w, h, z }` on the frontend, mirrors `placement.position` on the backend.

**Rationale:**
- (a) parallels F-3.1a's existing field-mapping treatment. Off-by-one logic for `starting_column` ↔ `column_start` stays valid for grid-shaped placements; new positioning fields ARE the same on both sides (pixel coordinates, no index convention).
- (b) overloads `chrome` semantically — positioning is layout, not chrome. Violates F-3.1a's documented field-mapping semantics (canon entry: "chrome stores the full per-placement override surface" but specifically excluded layout).
- (c) duplicates per-placement structure for negligible gain.

**LOCKED: (a) — adapter extended with new fields.** Per Q-3's separate-top-level-fields decision, the adapter treats `x` / `y` / `width` / `height` / `z_index` as direct 1:1 round-trip fields (no index convention translation; pixel coordinates are identical on both sides). Frontend `WidgetPlacement` shape gains the same fields. Existing fields (`column_start` / `column_span` / `chrome` ↔ `starting_column` / `column_span` / `prop_overrides`) continue working unchanged.

#### Q-26: Persistence across operator sessions

**At stake:** Free-form positioning produces lots of small changes (every nudge is a state change). How does the save pipeline handle this?

**LOCKED: existing debounced save pipeline carries forward.** `useFocusTemplateDraft`'s 300ms-debounced auto-save handles positioning changes identically to chrome edits. A burst of drag events produces one save at the end of the burst. Edit-session semantics + 410-retry + URL recovery from F-3.1a.2 inherit forward unchanged. No new save infrastructure needed.

#### Q-27: Per-user vs per-tenant layout state

**At stake:** Free-form positioning is operator-driven. Does each operator get their OWN free-form layout, or is the layout per-tenant (every operator on the tenant sees the same arrangement)?

**Options:**
- (a) **Per-tenant** — three-scope inheritance holds (platform_default → vertical_default → tenant_override). All operators on the tenant see the tenant's layout.
- (b) **Per-user override layer added** below tenant_override. Operator can author their own arrangement.
- (c) **Per-Focus-instance** — when a Focus is opened, the operator's manipulation is scoped to that instance; instance state persists per-user.

**Rationale:**
- (a) preserves the F-series three-scope inheritance model. Simplest. Matches how dashboards work.
- (b) introduces a fourth scope layer for substantial UX gain (operator's preferred arrangement) but substantial substrate cost (new scope, new resolver, new endpoint). Defer post-arc.
- (c) is the canon-vibed answer per the 2026-05-20 entry ("operator's per-decision workspace is their own working surface") but requires Focus-instance substrate (instance vs template distinction) that doesn't exist yet.

**LOCKED: (a) — per-tenant three-scope inheritance** for FF-series. The per-user / per-Focus-instance personalization layer is **deferred per Q-37** as a follow-up substrate concern requiring Focus-instance modeling first. The locked decision matches F-series's substrate scope; FF-series adds free-form positioning to the SAME scope model, not a new scope dimension.

### Canvas substrate replacement (Q-28 through Q-29)

#### Q-28: FocusBuilderCanvas's WidgetRowsLayer

**At stake:** F-3 shipped `WidgetRowsLayer` rendering rows of grid-positioned widgets BELOW the core. Free-form positioning makes the rows-grid model obsolete on Decide canvas.

**Options:**
- (a) **Replace `WidgetRowsLayer` with `WidgetFreeFormLayer`** — new component renders free-form-positioned widgets via absolute positioning.
- (b) **Refactor `WidgetRowsLayer` to support both modes** — detect placement shape per-row; render grid OR free-form.
- (c) **Keep both side-by-side** — `WidgetRowsLayer` continues for grid-shaped rows; `WidgetFreeFormLayer` for free-form placements.

**Rationale:**
- (a) is the cleanest — Decide canvas is free-form-only; Monitor canvas (dashboards, future Page Builder) has its own canvas component using `WidgetRowsLayer` or analogous. Focus Builder's canvas swaps to `WidgetFreeFormLayer`.
- (b) creates a polymorphic component handling both rendering models — high complexity, low reuse value.
- (c) coexistence path; valid IF Focus Builder needs to render mixed grid + free-form placements (some templates partially-migrated). Per Q-24 (no migration), templates are 100% one shape or the other.

**LOCKED: (a) — replace `WidgetRowsLayer` with new `WidgetFreeFormLayer` in `FocusBuilderCanvas`.** `WidgetRowsLayer` is preserved as a library component for future Monitor canvas consumption (e.g., the Page Builder's dashboard authoring surface that ships post-FF). Focus Builder's canvas in FF-2 forward consumes `WidgetFreeFormLayer` only.

#### Q-29: PlacedWidget wrapper

**At stake:** `PlacedWidget` in F-3.1c wraps each placement in selection chrome + chrome resolution + grid-column positioning. How does free-form positioning interact with chrome rendering?

**Options:**
- (a) **Extend `PlacedWidget` with absolute positioning** — same component, render-mode discriminator.
- (b) **New `FreeFormPlacedWidget` component**; keep `PlacedWidget` grid-only.
- (c) **Compose** — extract chrome+selection logic into a shared wrapper; `PlacedWidget` and `FreeFormPlacedWidget` are thin positioning shells around it.

**Rationale:**
- (c) is the cleanest factoring. Chrome resolution + selection chrome + click handlers are positioning-agnostic; they extract cleanly.
- (a) makes `PlacedWidget` carry positioning-mode state. Mid-complexity.
- (b) duplicates chrome+selection logic. Lowest factoring.

**LOCKED: (c) — extract `PlacedWidgetCore` (chrome + selection + click handlers) as shared inner wrapper; `PlacedWidget` (grid) and `FreeFormPlacedWidget` (absolute) become positioning shells.** This is a small refactor (~50 LOC) that ships in FF-2 alongside the new free-form layer. The shared inner component lives at `components/focus-builder/PlacedWidgetCore.tsx`.

### Inspector implications (Q-30 through Q-31)

#### Q-30: Inspector showing positioning fields

**At stake:** When a widget is selected, does the inspector show positioning fields (x, y, w, h, z) as editable inputs?

**Options:**
- (a) **Canvas-only manipulation; inspector shows positioning READ-ONLY** as informational display.
- (b) **Inspector exposes positioning as editable numeric inputs** alongside chrome controls.
- (c) **Both** — inspector shows position numerically; operator edits canvas OR inspector; bidirectional sync.

**Rationale:**
- (c) is the Figma model. Power-users edit numerically when they need pixel precision; visual users drag. Both paths update the same state.
- (a) loses the precision affordance.
- (b) is sufficient but loses the visual feedback loop.

**LOCKED: (c) — inspector exposes editable positioning fields alongside canvas drag.** New "Position" section in the widget inspector (below chrome, above class-level chrome) renders four numeric inputs (X, Y, Width, Height) + a z-index control with send-to-front / send-to-back buttons. Inputs commit on blur + Enter. Drag/resize from canvas updates same state, reflected in inputs live.

#### Q-31: Z-index in inspector

**At stake:** Where do operators access z-order controls?

**Options:**
- (a) **Inspector buttons** — "Bring to front" / "Send to back" / "Forward" / "Backward".
- (b) **Canvas context menu** (right-click).
- (c) **Both.**

**Rationale:**
- (a) is discoverable.
- (b) is fast for power users.
- (c) both wins.

**LOCKED: (c) — both.** Inspector ships the four buttons (Q-30). Right-click canvas context menu replicates the same options. Keyboard shortcuts per Q-12 (`]` / `[` / `Shift+]` / `Shift+[`) ship in FF-7 alongside other keyboard nudge work.

### Deferred for later (Q-32 through Q-37)

#### Q-32: Layout templates (save free-form arrangement as reusable layout)

**Deferred** with reason: layout templates introduce a new persistence surface (named layouts table or layouts JSONB substrate). Substantial substrate work for unclear demand. Defer until operator demand surfaces post-FF ship.

#### Q-33: Mobile/touch interactions

**Deferred** with reason: Focus Builder is admin-only desktop tooling. Touch interactions for free-form drag/resize require gesture state machines + larger touch targets + viewport-bound canvas adjustments that don't pay for admin use case. Defer indefinitely; revisit if operator-facing Focus instances (vs Focus Builder authoring) need mobile.

#### Q-34: Collaborative cursors during free-form arrangement (Liveblocks/Yjs)

**Deferred** with reason: multi-operator concurrent editing is a substantial substrate concern (operational transform / CRDT / conflict resolution semantics over JSONB placements). No current substrate for collaborative editing exists. Defer post-FF; revisit when authoring substrate demands it.

#### Q-35: Smart positioning engine (intelligence-driven)

**Deferred** with reason: AI-assisted "place this widget intelligently" requires substantial intelligence-substrate integration + heuristics for "what's a good placement" that no canonical answer exists for. Defer post-FF; revisit when AI authoring patterns emerge.

#### Q-36: "Tidy up" auto-arrangement button

**Deferred** with reason: auto-tidy implies the substrate has an opinion about ideal arrangement, which conflicts with the operator-flexibility canon. If operators want grid-snapped layouts, they author on Monitor canvas substrate. Defer indefinitely.

#### Q-37: Multi-select for cross-widget operations (Focus item data, not canvas widgets — flag distinction)

**Deferred** with reason — **but with explicit distinction-flag**: this question conflates two different concepts.

- **Canvas widget multi-select** (Q-16): selecting multiple PLACED WIDGETS on the canvas for move/align operations. **LOCKED in Q-16 (a); ships in FF-7.**
- **Focus item data multi-select**: selecting multiple ITEMS within a single widget's data (e.g., shift-clicking two funeral orders in the kanban core to trigger contextual action). This is a substrate concern at the FOCUS RUNTIME level (how operators interact with Focus INSTANCES post-arrangement-authoring), not the Focus Builder authoring level. Belongs to a separate Focus instance interaction-model arc.

**Deferred Focus-item-data multi-select with the reason: it's a different substrate concern than canvas widget multi-select.** The operator-motivation example from the 2026-05-20 canon entry ("shift-click two funeral orders → route-map widget appears") describes Focus INSTANCE behavior, not Focus Builder authoring. FF-series authors the canvas; Focus runtime substrate handles instance-level multi-select on item data. The two have orthogonal substrate concerns.

---

## Architectural risks

### Q-38: Free-form positioning + automatic layout migration (operator mid-edit during deploy)

**Risk:** An operator with the Focus Builder open is editing free-form positioning when a deploy lands that changes positioning validation (e.g., FF-1 ships and an operator was authoring a template against pre-FF-1 backend). Operator's debounced save fires; backend rejects with a validation error the frontend doesn't expect. Operator's work is lost OR persisted partially.

**Mitigations:**
- FF-1's validator extension is **purely additive** — existing grid-shape placements remain valid; new free-form-shape placements are newly-accepted. The "operator mid-edit during deploy" risk is therefore limited to operators authoring on the FF-2-shipped canvas before FF-1's validator is deployed. Sequencing FF-1 (backend) BEFORE FF-2 (frontend) eliminates this window.
- F-3.1a.2's 410-retry pattern handles version-bump-mid-edit gracefully; positioning changes follow the same save path so the same recovery applies.
- If a 422 surfaces from the boundary anyway, the existing error UI from F-3.1a.2 surfaces it.

**LOCKED mitigation: FF-1 dispatches before FF-2.** FF-1 is backend-only (validator extension + adapter extension + tests). FF-2 is frontend-only (canvas substrate replacement consuming the FF-1 adapter shape). Sequential dispatch eliminates the deploy-race risk. Build report MUST confirm FF-1 ships before FF-2 dispatches.

### Q-39: Per-tenant variability of canvas dimensions (screen-size-dependent positioning overflow)

**Risk:** An operator on a 1366×768 laptop authors a Focus template at canvas-dimensions 1200×800. Another operator on the same tenant opens it on a 1920×1080 display — canvas dimensions are 1200×800 (fixed per template per Q-2), so widgets render at their authored positions. The smaller-display operator sees vertical scroll; the larger-display operator sees a 1200×800 canvas with empty surround. Both are acceptable. The REAL risk: an operator authoring on a 1920×1080 display drops widgets in positions beyond what a 1366×768 operator can scroll to comfortably.

**Mitigations:**
- Canvas dimensions are fixed per template (Q-2). Authors knowingly compose within that bound; consumers see the same canvas.
- Resize gestures clamp at canvas bounds (Q-14), so widgets can't escape.
- Per-template canvas dimensions are configurable (Q-2 follow-up); a tenant that needs larger canvas can override.
- Operator-side viewport that's smaller than canvas dimensions gets scroll. Acceptable.

**LOCKED mitigation: canvas dimensions baked into `canvas_config.width` / `.height` per template; default 1200×800; per-template override is a low-priority follow-up.** Operators authoring on large displays should size canvases responsibly; per-template override exists when they don't. No further substrate action needed.

### Q-40: Integration test infrastructure for drag interactions (JSDOM weakness vs operator-observable assertion canon)

**Risk:** F-series's operator-observable assertion canon (2026-05-19 late-evening entry) requires integration tests that assert at the rendered element. Drag interactions in JSDOM are notoriously brittle — JSDOM doesn't implement HTML5 drag events, doesn't compute layout, doesn't compute getBoundingClientRect properly. The @dnd-kit library used in F-3 has a `KeyboardSensor` that works in JSDOM but `PointerSensor` does not. Free-form drag-to-move + resize-handle drag both rely on pointer events.

**Mitigations:**
- **FF-3 baseline integration tests use @dnd-kit's `KeyboardSensor` test path** — drive drag via keyboard events (Space to grab, arrow keys to move, Space to drop). Asserts at the rendered element's `style.left` / `style.top` post-drop per operator-observable canon.
- **FF-4 resize tests use direct hook invocation** — call `updateWidget(id, { width, height })` and assert at the rendered element. The drag-gesture portion (pointer events to position deltas) is unit-tested separately at the gesture-state-machine level.
- **Visual drag-from-pointer tests defer to Playwright** in FF-7. Cross-side rendering of pointer-event-driven gestures requires a real browser. CI gate at FF-7 finale.
- Operator-observable canon is preserved: `element.style.left === "120px"` is asserted at the rendered `<div data-testid="focus-builder-placed-widget">`, not at a wrapper.

**LOCKED mitigation: FF-3 + FF-4 use @dnd-kit KeyboardSensor + direct hook-invocation integration tests; FF-7 adds Playwright pointer-event coverage as CI gate.** This split honors operator-observable canon while accepting JSDOM constraints documented in F-3.1c.

---

## Sub-arc decomposition

FF-series decomposes into 7 sub-arcs. Each sub-arc falls under ~2,500 production LOC (consistent with C-2 / F-series decomposition ceiling per DECISIONS.md 2026-05-13 PM), ships visibly, and has no interleaving dependencies beyond sequential ordering.

### FF-1 — Backend schema validator extension + adapter extension

**Scope.** Extend `_validate_placement` at `focus_templates_service.py:189-235` with a free-form branch: when `x` / `y` / `width` / `height` are present in a placement dict, validate as positive numbers within canvas bounds (read from row's parent template's `canvas_config.width` / `.height`, defaulting 1200×800), validate `z_index` as integer (default 0), and skip the `starting_column` / `column_span` / `column_count` exceeds check. Both shapes (grid + free-form) co-exist in the same column. Extend `_placement-adapter.ts` per Q-25: `frontendToBackendPlacement` includes positioning fields; `backendToFrontendPlacement` reads them. Frontend `WidgetPlacement` interface in `useFocusTemplateDraft.ts` gains `x?: number`, `y?: number`, `width?: number`, `height?: number`, `z_index?: number`. Hook helpers (`addWidget` / `updateWidget` / `removeWidget`) accept positioning fields. Backend tests verify both shapes accepted; mixed shape (grid + free-form within same template) rejected with clear error message.

**Estimated LOC.** ~800–1,200 (production + tests + parity tests against existing grid templates).

**Ships visibly.** Backend accepts free-form-shaped placements. No frontend change yet — operators see no visible difference. Build verification via backend tests + adapter round-trip tests.

**Dependencies.** Q-1, Q-2, Q-3, Q-4, Q-5, Q-23, Q-24, Q-25 — all LOCKED.

**Deferred-decision flags for FF-1:** Q-27 (per-user vs per-tenant layout state) confirms three-scope inheritance unchanged; no FF-1 work required.

### FF-2 — Canvas substrate replacement (WidgetRowsLayer → WidgetFreeFormLayer)

**Scope.** New `WidgetFreeFormLayer` component at `components/focus-builder/WidgetFreeFormLayer.tsx`. Renders free-form-positioned widgets via absolute positioning + CSS `transform: translate(x, y)`. Extract `PlacedWidgetCore` (chrome + selection + click handlers) per Q-29 (c). `PlacedWidget` (grid) preserves prior behavior; `FreeFormPlacedWidget` (absolute positioning) is the new shell. Canvas renders core at canonical anchored position per Q-20 (computed from canvas dimensions + core's `default_column_span`). Drop coordinates from @dnd-kit translate to free-form `x` / `y` via Q-4 (centered on cursor) using the new `defaultDimensions` lookup per Q-5. Existing F-series grid template renders preserved (FocusBuilderCanvas mode detection: free-form vs grid based on placement shape). FocusBuilderCanvas's `mode === "template"` branch checks placement shape and routes to `WidgetFreeFormLayer` OR `WidgetRowsLayer`. New seeded templates default to free-form.

**Estimated LOC.** ~1,500–2,200.

**Ships visibly.** Operator can drop widgets onto canvas; widgets land at drop coordinate with default size. NO drag-to-move yet (FF-3). NO resize yet (FF-4). Widgets sit where dropped.

**Dependencies.** FF-1 ships first. Q-2, Q-4, Q-5, Q-13, Q-14, Q-20, Q-21, Q-22, Q-28, Q-29 LOCKED.

### FF-3 — Drag-to-move

**Scope.** Drag handle wiring via @dnd-kit (consistent with F-3 canon). PointerSensor + KeyboardSensor configured per Q-9. Drag activation threshold 3px. Pointer-down anywhere on widget body initiates drag (Q-9). Position state updates via hook's `updateWidget(id, { x, y })`. Persistence via auto-save (existing pipeline per Q-26). Drop-target = canvas itself; on drag-end, `delta.x` / `delta.y` added to current placement position, clamped to canvas bounds. Selection chrome preserved during drag (widget stays selected). Integration tests use KeyboardSensor path per Q-40 to assert at rendered element's `style.transform` or `style.left` / `style.top`. Cross-side render assertion verifies positioning persists through save + reload round-trip.

**Estimated LOC.** ~1,200–1,800.

**Ships visibly.** Operator drags widgets to reposition. Save + reload preserves positions.

**Dependencies.** FF-2 ships first. Q-9 LOCKED.

**Deferred-decision flags for FF-3:** Q-11 snap-to-alignment deferred to FF-7. FF-3 ships drag-only-no-snap baseline.

### FF-4 — Resize-to-resize

**Scope.** 8 resize handles per Q-10 rendered on selected widgets only. Corner handles preserve aspect ratio when Shift held. Edge handles resize single dimension. Hook gains `resizeWidget(id, { width, height })` helper (~30 LOC; same shape as `updateWidget`). Min/max constraints per Q-13 + Q-14 enforced at resize gesture level (clamp to widget's `minDimensions` / `maxDimensions` from registry metadata + canvas bounds). Handle visual styling: 8px square, accent-token-colored, absolute-positioned children of selection chrome layer. Resize state updates the placement's `width` / `height` via debounced save. Integration tests use direct-hook-invocation pattern per Q-40; assert at rendered element's `style.width` / `style.height`.

**Estimated LOC.** ~1,200–1,800.

**Ships visibly.** Operator resizes widgets via corner + edge handles; persistence via auto-save.

**Dependencies.** FF-3 ships first. Q-10, Q-13, Q-14 LOCKED.

### FF-5 — Z-index + layering

**Scope.** Explicit `z_index` field per Q-6. Send-to-front / send-to-back affordances. Hook gains `setWidgetZIndex(id, mode: "front" | "back" | "forward" | "backward")` helper. "Forward" = current + 1; "backward" = current - 1; "front" = max(others) + 1; "back" = min(others) - 1. Z-index applied via CSS `z-index` on the FreeFormPlacedWidget. Right-click context menu on canvas widget exposes the four operations per Q-31 (c). Core has implicit `z_index: 0`; widgets default `z_index: 0`. Overlap rendering verified via integration tests asserting computed stacking order matches authored z-index.

**Estimated LOC.** ~800–1,200.

**Ships visibly.** Operator manages widget stacking via send-to-front etc.

**Dependencies.** FF-4 ships first. Q-6, Q-7, Q-8, Q-22 LOCKED.

### FF-6 — Inspector positioning fields

**Scope.** F-2's inspector gains a "Position" section in the widget inspector per Q-30. Four numeric inputs (X, Y, Width, Height) + z-index control with send-to-front / send-to-back buttons (Q-31 inspector path). Inputs commit on blur + Enter. Drag/resize from canvas updates same state; bidirectional sync verified via integration test (drag widget → inspector inputs update live; edit input → widget moves on canvas). Section composition reuses existing C-1 primitives (PropertyPanel, PropertySection, PropertyRow). Estimated section LOC: ~250.

**Estimated LOC.** ~600–900.

**Ships visibly.** Inspector exposes positioning controls for power-users + precision editing.

**Dependencies.** FF-5 ships first. Q-30, Q-31 LOCKED.

### FF-7 — Polish + verification gate (snap, keyboard, multi-select, Playwright pointer-event tests)

**Scope.** **Snap-to-alignment helpers** per Q-11 (b): proximity detection during drag, guide lines rendered as overlays, 6px snap threshold, Alt-key to disable. **Keyboard nudge** per Q-12: arrow keys 1px, Shift+arrow 10px, `]` / `[` z-order shortcuts. **Multi-select on canvas** per Q-16 (a) + Q-17 (b): shift+click adds to selection, marquee drag, move-together gesture, align affordances in inspector (left/center/right/top/middle/bottom). **Playwright pointer-event gate**: real-browser drag/resize tests covering operator-observable scenarios that JSDOM cannot exercise (pointer-down on widget → drag → pointer-up → widget at new position; pointer-down on resize handle → drag → widget resized). **Staging verification**: end-to-end operator-flow on staging (operator opens free-form template, drops widget, drags it, resizes it, sees auto-save indicator, reloads page, verifies positions persisted).

**Estimated LOC.** ~1,500–2,400.

**Ships visibly.** FF-series is feature-complete. Snap helpers + keyboard accessibility + multi-select power features. Real-browser test coverage closes JSDOM gap.

**Dependencies.** FF-6 ships first. Q-11, Q-12, Q-16, Q-17, Q-18, Q-40 LOCKED.

### Total

**FF-series midpoint LOC: ~8,000.** Worst-case ~11,500. Decomposition is natural at every seam; no sub-arc bundles concerns from another. Each ships visibly.

---

## Deferred for later substrate work

Explicit deferrals NOT in FF-series scope (Q-32 through Q-37):

- **Q-32 — Layout templates** (save free-form arrangement as reusable layout). Deferred post-arc; revisit on operator demand.
- **Q-33 — Mobile/touch interactions** on Focus Builder. Deferred indefinitely; admin tooling is desktop-only.
- **Q-34 — Collaborative cursors during free-form arrangement** (Liveblocks/Yjs CRDT/operational-transform substrate). Deferred post-arc.
- **Q-35 — Smart positioning engine** (AI-assisted "intelligent" placement). Deferred post-arc.
- **Q-36 — "Tidy up" auto-arrangement button** (auto-grid-snap-everything). Deferred indefinitely; conflicts with operator-flexibility canon.
- **Q-37 — Focus item data multi-select** (shift-clicking items within a widget's data, e.g., kanban orders). Different substrate concern; belongs to Focus runtime interaction-model arc, not Focus Builder authoring arc.

Additional deferrals carried forward from F-series:

- **Per-user / per-Focus-instance layout personalization** (Q-27 elaboration): requires Focus-instance modeling first. Three-scope inheritance (platform_default → vertical_default → tenant_override) holds for FF-series.
- **Per-template canvas dimensions override UI** (Q-2 follow-up): exposed via `canvas_config.width` / `.height` JSONB but no inspector UI in FF-series. Operators get platform default 1200×800.

---

## References

- `DECISIONS.md` 2026-05-20 — Discovered canon: Monitor canvas (grid model) and Decide canvas (free-form model) are architecturally distinct substrate concerns
- `DECISIONS.md` 2026-05-19 — Discovered canon: Core placement position is structurally immutable in Focus Builder canvas
- `DECISIONS.md` 2026-05-19 — Discovered canon: Component registry requires ≥3 configurableProps per registration
- `DECISIONS.md` 2026-05-19 (PM) — Discovered canon: Off-by-one column index between frontend and backend placement coordinates
- `DECISIONS.md` 2026-05-19 (PM) — Discovered canon: `chrome` field on placements stores the full per-placement override surface
- `DECISIONS.md` 2026-05-19 (PM) — Discovered canon: Ordinary template updates version-bump by default; session-aware mutate-in-place is the exception
- `DECISIONS.md` 2026-05-19 (PM) — Discovered canon: URL stability for versioned entities requires slug-based addressing as long-term canonical pattern
- `DECISIONS.md` 2026-05-19 (evening) — Discovered process canon refinement: Cross-side contract framing extends to data↔render boundaries
- `DECISIONS.md` 2026-05-19 (late evening) — Discovered process canon refinement: Render-side assertions must target operator-observable CSS at the specific rendered element
- `docs/investigations/2026-05-18-focus-builder.md` — F-series investigation (reference shape; 40 Q precedent)
- `frontend/src/bridgeable-admin/components/focus-builder/FocusBuilderCanvas.tsx` — F-3.1c substrate (WidgetRowsLayer + PlacedWidget); replaced by FF-2
- `frontend/src/bridgeable-admin/hooks/_placement-adapter.ts` — F-3.1a adapter pattern; extended in FF-1
- `frontend/src/bridgeable-admin/hooks/useFocusTemplateDraft.ts` — debounced save + 410-retry pipeline; consumed unchanged
- `frontend/src/bridgeable-admin/lib/visual-editor/chrome-resolver.ts` — chrome resolution; consumed unchanged
- `backend/app/services/focus_template_inheritance/focus_templates_service.py` — `_validate_placement` at lines 157-235; extended in FF-1
- `backend/alembic/versions/r103_focus_templates_edit_session.py` — current migration head for the focus_template chain; FF-series adds NO new migrations (JSONB schema extension only)
- F-series build commits: F-3 (`8ced75a`), F-3.1a (`084f0ee`), F-3.1a.2 (`4a73dbf`), F-3.1b (`c36f1e2`), F-3.1c (`4bcdf96`), F-4 (`cd2d0f7`), F-4.1 (`89fd867`), F-5 (`b4e1fa2`)
- 2026-05-20 canon commit: `0fa9ce1`

---

---

## Post-arc canon filing (2026-05-21)

Filed during the FF-series consolidated canon-update arc. Two DECISIONS.md entries refine locks established in this investigation:

- **Entry 23 (`DECISIONS.md` 2026-05-21 — Q-10 refinement: Resize handles visible on hover OR selection OR active drag)** — refines Q-10's "selection-only handles" lock at §Q-10. Operator hand-validation during FF-4 staging verification surfaced that selection-only forced operators into a two-step gesture for what felt like single intent. The original Q-10 lock stays in the historical record as the investigation-time decision; entry 23 supersedes it operationally with three-predicate render gate (hover OR selection OR active drag).
- **Entry 24 (`DECISIONS.md` 2026-05-21 — Q-10 addendum: Shift-for-aspect-ratio resize is unimplemented (KNOWN GAP))** — files the Shift-for-aspect-ratio resize as a KNOWN GAP relative to Q-10's lock. The FF-4 implementation ships the 8-handle resize substrate without the Shift modifier path because @dnd-kit's DragMoveEvent doesn't expose modifier-key state mid-gesture. Three fix paths enumerated in entry 24; selection deferred to future arc.

Entry 30 (`DECISIONS.md` 2026-05-21 — Q-40 generalization: All pointer-event surfaces require Playwright coverage) refines Q-40's drag-gesture-specific framing to cover ALL pointer-event surfaces. See `docs/investigations/2026-05-20-hover-state-staging-regression.md` post-arc canon filing for surfacing context.
