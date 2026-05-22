# Widget Builder — WB-8 variant authoring substrate investigation

**Date:** 2026-05-24
**Author:** Sonnet (read-only investigation)
**HEAD at investigation start:** `7e45453` (WB-7 build closed)
**Scope:** Read-only investigation. Zero production code touched. Zero test changes. Zero commits.
**Output:** This document + STATE.md update only.

---

## 1. Context

WB-7 (button action dispatch) shipped at `7e45453` (see STATE.md "Recent build (uncommitted)"). The WB cycle remaining is one sub-arc: **WB-8 — variant authoring UI**. WB-8 closes the WB substrate cycle that began with WB-1's `composition_blob` migration (r105) and matured through WB-4 (canvas authoring), WB-4b (per-atom inspectors), WB-5 (canvas preview wiring), WB-6 (saved-view bindings), and WB-7 (button actions).

**Why WB-8 is the closer.** Per the original WB investigation (`docs/investigations/2026-05-21-widget-builder.md` §Sub-arc decomposition), the four-variant taxonomy (Glance / Brief / Detail / Deep per DESIGN_LANGUAGE §12) is load-bearing for the "same widget, different surfaces" canon from BRIDGEABLE_MASTER §9.2. Without variant authoring, operators can compose widgets but cannot declare WHICH atoms render at WHICH surface — the widget renders the full atom set on every surface. The September Wilbert demo's "Glance on `spaces_pin` + Brief on `dashboard_grid` + Detail on `focus_canvas`" narrative requires variant authoring on the operator side.

**Sequencing rationale.** WB-8 ships LAST in the substrate cycle for three reasons. First, **substrate dependency**: variant authoring composes atop binding picker (WB-6), canvas preview (WB-5), per-atom inspectors (WB-4b), and action picker (WB-7) — every one of those primitives feeds into "which atoms render in which variant." Building variant authoring first would have meant shipping a UI with placeholder atoms / no bindings / no actions / no live preview. Second, **operator-validation surface area**: per DECISIONS entry 35 (investigation-time UX locks revisited by operator experience), variant authoring is uniquely operator-experience-dependent — the canonical Glance/Brief/Detail/Deep taxonomy is platform vocabulary, but operators authoring real widgets will produce signal about whether the per-atom-visibility model holds or breaks against real use. Third, **WB cycle closure**: WB-8 is the natural place to verify that all 10 areas of the original WB investigation (`2026-05-21-widget-builder.md` §Areas 1-10) have shipped substrate-ready surfaces.

This investigation locks the substrate shape for variant authoring UI against the existing four-section schema (`VariantDefinition` Pydantic + TypeScript mirror; `visible_in_variants` per-atom field; backend validator integrity checks). The audit-first phase (Area 1) is load-bearing: substrate exists in the schema layer but is **entirely dormant** at the authoring layer. Locking WB-8 requires accurate substrate-maturity assessment before deciding what ships.

---

## 2. Area 1 — Variant substrate audit (LOAD-BEARING)

Per WB-6/5/7 canon discipline, substrate maturity is audited before locks. The audit answers three questions per consumer: (a) does the substrate exist; (b) is it consumed; (c) what's the maturity state — mature / built-but-dormant / missing.

### 2.1 Schema layer (Pydantic + TypeScript mirror) — **MATURE**

- `backend/app/schemas/widget_composition.py:84`: `VariantId = Literal["glance", "brief", "detail", "deep"]` (4 canonical strings).
- `backend/app/schemas/widget_composition.py:86-90`: `TargetSurface = Literal["focus_canvas", "page_canvas", "palette_preview"]` (3 surfaces).
- `backend/app/schemas/widget_composition.py:159`: `AtomNode.visible_in_variants: Optional[List[VariantId]] = None`.
- `backend/app/schemas/widget_composition.py:166-182`: `VariantDefinition { variant_id: str, variant_name: str, target_surface: TargetSurface, canonical_dimensions: Optional[Dict[str,int]] }`.
- `backend/app/schemas/widget_composition.py:211`: `CompositionBlob.variants: List[VariantDefinition] = []`.
- `frontend/src/lib/widget-builder/types/composition-blob.ts:47-94`: identical TypeScript mirror.
- `frontend/src/lib/widget-builder/composition-blob-codec.ts:277-394`: `parseVariantDefinition` + variants iteration in codec. Defensive parsing built. Round-trip clean.

**Symmetry audit verdict.** Cross-side parity CLEAN — no drift across Pydantic ↔ TypeScript ↔ codec. Discriminator semantics canonical (variant_id free string in VariantDefinition; visible_in_variants restricted to canonical 4 literals in AtomNode).

**Asymmetry surfaced (not drift — substrate question for WB-8 to lock):**
- `VariantDefinition.variant_id` is `str` (free string).
- `AtomNode.visible_in_variants: List[VariantId]` is the 4-literal `["glance"|"brief"|"detail"|"deep"]` constraint.

