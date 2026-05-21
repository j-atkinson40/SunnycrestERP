# Widget Builder Canvas Investigation (WB-4 sub-arc)

Date: 2026-05-21
Purpose: Lock architectural decisions for **WB-4** — the first operator-facing Widget Builder sub-arc. Establishes the substrate shape for canvas authoring: operators compose widgets by dropping atoms onto a canvas, configuring each atom's properties, and saving as a named widget definition.
Status: Investigation closed; 10 Areas locked (Areas 1-2 load-bearing, 3-5 tactical, 6-10 supporting); 4 architectural risks surfaced with mitigations; WB-4 execution plan with LOC estimate.
Pre-flight: HEAD verified `4b6b173` (WB-3). 114 stale Playwright screenshot deletions in working tree, untouched per scope discipline.

---

## Context

WB-1 (`7eb1280`), WB-2 (`95ddd16`), and WB-3 (`4b6b173`) shipped the foundational substrate + invisible runtime for composed widgets. Recap of what's in place:

- **WB-1** — migration `r105_widget_definitions_composition_extension` added 6 columns to `widget_definitions`: `composition_blob` (JSONB), `composition_version` (Integer), `tier_scope` (CHECK `{platform, vertical}`), and three session-aware columns (`last_edit_session_id` / `last_edit_session_at` / `last_edit_session_actor_id`) mirroring the r102/r103 focus_templates pattern. Backend Pydantic schema at `backend/app/schemas/widget_composition.py` (367 LOC). Frontend mirror at `frontend/src/lib/widget-builder/types/composition-blob.ts`. Composition-blob codec at `frontend/src/lib/widget-builder/composition-blob-codec.ts` (427 LOC) handles defensive parsing + deterministic serialization. Cross-side validators (`backend/app/services/widget_definitions/validators.py`, 345 LOC) enforce: schema_version match, max 30 atoms, max 2 nesting levels, data_source resolvable, required_permission valid, visible_in_variants canonical subset.
- **WB-2** — `ComposedWidget` runtime renderer at `frontend/src/lib/widget-builder/runtime/ComposedWidget.tsx` (124 LOC) registered under canvas slug `composed_widget`. AtomRenderer dispatch at `runtime/AtomRenderer.tsx` walks the atom_tree, resolves bindings, and dispatches each atom_type to its renderer. resolveBinding service at `runtime/resolveBinding.ts` translates BindingRef → resolved value (literal pass-through; field_path placeholder). Six Phase 1 atoms shipped: `text_label`, `value_display`, `icon`, `status_badge`, `divider`, `conditional_container`.
- **WB-3** — Expanded atom catalog to 9 production atoms + `repeater_atom` architectural primitive. Atoms added at WB-3: `button`, `image`, `repeater_atom`. `RepeaterAtomRenderer` introduces iteration semantics (renders children once per row when bound to `iteration_mode: 'per_row'`). Container atoms (`conditional_container`, `repeater_atom`) carry **layout vocabulary**: `direction` (row/column), `spacing` (compact/normal/loose), `alignment` (start/center/end). This is a load-bearing observation for Area 1. Visual-editor registry bridge at `runtime/registerComposedWidgets.ts` (155 LOC) fetches composed widget DTOs at boot and registers each as a registerComponent metadata entry so Focus Builder palette + PlacedWidgetCore can discover composed widgets at runtime. Canonical `WidgetDefinition` interface extended with composition fields. WB-3 build report ("0 architectural surprises").

**What WB-4 is.** WB-4 is the **first operator-facing sub-arc** of the widget-builder cycle. WB-1/2/3 shipped the runtime; operators see no UI. WB-4 ships the authoring UI: a Studio editor at `/studio/widgets/<slug>` where operators (platform admins authoring Tier-1; vertical-scope operators authoring Tier-2) compose widgets visually. Save → composition_blob persists → ComposedWidget runtime renders → registry bridge surfaces the widget to Focus Builder palette.

**Sequencing rationale.** Prior investigation (`docs/investigations/2026-05-21-widget-builder.md` §Sub-arc decomposition) sketched WB-4 as "Drag-to-reorder + per-atom selection + chrome inspector" — that decomposition assumed WB-3 shipped the shell + drop-only canvas. WB-3 actually shipped the atom catalog runtime (9 atoms + repeater_atom + visual-editor registry bridge). The "shell + canvas" concern moved forward to WB-4. This re-investigation locks the consequent design decisions for the new WB-4 scope — first operator-facing UI rather than incremental polish over a prior shipped shell.

**Canon this investigation answers to:**
- DECISIONS.md entry 22 (Monitor-vs-Decide canvas distinction)
- DECISIONS.md entry 32 (Q-10 hover-or-selection-or-drag visibility refinement)
- DECISIONS.md entry 33 (Q-10 Shift-aspect-ratio gap)
- DECISIONS.md entry 38 (cumulative-delta-vs-per-tick-state for stateful drag)
- DECISIONS.md entry 41 (@dnd-kit transform position-only model)
- DECISIONS.md entry 42 (gesture-vs-input symmetry heuristic)
- DECISIONS.md entry 26 (investigation-time UX locks revisitable by operator experience)
- DECISIONS.md entry 28 (cross-substrate HOC audit — registerComponent display:contents)
- DECISIONS.md entry 30 (Q-40 all pointer-event surfaces require Playwright)
- DECISIONS.md entry 31 (source-shape regression gate as test-substrate pattern)
- Prior WB investigation `docs/investigations/2026-05-21-widget-builder.md` Areas 5/6/7/10 (operator mental model, HOC reconciliation, persistence, tier inheritance — locks consumed unchanged)

---

## Canonical UX target

```
┌─ Platform › Widgets › author-mode › Funeral Schedule Card ────────────────┐
│  Tier-1 (platform_default)   Auto-saved 12s ago   [Save & publish]        │
├──────────────┬─────────────────────────────────────────┬──────────────────┤
│ Atom palette │  Composition canvas                     │ Inspector        │
│              │                                         │                  │
│ Containers   │   ┌───────────────────────────────┐     │ Selected:        │
│  ▸ Repeater  │   │ Repeater (per row)            │     │   value_display  │
│  ▸ Condition │   │   row direction = row          │     │                  │
│              │   │   ┌─────┐ ┌──────┐  ┌──────┐ │     │ Atom config:     │
│ Display      │   │   │Icon │ │Label │  │Status│ │     │   format: text   │
│  ▸ Text      │   │   └─────┘ └──────┘  └──────┘ │     │   align: left    │
│  ▸ Value     │   └───────────────────────────────┘     │                  │
│  ▸ Icon      │                                         │ Binding:         │
│  ▸ Status    │                                         │   field_path     │
│  ▸ Image     │                                         │   delivery.name  │
│  ▸ Button    │                                         │   fallback: "—"  │
│  ▸ Divider   │                                         │                  │
│              │                                         │ Visible in:      │
│ [validation  │                                         │  ☑ brief  ☑ deep │
│  warnings]   │                                         │  ☐ glance ☐detail│
└──────────────┴─────────────────────────────────────────┴──────────────────┘
```

- **Left rail** — atom palette grouped into 2 sections (Containers / Display). Drag a tile onto canvas → atom appended.
- **Center canvas** — composition surface. Atom tree renders the actual composed widget. Container atoms render as visible group boxes with subtle border. Atoms inside containers render via the recursive `AtomRenderer` dispatch the runtime already uses; the canvas is `ComposedWidget` in "edit affordance" mode.
- **Right rail** — inspector. Per-atom config + binding + visibility. Widget-root selection (background click) → widget-level chrome + data-source picker + variant declarations.
- **Top bar** — tier indicator, save status, breadcrumb, [Save & publish] for explicit promotion gate (per Area 2 lock).
- **Validation banner** — surfaces inline when composition fails schema constraints (per Area 5 lock).

