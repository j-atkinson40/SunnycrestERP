# Widget Builder Investigation

Date: 2026-05-21
Purpose: Lock architectural decisions for the **widget-builder arc** — the operator-facing authoring substrate that produces composed widgets out of primitive atoms + data bindings + behavior contracts, dispatched against ten Areas: composition primitives, data bindings, behavior, rendering targets, operator mental model, registerComponent HOC coexistence, persistence, test substrate, future-builder coexistence, tier inheritance.
Status: Investigation closed; 40 questions enumerated (37 locked, 3 deferred-with-reason), 4 architectural risks surfaced with mitigations, decomposition into 8 sub-arcs.
Pre-flight: HEAD verified `a113d23` (FF-series consolidated canon-update arc; canon entries 31 → 42).
Working tree carries 114 stale Playwright screenshot deletions left untouched per scope discipline.
Estimated total WB-series LOC: ~9,500–14,000 across 8 sub-arcs (range; see §Sub-arc decomposition).
Recommended dispatch shape: **WB-1 → WB-2 → WB-3 → WB-4 → WB-5 → WB-6 → WB-7 → WB-8**, in order, no interleaving.

---

## Context

Yesterday's FF-series canon-update arc closed the Decide canvas substrate cycle (DECISIONS.md entries 22-42 across the May 19-21 batch). Widget Builder is the next-on-queue substrate concern that the FF-series and F-series investigations explicitly flagged as deferred: F-3 shipped THREE placeholder widgets (`day-strip-widget`, `today-pin-widget`, `map-placeholder-widget`) hand-coded as React components in `frontend/src/components/widgets/focus-builder/PlaceholderWidgets.tsx` (114 LOC, `PlaceholderShell` + 3 typed-shell exports per `focus-builder-widgets.ts` registry). DECISIONS.md 2026-05-13 entry "Widget authoring is data-source-first" locked the foundational principle: no widget can be authored without first selecting a Vault data source. Studio 1a-ii's overview surface enumerated "Widgets" as a future Studio editor surface; the current /studio/widgets route is a placeholder pending widget builder.

The current frontend codebase has **two layers of widget registration**:

1. **Visual-editor metadata layer** at `frontend/src/lib/visual-editor/registry/register.ts:174-238` — the `registerComponent` HOC that every widget invokes to declare metadata (`type`/`name`/`displayName`/`verticals`/`userParadigms`/`consumedTokens`/`configurableProps`/`schemaVersion`/`componentVersion`). The HOC wraps the component in a `display: contents` boundary div at line 215 carrying `data-component-name` / `data-component-type` / `data-component-version` for the runtime editor's `SelectionOverlay` click-to-edit gesture.
2. **Canvas runtime dispatch layer** at `frontend/src/components/widgets/foundation/register.ts` and `…/manufacturing/register.ts` — side-effect-on-import modules calling `registerWidgetRenderer(widget_slug, ComponentReference)` populating the canvas widget renderer registry consumed by `getWidgetRenderer(widget_id)` at canvas render time (Pulse / dashboard / focus_canvas / focus_stack / spaces_pin / bottom_sheet).

R-1.6.12 (per file header at `widgets.ts:20-29`) wired the second layer to consume **the wrapped output of the first** so canvas widgets carry the `data-component-name` boundary div at runtime. This is the load-bearing cross-substrate dependency the widget-builder arc cannot ignore.

The current widget catalog spans:

- 4 foundation widgets pre-Arc-1 (`today`, `operator_profile`, `recent_activity`, `anomalies`)
- 6 foundation widgets lifted Arc-1 into the wrapped set (`saved_view`, `briefing`, `email_glance`, `calendar_glance`, `calendar_summary`, `calendar_consent_pending`)
- Manufacturing-vertical widgets at `widgets.ts` (`vault_schedule`, `line_status`, `urn_catalog_status`)
- 3 F-3 placeholder widgets (`day-strip-widget`, `today-pin-widget`, `map-placeholder-widget`)
- Phase 1 dashboard widgets at `dashboard-widgets.ts` (963 LOC) + scheduling widgets at `scheduling-widgets.ts` (125 LOC) + workflow nodes + focus types + focus templates (5,262 LOC total across 15 registration files)

Every entry above is hand-coded in TypeScript and hand-registered at module bootstrap. The widget-builder arc operationalizes a substrate where operators (Bridgeable Platform admins authoring Tier 1/2 widgets; tenants authoring Tier 3 widget instances) produce widget definitions through a Studio editor without writing TypeScript.

**Canon entries this investigation answers to (must-cite):**

- DECISIONS.md 2026-05-13 — Studio as consolidated visual authoring environment
- DECISIONS.md 2026-05-13 — Widget authoring is data-source-first
- DECISIONS.md 2026-05-18 — Cores are canonical-shared-across-verticals (analog: widget primitives may be canonical-shared)
- DECISIONS.md 2026-05-18 — Template vertical is design-time-permanent (analog: widget definition vertical)
- DECISIONS.md 2026-05-19 — Multi-hook-mount pattern for builder UIs surfacing heterogeneous subjects
- DECISIONS.md 2026-05-19 — Component registry requires ≥3 configurableProps per registration (hard constraint — widget builder MUST produce registrations satisfying this)
- DECISIONS.md 2026-05-19 (PM) — Ordinary template updates version-bump by default; URL stability via slug-based addressing (analog: widget definition versioning)
- DECISIONS.md 2026-05-19 (late PM) through 2026-05-19 (late evening) — Cross-side contract framing (save-side + render-side + operator-observable assertions at rendered elements)
- DECISIONS.md 2026-05-20 — Monitor canvas vs Decide canvas distinction (widgets render on BOTH; substrate must serve both)
- DECISIONS.md 2026-05-21 entry 28 — Cross-substrate HOC audit (registerComponent HOC display:contents wrapper at register.ts:215)
- DECISIONS.md 2026-05-21 entry 30 — All pointer-event surfaces require Playwright coverage
- DECISIONS.md 2026-05-21 entry 31 — Source-shape regression gate as test-substrate pattern

**FF-series substrate inherited forward:**

- `useFocusTemplateDraft` multi-hook-mount + 410-retry + draft-ref-against-stale-closure pattern (per 2026-05-19 + C-2.1.4 canon)
- F-3.1a placement adapter pattern (frontend chrome blob ↔ backend `prop_overrides`)
- F-3.1c cross-side render+save integration test discipline
- E-1 empty-blob discipline (operator-typed empty objects preserved verbatim through round-trip)

**FF-series substrate NOT directly applicable but precedent-shaped:**

- FF-series ships **placements on Focus canvas**. Widget builder ships **widget definitions** which become placement targets. Different scope. WB does not have a free-form canvas (the widget authoring surface is the data + atoms + bindings editor; placements happen at Focus Builder).

**F-series substrate consumed unchanged:**

- `useFocusTemplateDraft` debounce + save + version-bump + URL recovery — analog hook for `useWidgetDefinitionDraft` follows the same shape.
- `chrome-resolver.ts` — chrome resolution patterns apply unchanged to composed widget chrome.
- `FocusBuilderSelectionContext` — selection model precedent for nested-atom selection within widget builder canvas.

---

## Canonical UX target

The widget-builder Studio editor surfaces an authoring environment with **three load-bearing canvas regions**:

```
┌─ Platform › Widgets › author-mode › Funeral Schedule Card ───────────────┐
│  Auto-saved 12s ago                                                       │
├─────────────────────┬──────────────────────────────────┬─────────────────┤
│                     │                                  │                 │
│  Data source        │       Widget composition          │   Atom + chrome│
│  (left rail)        │       canvas (center)            │   inspector    │
│                     │                                  │   (right rail) │
│                     │                                  │                │
│  ▣ Vault saved view │   ┌─────────────────────────┐    │ Selected atom: │
│    "Today's deliv-  │   │  ┌──────────┐           │    │   Status badge │
│    eries"           │   │  │ [Status] │  Hopkins  │    │                │
│                     │   │  └──────────┘  Smith    │    │ Binding:       │
│  Bound fields:      │   │  ┌──────────────────┐   │    │   delivery.    │
│   • delivery_id     │   │  │ Hole dug at 7:42 │   │    │   status       │
│   • status          │   │  └──────────────────┘   │    │                │
│   • assigned_at     │   │  ┌────────────┐         │    │ Map:           │
│   • driver_name     │   │  │  Out 09:15 │         │    │  scheduled →   │
│   • ETA             │   │  └────────────┘         │    │    [info chip] │
│   • cemetery        │   │                         │    │  hole_dug →    │
│                     │   └─────────────────────────┘    │    [success]   │
│  (Iteration scope:  │                                  │  out_for_del → │
│   per row, fan-out  │                                  │    [warning]   │
│   to N cards)       │                                  │                │
│                     │                                  │ Chrome:        │
│                     │                                  │  surface →     │
│                     │                                  │   elevated     │
│                     │                                  │  radius → 12   │
└─────────────────────┴──────────────────────────────────┴─────────────────┘
```

- **Left rail**: data source picker (Vault saved view / item-type filter / ad-hoc query). Selected source surfaces bound fields below; iteration scope declared (per-row fan-out for list-shaped widgets, single-snapshot for scalar widgets).
- **Center canvas**: widget composition surface. Atoms (text labels / value displays / icons / status badges / dividers / nested groupings) are dragged from a palette or added via context-menu. Atoms bind to fields from the left rail (drag field onto atom → binding established). Sub-selection works at atom level for chrome editing.
- **Right rail**: inspector. When an atom is selected, shows the atom's binding (field source + optional value-map for enums) + chrome (per-atom override) + behavior (click → navigate / open Focus / no-op). When the widget root is selected, shows widget-level chrome (corners, padding, surface) + the widget's surface-availability declarations (Glance / Brief / Detail / Deep variant shapes per §12 of DESIGN_LANGUAGE).
- **Background click**: deselect → show widget root inspector.
- **Tier indicator** at top: "Editing Tier 2 (vertical_default for funeral_home)" / "Editing Tier 3 (tenant override at Hopkins FH)".

The mental model is **Figma-like compositional editor on a Vault row** — operators are building a card layout that will render once-per-row from a Vault query (or once-as-snapshot for scalar widgets). The fan-out is configured at left-rail iteration scope; the visual composition is one row's render.

This UX surface is the central hypothesis the investigation locks against. It is consistent with the 2026-05-13 "data-source-first" canon (no widget without a source picked first), the 2026-05-13 Studio thesis (single-app metaphor across editors), the §9.4 BRIDGEABLE_MASTER thesis ("widgets are Vault views with chrome"), and the §12 DESIGN_LANGUAGE widget-variant taxonomy (Glance/Brief/Detail/Deep).

---

## Locked decisions

### Area 5 — Operator mental model (Q-1 through Q-3) — LOAD-BEARING

Per the dispatch prompt's "load-bearing UX decision" classification, this area is locked first because every other Area inherits its consequences.

#### Q-1: Composition model (A / B / C)

**At stake:** What is the operator's primary act when building a widget?

