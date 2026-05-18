# Focus Builder Investigation

Date: 2026-05-18
Purpose: Surface architectural questions + lock decisions where defensible for the **F-series** arc — the operator-facing **Focus Builder** that replaces the tier-aware editor's UX while consuming the same C-2 / E-1 substrate.
Status: Investigation closed; awaiting James review on TBD questions before F-1 dispatch.
Estimated total F-series LOC: ~6,500–9,500 across 5 sub-arcs (range; see §Sub-arc decomposition).
Recommended dispatch shape: **F-1 → F-2 → F-3 → F-4 → F-5**, in order, no interleaving.

---

## Purpose + scope

C-2 shipped the tier-aware editor (Tier 1 cores in `Tier1CoresEditor`, Tier 2 templates in `Tier2TemplatesEditor`, explicit tier-toggle UI in `FocusEditorPage`'s top bar, lineage chrome + InheritedCoreInspectorPanel for cross-tier inspection). E-1 + E-1.1 closed canonical visual alignment of the scheduling-kanban-core's chrome + the Tier 1 preview backdrop.

The **Focus Builder** is a different UX over the same backend substrate. It:

- Hides "Tier 1 vs Tier 2" from the operator entirely. Cores and templates are surfaced through a **vertical-grouped tree** where the discoverability story is "find the right focus type inside your vertical" — not "pick a tier."
- Replaces the C-2 all-visible inspector with a **selection-driven** inspector: empty canvas selection → "nothing selected" state in right rail; click background → substrate + theme editing; click core → core chrome editing; click widget → widget chrome.
- Promotes the **widget palette** and the **theme picker** to first-class right-rail content (collapsible sections coexisting with the inspector).
- Surfaces editing context via a **breadcrumb** (vertical → focus-type → core/template), replacing C-2's tier-toggle pill.

The investigation produces lockable architectural decisions across navigation, selection, palette, theme picker, breadcrumb, and decomposition. It deliberately does **not** address Tier 3 in-place editing (sub-arc D), the standalone Theme editor refinements, audit substrate, edge-panel work, mobile, performance, or cross-tenant publishing.

---

## Context

What C-2 + E-1 shipped that Focus Builder consumes:

- **Backend substrate** (`backend/app/services/focus_template_inheritance/*`): `focus_cores_service`, `focus_templates_service`, `resolver.py`, `schemas.py`. Endpoints at `/api/platform/admin/focus-template-inheritance/{cores,templates}/*` with `/resolve` endpoint returning `sources.chrome_sources`, `sources.substrate_sources`, `sources.typography_sources` provenance. Edit-session semantics (C-2.1.1 + C-2.1.2) handle in-place mutation within a 5-minute window without version-bumping on every scrub.
- **Frontend services** (`bridgeable-admin/services/`): `focus-cores-service.ts`, `focus-templates-service.ts`, `focus-compositions-service.ts`. Typed CoreRecord / TemplateRecord + create/update payloads + StaleCoreErrorBody contract for 410 Gone responses.
- **Draft hooks** (`bridgeable-admin/hooks/`): `useFocusCoreDraft` (366 LOC) + `useFocusTemplateDraft` (458 LOC). Both: 300ms-debounced auto-save, dirty-state tracking, edit-session token, full-shape response handling (C-2.1.3), defensive dirty-state comparison.
- **C-1 visual-authoring primitives** (`components/visual-authoring/`): `PropertyPanel`, `PropertySection`, `PropertyRow`, `ScrubbableButton`, `TokenSwatchPicker`, `ChromePresetPicker`, `SubstratePresetPicker`, `TypographyPresetPicker`, with `PropertyRowInheritance` shape for per-row "inherited from" indicators.
- **Resolver modules** (`bridgeable-admin/lib/visual-editor/`): `chrome-resolver.ts` (expandPreset, mergeChromeWithOverrides, resolveChromeStyle), `substrate-resolver.ts` (5 canonical presets — morning-warm + 4 others, expandSubstratePreset, resolveSubstrateStyle), `typography-resolver.ts` (4 canonical presets, head/body resolution).
- **Shared substrate**: `BASE_TOKENS` (`lib/visual-editor/themes/base-tokens.ts`) + `resolveEffectiveTokens`. Tokens.css remains canonical platform-default; `platform_themes` carries override layers. Locked decision from C-2 Q7.
- **Tier-aware editor surfaces** (READ-ONLY for F-series): `FocusEditorPage` (328 LOC), `Tier1CoresEditor` (453), `Tier2TemplatesEditor` (923), `InheritedCoreInspectorPanel` (324), `CreateTierOneCoreModal`, `CreateTierTwoTemplateModal`.

The Focus Builder mounts at a new route (TBD per Q-19) and **coexists** with `FocusEditorPage` initially (Q-21).

---

## Canonical UX target

James's hand-drawn mockup (referenced verbally; not committed as image asset at investigation time — see "Report MUST surface" #3) depicts a three-region layout:

**LEFT RAIL — vertical-grouped tree**

```
▾ Manufacturing
  ▾ Production
    Kanban dispatch                    ← clickable core
    ▾ Kanban dispatch templates
       Scheduling — FH evening shift   ← template inheriting
       Scheduling — manufacturing day
       + New Kanban-dispatch-based template
  ▸ Decision
  ▸ Coordination
▸ Funeral Home
▸ Cemetery
▸ Crematory
```

- Top level: verticals (Manufacturing, Funeral Home, Cemetery, Crematory, future extension verticals), each collapsible.
- Inside a vertical: **focus-type sub-groups** (Decision, Coordination, Production, Triage, Scribe, etc.) derived from `registered_component_kind` or a curated focus-type taxonomy.
- Inside a focus-type: individual **cores**, expandable via the ▾ chevron to reveal their inheriting **templates** + a "+ New `<CoreName>`-based template" affordance.
- Click a core → editor loads the core (Tier 1 in C-2 vocabulary, "the canonical chrome for X" in Focus Builder vocabulary).
- Click a template → editor loads the template (Tier 2 vocabulary, "this variant of X" in Focus Builder vocabulary).
- Tier mechanics are hidden; the operator sees a tree of focuses they can author.

**CENTER CANVAS — focus preview + selection-driven interaction**

```
┌─ Manufacturing › Production › Kanban dispatch › Scheduling FH evening ───┐
│  Auto-saved 12s ago                                                       │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  [Substrate atmosphere — gradient backdrop]                               │
│                                                                           │
│   ┌─────────────────────────────────────────────┐                         │
│   │ [Inherited core placement — Kanban canvas]  │                         │
│   └─────────────────────────────────────────────┘                         │
│                                                                           │
│   ┌─ AncillaryPoolPin ─┐    ┌─ TodayWidget ─┐                             │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

- Top: breadcrumb showing **vertical → focus-type → core → template** (when a template is loaded) + dirty/saved indicator.
- Below: focus preview canvas. Inherited core placement + accessory widgets.
- Background click → right rail shows substrate + theme.
- Core click → right rail shows core chrome.
- Widget click → right rail shows widget chrome.
- Outside click → right rail returns to "nothing selected."

**RIGHT RAIL — three coexisting sections**

```
┌─ Inspector ─────────────────────┐
│ (selection-driven)              │
│ Nothing selected.               │
│ Click background to edit theme. │
├─ Widget Palette ▾ ──────────────┤
│ ─ Ancillaries                   │
│   [AncillaryPool] [Driver Stack]│
│ ─ Map                           │
│   [RouteMap] [ZonePins]         │
│ ─ Information                   │
│   [TodayWidget] [Briefing]      │
├─ Theme ▾ ───────────────────────┤
│ Substrate presets               │
│   ◉ Morning Warm  ○ Cool Morn   │
│   ○ Twilight       ○ Studio     │
│ Typography presets              │
│   ◉ Plex Editorial ○ Plex Tight │
└─────────────────────────────────┘
```

**Hidden from operator:**
- "Tier 1 vs Tier 2."
- `inherits_from_core_version` (the version pin from C-2.3).
- Orphan cores not surfaced through a vertical (cores whose `registered_component_kind` doesn't map cleanly to a focus-type taxonomy entry — see Q-7).

---

## Architectural questions

For each Q-N below: title · what's at stake · options + rationale · **LOCKED** (with locking reasoning) or **TBD with James** (with sub-options articulated).

### Q-1: Vertical discovery in the left rail

**At stake:** How does the left rail know what verticals to render at the top level?

**Options:**
- (a) **DB-backed** — fetch `verticals` table (added in r92, ~5 active rows) via a `/api/platform/admin/verticals` endpoint (TBD whether one exists; needs check or new route).
- (b) **Hardcoded** in frontend constant (`["manufacturing", "funeral_home", "cemetery", "crematory"]`).
- (c) **Hybrid** — backend endpoint with frontend constant as fallback.

**Rationale:**
- (a) is the canonical pattern (vertical-as-FK migration is in flight; r92 created `verticals` as first-class). Future extension verticals will land in the DB, not in frontend constants.
- (b) wins on simplicity for F-1 but creates a drift surface — extension installs that add a vertical (per the post-r92 migration plan) wouldn't show up in the builder without a code change.
- (c) is over-engineered for a 5-row table.

**LOCKED: (a)** — DB-backed via new endpoint `GET /api/platform/admin/verticals` returning active verticals ordered by `sort_order`. F-1 ships the endpoint if it doesn't exist; rationale is the canonical migration pattern locked in r92 + CLAUDE.md §5 "Vertical column convention" entry.

### Q-2: Focus-type sub-group taxonomy

**At stake:** What does "Production / Decision / Coordination / Triage / Scribe" mean structurally? Does the tree's middle level come from data or from a curated taxonomy?

**Options:**
- (a) **Derive from `registered_component_kind`** on each core. Today `focus_cores.registered_component_kind` is a free-form string (e.g. `"focus-template"` from the registry, or future kinds like `"focus-core"`). Group cores by this field.
- (b) **Curated taxonomy in frontend** — a fixed `FOCUS_TYPE_TAXONOMY` constant declaring focus-types as a closed enum (Decision, Coordination, Production, Triage, Scribe, Authoring, Monitoring). Each core declares its focus-type via a new field.
- (c) **DB field on `focus_cores`** — add `focus_type` column (nullable for back-compat; defaulted by code per existing core). New migration.

**Rationale:**
- (a) leaks implementation detail (`registered_component_kind` is a registry-level string, not a UX-level grouping).
- (b) is a maintenance burden — every new focus-type needs a code change. But it's the *correct* opinionated default per CLAUDE.md §1a "Opinionated but Configurable" — platform ships a taxonomy; tenants can't add focus-types ad-hoc.
- (c) gives operators the ability to recategorize, but the operator-recategorize use case is implausible (a kanban core IS a Production focus; recategorization invites incoherence).

**LOCKED: (b)** — curated frontend taxonomy in `lib/visual-editor/focus-types.ts`. F-1 ships an initial taxonomy (Production, Decision, Coordination, Triage, Scribe) plus a mapping `function focusTypeForCore(core: CoreRecord): FocusType` that consults `registered_component_kind` + a `core_slug`-to-type override table. Adding a new focus-type = one row in the taxonomy + the mapping table.

### Q-3: Categorization assignment per core

**At stake:** Where does the "kanban-dispatch core belongs to Production focus-type" mapping live?

**Options:**
- (a) **Derived from component registry metadata** — the registered React component declares its focus-type via `RegistrationMetadata.focusType` (new optional field).
- (b) **Frontend mapping table** — `CORE_SLUG_TO_FOCUS_TYPE: Record<string, FocusType>` constant.
- (c) **DB field on `focus_cores`** — adds the column from Q-2 option (c).

**Rationale:**
- Q-2 locked (b), so categorization needs to coexist with the curated taxonomy. (a) is principled but couples Focus Builder UX to the component registry's schema (which would balloon registry-types.ts).
- (b) is the natural complement to Q-2's locked taxonomy — single file holds both. ~30 rows max in initial state.

**LOCKED: (b)** — `lib/visual-editor/focus-types.ts` ships both the taxonomy AND the `core_slug → focus_type` map. Fallback: cores without an explicit mapping render under an "Other" sub-group (NOT under a vertical — see Q-7 for orphan handling).

### Q-4: Tree expansion state persistence

**At stake:** Does the operator's tree state (which verticals/focus-types are expanded) persist across sessions?

**Options:**
- (a) **Per-user persistent** via a new field on `User.preferences.focus_builder_tree_expanded: string[]` (list of expanded node ids).
- (b) **Session ephemeral** — `useState`, lost on page reload.
- (c) **localStorage** — persists across reloads on the same device, doesn't sync cross-device.

**Rationale:**
- (a) is the "platform remembers you" canon (cf. Spaces preferences). But Focus Builder is an admin-only surface; cross-device persistence is low-value.
- (b) is fine for F-1 but the operator-tested-it-and-it-collapsed-everything-on-reload experience is bad.
- (c) is the lightest pragmatic answer — single-machine power user gets their state back.

**LOCKED: (c)** — localStorage under key `bridgeable.focus-builder.tree-expanded` (JSON array of node ids). Future arc can lift to per-user `preferences` if cross-device demand surfaces.

### Q-5: Default expansion on first load

**At stake:** What's the first-load tree state for a brand-new operator (no localStorage)?

**Options:**
- (a) **All verticals expanded, focus-types collapsed.**
- (b) **First vertical expanded** (alphabetical or by `sort_order`), rest collapsed.
- (c) **Studio's active vertical expanded** — if the operator entered Focus Builder via Studio with a vertical in scope, expand that vertical's tree.

**Rationale:**
- (a) drops the operator into a wall of focus-types — high cognitive load.
- (b) is arbitrary.
- (c) preserves operator intent (they were just working in funeral_home → land them there).

**LOCKED: (c)** — Studio-active-vertical expanded by default. Fallback to alphabetical-first when no Studio scope is active. Inside the expanded vertical, all focus-types start expanded so cores are visible. Templates inside cores stay collapsed (the ▾ on each core is the operator's entry point).

### Q-6: Search/filter in the left rail

**At stake:** Should the left rail expose a search box to filter the tree?

**Options:**
- (a) **Ship in F-1** — single text input at the top of the rail; substring-matches against vertical names + focus-type names + core display_names + template display_names; collapses non-matching subtrees.
- (b) **Defer to F-5 polish** or post-arc.

**Rationale:**
- Initial tree size is modest (5 verticals × ~5 focus-types × ~2 cores × ~3 templates ≈ 150 leaf nodes worst case). Scroll suffices.
- BUT — once the platform ships ~20 cores + ~50 templates, search becomes load-bearing.
- F-1 is the layout-shell sub-arc; adding search complicates scope (debounce, highlight, scroll-into-view).

**LOCKED: defer to F-5** — F-1 ships scroll-only navigation; F-5's polish pass adds search if operator feedback demands it. Decision can be revisited at F-3 dispatch if accessory authoring exposes scroll fatigue.

### Q-7: Orphan cores handling

**At stake:** What happens to cores that don't map to a focus-type taxonomy entry (e.g., a new core whose `core_slug` isn't in `CORE_SLUG_TO_FOCUS_TYPE`)?

**Options:**
- (a) **Render under an "Other" focus-type sub-group inside the core's matched vertical.**
- (b) **Surface in a dedicated "Unclassified cores" section at the bottom of the rail** (above all verticals).
- (c) **Hide entirely** — operators only see classified cores. Unclassified cores are platform-engineering work (drop them into the taxonomy before they ship).

**Rationale:**
- (a) keeps the vertical grouping intact but normalizes unclassified state.
- (b) is more honest about "this needs platform-engineering attention" but creates a UI escape hatch operators won't understand.
- (c) is the strictest opinionated default — cores ship classified or they don't ship. But it breaks the iterative pattern where a new core lands in code first + gets classified in a follow-up.

**LOCKED: (a)** — "Other" sub-group inside vertical when the core's vertical can be determined (via Studio active vertical or via a `vertical` column on `focus_cores` if one exists; check at F-1). If vertical cannot be determined, fall back to a top-level "Unclassified" pseudo-vertical at the bottom of the rail. The pseudo-vertical is platform-engineering's signal to classify.

### Q-8: Platform-default vs vertical-default vs tenant-default surfacing

**At stake:** Templates have `scope ∈ {platform_default, vertical_default}` and (post-arc) `tenant_override`. The tree must communicate scope without leaking jargon.

**Options:**
- (a) **Single flat list of templates inside a core**, with a small chip (▲ "platform" / ▲ "vertical" / ▲ "tenant") next to scope-divergent templates.
- (b) **Sub-grouped templates by scope** — "Platform defaults" subheader, "Vertical defaults" subheader, etc.
- (c) **Hide scope entirely** — templates render flat, scope is shown only when editing the template (in the inspector or breadcrumb).

**Rationale:**
- (a) preserves the flat list while giving sophisticated operators a signal. The chip is small, non-modal, ignorable by novices.
- (b) creates visual fragmentation in the tree for an attribute most operators don't think in.
- (c) is the most opinionated-defaults play — operators discover scope only when it becomes relevant (editing).

**LOCKED: (a)** — flat list with chip. Chip styling tracks the DESIGN_LANGUAGE muted-token palette (`text-content-muted`, font-plex-mono, 9px caps). Tenant scope is post-arc (no tenant_override surface yet in F-series); chip vocabulary ships with "platform" + "vertical" + a reserved "tenant" slot.

### Q-9: Tree leaf model — cores vs templates differentiation

**At stake:** Visually, how does an operator know a core leaf differs from a template leaf?

**Options:**
- (a) **Icon prefix** — core = `◆`, template = `◇` (or icon component variants).
- (b) **Indentation depth** — cores at one indent level, templates one level deeper.
- (c) **Both** — icon + indent.

**Rationale:** Indent alone is ambiguous because the ▾-expanded core also adds visual depth. Icon alone might read as decoration. Combining them gives both a structural and a typographic cue.

**LOCKED: (c)** — both. F-1 ships with placeholder icons (lucide `Square` for core, `SquareDashed` for template); F-5 polish refines.

### Q-10: "+ New `<CoreName>`-based template" affordance

**At stake:** What does clicking the inline "+ New" affordance under a core do?

**Options:**
- (a) **Open the existing `CreateTierTwoTemplateModal`** with `inherits_from_core_id` pre-filled.
- (b) **New dedicated flow** — inline tree entry that becomes editable (no modal).
- (c) **Open a streamlined modal** — drops the scope/vertical pickers when context is unambiguous (operator is inside the manufacturing tree → vertical_default + manufacturing).

**Rationale:**
- (a) reuses canonical modal, lowest LOC.
- (b) breaks tree-as-navigation invariant (tree becomes write-surface too).
- (c) is the right opinionated UX — vertical is contextually determined; scope defaults to vertical_default (since operator is in a vertical's subtree); operator confirms slug + name only.

**LOCKED: (c)** — F-3 ships a streamlined `CreateTemplateFromCoreFlow` component (~150 LOC) that wraps the existing service call. `CreateTierTwoTemplateModal` stays in place for the tier-aware editor's coexistence period (Q-21).

### Q-11: Editing core vs template visual differentiation in the canvas

**At stake:** When the operator is editing a core (vs a template), the canvas semantically differs — the core has no inherited core to place; the template does. How does the canvas convey "you're editing the canonical version" vs "you're editing a variant"?

**Options:**
- (a) **Breadcrumb is the only signal** — the canvas renders identically; only the breadcrumb shows whether you're at the core or template leaf.
- (b) **Subtle canvas chrome difference** — e.g., breadcrumb-attached "Canonical" label when editing a core; faded "Variant of `<CoreName>`" caption when editing a template.
- (c) **Distinct canvas backdrops** — different substrate atmosphere for core vs template.

**Rationale:** (c) is overengineered (breaks the substrate-resolver canon). (a) is too subtle — operator scrolling fast might not register. (b) gives a typographic cue without rearranging visual language.

**TBD with James** — (b) is the recommended lean but the exact copy + placement is a design call. Default option for F-1 dispatch: (b) with text "Canonical core" vs "Variant of `<CoreName>`" rendered immediately under the breadcrumb in `text-content-muted` 11px.

### Q-12: Inheriting templates visible when editing core

**At stake:** When the operator edits a core, can they see at a glance which templates inherit from it?

**Options:**
- (a) **Surface in the right rail when no canvas selection** — a "Templates inheriting from this core" section below the empty-state inspector message.
- (b) **Surface in the breadcrumb** — "Editing Kanban dispatch › 3 inheriting templates".
- (c) **Surface inline in the left tree** — the templates are already visible there; no second surface needed.

**Rationale:** (c) is already the canonical answer — the tree is the operator's mental model of "what depends on what." Adding (a) or (b) is duplication.

**LOCKED: (c)** — left tree is sole surface. Operator can click any inheriting template to switch into it.

### Q-13: InheritedCoreInspectorPanel fate

**At stake:** C-2.2c shipped `InheritedCoreInspectorPanel` (324 LOC) — a side panel that lets the Tier 2 editor inspect the Tier 1 core's values read-only. Does Focus Builder keep this affordance?

**Options:**
- (a) **Keep** the side panel; trigger it from a "View canonical core" button in the breadcrumb or inspector when editing a template.
- (b) **Remove** — replace with "switch to the core leaf in the left tree" workflow. The tree IS the navigation.
- (c) **Reuse inline** — render the panel's contents inline in the inspector when an inherited-core element is selected on the canvas.

**Rationale:**
- (b) is the natural Focus Builder simplification — tree navigation replaces tier toggle + side panel.
- (a) preserves the cross-tier-without-losing-state affordance from C-2.3, but Focus Builder operators don't think in tiers; the affordance loses its motivating context.
- (c) confuses "selection-driven inspector" with read-only inspection.

**LOCKED: (b)** — remove from Focus Builder. Tree navigation is the canonical cross-context path. `InheritedCoreInspectorPanel` stays in the codebase for the coexistence period (Q-21); when `FocusEditorPage` retires, the component file can be deleted.

### Q-14: Selection state location

**At stake:** Where does "what's selected on the canvas" live?

**Options:**
- (a) **Local React state** in the Focus Builder root component.
- (b) **React context provider** (`FocusBuilderSelectionContext`) so nested canvas + inspector components can read/write.
- (c) **URL** — selection in `?selected=core|widget:<id>|background`.
- (d) **A reactive store** (Zustand / Jotai).

**Rationale:**
- (a) requires prop-drilling through canvas → placement → widget hierarchy.
- (b) is the canonical Bridgeable pattern (cf. SpaceContext, StudioRailContext).
- (c) is brittle (URL gets cluttered; deep-linkable selection has limited use cases).
- (d) introduces new dependency for a small state surface.

**LOCKED: (b)** — `FocusBuilderSelectionContext` colocated with the Focus Builder root. Shape: `{ selection: { kind: "background" | "core" | "widget" | "none", id?: string }; setSelection: (s) => void }`. Tracks single selection only (Q-15).

### Q-15: Multi-select

**At stake:** Should F-series support selecting multiple widgets at once?

**Options:**
- (a) **Ship in F-2** — shift-click adds to selection; inspector shows union of editable props.
- (b) **Defer post-arc** — single-select only in F-series.

**Rationale:** Multi-select implies multi-edit (common-prop union). Multi-edit is a substantial UX surface (which props are common? what's the "mixed" state look like?). C-2 didn't ship multi-edit; F-series shouldn't either without operator demand.

**LOCKED: (b) — defer.** F-2 ships single-select. Multi-select is a follow-up if operators ask.

### Q-16: Click-outside-to-deselect

**At stake:** What counts as "outside the canvas" for deselect purposes?

**Options:**
- (a) **Click on the canvas background area** (substrate region not covered by core or widgets) deselects.
- (b) **Click anywhere outside the right-rail inspector content** deselects, including on top of widgets (which would re-select to the clicked widget).
- (c) **Explicit "Deselect" button + Esc keyboard.**

**Rationale:** (a) is the canonical native-app behavior (Figma, Sketch). (b) collapses select + deselect into one path. (c) is friction.

**LOCKED: (a) + Esc** — Esc-to-deselect ships as keyboard convenience. Clicking a different widget re-selects (does not double-fire deselect→select).

### Q-17: Hook layer extension vs replacement

**At stake:** `useFocusCoreDraft` + `useFocusTemplateDraft` are written for the tier-aware editor's all-visible inspector. Does Focus Builder reuse them or wrap them?

**Options:**
- (a) **Reuse as-is** — Focus Builder's inspector imports the same hooks; selection-driven UI just chooses which subset of hook state to render.
- (b) **Wrap with a `useFocusBuilderDraft` hook** — accepts either core_id or template_id, returns a uniform `{ subject, draft, updateDraft, ... }` shape.
- (c) **Replace** — write new hooks from scratch tuned for selection-driven editing.

**Rationale:**
- (a) is correct — the hooks are model-of-edit, not model-of-UI. They handle draft state, debounce, dirty tracking, edit sessions. Selection-driven rendering is a presentation concern.
- (b) is sugar that pays off if Focus Builder edits cores + templates interchangeably (it doesn't — selection of a leaf in the tree decides which hook to mount).
- (c) reinvents 800+ LOC of edit-session + dirty-state + autosave logic.

**LOCKED: (a)** — reuse `useFocusCoreDraft` + `useFocusTemplateDraft` unchanged. Focus Builder root component mounts one or the other based on which tree leaf is selected.

**Architectural conflict surfaced:** the hooks currently surface ALL fields. Selection-driven rendering needs the hooks to expose `widgetChrome(widgetId)` + `coreChromeOverride()` + `substrate()` + `typography()` as distinct read paths. The shape is mostly there — `draft.chrome_overrides`, `draft.substrate`, `draft.typography` exist on `useFocusTemplateDraft`. F-2 will need an `updateWidget(widgetId, partialChrome)` helper that the current hook doesn't expose; surface area is small (~30 LOC).

### Q-18: Inspector content composition

**At stake:** Does the selection-driven inspector use the same C-1 primitives (`PropertyPanel`, `PropertySection`, `PropertyRow`, `ScrubbableButton`, `TokenSwatchPicker`) or does it need new abstractions?

**Options:**
- (a) **Same C-1 primitives** — selection just chooses which sections render.
- (b) **New `SelectionDrivenInspector` primitive** that abstracts the "render different sections based on selection.kind" pattern.

**Rationale:** (a) is correct; selection is a render-decision, not a primitive concern.

**LOCKED: (a)** — F-2 renders chrome / substrate / typography sections via the same C-1 primitives. The conditional logic (which sections to render given `selection.kind`) lives in the Focus Builder inspector component (`FocusBuilderInspector.tsx`).

### Q-19: Canvas dimensions

**At stake:** How big is the canvas? Fixed? Responsive?

**Options:**
- (a) **Fixed-fit-to-viewport** with horizontal scroll on overflow (matches C-2's canvas).
- (b) **Responsive grid** that scales accessory placements proportionally.
- (c) **Zoom + pan** — operator controls canvas viewport.

**Rationale:** (c) was deferred by C-2 Q3. Same reasoning applies. (b) introduces resolution-aware placement layout that the substrate doesn't model.

**LOCKED: (a)** — defer zoom/pan to a follow-up arc. F-series ships fixed-fit-to-viewport. Inheriting from C-2 canon.

### Q-20: Theme preview interaction

**At stake:** When the operator clicks a substrate or typography preset chip in the right-rail Theme section, does the change save immediately or stage-then-confirm?

**Options:**
- (a) **Immediate auto-save** — chip click → 300ms-debounced save via `useFocusTemplateDraft`'s existing pipeline.
- (b) **Stage-then-confirm** — chip click sets a preview; explicit Apply button commits.
- (c) **Hybrid** — immediate save, "Undo" toast for 5 seconds.

**Rationale:** C-2 locked auto-save canon (300ms debounce). Preset-click is the same UX shape — operator wants instant feedback. Reverting is the existing reset-to-inherited affordance.

**LOCKED: (a)** — immediate auto-save. Existing dirty-state + last-saved indicator surfaces in the breadcrumb.

### Q-21: Widget palette categorization

**At stake:** What are the widget categories?

**Options:**
- (a) **Curated frontend taxonomy** — `Ancillaries / Map / Information / Action / Decision`.
- (b) **Derived from component registry** — read each registered widget's `category` field.
- (c) **DB-backed**.

**Rationale:** Same shape as Q-2/Q-3 for focus-types. (a) is the locked answer for focus-types; consistency wins.

**LOCKED: (a)** — `lib/visual-editor/widget-palette.ts` ships the category taxonomy + the `widget_name → category` mapping. Adding a new widget category = one row in the taxonomy.

### Q-22: Widget palette registry source

**At stake:** What's the data source for "the list of widgets that can be placed"?

**Options:**
- (a) **Backend endpoint** — `GET /api/platform/admin/widget-registry` returns active widgets.
- (b) **Frontend component registry** — read from `getAllRegistered({kind: "widget"})` (the in-memory `lib/visual-editor/registry/` registrations).
- (c) **Hybrid** — backend supplies metadata, frontend supplies render function.

**Rationale:** Widgets ARE React components — they have to be locally registered to render anyway. The registry IS the source.

**LOCKED: (b)** — read from `getAllRegistered({kind: "widget"})`. The component registry's existing metadata (displayName, category, default props) is the source. F-3 ships a thin `useWidgetPalette()` hook reading from the registry + filtering to widgets with `canvasPlaceable: true`.

### Q-23: Widget palette per-item metadata

**At stake:** What does each widget card in the palette show?

**Options:**
- (a) **Name + icon + drag handle.**
- (b) **Name + icon + 1-line description.**
- (c) **Full preview thumbnail.**

**Rationale:** (c) requires per-widget thumbnail assets — too much asset work for F-3. (a) is minimal but operators might not recognize widgets by name alone.

**LOCKED: (b)** — name + icon + description. Description comes from `RegistrationMetadata.description` (existing field; defaults to displayName if absent).

### Q-24: Drag-drop infrastructure

**At stake:** What library powers widget → canvas drag?

**Options:**
- (a) **react-dnd**.
- (b) **@dnd-kit**.
- (c) **Native HTML5 drag-drop**.
- (d) **Bespoke pointer-event state machine** (matches C-2's `InteractivePlacementCanvas`).

**Rationale:**
- C-2 canon locks bespoke pointer-event for 2D-grid canvas (Arc 3a + 4c), @dnd-kit for 1D-list reorder (Arc 4b.1b).
- F-3 introduces a NEW drag pattern: widget palette (list) → canvas (2D grid). This crosses both canons.
- (a) ships in bundle size we don't pay yet.
- (b) is already in the codebase (Arc 4b.1b lock).
- (c) is friction-free for bundle but limited in coordination (e.g., dropping ghost preview).
- (d) is heaviest LOC.

**LOCKED: (b) @dnd-kit for the palette-to-canvas drag**, reusing the canon-locked @dnd-kit usage. The drop target on the canvas converts the @dnd-kit drop event into a placement-creation call that the bespoke 2D-grid pipeline handles thereafter. Hybrid is acceptable because the @dnd-kit boundary stops at the canvas edge.

### Q-25: Drop target scope on canvas

**At stake:** Where on the canvas can a widget be dropped?

**Options:**
- (a) **Anywhere on the canvas substrate area** (excluding the inherited core placement).
- (b) **Snapping to a 12-column grid** (existing C-2 canvas grid).
- (c) **Free placement** (x/y coordinates), no grid.

**Rationale:** The accessory placement model is rows-shape with column_count. Free placement would diverge from substrate schema.

**LOCKED: (b)** — snap to 12-column grid; dropped widget gets a new row with column_count=12 and the widget at column_start=1, column_span=4 (sensible default). Operator can resize via existing canvas affordances.

### Q-26: Newly-dropped widget position

**At stake:** When a widget is dropped, where does it land if the drop coordinate is ambiguous?

**Options:**
- (a) **At the cursor's grid cell.**
- (b) **At the next empty row below the existing placements.**
- (c) **Inside the nearest existing row if there's space; new row otherwise.**

**Rationale:** (a) is most intuitive but might collide with the inherited core. (c) is the canon for Figma-style canvases.

**LOCKED: (c)** — drop position resolves to (i) the nearest row with available column space if the drop coordinate is within a row, else (ii) a new row appended below. Inherited core's row is treated as full (no insertions allowed in the core's row).

### Q-27: Conflict with inherited core placement

**At stake:** If a widget would overlap the inherited core, what happens?

**Options:**
- (a) **Reject the drop** with a visual snap-back animation.
- (b) **Place adjacent** — drop coordinate slides to the nearest non-overlapping cell.
- (c) **Insert a new row** above or below the core.

**Rationale:** (b) is the least-surprising default in canvas authoring tools.

**LOCKED: (b)** — slide to nearest non-overlapping cell. The inherited core's row is treated as immutable (its placement geometry is bound by `min_column_span` / `max_column_span` per C-2 Q2).

### Q-28: Widget chrome editing

**At stake:** When a placed widget is selected, what does its inspector show?

**Options:**
- (a) **The widget's `consumedTokens` + `configurableProps`** from the registry metadata.
- (b) **A chrome-shape inspector** (preset / elevation / radius / etc.) treating the widget as a chromed surface.
- (c) **Both** — widget-specific props on top, chrome at the bottom.

**Rationale:** Widgets ARE chromed surfaces by class definition (registry's `class-registrations.ts`). They expose their own configurable props (defined per registration) and inherit class-level chrome props (shadowToken, surfaceToken, radiusToken, density, etc.).

**LOCKED: (c)** — F-3 ships widget inspector composing (i) widget-specific configurable props on top, (ii) class-level chrome props at the bottom (collapsible section). Two PropertySection stacks within one PropertyPanel.

### Q-29: Widget removal

**At stake:** How does the operator remove a placed widget?

**Options:**
- (a) **Delete key** when widget is selected.
- (b) **Context menu** (right-click) with "Remove."
- (c) **Inspector-level "Remove" button.**

**Rationale:** Power-user canvas convention.

**LOCKED: (a) + (c)** — Delete key (canonical canvas pattern) + inspector "Remove" button for discoverability. F-3 ships both.

### Q-30: Theme picker scope

**At stake:** Is "Theme" in the right rail the same vocabulary as `substrate` + `typography`, or a different abstraction?

**Options:**
- (a) **Theme = substrate preset alone.**
- (b) **Theme = typography preset alone.**
- (c) **Theme = substrate + typography combined.**
- (d) **Theme = a new compositional layer** (substrate + typography + chrome defaults bundled).

**Rationale:** The mockup's "Theme" section depicts both substrate and typography presets. (c) matches operator intuition: "the look of this focus."

**LOCKED: (c)** — Theme section contains two collapsible sub-sections: Substrate (5 presets) + Typography (4 presets). Backed by existing resolvers.

### Q-31: Theme preset registry source

**At stake:** Where do substrate + typography presets live?

**Options:**
- (a) **Frontend constants** (existing `substrate-resolver.ts` + `typography-resolver.ts`).
- (b) **Backend endpoint** returning seeded presets.

**Rationale:** Presets are code-defined per B-4 + B-5. Adding a new preset = code change in the resolver.

**LOCKED: (a)** — frontend resolver modules are the source.

### Q-32: Custom theme save (named preset creation)

**At stake:** Can operators save a custom substrate/typography config as a new named preset?

**Options:**
- (a) **F-4 ships custom theme save** — operator tunes substrate + typography, hits "Save as preset," names it, it appears alongside canonical presets.
- (b) **Defer post-arc.**

**Rationale:** Custom preset save introduces a new persistence surface (per-tenant or per-platform presets). Substrate at B-4 didn't ship a custom-preset table. This is meaningfully new substrate work.

**LOCKED: (b) — defer**. F-4 ships preset application only. Custom-preset persistence is a separate substrate arc (likely a "Theme editor refinement" arc — was flagged in C-2 Q7 as a follow-up).

### Q-33: Dark mode in Focus Builder

**At stake:** Does the operator-facing Focus Builder respect dark mode?

**Options:**
- (a) **Same theme as rest of admin chrome** (current theme-mode setting governs).
- (b) **Always light** — admin tooling stays in canonical light.
- (c) **Dual-mode preview** — operator can flip preview pane between light and dark independently of admin chrome.

**Rationale:** Aesthetic Arc Sessions 4 + 5 shipped dark mode end-to-end. Builder operator needs to author for both modes — a dual-mode preview is the right opinionated answer.

**TBD with James** — (c) is recommended but (a) is the simpler default for F-1 dispatch. Recommendation: F-1 ships (a); F-4 (theme picker arc) adds the dual-mode preview toggle to the Theme section.

### Q-34: Breadcrumb hierarchy

**At stake:** What levels appear in the breadcrumb?

**Options:**
- (a) **vertical → focus-type → core → template.**
- (b) **vertical → focus-type → template** (drop core when editing a template since it's implicit).
- (c) **vertical → core/template** (drop focus-type since the tree already shows it).

**Rationale:** Breadcrumb mirrors tree path. Operators navigating via deep-link benefit from full hierarchy.

**LOCKED: (a)** — full four-level breadcrumb when editing a template. When editing a core, drops the last level (vertical → focus-type → core). Auto-saved indicator floats right-aligned on the breadcrumb row.

### Q-35: Breadcrumb clickable navigation

**At stake:** Are breadcrumb crumbs clickable?

**Options:**
- (a) **All crumbs clickable** — vertical link navigates to vertical-scoped Focus Builder view (collapses other verticals in tree); focus-type link expands that subtree.
- (b) **Only "Back" affordance** — single up-level button.
- (c) **Non-clickable text only.**

**Rationale:** Clickable breadcrumb is the canonical pattern. Even simple "back up one level" use cases are well-served by it.

**LOCKED: (a)** — all crumbs clickable. Clicking a vertical crumb collapses other verticals in the tree (single-vertical focus mode). Clicking a focus-type crumb scrolls to + highlights that sub-group. Clicking the core crumb loads the core (Focus Builder doesn't switch from template-edit to core-edit destructively — the dirty-state guard from C-2.2c applies).

### Q-36: Dirty state in breadcrumb

**At stake:** Where does dirty/saved state surface — in the breadcrumb, or elsewhere?

**Options:**
- (a) **In the breadcrumb's right edge** (matches FocusEditorPage's top-bar pattern).
- (b) **Inside the right rail** — header chip on the inspector.
- (c) **Floating toast** — appears on save, dismisses after 2s.

**Rationale:** Operator's eye is on the canvas; dirty state must be peripherally-visible. (a) matches C-2 canon and is most pragmatic.

**LOCKED: (a)** — breadcrumb right-aligned indicator. Reuses the existing dirty-pulse + last-saved chrome from `FocusEditorPage`.

### Q-37: Tier indicator pill removal

**At stake:** C-2.3 shipped a "Tier 1" / "Tier 2" pill in the top bar. Does Focus Builder retain it?

**Options:**
- (a) **Remove entirely** — tier is hidden from operator.
- (b) **Keep, but rename** (e.g., "Canonical" vs "Variant").
- (c) **Keep, but show only in a debug/dev mode.**

**Rationale:** Q-11 already locked (b) — "Canonical core" / "Variant of X" captions render under the breadcrumb. Tier-pill is the same signal in different vocabulary; (a) avoids redundancy.

**LOCKED: (a)** — pill removed. Q-11's caption is the sole tier-equivalent signal.

### Q-38: Component decomposition / directory layout

**At stake:** Where do new Focus Builder components live?

**Options:**
- (a) **Extend `bridgeable-admin/components/visual-editor/`** with new files prefixed `FocusBuilder*`.
- (b) **New directory `bridgeable-admin/components/focus-builder/`** dedicated to the surface.
- (c) **New directory `bridgeable-admin/components/builder-primitives/`** for shared reusable bits + `focus-builder/` for Focus-specific.

**Rationale:** Pattern abstractions (Q-43) live in `builder-primitives/`; Focus-specific composition in `focus-builder/`. Reuse story for Page Builder / Document Builder lifts the primitives.

**LOCKED: (c)** — F-1 ships `bridgeable-admin/components/builder-primitives/` (VerticalGroupedTree, SelectionDrivenInspector, RightRailWithSections, BreadcrumbContext) + `bridgeable-admin/components/focus-builder/` (FocusBuilderPage, FocusBuilderInspector, FocusBuilderTree, FocusBuilderCanvas, FocusBuilderRightRail).

### Q-39: Route

**At stake:** What URL mounts the Focus Builder?

**Options:**
- (a) **Rename `/studio/focuses` → `/studio/builder/focuses`**, retiring the existing FocusEditorPage immediately.
- (b) **Keep `/studio/focuses` for FocusEditorPage**, mount Focus Builder at `/studio/builder/focuses`. Old route is the coexistence path.
- (c) **Same `/studio/focuses` but flag-gated** — feature flag toggles between FocusEditorPage and Focus Builder.

**Rationale:** Coexistence story (Q-21) requires both editors to be reachable. Flag-gating is heavy infrastructure for one feature. Separate route is the cleanest.

**LOCKED: (b)** — Focus Builder mounts at `/studio/builder/focuses`. FocusEditorPage stays at `/studio/focuses` for the coexistence period. Studio rail's Focus entry gets a small "Try the new Focus Builder" link pointing at the new route (one-time dismissible per operator).

### Q-40: URL deep-linking shape

**At stake:** What URL params does Focus Builder accept?

**Options:**
- (a) **`?vertical=manufacturing&focusType=production&core=<id>&template=<id>`** — full hierarchical params.
- (b) **`?subject=core:<id>` or `?subject=template:<id>`** — single param identifying the loaded subject; tree state inferred from subject.
- (c) **Hierarchical path** — `/studio/builder/focuses/manufacturing/production/kanban-dispatch/scheduling-fh-evening`.

**Rationale:**
- (a) is verbose but explicit.
- (b) is clean but requires tree-state-inference logic on load.
- (c) is the canonical web pattern but introduces a routing complexity React Router 7 can handle but Studio shell hasn't used.

**LOCKED: (b)** — single `?subject=core:<id>` or `?subject=template:<id>` param. Tree state inferred on load (vertical expanded → focus-type expanded → core expanded if subject is template). Preserves the `?return_to=` contract from FocusEditorPage.

### Q-41: Migration / coexistence

**At stake:** What happens to operators with FocusEditorPage bookmarked or linked?

**Options:**
- (a) **301-redirect** `/studio/focuses` → `/studio/builder/focuses` immediately.
- (b) **Coexist** — both routes work; deprecation banner on FocusEditorPage points at builder.
- (c) **Slow burn** — FocusEditorPage stays unchanged for 1 release; redirects in release N+1; deletes in release N+2.

**Rationale:** F-series is operator-facing breaking change. (a) is too abrupt for an internal tool used by a small population. (c) is over-engineered for an admin tool.

**LOCKED: (b)** — coexist with deprecation banner. Banner copy + dismiss persistence is F-5 polish work.

### Q-42: Deprecation timeline

**At stake:** When does FocusEditorPage delete?

**Options:**
- (a) **After F-5 ships + 1 release window** (~2 weeks).
- (b) **After operator sign-off** — James confirms migration is complete.
- (c) **Indefinite coexistence** — never delete.

**Rationale:** (c) is tech debt. (a) is too time-bound for an internal tool.

**LOCKED: (b)** — delete on James sign-off after F-5 ships. The component files (`Tier1CoresEditor`, `Tier2TemplatesEditor`, `InheritedCoreInspectorPanel`, `CreateTier{One,Two}*Modal`, `FocusEditorPage` itself, the two draft hooks if no longer used) get removed in a single cleanup commit.

---

## Pattern abstractions for future replication

Focus Builder is the first of four planned builders (Page Builder, Document Builder, Workflow Builder). The substrate-design opportunity is to extract the reusable primitives in F-1 and have the future builders consume them.

**Primitives to extract into `bridgeable-admin/components/builder-primitives/`:**

| Primitive | Contract | Consumer F-series sub-arc | Future reuse |
|---|---|---|---|
| `VerticalGroupedTree` | Props: `groups: TreeNode[]`, `selected: string \| null`, `onSelect(id)`, `expandedState: Record<string, boolean>`, `onExpandChange`. Renders nested collapsible tree. Selection model = single. | F-1 | Page Builder navigation (pages grouped by vertical), Document Builder (templates grouped), Workflow Builder (workflows grouped) |
| `SelectionDrivenInspector` | Props: `selection: { kind, id }`, `renderers: Record<SelectionKind, ReactNode>`. Renders appropriate child given selection.kind. Includes empty state. | F-2 | All four builders |
| `RightRailWithSections` | Props: `sections: { id, label, content, collapsible, defaultExpanded }[]`. Three+ stacked collapsible sections. | F-2 + F-3 + F-4 | All four builders (palette + properties + theme is a common shape) |
| `BreadcrumbContext` | Props: `crumbs: { label, href? }[]`, `rightSlot?: ReactNode`. Clickable hierarchical breadcrumb with optional right-aligned slot for dirty/saved chrome. | F-5 | All four builders |
| `WidgetPalette` | Props: `categories: PaletteCategory[]`, `onDragStart(widget)`. Categorized draggable cards. | F-3 | Page Builder (block palette), Document Builder (block palette) |
| `BuilderDragContext` | Encapsulates @dnd-kit boundary for palette → canvas drag. | F-3 | Page Builder, Document Builder |

**Anti-patterns to avoid** (so future builders inherit good substrate):
- Don't embed vertical-grouping logic inside `VerticalGroupedTree`. Pass `groups` as data, let consumer derive groups from their own taxonomy.
- Don't tie `SelectionDrivenInspector` to the C-1 PropertyPanel primitive. It takes opaque ReactNode renderers — Page Builder might render a TipTap toolbar there.
- Don't tie `RightRailWithSections` to specific section types. Consumer composes content into each section.

**Primitive that does NOT get extracted:**
- The Focus Builder's specific tree-to-hook glue (which hook to mount for which selected leaf) — this is Focus-specific because cores ≠ templates. Page Builder will have different subject types.

---

## Out-of-scope (explicit deferrals)

The following are explicitly NOT in F-series scope:

- **Tier 3 in-place editor (sub-arc D)** — the operator-level "edit this dashboard inline from the running platform" pattern lands in sub-arc D, not F.
- **Page Builder / Document Builder / Workflow Builder** — separate investigations and arcs. F-series extracts primitives for them but does not build them.
- **Standalone Theme editor** — the dedicated editor for `platform_themes` overrides is its own arc. Focus Builder's theme picker reads canonical presets only (Q-31, Q-32).
- **Custom theme preset persistence** — operators cannot save a custom substrate/typography combination as a new named preset in F-series (Q-32). Substrate arc adds this.
- **Audit substrate** — who-edited-what tracking for Focus Builder edits relies on existing audit infrastructure; no new substrate.
- **Edge-panel work** — sub-arc-D-adjacent territory.
- **Mobile-responsive Focus Builder** — admin surface; desktop-only.
- **Performance optimizations** — virtualization of the tree, lazy-load of inspector, etc. Initial corpus is small enough to skip.
- **Cross-tenant template publishing** — tenant_override scope is reserved but not surfaced in F-series (Q-8).
- **Multi-select on canvas** (Q-15).
- **Zoom / pan on canvas** (Q-19).
- **Search in left rail** (Q-6 — deferred to F-5 if demand surfaces).

---

## Sub-arc decomposition recommendation

F-series decomposes naturally into 5 sub-arcs around the surface seams. Each sub-arc:
- Falls under ~2,500 production LOC (consistent with C-2's decomposition ceiling per DECISIONS.md 2026-05-13 PM).
- Ships visibly — operator can use the surface after that sub-arc lands.
- Has no interleaving dependencies with adjacent F-arcs except sequential ordering.

### F-1 — Layout shell + vertical-grouped tree + URL state (read-only)

**Scope.** New route `/studio/builder/focuses`. Three-region layout shell (left tree / center canvas / right rail), placeholder content in canvas + right rail. `VerticalGroupedTree` primitive in `builder-primitives/`. Focus-type taxonomy + core-slug-to-focus-type mapping in `lib/visual-editor/focus-types.ts`. New endpoint `GET /api/platform/admin/verticals` if missing. localStorage tree-expansion persistence. URL contract (`?subject=core:<id>` / `?subject=template:<id>`). Tree → URL → subject load (read-only render of the loaded subject in the canvas; right rail = "nothing selected").

**Estimated LOC.** ~1,500–2,000 (production + tests).

**Ships visibly.** Operator can browse the new tree, click a core or template, see it load. No editing yet.

**Dependencies.** Q-1, Q-2, Q-3, Q-4, Q-5, Q-7, Q-8, Q-9, Q-14, Q-38, Q-39, Q-40 — all LOCKED or have lean defaults. F-1 can dispatch immediately.

### F-2 — Selection-driven inspector composition

**Scope.** `SelectionDrivenInspector` + `RightRailWithSections` primitives. Background-click + core-click selection states wired to the canvas. Right rail renders chrome / substrate / typography sections (when applicable to selection.kind) using existing C-1 primitives. Reuse of `useFocusCoreDraft` + `useFocusTemplateDraft`. `FocusBuilderSelectionContext`. Esc-to-deselect + click-outside-to-deselect. Per-row inheritance indicators (read from existing `sources.*_sources` provenance).

**Estimated LOC.** ~1,500–2,200.

**Ships visibly.** Operator can edit cores AND templates end-to-end (chrome, substrate, typography). Widget editing is still placeholder.

**Dependencies.** F-1 ships first. Q-14, Q-17, Q-18, Q-20 LOCKED.

### F-3 — Widget palette + drag-to-canvas + accessory placement editing

**Scope.** `WidgetPalette` primitive (right-rail middle section). @dnd-kit drag layer from palette to canvas. Drop-target conversion to placement-creation. Widget-selected inspector composition (widget-specific props + class-level chrome from registry). Widget remove (Delete key + inspector button). Conflict-with-core handling.

**Estimated LOC.** ~1,500–2,500.

**Ships visibly.** Operator can place + edit + remove accessory widgets on templates.

**Dependencies.** F-2 ships first. Q-21–Q-29 LOCKED.

### F-4 — Theme picker + preset application

**Scope.** Right-rail bottom section. Substrate preset chips (5) + Typography preset chips (4). Click → immediate save via existing hook pipeline. Optional dual-mode preview toggle (Q-33 TBD). Cross-link from the right-rail theme picker to the (separate) Theme editor for advanced operators.

**Estimated LOC.** ~600–1,000.

**Ships visibly.** Theme presets work in the Focus Builder. Custom preset save is deferred.

**Dependencies.** F-3 ships first. Q-30, Q-31, Q-32 LOCKED. Q-33 has lean default.

### F-5 — Breadcrumb context + dirty state + final UX polish + coexistence deprecation banner

**Scope.** `BreadcrumbContext` primitive. Breadcrumb mounted at top of canvas. Clickable crumbs. Dirty/saved chrome in right slot. "Canonical core" vs "Variant of X" caption (Q-11). Inheriting-templates surface (left tree only — already shipped in F-1 via Q-12 LOCKED choice). Tree search (if demand surfaced from F-3 operator feedback). Deprecation banner on FocusEditorPage pointing at builder route. Final accessibility pass (focus rings, ARIA labels, keyboard nav).

**Estimated LOC.** ~800–1,200.

**Ships visibly.** Focus Builder is feature-complete. Coexistence story is established.

**Dependencies.** F-4 ships first. Q-11 (TBD with James — gating F-5 design exit). Q-33 (TBD — recommend defer). Q-34, Q-35, Q-36, Q-37, Q-41 LOCKED.

### Total

**F-series midpoint LOC: ~6,500.** Worst-case ~9,500. Decomposition is natural at every seam; no sub-arc bundles concerns from another.

---

## Decisions summary

**LOCKED (agent decisions defensible from canon or substrate compatibility):** Q-1, Q-2, Q-3, Q-4, Q-5, Q-6, Q-7, Q-8, Q-9, Q-10, Q-12, Q-13, Q-14, Q-15, Q-16, Q-17, Q-18, Q-19, Q-20, Q-21, Q-22, Q-23, Q-24, Q-25, Q-26, Q-27, Q-28, Q-29, Q-30, Q-31, Q-32, Q-34, Q-35, Q-36, Q-37, Q-38, Q-39, Q-40, Q-41, Q-42 — **40 LOCKED**.

**TBD with James:** Q-11 (canonical/variant caption copy + placement), Q-33 (dark mode preview model — recommend (a) for F-1, defer dual-mode preview to F-4 or later) — **2 TBD**.

If James locks Q-11 and Q-33, F-1 can dispatch immediately. Q-33's resolution affects F-4 scope only; F-1 + F-2 + F-3 are not blocked.

---