This UX target is locked against the Prior WB investigation's §Canonical UX (which sketched a similar three-pane layout) and inherits the FocusBuilderPage canon shape (left palette / center canvas / right inspector / top breadcrumb + save indicator) verbatim.

---

## Area 1 — Canvas layout model (LOAD-BEARING)

**At stake.** When the operator drops atoms onto the widget canvas, how are they positioned?

### Options enumerated

- **Option A — Free-form (FF-2 substrate reuse).** Per-atom `x` / `y` / `width` / `height`; reuses FF-2 (`WidgetFreeFormLayer` + `FreeFormPlacedWidget` + `PlacedWidgetCore`), FF-3 (drag-to-move), FF-4 (resize), FF-6 (PositionInspectorSection), FF-7 (multi-select). Substrate continuity with Focus canvas.
- **Option B — Flex-stack (semantic layout matching container atoms).** Canvas is itself a flex container. Atoms stack semantically per CSS flex flow. Container atoms (conditional_container, repeater_atom) render as nested flex boxes carrying their own direction/spacing/alignment. Reorder = drag-to-rearrange-within-stack (Z-shaped reorder per Webflow / Notion / Figma Auto-Layout). No x/y; atom position is its index in its parent container's children array.
- **Option C — Hybrid (canvas flex-stack; atoms can opt-in to free-form).** Flex-stack default; per-atom `position_mode: 'flow' | 'absolute'` enum; absolute-positioned atoms carry x/y/width/height; flow atoms stack.
- **Option D — Container-first (canvas IS a conditional_container).** Widget canvas root is itself a conditional_container atom (or analogous). All atoms are its children. The root container's direction/spacing/alignment cascades. Same composition primitive at canvas + container levels.

### Audit

**Production widget composition needs.** Per the prior WB investigation §Canonical UX target + the audit of the 28 existing hand-coded widgets:
- 7 dashboard widgets per BRIDGEABLE_MASTER: today's schedule, case overview, vault personalization queue, route optimization, operator profile, service timing pipeline, quick metrics.
- 5 Family Portal widgets per FH vertical canon (case status, service-time card, document inbox, payment status, message thread).
- Manufacturing surfaces: vault production tracking, scheduling calendars, line-status cards.

The composition shape across these is **stack-shaped**: a card with a header row + body column + status footer; a list with a per-row repeater; a tile with icon + label + value. None of the audited widgets use absolute positioning. None overlap. None have the floating-tablet aesthetic of Decide canvas widgets.

**Substrate reuse vs build-new LOC.**
- Option A reuse: FF-2 `WidgetFreeFormLayer` (291 LOC) + `FreeFormPlacedWidget` (296 LOC) + `PlacedWidgetCore` (170 LOC) + FF-6 `PositionInspectorSection` (279 LOC) — ~1,036 LOC of free-form-canvas substrate to either consume verbatim or fork. **Reuse cost reality check**: this substrate is tightly coupled to `WidgetPlacement` (Focus's placement shape, NOT WB's `AtomNode` shape), to `useFocusTemplateDraft` (Focus's hook, NOT WB's `useComposedWidgetDraft`), to F-3.1c's chrome-resolver pipeline (per-placement chrome cascade, not per-atom config), and to canvas-bounds-clamp semantics computed against `template.canvas_config.{width,height}`. The substrate would need a forking refactor — at minimum, an interface-level abstraction over placement-vs-atom, hook-vs-hook, chrome-vs-config. Mechanical reuse is not free.
- Option B build-new: a flex-stack canvas is structurally a render of `ComposedWidget` in edit mode + drop targets between siblings + atom-level selection chrome. No x/y persistence; the composition_blob's `atom_tree` + `children` array IS the layout state. Estimated net-new: a canvas wrapper (~120 LOC) + drop-target slot components (~150 LOC) + atom selection overlay (~120 LOC) + tree manipulation helpers (~200 LOC) ≈ ~590 LOC.
- Option C: flex-stack + opt-in absolute. Carries both substrates' costs. Worst LOC; most operator complexity.
- Option D: same LOC as Option B but reframes the root as a container atom. Mostly a semantic relabel.