**Options:**
- (a) **Template-based** — operator picks a widget archetype ("status card", "list with header", "stat tile") from a fixed catalog of templates; fills in slots with data; the template's shape is locked.
- (b) **Free composition of atoms** — operator drags individual atoms (text label, value display, icon, status badge, divider, nested group) onto a blank canvas; binds each atom to a data field; arranges them spatially with flex/grid containers.
- (c) **Hybrid** — operator picks a starting template (or "blank") + freely modifies the composition (add atoms, remove atoms, restructure). Templates are seed shapes, not final shapes.

**Reasoning:**

- (a) is the lowest-LOC, fastest-to-ship path. Most enterprise widget builders ship this way (Salesforce Lightning Components, Notion-style block templates). Cost: ceiling on what operators can express. Every "I need a widget shaped like X" requires platform code to add X as a template type. For a four-vertical platform with cross-vertical product lines + future verticals, the template proliferation eventually demands a richer model.
- (b) is the highest-ceiling path but highest-LOC. Pure free composition requires solving layout (flex/grid container nesting), atom catalog completeness from day one, and operator competence with compositional thinking. Most operators struggle with pure free composition (Webflow-style learning curve is real). Cost: months of substrate work before any value ships.
- (c) starts operators with a seed shape they can immediately modify. Locks the template gallery as "common patterns" without forcing those patterns to be terminal. Allows the atom catalog to grow as concrete needs emerge — first few widgets ship as template-only-no-modification; later widgets exercise the modification path.

**Canon cross-check:**
- DECISIONS.md 2026-05-13 "Widget authoring is data-source-first" anchors authoring on data source selection, not template choice. (a) couples data source to template post-hoc; (b) and (c) both honor the data-first canon naturally.
- BRIDGEABLE_MASTER §9 widget thesis ("widgets are Vault views with chrome") aligns with all three options structurally.
- DESIGN_LANGUAGE §12 variant taxonomy (Glance/Brief/Detail/Deep) is variant-per-widget, not per-template — meaning every authored widget must carry four variants regardless of the composition path. (a)'s templates would need to declare four variants per template; (b)'s composition canvas would need a variant-switcher; (c) inherits the same complexity but distributes it through both layers.

**LOCKED: (c) — hybrid.** Starting templates for common patterns + free modification of atoms within the chosen template. The template seed makes the first widget achievable in minutes (operator picks "status card", points at saved view, ships); the modification path lets operators evolve a widget past its seed shape. The atom catalog grows incrementally as concrete needs emerge — WB-series ships ~6-8 atom types Phase 1 (text label, value display, icon, status badge, divider, conditional container) covering 80% of observed widget needs.

**Alternative considered + rejected**: pure (b) was rejected because the substrate cost to ship a usable atom-only canvas + container nesting + responsive variant authoring is prohibitively high relative to the demo timeline + operator learning curve. Pure (a) was rejected because the template proliferation cost over time exceeds the substrate cost of (c)'s modification path.

#### Q-2: Coexistence sub-option (a / b / c)

**At stake:** How do composed widgets coexist with the current register.ts hand-coded widget registrations?

**Options:**
- (a) **Build-time codegen** — composed widget definitions in the DB compile to React components emitted as `.tsx` files at deploy time; same registerComponent HOC; identical runtime DOM shape to hand-coded widgets.
- (b) **Runtime interpretation** — single generic `ComposedWidget` runtime renderer reads widget definition from DB at render time + dispatches atoms accordingly. Hand-coded widgets and composed widgets share the same canvas runtime dispatch table but render through different code paths.
- (c) **Coexistence (both render paths)** — legacy React widgets continue to ship via hand-coded `registerComponent` + `registerWidgetRenderer` calls; composed widgets ship via `ComposedWidget` runtime renderer keyed on a generic `composed_widget` registration. Both paths coexist indefinitely.

**Reasoning:**