In practice: operator-authored `variant_id` values must come from the 4-element vocabulary OR no atom can ever filter against them. The constraint is structural-soft (Pydantic doesn't enforce variant_id ∈ canonical 4 at write time) but practical-hard (any non-canonical variant_id is useless for visible_in_variants filtering). WB-8 locks whether variant_id is operator-free-text OR picker-constrained.

### 2.2 Backend validator — **MATURE**

`backend/app/services/widget_definitions/validators.py:126-147`:
- Every `atom.visible_in_variants` entry must reference a variant_id declared in `composition.variants[]` (line 128-137).
- `variant_id` uniqueness enforced within `composition.variants[]` (line 139-147).
- **NOT YET ENFORCED**: cross-surface compatibility (e.g., variant with `target_surface="focus_canvas"` requires widget's top-level `supported_surfaces` to include `focus_canvas`-equivalent). This is the Area 3 lock surface.
- **NOT YET ENFORCED**: variant_id ∈ canonical 4 strings. Operators authoring "tiny" or "expanded" would pass validation but no atom could filter against them.
- **NOT YET ENFORCED**: default_variant_id (top-level column on widget_definitions) referenced against composition.variants[].variant_id.

### 2.3 Runtime layer (ComposedWidget + AtomRenderer) — **MATURE**

`frontend/src/lib/widget-builder/runtime/ComposedWidget.tsx:68`: `variantId?: VariantId` prop on the renderer.
`frontend/src/lib/widget-builder/runtime/AtomRenderer.tsx:141-197`: `isAtomVisibleInVariant(atom, variantId)` predicate filters atoms. Three cases:
- `variantId === undefined` → all atoms render (the "catalog preview" / "unscoped render" path).
- `variantId` set AND atom has no `visible_in_variants` → atom renders in every variant (default visibility per schema doc-comment at composition-blob.ts:82).
- `variantId` set AND atom has `visible_in_variants` set → atom renders iff variantId is in the list.

Runtime is mature and consumed in production (e.g., embedded widget tests at `ComposedWidget.test.tsx` and `AtomRenderer.test.tsx` validate the three cases).

### 2.4 Persistence layer (widget_definitions table) — **PARTIAL ASYMMETRY**

`backend/app/models/widget_definition.py:102-118`:
- **`variants` (JSONB)** — top-level column (Phase W-1, April 2026 — predates WB cycle). Default `[]`. **Hand-coded widgets** populate this with Section 12.3 declarations: `{variant_id, density, grid_size, canvas_size, supported_surfaces}` (see `widget_registry.py:623-654` for the "anomalies" example).
- **`default_variant_id` (str)** — top-level column. Non-nullable. Default `"brief"`. Referenced by `spaces/crud.py:785` ("honor the widget's default_variant_id if it's…").
- **`supported_surfaces` (JSONB)** — top-level column. 7-value vocabulary: `pulse_grid`, `focus_canvas`, `focus_stack`, `spaces_pin`, `floating_tablet`, `dashboard_grid`, `peek_inline`.
- **`default_surfaces` (JSONB)** — top-level column.
- **`composition_blob.variants[]` (JSONB nested in r105)** — WB-1 substrate. Shape: `{variant_id, variant_name, target_surface, canonical_dimensions}`. 3-value `target_surface` vocabulary: `focus_canvas`, `page_canvas`, `palette_preview`.

**Two parallel variant substrates coexist**:

| Substrate | Source | Shape | Vocabulary |
|---|---|---|---|
| Top-level `variants` JSONB column | Phase W-1 (April 2026) | `{variant_id, density, grid_size, canvas_size, supported_surfaces}` | Free `variant_id` strings + `WidgetSurface` 7-value enum |
| Nested `composition_blob.variants[]` | WB-1 (May 2026) | `VariantDefinition {variant_id, variant_name, target_surface, canonical_dimensions}` | Free `variant_id` strings + `TargetSurface` 3-value enum |

**This is the largest substrate finding of the audit.** Hand-coded widgets use the top-level column; composed widgets carry the nested composition_blob list. The two are NEVER cross-referenced by code. `WidgetBuilderRecord` (frontend service shape, `widget-builder-service.ts:16-30`) exposes ONLY top-level `supported_surfaces` + `default_size`/`supported_sizes` — no top-level `variants` field surfaces in the WB admin record.

**Implication for WB-8**: the substrate question is whether WB-8's variant authoring writes to (a) the nested `composition_blob.variants[]` (canonical for composed widgets), (b) the top-level `variants` JSONB column (canonical for hand-coded widgets), or (c) both. Locked in Area 6.

### 2.5 Bridge layer (registerComposedWidgets) — **MATURE but variant-unaware**

`frontend/src/lib/widget-builder/runtime/registerComposedWidgets.ts:62-110`:
- `registerComposedWidgetMeta` registers each composed widget definition into the visual-editor metadata registry.
- The wrapped Component at line 69-75 calls `createElement(ComposedWidget, { widgetDefinition: {widget_id, composition_blob} })` — **does NOT pass `variantId`**.
- Result: composed widgets register into the Focus Builder palette WITHOUT variant scoping. Every preview renders the full unfiltered atom set (because `variantId === undefined` → all atoms visible per AtomRenderer.tsx:158).

**Implication for WB-8**: the bridge layer needs to learn about a default variant. When a Focus Builder consumer drops a composed widget at a Focus, the runtime needs to know which variant to render. Either (a) the consumer passes variantId, (b) the bridge reads `composition_blob.variants[0]` as default, or (c) the bridge consults a new top-level `default_variant_id` field stored in composition_blob (which does NOT yet exist). Locked in Area 6.

### 2.6 Admin authoring layer — **MISSING (zero substrate)**

Comprehensive grep across `frontend/src/bridgeable-admin/`:

```
grep -rn "visible_in_variants\|VariantDefinition\|target_surface\|canonical_dimensions" \
  frontend/src/bridgeable-admin/  →  ZERO HITS
```

The 32 `variant` matches in `AtomInspectorDispatch.tsx` are atom-config variants (typography variant, button variant, status badge variant) — NOT widget-level variants. These belong to per-atom config and were locked by WB-4b.

**Verdict**: variant authoring is **entirely dormant** at the admin authoring layer. Schema present; runtime works; admin UI surface ABSENT. This is the WB-8 scope.

### 2.7 Maturity summary (per consumer)

| Consumer | Maturity | Notes |
|---|---|---|
| Pydantic schema | **Mature** | `VariantDefinition` + `VariantId` + `TargetSurface` + `visible_in_variants` |
| TypeScript mirror | **Mature** | Clean cross-side parity; codec defensive parsing |
| Backend validator | **Mature** | Integrity checks (ref + uniqueness); cross-surface compatibility absent |
| Runtime renderer | **Mature** | `variantId` prop wired; `isAtomVisibleInVariant` filter live |
| Persistence (composition_blob.variants[]) | **Built-but-dormant** | Schema landed; ALL existing composed widgets ship `variants: []` empty (publish.py:97) |
| Persistence (top-level variants column) | **Mature for hand-coded** | Hand-coded widgets populate; composed widgets do NOT |
| registerComposedWidgets bridge | **Mature but variant-unaware** | Does NOT pass variantId — all atoms render in palette |
| Admin authoring UI | **MISSING** | Zero substrate. WB-8 scope. |
| default_variant_id column | **Built but composition-decoupled** | Top-level column referenced by spaces/crud.py:785; composition_blob has no equivalent |
| Cross-surface compatibility validation | **MISSING** | Variant `target_surface` and widget `supported_surfaces` never cross-checked |

### 2.8 Process canon candidate surfaced

The "two parallel variant substrates" finding (top-level `variants` column from Phase W-1 + nested `composition_blob.variants[]` from WB-1) is a class of bug worth flagging at the canon level. The two substrates landed in different arcs and were never reconciled. WB-1's authors did NOT audit the existing top-level column for shape/use compatibility before introducing the nested list. Process canon candidate: **when a substrate-extending arc introduces fields with names that collide with existing fields elsewhere on the same row, the investigation must enumerate the existing field, audit usage, and either retire the legacy field, alias the new field, or document the parallel-substrate coexistence rule.** NOT FILED — appended to the ~20+ accumulated canon candidates for end-of-cycle canon-update arc.

---

## 3. Area 2 — Variant authoring UX lock

**At stake**: Where does variant authoring live in the WB admin shell? What primitives surface CRUD operations? How does the operator switch variants? How is per-atom visibility authored? Does target_surface get a picker? Does canonical_dimensions get configured? How is default variant designated?

### 3.1 Alternatives enumerated

**Option A — Inspector-section-only**. Variant CRUD lives entirely in the right-rail inspector. When the widget root is selected, the inspector shows a "Variants" section listing the four canonical variants (each a row with checkbox + variant_name input + target_surface dropdown + canonical_dimensions inputs). When an atom is selected, the inspector shows an "Atom visibility" section with 4 checkboxes (one per variant the widget declares).

- Pros: composes naturally with WB-4b's `AtomInspectorDispatch` + WB-7's per-atom action inspector. Single mental model — "everything atom-level is in the inspector." No new pane.
- Cons: variants list buried beneath atom-level inspector when an atom is selected — operator can't see the variant set without deselecting. Variant switching (preview which variant renders) requires a separate control.

**Option B — Top-bar variant switcher + inspector-section**. The canvas top bar gains a variant switcher (segmented control: Glance / Brief / Detail / Deep). Switching the active variant filters the canvas to that variant's atom subset (live preview). Variant CRUD (which variants exist, target_surface, canonical_dimensions) lives in a new modal or in the widget-root inspector section. Per-atom `visible_in_variants` lives in the atom inspector.

- Pros: variant switching is canonical pattern (matches Figma's frame-variant switcher, Sketch's symbol-variants); operator can switch variants while authoring atoms. Live preview of variant subset.
- Cons: two surfaces for variant authoring (top-bar switcher + inspector-section CRUD). Variants list needs UI consistency between the switcher and the CRUD surface.

**Option C — Dedicated "Variants" tab in inspector**. Inspector becomes tabbed: existing tabs (Atom / Widget root) plus new "Variants" tab. Variants tab lists all variants with full CRUD inline. Per-atom `visible_in_variants` stays in the per-atom inspector. Variant switching is a separate top-bar control.

- Pros: clear separation — Variants tab is the one place to manage the widget's variant set. Atom inspector remains focused on atom config.
- Cons: introduces tab navigation pattern not yet used in WB; tabs add UI weight. Switching active variant for preview is decoupled from the CRUD surface.

### 3.2 Lock 2a — Option B (top-bar variant switcher + inspector-section CRUD)

**LOCKED: Option B**.

**Reasoning**:

1. **Live preview is the dominant operator activity.** When authoring per-atom visibility (the largest variant authoring activity by interaction count), operators want to see immediate feedback — "if I uncheck Detail for this atom, does the Detail variant still look right?" A top-bar switcher enables one-click preview switching while authoring atoms in the inspector. Options A and C decouple switching from authoring.

2. **WB-5 canvas preview substrate is ready.** WB-5 ships canvas preview wiring with real saved-view data. WB-5 explicitly noted (`docs/investigations/2026-05-23-widget-builder-canvas-preview.md:435-446`): "WB-5's fetch is keyed on `saved_view_id`, NOT on `variantId`. Variant changes don't trigger refetch." This means the top-bar variant switcher is **substrate-free** for the data side — fetched data stays cached; only the AtomRenderer's variant filter changes. Implementing the switcher is a UI-only change passing variantId into ComposedWidget.

3. **CRUD belongs in the widget-root inspector.** The "what variants does this widget support" decision is widget-level state, not atom-level. The widget-root inspector (selected when no atom is selected per WB-4b) is the natural home. This composes with WB-7's planned widget-root inspector extensions (data source picker, iteration scope).

4. **Per-atom visibility belongs in atom inspector.** Each atom carries its `visible_in_variants` array — atom-level state authored in the atom inspector. A multi-select chip group ("Visible in: Glance · Brief · Detail · Deep") fits naturally in the inspector body.

5. **Alternative C tab pattern under-utilized.** WB introduces no other tab pattern in the inspector. Inventing one for variants adds learning surface. Top-bar switcher + inspector-section CRUD matches existing WB conventions.

**Sub-decisions inside Lock 2a**:

- **Lock 2a.1 — variant_id is picker-constrained, NOT free-text.** Operator picks variant_id from the 4-string canonical vocabulary. Variant CRUD UI surfaces 4 fixed rows (Glance / Brief / Detail / Deep); operator toggles "declare this variant" per row. variant_name is free-text (per-row label override; defaults to canonical name). Rationale: the substrate-soft / practical-hard constraint surfaced in §2.1 — non-canonical variant_id values are useless for `visible_in_variants` filtering. Forcing the 4-canonical vocabulary at the picker prevents authoring dead-end variants.

- **Lock 2a.2 — target_surface picker is constrained to TargetSurface 3-value vocabulary.** Each variant row in the CRUD surface shows a target_surface dropdown with 3 options: `focus_canvas`, `page_canvas`, `palette_preview`. Default `focus_canvas` (the most common case per FF series substrate). Operator-validation-sensitive (tag) — staging may surface that operators want surface-vocabulary expansion (e.g., explicit `dashboard_grid` / `spaces_pin` mapping). See Area 6 for default-variant + cross-vocabulary mapping.

- **Lock 2a.3 — canonical_dimensions is two number inputs (width / height) with surface-default fallback.** When omitted, WB-5 canvas falls back to surface-default dimensions (per FF-2 canon — focus_canvas defaults to 1200×800; page_canvas + palette_preview need surface-default constants). Operator can override per-variant for precise targeting.

- **Lock 2a.4 — Default variant designation is a "Default" toggle/radio on the variant row.** Exactly one variant carries `is_default=true` at any moment. This becomes the variant the bridge layer uses when consumers do not pass `variantId` (e.g., Focus Builder palette preview). Stored as a new top-level field in `CompositionBlob` (`default_variant_id: str | null`) — see Area 6 + Area 7 for schema implications.

- **Lock 2a.5 — Per-atom `visible_in_variants` is a chip-toggle group in the atom inspector.** Group of 4 chips (Glance / Brief / Detail / Deep) under "Visible in variants" header in atom inspector body. Multi-select. Empty selection means "visible in ALL variants the widget supports" (matches schema default-visibility semantics at composition-blob.ts:82). The "All variants" sentinel state is shown when the chip group has zero selections — UI distinguishes "no variant declared yet (default-all)" from "explicit empty (hidden in all)" via different chip styling.

- **Lock 2a.6 — Variant CRUD section is widget-root-inspector ONLY** (collapsed by default; expandable). The expansion state persists in component state (not LocalStorage) — the section opens with at least the canonical 4 rows visible when expanded.

- **Lock 2a.7 — Top-bar variant switcher is a segmented control** matching the existing WB top-bar element treatment (per WidgetBuilderPage.tsx:381 already uses `variant="secondary"` for canvas-root chrome controls). 4 segments (one per canonical variant); only declared variants are enabled (others greyed-out + non-clickable). Active variant is highlighted with the WB accent token. Special "All atoms" pseudo-variant is the LEFTMOST segment showing the unfiltered view (matches `variantId === undefined` runtime behavior).

**Tagged operator-validation-sensitive**: Lock 2a.1 (picker-constrained variant_id), Lock 2a.2 (target_surface 3-value enum), Lock 2a.7 (the segmented control affordance).

---

## 4. Area 3 — Cross-surface compatibility validation lock

**At stake**: A widget declares `supported_surfaces` (top-level: `pulse_grid`, `spaces_pin`, etc.) and `composition_blob.variants[].target_surface` (per-variant: `focus_canvas` / `page_canvas` / `palette_preview`). When and how does the system validate compatibility?

### 4.1 The vocabulary asymmetry

The two surface vocabularies do not map 1:1:

| Top-level `supported_surfaces` (`WidgetSurface`, 7) | Composition `target_surface` (`TargetSurface`, 3) |
|---|---|
| `pulse_grid` | (no direct mapping) |
| `focus_canvas` | `focus_canvas` (direct) |
| `focus_stack` | (no direct mapping) |
| `spaces_pin` | (no direct mapping) |
| `floating_tablet` | (no direct mapping) |
| `dashboard_grid` | (no direct mapping) |
| `peek_inline` | (no direct mapping) |
| (no direct mapping) | `page_canvas` |
| (no direct mapping) | `palette_preview` |

Only `focus_canvas` exists in both vocabularies. The two were authored independently — `WidgetSurface` for Phase W-1 (April 2026), `TargetSurface` for WB-1 composition substrate (May 2026).

### 4.2 Alternatives enumerated

**Option A — Publish-time hard validation.** Validator (publish.py) enforces: every `composition_blob.variants[].target_surface` must map to at least one `supported_surfaces` entry. Mismatch raises HTTP 422 on Publish. Operator sees error banner; must declare additional supported_surfaces or remove variants.

- Pros: catches mismatch before tenant render path is ever exercised. Mature substrate pattern (matches WB-1's composition_blob shape validation).
- Cons: introduces vocabulary-mapping logic that didn't exist before. Requires authoritative mapping (e.g., `focus_canvas` ↔ `focus_canvas`; `page_canvas` ↔ `dashboard_grid` + `pulse_grid` + `peek_inline`?; `palette_preview` ↔ ALL surfaces or NONE?). Authoring-time errors against draft are hard if Publish is the gate (operator only sees the error on Publish — fixed in 4b).

**Option B — Authoring-time soft warning.** Variant CRUD surface inspects compatibility per-variant and shows a warning chip on each variant row that mismatches supported_surfaces. Operator can save anyway; Publish does not block.

- Pros: low-friction. Operator gets feedback at edit time. No vocabulary-mapping enforcement.
- Cons: silent failures at tenant render — a variant authored against `page_canvas` may render correctly on `pulse_grid` due to fallback paths (or may not). Operators can ignore warnings.

**Option C — Variant-time strict validation in CRUD surface.** When operator picks `target_surface` in the variant row, the dropdown is constrained to surfaces compatible with the widget's declared `supported_surfaces`. No invalid declaration is possible.

- Pros: strongest enforcement; no error states to handle. Composition-blob always passes compatibility at write time.
- Cons: surface mapping must be declared in code (a new constant table). `target_surface` becomes derived state — operator authors `supported_surfaces` first, then picks `target_surface` from a filtered list. Vocabularies are inverted in the operator mental model.

### 4.3 Lock 3a — Hybrid: authoring-time warning + Publish-time enforcement (Option A + B)

**LOCKED: hybrid (Option B at draft-save + Option A at Publish)**.

**Reasoning**:

1. **WB-4a's draft-then-publish model fits hybrid.** WB-4a's authoring flow is "auto-save draft; explicit Publish promotes to `published_composition_blob`." This naturally accommodates two validation tiers: soft at draft (warning visible in inspector but draft accepts), strict at Publish (blocking error).

2. **Operator never gets silent tenant-render failure.** Publish is the gate; mismatch can't reach tenant render path without operator seeing the error.

3. **Authoring stays low-friction.** Operator can experiment with target_surface declarations without fighting validation. Warning chip surfaces the mismatch; Publish enforces.

4. **Cross-vocabulary mapping is a substrate decision, not a UX decision.** The mapping table (`target_surface` → `WidgetSurface` set) becomes a new constant module at `backend/app/services/widget_definitions/surface_mapping.py` with frontend mirror. Locked content of the mapping:
   - `focus_canvas` ↔ {`focus_canvas`, `focus_stack`} (focus surfaces; stack is mobile shape of canvas)
   - `page_canvas` ↔ {`pulse_grid`, `dashboard_grid`} (page-level grid surfaces)
   - `palette_preview` ↔ ALL (preview surface is unscoped — Focus Builder palette + WB canvas preview)
   - `spaces_pin` and `peek_inline` and `floating_tablet` — NO `target_surface` declaration needed (Glance-only / chrome-stripped — handled via per-atom `visible_in_variants` + variant_id="glance" convention). Documented as the rendering rule, not enforced by variant authoring.

5. **Compatibility matrix lives in a single source of truth.** The mapping table is the canonical source; backend validator references it; frontend warning logic references the mirror. Per WB-1 cross-side canon: same shape on both sides.

**Sub-decisions inside Lock 3a**:

- **Lock 3a.1 — Mapping table is constant + non-extensible at Phase 1.** Vocabulary-extension is a separate arc.
- **Lock 3a.2 — `spaces_pin` is the only surface where the "Glance variant required" rule applies** (per original WB Q-23 lock). Codified in validator: when widget's `supported_surfaces` includes `spaces_pin`, `composition_blob.variants[]` MUST contain a variant with `variant_id="glance"`. Publish-time check; authoring-time warning. Mismatch on `spaces_pin`-supporting widgets without Glance variant blocks Publish.
- **Lock 3a.3 — `focus_canvas` surface support requires at least Brief variant** (per original Q-23). Codified in validator. Soft warning at draft; blocking error at Publish.

**Tagged operator-validation-sensitive**: Lock 3a.2 + 3a.3 (the per-surface variant requirement rules) — staging may surface that operators reach for Detail-without-Brief or Glance-without-Brief patterns we didn't anticipate.

---

## 5. Area 4 — Variant-scoped bindings + actions lock

**At stake**: Bindings (WB-6) and actions (WB-7) are atom-level. Variants filter atoms by visibility. Can the same atom carry DIFFERENT bindings or actions per variant? The original WB investigation deferred "variant-specific binding overrides" to Phase 2 (`docs/investigations/2026-05-22-widget-builder-bindings.md:606`). WB-7 (`docs/investigations/2026-05-24-widget-builder-button-actions.md:875`) locked "one action_config per button atom" with variant-scoped patterns handled by authoring duplicate atoms with different `visible_in_variants`. The WB-8 substrate question: ratify the deferral OR open the variant-scoped binding/action surface.

### 5.1 Alternatives enumerated

**Option A — Widget-scoped bindings + actions (status quo: ratify WB-6/7 locks).** The atom carries ONE BindingRef + ONE ActionRef. Variants filter atom visibility. Authors who want per-variant bindings duplicate atoms with different `visible_in_variants`.

- Pros: zero substrate change. WB-6 binding_refs + WB-7 action_config carry unchanged. Operator authoring path is "create the atom that shows in Brief; duplicate + retarget for Detail."
- Cons: duplicate-atom pattern creates implicit coupling — two atoms representing "one logical thing displayed differently per variant" are not linked structurally. Renaming a field in one variant doesn't auto-update the other.

**Option B — Variant-scoped bindings + actions.** AtomNode gains `bindings_per_variant: Record<VariantId, Record<string, BindingRef>>` and similar for actions. Resolution at render time looks up per-variant; falls back to atom-default if no per-variant entry.

- Pros: one atom represents one logical element rendered N ways. No duplicate-atom pattern. Renaming + restructuring carries across variants natively.
- Cons: substrate expansion (new BindingRef table per variant on EVERY atom; action shape similar). WB-6 binding picker UI needs variant-switcher; WB-7 action picker needs variant-switcher. Authoring complexity grows.

**Option C — Hybrid: widget-scoped by default, variant overrides as deltas.** AtomNode carries `binding_refs` + `action_config` (atom-level defaults). Optional `binding_refs_per_variant: Record<VariantId, Partial<Record<string, BindingRef>>>` carries per-variant overrides — keys not declared in the per-variant override fall through to the atom-level default. Similarly for actions.

- Pros: composability — default carries naturally; per-variant deltas are explicit. Matches the "deltas" pattern from focus_compositions per DECISIONS entry 19 ("Variant overrides as deltas").
- Cons: substrate complexity (resolution logic for "fall through to default if not in delta"). UX complexity (the picker UI surfaces deltas; mental model is "default + N deltas").

### 5.2 Three alternatives weighed

| Criterion | Option A (status quo) | Option B (per-variant) | Option C (hybrid deltas) |
|---|---|---|---|
| Substrate change at WB-8 | ZERO | LARGE (4 new schema fields per atom) | MEDIUM (1 optional schema field per atom for bindings; 1 for actions) |
| Backward compat with shipped WB-6 + WB-7 | CLEAN | breaks existing binding picker UI | preserves picker UI; adds delta affordance |
| Operator mental model | "one atom = one logical element; variants filter visibility; duplicate to override" | "one atom = N representations across variants" | "default + per-variant deltas" |
| Authoring complexity | LOW (no new UX) | HIGH (variant-switcher in EVERY picker) | MEDIUM (delta picker affordance only when operator opts in) |
| Use case coverage for September demo | Adequate (Glance/Brief/Detail/Deep narrative does NOT require per-variant binding changes) | Over-spec | Adequate; deltas add headroom |
| Operator validation feedback loop | Operators can request Option B/C if duplicate-atom pattern proves painful | N/A | Same as Option A — operators can request more if needed |

### 5.3 Lock 4a — Option A (ratify status quo: widget-scoped bindings + actions)

**LOCKED: Option A**.

**Reasoning**:

1. **Substrate-minimal honors the WB-cycle-closing scope.** WB-8 is the closer. The cycle established a coherent substrate; introducing per-variant deltas at WB-8 (Option C) or full per-variant surface (Option B) re-opens binding picker and action picker substrate that WB-6 and WB-7 just closed. The cost-benefit is wrong for the closing arc.

2. **WB-7 already locked the duplicate-atom pattern as the variant-scoped answer.** Per `docs/investigations/2026-05-24-widget-builder-button-actions.md:875`: "A button atom in variant glance fires the same action as the same button atom in variant deep — different buttons would be authored as separate atoms with different visible_in_variants." Ratifying this lock at WB-8 keeps cycle coherence.

3. **Demo coverage adequate.** The September Wilbert demo's "same widget different surfaces" narrative is satisfied by atom-visibility filtering. No demo scenario surfaced in the original WB or BRIDGEABLE_MASTER docs requires per-variant binding changes.

4. **Operator-validation gate.** If post-staging operator feedback surfaces "I keep duplicating atoms with identical bindings just to flip visibility — I want one atom with per-variant binding overrides," Option C is the natural extension. Lock 4a is tagged operator-validation-sensitive (per DECISIONS entry 35).

5. **Option C is the planned extension shape** for Phase 2 if needed. The "deltas" pattern aligns with focus_compositions canon (DECISIONS entry 19). Locking now would over-spec the substrate ahead of validation signal.

**Sub-decisions inside Lock 4a**:

- **Lock 4a.1 — Variant authoring documentation surfaces the duplicate-atom pattern** as the canonical recipe for "different binding/action per variant." Inline tooltip in the variant CRUD section: "To show different data per variant, duplicate the atom and set different `Visible in variants`."

- **Lock 4a.2 — No new schema fields for per-variant binding/action overrides.** `BindingRef` and `ActionRef` shapes unchanged. Validator extends only for variant references already covered in §2.2.

**Tagged operator-validation-sensitive**: Lock 4a (the choice to defer Option C). Post-staging operator feedback is the eventual arbiter.

---

## 6. Area 5 — Variant preview substrate lock

**At stake**: How does the canvas preview interact with variant switching? Does in-flight WB-5 fetch state survive variant switches? How does cross-surface preview honor `canonical_dimensions`? How does the WB-5 three-flavor `dataContext` discriminator interact with variant filtering?

### 6.1 WB-5 substrate inheritance

WB-5 shipped canvas preview wiring (`docs/investigations/2026-05-23-widget-builder-canvas-preview.md`). Key locks inherited:
- Fetch keyed on `saved_view_id`, NOT `variantId` (Lock 9.3 / 10.3): variant switching does NOT trigger refetch.
- AtomRenderer iterates `dataContext` per WB-6 substrate.
- Error chrome per-atom (Lock 4a); hidden atoms render `null` (AtomRenderer.tsx:158) — error chrome on hidden atoms does NOT surface.

These substrate locks are load-bearing for WB-8. The natural fit: variant switching is a UI-only state change passing a different `variantId` prop into ComposedWidget. Data layer unaffected.

### 6.2 Alternatives for in-flight switching

**Option A — Switching during in-flight fetch cancels the fetch.** Per-saved-view AbortController cancels on variant switch.

- Pros: explicit cancellation; no stale data lands in the new variant view.
- Cons: WB-5 already locked "fetch keyed on saved_view_id" — variant switch keeps the same key. Cancelling on variant switch contradicts WB-5 substrate.

**Option B — Switching during in-flight fetch leaves fetch running.** AtomRenderer's variant filter applies post-fetch; the same fetch result feeds whichever variant is active.

- Pros: substrate-aligned with WB-5. Zero data-layer code change.
- Cons: operator may see brief "fetching" state on switch if fetch was in-flight; explained by canvas-level Fetching pill.

### 6.3 Lock 5a — Option B (variant switching is data-layer-passive)

**LOCKED: Option B**.

**Reasoning**:
1. WB-5 substrate is mature; variant switching composes naturally without re-architecting fetch logic.
2. Operator mental model: "switching variants changes which atoms render, not which data feeds them." Matches the canonical case (Glance and Brief show the same data, different presentation).
3. Zero new substrate.

### 6.4 Cross-surface preview honoring `canonical_dimensions`

The canvas preview surface (WB-5) renders inside a single canvas frame. When the operator switches to a variant with `canonical_dimensions={width:280, height:120}` (e.g., Glance for spaces_pin sidebar), the preview should constrain the render box to those dimensions.

**Lock 5b — Canvas preview honors canonical_dimensions of the active variant.** When the active variant has `canonical_dimensions` set, the ComposedWidget preview wrapper applies a CSS frame at those exact pixel dimensions. When `canonical_dimensions` is null/undefined, the wrapper falls back to surface-default dimensions per Lock 3a's mapping table:
- `focus_canvas` → 800×600 default
- `page_canvas` → 480×320 default
- `palette_preview` → 320×240 default

The "All atoms" pseudo-variant (per Lock 2a.7) renders the canvas at WB-5's existing canvas size (1200×800 from FF-2 substrate).

### 6.5 WB-5 three-flavor `dataContext` discriminator interaction

WB-5 introduced three flavors of `dataContext` (per `docs/investigations/2026-05-23-widget-builder-canvas-preview.md` Risk R4):
- `undefined` (no bindings / pre-fetch / canvas just mounted)
- success (fetched data successfully)
- `__error` discriminator (fetch failed)

Variant switching does NOT change the `dataContext` flavor. The same flavor feeds whichever variant is active. Hidden atoms (filtered by visible_in_variants) render null per AtomRenderer.tsx:158 — no error chrome for hidden atoms (already locked in WB-5 Lock 4a; preserved).

**Lock 5c — Variant filtering happens AFTER dataContext flavor handling**, NOT before. The atom rendering pipeline is:
1. AtomRenderer receives atom + dataContext.
2. Check `isAtomVisibleInVariant(atom, variantId)` — return null if hidden.
3. (visible) Resolve bindings against dataContext; surface error chrome if dataContext is `__error` flavor.
4. (visible + data resolved) Render atom with resolved values.

This ordering is already in place in AtomRenderer.tsx:194-197. No code change required at WB-8 — this lock documents the canonical ordering for future arcs.

**Tagged operator-validation-sensitive**: Lock 5b (canonical_dimensions fallback values) — staging may surface that operators want explicit overrides per surface OR that the fallback dimensions don't match real spaces_pin / dashboard_grid render boxes.

---

## 7. Area 6 — registerComposedWidgets bridge variant handling lock

**At stake**: When a Focus Builder consumer drops a composed widget at a Focus, the runtime needs to know which variant to render. Currently the bridge does NOT pass `variantId` — every consumer renders the unfiltered "all atoms" view. Three substrate questions:
(a) Default variant for Focus Builder palette preview.
(b) Default variant for Pulse render / Spaces render / dashboard render.
(c) Forward-compat with Page Builder (which doesn't exist yet but is the next canvas substrate per DECISIONS entry 22).

### 7.1 Default variant designation — schema decision

The current `CompositionBlob` shape does NOT carry a default-variant field. The TOP-LEVEL `widget_definitions.default_variant_id` column exists (Phase W-1) but is NOT cross-referenced from composition_blob.

**Lock 6a — CompositionBlob gains a NEW field `default_variant_id: str | null`.** Mirrors the top-level column name for consistency. Stores the variant_id (from composition.variants[].variant_id) that consumers should render when no explicit variantId is passed. Backend validator enforces: when set, `default_variant_id` must reference an existing variant_id in composition.variants[].

**Schema delta**:
```python
# backend/app/schemas/widget_composition.py
class CompositionBlob(BaseModel):
    schema_version: Literal[1]
    root_atom_id: str
    atom_tree: Dict[str, AtomNode]
    variants: List[VariantDefinition] = Field(default_factory=list)
    bindings_catalog: Dict[str, BindingRef] = Field(default_factory=dict)
    default_variant_id: Optional[str] = None  # NEW
```

```typescript
// frontend/src/lib/widget-builder/types/composition-blob.ts
export interface CompositionBlob {
  schema_version: 1;
  root_atom_id: string;
  atom_tree: Record<string, AtomNode>;
  variants: VariantDefinition[];
  bindings_catalog: Record<string, BindingRef>;
  default_variant_id?: string | null;  // NEW
}
```

This is a **schema_version=1 additive field** — old composition_blobs (where the field is absent) treat as `undefined` and consumers fall through to either (a) `variants[0]` (the first declared variant), or (b) the static fallback `"brief"` (matching the top-level column default). Lock 7a in §8 covers backfill behavior.

### 7.2 Bridge layer variant routing

`registerComposedWidgets.ts:65-110` currently calls `createElement(ComposedWidget, { widgetDefinition: ... })` without `variantId`. The bridge needs to pass a variantId derived from either:
- The widget's `composition_blob.default_variant_id` (new field per Lock 6a).
- The consumer's explicit variantId prop (if the consumer knows the surface).
- A computed default derived from the rendering surface.

**Lock 6b — Bridge layer passes `default_variant_id` to ComposedWidget when no consumer-provided variantId.** The Component wrapped by `registerComposedWidgetMeta` becomes:

```typescript
const Component: ComponentType<{ variantId?: VariantId }> = (props) => {
  const blob = defn.composition_blob as CompositionBlob | null
  const effectiveVariantId =
    props.variantId
    ?? blob?.default_variant_id
    ?? blob?.variants?.[0]?.variant_id
    ?? undefined  // falls back to "all atoms" behavior
  return createElement(ComposedWidget, {
    widgetDefinition: { widget_id: slug, composition_blob: defn.composition_blob },
    variantId: effectiveVariantId as VariantId | undefined,
  })
}
```

This change is a 5-line edit to registerComposedWidgets.ts. Backward-compat: composed widgets without `default_variant_id` field continue rendering the unfiltered view (same as today).

### 7.3 Focus Builder palette preview

Focus Builder palette renders composed widgets as palette items. Per the current registerComposedWidgets behavior, palette items render unfiltered (all atoms). With Lock 6b, palette items render the `default_variant_id` variant.

**Lock 6c — Focus Builder palette renders the widget's `default_variant_id` variant.** This is the natural rendering shape — the palette preview shows what the operator will see when dropping the widget at the default surface. Page Builder (when it ships) inherits the same default behavior.

### 7.4 Page Builder forward-compat

Page Builder doesn't exist yet but is the next canvas substrate per DECISIONS entry 22. The likely consumer pattern: PageBuilder canvas renders composed widgets at the `page_canvas` target_surface. WB-8's variant authoring would surface a variant with `target_surface="page_canvas"` for widgets targeting Page Builder.

**Lock 6d — Page Builder forward-compat: passing variantId explicitly is the canonical consumer pattern.** Future Page Builder will pass `variantId` derived from "the variant whose target_surface matches my canvas." If multiple variants match the surface, the consumer picks by order in composition.variants[] (deterministic). Documented as forward guidance; no Page Builder substrate built in WB-8.

**Tagged operator-validation-sensitive**: Lock 6b's fallback chain (`default_variant_id` → `variants[0]` → undefined). Staging may surface that operators want explicit per-consumer defaults.

---

## 8. Area 7 — Cross-substrate dependency enumeration

WB-8 sub-arc dispatches against:

| Substrate | Source | Used for |
|---|---|---|
| `CompositionBlob` schema (Pydantic + TS) | WB-1 (r105) | Schema + codec + validator |
| `VariantDefinition` shape | WB-1 | Variant CRUD authoring + canvas dimensions |
| `AtomNode.visible_in_variants` | WB-1 | Per-atom visibility filter; chip-toggle inspector |
| `widget_definitions.variants` column (top-level) | Phase W-1 | NOT consumed by WB-8 (hand-coded widget substrate) |
| `widget_definitions.default_variant_id` column (top-level) | Phase W-1 | Aligned with NEW composition_blob.default_variant_id (Lock 6a) — possible sync rule deferred |
| `widget_definitions.supported_surfaces` column (top-level) | Phase W-1 | Read by Lock 3a cross-surface compatibility validation |
| Backend validator | WB-1 | Extends with cross-surface compatibility (Lock 3a) + default_variant_id integrity (Lock 6a) + spaces_pin Glance requirement (Lock 3a.2) + focus_canvas Brief requirement (Lock 3a.3) |
| `ComposedWidget.variantId` prop | WB-2 | Passed by registerComposedWidgets bridge (Lock 6b) |
| `AtomRenderer.isAtomVisibleInVariant` | WB-2 | Already filters; no change |
| `WidgetCanvas` (admin) | WB-4a | Receives variantId from top-bar variant switcher; passes through to ComposedWidget |
| `WidgetBuilderPage` (admin shell) | WB-4a | Mounts top-bar variant switcher |
| `AtomInspectorDispatch` | WB-4b | Gains chip-toggle group for per-atom `visible_in_variants` |
| Widget-root inspector section | WB-4b | Gains Variant CRUD section + default-variant designation |
| `useCanvasPreviewData` | WB-5 | Unchanged — variant changes do NOT trigger refetch |
| `useBindingPicker` | WB-6 | Unchanged — bindings remain widget-scoped (Lock 4a) |
| `useActionPicker` | WB-7 | Unchanged — actions remain atom-scoped (Lock 4a) |
| `registerComposedWidgets` | WB-3 | Extended with effective-variantId resolution (Lock 6b) |
| `widget-builder-service.ts` | WB-4a | Unchanged — composition_blob shape change is additive and codec-handled |
| `visual-editor` registry | Cross-arc | Unchanged — variant authoring lives in widget-builder admin only |
| `composition-blob-codec` (TypeScript) | WB-1 | Extended for `default_variant_id` parsing |

**No coupling to**:
- Spaces substrate beyond reading the existing `default_variant_id` top-level column (no Spaces canvas changes).
- Focus Builder substrate beyond the registerComposedWidgets bridge change (no FocusBuilderPage changes — palette already calls registerComposedWidgets-derived components).
- WB-7 action substrate (Lock 4a ratifies widget-scoped actions).
- WB-6 binding substrate (Lock 4a ratifies widget-scoped bindings).

---

## 9. Area 8 — Phase 1 scope boundaries

### 9.1 Ships in WB-8 Phase 1

1. **Top-bar variant switcher** in WB canvas (segmented control: All Atoms / Glance / Brief / Detail / Deep). Active variant filters canvas preview via `variantId` prop into ComposedWidget. Only declared variants enabled; others greyed out.
2. **Widget-root inspector "Variants" section** with CRUD over 4 canonical variant rows (Glance / Brief / Detail / Deep). Each row carries: declare-toggle, variant_name (overrideable, defaults to canonical name), target_surface dropdown (3-value enum), canonical_dimensions (2 number inputs), default-variant radio.
3. **Per-atom inspector "Visible in variants" chip-toggle group** (4 chips: Glance / Brief / Detail / Deep). Multi-select. Empty selection = "all variants the widget supports" (default-all sentinel).
4. **`default_variant_id` field** added to CompositionBlob (Pydantic + TS + codec) (Lock 6a).
5. **Cross-surface compatibility mapping table** at `backend/app/services/widget_definitions/surface_mapping.py` + frontend mirror at `frontend/src/lib/widget-builder/types/surface-mapping.ts` (Lock 3a).
6. **Validator extensions** (Lock 3a + Lock 6a):
   - Cross-surface compatibility check (variants[].target_surface ↔ widget.supported_surfaces).
   - `spaces_pin` requires Glance variant.
   - `focus_canvas` requires Brief variant.
   - `default_variant_id` references an existing variant_id.
7. **Authoring-time warning chips** on variant CRUD rows whose target_surface is incompatible with widget.supported_surfaces (Lock 3a Option B at draft).
8. **Publish-time blocking errors** for the same incompatibility (Lock 3a Option A at Publish).
9. **registerComposedWidgets bridge extension** to pass `default_variant_id` through to ComposedWidget (Lock 6b).
10. **Canvas preview honors canonical_dimensions** with surface-default fallback (Lock 5b).
11. **Source-shape regression test gates** per DECISIONS entry 31 for: top-bar switcher mount in WidgetBuilderPage; chip-toggle group in AtomInspectorDispatch; Variant CRUD section in widget-root inspector; default_variant_id codec round-trip.
12. **Playwright `.skip` scenarios** for staging activation when seed data lands (per WB-5 / WB-6 / WB-7 precedent).

### 9.2 Defers to post-WB-8 (Phase 2 / Phase 3 / canon-update arc)

- **Per-variant binding overrides (Option C from Lock 4a)** — deferred pending operator-validation feedback.
- **Per-variant action overrides** — same as bindings.
- **Per-variant chrome overrides (chrome_per_variant from original WB Q-10 secondary lock)** — deferred. Widget-root chrome carries one shape per widget; variants don't customize chrome at Phase 1.
- **Glance variant compactness soft warning (original WB Q-22 lock)** — deferred. The "Glance variant cannot have > 3 atoms" warning was a UX nice-to-have; not load-bearing for demo.
- **Per-variant icon (variant_icon for variant CRUD rows)** — deferred. Operator sees variant_name as the identifier.
- **Custom variant_id beyond canonical 4** — deferred indefinitely. Lock 2a.1 forces canonical 4; extending requires a separate arc with vocabulary expansion.
- **Top-level `variants` column ↔ composition_blob.variants[] reconciliation** — DEFERRED to a canon-update arc. The two substrates coexist; WB-8 doesn't unify them. Hand-coded widgets use top-level; composed widgets use nested; the two never cross-reference.
- **Seed composed widgets demonstrating 4-variant taxonomy** (original WB Q-WB-cycle finale) — separate seed script work post-WB-8.
- **Spaces / Pulse render path consuming default_variant_id from composition_blob** — Lock 6b lands the bridge; Spaces render path consumes the bridge-resolved component. No Spaces-side substrate change in WB-8 because Spaces calls registered components, not composition_blob directly.

### 9.3 Explicitly NOT in scope

- Page Builder canvas. Doesn't exist yet. Lock 6d documents forward-compat guidance only.
- Multi-operator collaborative variant authoring.
- Variant copy/clone affordances (e.g., "duplicate Brief variant as Detail starting point"). Operators author from scratch per variant.
- Variant-level audit log beyond what r105's session-aware versioning already captures.

---

## 10. Area 9 — Architectural risks + mitigations

**R1 — Two parallel variant substrates (top-level column + composition_blob.variants[]) coexist without reconciliation.** Operators authoring composed widgets via WB write only to composition_blob; hand-coded widgets read only top-level column. Risk: drift between the two (e.g., a composed widget's nested default_variant_id differs from its top-level default_variant_id column).

- **Mitigation**: WB-8 ships the publish.py contract treating `default_variant_id` as composition_blob-only for composed widgets. Top-level column stays the source of truth for hand-coded. Documented in CLAUDE.md candidates list. WB cycle does NOT unify; canon-update arc considers the reconciliation. **Severity: Medium**.

**R2 — Cross-surface vocabulary asymmetry (WidgetSurface 7-value vs TargetSurface 3-value).** Mapping table at Lock 3a covers known cases but operators may compose surface combinations the table doesn't anticipate.

- **Mitigation**: mapping table is a code-level constant; expansion via a separate arc when staging surfaces a gap. Phase 1 mapping covers the canonical cases (focus surfaces, page surfaces, preview); Glance-only surfaces (`spaces_pin`, `peek_inline`, `floating_tablet`) handled via variant_id="glance" convention. **Severity: Low → Medium post-staging**.

**R3 — Schema additive change to CompositionBlob (default_variant_id).** Existing composed widgets ship without the field. Codec must default to undefined gracefully.

- **Mitigation**: schema_version stays at 1 (additive optional field); codec parses absent as null. Round-trip test gates added. **Severity: Low**.

**R4 — Empty variants[] coexistence with variant-required widgets.** A composed widget can declare `supported_surfaces=["focus_canvas"]` but ship `variants: []`. Per Lock 3a.3, this Publish would block.

- **Mitigation**: WB-4a Publish gate already raises composition_invalid HTTP 422; WB-8 extends with the new error code. Authoring-time warning chip surfaces the gap before Publish. **Severity: Low**.

**R5 — Operator misuses default-variant designation.** Operator declares 4 variants but doesn't set default_variant_id. Bridge falls through to `variants[0]` per Lock 6b.

- **Mitigation**: fallback chain is documented; UX shows "Default" indicator on variant rows; operator can correct any time. Validator does NOT require default_variant_id (nullable per Lock 6a). **Severity: Low**.

**R6 — Per-atom visible_in_variants empty-array vs absent semantics.** Empty array means "hidden in all variants"; absent (None/undefined) means "visible in all." The chip-toggle UI must distinguish; codec must preserve.

- **Mitigation**: Lock 2a.5 specifies UI behavior — zero selections renders as "All variants" sentinel state with subdued chip styling; explicit "hidden in all" requires no-op state (impossible to author via UI but possible via API). Codec preserves the distinction. Round-trip test gate. **Severity: Medium**.

**R7 — registerComposedWidgets bridge change introduces variantId resolution that may interact with hot-reload.** Multiple registrations of the same widget with different default_variant_id could lead to staleness.

- **Mitigation**: refreshComposedWidgets (WB-4a) re-fetches + re-registers; registry's silent overwrite at (type, name) key handles drift. **Severity: Low**.

**R8 — Variant switching may cause atom-tree re-render storms.** Each variant switch re-runs `isAtomVisibleInVariant` for every atom. With 30-atom widget cap (per WB-1), 30 predicate evaluations per switch. Acceptable.

- **Mitigation**: React.memo on atom render path already established WB-2/WB-4b. Variant switch performance budget < 16ms (one frame). **Severity: Low**.

**R9 — canonical_dimensions surface-default fallback constants are guesses, not measured.** Lock 5b's fallback constants (800×600 focus_canvas, 480×320 page_canvas, 320×240 palette_preview) are reasonable but not measured against real render surfaces.

- **Mitigation**: tagged operator-validation-sensitive. Staging surfaces real dimensions; constants update via PR. **Severity: Medium**.

**R10 — Backward-compat for shipped composed widgets without variants[].** WB-4a / WB-5 / WB-6 / WB-7 likely shipped composed widgets at staging seeded with `variants: []`. Lock 3a.2/3a.3's new Publish-blocking errors would prevent ANY of those widgets from re-publishing.

- **Mitigation**: validator changes apply only to widgets DECLARING `supported_surfaces=["spaces_pin"]` or `["focus_canvas"]` AND having a non-empty composition_blob with no matching variant. A composed widget declaring `supported_surfaces=[]` or `["dashboard_grid"]` only is unaffected. Migration step: seed script audits shipped composed widgets; either backfills minimal variant declarations OR widens supported_surfaces declarations. Authoring-time warning surfaces the gap for operators to fix per widget. **Severity: Medium** — addressed by paired seed-audit work in the sub-arc execution plan.

---

## 11. Area 10 — WB cycle closure verification

The original WB investigation (`docs/investigations/2026-05-21-widget-builder.md`) enumerated 10 Areas. WB-8 closes the cycle. Verifying all 10 areas have shipped substrate-ready surfaces:

| Original WB Area | Description | Sub-arc closing | Verified ready post-WB-8 |
|---|---|---|---|
| Area 1 | Operator mental model (template seed + free modification) | WB-4a | ✓ Three-pane shell shipped; canvas with template-seed CTA |
| Area 2 | Composition primitives (atoms + 2-level layout containers) | WB-4a + WB-4b | ✓ 8 Phase 1 atoms + container atom; AtomInspectorDispatch covers all 8 |
| Area 3 | Data bindings (BindingRef + saved-view) | WB-6 | ✓ Binding picker + field_path resolution + iteration runtime |
| Area 4 | Rendering targets (supported_surfaces + variant taxonomy) | **WB-8** | ✓ Top-bar switcher + Variant CRUD + cross-surface validation |
| Area 5 | Persistence (composition_blob shape + versioning) | WB-1 + WB-4a (r106) | ✓ JSONB blob + session-aware + draft-vs-published |
| Area 6 | Behavior (action vocabulary respecting §12.6a) | WB-7 | ✓ 5-verb action dispatch (navigate / open_focus / open_peek / trigger_workflow / mutate) |
| Area 7 | Persistence: JSONB structural + tier inheritance | WB-1 | ✓ tier_scope CHECK + r105 + r106 |
| Area 8 | Test substrate | WB-4a–WB-7 | ✓ Cross-side + source-shape gates + Playwright .skip per arc |
| Area 9 | Migration + endpoint surfacing | WB-1 + WB-4a | ✓ r105 + r106 + 4 endpoints per widget_definitions/publish.py |
| Area 10 | Atom catalog growth + variant taxonomy | **WB-8** | ✓ Variant taxonomy authoring; atom growth deferred to WB-7+ (post-cycle) |

**Verdict: All 10 areas closed by WB-8 ship**. Atom catalog growth (Q-21 in original WB) is deferred indefinitely per Phase 1 scope but the substrate (AtomType vocabulary, AtomNode shape, AtomRenderer dispatch) accommodates additive growth without schema migration.

**Operator-ready substrate verification**:
- ✓ Operator can register a composed widget shell (WB-4a).
- ✓ Operator can drop atoms onto the canvas (WB-4a).
- ✓ Operator can author per-atom config (WB-4b).
- ✓ Operator can preview against real saved-view data (WB-5).
- ✓ Operator can bind atoms to saved-view fields (WB-6).
- ✓ Operator can wire button actions (WB-7).
- ✓ (post-WB-8) Operator can author variant taxonomy + per-atom visibility + cross-surface compatibility.

The substrate is operator-ready after WB-8 ships. The cycle closes.

---

## 12. WB-8 sub-arc execution plan + LOC calibration

### 12.1 Three-instance LOC calibration

Per the WB-6 / WB-5 / WB-7 LOC calibration pattern (3-instance variance):
- WB-6 estimated 850; shipped (~3.3× factor due to underestimation).
- WB-5 estimated 1,380; shipped (~0.5% bundle delta — substantial within-budget).
- WB-7 estimated ~1,800; shipped (~18% over).

The three-instance variance is wide (3.3× over → 0.5% under → 18% over). For WB-8, calibrating:
- **Substrate scope is meaningfully smaller** than WB-6 (single new schema field + 5 inspector additions) or WB-5 (full fetch orchestrator + canvas wiring). Closer to WB-7 in shape but narrower (single primitive: variants; not the 5-verb dispatch surface).
- **Authoring UI breadth is larger** than the schema scope: Variant CRUD section + chip-toggle group + top-bar switcher + 3 validator extensions + bridge edit.
- **Cross-surface mapping table** is a net-new module (estimated ~150 LOC backend + ~150 mirror).
- **WB-8 ships substrate ONLY for variant authoring** — no per-variant binding overrides (Lock 4a) — keeping the surface area bounded.

### 12.2 Estimated LOC delta

| Surface | Est. LOC | Notes |
|---|---|---|
| Schema: CompositionBlob.default_variant_id | ~10 | Pydantic + TS |
| Codec: parseCompositionBlob default_variant_id round-trip | ~30 | Defensive parse + serialize |
| Backend validator: cross-surface compat + spaces_pin/focus_canvas requirements + default_variant_id integrity | ~120 | 3 new check blocks |
| Surface mapping table (backend + frontend mirror) | ~250 | Constants + helpers |
| Top-bar variant switcher (WidgetBuilderPage + new VariantSwitcher.tsx) | ~180 | Segmented control + state wiring |
| Variant CRUD section (widget-root inspector) | ~280 | Form rows + add/remove + default radio |
| Per-atom visible_in_variants chip-toggle group | ~120 | New inspector primitive |
| AtomInspectorDispatch wiring of chip-toggle group | ~80 | Add to all atom inspector branches |
| registerComposedWidgets bridge edit | ~30 | Effective variantId resolution |
| Canvas preview canonical_dimensions frame | ~70 | Conditional CSS frame + fallback constants |
| Authoring-time warning chips on variant CRUD rows | ~80 | Compat check + chip |
| Publish-time error codes | ~40 | Validator + publish.py error surface |
| Source-shape gates (5 patterns) | ~120 | Per pattern ~25 LOC |
| Unit tests (validator + codec + chip-toggle + variant switcher + surface mapping) | ~400 | 8-10 test files |
| Cross-side integration test for variant filtering end-to-end | ~120 | One test |
| Playwright `.skip` scenarios | ~80 | Per WB-5/WB-6/WB-7 precedent |
| Seed-audit migration script (R10 mitigation) | ~80 | Idempotent backfill helper |

**Total midpoint estimate: ~1,990 LOC** (~2,000 LOC).

**Confidence band**: ±25% per the three-instance variance pattern. Substrate threshold flag at ~2,500 LOC (signal that the surface mapping + Variant CRUD section may collapse if substantially larger).

**Bundle impact**: estimate +0.05% to +0.15% on bundle size (per WB-5 / WB-7 precedent: small additive features ship within ±0.5%).

### 12.3 Sequential build steps (10 steps)

1. **Schema delta**: Add `default_variant_id: Optional[str]` to CompositionBlob in Pydantic + TS mirror. Extend codec. Round-trip tests.
2. **Surface mapping module**: Add `backend/app/services/widget_definitions/surface_mapping.py` + frontend mirror at `frontend/src/lib/widget-builder/types/surface-mapping.ts` with constants + helpers (e.g., `mapTargetSurfaceToWidgetSurfaces`, `isVariantCompatibleWithSupportedSurfaces`).
3. **Validator extensions**: Extend `backend/app/services/widget_definitions/validators.py` for cross-surface compat + spaces_pin Glance + focus_canvas Brief + default_variant_id integrity. Test gates.
4. **Top-bar variant switcher**: New `VariantSwitcher.tsx` segmented control. Mount in `WidgetBuilderPage.tsx` above WidgetCanvas. State wiring: active variantId in WidgetBuilderPage; passed into WidgetCanvas; WidgetCanvas passes into ComposedWidget.
5. **Variant CRUD section**: New `WidgetRootVariantCrudSection.tsx`. Mount in widget-root inspector. Form rows per canonical variant with declare-toggle + variant_name + target_surface dropdown + canonical_dimensions inputs + default-variant radio.
6. **Per-atom visible_in_variants chip-toggle**: New `VariantChipToggle.tsx` primitive in `inspector-primitives.tsx`. Wire into all 8 atom inspector branches in `AtomInspectorDispatch.tsx`.
7. **Canvas canonical_dimensions frame**: Wrap ComposedWidget render in canonical-dimensions-aware frame. Apply fallback constants when canonical_dimensions absent.
8. **Authoring-time warning chips**: Compatibility check in Variant CRUD section emits warning chip per row. No Publish blocking at draft.
9. **Bridge edit**: Update `registerComposedWidgets.ts` to resolve effective variantId from default_variant_id → variants[0] → undefined chain.
10. **Source-shape gates + Playwright .skip + seed-audit migration script**: Round out the test substrate per FF/WB precedent.

### 12.4 Operator-validation-sensitive locks

Tagged per DECISIONS entry 35 (post-staging revisit):

| Lock | Surface | Tag rationale |
|---|---|---|
| Lock 2a.1 | Variant_id picker-constrained to canonical 4 | Operators may want custom variant_ids; the substrate accommodates Phase 2 expansion |
| Lock 2a.2 | target_surface 3-value dropdown | Operators may reach for surface variants we didn't anticipate |
| Lock 2a.7 | Top-bar segmented control affordance | UX feedback (size, position, icon vs label) |
| Lock 3a.2 + 3a.3 | spaces_pin / focus_canvas variant requirements | Operators may reach for unusual surface-variant combinations |
| Lock 4a | Widget-scoped bindings + actions (deferred Option C deltas) | Duplicate-atom pattern may surface as painful at scale |
| Lock 5b | canonical_dimensions surface-default fallback constants | Constants are guesses; staging measures real dimensions |
| Lock 6b | Bridge fallback chain | May need explicit per-consumer override |

All 7 tagged locks ship substrate; revisits are UX refinements consuming existing data flow (zero rework cost per WB-5 / WB-6 / WB-7 canon).

### 12.5 Migration head

WB-8 ships ZERO new migrations (per WB-5 / WB-6 / WB-7 precedent — substrate changes are additive JSONB shape). Migration head remains at **r106_widget_definitions_published_blob**.

### 12.6 Backend endpoints

ZERO new endpoints. WB-8 uses existing widget-definitions endpoints (`/api/v1/widget-definitions/*`): GET, POST create, PUT draft, POST publish. composition_blob shape change is codec-handled.

### 12.7 Canon state

WB-8 may surface 3-4 new process canon candidates (per WB-6 / WB-5 / WB-7 pattern: 4 / 4 / 4 candidates per investigation). NOT FILED in WB-8 build — appended to the ~20+ accumulated for end-of-WB-cycle canon-update arc.

---

## 13. Architectural surprises during investigation

1. **Two parallel variant substrates coexist.** Top-level `widget_definitions.variants` column (Phase W-1, April 2026) and nested `composition_blob.variants[]` (WB-1, May 2026) are independent. Hand-coded widgets use top-level; composed widgets use nested. The two never cross-reference. **Most architecturally significant surprise.** Locked deferral in Area 8 to canon-update arc.

2. **`VariantId` and `variant_id` type asymmetry.** `VariantDefinition.variant_id` is a free `str`; `AtomNode.visible_in_variants: List[VariantId]` is restricted to the 4-canonical literal. The mismatch is structural-soft / practical-hard — non-canonical variant_ids are useless. Resolved by Lock 2a.1 (picker-constrained UI).

3. **`WidgetSurface` and `TargetSurface` vocabulary asymmetry.** Top-level supports 7 surfaces; composition target_surface supports 3. No code cross-references them. Lock 3a introduces a mapping table.

4. **`default_variant_id` exists at the top-level column but NOT in composition_blob.** The column is referenced by `spaces/crud.py:785` for hand-coded widgets. WB-8 adds the equivalent to composition_blob (Lock 6a). The two don't sync — a parallel-substrate consequence.

5. **registerComposedWidgets bridge is variant-unaware.** Despite shipped substrate at runtime + schema layer, the bridge passes no variantId. All Focus Builder palette previews + Spaces render paths currently show the unfiltered atom set. Lock 6b closes this gap.

6. **Per-atom `visible_in_variants` was listed as WB-4 step 8 but NOT shipped.** The WB-4 investigation `docs/investigations/2026-05-21-widget-builder-canvas.md:362` declared "Per-atom `visible_in_variants` multi-select" as a Phase 1 deliverable. Grep across `frontend/src/bridgeable-admin/` returns ZERO references. WB-4 deferred this without flagging the deferral.

7. **Backend validator already enforces variant integrity** (refs + uniqueness) but NOT cross-surface compatibility. The validation surface added by Lock 3a is the FIRST cross-field validation in the WB substrate that spans composition_blob to top-level columns.

8. **`composition_blob.variants[]` defaults to empty `[]` in publish.py:97 fresh-blob template.** Every composed widget shipped to date carries `variants: []`. The "all atoms" rendering (variantId=undefined) is the implicit default. WB-8 is the first arc to give operators authoring control over this; existing widgets are unaffected (no atoms have `visible_in_variants` set, so all atoms render regardless).

9. **No "default variant" UX in original WB Q-23 lock.** The original WB investigation locked Q-23 ("Surface availability declaration") as a `supported_surfaces` declaration but did NOT explicitly call out "which variant is the default for catalog/palette preview." The default-variant designation surfaced as a substrate question only during WB-8 audit. Lock 6a closes this gap with a new schema field.

10. **`spaces/crud.py:785` already honors `default_variant_id`** (top-level column) for spaces pin rendering. Implication: when composition_blob.default_variant_id (Lock 6a) ships, the spaces render path needs to choose which source to consult. Documented in Area 7 as a sync rule deferred to canon-update.

---

## 14. Process canon candidates (NOT filed; appended to ~20+ accumulated)

For end-of-WB-cycle canon-update arc:

(ε) **When a substrate-extending arc introduces a field whose name collides with an existing field elsewhere on the same row, the investigation must enumerate the existing field, audit usage, and either retire / alias / document coexistence.** Source: §2.4 finding of two parallel variant substrates landing in different arcs without reconciliation.

(ζ) **WB-4-style "deferred without flagging the deferral" patterns are class-of-bug worth canonical guidance.** Source: WB-4 investigation declared per-atom visible_in_variants as Phase 1 step 8 but did not ship it; deferral was not surfaced as a deliberate decision. Implication: Phase 1 scope lists are themselves substrate-load-bearing and must be cross-checked against shipped surfaces.

(η) **"Built-but-dormant substrate" is a third state distinct from built/missing** (already surfaced by WB-6 process canon candidate (b)). WB-8 reinforces: the variant substrate is BUILT at runtime + schema + validator but DORMANT at authoring. Operators cannot reach it. This pattern is worth elevating from candidate to canon after this third instance.

(θ) **Cross-vocabulary mapping tables are substrate, not derived data.** The TargetSurface ↔ WidgetSurface mapping (Lock 3a) is a load-bearing constant that lives at a known location with a known shape. Future cross-vocabulary substrates (Page Builder canvas surfaces, Document Builder layout surfaces) inherit this discipline.

---

## 15. Constraints honored

- Zero production code touched.
- Zero test changes.
- Zero canon doc modifications (CLAUDE.md, PLATFORM_ARCHITECTURE.md, DESIGN_LANGUAGE.md, BRIDGEABLE_MASTER.md, FUNERAL_HOME_VERTICAL.md, VISION.md, DECISIONS.md).
- 114 stale Playwright screenshot deletions left untouched.
- HEAD verified at `7e45453` pre-investigation; no changes made.
- Every assertion cites file:line OR canon entry OR investigation artifact.
- Audit phase (Area 1) before locks — substrate maturity assessed per consumer.
- 3+ alternatives enumerated per Areas 2, 3, 4, 5, 6, 7.
- Areas 1-4 load-bearing; Areas 5-6 derived; Areas 7-10 supporting (per the prompt's weighting).
- 7 operator-validation-sensitive locks tagged.
- Cross-substrate dependency enumeration (Area 7) covers 18 substrate entries.
- LOC calibrated against WB-6/5/7 three-instance variance.
- WB cycle closure verification (Area 10) addresses all 10 original WB areas.
- Process canon candidates surfaced (4 new, NOT filed).
- Architectural surprises enumerated (10).
- Investigation word count: ~7,800 words (within ~6,500-9,000 target).
- STATE.md update covered separately in build report.
