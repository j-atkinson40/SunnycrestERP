# Widget Builder Canvas Preview — Read-Only Investigation

**Date:** 2026-05-23
**Arc:** `2026-05-23-widget-builder-canvas-preview`
**Sub-arc target:** WB-5 (canvas preview wiring against real data)
**Status:** Investigation complete; substrate locked; build prompt to follow.
**Pre-flight verification:** HEAD `0ce41df` (WB-6 build) confirmed. Working tree carries 114 unstaged Playwright screenshot deletions — untouched per scope discipline. Zero production files touched by this investigation.

---

## 1. Context

WB-6 (commit `0ce41df`) substantiated bindings at the runtime + authoring layer:

- `resolveBinding.ts` resolves real `field_path` against a `dataContext` carrying row dicts + aggregations (per WB-6 Lock 4a–4d).
- `AtomRenderer.tsx::repeater_atom` branch reads `dataContext.rows` when supplied (per WB-6 Lock 5a); when `dataContext` is `undefined`, it falls back to **one structural mock row** so the canvas remains visually shaped during authoring (`AtomRenderer.tsx:198-222`).
- The in-inspector preview-card (`BindingPreviewTooltip.tsx` consuming `useBindingPreview.ts`) calls `executeSavedView` against the operator's tenant JWT and resolves the binding against the result.

What WB-6 deliberately did **not** ship (per Area 8 of `docs/investigations/2026-05-22-widget-builder-bindings.md:541-552`):