- (a) is the highest-purity path — composed widgets are indistinguishable from hand-coded widgets at runtime. Cost: build pipeline complexity (template engine + tsc invocation at deploy time + handling of failed builds + Git artifact tracking + chicken-and-egg if a composed widget references a TypeScript dep that isn't installed). Operators cannot ship widget changes between deploys. Cost > value for a platform with ~weekly deploys.
- (b) is the lowest-LOC path. One `ComposedWidget` renderer interprets all composed widget definitions. Cost: every render walks a JSONB-shaped definition tree; performance ceiling per render is bounded by atom tree depth. For widgets with O(10) atoms this is fine; for widgets with O(100) atoms it requires optimization. Most widgets observed in the platform today are O(10) atoms; the ceiling is unlikely to bite pre-September.
- (c) is the pragmatic path — preserves the existing 28 hand-coded widgets unchanged, ships composed widgets through a new render path, lets both coexist. Cost: two code paths means two test surfaces, two bug surfaces, two maintenance overheads. Benefit: zero migration cost for existing widgets, composed widgets can ship without regressing hand-coded widgets.

**Canon cross-check:**
- DECISIONS.md 2026-05-19 entry "Multi-hook-mount pattern for builder UIs surfacing heterogeneous subjects" generalizes: heterogeneous content models in the same builder UI are canonically supported. (c) extends this generalization from hook-level to render-path-level.
- DECISIONS.md 2026-05-21 entry 28 "Investigation cross-substrate HOC audit" — registerComponent HOC's display:contents wrapper is load-bearing for runtime-editor click-to-edit. (a) and (c) both preserve the wrapper via running registerComponent at composition emit; (b) requires running registerComponent dynamically OR replicating the wrapper inside the ComposedWidget renderer.

**LOCKED: (c) — coexistence.** The 28 hand-coded widgets continue rendering unchanged via their existing registerComponent → registerWidgetRenderer chains. Composed widgets ship via a new `ComposedWidget` runtime renderer registered ONCE under widget slug `composed_widget` (or generic dispatch keyed on widget definition's `kind`). The composed widget's actual configuration lives in `widget_definitions` table (existing) extended with a `composition_blob` JSONB column (new — WB-1) describing atoms + bindings + layout. Both render paths coexist long-term; the migration of hand-coded widgets to composed is not a goal of WB-series. Hand-coded widgets that operators want to modify but cannot author in WB (e.g., complex widgets like `AnomaliesWidget` with bespoke state machines) stay hand-coded.

**Alternative considered + rejected**: (a) was rejected because the build-pipeline cost is disproportionate to the value at this stage; tenant-tier composed widgets MUST be authorable without a deploy, which (a) cannot serve. (b) without (c) was rejected because forcing the 28 existing widgets onto the runtime-interpretation path adds risk + LOC without value.

#### Q-3: Widget identity per authoring path

**At stake:** When a tenant authors a Tier-3 widget override, is it a NEW widget or a customization of an existing one?

**Options:**
- (a) **Forking model** — Tier-3 widget is a new widget definition with a new `widget_id`, no inheritance relationship to Tier-2 parent.
- (b) **Inheritance model** — Tier-3 widget has same `widget_id`, deltas stored against Tier-2 base, resolved at READ.
- (c) **Per-instance override at placement level** — widget definition stays Tier-2; per-placement `prop_overrides` (existing) carry tenant-specific atom binding/chrome overrides.

**Reasoning:**

- (a) loses cross-platform updates entirely (Tier-1 platform updates do not propagate to forked Tier-3 widgets). Matches the workflow_templates fork model from Phase 8a + the focus_templates fork model from F-2. Operator-comprehensible: "this is my version, untouched by future platform changes."
- (b) is closer to focus_compositions and platform_themes inheritance — first-match-wins read time + delta-only persistence. Tier-1 platform updates DO propagate to Tier-3 deltas unless the tenant has overridden the specific field. Better long-term hygiene; harder to reason about ("why did my widget change?").
- (c) is the lightest path: NO Tier-3 widget definitions, just per-placement chrome overrides on Tier-2 widgets. Operators cannot author entirely-new widgets at tenant tier (only platform admins author the widget DEFINITION; tenants can ONLY override placement-level chrome). Severely constrains tenant flexibility; canonically matches the existing 5-axis filter model (widget catalog = Tier-1+2; per-placement chrome already exists).

**Canon cross-check:**
- DECISIONS.md 2026-05-13 entries on Studio + scope-as-mode lock the three-tier inheritance shape for visual authoring (platform_default → vertical_default → tenant_override). All three editors (themes, components, workflows) follow this shape; new editors should follow it.
- DECISIONS.md 2026-05-13 "Live mode is vertical-or-tenant-tier authoring; platform-tier changes happen in Edit mode" implies tenants CAN author at tenant tier via Live mode — meaning (c)'s "tenants cannot author widget definitions" stance is incongruent with the broader Studio thesis.
- BRIDGEABLE_MASTER §9 "widgets are Vault views with chrome" — chrome is a per-placement concern; the widget's shape (atoms + bindings + layout) is platform-tier. (c) honors this most naturally; (a) and (b) generalize to "tenants can author widget shape too" which is a richer claim.

**LOCKED: hybrid (c) + (b)** — Platform-tier (Tier 1) and vertical-tier (Tier 2) widget definitions are authored by platform admins via Studio Edit mode. Tenant-tier (Tier 3) "widgets" are NOT new widget definitions; they are per-placement chrome+binding-override blobs stored at placement level (existing `prop_overrides`). When a tenant needs an entirely-new widget shape, they request platform-admin promotion (a new vertical_default Tier-2 widget definition or a one-off platform_default Tier-1). Tier-1 → Tier-2 → placement-level chrome override is the canonical authoring stack; field-level inheritance per (b) for chrome overrides.

**Future expansion path (post-September):** if tenant-tier widget definitions become a real demand, add a `tenant_widget_overrides` table parallel to `focus_compositions`. Defer until concrete demand surfaces.

---

### Area 1 — Composition primitives (Q-4 through Q-10)

#### Q-4: Atom catalog Phase 1

**At stake:** What atoms ship in the WB-series Phase 1 catalog?

**Options:**
- (a) Minimal — 4 atoms (text label, value display, icon, divider). Forces composition discipline at the cost of widget expressiveness.
- (b) Adequate — 8 atoms (text label, value display, icon, status badge, divider, button/action, image, conditional container).
- (c) Maximal — 15+ atoms (above + list/table/grid container, time chip, progress bar, sparkline, avatar, link, badge, tooltip, etc.).

**Reasoning:**

- (a) covers ~50% of observed widget patterns. Status badges (which are everywhere) require composition out of text + icon + chrome at every render site — operator friction.
- (b) covers ~85% of observed widget patterns per audit of the 28 existing widgets. Status badge as a first-class atom + button/action for the limited per-§12.6a action surface + image (for the future Vault asset story) + conditional container (for "render this row only if X") covers the breadth without ballooning the atom test surface.
- (c) covers ~95% but the marginal value per atom drops fast. List/table/grid container should NOT be Phase 1 atoms — they are layout containers, addressed in Q-5. Sparkline + progress bar are visualization-specific and warrant their own arc.

**Canon cross-check:**
- DECISIONS.md 2026-05-19 "Component registry requires ≥3 configurableProps per registration" — each atom registration must satisfy this. Atoms are themselves `registerComponent`-registered atoms with the canonical metadata shape.

**LOCKED: (b) — 8 atoms Phase 1.** `text_label` (static or templated string), `value_display` (single bound field with format spec — number/currency/percent/date/duration), `icon` (Lucide-name-keyed), `status_badge` (composite: text + icon + status family), `divider` (1px hairline + spacing), `button` (label + action_ref), `image` (URL or Vault asset ref), `conditional_container` (children render only when `condition` evaluates true). Each atom ships with the canonical ≥3 configurableProps.

**Risks:**
- Atom catalog over-narrow + early friction. Mitigated by reserving WB-7 explicitly for atom-catalog-expansion based on observed pain points.
- Composite atoms (status_badge) hide composition that operators may want to deconstruct. Operator can swap status_badge for `text + icon + status family` sub-composition at any time; status_badge is sugar.

#### Q-5: Layout containers

**At stake:** How are atoms arranged spatially within a composed widget?

**Options:**
- (a) **Single flex direction** per widget — operator picks "row" or "column" at widget root; all atoms render in flex flow. No nesting.
- (b) **Two-level nesting** — root flex (row/column) + one level of inner groupings. Each group has its own flex direction.
- (c) **Arbitrary nesting** — operator can nest containers infinitely with flex/grid/absolute positioning.

**Reasoning:**

- (a) is the simplest substrate. ~70% of observed widgets fit this model (a status card with `[icon] [text] [badge]` in a row). Cost: complex widgets (a card with header + body + footer regions) cannot be expressed.
- (b) covers ~95% of observed widget patterns. Most observed widgets have at most one level of grouping (header row + body column + actions row).
- (c) covers 100% but operators struggle with arbitrary nesting (Webflow learning curve). Cost: substrate complexity + testing surface explosion.

**LOCKED: (b) — two-level nesting.** Root widget is a flex container (operator chooses row/column at widget level). Each atom OR group sits at root level. Groups can hold atoms but not other groups (one level of nesting). This shape matches ~95% of observed widget patterns and bounds the composition-tree depth at 2, which keeps the runtime interpreter (per Q-2 lock) fast.

**Deferred-with-reason:** Arbitrary nesting (c) deferred to post-September. If concrete operator demand surfaces for 3+ levels of nesting, the substrate can extend in a backward-compatible way (the JSONB composition blob accepts deeper trees; the runtime interpreter recurses).

#### Q-6: Atom registration substrate

**At stake:** Are atoms registered via `registerComponent` (the same path as today's widgets) or via a new atom-specific registration substrate?

**Options:**
- (a) **Atoms as widgets** — every atom is a `registerComponent({type: "widget", ...})` registration. Composed widgets nest atom widgets via the composition blob. Atoms are placeable on Focus canvas individually (potentially confusing).
- (b) **Atoms as a new ComponentKind** — add `"widget-atom"` to the ComponentKind discriminator in `types.ts:38-73`. Atoms are NOT placeable on Focus canvas; they only render within composed widgets.
- (c) **Atoms are runtime-only** — atoms are NOT registered components; they are runtime renderers inside `ComposedWidget` keyed on atom_type string in the composition blob.

**Reasoning:**

- (a) re-uses the existing substrate verbatim but causes operator confusion (Focus Builder palette would surface atoms as droppable widgets, which they shouldn't be — atoms only make sense inside a composed widget).
- (b) honors the existing registry shape + adds a clean discriminator. `canvasPlaceable: false` already exists on `RegistrationMetadata` — atoms set this to `false` so they don't surface in Focus Builder palette. The new `"widget-atom"` ComponentKind is documented in registry; visual editor surfaces atom selection in WB's atom palette only.
- (c) is the lightest path — atoms are not registry citizens, just enums in the composition blob handled by `ComposedWidget`. Cost: atoms have no metadata (no `consumedTokens`, no configurableProps schema, no per-atom inspector control rendering). Inspector composition for atom configuration becomes hand-coded per atom_type rather than registry-driven.

**Canon cross-check:**
- DECISIONS.md 2026-05-21 entry 28 — registerComponent HOC display:contents wrapper. Atoms registered via the HOC inherit the wrapper for free, which preserves click-to-edit selectability on the runtime-editor side. (c) does not get this for free.
- DECISIONS.md 2026-05-19 — ≥3 configurableProps. (b) enforces this for atoms; (c) doesn't.

**LOCKED: (b) — atoms as new ComponentKind `"widget-atom"`.** New ComponentKind added to `types.ts` ComponentKind union. Atoms register via `registerComponent({type: "widget-atom", name: "value-display", canvasPlaceable: false, ...})`. Each atom carries ≥3 `configurableProps` matching the registry contract. Atoms inherit the display:contents wrapper, which means atom-level click-to-edit works in runtime editor (selecting an atom within a composed widget on a tenant's deployed page).

#### Q-7: Atom prop binding shape

**At stake:** How does an atom express "this value comes from field X of the iteration scope"?

**Options:**
- (a) **String template** — atom's `text` prop = `"{{ delivery.driver_name }}"`. Jinja-style; runtime interpolation.
- (b) **Structured binding** — atom's prop carries a `BindingRef` object: `{kind: "field_path", path: "delivery.driver_name"}` or `{kind: "literal", value: "Hopkins"}`.
- (c) **Hybrid** — string templates for simple cases; structured bindings for complex cases (transforms, conditionals).

**Reasoning:**

- (a) is operator-familiar (every legacy template syntax). Cost: parsing fragility, weak validation, no type-safety at author time.
- (b) is structural + validatable + type-safe. Cost: cannot mix literals + bindings within a single string (`"{driver_name}, on the way"` requires concatenation atom).
- (c) is the pragmatic middle ground.

**Canon cross-check:**
- DECISIONS.md 2026-05-19 (PM) — Off-by-one column index between frontend and backend placement coordinates surfaced via mismatched type representations. Structured bindings (b) avoid that class of bug.

**LOCKED: (b) — structured binding only.** Atom props carry `BindingRef` objects of three kinds: `{kind: "literal", value: ...}` / `{kind: "field_path", path: "delivery.driver_name", fallback?: ...}` / `{kind: "expression", expression: "<sandboxed-subset>"}` (deferred to WB-7; Phase 1 atoms only support literal + field_path).

**Deferred-with-reason:** expression bindings (filter/transform/derive) deferred to WB-7. Operators initially live with literal + field_path; demand for expression bindings surfaces concrete shapes that inform what the expression subset needs to support.

#### Q-8: Value formatter substrate

**At stake:** How do operators specify "render this number as currency" / "render this date as MM/DD"?

**Options:**
- (a) **Per-atom formatter prop** — `value_display` atom has a `format` prop with enum (number / currency / percent / date / time / duration / status); each format has its own sub-config.
- (b) **Format library at binding level** — `BindingRef.format` carries the format spec; any atom consuming the binding picks up the format.
- (c) **Format as separate atom** — `value_display` atom takes raw value; operator composes formatter atoms in front of it.

**Reasoning:**

- (a) is the natural shape for the `value_display` atom (which is the primary consumer of formats). Cost: format logic per-atom; status_badge needs its own format vocabulary.
- (b) decouples format from atom — every atom consuming a `BindingRef` knows how to render the formatted value. Cleaner separation; harder to author (operator must understand format-belongs-to-binding rather than format-belongs-to-display).
- (c) is over-engineered for the atom-catalog ceiling.

**LOCKED: (a) — per-atom formatter prop.** `value_display` carries `format: enum` + `format_config: object`. `status_badge` carries `status_map: Record<string, StatusFamily>` mapping observed values to status families. Each format-aware atom owns its format vocabulary.

#### Q-9: Container chrome vs atom chrome

**At stake:** Per-atom chrome (surface, radius, padding) — does it exist?

**Options:**
- (a) **Atom-level chrome only** — every atom has chrome props (surface_token, padding, border, radius). Composition is "stack atoms with their own chrome."
- (b) **Container-level chrome only** — chrome lives on the widget root OR on container groups. Atoms are chromeless; they render text/icons in the chrome's box.
- (c) **Both** — atoms have per-atom chrome (rare overrides); containers carry default chrome.

**Reasoning:**

- (a) leads to nested boxes-within-boxes visual chaos. Most widgets have one chrome layer (the card) + inner atoms that don't need their own chrome.
- (b) is closer to design discipline. `status_badge` is the canonical exception (it has its own surface treatment); model it as a composite atom with built-in chrome rather than a normal atom with chrome props.
- (c) is over-engineered; operators don't reach for per-atom chrome 90% of the time.

**LOCKED: (b) — container-level chrome only.** Widget root + groups carry chrome (surface_token, padding_token, border_token, radius_token, shadow_token). Atoms are chromeless except for `status_badge` (composite atom with built-in chrome variants). Per-atom chrome can be added in WB-7 if concrete demand surfaces.

#### Q-10: Variant taxonomy (Glance / Brief / Detail / Deep)

**At stake:** DESIGN_LANGUAGE §12 mandates four variant shapes per widget. How does WB serve this?

**Options:**
- (a) **One composition per variant** — operator authors 4 separate compositions, one per variant. Most explicit.
- (b) **Single composition + variant-driven atom visibility** — atoms declare `visible_in_variants: ["brief", "detail"]`; one composition renders four shapes based on which atoms are visible.
- (c) **Default + delta variants** — operator authors a `default` composition (typically Brief); other variants declared as deltas (Glance = "hide these atoms", Detail = "add these atoms + restructure").

**Reasoning:**

- (a) is most explicit but quadruples authoring effort.
- (b) is the natural fit for the variant taxonomy — `Glance` is "tiny pin of the most-essential data", `Brief` is "card with key data", `Detail` is "card with all data", `Deep` is "panel with all data + history". The variants are subsets/supersets of each other most of the time. Author-once-render-four-ways aligns with the canon "same widget, different surfaces" thesis (BRIDGEABLE_MASTER §9.2).
- (c) is the closest analog to focus_compositions inheritance but adds a per-variant resolver layer.

**LOCKED: (b) — single composition + variant-driven atom visibility.** Each atom carries `visible_in_variants: VariantId[]` (subset of `["glance", "brief", "detail", "deep"]`). The widget renders different shapes by filtering atoms per variant at render time. Container chrome can also have per-variant overrides (`chrome_per_variant: Record<VariantId, ChromeOverride>`).

---

### Area 2 — Data bindings (Q-11 through Q-16)

#### Q-11: Data source vocabulary

**At stake:** What does "select a data source" actually pick from?

**Options:**
- (a) **Vault saved view only** — operator picks a saved view from the catalog. The view defines the query + filter + sort; the widget iterates rows.
- (b) **Saved view OR direct VaultItem-type filter** — operator picks a saved view OR composes an ad-hoc filter directly against a VaultItem type.
- (c) **Saved view OR VaultItem filter OR cross-system query (joins across hubs)** — full querying ceiling.

**Reasoning:**

- (a) is the simplest substrate. Reuses the existing saved-views catalog. Cost: operator must create saved views before widgets; some widgets want bespoke queries that don't make sense as catalog entries.
- (b) is the pragmatic middle ground. Saved views for catalog-able queries; ad-hoc filters for one-off widgets.
- (c) requires cross-hub query semantics that don't exist today.

**Canon cross-check:**
- BRIDGEABLE_MASTER §9.4 — "widgets are Vault views with chrome." Vault is the foundational data layer; widgets project Vault state.
- BRIDGEABLE_MASTER §3 (Three primitives — Spaces / Saved Views / Pins) — saved views are first-class platform primitives; widgets composing over them is canonical.

**LOCKED: (a) for WB-Phase-1.** Operator picks a Vault saved view. Direct VaultItem-type filter authoring (b) deferred to WB-6 or post-September depending on demand. Cross-system queries (c) deferred indefinitely until cross-hub query semantics exist as canonical platform infrastructure.

**Operator-friction mitigation:** widget builder Step 1 includes an inline "Create saved view" affordance that opens the saved-view creator in a modal/side panel. Operator can create the view, save it, and have it pre-selected as the widget's source. Reduces the "I need a view first" friction without expanding the widget-side substrate.

#### Q-12: Iteration scope declaration

**At stake:** How does the operator declare "this widget renders once-per-row" vs "this widget renders one scalar summary"?

**Options:**
- (a) **Inferred from saved view** — if the saved view is list-shaped (multiple rows), widget iterates; if scalar-shaped (single row or aggregate), widget renders once.
- (b) **Explicit operator choice** — operator declares iteration mode in widget builder: "per-row card" / "single summary" / "aggregate stat".
- (c) **Per-variant iteration** — Glance is always scalar (single summary), Brief is per-row, Detail is per-row, Deep is per-row.

**Reasoning:**

- (a) inference is fragile — same saved view can drive both scalar widget (count) and per-row widget (table). Operator may want both.
- (b) is the most flexible — operator picks. Cost: another decision in the authoring flow.
- (c) is consistent with §12 variant taxonomy but rigid (Glance can sometimes be per-row in canonical cases like a chip strip).

**LOCKED: (b) — explicit operator choice.** Widget builder's left rail has an "Iteration mode" picker: `per_row` (widget renders N times, one per saved-view row) | `single_summary` (widget renders once over the entire result set; atoms bind to aggregate functions like `count`, `sum`, `max`) | `single_record` (widget renders once over the first/active record). Defaults driven by saved-view shape but operator can override.

#### Q-13: Missing-data + error states

**At stake:** What renders when a binding resolves to null / undefined / error?

**Options:**
- (a) **Render nothing** — atom is absent; layout reflows.
- (b) **Render placeholder** — `--` or `Loading…` per atom + atom type.
- (c) **Operator-configured fallback** — each binding declares a `fallback` value.
- (d) **Atom-level + widget-level** — atoms render placeholder; widget root renders error/skeleton state for whole-widget failure.

**LOCKED: (c) for atom-level + canonical (d)-style for widget-level.** `BindingRef.fallback` per atom (Q-7). Widget-root error/skeleton states are canonical patterns rendered by `ComposedWidget` (skeleton when loading, error chrome when source fails). Widget-root chrome is operator-modifiable; per-atom fallbacks are operator-modifiable.

#### Q-14: Permission interaction

**At stake:** Operator authors a widget. The widget renders on a tenant where the operator authoring the widget has permission X but the rendering user has only permission Y.

**Options:**
- (a) **Server-side filtering** — widget's underlying saved view enforces permissions at query time. Widget renders whatever rows the user can see.
- (b) **Per-atom permission gate** — each atom carries `required_permission`; atom hidden if user lacks permission.
- (c) **Both** — server-side filters rows; per-atom gates fields within a row.

**LOCKED: (c).** Server-side row filtering via saved view (existing). Per-atom permission gates via optional `required_permission` field on atom config. Defaults to no gate (atom always renders); operator opts into gating per atom.

#### Q-15: Reactive vs snapshot rendering

**At stake:** Does the widget re-fetch when underlying data changes mid-session?

**Options:**
- (a) **Snapshot on mount** — widget fetches data once, renders. Refresh via manual reload.
- (b) **Polling interval** — widget polls every N seconds (operator configures via widget-level prop).
- (c) **WebSocket-driven** — widget subscribes to data changes via WebSocket channel.

**LOCKED: (b) for WB-Phase-1.** Operator declares `refresh_interval_seconds` at widget level (default 300s, range 60-3600s — matches the existing `TodayWidget.refreshIntervalSeconds` precedent in `widgets.ts:111-118`). WebSocket-driven (c) deferred until platform has canonical real-time substrate.

#### Q-16: Live preview during authoring

**At stake:** Does the widget builder render live data during authoring?

**Options:**
- (a) **Mock data** — widget builder uses synthetic mock data matching the saved view's shape.
- (b) **Live data, capped row count** — widget builder fetches actual data, caps to 5-10 rows for performance.
- (c) **Operator-selected sample record** — operator picks one record (or last 3) from the live data as the preview anchor.

**LOCKED: (c) primary + (b) fallback.** Operator picks one (or up to 3) sample records from the live saved view as the preview anchor. Widget composition canvas renders those samples. Empty-state preview when no sample data exists (fallback to (a) with synthetic data clearly marked "Sample").

---

### Area 3 — Behavior (Q-17 through Q-22)

Behavior is bounded by DESIGN_LANGUAGE §12.6a "Widget interactivity discipline" — state changes are widget-appropriate; decisions belong in Focus.

#### Q-17: Click → behavior vocabulary

**At stake:** What can a widget atom / widget root do on click?

**Options:**
- (a) **Navigate only** — click → goto URL. Simplest.
- (b) **Navigate + open Focus + open peek** — three canonical click targets.
- (c) **Above + mutate (state flip) + trigger workflow** — full action vocabulary.

**Canon cross-check:**
- DESIGN_LANGUAGE §12.6a — widgets allow bounded state flips (acknowledge-anomaly, mark-read). Anything more complex routes to Focus.
- PLATFORM_INTERACTION_MODEL — chip pattern; peek panels; pause sensor; observe-and-offer.

**LOCKED: (c) bounded.** Click targets supported: `navigate` (URL or route) / `open_focus` (Focus invocation with widget data as context) / `open_peek` (peek panel for entity) / `mutate` (bounded single-field state flip with audit trail; ONLY for state-change-widget-appropriate per §12.6a) / `trigger_workflow` (named workflow invocation; bounded confirmation gate). Each click target carries a structured action ref similar to Q-7's BindingRef.

#### Q-18: Action target binding

**At stake:** How does the click target reference the entity being clicked?

**Options:**
- (a) **Implicit** — click target inherits the row's identity field automatically.
- (b) **Explicit binding** — operator declares which field provides the action target.
- (c) **Both** — implicit for common cases; explicit override for advanced cases.

**LOCKED: (c).** Default implicit (uses iteration scope's primary identity field, e.g., `delivery.id`). Operator can override via explicit `target_field` in action config.

#### Q-19: Hover affordances

**At stake:** Do widgets support hover state? Tooltips? Hover-reveal action buttons?

**Options:**
- (a) **No hover state** — render-only.
- (b) **Optional hover tooltip** — atom carries `hover_tooltip` prop.
- (c) **Above + hover-reveal action buttons** — buttons declared on atoms surface on hover.

**Canon cross-check:**
- DECISIONS.md 2026-05-21 entry 30 — All pointer-event surfaces require Playwright coverage. Hover affordances in WB-emitted widgets MUST have Playwright coverage.

**LOCKED: (b) Phase 1 + (c) deferred to WB-7.** Phase 1 atoms carry optional `hover_tooltip` (literal or bound). Hover-reveal action buttons deferred until the static-action path proves out and operator demand surfaces.

#### Q-20: Internal filter/sort/search within widget

**At stake:** Can a widget have internal interactivity (operator types a search box that filters the widget's data)?

**LOCKED: deferred to WB-6 or post-September.** Phase 1 widgets are render-only over their bound data. Internal filter/sort/search would couple widget runtime to interactivity state machines that don't yet have a canonical pattern. Operators wanting filterable lists today author saved views with the filter baked in.

#### Q-21: Pagination

**At stake:** Lists with > N rows — what happens?

**Options:**
- (a) **No pagination — render all rows** — fine for small saved views; breaks for large ones.
- (b) **Cap at row limit + "View more" link** — widget caps at N (operator-configurable; default 10) + offers a "View all in {SavedView}" link.
- (c) **Inline pagination** — widget has its own page-next/page-prev controls.

**LOCKED: (b).** Widget caps at `max_rows` (default 10, range 1-50). "View more" link routes to saved-view detail page. Inline pagination (c) deferred.

#### Q-22: Operator-authored Glance variant compactness rules

**At stake:** Glance must fit in a sidebar pin (typically 200-300px wide). What enforces compactness?

**Options:**
- (a) **No enforcement** — operator authors Glance variant atoms; rendering breaks if oversized.
- (b) **Soft warning at authoring** — variant authoring inspector warns when Glance's atom count > 3.
- (c) **Hard cap** — Glance variant cannot have > 3 atoms.

**LOCKED: (b) — soft warning + best-effort layout.** Glance variant inspector warns when atom count > 3 OR when atom-tree depth > 1. Operator can override; runtime CSS bounds the Glance render box at max-width per surface (sidebar = 280px). Hard caps (c) feel disrespectful per "opinionated but configurable" canon.

---

### Area 4 — Rendering targets (Q-23 through Q-25)

#### Q-23: Surface availability declaration

**At stake:** Where can a widget render? Pulse? Focus canvas? Sidebar pin? Peek? Document inline?

**Options:**
- (a) **Operator declares per widget** — `supported_surfaces` per widget (already exists on `WidgetDefinition` per `widget_definition.py:113-118`).
- (b) **Inferred from variant set** — widget's available variants determine surfaces (Glance → spaces_pin; Brief → dashboard_grid + focus_canvas; etc.).
- (c) **Both** — operator declares supported surfaces; surfaces require canonical variants per §12 compatibility matrix; mismatches caught at validation.

**LOCKED: (c).** Existing `supported_surfaces` field on `WidgetDefinition` (`["pulse_grid", "focus_canvas", "focus_stack", "spaces_pin", "floating_tablet", "dashboard_grid", "peek_inline"]`) honored. Validation rule: a widget surfacing on `spaces_pin` MUST have a Glance variant authored; a widget surfacing on `focus_canvas` MUST have a Brief variant (Detail recommended); etc. WB-2 implements the validation.

#### Q-24: Once-everywhere vs surface-specific composition

**At stake:** Does a single widget definition render the same composition on every surface, or can compositions vary per surface?

**Options:**
- (a) **Variant-driven** — one composition per widget; surfaces pick variants. Per the BRIDGEABLE_MASTER §9.2 canon ("same library, different surfaces").
- (b) **Per-surface composition** — operator authors different compositions per surface.

**LOCKED: (a) — variant-driven.** Surface chooses variant; variant determines visible atoms (per Q-10). One composition, four-five variant shapes. Per-surface composition (b) would explode the authoring effort and contradict the canon.

#### Q-25: Operator/customer/shared widget categories

**At stake:** Are there widgets only customers see (in portals) vs only operators see vs shared?

**Options:**
- (a) **Single widget catalog** — every widget renders in any surface that supports it; 5-axis filter handles visibility.
- (b) **Operator vs customer categories** — explicit category on widget definition. Customer-facing portals filter to customer widgets.
- (c) **Per-surface category tagging** — widget declares which surface categories (operator/customer/admin) it serves.

**Canon cross-check:**
- BRIDGEABLE_MASTER §10 Phase 8e.2 portal-as-space-with-modifiers canon — portal widgets are NOT a separate catalog; they are canonical widgets surfacing on portal spaces filtered by portal-Space access modes.

**LOCKED: (a) — single catalog.** Customer / partner / operator distinctions ride the existing 5-axis filter (`required_permission`, `required_module`, etc.) + Space access modes (`portal_partner`, `portal_external`). No category proliferation; canonical widget catalog serves all paradigms.

---

### Area 6 — registerComponent HOC reconciliation (Q-26 through Q-28) — LOAD-BEARING

Per DECISIONS.md 2026-05-21 entry 28, `registerComponent` HOC at `register.ts:215` wraps every registered component in `display: contents` for runtime-editor click-to-edit. The widget builder substrate inherits this constraint.

#### Q-26: Composed widget HOC wrapping

**At stake:** When the runtime `ComposedWidget` renderer renders a composed widget definition, is the OUTPUT wrapped by registerComponent's display:contents wrapper?

**Options:**
- (a) **`ComposedWidget` itself is registerComponent-wrapped** — single widget registration under name `composed_widget`; wrapper applied at the runtime renderer level. Click-to-edit selects the entire composed widget, not individual atoms.
- (b) **Per-atom registerComponent wrapping** — each atom inside `ComposedWidget` is itself a registered component (per Q-6's lock on (b)). Atoms inherit the wrapper. Click-to-edit can drill from widget → atom.
- (c) **Both** — `ComposedWidget` wrapped + atoms within wrapped. SelectionOverlay walks the deepest match.

**Canon cross-check:**
- DECISIONS.md 2026-05-21 entry 28 — "investigations of behavioral symptoms on a substrate that consumes registered components MUST audit the cross-substrate HOC chain." Cross-substrate audit explicit: every component the operator can select must be registerComponent-wrapped.

**LOCKED: (c) — both.** `ComposedWidget` registers under widget slug `composed_widget` (or one slug per composed widget id, depending on Q-2's resolution; the Q-2 lock at (c) means atoms render within `ComposedWidget`'s dispatch — so single `composed_widget` registration carrying composition_blob via prop_overrides is the shape). Atoms (per Q-6) register as `"widget-atom"` ComponentKind via registerComponent. SelectionOverlay walks deepest match; click on an atom selects the atom; click on widget chrome selects the widget root.

#### Q-27: display:contents cascade behavior

**At stake:** Layout container atoms (per Q-5 — group containers with flex direction) need to BE the flex container. display:contents removes the wrapper from layout flow. How do containers + display:contents coexist?

**Options:**
- (a) **Container atom's wrapper IS the flex container** — registerComponent's display:contents is overridden by the container atom's own style.
- (b) **Container atom's CHILDREN form the flex layout** — the registered atom wraps an inner `<div>` with flex styles; display:contents wrapper passes through.
- (c) **Bypass registerComponent for container atoms** — container atoms don't go through registerComponent; they're plain React components.

**LOCKED: (b).** Container atoms render an inner `<div>` with the flex/grid styles. The registerComponent wrapper's display:contents passes through transparently. This matches the precedent FF-3 / FF-4 / placeholder widgets follow: a "widget" registered via registerComponent renders an inner `<div>` carrying the actual layout/chrome; the wrapper is invisible to layout. The flex/grid styles live on the inner div, not the wrapper.

**Risk:** if a future atom needs to BE the flex container (e.g., a Grid atom using CSS subgrid where the registered component must be the grid item), the display:contents wrapper interrupts subgrid participation. Mitigation: filed as KNOWN GAP per entry-24 precedent; CSS subgrid use cases are not Phase 1.

#### Q-28: Atom-level non-bubbling pointer event semantics

**At stake:** DECISIONS.md 2026-05-21 entry 27 surfaced that `onPointerEnter` / `onPointerLeave` are non-bubbling. Atoms inside a composed widget need hover state for the operator-observable hover-state-mid-edit case (e.g., atom hover during widget builder authoring).

**LOCKED: bubbling events as canonical pattern + Playwright coverage gate.** Per entry 27's canon, atom-level pointer event semantics use `onPointerOver` / `onPointerOut` (bubbling) inside the display:contents wrapper. Source-shape regression gates (per entry 31) enforce bubbling-event names at the source level for any new atom carrying pointer-event interactivity. Playwright coverage (per entry 30) ships in WB-7 for atom hover semantics + widget builder authoring canvas pointer surfaces.

---

### Area 7 — Persistence + schema (Q-29 through Q-32)

#### Q-29: Backend table for composed widget definitions

**At stake:** Where does the composition blob live?

**Options:**
- (a) **Extend `widget_definitions` with `composition_blob` JSONB column** — single table; legacy hand-coded widgets carry `composition_blob = null`; composed widgets carry the blob.
- (b) **New `composed_widget_definitions` table** — separate concern; cleaner discrimination.
- (c) **Reuse `focus_templates`-style three-table inheritance** — `widget_cores` (tier 1) + `widget_templates` (tier 2) + `widget_compositions` (tier 3).

**Canon cross-check:**
- Q-3 lock (per-instance override at placement level for Tier 3) means tier-3 doesn't need a separate table — placement `prop_overrides` already carries tenant-level overrides. So Tier 1 + Tier 2 + placement overrides covers the inheritance.

**LOCKED: (a) — extend `widget_definitions` with `composition_blob` JSONB + `composition_version` integer + `tier_scope` enum (`platform_default | vertical_default`).** Existing 5-axis filter columns honored. Tier-3 lives at placement level via existing `prop_overrides`. Migration WB-1 ships the column extension + tier_scope enum. NO new table.

**Why not (c) — focus-templates-style 3-table?** Widgets don't have a "core that's separate from the template" semantic. The atom catalog is platform-canonical (registered components, not DB rows); the composition itself is what the widget IS. A widget-cores table would mean "core composition that templates extend" — but composed widgets ARE the unit; there's no sub-extension model that makes sense at widget level. Three-table inheritance would over-engineer.

#### Q-30: Composition blob shape

**At stake:** What's the JSONB shape for a composed widget?

**LOCKED:** schema below. Backend validator (in WB-1) enforces.

```jsonc
{
  "schema_version": 1,
  "root": {
    "kind": "container",
    "container_id": "root",
    "direction": "row" | "column",
    "atoms": [
      {
        "atom_id": "uuid-str",
        "atom_kind": "text_label" | "value_display" | "icon" | "status_badge" | "divider" | "button" | "image" | "conditional_container",
        "visible_in_variants": ["glance" | "brief" | "detail" | "deep"],
        "props": {
          "text": { "kind": "literal" | "field_path", "value"|"path": "..." },
          // atom-kind-specific props per Q-7/Q-8
        },
        "behavior": { "click": {...}, "hover_tooltip": {...} } | null,
        "required_permission": "string?" | null
      },
      // OR nested group:
      {
        "kind": "container",
        "container_id": "group-1",
        "direction": "row" | "column",
        "chrome": { ...per-group chrome overrides },
        "atoms": [ ...atoms; one level deep only per Q-5 ]
      }
    ]
  },
  "chrome": { ...widget-root chrome },
  "chrome_per_variant": { "glance": {...}, "brief": {...}, ... } | null,
  "data_source": {
    "kind": "saved_view",
    "saved_view_id": "uuid-str",
    "iteration_mode": "per_row" | "single_summary" | "single_record",
    "max_rows": 10,
    "refresh_interval_seconds": 300
  }
}
```

Backend validator ships in WB-1. Frontend mirror at `frontend/src/lib/widget-builder/composition-validator.ts`. Cross-side parity test per F-3.1a precedent (real backend validator import + real frontend emit through real adapter).

#### Q-31: Versioning model

**At stake:** Composed widget edits — version-bump like focus_templates or mutate in place?

**Options:**
- (a) **Version-bump on every save** — mirror focus_templates default path.
- (b) **Session-aware mutate-in-place + version-bump fallback** — mirror focus_templates session-aware exception path.
- (c) **Always mutate in place** — single version; no audit trail.

**Canon cross-check:**
- DECISIONS.md 2026-05-19 (PM) — "Ordinary template updates version-bump by default; session-aware mutate-in-place is the exception." Canonical for focus_templates; applies to widget definitions analogously.

**LOCKED: (b) — mirror focus_templates session-aware versioning.** Same `edit_session_id` + `EDIT_SESSION_WINDOW_SECONDS` mechanism. WB-1 migration adds session columns to `widget_definitions`. URL recovery (per 2026-05-19 PM canon) ships in WB-3 (the authoring hook).

#### Q-32: URL stability

**At stake:** Operator's widget builder URL — `?widget=<id>` — versioning bumps the id.

**Options:**
- (a) **id-based URL + 410-retry recovery** — F-3.1a.2 pattern.
- (b) **slug-based URL** — `?widget=widget-slug:funeral-schedule-card` — addresses the active version.

**Canon cross-check:**
- DECISIONS.md 2026-05-19 (PM) — "URL stability for versioned entities requires slug-based addressing as long-term canonical pattern." Future builders SHOULD adopt slug-based from the start.

**LOCKED: (b) — slug-based addressing from inception.** `?widget=widget-slug:<slug>` resolves to active widget at READ time. URL stable across version bumps forever. Avoids the F-3.1a.2 retrofit pattern.

---

### Area 8 — Test substrate (Q-33 through Q-35)

#### Q-33: Composition canvas pointer surfaces

**At stake:** Widget builder's center canvas has drag-from-palette + drag-to-arrange + atom hover affordances. All are pointer surfaces.

**Canon cross-check:**
- DECISIONS.md 2026-05-21 entry 30 — All pointer-event surfaces require Playwright coverage.

**LOCKED:** Every pointer-event surface in WB-series ships with Playwright + JSDOM behavioral + source-shape regression gate per entry 31 + entry 30. Specifically:
- Drag atom from palette to canvas (Playwright)
- Drag atom to reposition within canvas (Playwright + JSDOM via KeyboardSensor pattern per FF-3)
- Atom hover for selection chrome (Playwright + source-shape gate enforcing bubbling event names)
- Atom click for selection (JSDOM + Playwright)
- Drag binding from left-rail data picker onto atom (Playwright)

#### Q-34: Cross-side render+save integration tests

**Canon cross-check:**
- DECISIONS.md 2026-05-19 (late PM) through 2026-05-19 (late evening) — cross-side contract framing; render-side assertions at operator-observable element.

**LOCKED:** Every WB sub-arc shipping operator-flow produces cross-side integration tests at `frontend/src/bridgeable-admin/components/widget-builder/WidgetBuilderPage.test.tsx`. Save-side mock service expectations on PUT body shape; render-side assertions at operator-observable rendered element (per 2026-05-19 late evening canon). Verify-against-pre-fix discipline applied to both assertion sides independently.

#### Q-35: Stateful drag modeling

**At stake:** Widget builder's drag-atom-from-palette involves @dnd-kit cumulative-delta semantics (per entry 29).

**LOCKED:** Per DECISIONS.md 2026-05-21 entry 29, snapshot-at-drag-start ref pattern (`paletteDragInitialPositionRef`, `atomDragInitialPositionRef`) for atom moves on canvas. Cumulative-delta-vs-per-tick-state explicitly modeled per the canon. Three-handler enumeration (dragStart / dragMove / dragEnd) for each gesture documented in WB-3 build report.

---

### Area 9 — Coexistence with Page Builder + Document Builder + Workflow Builder (Q-36 through Q-37)

#### Q-36: Widget primitive sharing across downstream builders

**At stake:** Are widgets the same primitive on Page Builder (Monitor canvas) as on Focus Builder (Decide canvas)?

**Canon cross-check:**
- DECISIONS.md 2026-05-20 — Monitor canvas (grid) vs Decide canvas (free-form) are architecturally distinct.
- BRIDGEABLE_MASTER §9.2 — widgets render on BOTH Pulse (Monitor) and Focus (Decide); same library, different surfaces.

**LOCKED:** Widget definitions ARE the same primitive across all downstream builders. The widget's CANVAS placement shape differs per downstream builder (grid placement coords for Page Builder per Monitor canon; free-form x/y/w/h per Decide canon). Widget builder produces widget DEFINITIONS that any downstream builder consumes by placing them on the appropriate canvas shape. Widget builder is the substrate; downstream builders are the placement surfaces.

#### Q-37: Document Builder block coexistence

**At stake:** Document Builder produces document blocks (per Documents arc D-10/D-11). Are document blocks the same as widget atoms?

**LOCKED:** Document blocks and widget atoms are DISTINCT primitives. Document blocks render in document templates (HTML emission for PDF + email); they have a different runtime (Jinja-rendered server-side). Widget atoms render in React on canvas. The two substrates inform each other (status badge as atom + status badge as document block share visual treatment from DESIGN_LANGUAGE) but are independent. Widget builder does NOT subsume Document Builder. Workflow Builder's nodes are also a separate primitive (workflow canvas graph nodes; not widgets).

**Cross-builder shared vocabulary:** Status families, color tokens, type tokens, surface tokens are platform-canonical (DESIGN_LANGUAGE). All three downstream builders consume them. The shared substrate is design tokens, not primitive shapes.

---

### Area 10 — Tier inheritance (Q-38 through Q-40)

#### Q-38: Tier-1 / Tier-2 / Tier-3 model

**At stake:** How does the platform → vertical → tenant inheritance work for composed widgets?

**Canon cross-check:**
- Q-3 lock: Tier 1 + Tier 2 widget definitions in `widget_definitions`; Tier 3 at placement level via `prop_overrides`.
- DECISIONS.md 2026-05-18 — "Template vertical is design-time-permanent." Tier-2 vertical_default widget definitions cannot migrate verticals via update.

**LOCKED:** Tier-1 (`platform_default`) widget definitions in `widget_definitions` with `tier_scope='platform_default'` + `vertical=NULL`. Tier-2 (`vertical_default`) with `tier_scope='vertical_default'` + `vertical=<slug>`. Tier-3 widget INSTANCES live at placement level via existing `focus_compositions.deltas` (Decide canvas) or future Pulse placement override (Monitor canvas, per Page Builder arc). NO Tier-3 widget definitions table.

#### Q-39: Tier-2 widget definition fork mechanism

**At stake:** Tenant wants a Tier-2 widget shape modified for their use case.

**LOCKED: NOT in WB scope.** Tenants requesting widget-shape modifications work with platform admins; the platform admin authors a new vertical_default Tier-2 widget definition (or revises an existing one with operator coordination). The fork mechanism modeled on workflow_templates / focus_templates is deferred to post-September; concrete tenant demand surfaces shape decisions there.

#### Q-40: Tier-1 update propagation to Tier-2

**At stake:** Platform admin updates a Tier-1 widget. Tier-2 widgets that inherited from it — do they pick up the update?

**LOCKED:** Tier-1 widget definitions and Tier-2 widget definitions are INDEPENDENT rows. There is no Tier-1 ↔ Tier-2 inheritance for widget DEFINITIONS (analogous to workflow_templates lock-to-fork semantics per Phase 8a). Tier-2 widget definitions are AUTHORED FROM SCRATCH at vertical scope; they don't inherit from a Tier-1 base. If platform admins want a Tier-2 widget to track a Tier-1 update, they re-author. Three-tier inheritance for widget definitions is LIGHTER than for themes / focus_compositions; reason: widget definitions are themselves bounded composition documents (~10s of atoms), not unbounded delta accretion. Re-authoring is cheap.

---

## Architectural risks

### Q-RISK-1: Runtime interpretation performance ceiling

**At stake:** `ComposedWidget` runtime renderer walks the JSONB composition blob on every render. For widgets with O(100) atoms, this is non-trivial.

**Mitigation:**
1. Cap composition blob complexity at validation time (max 30 atoms per widget; max nesting 2 levels per Q-5).
2. React.memo on per-atom renders; memoize the binding resolution.
3. Profile in WB-4 (first render-target hookup); if budget exceeded, ship per-atom React.memo + binding cache.
4. Long-term: build-time codegen path per Q-2 (a) as fallback if perf becomes load-bearing. Build pipeline cost is justified IF widget runtime is hot.

### Q-RISK-2: Binding shape changes when saved view shape changes

**At stake:** Operator authors widget bound to saved view with field `delivery.driver_name`. Later, the saved view's underlying VaultItem type drops the `driver_name` field. Widget breaks.

**Mitigation:**
1. Backend validator at widget save time checks every `field_path` BindingRef against the saved view's known shape. Validation fails with operator-visible error listing broken bindings.
2. Per-binding fallback per Q-13 (c) — operator declares fallback at binding time; broken binding renders fallback instead of crashing.
3. Saved-view shape change surfaces as a "this view is referenced by 3 widgets" warning in saved-view editor.
4. Filed as KNOWN GAP for WB-2; production-grade widget-saved-view-coupling-validation is a WB-7 polish concern.

### Q-RISK-3: Atom catalog over-narrow forces operator workarounds

**At stake:** 8 atoms Phase 1 (per Q-4) means some widgets cannot be authored cleanly. Operators reach for workarounds (compose `status_badge` from `text + icon` because the canonical status_badge doesn't support their custom variant).

**Mitigation:**
1. Atom catalog is extensible. Each atom is a normal registerComponent registration; new atoms add via PR + WB-7 cycle.
2. Composite atoms (status_badge) carry escape hatches: per-atom chrome override for one-off cases.
3. Observable signal: count of widgets using "compose around the catalog" patterns. If signal grows, expand catalog.
4. Document the catalog-growth-mechanism in WB-2 build report so operators know how to request new atoms.

### Q-RISK-4: Widget runtime + builder authoring share atom code paths (test surface bleed)

**At stake:** Atoms run in two contexts: live render via `ComposedWidget` runtime renderer AND authoring preview via the widget builder canvas. Bugs in atom render shape may surface in only one context, evading the other's tests.

**Mitigation:**
1. Cross-side integration tests per Q-34 cover both contexts at the WidgetBuilderPage test surface.
2. Source-shape regression gates per entry 31 protect atom render contracts.
3. Atom unit tests render atoms in isolation; widget builder canvas tests render atoms in authoring context; runtime composed widget tests render atoms in render context. Three test layers per atom.
4. WB-1 build report enumerates the three contexts atoms render in (atom isolated; widget builder canvas; runtime ComposedWidget) and confirms each atom carries coverage across all three.

---

## Sub-arc decomposition

WB-series decomposes into 8 sub-arcs. Each sub-arc falls under ~2,500 production LOC (consistent with F/FF series decomposition ceilings per DECISIONS.md 2026-05-13 PM canon), ships visibly, and has no interleaving dependencies beyond sequential ordering.

### WB-1 — Composition validator + schema + adapter

**Scope.** Migration extending `widget_definitions` with `composition_blob` JSONB + `composition_version` int + `tier_scope` enum + session-aware columns (per Q-31 lock mirroring r103 focus_templates_edit_session). New `composed_widget_validation.py` service-layer module + frontend mirror at `lib/widget-builder/composition-validator.ts`. New `ComposedWidget` runtime renderer at `frontend/src/components/widgets/composed/ComposedWidget.tsx` registered as widget slug `composed_widget`. New `useComposedWidgetDraft` hook at `bridgeable-admin/hooks/useComposedWidgetDraft.ts` (multi-hook-mount canon per 2026-05-19 + draft-ref pattern per C-2.1.4 + 410-retry + slug-based URL recovery). Validator enforces: schema_version match; max 30 atoms; max 2 nesting levels; data_source.saved_view_id resolvable; per-atom required_permission valid; visible_in_variants subset of canonical 4. NO frontend authoring UI yet — operators see no visible change. Backend tests verify shape acceptance + rejection cases; frontend tests verify adapter round-trip + hook null-safe handling.

**Estimated LOC.** ~1,400–2,000.

**Ships visibly.** Composed widget runtime renderer exists; can render seed composed widget definitions (one seeded for the demo). Builder UI ships in WB-2.

**Dependencies.** Q-1 through Q-3 (Area 5 locks), Q-29 through Q-32 (persistence locks), Q-38 (tier 1+2 schema lock).

### WB-2 — Atom catalog + atom registry + atom inspectors

**Scope.** 8 atoms registered under new `"widget-atom"` ComponentKind: `text_label`, `value_display`, `icon`, `status_badge`, `divider`, `button`, `image`, `conditional_container`. Each carries ≥3 configurableProps per registry contract. Each atom has a corresponding inspector control component for the widget builder right rail. Atom inspectors share C-1's PropertyPanel + PropertySection + PropertyRow primitives. `canvasPlaceable: false` on all atoms so they don't pollute Focus Builder palette. Atom catalog file at `lib/visual-editor/registry/registrations/widget-atoms.ts`. Inspector controls at `bridgeable-admin/components/widget-builder/inspector-controls/<atom_kind>InspectorControl.tsx`. Storybook-style demo route at `/bridgeable-admin/visual-editor/_atom-catalog-demo` for QA. Cross-side validation: composed widget composition blob referencing each atom_kind renders correctly through ComposedWidget runtime.

**Estimated LOC.** ~2,000–2,800.

**Ships visibly.** Atoms render via runtime; demo route exhibits each atom at brief variant.

**Dependencies.** WB-1 ships first. Q-4 through Q-10 (Area 1 locks), Q-26 through Q-28 (HOC reconciliation locks).

### WB-3 — Widget Builder shell + data source picker + composition canvas (drop only)

**Scope.** New page at `/studio/widgets/<slug-based-url>` per Q-32. Three-pane layout (left: data source + iteration scope; center: composition canvas; right: inspector). Hook `useComposedWidgetDraft` consumed for save/load. Data source picker reads existing saved-views catalog via `savedViewsService.list()`. Iteration scope picker per Q-12. Composition canvas: empty-state CTA → "Pick a starting template (hybrid (c) lock per Q-1) OR start blank". Template seed selection ships 3 seeded templates (Status Card / Stat Tile / Card with Header). Drop-only: drag atom from atom palette onto canvas → atom added to composition blob with default chrome+empty binding. NO drag-to-reorder yet (WB-4). NO atom binding to fields yet (WB-5). NO variant authoring yet (WB-6). Save indicator + breadcrumb + tier indicator pill matching FocusBuilderPage canon. Cross-side integration test at `WidgetBuilderPage.test.tsx` per Q-34: drop atom → assert PUT body shape + assert rendered atom on canvas + render side at operator-observable rendered element.

**Estimated LOC.** ~2,000–2,800.

**Ships visibly.** Operators can open WB, pick a data source, start a composed widget, drop atoms. Authoring is incomplete (binding + variants come next) but the shell exists.

**Dependencies.** WB-2 ships first. Q-11 / Q-12 / Q-16 (data source + iteration + preview locks).

### WB-4 — Drag-to-reorder + per-atom selection + chrome inspector

**Scope.** Atoms draggable within composition canvas via @dnd-kit (per FF-3 / FF-4 canon — snapshot-at-drag-start ref per entry 29, bubbling pointer events per entry 27, KeyboardSensor for JSDOM coverage per Q-40). Pointer-event surfaces follow source-shape regression gates per entry 31. Per-atom selection via FocusBuilderSelectionContext-shaped selection context (`WidgetBuilderSelectionContext`). Selected atom shows in right rail inspector with atom-kind-specific control composition. Widget root chrome inspector (PropertyPanel composing surface_token + border_token + radius_token + padding_token + shadow_token controls; reuses C-1 ScrubbableButton + TokenSwatchPicker). Per-atom chrome NOT exposed (per Q-9 lock at (b) — container chrome only). NO bindings yet (WB-5). Playwright spec for drag-to-reorder + JSDOM behavioral test for keyboard-driven move. Cross-side render+save integration test for chrome scrubs at the widget-root element.

**Estimated LOC.** ~1,500–2,200.

**Ships visibly.** Operator can reorder atoms, edit widget chrome, select atoms.

**Dependencies.** WB-3 ships first. Q-9 / Q-26-28 / Q-33-35 / entry 27 / entry 29 / entry 30 / entry 31.

### WB-5 — Atom binding + behavior + permissions

**Scope.** Atom inspector gains "Binding" section per Q-7 + Q-8: operator picks `literal` or `field_path` for each atom prop; format spec for `value_display`; status_map for `status_badge`. Data source's bound fields enumerated in inspector dropdown via existing saved-view schema introspection. Per-atom `behavior` section per Q-17 / Q-18: `click` action picker with action-kind dropdown (navigate / open_focus / open_peek / mutate / trigger_workflow). Per-atom optional `required_permission`. Per-atom `hover_tooltip` per Q-19. Backend binding validator at widget save time checks `field_path` against saved view's schema (per Q-RISK-2 mitigation). Cross-side integration tests: bind atom to field → assert PUT body shape + assert rendered atom shows bound value in live preview (per Q-16 (c) lock, operator-selected sample record powers preview).

**Estimated LOC.** ~1,800–2,500.

**Ships visibly.** Composed widgets render real data in live preview AND in deployed render path.

**Dependencies.** WB-4 ships first. Q-7 / Q-8 / Q-13 / Q-14 / Q-17 / Q-18 / Q-19.

### WB-6 — Variant authoring + variant-driven atom visibility + surface availability

**Scope.** Inspector gains "Variants" tab at widget root: operator declares which variants the widget supports (Glance / Brief / Detail / Deep) per Q-10. Each atom's inspector gains `visible_in_variants` multi-select. Composition canvas gains variant-switcher chrome at top (preview which variant shape renders). Surface availability declaration per Q-23: operator picks `supported_surfaces` from canonical list; validation enforces canonical variant-per-surface compatibility (`spaces_pin` requires Glance; `focus_canvas` requires Brief; etc.). Per-variant chrome overrides at widget root per Q-10 secondary lock. Glance variant compactness soft-warning per Q-22. Cross-side test: author variant set → switch preview variant → assert visible atom set + assert PUT body shape carries the variant subset.

**Estimated LOC.** ~1,500–2,200.

**Ships visibly.** Composed widgets carry the full four-variant taxonomy. Demo flow showing same widget rendering Glance on spaces_pin + Brief on dashboard works end-to-end.

**Dependencies.** WB-5 ships first. Q-10 / Q-22 / Q-23 / Q-24 / Q-25.

### WB-7 — Polish + Playwright + atom-catalog-expansion-readiness + KNOWN GAPs from Q-RISKs

**Scope.** Playwright spec gates for all WB pointer surfaces per Q-33 (drag-from-palette / drag-to-reorder / atom-hover / atom-click-select / drag-binding-onto-atom). Source-shape regression gates for bubbling event names. Atom-catalog-expansion documentation (how to add a new atom kind; PR template; coverage requirements). Per-atom chrome escape hatch per Q-9 + Q-RISK-3 (operator can override atom-level chrome on a per-atom basis when composite atoms don't fit). Hover-reveal action buttons per Q-19 (c) — deferred sub-feature lifted from KNOWN GAP. Saved-view-shape-change widget-coupling warning UI per Q-RISK-2 mitigation step 3. KNOWN GAPs filed for Q-20 (internal filter/sort/search) + Q-39 (Tier-2 fork) + arbitrary nesting (Q-5 deferral).

**Estimated LOC.** ~1,500–2,200.

**Ships visibly.** WB-series is feature-complete for the September demo. Operator can build composed widgets matching the four-variant taxonomy from start to finish without writing code.

**Dependencies.** WB-6 ships first. Q-19 / Q-20 / Q-33 / Q-RISK-2 / Q-RISK-3.

### WB-8 — Demo seed + Wilbert narrative integration + staging verification

**Scope.** Three seeded composed widgets shipped via `seed_composed_widgets.py`: one funeral-home-vertical (Funeral Schedule Card), one manufacturing-vertical (Vault Pour Status Card), one cross-vertical (Recent Activity Card). Each seeded as Tier-2 `vertical_default` (or `platform_default` for cross-vertical). Each demonstrates: a) data binding to a saved view; b) the four-variant taxonomy; c) per-atom behavior (click → navigate to entity); d) chrome composition; e) cross-surface rendering (placed on a Focus + Pulse). Staging verification: deploy → seed runs → composed widgets appear on Hopkins FH's Pulse + testco's Manufacturing Pulse. Demo flow walked end-to-end. README update at `frontend/src/bridgeable-admin/components/widget-builder/README.md` describing the substrate, the authoring flow, the atom catalog, the test discipline.

**Estimated LOC.** ~600–1,000.

**Ships visibly.** Demo-ready. Sunnycrest can show "we built this widget in 5 minutes" at Wilbert.

**Dependencies.** WB-7 ships first.

### Total

**WB-series midpoint LOC: ~11,000.** Worst-case ~14,000. Decomposition is natural at every seam; no sub-arc bundles concerns from another. Each ships visibly.

---

## Deferred for later substrate work

Explicit deferrals NOT in WB-series scope:

- **Arbitrary nesting** (Q-5 deferral). 3+ levels of group nesting deferred until concrete operator demand.
- **Expression bindings** (Q-7 deferral). Sandboxed expression subset (filter / transform / derive) deferred to a future arc when concrete shape requirements surface.
- **Direct VaultItem-type filters** (Q-11 deferral). Operators who need this today create a saved view first; UX-cost-of-the-detour is acceptable in WB scope.
- **WebSocket-driven reactive rendering** (Q-15 deferral). Deferred until platform has canonical real-time substrate.
- **Internal filter/sort/search within widget** (Q-20 deferral). Internal interactivity state machines deferred to a coupling arc.
- **Hover-reveal action buttons** (Q-19 deferral). Lifted into WB-7 polish; if WB-7's budget is tight, slips to post-September.
- **Per-atom chrome override** (Q-9 deferral). Lifted into WB-7 escape hatch; if WB-7's budget is tight, slips to post-September.
- **Tenant-tier (Tier 3) widget DEFINITIONS** (Q-39 deferral). Tier-3 instances via placement-level prop_overrides; tenant-authored widget DEFINITIONS deferred indefinitely.
- **Tier-1 → Tier-2 fork mechanism for widgets** (Q-40 deferral). Vertical_default widgets are re-authored from scratch; explicit fork mechanism modeled on workflow_templates / focus_templates deferred until concrete tenant demand surfaces.
- **Build-time codegen** (Q-2 (a) deferral). Runtime interpretation suffices for September demo; codegen path remains the long-horizon fallback if runtime performance hits a ceiling.
- **CSS subgrid atom layouts** (Q-27 KNOWN GAP). display:contents wrapper interrupts subgrid; deferred until concrete subgrid need surfaces.
- **Sparkline / progress bar / avatar / chart atoms** (Q-4 (c) deferral). Visualization-specific atoms deferred to a dedicated visualization-atom arc post-WB.

---

## References

### Canon entries (DECISIONS.md)
- 2026-05-13 — Studio as consolidated visual authoring environment
- 2026-05-13 — Widget authoring is data-source-first
- 2026-05-18 — Cores are canonical-shared-across-verticals (analog for atoms)
- 2026-05-18 — Template vertical is design-time-permanent (analog for widget vertical)
- 2026-05-19 — Multi-hook-mount pattern for builder UIs surfacing heterogeneous subjects
- 2026-05-19 — Component registry requires ≥3 configurableProps per registration
- 2026-05-19 (PM) — Ordinary template updates version-bump by default
- 2026-05-19 (PM) — URL stability for versioned entities requires slug-based addressing
- 2026-05-19 (late PM) — Mock-only tests verify one side of cross-side contracts
- 2026-05-19 (evening) — Cross-side contract framing extends to data↔render boundaries
- 2026-05-19 (late evening) — Render-side assertions must target operator-observable CSS at specific rendered element
- 2026-05-20 — Monitor canvas (grid) and Decide canvas (free-form) are architecturally distinct
- 2026-05-21 entry 25 — Investigation source-candidate audit must cover all consumers of affected state
- 2026-05-21 entry 26 — Investigation-time UX locks can be refined by operator experience
- 2026-05-21 entry 27 — Investigation event-type semantic enumeration is a discriminator axis (bubbling vs non-bubbling)
- 2026-05-21 entry 28 — Investigation cross-substrate HOC audit (registerComponent display:contents wrapper)
- 2026-05-21 entry 29 — Investigations of stateful drag must model cumulative-delta-vs-per-tick-state
- 2026-05-21 entry 30 — All pointer-event surfaces require Playwright coverage
- 2026-05-21 entry 31 — Source-shape regression gate as test-substrate pattern
- 2026-05-21 entry 32 — @dnd-kit transform model is position-only
- 2026-05-21 entry 33 — Gesture-vs-input symmetry as design heuristic

### Canon docs
- `BRIDGEABLE_MASTER.md` §9 Widget Library Architecture
- `PLATFORM_ARCHITECTURE.md` §9 Widget Library Architecture (5-axis filter)
- `DESIGN_LANGUAGE.md` §12 Widget Library — variant taxonomy + interactivity discipline + §12.6a state-changes-are-widget-appropriate
- `PLATFORM_INTERACTION_MODEL.md` — chip pattern + peek panels + pause sensor + observe-and-offer
- `CLAUDE.md` §3 (Hub-Based Organization + Widget-Based Dashboards)

### Substrate file references
- `frontend/src/lib/visual-editor/registry/register.ts:174-238` — registerComponent HOC
- `frontend/src/lib/visual-editor/registry/register.ts:215` — display:contents wrapper (entry 28 source)
- `frontend/src/lib/visual-editor/registry/types.ts:38-73` — ComponentKind discriminator (Q-6 extension target)
- `frontend/src/lib/visual-editor/registry/types.ts:249-362` — RegistrationMetadata shape
- `frontend/src/lib/visual-editor/registry/registrations/widget-atoms.ts` — WB-2 deliverable
- `frontend/src/lib/visual-editor/registry/registrations/focus-builder-widgets.ts` — F-3 placeholder widgets (precedent shape)
- `frontend/src/lib/visual-editor/registry/registrations/widgets.ts:1-200` — production widget registrations (R-1.6.12 wrapped versions)
- `frontend/src/components/widgets/foundation/register.ts` — canvas runtime dispatch registration (two-layer registration system documented)
- `frontend/src/components/widgets/focus-builder/PlaceholderWidgets.tsx` — F-3 placeholder widget components
- `frontend/src/components/widgets/foundation/SavedViewWidget.tsx` — config-driven container widget precedent ("user-authored widget catalog without widget code")
- `frontend/src/bridgeable-admin/components/focus-builder/FocusBuilderPalette.tsx` — F-3 palette precedent for widget palette substrate
- `frontend/src/bridgeable-admin/components/focus-builder/FocusBuilderCanvas.tsx` — FF-2 canvas substrate (mode detection per shape)
- `frontend/src/bridgeable-admin/components/focus-builder/FocusBuilderInspector.tsx` — F-3.1b inspector composition precedent
- `frontend/src/bridgeable-admin/components/focus-builder/WidgetInspectorSection.tsx` — F-3 widget inspector pattern
- `frontend/src/bridgeable-admin/hooks/useFocusTemplateDraft.ts` — draft hook canon (consumed unchanged by WB-3 hook shape)
- `frontend/src/bridgeable-admin/hooks/_placement-adapter.ts` — F-3.1a adapter pattern (composition_blob adapter analog)
- `backend/app/models/widget_definition.py` — WidgetDefinition model (WB-1 extension target)
- `backend/app/models/focus_template.py` — focus_templates model (canonical tier-aware versioning shape for WB-1)
- `backend/app/models/focus_composition.py` — focus_compositions model (tier-3 inheritance precedent)
- `backend/app/services/focus_template_inheritance/focus_templates_service.py` — `_validate_placement` precedent for composition validator
- `backend/alembic/versions/r103_focus_templates_edit_session.py` — session-aware versioning migration (analog for WB-1 migration shape)

### FF-series precedent files
- `docs/investigations/2026-05-20-free-form-focus-canvas.md` — FF investigation as structural template
- `docs/investigations/2026-05-20-resize-handle-ux-refinements.md` — Finding 2 (drag UUID label leak — entry 25 source)
- `docs/investigations/2026-05-20-hover-state-staging-regression.md` — entry 27 source (event-type semantic enumeration)
- `docs/investigations/2026-05-20-resize-live-preview.md` — entry 29 + entry 32 + entry 33 sources

### Recent build commits
- F-3 `8ced75a` — F-series widget palette + canvas + inspector precedent
- F-3.1a `084f0ee` — placement adapter pattern
- F-3.1a.2 `4a73dbf` — URL recovery on 410-retry
- F-3.1b `c36f1e2` — chrome editing inspector
- F-3.1c `4bcdf96` — cross-side render+save integration test
- FF-1 `10321ed` — backend validator + adapter extension shape
- FF-2 `667deff` — canvas substrate replacement (mode detection)
- FF-6 `065b59e` — inspector positioning fields (uncontrolled-with-sync)
- FF-7 `14844c6` — Polish + Playwright verification gate (substrate locks)
- hover-fix `d9ffd90` — display:contents finding (entry 28)
- resize-handle UX `a1c10c7` — Q-10 hover refinement + resolveDragLabel
- resize-live-preview `9958fe0` — resizeInitialPlacementRef snapshot pattern (entry 29)
- canon-update `a113d23` — FF-series consolidated canon-update arc (current HEAD)

---

## Architectural surprises during investigation

1. **`widget_definitions` table already exists.** Pre-investigation expectation: WB-1 would create a new table. Discovery: the `widget_definitions` table has been in production since Phase W-1 (April 2026) carrying the 5-axis filter + variant declarations + supported_surfaces. The current table is a CATALOG (each row describes a widget's metadata + visibility); it does NOT yet carry a composition blob. WB-1 EXTENDS the existing table with `composition_blob` + `composition_version` + `tier_scope` + session-aware columns. This is structurally simpler than the expected new-table path.

2. **Two-layer widget registration system.** The full registration shape is `registerComponent(metadata)(Component) → wrapped` THEN `registerWidgetRenderer(slug, wrapped)`. R-1.6.12 (per file header at `widgets.ts:20-29`) wired the canvas runtime to consume the WRAPPED output specifically so the runtime DOM carries `data-component-name` for click-to-edit. This is a load-bearing two-layer pattern. WB's `ComposedWidget` runtime renderer must navigate both layers correctly — `ComposedWidget` itself registers via `registerComponent` (gets the wrapper) and via `registerWidgetRenderer` (becomes canvas-dispatchable).

3. **`SavedViewWidget` is the canonical precedent for config-driven container widgets.** Pre-investigation assumption: composed widgets are net-new architectural pattern. Discovery: `frontend/src/components/widgets/foundation/SavedViewWidget.tsx` already implements the "user-authored widget catalog without widget code" pattern — a single registered widget that takes `config.view_id` and renders any saved view. WB-series's `ComposedWidget` is the GENERALIZATION of this pattern from "saved view + variant rendering" to "saved view + composition blob + variant rendering." The architectural precedent strengthens the case for runtime interpretation (Q-2 (c) lock) — the platform already runs config-driven widgets in production and it works.

4. **Atom catalog Phase 1 cardinality (8) matches the existing config_prop_type cardinality (8 + 4 = 12 with Documents extensions).** Both substrates ship a curated finite catalog at Phase 1, both grow incrementally. The PARALLELISM is not coincidence — both are operator-facing primitive catalogs over operator-author surfaces. Pattern: "curated finite Phase 1 + documented growth mechanism" is canon-shape-worthy for future builder primitives.

5. **Tier-3 widget definitions are NOT in scope.** Pre-investigation expectation: WB ships full three-tier inheritance (platform → vertical → tenant) for widget definitions parallel to focus_compositions. Discovery: tenant-tier widget customization rides on PLACEMENT-LEVEL prop_overrides (existing). Tier-3 widget DEFINITIONS don't need to exist for September. This significantly de-risks the schema substrate.

6. **register.ts:215's display:contents wrapper is load-bearing for atom-level click-to-edit.** Per entry 28 canon, but architecturally significant: the wrapper makes click-to-edit work at every layer of nested composition. An atom inside a composed widget inside a placement on a Focus canvas can be click-selected by walking up `data-component-name` ancestors. This is the substrate that makes Tier-3 placement chrome editing work in Live mode. WB MUST preserve this.

---

## Operator-validation gates (per entry 26 canon)

Locks tagged "operator-validation-sensitive" — calibrated against intuition + canonical reference but should be revisited after operators hand-validate on staging:

- **Q-4 (atom catalog Phase 1)** — 8 atoms may be too narrow or too broad. Concrete operator usage post-WB-2 informs the WB-7 expansion catalog.
- **Q-5 (two-level nesting)** — operators may want 3+ levels. Post-WB-3 usage informs.
- **Q-10 (variant-driven atom visibility)** — operators may prefer separate-composition-per-variant for complex widgets. Post-WB-6 usage informs.
- **Q-12 (explicit iteration mode)** — operators may find the picker confusing or under-specified. Post-WB-3 usage informs.
- **Q-22 (Glance compactness soft warning)** — soft warning may be ignored, producing broken Glance layouts. Operator feedback informs whether to harden to a stronger constraint.
- **Q-RISK-3 (atom catalog over-narrow)** — observable signal: count of widgets composing around catalog gaps.

Locks tagged "architecturally-determined" — do NOT revisit on operator feedback alone; revisit only if architectural constraint changes:

- **Q-1 (operator mental model — hybrid)** — substrate cost reasoning
- **Q-2 (coexistence — both render paths)** — canon + cross-substrate audit
- **Q-3 (Tier-3 at placement level)** — canon + scope discipline
- **Q-26/Q-27/Q-28 (HOC reconciliation)** — entry 28 canon
- **Q-29 (extend widget_definitions table)** — existing substrate
- **Q-32 (slug-based URL)** — 2026-05-19 PM canon

---

## Process canon candidates (surfaced for future canon-update arc; NOT filed in this investigation)

Per dispatch prompt's deliverable §13 — flag for future canon-update arc; do NOT file in this investigation:

1. **"Curated finite Phase 1 catalog + documented growth mechanism" as pattern** — observed in three substrate locations (config_prop_type, status families, atom catalog Phase 1). Worth canon-shape-extracting in a future canon-update arc.

2. **"Two-layer registration system" as cross-substrate pattern audit candidate** — registerComponent + registerWidgetRenderer is a load-bearing two-layer registration. R-1.6.12 wired them; the discovery pattern is "find the wrapped-vs-unwrapped layer; assert both layers consume the same wrapped reference." Generalizes to: focus_compositions + CompositionRenderer; future Page Builder layouts + PageRenderer; etc. Worth canon-extracting "two-layer registration audit" pattern.

3. **"Existing substrate as architectural precedent" pre-investigation discovery discipline** — three surprises in this investigation came from existing-substrate-already-implements-the-pattern (widget_definitions table; SavedViewWidget config-driven pattern; R-1.6.12 wrapped registration discipline). Worth canon-extracting "always grep for the pattern's existing implementation before designing a new one." Adjacent to the existing entry 28 "cross-substrate HOC audit" but on a different axis (existing-substrate-precedent vs cross-substrate-dependency).

4. **"Architectural-vs-operator-validation lock tagging at investigation time"** — this investigation explicitly tags each lock as "operator-validation-sensitive" vs "architecturally-determined" per entry 26's spirit but more granular. Worth canonicalizing tagging discipline (investigation authors mark each lock at lock time).

5. **"Tier-3 at placement level instead of new table"** — Q-3 lock is a load-bearing schema-simplification driven by canon discipline. The pattern "before adding a Tier-3 table, ask whether placement-level overrides suffice" generalizes. Worth canon-extracting.

---

## Closing summary

WB-series ships 8 sub-arcs producing the operator-facing composed widget authoring substrate. Locked operator mental model = hybrid (template seed + free modification); composition primitives = 8 atoms Phase 1 + 2-level layout containers; data bindings = structured BindingRef referring to Vault saved views; behavior = bounded vocabulary respecting DESIGN_LANGUAGE §12.6a; rendering = variant-driven across canonical surfaces. registerComponent HOC reconciled via dual wrapping (composed widget + atoms). Persistence extends existing `widget_definitions` table; tier inheritance via Tier 1+2 definitions + placement-level Tier 3 overrides. Test substrate per FF-series canon (Playwright + cross-side + source-shape gates). Coexists cleanly with future Page Builder, Document Builder, Workflow Builder per primitive-shape-distinction.

Estimated total LOC ~11,000 (midpoint) / ~14,000 (worst case). Sequential dispatch WB-1 → WB-8. Each sub-arc ships visibly. Architecture honors every relevant canon entry; surprises documented; risks mitigated.