**Operator mental model.** Free-form canvas tooling (Figma, Sketch, Webflow's free-position mode) is operator-familiar but **WRONG for widget composition** — widgets are stack-shaped data displays, not free-form artwork. The operator's intent when authoring "a card with icon + label + status" is structural ("these three atoms form a row") not spatial ("the icon is at x=20, the label at x=60"). Flex-stack matches the structural intent natively. Free-form forces the operator to think in pixels for something that doesn't need pixels.

Container atoms already carry layout vocabulary (`direction` / `spacing` / `alignment` per WB-3, `frontend/src/lib/widget-builder/runtime/atoms/index.tsx:679-686`). If the canvas root is itself a container OR the atoms within a flex-stack canvas use the same vocabulary, **the layout authoring is the same operation at canvas + container levels**. Operators learn one model.

**Render-time consistency.** Critical: the canvas during authoring MUST render the same atom tree the operator sees at runtime. ComposedWidget renders the atom_tree via AtomRenderer dispatch. If the canvas during authoring uses a DIFFERENT layout model (free-form), the WYSIWYG promise breaks — operator sees `[icon] [label] [status]` arranged at x=20/x=60/x=140 in authoring, sees them flowed naturally at runtime. Mismatch. The canvas during authoring renders the same flex-flow the runtime uses; operator-observable WYSIWYG holds.

**FF-2 substrate reuse implications.** FF-2 substrate exists for Decide canvas (Focus instances) where operator-driven free-form positioning is the load-bearing constraint per DECISIONS.md entry 22 (Monitor-vs-Decide canon). Widget builder is **NOT** a third canvas variant — widgets are composition primitives that render on Monitor AND Decide canvases. The widget's INTERNAL composition is structural; the widget's PLACEMENT on a downstream canvas (Pulse grid for Monitor, free-form for Decide) is the canvas-shape concern. Forcing free-form internal composition would conflate the two concerns.

### LOCK

**Option B — Flex-stack canvas matching container-atom layout vocabulary.**

The widget canvas is a vertical flex stack (root direction: column by default; operator can change root direction). Atoms appended at root level stack semantically. Container atoms (conditional_container, repeater_atom) render as nested flex boxes carrying their own direction/spacing/alignment per WB-3. Reorder = drag-to-rearrange-within-flow (between siblings in the parent's children array). Drop-from-palette = append-to-parent (root by default; selected container if a container is selected).

**Reasoning.**
1. Production widgets are stack-shaped per audit; free-form positioning is over-engineered for the observed need.
2. Container atoms already carry layout vocabulary; reusing flex-stack at canvas root means one layout model, not two.
3. WYSIWYG promise holds — canvas during authoring renders the same flex-flow the runtime renders.
4. FF-2 substrate reuse would require non-trivial refactor (placement-vs-atom, hook-vs-hook, chrome-vs-config); net-new flex-stack canvas is lower LOC.
5. Monitor-vs-Decide canon (entry 22) makes free-form canvas a Decide-specific concern; widget authoring is neither — widgets are primitives that render on both. Internal composition is structural.

**Alternatives considered + rejected.**
- **Option A (free-form)** rejected — substrate reuse cost is real (placement-vs-atom mismatch), operator mental model wrong for stack-shaped data displays, WYSIWYG ceiling cannot mirror runtime free-form-in-authoring → flex-at-runtime.
- **Option C (hybrid)** rejected — combines costs without commensurate benefit; operators don't reach for absolute positioning when authoring stack-shaped widgets.
- **Option D (canvas-is-conditional-container)** rejected as a separate option but **partially adopted** — the canvas root behaves AS IF it's a container atom for the operator's purposes (root direction, root spacing, root alignment editable in inspector when widget root is selected). Whether the persistence shape stores a synthetic root container atom OR stores root-level layout as widget-root chrome is a Phase 1 implementation detail; Phase 1 ships root-level layout as widget-root config (matches the existing composition_blob shape: `root_atom_id` references a real atom, but the widget root's layout is widget-level not atom-level). The "canvas IS a container atom" framing remains a Phase 2+ refactor candidate.

**Operator-validation-sensitive (per entry 26).** The flex-stack lock is structurally-determined (architecturally correct given production widget shape + canon entry 22 + WYSIWYG discipline). NOT operator-validation-sensitive. Lock holds.

---

## Area 2 — Save semantics (LOAD-BEARING)

**At stake.** WB-1 proactively shipped session-aware columns at r105. Question: continuous auto-save (FF-2 substrate pattern via `useFocusTemplateDraft`) OR draft-then-publish (r103 edit-session pattern WB-1's session columns enable)?

### Options enumerated

- **Option A — Auto-save (FF-2 substrate reuse).** Per-tick debounced save via `useComposedWidgetDraft` analog to `useFocusTemplateDraft`. Every operator edit lands in the canonical row. Composed widgets rendered on placed Focuses pick up updates LIVE.
- **Option B — Draft-then-publish (r103 pattern).** Edits live in edit-session-scoped state on the same row (per the r103 session-aware mutate-in-place canon). The widget continues to render its LAST PUBLISHED composition_blob on placed Focuses; an explicit "Publish" action commits the edit-session draft to the live composition_blob.
- **Option C — Hybrid (auto-save into draft; explicit publish).** Auto-save continuously into a draft-blob field separate from the live composition_blob. Explicit Publish promotes draft → live. Three-state: live + draft + transitioning.

### Audit

**Operator mental model.**
- Option A: "I'm editing the live widget. Every change ships." → operator anxiety. Funeral homes literally see operator scratch work. The "every keystroke ships to live" model is correct for focus_templates (per-instance bounded decision scope; operator's edit doesn't leak past their session) but WRONG for widget definitions (shared substrate — widgets rendered on many places).
- Option B: "I'm editing a draft. Live stays stable. I publish when ready." → operator confidence + explicit promotion gate. Matches platform_themes Phase 2 + component_configurations Phase 3 + workflow_templates Phase 4 + focus_compositions May 2026 — all three-tier editors carry an explicit save (not auto-save) for vertical_default rows.
- Option C: split mental model; auto-save anxiety partially mitigated but operators still wonder "if I edited and didn't publish, what's the state on next visit?"

**Cross-tenant exposure (shared composed widgets in shared Focuses).** Composed widgets are Tier-1 (platform_default) or Tier-2 (vertical_default). A Tier-2 vertical_default funeral_home widget shipped on Hopkins's Pulse, St. Mary's Pulse, and 10 other funeral_home tenant Pulses simultaneously. If the platform admin or vertical-scope authoring operator edits the widget under auto-save, every keystroke flips composition for every tenant rendering the widget. **This is operationally unacceptable.** The shared-substrate property — which Tier-1 widgets get for free by virtue of being canonical-cross-tenant — makes auto-save a multi-tenant exposure risk.

Contrast with focus_templates: Tier-2 focus_templates DO carry the same cross-tenant property and DO use auto-save. The structural difference is that focus_templates are *templates* (operators clone them to per-instance focus_compositions before personalizing); the live tenant render reads focus_compositions, not focus_templates. The auto-save authoring landing in focus_templates doesn't flicker the per-tenant render. Composed widgets have no analogous instance-vs-template distinction — the widget IS the rendered thing. Auto-save semantics that work for templates don't work for shared rendered primitives.

**WB-1 session columns disposition.** WB-1 ship report flagged session columns as "proactive addition per r103 focus_templates_edit_session precedent." If Area 2 locks auto-save, the session columns become substrate debt — added with no consumer. If Area 2 locks draft-then-publish, the columns serve the canonical purpose: session-scoped mutate-in-place during draft authoring, version-bump on explicit Publish. **Area 2 lock determines column disposition.**

**Conflict resolution.** Auto-save (A) sidesteps conflict — last write wins; no merging. Draft-then-publish (B) introduces a possible conflict: two operators editing the same widget concurrently. Per the existing focus_templates pattern, edit_session_id discriminates concurrent edit sessions; the last published session wins. Acceptable trade-off — widget authoring is rare enough that concurrent edits are unlikely.

**Production reality.** September Wilbert demo + Sunnycrest pilot launch are operator-validation moments. A widget shipping incorrectly composed because an editor's mid-edit autosave landed live is a demo-day catastrophe. Draft-then-publish lets the operator confirm the final shape before promotion. Worth the substrate complexity.

### LOCK

**Option B — Draft-then-publish (r103 session-aware pattern).**

Operator edits land in edit-session-scoped state on the `widget_definitions` row. The live `composition_blob` field is NOT mutated during the edit session; instead, edits accumulate in a draft-scoped representation (TBD: the row's `composition_blob` field IS mutated but the edit_session_id discriminates the "draft session" state from "published" state — same shape as focus_templates per r103 canon). Auto-save fires continuously to persist the in-progress edit session (so closing the tab doesn't lose work) but the widget remains rendered at its last-published composition_blob on all Focuses + Pulses across all tenants. Explicit "Save & publish" action promotes the edit-session draft to live: bumps composition_version + clears the edit_session_id + sets last_edit_session_at.

**Persistence shape details (Phase 1, expandable):**
- Same `composition_blob` column; edit_session_id discriminates "currently being edited under session X" from "live published state."
- Edit-session window of N seconds (matches r103 EDIT_SESSION_WINDOW_SECONDS = 30 minutes default). Operator returning within window resumes their session. Beyond the window, draft is considered abandoned and live composition_blob is the source of truth.
- An abandoned draft DOES become a known data shape: composition_blob has unpublished changes + last_edit_session_at within window. WB-4 ships a "draft state" indicator on the widget list view; abandoned drafts surface as "draft pending" until the operator clears them (Publish or Discard).
- Loaded widgets at runtime read composition_blob unfiltered. Inflight drafts therefore DO render to runtime consumers IF the operator's session window has not closed. **Mitigation**: at render time, ComposedWidget detects a non-null `last_edit_session_id` + within-window `last_edit_session_at` and renders the LAST-KNOWN-GOOD frozen blob (stored separately as `published_composition_blob` JSONB column — WB-4 migration extends the row).

**WB-4 migration extension.** WB-4 ships migration r106 adding `published_composition_blob` JSONB column. composition_blob remains the draft authoring surface; published_composition_blob is the live render surface. Publish action copies composition_blob → published_composition_blob + bumps composition_version. The proactive r105 session columns finally have their consumer; r106 is the consequent extension.

**Disposition of WB-1 session columns.** Load-bearing per the Area 2 lock. NOT debt. r105 was correctly proactive.

**Alternatives considered + rejected.**
- **Option A (auto-save)** rejected — multi-tenant exposure unacceptable for shared-substrate widget definitions.
- **Option C (auto-save into draft; explicit publish)** rejected as a label — IS what Option B actually implements (auto-save continuously persists the edit-session draft via the existing debounce; the difference from raw Option A is that ComposedWidget reads published_composition_blob, not composition_blob).

**Operator-validation-sensitive (per entry 26).** Draft-then-publish IS structurally-determined for shared-substrate widgets. NOT operator-validation-sensitive. Lock holds. (The UI surfacing of the Publish action — modal confirmation? toast? both? — IS operator-validation-sensitive and revisitable.)

---

## Area 3 — Atom palette UI (TACTICAL — derives from Area 1)

**At stake.** How does the left-rail atom palette look + behave?

### Locked decisions

**Categorization.** Two sections in Phase 1: **Containers** (conditional_container, repeater_atom) and **Display** (text_label, value_display, icon, status_badge, image, button, divider). Two sections cover all 9 Phase 1 atoms cleanly. Section headers visible; both sections expanded by default. Collapse semantics deferred to WB-7 (8-9 atoms across 2 sections fits without scroll; collapse adds substrate complexity for no Phase 1 value).

**Search.** Deferred to WB-7. With 9 atoms, search is unnecessary. When the catalog expands past ~15 atoms, surface search.

**Drag-to-canvas.** Drag a palette tile → on drop, atom appended to root container's children (or to selected container if a container is selected). @dnd-kit `useDraggable` on each palette tile; canvas root is the primary drop zone; container atoms are secondary drop zones (drop-into-container). Pointer-event surfaces follow canon entry 30 (Playwright coverage required) + entry 31 (source-shape regression gates).

**Atom card visual minimum-viable.** Each palette tile shows: icon (Lucide name from the atom's registry metadata) + atom label (from `ATOM_TYPE_LABELS` per WB-3). Hover state: subtle accent. Drag-state: dragging tile gets ghost opacity. Restraint principle (DESIGN_LANGUAGE): no decorative chrome on tiles; minimal visual weight; respect the canvas as the operator's focus surface.

**Drop semantics.**
- Drop on canvas root → append to root atom_tree.
- Drop ON a container atom → append to container's children (if Phase 1 nesting cap respected; reject otherwise with inline error toast).
- Drop NEAR a container atom but outside it → append as sibling.
- Drop BETWEEN two siblings → insert between (drop-target zones between siblings, narrow strip).

**Reasoning.** Two-section flat catalog is the canonical pattern for small atom catalogs (matches Figma's left rail, Notion's `/` menu sections). Drag-to-canvas is the canonical "compose visually" gesture; click-to-append is a secondary path WB-4 omits (deferred to keyboard accessibility pass in WB-7).

**Operator-validation-sensitive.** Drop affordance UX (drop zones visible vs invisible-until-hover; reorder vs insert distinction) is operator-validation-sensitive. Phase 1 ships drop zones visible during drag; revisit after staging.

---

## Area 4 — Inspector substrate (TACTICAL — derives from Areas 1-2)

**At stake.** Right-rail inspector renders per-atom config UI (different per atom type) + binding picker + variant visibility. Pattern + dependencies.

### Locked decisions

**Composition pattern.** Inspector follows FF-6's **uncontrolled-with-sync** pattern (`PositionInspectorSection` + `LayerInspectorSection` at `frontend/src/bridgeable-admin/components/focus-builder/PositionInspectorSection.tsx`). Each section renders an inspector for a specific concern (Atom config, Binding, Visibility, Behavior). When selection changes, sections receive new initial values and sync; operator edits land in local state and propagate via debounced callback to the page-level draft mutator. Same uncontrolled-with-sync canon; reused at WB-4.

**Per-atom config UI.** Inspector reads the selected atom's `atom_type` and dispatches to an atom-kind-specific control component. Phase 1 ships 9 inspector control components, one per atom_kind, each composing C-1 PropertyPanel + PropertyRow primitives. Atom-kind controls live at `frontend/src/bridgeable-admin/components/widget-builder/inspector-controls/<atom_kind>Inspector.tsx`.

**Saved-view binding picker for repeater_atom.** Depends on WB-6 (saved-view substrate availability). Phase 1 surface: dropdown listing existing saved views; operator picks a saved-view-id; iteration scope inferred from saved-view shape (per Q-12 lock). **Dependency**: WB-6 ships saved-view-shape introspection enabling the dropdown to surface bindable fields. Phase 1 (WB-4) ships a *placeholder* binding picker that accepts a saved-view-id string + binds repeater to its rows abstractly; the per-field-path picker activates in WB-5 (binding sub-arc). For WB-4 ship: operators can create a repeater_atom + give it a saved_view_id; the actual per-row field bindings on inner atoms ship in WB-5.

**Variant authoring.** Per the prior WB investigation Q-10 lock, variants ship as `visible_in_variants` per atom. Phase 1 (WB-4) inspector surfaces a multi-select control on each atom: which variants does this atom appear in? Operator picks from `[glance, brief, detail, deep]`. Widget-level variant set (which variants the widget supports) ships in WB-6 alongside surface availability. WB-4 ships per-atom visibility; WB-6 ships the full variant taxonomy.

**Nesting management for container atoms.** Selecting a container shows: direction (row/column) + spacing (compact/normal/loose) + alignment (start/center/end) + (for conditional_container) condition_binding_id picker + (for repeater_atom) saved_view_id + max_rows + empty_state copy. Adding a child atom = drag from palette onto container OR keyboard "insert atom inside container" deferred to WB-7. Removing a child = delete via toolbar or keyboard Delete. Reorder children = drag-to-reorder within container.

**FF-6 composition pattern reuse audit.** FF-6 introduced PositionInspectorSection + LayerInspectorSection + the C-1 PropertyPanel composition. WB-4 reuses the pattern (uncontrolled-with-sync + PropertyPanel composition) but NOT the specific components (PositionInspectorSection is x/y/width/height-focused for Decide canvas; WB-4 inspector is atom-config-focused). New WB-4 components: WidgetRootInspectorSection (widget-root chrome + data source + iteration scope), AtomConfigInspectorSection (per-atom-type config), AtomBindingInspectorSection (binding picker — placeholder in WB-4), AtomVisibilityInspectorSection (per-variant visibility).

---

## Area 5 — Composition validation surfacing (TACTICAL — derives from Areas 1-2)

**At stake.** WB-1's validator throws at write time (max 30 atoms, max 2 nesting, schema_version, etc.). During authoring, intermediate states pass through invalid shapes (operator drops 3 atoms then deletes 2 → mid-drag intermediate state has invalid orphan references). When + how does validation surface?

### Locked decisions

**Hybrid — warnings inline; errors block publish (not save).**

- **Inline validation runs continuously** during authoring (debounced, ~300ms). Validation results surface as a banner above the canvas + per-atom warning chrome on affected atoms.
- **Errors** (composition violates schema invariants: cyclic atom_tree, orphan references, > 30 atoms, > 2 nesting levels, missing required atom_type config fields) → banner red; per-atom red outline; **Publish button disabled**.
- **Warnings** (non-fatal lint: empty text_label, value_display without binding, repeater_atom with no children) → banner amber; per-atom amber outline; Publish remains enabled (operator can publish a widget with warnings; warnings are advisory).
- **Auto-save continues** during invalid states; the edit-session draft can hold invalid intermediate compositions (operator deletes a parent container → orphan children persist briefly until operator deletes them or reattaches). Auto-save persists what the operator typed; Publish is the gate that enforces composition validity.

**Why this composition.** Per Area 2 lock (draft-then-publish), auto-save is for resumability; publish is for promotion. Validation aligns with promotion: errors block publish (the published state MUST be valid); warnings inform the operator but don't block. Inline (continuous) feedback during authoring matches FocusBuilderPage's pattern of surfacing canvas-level warnings inline.

**Dependency on Area 2 lock.** Confirmed: this composition is impossible under Area 2 Option A (auto-save direct to live) — auto-saving an invalid composition to a live-rendering state would crash ComposedWidget for every tenant rendering the widget. Area 2 lock (draft-then-publish) enables Area 5's permissive auto-save + restrictive publish.

**Operator-validation-sensitive.** The specific UI of warnings (banner vs toast vs per-atom decoration vs all three) is operator-validation-sensitive. Phase 1 ships banner + per-atom outline; revisit after staging.

---

## Area 6 — Cross-substrate dependency enumeration

Reused vs left-untouched vs net-new substrate inventory.

### Reused (consumed; NOT modified)

1. **WB-1 composition_blob schema + Pydantic schemas + frontend mirror.** The shape WB-4 reads/writes. `backend/app/schemas/widget_composition.py` + `frontend/src/lib/widget-builder/types/composition-blob.ts`. **Untouched.**
2. **WB-1 composition-blob codec.** `frontend/src/lib/widget-builder/composition-blob-codec.ts` — defensive parse + deterministic serialize. **Untouched.**
3. **WB-1 backend validators.** `backend/app/services/widget_definitions/validators.py` — schema_version, atom-count caps, nesting caps, saved-view resolution. **Untouched** at the validation layer; **invoked** by the save handler + publish handler.
4. **WB-2 ComposedWidget runtime renderer.** `frontend/src/lib/widget-builder/runtime/ComposedWidget.tsx` — renders the atom_tree. WB-4 canvas reuses ComposedWidget as the WYSIWYG render surface (canvas IS a ComposedWidget rendering with edit-affordance overlays). **Untouched in WB-4**; WB-4 wraps it with selection chrome + drop overlays.
5. **WB-2 AtomRenderer dispatch.** `frontend/src/lib/widget-builder/runtime/AtomRenderer.tsx` — atom-kind → renderer dispatch. **Untouched.**
6. **WB-3 atom renderers.** All 9 atoms at `frontend/src/lib/widget-builder/runtime/atoms/index.tsx`. **Untouched** in rendering behavior; consumed by AtomRenderer.
7. **WB-3 visual-editor registry bridge.** `runtime/registerComposedWidgets.ts` — fetches composed widgets + registers them with the registry. **Untouched.**
8. **registerComponent HOC** at `frontend/src/lib/visual-editor/registry/register.ts:174-238`. Composed widgets register via the bridge; atom-level click-to-edit relies on the HOC's display:contents wrapper (per entry 28). **Untouched.**
9. **FF-6 uncontrolled-with-sync inspector PATTERN** (not components). The pattern is reused; FF-6's components are NOT consumed.
10. **C-1 PropertyPanel + PropertyRow + ScrubbableButton + TokenSwatchPicker primitives.** Inspector primitive composition. **Consumed unchanged.**

### Net-new WB-4 substrate

1. **Migration r106 (WB-4)** — adds `published_composition_blob` JSONB column on `widget_definitions`. Migrates existing rows: published_composition_blob = composition_blob (current state IS the published state for rows existing pre-r106).
2. **`useComposedWidgetDraft` hook** at `frontend/src/bridgeable-admin/hooks/useComposedWidgetDraft.ts`. Multi-hook-mount pattern per 2026-05-19 canon; debounced auto-save into edit-session-scoped composition_blob; 410-retry recovery; slug-based URL recovery per 2026-05-19 PM canon. Mirror of useFocusTemplateDraft's pipeline, adapted for the WidgetDefinition shape + the publish action.
3. **`WidgetBuilderPage` shell** at `frontend/src/bridgeable-admin/components/widget-builder/WidgetBuilderPage.tsx`. Three-pane layout. Breadcrumb + save indicator + tier indicator + Publish button at top.
4. **`WidgetBuilderCanvas`** at `frontend/src/bridgeable-admin/components/widget-builder/WidgetBuilderCanvas.tsx`. Flex-stack canvas. Wraps ComposedWidget with selection overlay + drop targets between siblings + drop-target chrome on containers.
5. **`WidgetBuilderPalette`** at `frontend/src/bridgeable-admin/components/widget-builder/WidgetBuilderPalette.tsx`. Two-section atom palette. @dnd-kit draggables.
6. **`WidgetBuilderInspector`** at `frontend/src/bridgeable-admin/components/widget-builder/WidgetBuilderInspector.tsx`. Right-rail composition of section components.
7. **9 inspector control components** at `frontend/src/bridgeable-admin/components/widget-builder/inspector-controls/<atom_kind>Inspector.tsx`. Atom-kind-specific config UI.
8. **`WidgetBuilderSelectionContext`** at `frontend/src/bridgeable-admin/components/widget-builder/WidgetBuilderSelectionContext.tsx`. Selection model — selected atom_id OR null (widget-root). Matches FocusBuilderSelectionContext shape; new context for the new substrate (NOT a reuse — the selection IDs differ).
9. **`WidgetValidationBanner`** at `frontend/src/bridgeable-admin/components/widget-builder/WidgetValidationBanner.tsx`. Renders validation results inline. Subscribes to validator via debounced effect.
10. **Backend route extensions.** `backend/app/api/routes/widgets.py` gains `POST /api/v1/widgets/{slug}/publish` action endpoint (copies composition_blob → published_composition_blob + bumps version + clears edit_session_id). Existing GET/PUT/POST endpoints honored.
11. **Studio route mount** at `/studio/widgets/<slug>` consumed via slug-based addressing per 2026-05-19 PM canon. New route registration in BridgeableAdminApp.

### Left untouched in WB-4 (deferred)

- **Saved-view substrate** for binding picker (deferred to WB-6).
- **Action authoring** for button atoms (`action_kind` config dropdown stub; deferred to WB-7).
- **Variant authoring UI** at widget-root (per-atom visibility ships in WB-4; widget-level variant declarations ship in WB-6).
- **Multi-operator collaborative authoring** (deferred indefinitely).
- **Mobile/touch widget authoring** (deferred — Studio is desktop-only Phase 1).
- **Live preview against real saved-view data** — WB-2's placeholder resolver continues. Real live-data preview ships in WB-5 alongside binding work.

---

## Area 7 — Operator mental model

**At stake.** Entry point + naming + preview behavior + save-then-place + edit-existing + tier visibility.

### Locked decisions

**Entry point.** Studio overview at `/studio` surfaces a "Widgets" card. Clicking enters the widget list at `/studio/widgets`. List view shows existing widget definitions (filterable by tier + vertical + category). Two affordances:
- **`+ New widget`** primary CTA → creates a new draft widget at `/studio/widgets/<new-slug>` (slug auto-generated as `untitled-widget-N`; operator renames in inspector). Empty composition; operator picks a starting template OR starts blank.
- **`+ From template`** secondary path → modal selecting from 3 seeded templates (Status Card / Stat Tile / List with Header) per the prior WB investigation Q-1 (c) hybrid lock. Templates seed the composition with atoms; operator modifies. (Seed templates ship in WB-8.)

**Naming.** Widget name editable in widget-root inspector as a top field. Slug auto-derived from name on first save (operator can override). Slug becomes URL stability anchor per 2026-05-19 PM canon.

**Preview behavior.** Canvas during authoring renders the actual composition via ComposedWidget. **Live** preview — operator sees the runtime appearance as they author. Per WB-2's placeholder resolver, binding values are placeholders until WB-5 lights up real saved-view data. The canvas chrome includes selection overlays + drop-target zones + per-atom hover chrome; these are authoring-only and DO NOT appear in runtime renders (overlays added by WidgetBuilderCanvas, not by ComposedWidget itself).

**Save → place behavior.** After Publish, the widget definition is queryable + registered via the WB-3 bridge at next app boot. The widget surfaces in Focus Builder palette + Pulse palette + Studio widgets list. **Immediate registration** within the operator's session: WB-4 dispatches a registry refresh after publish so the operator sees their new widget surface in the palette without reload. (Without this hook, operator publishes a widget + has to reload to see it surface — friction.)

**Editing existing widget.** Widget list shows existing widgets with edit affordance per row. Click → enter widget builder at `/studio/widgets/<slug>`. Loads the current published_composition_blob into the canvas. Operator's edits land in composition_blob (draft); explicit Publish promotes. The draft-state indicator (per Area 2) surfaces if the operator returns to a widget with an in-progress draft.

**Tier visibility.** Top bar tier indicator pill matches the FocusBuilderPage canon ("Editing Tier 1 (platform_default)" / "Editing Tier 2 (vertical_default for funeral_home)"). The list view groups widgets by tier (Platform / Vertical Default per Vertical / + tenant-scoped widgets if any). Tier is set at widget creation time per the prior WB investigation Q-38 lock (Tier-1 platform_default + Tier-2 vertical_default; no Tier-3 widget definitions). Tier cannot change post-creation (per the 2026-05-18 canon "Template vertical is design-time-permanent" analog).

**Operator-validation-sensitive (per entry 26).**
- The exact widget-list filtering + sorting UX is operator-validation-sensitive. Phase 1 ships list grouped by tier + filterable by vertical + searchable by name; revisit after staging.
- The "From template" affordance is operator-validation-sensitive — depends on whether seeded templates resonate with concrete operator needs. Phase 1 ships 3 templates per the prior WB lock; staging signals expansion or pruning.
- The slug auto-derivation collision behavior (when "Today's Schedule" → `todays-schedule` collides with existing slug) is operator-validation-sensitive; Phase 1 ships `todays-schedule-2` suffix; revisit after staging.

---

## Area 8 — Test substrate strategy

**At stake.** JSDOM vs Playwright allocation. Source-shape regression gate coverage per entry 31. Inline fixture vs staging seed.

### Locked decisions

**JSDOM coverage.**
- **Atom manipulation via KeyboardSensor.** Per FF-3 / FF-4 / FF-7 canon (KeyboardSensor reliable in JSDOM; PointerSensor unreliable), JSDOM tests exercise atom drag-from-palette, atom reorder-within-canvas, atom move-into-container, atom delete via keyboard activation + arrow keys + Space-drop.
- **Inspector field manipulation.** JSDOM tests cover: select atom → change config field → assert state propagation + assert PUT body shape on debounced save fire.
- **Validation banner state.** JSDOM tests cover: cause invalid composition (e.g., > 30 atoms) → assert banner renders + Publish button disables + Publish endpoint NOT callable.
- **Save dispatch + edit_session_id propagation.** JSDOM tests cover the auto-save debounce + edit_session_id increments + 410-retry path.
- **Publish action.** JSDOM tests cover Publish → PUT /publish endpoint → composition_blob → published_composition_blob copy.
- **Widget root selection.** JSDOM tests cover background-click → selection clears → widget-root inspector renders.

**Playwright coverage** (per entry 30, all pointer-event surfaces require Playwright):
- **Drag atom from palette to canvas** (pointer events; full @dnd-kit sensor pipeline).
- **Drag atom to reorder within canvas** (pointer events; flex-stack reorder gesture).
- **Drag atom INTO a container** (pointer events; nested drop target).
- **Hover state on atom for selection chrome** (pointer events; bubbling events per entry 27).
- **Multi-step authoring scenario** — operator authors a 3-atom widget from scratch + publishes + asserts published_composition_blob shape via API.

**Source-shape regression gates** (per entry 31):
- Source-shape gate inspecting `WidgetBuilderCanvas.tsx` for bubbling pointer event names (`onPointerOver` + `onPointerOut`) per entry 27.
- Source-shape gate inspecting `useComposedWidgetDraft.ts` for the edit_session_id ref pattern + 410-retry handler shape per FF-3 / C-2.1.4 canon.
- Source-shape gate inspecting `WidgetBuilderPage.tsx` for the snapshot-at-drag-start ref pattern per entry 38 (cumulative-delta-vs-per-tick-state) — applies to atom drag-to-reorder.

**Cross-side render+save integration tests** (per 2026-05-19 late-PM through late-evening canon):
- WidgetBuilderPage.test.tsx: full save-side mock service expectations on PUT body shape + render-side assertions at operator-observable rendered atom element (NOT at the wrapper level; at the inner atom inside the display:contents boundary per entry 28). Verify-against-pre-fix discipline applied to both sides.

**Inline fixture vs staging seed.** Phase 1 (WB-4) ships with inline fixtures for JSDOM tests (no staging dependency) + Playwright tests run against staging-seeded composed widgets (WB-8 will seed; WB-4 Playwright spec assumes the test tenant has one composed widget for edit scenarios — provisioned via test fixture per the FF-7 precedent inline-fixture pattern).

**Test substrate gap surfaced (entry 30 application):** Atom drop-from-palette and atom drop-into-container are pointer-event-driven; JSDOM coverage uses KeyboardSensor only. Playwright is the substrate gate for these surfaces. WB-4 ships the Playwright spec at `tests/e2e/widget-builder-canvas.spec.ts`.

---

## Area 9 — Phase 1 scope boundaries

### Ships in WB-4

1. Studio route `/studio/widgets` + `/studio/widgets/<slug>` mounted.
2. Widget list view with create + edit affordances.
3. WidgetBuilderPage three-pane shell.
4. Left-rail atom palette with 9 Phase 1 atoms in 2 sections (Containers + Display).
5. Center-pane flex-stack composition canvas via ComposedWidget + selection chrome + drop targets.
6. Right-rail inspector with widget-root + per-atom-kind inspector sections.
7. Per-atom-type config UI (9 inspector control components).
8. Per-atom `visible_in_variants` multi-select.
9. Drag-from-palette + drag-to-reorder + drag-into-container gestures.
10. Auto-save into edit-session-scoped composition_blob + Publish action → published_composition_blob.
11. Inline validation banner + Publish-disable on errors.
12. Slug-based URL stability + 410-retry recovery.
13. Tier indicator pill.
14. Migration r106 + new POST /publish endpoint.
15. registry refresh hook on publish (no-reload widget surface in palette).

### Defers to subsequent WB sub-arcs

- **Widget-level variant declarations** (which variants the widget supports + per-variant chrome) → WB-6.
- **Surface availability declaration** (supported_surfaces UI) → WB-6.
- **Saved-view binding picker for repeater_atom** — placeholder picker accepting saved_view_id string in WB-4; real picker with field-path enumeration in WB-5 (after WB-6 ships saved-view substrate? Or in WB-5 with WB-6 ordered before? **Ordering follow-up**: WB-6 (saved-view substrate) reordered before WB-5 (binding) in the sequence. Updated sub-arc plan reflects this.).
- **Action authoring for button atoms** (action_kind dropdown + action_config form) → WB-7.
- **Per-atom theme/styling override** → WB-7.
- **Multi-operator collaborative authoring** → deferred indefinitely.
- **Mobile/touch widget authoring** → deferred indefinitely.
- **Live preview against real saved-view data** → WB-5.
- **Hover-reveal action buttons on atoms** → WB-7.
- **Internal filter/sort/search within widget** → WB-6 or post-September.
- **Arbitrary nesting beyond 2 levels** → deferred post-September.
- **Atom-catalog expansion** (sparkline / progress bar / list-table-grid container / time chip / avatar / link / badge / tooltip) → WB-7.

### Explicit non-goals

- No migration of the 28 existing hand-coded widgets to composed form. Hand-coded widgets continue rendering via their existing registerComponent + registerWidgetRenderer chains.
- No Tier-3 widget definition authoring (tenants cannot author widget shapes; placement-level chrome override is the tenant flexibility surface per the prior WB investigation Q-3 lock).
- No build-time codegen path (runtime interpretation only per the prior Q-2 lock).

---

## Area 10 — Architectural risks + mitigations

### Risk 1: Drop-target affordance UX brittleness

**At stake.** Flex-stack canvas with sibling-drop + container-drop has 3+ drop targets visible per gesture (root append zone + between-siblings zones + on-container zones). Visual chrome for drop affordance can either be invisible-until-drag (clean default; weak discoverability) or always-visible (cluttered; clear). Operator confusion likely if both kinds of drop are unclear.

**Mitigation.**
- Phase 1 ships drop zones HIDDEN by default; visible during drag (chromium-native pointer-events-driven affordance per entry 30 canon).
- Drop target highlight chrome (1px accent border on the target zone) PLUS the container atom gets a slight accent-tinted background during drag-over.
- Operator-validation gate per entry 26 — revisit post-staging if operators struggle.
- Source-shape regression gate on `WidgetBuilderCanvas.tsx` enforcing the drop-zone visibility logic.

### Risk 2: Inspector composition tree depth (2 nesting limit)

**At stake.** With 2-level nesting cap (a repeater_atom containing a conditional_container containing atoms), selecting an inner atom requires the operator to mentally navigate the tree. Inspector breadcrumb may be needed.

**Mitigation.**
- Phase 1 ships inspector with selected-atom breadcrumb at top: `Widget root > Repeater > Conditional > Status badge`. Operator can click any segment to ascend to that level.
- Selection chrome on canvas shows the selected atom AND its parent containers (subtle highlight outline).
- Operator-validation gate per entry 26 — revisit post-staging.

### Risk 3: Publish gate friction (operators forget to publish)

**At stake.** Draft-then-publish (Area 2 lock) imposes a discrete operator action. Inexperienced operators may make edits + close the tab + expect those edits to be live.

**Mitigation.**
- Draft-state pill prominently surfaces in widget list view AND on widget-builder top bar.
- Auto-save indicator clearly distinguishes "draft saved" (after debounce) from "published" (after Publish action).
- Closing the tab with unpublished edits surfaces an inline non-blocking banner: "You have unpublished changes" — operator clicks to return to publish.
- Operator-validation gate per entry 26 — if operators consistently forget to publish, consider a "scheduled publish" feature OR a Publish-on-tab-close prompt. Phase 1 ships the banner; revisit semantics.

### Risk 4: Saved-view binding picker placeholder in WB-4 leaks into operator perception

**At stake.** WB-4 ships repeater_atom inspector with a placeholder saved_view_id input (string) — operators can wire it abstractly but the resolved per-row data isn't yet real (WB-5 lights up real binding). Operator confusion likely: "I bound this repeater to my saved view; why doesn't the canvas show real rows?"

**Mitigation.**
- Inspector binding section in WB-4 surfaces explicit "Preview shows placeholder data until WB-5 ships" copy. NOT a hidden quirk.
- Repeater_atom inspector exposes the saved_view_id but disables the per-row field-binding UI on inner atoms (greyed out + tooltip: "Available after WB-5").
- Documentation in the widget-list view's empty state: "Today: compose widgets visually. Tomorrow: bind to live data."
- WB-4 → WB-5 ordering is sequential; the operator-perception gap closes in <1 week. Acceptable.

---

## Proposed WB-4 sub-arc execution plan

### Files (net-new)

- `backend/alembic/versions/r106_widget_definitions_published_blob.py` — migration.
- `backend/app/services/widget_definitions/publish.py` — publish action service (composition_blob → published_composition_blob + version bump + edit_session clear).
- `backend/app/api/routes/widgets.py` — extend with `POST /api/v1/widgets/{slug}/publish` endpoint.
- `frontend/src/bridgeable-admin/hooks/useComposedWidgetDraft.ts` — multi-hook-mount + debounced auto-save + 410-retry + edit_session.
- `frontend/src/bridgeable-admin/components/widget-builder/WidgetBuilderPage.tsx` — three-pane shell + breadcrumb + save/publish indicators.
- `frontend/src/bridgeable-admin/components/widget-builder/WidgetBuilderCanvas.tsx` — flex-stack canvas + drop targets + selection overlay.
- `frontend/src/bridgeable-admin/components/widget-builder/WidgetBuilderPalette.tsx` — left-rail atom palette.
- `frontend/src/bridgeable-admin/components/widget-builder/WidgetBuilderInspector.tsx` — right-rail composition.
- `frontend/src/bridgeable-admin/components/widget-builder/WidgetBuilderSelectionContext.tsx` — selection model.
- `frontend/src/bridgeable-admin/components/widget-builder/WidgetValidationBanner.tsx` — validation banner.
- `frontend/src/bridgeable-admin/components/widget-builder/WidgetBuilderBreadcrumb.tsx` — selected-atom breadcrumb.
- `frontend/src/bridgeable-admin/components/widget-builder/inspector-controls/*.tsx` — 9 inspector control components (one per atom_kind) + WidgetRootInspector + AtomConfigInspector composition.
- `frontend/src/bridgeable-admin/pages/WidgetListPage.tsx` — `/studio/widgets` list view.
- Test files alongside each above per JSDOM coverage canon.
- `frontend/tests/e2e/widget-builder-canvas.spec.ts` — Playwright spec.

### LOC estimate

Per the canon decomposition ceiling at ~2,500 LOC for operator-facing sub-arcs:
- Migration + service + endpoint: ~250 LOC.
- useComposedWidgetDraft hook: ~600 LOC (mirrors useFocusTemplateDraft's 937 LOC scaled for WB's narrower surface).
- WidgetBuilderPage + shell composition: ~400 LOC.
- WidgetBuilderCanvas + drop targets + selection overlay: ~500 LOC.
- WidgetBuilderPalette: ~150 LOC.
- WidgetBuilderInspector composition: ~200 LOC.
- 9 inspector control components: ~80 LOC each = ~720 LOC.
- WidgetBuilderSelectionContext + ValidationBanner + Breadcrumb: ~250 LOC.
- WidgetListPage: ~250 LOC.
- Test files (JSDOM + Playwright + source-shape gates): ~1,200 LOC (per FF-4 / FF-7 ratio).

**Midpoint estimate: ~4,500 LOC.** Worst-case: ~6,500 LOC (if inspector control components hit 120 LOC each; if Playwright spec exceeds 400 LOC).

**Above the 2,500 ceiling.** Possible split:
- **WB-4a** — Shell + canvas + palette + drop + selection + widget-root inspector + auto-save + publish endpoint (~3,000 LOC).
- **WB-4b** — 9 atom-kind inspector controls + validation banner + breadcrumb + list view (~2,500 LOC).

The split is natural at the seam: WB-4a ships a usable but inspector-limited canvas (operators can drop atoms + see them render + publish, but cannot edit atom-kind-specific config); WB-4b ships the per-atom config inspectors + validation surfaces. WB-4a ships visibly; WB-4b ships the polish to make widget authoring truly usable.

**Recommendation: ship WB-4 as a single arc at the ~4,500 LOC midpoint** if dispatch tolerance allows; split into WB-4a + WB-4b only if exceeded. The internal seam is clean.

### Dependencies

- WB-3 ships first (DONE at `4b6b173`).
- WB-4 ships before WB-5 (binding) which ships before WB-6 (saved-view substrate) — **revised ordering**: actually WB-6 (saved-view substrate) before WB-5 (binding) per Area 4 deferred-with-reason note; binding picker needs saved-view-shape introspection.
- WB-5 ships before WB-7 (polish + action authoring).
- WB-8 (demo seed) ships last.

---

## Operator-validation-sensitive locks (per entry 26)

Tagged for revisit-after-staging:

1. **Area 2** — Publish action surfacing (modal? toast? both?).
2. **Area 3** — Drop affordance UX (drop zones visible vs invisible-until-drag).
3. **Area 4** — Saved-view binding picker placeholder copy + greyed-out per-row field-binding UI.
4. **Area 5** — Validation banner + per-atom outline composition.
5. **Area 7** — Widget-list filtering + sorting UX.
6. **Area 7** — "From template" affordance — depends on whether seeded templates resonate.
7. **Area 7** — Slug auto-derivation collision behavior.
8. **Area 10 Risk 1** — Drop-target chrome treatment.
9. **Area 10 Risk 2** — Inspector breadcrumb depth + selection chrome on parent containers.
10. **Area 10 Risk 3** — Unpublished-changes banner semantics.

NOT operator-validation-sensitive (architecturally-determined):
- Area 1 lock (flex-stack canvas).
- Area 2 lock (draft-then-publish).
- Area 6 substrate boundaries.

---

## Process canon candidates (NOT filed; flagged for future canon-update arc)

1. **Shared-substrate auto-save vs per-instance auto-save distinction.** focus_templates auto-save works because templates are clone-able primitives, not the rendered thing. composition_blob auto-save would fail because composed widgets ARE the rendered thing. The shape of "auto-save vs draft-then-publish" depends on the substrate's relationship to render — shared-rendered-primitive substrates require draft-then-publish; instance-personalization substrates can use auto-save. Worth filing as canon.

2. **WYSIWYG discipline as canvas-layout-model constraint.** Area 1's flex-stack lock rests partly on: the canvas during authoring MUST render the same shape the runtime renders. Free-form during authoring → flex-flow at runtime would break WYSIWYG; reject the authoring shape. WYSIWYG discipline is a load-bearing constraint on canvas substrate choice. Worth filing.

3. **Sub-arc decomposition seam discovery during operator-facing arcs.** The prior WB investigation pre-decomposed WB into 8 sub-arcs against then-current state of the substrate. WB-3 actually shipped a different distribution of concerns (atom catalog runtime instead of shell+canvas). The decomposition naturally re-anchors as sub-arcs ship — but the canon doesn't yet document the pattern "investigation-time sub-arc decomposition is provisional; re-investigate when actual ship anchor differs." Worth filing.

4. **Substrate-relationship audit in shared-vs-instance contexts.** Area 2 lock surfaced that the auto-save vs draft-then-publish question is **identified by asking what reads the persisted state**. focus_templates reads come from focus_compositions instances (clone-relationship); widgets reads come directly from composition_blob (no clone). Investigation gate: enumerate ALL READ paths of persisted state before locking write semantics. Worth filing.

---

## Architectural surprises during investigation

1. **WB-3 container atoms already carry layout vocabulary.** `conditional_container` + `repeater_atom` have `direction` / `spacing` / `alignment` per `frontend/src/lib/widget-builder/runtime/atoms/index.tsx:679-686`. This is structural input for Area 1: flex-stack canvas matches the container atom layout vocabulary natively. The Area 1 lock for flex-stack is partly determined by what WB-3 already shipped.

2. **r105 session columns enable Area 2's lock without a new migration.** WB-1's proactive session column addition (flagged as ahead-of-need in the WB-1 build report) is load-bearing for the draft-then-publish lock. The Area 2 LOCK validates the WB-1 proactive decision retroactively. Only `published_composition_blob` needs to be added in WB-4 (migration r106).

3. **FF-2 substrate reuse cost is higher than first apparent.** Initial Area 1 audit suggested FF-2 reuse as a viable path (~1,036 LOC of free-form substrate). On closer inspection, the substrate is tightly coupled to Focus-specific concerns (WidgetPlacement shape, useFocusTemplateDraft hook, F-3.1c chrome-resolver, canvas-bounds-clamp). Mechanical reuse without forking refactor is not feasible. Build-new flex-stack is lower LOC and architecturally cleaner.

4. **Visual-editor metadata registry bridge (WB-3) closes the runtime registration loop already.** Composed widget definitions registered via `registerComposedWidgetsFromApi` get the registerComponent HOC wrapping for free; click-to-edit selectability is inherited from the canonical HOC chain. WB-4 inherits this without explicit substrate work.

5. **Sub-arc decomposition has refactored organically.** The prior WB investigation's sub-arc plan put "shell + canvas" as WB-3; WB-3 actually shipped atom catalog runtime instead. The decomposition isn't broken — concerns naturally migrated as the actual ship anchors revealed themselves. Process canon candidate #3.

6. **The Area 5 validation lock cascades from the Area 2 lock cleanly.** Auto-save into edit-session draft permits invalid intermediate states; Publish gates validity. Without Area 2 first, Area 5's "permissive auto-save + restrictive publish" composition is structurally impossible. Two load-bearing locks compose into the tactical Area 5 lock without conflict.

---

## Closing summary

WB-4 is the first operator-facing Widget Builder sub-arc. Two load-bearing decisions:

- **Area 1 (canvas layout model)** locked to **flex-stack** — matches container atom layout vocabulary (WB-3), aligns with production widget shape (stack-shaped), preserves WYSIWYG discipline, lower LOC than FF-2 reuse, separates Monitor/Decide canvas concerns from internal widget composition.
- **Area 2 (save semantics)** locked to **draft-then-publish via r103 session-aware pattern** — preserves shared-substrate widget rendering against operator's mid-edit scratch, validates WB-1's proactive session column addition, adds r106 migration for `published_composition_blob`.

Tactical locks derive cleanly: atom palette (Area 3) is a two-section flat catalog with drag-to-canvas; inspector (Area 4) reuses the FF-6 uncontrolled-with-sync pattern; validation (Area 5) auto-saves permissively + publishes strictly.

Cross-substrate dependencies (Area 6) enumerate ~10 reused substrates + ~11 net-new WB-4 components. Operator mental model (Area 7) is "Studio editor with widget list + new widget + edit existing + tier indicator + auto-save into draft + explicit publish." Test substrate (Area 8) follows the FF-series canonical 3-layer pattern: JSDOM behavioral + Playwright pointer-event + source-shape regression gate. Scope (Area 9) ships canvas authoring; defers binding (WB-5), saved-view substrate (WB-6), action authoring (WB-7), seed templates (WB-8). Risks (Area 10) center on drop affordance UX + Publish gate friction + the WB-5-dependency placeholder gap.

**Estimated LOC: ~4,500 midpoint (~6,500 worst case).** Possible WB-4a / WB-4b split at the natural seam between shell-and-canvas vs per-atom-inspector-and-list.

**Substrate continuity preserved.** Composed widgets render via WB-2's ComposedWidget unchanged. WB-3's atom catalog + visual-editor registry bridge consumed unchanged. WB-1 session columns load-bearing per Area 2 lock. No backtracking; clean forward extension.

**Operator-validation-sensitive locks tagged** (10 items) for revisit-after-staging. Process canon candidates (4 items) surfaced for future canon-update arc.