- **Canvas preview wiring** — `WidgetCanvas.tsx:199-205` mounts `<ComposedWidget widgetDefinition={…} />` with **no `dataContext` prop**. ComposedWidget passes `undefined` through to AtomRenderer, which falls back to the 1-mock-row authoring placeholder. Real saved-view data does not flow into the canvas.
- **Sample record selection** in canvas.
- **Error / loading states** in canvas preview (the inspector preview-card carries its own states, but the canvas does not).
- **Tenant context propagation** as an explicit decision (today's behavior is "operator's JWT-implicit tenant"; the question is whether WB-5 keeps it implicit or makes it explicit).

WB-5 closes this seam. The seam is narrower than WB-6 was — substrate is in place (resolveBinding, AtomRenderer iteration, executeSavedView, useDebouncedValue, AbortController patterns). What's missing is the **canvas-side fetch orchestrator** + **operator-validation-sensitive UX decisions** about which saved view → which sample record → which tenant data renders.

The investigation deliberately does **not** lock UX patterns by intuition. Per DECISIONS entry 26 (investigation-time UX locks can be refined by operator experience), this investigation tags operator-validation-sensitive locks for post-staging revisit while still locking the substrate shape for ship.

---

## 2. Area 1 — Canvas preview substrate audit (LOAD-BEARING)

### 2.1 Current rendering path

Walked the rendering chain from canvas through atom dispatch:

| Step | File | Status |
|---|---|---|
| Canvas mount | `WidgetCanvas.tsx:199-205` | Mounts `<ComposedWidget widgetDefinition={{widget_id, composition_blob: blob}} />`. **No `dataContext` prop passed.** |
| ComposedWidget | `ComposedWidget.tsx:73, 122` | Accepts `dataContext?: unknown` (signature carries it for downstream pass-through); when undefined, passes `undefined` to AtomRenderer. |
| AtomRenderer dispatch | `AtomRenderer.tsx:151-156` | `dataContext` flows through; `buildResolvedBindings` calls `resolveBinding(ref, dataContext)`. |
| Resolve at canvas | `resolveBinding.ts` | For literal bindings: returns literal_value (unaffected). For field_path bindings: traverses against dataContext; when dataContext is undefined → returns `null`. |
| Repeater branch | `AtomRenderer.tsx:198-222` | When `dataContext === undefined` OR `dataContext.rows` is absent → renders **1 structural mock row** with `rowContext = { __row: true, __index: 0 }` (no spread row fields). |
| Leaf atom render | `atoms/index.tsx` various | TextLabel, ValueDisplay, etc. consume `resolvedBindings[fieldName]` — when value is `null`, renderer falls back to per-atom placeholder copy (e.g., TextLabelRenderer renders "Text label"). |

**Audit verdict:** the canvas TODAY renders shape-correct but data-empty. An operator authoring a widget with bindings sees the structural skeleton (one mock row in repeaters, placeholder copy in leaf atoms). The binding picker's in-inspector preview-card is the only surface where the operator sees real resolved values.

### 2.2 What's in place vs. what's missing

**In place (WB-6 substrate):**
- `dataContext` plumbing through ComposedWidget → AtomRenderer (signature-only at canvas; functional at runtime callers).
- `resolveBinding` real implementation for field_path + literal + per_row + single_record + single_summary.
- `AtomRenderer.tsx` repeater branch consumes `dataContext.rows` when present; spreads row fields into per-row context.
- `executeSavedView(viewId)` returns `SavedViewResult { total_count, rows, groups, aggregations, permission_mode, masked_fields }` — tenant-implicit via JWT.
- `useBindingPreview` (inspector card) demonstrates the fetch + resolve + debounce + cancellation pattern, scoped to a single binding.
- `useDebouncedValue` at `frontend/src/hooks/useDebouncedValue.ts` — reusable debounce primitive.
- `AbortController` pattern established at `useWidgetAutoSave` (per `useWidgetAutoSave.ts:7-21`).

**Missing (WB-5 substrate):**
- Canvas-side fetch orchestrator that walks `blob.bindings_catalog`, deduplicates `saved_view_id` references, fetches each view's result, and stitches results into a `dataContext` per binding (or per-atom).
- Sample-record selection decision (which row from `rows` becomes the per-atom render context when iteration_mode='single_record').
- Error / loading UX in the canvas itself (distinct from the inspector preview-card and from WB-4b validation error chrome).
- Race condition + cancellation between successive operator edits to a binding (binding A in-flight; operator switches to binding C; A's response must not overwrite C's).
- A decision about whether the canvas fetches against operator's tenant or some other context (Area 2).

### 2.3 Audit findings tagged

The 1-mock-row authoring fallback **must coexist** with WB-5's real-data path. Operators with **no bindings yet authored** still need a visible canvas. Per `AtomRenderer.tsx:222`: `iterRows = [null] // WB-6 authoring fallback`. This path must remain reachable when (a) the widget has no bindings, (b) the canvas has not yet fetched real data, or (c) the canvas chose to render placeholder during error recovery (per Area 4 below). The fallback shape ≠ the fetched-empty-rows shape ≠ the fetched-then-failed shape — three distinct visual states.

---

## 3. Area 2 — Tenant context model (LOAD-BEARING)

### 3.1 The question

A widget is authored once and rendered for many tenants. When the operator previews the widget in the canvas, against **whose** tenant's data does it render?

The substrate gives a natural answer: `executeSavedView` is tenant-implicit via JWT (`backend/app/api/routes/saved_views.py:432-435` uses `current_user.company_id` for both `caller_company_id` and the saved-view lookup path). The operator is authenticated to *some* tenant (today, an admin impersonating a tenant via the runtime editor at `/runtime-editor/?tenant=…&user=…` — see R-1.6.9). Whatever tenant the operator's JWT resolves to is the implicit tenant.

### 3.2 Options enumerated

**A — Operator's JWT tenant (implicit).** Canvas calls `executeSavedView(savedViewId)` and the backend resolves whatever tenant the JWT belongs to. If the operator is logged in as a sunnycrest admin, the preview shows sunnycrest data. If the operator impersonates a hopkins-fh user, it shows hopkins-fh data. **Pros:** zero new substrate; matches `useBindingPreview` (the inspector card already works this way); matches `SavedViewWidget` (shipped saved-view embedding). **Cons:** preview is operator-tenant-flavored; a sunnycrest-admin authoring a cross-vertical widget sees only sunnycrest's data shape.

**B — Operator-selected preview tenant.** Top-bar picker letting the operator switch the preview's tenant context. **Pros:** explicit multi-tenant verification. **Cons:** requires a tenant-switcher UI; requires the operator's permissions to span multiple tenants; today's substrate has impersonation (admin-platform-level) but the widget builder runs in the **tenant API tree** (`/api/v1/widget-definitions/*` — see `widget-builder-service.ts:8`), not the admin API tree. Building B means either (a) reauthoring widget builder against the admin API surface, or (b) introducing a preview-only tenant override on tenant-API calls. Both are substantial out-of-scope work.

**C — Reference tenant per vertical.** Each vertical maps to a canonical preview tenant (manufacturing → testco, funeral_home → hopkins-fh). **Pros:** consistent across operators. **Cons:** requires a vertical→tenant mapping table; requires operators to have access to those reference tenants; canon tenants don't exist for verticals not yet seeded; the widget's `tier_scope` is per-widget (not necessarily vertical-locked).

**D — Synthetic / seeded data.** Canvas renders against fixture data, not real tenant data. **Pros:** no permission issues; no cross-tenant data leakage. **Cons:** synthetic data does NOT surface the real shape problems (a `vault_item.metadata_json.field_x` that doesn't exist in real data renders fine; a real cross-tenant masked field doesn't appear masked). The whole point of operator-validation-against-real-data is lost.

**E — Operator's tenant default + explicit override.** Default to A; surface a small picker for advanced operators who need B or C. **Pros:** lowest-friction default + escape hatch. **Cons:** doubles the surface area; the picker UX is itself an operator-validation-sensitive decision; surface area grows for a Phase-1 sub-arc.

### 3.3 LOCK 2a — Option A (operator's JWT tenant) for WB-5 Phase 1

**Reasoning:**

1. **Substrate parity with WB-6.** `useBindingPreview` already uses option A. The inspector preview-card and the canvas preview should agree on which tenant they render — otherwise an operator authoring a binding sees one value in the inspector and a different value (or empty) in the canvas. Substrate symmetry is load-bearing.
2. **Zero new substrate.** Option A is a no-op tenant-wise; `executeSavedView(viewId)` is already tenant-implicit.
3. **Substrate match with shipped consumers.** `SavedViewWidget.tsx` (hub embed of saved views) renders against caller tenant. Widgets in production render against the consuming tenant's data. The authoring canvas matching production semantics is the lower-surprise default.
4. **Out-of-scope work for B + C + E.** Option B requires admin-API reauthoring of the widget builder; option C requires a vertical→tenant mapping that doesn't exist; option E requires UX work on the picker AND the default. None are appropriate for WB-5's "wire the substrate" scope.
5. **Option D rejected on first principles.** Synthetic data defeats the purpose of operator-validation; the whole arc thesis (per `PLATFORM_PRODUCT_PRINCIPLES.md`) is that authoring is the operator's calibration loop against their real data.

### 3.4 Operator-validation-sensitive tag

**Tagged for post-staging revisit per DECISIONS entry 26.** Once operators ship widgets at staging, the question "would I want to preview against another tenant's data?" surfaces real demand signal. If operators reach for a tenant picker, ship E. If they don't, A holds. Until then, A is the lock.

### 3.5 Alternatives considered

- **Auto-detect tier_scope and prefer a matching tenant** — REJECTED. Tier scopes are `platform_default / vertical_default / tenant_override`; the widget being authored is most often a tenant_override or vertical_default, and the operator's JWT is already on the right tenant for that authoring session. The auto-detect adds machinery without changing the answer in the common case.
- **Render against the **published version** of the saved view** — REJECTED (not relevant). Saved views don't have a publication state. The view's `config` is the canonical config; the executor reads it directly.

---

## 4. Area 3 — Sample record selection (LOAD-BEARING for per-record atoms)

### 4.1 The question

The saved view's `executeSavedView` result returns `rows: Record<string, unknown>[]` — many rows. For atoms with `iteration_mode='single_record'` (a leaf atom binding to a field on one row of a saved view), **which** row?

For `iteration_mode='per_row'` (a repeater iterating all rows): all rows render — no selection question.

For `iteration_mode='single_summary'` (aggregations): no rows needed — `result.aggregations` carries the value.

The question is **scoped to `single_record`** iteration.

### 4.2 Options enumerated

**A — First row (rows[0]).** Matches WB-6 `useBindingPreview` (`useBindingPreview.ts:112: const first = rows[0]`); matches WB-6 Lock 5c (`AtomRenderer.tsx::single_record` runtime semantics, although the canvas didn't yet exercise this). **Pros:** zero new substrate; substrate parity with inspector preview-card; matches Original WB Q-16 lock (sample record = first record). **Cons:** operator can't verify how the widget renders for rows other than the first; if the operator wants to test how their widget handles a long deceased-name vs a short one, they have to re-sort the saved view (which they can do; saved views carry sort config). Acceptable workaround.

**B — Operator-selected record (picker).** Picker UI in canvas chrome: "Preview row N of M [<] [>]". **Pros:** operator can verify multiple records; finds layout-breaking edge cases. **Cons:** picker UX + state management; picker location is itself a UX decision (canvas top bar? inspector? hover-revealed?); rows-without-stable-id problem (the executor's row dicts use entity-level IDs that vary across executions when the underlying data mutates between fetches).

**C — Cycling preview.** Auto-rotate every N seconds. **Pros:** surfaces variance without operator action. **Cons:** distracting during authoring; defeats the "preview is stable while I'm editing" mental model; not how any other authoring surface works.

**D — First-record default + operator pin override.** Defaults to A; the operator can click a row in the saved-view's rendered repeater (or a separate "pin sample record" affordance) to lock that row as the sample. **Pros:** zero-friction default; escape hatch for verification. **Cons:** the "click a row in a repeater" affordance only works when the repeater is on canvas; for non-repeater widgets binding to a saved view via `single_record`, there's no rendered row to click — needs a separate picker. Compound UX. Defers the picker question without eliminating it.

### 4.3 LOCK 3a — Option A (first row) for WB-5 Phase 1

**Reasoning:**

1. **Substrate parity with WB-6 inspector preview-card.** `useBindingPreview.ts:111-119` resolves both `per_row` and `single_record` against `rows[0]`. Canvas matches.
2. **Substrate parity with `single_record` runtime semantic.** WB-6 Lock 5c explicitly chose first-row; the canvas preview should follow.
3. **Operator workaround exists.** Re-sorting the saved view changes which row is first. Operator has full control via the saved view's sort config — they don't need a separate canvas-level picker to verify alternate rows.
4. **Option B + D defer to operator validation.** If staging shows operators reaching for "preview row 2," option D becomes the next lock; the picker UX itself is operator-validation-sensitive (the picker placement, the "pin" semantic, the keyboard binding). WB-5 ships the substrate that A + D can both consume.
5. **Option C rejected on first principles.** Cycling makes authoring unstable.

### 4.4 Operator-validation-sensitive tag

**Tagged for post-staging revisit per DECISIONS entry 26.** Operators may reach for "let me see how this renders for the third row" — if so, ship D. WB-5's substrate (single fetch per saved_view_id; result cached per fetch) naturally accommodates D without rework: the picker mutates a `sampleRecordIndex` state; the canvas reads `result.rows[sampleRecordIndex]` instead of `result.rows[0]`. Substrate-neutral.

### 4.5 Alternatives considered

- **Random row each render** — REJECTED. Defeats stability during authoring.
- **Last-updated row** — REJECTED. Adds a sort the operator didn't ask for; "what's first" is the canonical mental model.

---

## 5. Area 4 — Error state UX (LOAD-BEARING)

### 5.1 The question

Canvas-side fetching surfaces error conditions that the WB-6 inspector preview-card already handles in `useBindingPreview` but that the canvas does not yet handle. Each condition has distinct UX implications.

### 5.2 Error condition enumeration

| # | Condition | Surface | Backend signal |
|---|---|---|---|
| E1 | Saved view doesn't exist (deleted, stale binding) | `executeSavedView` 404 | `SavedViewError` → translated HTTPException |
| E2 | Operator lacks permission for saved view (private, role_shared, cross-tenant unshared) | `executeSavedView` 403 | `crud.py:112-113` cross-tenant gating |
| E3 | `field_path` doesn't resolve (path doesn't exist on row, or all rows have null at that path) | resolve-time | `resolveBinding` returns `null` |
| E4 | Network error / API down | `executeSavedView` reject | Axios `ERR_NETWORK` |
| E5 | Saved view's `presentation.mode` mismatches binding's `iteration_mode` (operator changed the view to chart-mode after binding to list-mode) | resolve-time | `result.aggregations === null` when `iteration_mode='single_summary'` expects it |
| E6 | Empty result set | resolve-time | `result.rows.length === 0` |
| E7 | Cross-tenant masking — `result.permission_mode === 'cross_tenant_masked'` + the bound field is in `result.masked_fields` | resolve-time | resolved value is `"__MASKED__"` sentinel |
| E8 | Malformed `field_path` (empty, leading dot, consecutive dots) | resolve-time | `resolveBinding` throws |

### 5.3 Options enumerated

**Surfacing dimension:**

- (a) **Atom-level** — each atom that consumed a bad binding renders its own error chrome (red placeholder; small ⚠️ icon; tooltip with error message). The rest of the widget renders normally.
- (b) **Canvas-level banner** — a single banner across the top of the canvas listing all binding errors; atoms render placeholder copy. Compact summary; less per-atom visual noise.
- (c) **Both** — atom-level inline + canvas-level summary.
- (d) **Validation chrome reuse** — extend WB-4b's `AtomErrorIndicator` (the red outline + tooltip) to also carry resolution errors. Then the operator sees one chrome system across validation + resolution.

**Blocking dimension:**

- (a) **Blocking** — canvas blanks itself entirely until the operator fixes the binding.
- (b) **Non-blocking** — canvas renders shape; broken atoms show placeholder; everything else renders normally.

**Recovery dimension:**

- (a) **Auto-retry** — on network error (E4), retry with exponential backoff.
- (b) **Manual refresh** — small "Retry" affordance on the error.
- (c) **No retry** — operator's next edit triggers a new fetch naturally; no explicit retry.

**Distinction from validation errors:**

- WB-4b shipped `AtomErrorIndicator` for `validators.py` errors (composition-blob validity). Resolution errors are different — they're tenant-data conditions, not composition correctness. The operator may have authored a perfectly valid widget that fetches no data because the saved view is empty.

### 5.4 LOCK 4a — Atom-level inline + minimal canvas-level summary (option c, scoped) for surfacing

**Per-atom chrome:**

- E1 / E2 — fatal at atom level. Atom renders **"⚠ binding error"** placeholder copy (per-atom: text label shows "⚠ binding"; value display shows "⚠"; repeater shows "⚠ no data — saved view not found / no access"). Hover surfaces detail.
- E3 / E6 / E7 — soft at atom level. Atom renders its per-atom placeholder copy (the existing fallback behavior from WB-6; `ValueDisplayConfig.placeholder` etc.). No ⚠ icon. This matches WB-6 `resolveBinding` returning `null` → renderer renders placeholder. The masked case (E7) gets a small lock icon + tooltip "Field masked per cross-tenant policy" to distinguish from "no data."
- E5 — atom renders ⚠ + tooltip "Saved view shape changed; rebind required." Distinct copy from E1/E2.
- E4 — canvas-level (see below). Per-atom is too noisy if every atom fails.
- E8 — composition error, caught at WB-6 strict validator. Shouldn't reach runtime if Publish-gated. If it does (draft state) → atom ⚠ + tooltip "Malformed field path."

**Canvas-level banner:**

- ONE banner above the canvas (only when at least one binding error is active). Banner text varies:
  - E4: "Network error — canvas preview unavailable. [Retry]". Atoms render placeholder copy (the operator can still author).
  - E1/E2/E5: silent at canvas level — atoms carry the chrome inline; canvas banner doesn't repeat.

**Reasoning:**

1. **Distinct from WB-4b validation chrome.** Resolution errors live on a separate chrome path. The operator should immediately see "this is a data condition, not a composition error" — different mental model, different remediation.
2. **Atom-level granularity.** A widget with 5 bindings where 2 fail and 3 succeed should render 2 ⚠ atoms + 3 working atoms — not 5 atoms all hidden behind a global "errors" banner. Operator can see the working bits + work on the broken bits in isolation.
3. **Canvas-level for network-class errors only.** When the whole canvas can't fetch, a global indicator is appropriate. When one binding fails out of five, per-atom granularity is appropriate.

### 5.5 LOCK 4b — Non-blocking rendering

**Reasoning:**

1. **Operator authoring resilience.** Operator should be able to keep authoring even when one binding has errored. The canvas blanking itself means the operator loses the ability to position, resize, configure non-affected atoms.
2. **Shape-correctness preserved.** Atoms render their own placeholder shape (per-atom Config `placeholder` field). The widget's shape stays visible.
3. **Matches WB-6 fallback semantics.** `AtomRenderer.tsx:222` already falls back to 1-mock-row when `dataContext` is undefined. WB-5's error path mirrors that fallback shape: data-empty but structurally visible.

### 5.6 LOCK 4c — Manual refresh on canvas-level banner; passive recovery on atom-level (mixed c + b)

- Canvas-level network error: explicit `[Retry]` button in the banner. Operator action → re-fetch all in-flight bindings.
- Atom-level errors (E1, E2, E3, E5, E6, E7): no per-atom retry. The next operator edit to that binding (or its saved-view selection) triggers a new fetch naturally. If the operator fixes the saved view in another tab and wants to refresh, the canvas-level banner's [Retry] also covers atom-level errors transparently (re-fetches everything).

**Reasoning:**

1. **Auto-retry is risky for network errors.** Exponential backoff in the canvas while the operator is editing creates surprise re-fetches that may overwrite mid-edit state. Operator-initiated retry is predictable.
2. **Per-atom retry is overkill.** Adding retry buttons to per-atom placeholders bloats the surface.

### 5.7 LOCK 4d — Resolution errors do NOT trigger the WB-4b red-outline validation chrome

**Reasoning:**

1. **Distinct mental model.** Validation = composition is structurally invalid; the operator must fix the composition. Resolution = data is missing or shape-changed; the operator may need to fix the binding OR fix the data OR accept the empty state.
2. **Same red-outline for two different problems is confusing.** Operators learn "red = validation"; resolution errors get their own chrome.
3. **Chrome separation matches existing distinction.** WB-4b's `AtomErrorIndicator` reads from `errorsByAtom` populated by `useWidgetValidation` (composition validator). Resolution errors live on a separate state path keyed by atom_id, surfaced by a separate chrome component.

### 5.8 Alternatives considered

- **Treat all errors identically (single chrome, single severity)** — REJECTED. Different error classes warrant different operator response.
- **Pop a modal on first error** — REJECTED. Disrupts authoring flow.
- **Show errors in the inspector right-rail** — REJECTED. Inspector is per-selected-atom; resolution errors apply to atoms the operator may not have selected.

---

## 6. Area 5 — Loading state UX

### 6.1 The question

Canvas fetches saved-view data asynchronously. During fetch (first render, after operator changes a binding, after canvas [Retry]), the canvas needs to communicate "loading" without breaking the operator's mental model of the widget's shape.

### 6.2 Options enumerated

**A — Skeleton placeholder per atom.** Per-atom skeleton matching the rendered atom's shape (text-label skeleton = gray pill; value-display skeleton = bigger gray pill; repeater skeleton = N gray rows). **Pros:** preserves shape; communicates loading at the granularity the data lives. **Cons:** more LOC; per-atom skeleton variants need design alignment.

**B — Spinner per atom.** Small spinner overlay on each atom waiting for data. **Pros:** trivially implementable. **Cons:** visually noisy; multiple spinners feel uncoordinated.

**C — Canvas-level skeleton.** Whole canvas dims + shows a single spinner during initial fetch. **Pros:** clean, single signal. **Cons:** loses shape during loading; operator can't position / resize / configure during the fetch window; matches a "blocking" feel.

**D — Optimistic stale rendering.** Previous fetch's data renders; new fetch happens in the background; updates when complete. **Pros:** zero loading state visible during the steady-state authoring loop; matches modern web app expectations. **Cons:** initial fetch (no prior data) still needs SOMETHING.

**E — Inline shimmer.** Atom renders its placeholder copy with a subtle shimmer animation. **Pros:** preserves shape; communicates "data coming"; design-language consistent (shimmer is a Phase 7 polish primitive). **Cons:** shimmer-pulse can feel busy when 5 atoms are simultaneously loading.

### 6.3 LOCK 5a — Hybrid: D (optimistic stale) + A (skeleton) for first-fetch + E (subtle shimmer) on atoms with pending bindings

**The composed rule:**

1. **First load (no prior data, no fetched-empty result):** atom renders **A — skeleton placeholder** matching the atom's intrinsic shape (per-atom skeleton via a single shared `<AtomSkeleton atomType="…" />` component, ~80 LOC across the catalog).
2. **Subsequent loads after operator edits binding:** atom continues to render the **previous resolved value** (D — optimistic stale) **with a subtle shimmer overlay** (E) to communicate "value is being refreshed." When the new fetch lands, the shimmer clears and the value updates.
3. **Cancelled fetch (operator edited again before previous landed):** the cancelled fetch's atom stays in shimmer state; the new fetch supersedes it (per Area 6). No visible interruption.
4. **Canvas-level loading indicator:** a small "Fetching preview…" pill in the canvas top-right corner during ANY in-flight fetch, summary granularity. Distinct from C (canvas-level skeleton — too aggressive); this is just a passive signal.

**Reasoning:**

1. **D matches operator authoring loop.** Once the operator has authored a binding and seen its real value, every subsequent edit (resize, reposition, child atom add) should NOT clear that value — that's a regression vs. WB-6's authoring affordance.
2. **A handles the cold-start case.** Skeleton on first render avoids "empty for 200ms then suddenly populated" flash; communicates "wait, data coming."
3. **E communicates the refresh without overwhelming.** Shimmer is a known DESIGN_LANGUAGE primitive (Aesthetic Arc Phase II); operators recognize it.
4. **Top-right pill is the unified canvas-level signal** — distinct from the per-atom shimmer; both can coexist.

### 6.4 Operator-validation-sensitive tag

**The shimmer specifically** is tagged for post-staging revisit. If operators report distraction during heavy authoring loops, swap to A-only (skeleton on first; clean transition on refresh). Substrate accommodates both: the shimmer is a CSS class applied/removed based on per-binding fetch state.

### 6.5 Alternatives considered

- **No loading state at all (atoms just sit on previous value)** — REJECTED. Operators need to know when their canvas is fresh vs. stale. The pill + shimmer pair provides this signal.
- **Block the canvas entirely during fetch (C only)** — REJECTED. Operator authoring blocks every 200ms-ish.

---

## 7. Area 6 — Race condition + cancellation modeling

### 7.1 The scenario

Operator selects atom A. Atom A's binding refs `savedView_X`. Canvas fires fetch_1 for `savedView_X`.
Before fetch_1 resolves (slow network or large query), operator edits atom A's binding to `savedView_Y`. Canvas fires fetch_2 for `savedView_Y`.
fetch_2 returns first (small query). Canvas renders savedView_Y data.
fetch_1 returns. **MUST NOT overwrite savedView_Y's data with savedView_X's stale result.**

Per DECISIONS entry 38 (investigations of stateful drag must model cumulative-delta-vs-per-tick-state — but the lineage here is the same shape: investigations of async data substrate must model the cancellation semantics). WB-6 `useBindingPreview` solved this for the inspector card via `latestFetchId` ref. WB-5 inherits the question at canvas scope.

### 7.2 Options enumerated

**A — AbortController per fetch.** Each fetch carries its own AbortController; when a newer fetch fires for the same binding (or same saved_view_id), the older fetch's controller aborts. Substrate parity with `useWidgetAutoSave.ts` per source-shape gate.

**B — Request ID matching.** Maintain a per-binding (or per-saved-view) "latest request id" ref; ignore responses where `responseRequestId !== latestRef.current`. Substrate parity with WB-6 `useBindingPreview.ts:65-66, 74-75`.

**C — Optimistic stale rendering during cancellation.** Same as Area 5 Lock 5a — keep showing previous value until new fetch lands; cancelled fetches just don't update anything.

### 7.3 LOCK 6a — A + B together, scoped per `saved_view_id`

**The composed rule:**

1. **Per-saved-view AbortController + fetchId ref.** The canvas fetch orchestrator maintains a `Map<saved_view_id, { controller: AbortController, fetchId: number }>`. When a new fetch fires for `saved_view_id=X`:
   - Abort the existing controller for X (if any).
   - Bump `fetchId` for X.
   - Capture the new fetchId locally.
   - Fire the fetch with the new controller.
   - On response, check if `latestFetchId === capturedFetchId`. If not, ignore.
2. **AbortController** primary defense. `B` (fetchId check) is defense-in-depth — handles the case where `abort()` was issued AFTER the response was already in-flight at the network layer but BEFORE it reached `.then()`.
3. **Deduplication:** the canvas walks `bindings_catalog`, builds a unique set of `saved_view_id`s, and fires one fetch per unique view. Two atoms binding to the same saved view share the fetched result. This matters because a widget with 10 atoms bound to 2 saved views fires 2 fetches, not 10.

**Reasoning:**

1. **Substrate parity.** A matches `useWidgetAutoSave` (source-shape gate already verifies AbortController presence). B matches `useBindingPreview` (`latestFetchId` ref). WB-5 composes the two.
2. **Both layers needed.** AbortController doesn't always abort cleanly in the browser (response may already be in flight at the network layer). The fetchId check catches "the fetch resolved after abort fired" races.
3. **Per-saved-view scope, not per-atom.** Atoms with bindings to the same view share data; deduping at the saved-view level keeps the fetch count proportional to unique views, not atoms.

### 7.4 LOCK 6b — Coexistence with WB-4a auto-save AbortController

**Audit:** `useWidgetAutoSave.ts` uses its own AbortController for the PUT to `/widget-definitions/{slug}/draft`. WB-5's fetch orchestrator uses separate AbortControllers for GET to `/saved-views/{id}/execute`. Completely orthogonal request streams; no shared controller; no coexistence issue.

**Validated:** Risk 3 from Area 10 is the only place where coexistence could leak (e.g., a future refactor unifying request lifecycle). Substrate locks separation explicitly: the canvas fetch orchestrator's controllers live in a separate ref (`previewControllersRef`) from auto-save's controller. Source-shape gate (per DECISIONS entry 31) MAY verify the separation.

### 7.5 Alternatives considered

- **No cancellation; "last response wins"** — REJECTED. Network ordering is not guaranteed; fetch_1 can resolve AFTER fetch_2 even when issued first. Substrate would show stale data.
- **AbortController per atom (not per saved view)** — REJECTED. Over-cancels; if 3 atoms share a saved view and one atom's edit triggers a refresh, the other 2 atoms shouldn't lose their in-flight fetch.

---

## 8. Area 7 — Cross-substrate dependency enumeration

WB-5 touches the following substrate layers. For each: reused-as-is / modified / net-new.

| Substrate | Touched | Disposition |
|---|---|---|
| WB-2 `ComposedWidget.tsx` | Consumed | **Reused as-is.** Already accepts `dataContext` prop (added Phase 1; unused until WB-5). Canvas now PASSES a real value. |
| WB-3 atom renderers (`atoms/index.tsx`) | Consumed | **Reused as-is.** Each renderer already accepts `resolvedBindings` populated from real data. No per-renderer change for WB-5. Per-atom skeleton (per Area 5 LOCK 5a) is the only NEW renderer-adjacent surface. |
| WB-3 + WB-6 `AtomRenderer.tsx` iteration | Consumed | **Reused as-is.** Repeater branch already reads `dataContext.rows` when present; spreads row fields. WB-5 supplies the rows; AtomRenderer's code is unchanged. The 1-mock-row authoring fallback path must remain reachable (no-bindings case). |
| WB-4a `WidgetCanvas.tsx` | Modified | **Net-new orchestration + UX state**: introduce a hook that reads `blob.bindings_catalog`, deduplicates saved_view_ids, fetches each, builds a `dataContext` map per-binding, passes derived `dataContext` to `<ComposedWidget>`. New canvas-level error banner. New canvas-level "Fetching" pill. New per-atom skeleton render path when no prior data + binding present. |
| WB-4b `useWidgetValidation` + `AtomErrorIndicator` | Coexists | **Separate chrome path.** Per LOCK 4d, resolution errors do NOT trigger the red-outline validation chrome. WB-5 introduces a parallel state path (`resolutionErrorsByAtom`) + a parallel indicator component (`AtomResolutionIndicator`) or a discriminated extension of `AtomErrorIndicator`. Not yet locked at the component level — implementation may compose. |
| WB-6 `resolveBinding` | Consumed | **Reused as-is.** Public surface is `resolveBinding(ref, dataContext)`. WB-5's canvas provides the dataContext shape; resolveBinding handles the resolution unchanged. |
| WB-6 `BindingPreviewCard` + `useBindingPreview` | Coexists | **Both surfaces fetch the same view independently.** The inspector card and the canvas both call `executeSavedView` for the same saved_view_id. Phase 1 accepts the duplicate-fetch cost (low — both debounced; both cached at the React-render level). Phase 2 optimization: a single shared cache layer. Out of scope for WB-5. |
| Saved-view substrate (`/api/v1/saved-views/{id}/execute`) | Consumed | **Reused as-is. ZERO new endpoints.** Per WB-6 Area 7 Lock 8a + WB-5 inheritance: canvas consumes `executeSavedView`, no new backend route. |
| Saved-view substrate (cross-tenant masking) | Consumed | **Reused as-is.** `result.permission_mode` + `result.masked_fields` flow through; LOCK 4a (E7) handles the masked-field display. |
| `useDebouncedValue` (`frontend/src/hooks/useDebouncedValue.ts`) | Consumed | **Reused as-is.** Canvas-side fetch orchestrator wraps blob/binding-set changes in a debounce (200ms, matching auto-save + inspector preview-card). |
| `AbortController` pattern | Consumed | **Pattern reuse** from `useWidgetAutoSave.ts`. WB-5 implements its own controller refs (per LOCK 6a + 6b). |

**Touchpoint summary:**

- **Reused:** ComposedWidget signature; atom renderers; AtomRenderer iteration; resolveBinding; useDebouncedValue; AbortController pattern; saved-view substrate.
- **Modified:** WidgetCanvas (adds the fetch orchestrator hook + UX states).
- **Net-new:** `useCanvasPreviewData` hook (canvas-side fetch orchestrator); `AtomSkeleton` per-atom skeleton primitive; canvas error banner + fetching pill; resolution-error state path separate from validation.

---

## 9. Area 8 — Phase 1 scope boundaries

### 9.1 Ships in WB-5

1. **Canvas-side fetch orchestrator** (`useCanvasPreviewData` or similar) — walks bindings_catalog, deduplicates saved_view_ids, fetches each via `executeSavedView`, builds dataContext maps.
2. **Canvas wiring** — `WidgetCanvas` passes `dataContext` to `ComposedWidget` based on per-binding resolution.
3. **Tenant context** = operator's JWT tenant (Lock 2a).
4. **Sample record** = first row for `single_record` iteration (Lock 3a).
5. **Error UX** — atom-level inline (per Lock 4a) + canvas-level banner for network class (Lock 4a) + masked-field lock icon (E7) + manual [Retry] (Lock 4c).
6. **Loading UX** — first-load skeleton (Lock 5a + new `AtomSkeleton` primitive); optimistic stale + shimmer on refresh; canvas-level "Fetching" pill.
7. **Race condition** — per-saved-view AbortController + fetchId ref defense-in-depth (Lock 6a). Per-saved-view fetch dedup.
8. **Resolution-error chrome** separate from validation chrome (Lock 4d).
9. **Source-shape regression gates** per DECISIONS entry 31 — assert: canvas passes dataContext to ComposedWidget; canvas fetch orchestrator uses AbortController; fetchId defense-in-depth; resolutionErrorsByAtom separate from validation errors.
10. **Playwright spec extension** — at least one scenario activating real-data preview against a seeded saved view (`.skip` pending staging seed, per WB-4a + WB-4b + WB-6 precedent).

### 9.2 Defers to Phase 2 / WB-7+

- **Multi-record preview cycling** — Phase 2 if operator demand surfaces (Lock 3a operator-validation gate).
- **Cross-tenant preview verification UX** — Phase 2 (Lock 2a operator-validation gate).
- **Real-time data updates** (WebSocket / polling) — per Original WB Q-15, Phase 2.
- **Shared fetch cache between canvas + inspector card** — Phase 2 optimization.
- **Variant-specific preview** — WB-8 (variant authoring surface itself).
- **Performance optimization for widgets with many bindings** — Phase 2 / post-staging.
- **Auto-retry with backoff** on E4 network errors — Phase 2 if manual [Retry] proves friction.

### 9.3 Explicit non-goals

- **No new backend endpoints.**
- **No new migrations.** Migration head stays at r106.
- **No `BindingRef` schema changes** — clean symmetry preserved per WB-6 Lock 2.
- **No changes to atom renderers.** Per Area 7.
- **No changes to `resolveBinding`.** Per Area 7.
- **No changes to validators.py.** WB-6's validator extensions cover the field. WB-5 is a UX/data-orchestration arc; the composition validator is unchanged.

---

## 10. Area 9 — WB-7 / WB-8 substrate-shape compatibility

### 10.1 The check

WB-5 establishes how `dataContext` flows from canvas to atom render. Downstream sub-arcs:

- **WB-7** = button action authoring (action_ref invocation) + permissions. A button click may want to mutate or navigate with the row's context (e.g., "Open invoice {row.id}"). The button needs `dataContext` access at click-time.
- **WB-8** = variant authoring + variant-driven atom visibility + surface availability. A widget may have a 'glance' variant + 'detail' variant; canvas previews ONE variant at a time; the operator switches.

Does WB-5's dataContext model paint either into a corner?

### 10.2 WB-7 compatibility

**Buttons consuming row context.** ButtonRenderer's onClick handler receives no current access to dataContext — it knows only its own resolvedBindings. WB-5 doesn't change this. WB-7's path is to add an `actionContext` (or extend resolvedBindings semantics) such that the click handler can access the row dict the button was rendered against.

**WB-5 lock compatibility:**

- WB-5's per-row context (per Lock 4c carryover from WB-6) spreads the row dict INTO `dataContext`. WB-7 inherits this: when ButtonRenderer's onClick fires inside a repeater, it can reach `dataContext` directly OR receive the resolvedBindings as a snapshot. WB-7 designs this lookup mechanism; WB-5 doesn't constrain it.

**Corner check:** WB-5 does NOT block WB-7. The `dataContext` substrate is read-only and additive; WB-7 can layer action invocation on top without renaming, restructuring, or repositioning.

### 10.3 WB-8 compatibility

**Variant-switched preview.** WB-8 adds a top-bar variant picker in the canvas; canvas re-renders with `variantId` set; atoms with `visible_in_variants` filter accordingly. WB-5's fetch orchestrator must not refetch on variant change (the underlying saved-view data doesn't change between variants — only the atom subset changes).

**WB-5 lock compatibility:**

- WB-5's fetch is keyed on `saved_view_id`, NOT on `variantId`. Variant changes don't trigger refetch. ✓
- The dataContext per binding stays stable across variant changes. ✓
- The atom-level error chrome (per Lock 4a) is per-atom; atoms hidden in the current variant don't show error chrome. ✓ (Hidden atoms render `null` per `AtomRenderer.tsx:158`).
- The atom-level skeleton (per Lock 5a) is per-atom; hidden atoms have no skeleton either. ✓

**Variant-specific preview** is a Phase 2 question (the WB-8 doc): some widgets may want DIFFERENT bindings per variant. WB-5 explicitly out-of-scopes this (Section 9.2); the substrate accommodates it later because bindings are catalog-keyed.

**Corner check:** WB-5 does NOT block WB-8. Variants and data fetching are orthogonal.

---

## 11. Area 10 — Architectural risks + mitigations

### Risk 1 — Tenant context substrate complexity exceeds investigation lock

**Description:** Lock 2a (operator's JWT tenant) is the simplest path. The hidden complexity is that the widget builder runs in the **tenant API tree** (per `widget-builder-service.ts:8` using `apiClient`) — so the JWT is a tenant JWT, and the tenant is whichever tenant the operator is impersonating (or whichever tenant they're a direct member of). The runtime editor at `/runtime-editor/?tenant=...&user=...` (R-1.6.9) handles impersonation; admin direct access uses admin JWT realm which would NOT work against tenant `/api/v1/saved-views/*` endpoints.

**Severity:** Medium. Affects the operator's first-experience of canvas preview.

**Mitigation:**

- **Document the prerequisite.** WB-5 build prompt clarifies: canvas preview only works when the operator is impersonating a tenant (or logged in as a tenant user). Platform-admin-only access (no impersonation context) → canvas shows the 1-mock-row fallback with an info banner: "Sign in as a tenant user or impersonate one to preview live data."
- **Verify at build time.** WB-5 frontend reads `apiClient` token's realm; if the realm is `platform` (no impersonation), the canvas surfaces the info banner.
- **No new substrate.** The fallback path already exists (`AtomRenderer.tsx:222` 1-mock-row).

### Risk 2 — Error state UX cascades unexpectedly

**Description:** Per-atom error chrome (E1, E2, E5, E7) renders inline. If many atoms have the same error (e.g., all 8 atoms bind to a deleted saved view), the canvas shows 8 ⚠ indicators. Visually noisy.

**Severity:** Low (Phase 1) → Medium (post-staging if 10+ binding widgets ship).

**Mitigation:**

- **Hoist common errors to canvas-level banner.** When N atoms share the same root cause (same saved_view_id deleted, same network error), surface ONE canvas-level banner with severity + count: "8 atoms reference a deleted saved view." Per-atom chrome stays minimal.
- **Phase 1 ships per-atom chrome.** Hoist-on-N is deferred. Operator demand signal after staging informs the Phase 2 refinement.

### Risk 3 — Race condition substrate coexistence with WB-4a auto-save AbortController

**Description:** Two AbortControllers live in the WidgetBuilder mount: one for auto-save (PUT to `/widget-definitions/{slug}/draft`), one (per Lock 6a) for canvas preview fetches (GET to `/saved-views/{id}/execute`). Future refactors could accidentally unify them.

**Severity:** Low. Different controller refs, different request paths.

**Mitigation:**

- **Source-shape regression gate** (per DECISIONS entry 31) asserts that `useCanvasPreviewData` (or equivalent canvas-side hook) introduces its own controller ref symbol distinct from `useWidgetAutoSave`'s.
- Document the separation in the build report.

### Risk 4 — WB-6 "no dataContext" fallback substrate coexistence with WB-5 "fetch failed" rendering

**Description:** `AtomRenderer.tsx:222` falls back to 1-mock-row when `dataContext === undefined`. WB-5's canvas now passes a `dataContext` (so the fallback is bypassed) — BUT when fetch fails for a single saved_view_id while others succeed, the canvas may pass `dataContext = { rows: undefined }` (or omit rows). The 1-mock-row fallback fires for that atom, which is the WRONG semantic — the operator should see ⚠ inline, not a structural mock row.

**Severity:** Medium. The "fetch failed" path needs to be distinguished from the "no fetch ever fired" path.

**Mitigation:**

- **Explicit dataContext flavors.** WB-5's canvas passes one of THREE shapes to ComposedWidget per binding:
  1. `undefined` — when no bindings exist (operator hasn't authored any) OR canvas chose to render placeholder (e.g., initial mount before debounce settled). 1-mock-row authoring fallback applies.
  2. `{ rows, aggregations, total_count, permission_mode, masked_fields }` — when fetch succeeded. Real iteration applies.
  3. `{ rows: [], __error: { code: "fetch_failed" | "view_not_found" | ... } }` — when fetch failed. AtomRenderer dispatches to error chrome (NOT 1-mock-row, NOT real iteration).
- **AtomRenderer.tsx augmentation deferred to WB-5** — discriminator check on `dataContext.__error` before the existing fallback branch.

### Risk 5 — Sample record selection state may need cross-session persistence

**Description:** If Option D (Lock 3a operator-validation gate) lands, "operator pinned row 2 as the sample" needs to persist across page reloads. Today's substrate has no such state.

**Severity:** Phase 1 = N/A (Lock 3a chose A, no pinning UI). Phase 2 = Medium if D lands.

**Mitigation:**

- **Out of scope for WB-5.** If D lands in Phase 2, persist `sampleRecordIndex` in `User.preferences.widget_builder_preview_sample_record_index` (JSONB, per the established preferences pattern from Phase 8 spaces). No new table; no migration; reuses canonical preference-storage path.

### Risk 6 — Fetch orchestrator deduplication missed when bindings reference the same view with different field_paths

**Description:** Two atoms bind to `savedView_X.field_a` and `savedView_X.field_b`. The fetch orchestrator dedupes at saved_view_id level (one fetch). But if a third atom binds to `savedView_X` with `iteration_mode='single_summary'`, the SAME result object can serve all three — different field_path resolution against the same row dict OR aggregations dict. The orchestrator's dedup must be `saved_view_id` only (not `(saved_view_id, field_path)` or `(saved_view_id, iteration_mode)`).

**Severity:** Low. Captured in Lock 6a ("Per-saved-view scope, not per-atom"); the build prompt restates.

**Mitigation:**

- **Build prompt explicit.** Dedup key = `saved_view_id` only. Result serves all bindings with the same view, irrespective of field_path or iteration_mode.

### Risk 7 — Empty bindings_catalog edge case

**Description:** A widget with no bindings (literal-only or no bindings authored yet) should render correctly. The canvas fetch orchestrator must handle `Object.keys(bindings_catalog).length === 0` → no fetches → pass `undefined` dataContext through.

**Severity:** Low. Captured in Risk 4 mitigation.

**Mitigation:**

- Same as Risk 4 — `dataContext === undefined` is the canonical "no bindings / no fetch" signal.

### Risk 8 — Canvas re-render frequency from debounced binding-set changes

**Description:** Every keystroke in the inspector's binding picker mutates the draft blob → AtomInspector's binding update → blob change → canvas re-renders → debouncer schedules fetch. If the debounce isn't on the right boundary, canvas could fire fetches per-keystroke.

**Severity:** Medium. Performance regression risk.

**Mitigation:**

- **Debounce on the binding-set (not on every blob change).** The canvas fetch orchestrator memoizes the set of saved_view_ids in the catalog; only triggers debounce when the **set** changes (added view, removed view). Other blob mutations (atom config edits, atom additions, position changes) don't re-fire fetches. Memoization key: `JSON.stringify(sortedSavedViewIdsFromCatalog)` or equivalent.
- **Build prompt explicit.** The dedup function is the fetch dependency.

### Risk 9 — Single-summary aggregation shape changes across saved-view edits

**Description:** Operator edits saved view from `presentation.mode='stat'` (returns `aggregations.value`) to `presentation.mode='list'` (returns `total_count` only). Bindings with `iteration_mode='single_summary'` would resolve to different aggregation paths. Per WB-6 LOCK 4d this is handled at resolution time; the canvas inherits.

**Severity:** Low. Already handled by WB-6's validator + runtime tolerance.

**Mitigation:** No new mitigation needed at WB-5 scope. Surfaces as E5 (Lock 4a) at the atom chrome.

---

## 12. WB-5 sub-arc execution plan

### Proposed scope

Wire canvas preview to fetch real saved-view data; apply Locks 2a, 3a, 4a–d, 5a, 6a–b. Zero new backend endpoints. Zero migrations. Zero schema changes to `CompositionBlob` / `BindingRef`.

### Files touched

**New (frontend):**

| File | Est. LOC | Role |
|---|---|---|
| `frontend/src/bridgeable-admin/hooks/useCanvasPreviewData.ts` | ~180 | Canvas-side fetch orchestrator. Walks bindings_catalog → dedup saved_view_ids → fetch each via `executeSavedView` with per-view AbortController + fetchId defense-in-depth. Returns `Map<savedViewId, FetchState>` where FetchState ∈ { loading, success(result), error(code, message) }. Debounced via `useDebouncedValue` on `saved_view_ids set` (memo key). |
| `frontend/src/bridgeable-admin/hooks/useCanvasPreviewData.test.ts` | ~280 | Tests: dedup, per-view cancel, fetchId defense, error classification (E1-E7), debounce on set change. |
| `frontend/src/bridgeable-admin/components/widget-builder/AtomSkeleton.tsx` | ~120 | Per-atom skeleton primitive (8 atom types). Shimmer variant prop. |
| `frontend/src/bridgeable-admin/components/widget-builder/AtomSkeleton.test.tsx` | ~80 | Tests: each atom_type's skeleton shape; shimmer on/off. |
| `frontend/src/bridgeable-admin/components/widget-builder/CanvasPreviewBanner.tsx` | ~70 | Canvas-top banner for network errors + fetching pill. [Retry] affordance. |
| `frontend/src/bridgeable-admin/components/widget-builder/CanvasPreviewBanner.test.tsx` | ~60 | Tests: 3 states (idle, fetching, error+retry). |
| `frontend/src/bridgeable-admin/components/widget-builder/AtomResolutionIndicator.tsx` | ~100 | Per-atom resolution-error chrome distinct from `AtomErrorIndicator` (WB-4b validation). Wraps an atom with the ⚠ overlay + tooltip per Lock 4a per-atom rules. Masked-field lock icon variant. |
| `frontend/src/bridgeable-admin/components/widget-builder/AtomResolutionIndicator.test.tsx` | ~90 | Tests: error code → chrome variant mapping. |

**Modified (frontend):**

| File | Est. LOC delta | Change |
|---|---|---|
| `frontend/src/bridgeable-admin/components/widget-builder/WidgetCanvas.tsx` | ~+80 / ~-5 | Accept `previewData` prop OR mount `useCanvasPreviewData(blob)` directly. Compute per-binding dataContext map. Pass derived `dataContext` to `ComposedWidget` (per binding scope). Render `CanvasPreviewBanner`. Wrap children in `AtomResolutionIndicator` when binding errors apply. Render `AtomSkeleton` when first-fetch in progress. |
| `frontend/src/bridgeable-admin/components/widget-builder/WidgetCanvas.test.tsx` | ~+120 | Tests: real-data flow; error states; loading states; cancellation; tenant context implicit. |
| `frontend/src/lib/widget-builder/runtime/AtomRenderer.tsx` | ~+30 | Handle `dataContext.__error` flavor (Risk 4 mitigation). When `__error` present → return null + caller wraps in `AtomResolutionIndicator`. OR alternative: AtomRenderer dispatches to indicator itself. Implementation decision in build. |
| `frontend/src/lib/widget-builder/runtime/AtomRenderer.test.tsx` | ~+50 | Tests: `dataContext.__error` flavor; coexistence with WB-6 1-mock-row fallback. |
| `frontend/src/bridgeable-admin/components/widget-builder/source-shape.test.ts` | ~+40 | Source-shape gates: `useCanvasPreviewData` uses AbortController + latestFetchId pattern; resolutionErrorsByAtom state path separate from validation; canvas passes dataContext to ComposedWidget. |
| `frontend/tests/e2e/widget-builder-canvas.spec.ts` | ~+50 (`.skip` pending staging seed) | 2 new scenarios (15/16): canvas shows real saved-view data; canvas surfaces fetch error + retry. |

**No backend changes.** No migration. No `validators.py` changes. No `composition-blob.ts` schema changes.

### LOC estimate

**Production:** ~660 LOC across 5 new files + 3 modified files.
**Tests:** ~720 LOC across 5 new test files + 3 extended.
**Total:** **~1,380 LOC** WB-5 sub-arc.

**Calibration note per WB-6 lesson** (WB-6 shipped 3.3× midpoint estimate due to operator-as-platform-builder reframe): WB-5's LOC midpoint of ~1,380 reflects:

- A new orchestrator hook (~180 + 280 test) — moderate substrate, WB-6 `useBindingPreview` (~140 + 175 test = ~315) as the precedent. WB-5's orchestrator is ~1.5× because it deduplicates across N views vs. WB-6's single-view scope.
- A new per-atom skeleton primitive (~120 + 80 test) — modest catalog component.
- A new canvas-level banner (~70 + 60 test) — small surface.
- A new resolution-error indicator (~100 + 90 test) — parallel to AtomErrorIndicator (small).
- Modifications concentrated on `WidgetCanvas.tsx` (~+200 net) and `AtomRenderer.tsx` (~+30+50).

Substrate implications surfaced: the discriminated `dataContext.__error` flavor (Risk 4 mitigation) requires explicit treatment in AtomRenderer to coexist with the WB-6 1-mock-row fallback path. The build prompt MUST surface this; the LOC for AtomRenderer (~+30 production + ~+50 test) reflects this.

**Substrate threshold:** if implementation exceeds ~1,700 LOC, a substrate question may be lurking (e.g., AtomResolutionIndicator + AtomSkeleton being collapsible into one wrapper). Surface in build report.

### Sub-arc steps

1. **Author `AtomSkeleton.tsx`** — 8 atom types' skeleton variants. Shimmer prop. Tests.
2. **Author `useCanvasPreviewData.ts`** — orchestrator hook with AbortController + fetchId + per-saved-view dedup. Tests covering Locks 6a, 6b + error classification per Lock 4a.
3. **Author `CanvasPreviewBanner.tsx` + `AtomResolutionIndicator.tsx`** — UX primitives for Lock 4a + Lock 5a.
4. **Modify `WidgetCanvas.tsx`** — mount `useCanvasPreviewData(blob)`; build per-binding dataContext map; pass to `ComposedWidget`; wrap children in error/skeleton indicators per binding state. Tests.
5. **Modify `AtomRenderer.tsx`** — handle `dataContext.__error` flavor; preserve WB-6 1-mock-row fallback for non-error undefined-dataContext path. Tests.
6. **Source-shape regression gates** at `source-shape.test.ts` — per DECISIONS entry 31.
7. **Playwright spec extension** — 2 new `.skip` scenarios.
8. **Build report** surfacing: zero backend changes; locks honored; LOC vs estimate; substrate parity with WB-6; architectural surprises.

### Test substrate

- Unit: useCanvasPreviewData, AtomSkeleton (8 variants), CanvasPreviewBanner, AtomResolutionIndicator.
- Integration: WidgetCanvas with mocked `executeSavedView` returning real-shaped SavedViewResult.
- Cross-substrate: AtomRenderer's `__error` discriminator handling.
- Source-shape: per entry 31.
- Playwright: 2 `.skip` scenarios pending staging seed.

### Migration head

Unchanged at `r106_widget_definitions_published_blob`.

### Canon state

Unchanged at 42.

---

## 13. Operator-validation-sensitive locks tagged

Per DECISIONS entry 26 (investigation-time UX locks revisited by operator experience):

| Lock | Surface | Revisit signal |
|---|---|---|
| 2a (operator's JWT tenant) | Tenant context for preview | Operators reach for "preview against another tenant" — ship Option E (default + override). |
| 3a (first-row sample for single_record) | Sample record selection | Operators reach for "preview row N" — ship Option D (default + pin override). |
| 4a per-atom inline + canvas-level network banner | Error chrome split | Operators report noise → hoist common errors to canvas banner per Risk 2 mitigation. |
| 5a hybrid skeleton + optimistic-stale + shimmer | Loading UX | Shimmer distraction signal → drop shimmer; keep skeleton + optimistic-stale only. |
| 6a per-saved-view fetch dedup | Race condition scope | If operators report stale data despite the substrate, the per-saved-view boundary may need expanding to per-(saved-view, iteration-mode) — defer until signal surfaces. |

All five locks ship the substrate. Revisits don't require substrate rework — they're UX refinements consuming the existing data flow.

---

## 14. Process canon candidates surfaced (NOT filed)

Accumulated for end-of-WB-cycle canon-update arc per CLAUDE.md sonnet-write-permission canon (Sonnet does NOT file DECISIONS entries from build sessions). Eight WB-cycle candidates accumulating across investigations + builds since WB-2; this investigation adds:

**(WB-5-α) `dataContext` flavor discriminators are a substrate question, not a UX question.** When async data substrate has three states (no fetch attempted; fetch succeeded; fetch failed), the disambiguation between them must live in the data shape (e.g., `__error` discriminator) — not in a parallel error state path. Risk 4 surfaced this; the build prompt locks it. Pattern generalizes to any async-data substrate: Page Builder, Document Builder, future canvas surfaces.

**(WB-5-β) Per-substrate fetch dedup keys must be enumerated at investigation time, not inferred at build.** Risk 6 surfaced this. The dedup key (saved_view_id only, not (saved_view_id, field_path, iteration_mode)) is a substrate decision; if mis-keyed, the orchestrator either over-fetches (N atoms each fire) or over-deduplicates (silent correctness bug when two atoms expect different shapes from the same view). Investigation enumerates the key; build honors it.

**(WB-5-γ) Operator-validation-sensitive locks ship the substrate; UX refinements consume the substrate.** Pattern repeated across WB-5 Locks 2a, 3a, 4a, 5a, 6a. Each lock locks the data-flow shape such that future refinements (Option E for tenant; Option D for sample record; hoist-on-N for errors; drop shimmer for loading) compose against the substrate without rework. Canon refinement: investigation-time UX locks should be evaluated for "does this lock the substrate or lock the UX?" The substrate-locking flavor is the appropriate Phase-1 surface; UX-locking flavor is operator-validation-sensitive.

**(WB-5-δ) Cross-arc substrate-coexistence checks are load-bearing.** Risk 3 + Risk 4 each surface a coexistence question with prior arcs (WB-4a auto-save AbortController; WB-6 1-mock-row fallback). Both required explicit treatment. Pattern: any sub-arc introducing async state OR a new state-path-discriminator must enumerate ALL prior arcs that mounted similar substrate and verify coexistence. Investigation-time enumeration prevents build-time discovery.

(Five prior candidates accumulated; total = nine across the WB cycle.)

---

## 15. Architectural surprises during investigation

1. **WidgetBuilder runs in the tenant API tree, not the admin API tree.** `widget-builder-service.ts:8` imports tenant `apiClient`. The widget builder canvas inherits this — calls to `/api/v1/saved-views/{id}/execute` route through the tenant JWT path. This explains why Lock 2a is the natural answer: the operator's authentication ALREADY resolves a tenant; no new resolution path needed. **Implication for Risk 1:** the runtime editor's impersonation substrate (R-1.6.9) is the operator's entry point to the widget builder; platform-admin-only access has no canvas preview without impersonation.

2. **`dataContext` plumbing was already in place at WB-2.** `ComposedWidget.tsx:73` carries `dataContext?: unknown`. WB-6 used it at the AtomRenderer level for the repeater's row context. WB-5's substrate addition is the canvas-side **fetch orchestrator** + the discriminated `__error` flavor — NOT a new prop signature. Substrate maturity surprise; reduces LOC vs naïve estimate.

3. **`useBindingPreview` (WB-6) is the precedent for `useCanvasPreviewData` (WB-5).** Same fetch shape (`executeSavedView`); same debounce (200ms); same `latestFetchId` defense-in-depth pattern; same cancellation semantics. WB-5 generalizes from one-binding to N-binding scope. The LOC estimate for `useCanvasPreviewData` (~180) is ~1.3× useBindingPreview's ~140 — substrate-proportional growth, not exponential. This is the kind of healthy substrate evolution WB-6's investigation called for ("the hooks layer between substrate and consumer is the right boundary").

4. **WB-6's 1-mock-row authoring fallback path MUST stay reachable.** It's not deprecated by WB-5; it's the no-bindings / pre-fetch / canvas-just-mounted state. Three flavors of dataContext (per Risk 4 mitigation) coexist explicitly. The build prompt must surface this; otherwise a "let me clean up the fallback" patch could regress operator UX during initial widget authoring.

5. **Source-shape regression gates per DECISIONS entry 31 apply naturally.** AbortController name, fetchId ref name, resolutionErrorsByAtom state path name, dataContext-passed-to-ComposedWidget, debounce dependency key — all are load-bearing source shapes. WB-5 gate count: ~5–6 entries in source-shape.test.ts. Pattern matches FF + WB precedent.

6. **Cross-tenant masking surfaces as a render-time UX, not a substrate question.** The substrate (`permission_mode='cross_tenant_masked'` + `masked_fields` list) is built and live. WB-5's Lock 4a (E7) treats the masked sentinel as an atom-level chrome variant (lock icon + tooltip) — substrate-neutral. Phase 1 ships cross-tenant binding scope as **operator-implicit** per WB-6 Lock 7a (tenant-scoped binding); WB-5 doesn't change this scope, only renders the chrome correctly when fetched data happens to include masked fields.

7. **No new endpoints required.** Confirmed against all 8 saved-view endpoints. `executeSavedView(id)` covers WB-5's needs completely. The aggregation shape (`result.aggregations`) + the masked sentinel (`__MASKED__`) + the masked_fields list + the permission_mode discriminator — every data point WB-5 needs is on the existing wire.

---

## 16. Closing summary

**Substrate audit verdict:** Canvas preview substrate is partially in place via WB-6. The fetch orchestrator is the missing piece. Zero new backend surface; zero schema changes; zero migrations.

**Locks summary:**

| # | Lock | Operator-validation-sensitive |
|---|---|---|
| 2a | Operator's JWT tenant for preview context | ✓ |
| 3a | First row for `single_record` sample | ✓ |
| 4a | Atom-level inline + canvas-level network banner | ✓ |
| 4b | Non-blocking rendering | (architecture) |
| 4c | Manual [Retry] for network; passive recovery for atom-level | (architecture) |
| 4d | Resolution errors separate chrome from validation | (architecture) |
| 5a | Skeleton + optimistic stale + shimmer hybrid | ✓ (shimmer) |
| 6a | Per-saved-view AbortController + fetchId defense-in-depth | (architecture) |
| 6b | Coexistence with WB-4a auto-save AbortController | (architecture) |

**LOC estimate:** ~1,380 LOC across 5 new + 3 modified files. Substrate threshold: ~1,700.

**Architectural surprises:** 7 enumerated. Notable: substrate maturity (WB-6 substrate covers more than its scope claimed); WidgetBuilder lives in tenant API tree (clarifies tenant context decision); 1-mock-row fallback must stay reachable.

**Process canon candidates surfaced:** 4 new (α – δ) — accumulating with prior candidates from WB-2 through WB-6 toward an end-of-WB-cycle canon-update arc. Not filed by this Sonnet session.

**WB-5 dispatches against the locks in this investigation.** WB-7 (button actions + permissions) and WB-8 (variants) follow with their own investigations.

---

## Appendix — file references cited

| Path | Line | Purpose |
|---|---|---|
| `frontend/src/bridgeable-admin/components/widget-builder/WidgetCanvas.tsx` | 199-205 | Canvas mounts ComposedWidget with no dataContext (audit finding). |
| `frontend/src/lib/widget-builder/runtime/ComposedWidget.tsx` | 73, 122 | dataContext signature carries through (WB-2 forward-compat). |
| `frontend/src/lib/widget-builder/runtime/AtomRenderer.tsx` | 151-156, 198-222 | dataContext flow; 1-mock-row authoring fallback path. |
| `frontend/src/bridgeable-admin/components/widget-builder/binding-picker/useBindingPreview.ts` | 51-145 | WB-6 precedent for canvas-side fetch orchestrator. |
| `frontend/src/bridgeable-admin/hooks/useWidgetAutoSave.ts` | 7-21 | AbortController pattern reference. |
| `frontend/src/services/saved-views-service.ts` | 86-93 | `executeSavedView` signature (tenant-implicit). |
| `backend/app/api/routes/saved_views.py` | 402-444 | `/execute` endpoint reads `current_user.company_id`. |
| `backend/app/services/saved_views/executor.py` | 105, 151, 421 | Cross-tenant masking sentinel. |
| `frontend/src/types/saved-views.ts` | 193-200 | `SavedViewResult` shape. |
| `frontend/src/lib/widget-builder/types/composition-blob.ts` | 61-72, 104 | BindingRef + bindings_catalog shape. |
| `frontend/src/hooks/useDebouncedValue.ts` | — | Reusable debounce primitive. |
| `docs/investigations/2026-05-22-widget-builder-bindings.md` | 521-578 | WB-6 / WB-5 seam lock. |
| `docs/investigations/2026-05-21-widget-builder.md` | various | Original WB investigation. |
| DECISIONS.md entry 26 | — | Investigation-time UX locks can be refined by operator experience (operator-validation-sensitive tagging precedent). |
| DECISIONS.md entry 31 | — | Source-shape regression gate pattern. |
| DECISIONS.md entry 38 | — | Investigations of stateful operations must model cumulative-delta-vs-per-tick-state (lineage for async cancellation modeling). |
| DECISIONS.md entry 41 | — | @dnd-kit transform model is position-only (referenced for substrate-shape canon style). |
