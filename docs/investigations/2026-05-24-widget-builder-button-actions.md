# Widget Builder — Button Actions (WB-7) read-only investigation

**Arc**: 2026-05-24-widget-builder-button-actions
**Type**: Read-only investigation (ZERO production code, ZERO commits beyond this doc + STATE.md)
**HEAD verified**: `07b183b` (WB-5 build — Canvas preview wiring + 3-flavor discriminator)
**Predecessor investigations**: WB-original `docs/investigations/2026-05-21-widget-builder.md` (Area 3 action vocabulary lock); WB-6 `docs/investigations/2026-05-22-widget-builder-bindings.md` (BindingRef triad, picker substrate); WB-5 `docs/investigations/2026-05-23-widget-builder-canvas-preview.md` (dataContext + 3-flavor discriminator)

---

## 1. Context

WB-7 substantiates the WB-3 ButtonRenderer onClick no-op (`frontend/src/lib/widget-builder/runtime/atoms/index.tsx:562-566`) and the WB-4b ButtonInspector disabled action picker placeholder (`frontend/src/bridgeable-admin/components/widget-builder/inspectors/AtomInspectorDispatch.tsx:780-786`). The action vocabulary was locked in the original WB investigation at Q-17 to five verbs: `navigate`, `open_focus`, `open_peek`, `mutate`, `trigger_workflow`. The Pydantic `ButtonConfig.action_kind` Literal mirrors that vocabulary (`backend/app/schemas/widget_composition.py:371-377`) and the TypeScript `ButtonActionKind` type matches (`frontend/src/lib/widget-builder/types/composition-blob.ts:215-220`).

WB-7's task: lock the action substrate shape and propose execution. After WB-5 closed the canvas preview seam, WB cycle remaining is WB-7 → WB-8 (variants) → end-of-cycle canon-update arc.

**Major shape-shifting discovery before any decisions are locked**: an R-4.0 button action substrate already exists at `frontend/src/lib/runtime-host/buttons/` (~600 LOC across types + dispatch + parameter-resolver + RegisteredButton + tests + 3 example registrations). It ships **navigate / open_focus / trigger_workflow / create_vault_item / run_playwright_workflow** with a complete dispatch table, parameter binding context (7 sources), confirm-before-fire Dialog UX, success behavior (stay / navigate / toast), and edge-panel auto-close coordination. The vocabulary overlaps WB-7's lock on three verbs, diverges on two (R-4.0 has `create_vault_item` + `run_playwright_workflow`; WB-7 has `open_peek` + `mutate`). R-4.0's authoring path is code-only — registrations live in `frontend/src/lib/visual-editor/registry/registrations/buttons.ts`; **no admin authoring UI exists** for R-4 button contracts. WB-7's action picker would be the FIRST admin authoring surface for action contracts on the platform.

This reshapes the investigation: WB-7 must decide whether to (a) consume R-4.0 substrate verbatim and inherit its action vocabulary asymmetry, (b) extend R-4.0 with `open_peek` + `mutate` handlers and become the canonical action substrate, or (c) ship a WB-scoped parallel dispatcher and accept duplication. Areas 1 → 3 below produce that decision.

---

## 2. Area 1 — Per-verb action substrate audit (LOAD-BEARING; AUDIT-FIRST)

For each of the five action verbs locked at the original WB Q-17, this section enumerates the substrate that exists today, its maturity tier, and what WB-7 would need to do to dispatch the verb at click-time.

### 2.1 Audit-first methodology

Per WB-6 lesson + WB-5 validation, decisions are locked AFTER substrate maturity is enumerated, not before. Maturity tiers (canonical from WB-6/WB-5):

- **MATURE**: production-grade endpoint or context API, in-tenant-tree mount, tenant isolation enforced, ≥1 existing production consumer. WB-7 consumes without modification.
- **BUILT-BUT-DORMANT**: substrate exists but not exposed to admin authoring, OR exists with limited consumer surface, OR exists with no convention-binding shape that WB-7 would lock. WB-7 consumes and activates / shapes.
- **MISSING**: no substrate. WB-7 either ships its own, defers the verb, or shapes the substrate as a precursor.

### 2.2 R-4.0 button action substrate (substrate-of-substrates)

Before per-verb audit, the R-4.0 substrate must be characterized — three of WB-7's five verbs overlap it.

**Files**: `frontend/src/lib/runtime-host/buttons/types.ts` (141 LOC); `action-dispatch.ts` (271 LOC, dispatch table for 5 R-4 verbs); `parameter-resolver.ts` (151 LOC, 7 binding sources); `RegisteredButton.tsx` (352 LOC, click target component with confirm Dialog + toast + edge-panel coordination); `RegisteredButton.test.tsx`; `action-dispatch.test.ts`; `parameter-resolver.test.ts`.

**Contract surface** (`types.ts:101-121`):

```ts
interface R4ButtonContract {
  actionType: R4ActionType
  actionConfig: ActionConfig
  parameterBindings: ParameterBinding[]
  confirmBeforeFire?: boolean
  confirmCopy?: string
  successBehavior?: SuccessBehavior  // 'stay' | 'navigate' | 'toast'
  successNavigateRoute?: string
  successToastMessage?: string
  closePanelAfterFire?: boolean
}
```

**Parameter binding sources** (`types.ts:68-77`): `literal | current_user | current_tenant | current_date | current_route_param | current_query_param | current_focus_id`. Resolver runs at click-time via `resolveBindings(bindings, ctx)` → `Record<paramName, ResolvedValue>`. Missing context returns null gracefully (`RegisteredButton.tsx:99-122` — `useFocusOptional` + `useAuthOptional` for admin-tree preview pages).

**Dispatch table** (`action-dispatch.ts:227-233`):

| R-4 verb | Handler | Substrate consumed |
|---|---|---|
| `navigate` | `handleNavigate` | react-router `useNavigate()` via `deps.navigate(route)`; template substitution for `{paramName}` placeholders |
| `open_focus` | `handleOpenFocus` | `useFocus().open(focusId, { params })` (admin tree no-op via `useFocusOptional`) |
| `trigger_workflow` | `handleTriggerWorkflow` | `POST /workflows/{workflowId}/start` with `{ trigger_context: { source: "r4_button", ...resolved } }` |
| `create_vault_item` | `handleCreateVaultItem` | `POST /vault/items` with `{ item_type, ...resolved }` |
| `run_playwright_workflow` | `handleRunPlaywrightWorkflow` | `POST /playwright-scripts/{scriptName}/run` with `{ inputs: resolved }` |

**Maturity**: MATURE for navigate / open_focus / trigger_workflow. R-4.0 + R-5.0.x have shipped against staging, including edge-panel coordination + null-safe useFocus/useAuth for admin previews. `RegisteredButton.tsx:131-138` reads `entry.metadata.extensions.r4` from the visual-editor registry — admin authoring of R-4 contracts today happens only via code edits to registration files (no UI).

**Cross-substrate dependency the R-4 substrate makes load-bearing for WB-7**: the dispatcher takes `deps: DispatchDeps` (`{ navigate, openFocus }`) bound from React hooks at click-time. WB-7's ButtonRenderer is rendered inside the widget builder admin tree (no FocusProvider, no PeekProvider, no AuthProvider for tenant) AND inside the tenant runtime (Pulse, Spaces, dashboards — all of which DO mount the providers). The R-4.0 `useFocusOptional` / `useAuthOptional` pattern is the canonical defense; WB-7 must follow it for any new handlers (open_peek + mutate).

### 2.3 Verb 1: `navigate`

**Maturity**: MATURE — covered verbatim by R-4.0 `handleNavigate`.

**Substrate citations**:
- `frontend/src/lib/runtime-host/buttons/action-dispatch.ts:72-90` — handler implementation
- React-router `useNavigate` mounted in tenant tree at `frontend/src/App.tsx`; admin tree at `frontend/src/bridgeable-admin/BridgeableAdminApp.tsx`
- `RegisteredButton.tsx:98` — `navigate = useNavigate()`
- Existing consumers: 3 example button registrations at `frontend/src/lib/visual-editor/registry/registrations/buttons.ts` + production placement consumers via `CompositionRenderer` extended in R-4.0

**Per-tenant scoping**: react-router operates on the deployed-bundle URL. Tenant-scoping happens at the route-resolution layer (`getCompanySlug` etc.). WB-7 `navigate` action_config carries a route string (relative or absolute); the existing tenant route discipline applies.

**API/endpoint state**: N/A — pure client-side navigation.

**WB-7 implication**: zero substrate construction. WB-7 reuses `handleNavigate` directly OR maps `ButtonConfig.action_config.route + action_config.params` into `dispatchAction("navigate", { route }, resolved, deps)`.

### 2.4 Verb 2: `open_focus`

**Maturity**: MATURE — covered verbatim by R-4.0 `handleOpenFocus`.

**Substrate citations**:
- `frontend/src/lib/runtime-host/buttons/action-dispatch.ts:93-112` — handler implementation
- `frontend/src/contexts/focus-context.tsx:114-156` — `FocusContextValue.open(id, options?)` API
- `frontend/src/contexts/focus-registry.ts:188-238` — `registerFocus(config)` + `FocusConfig.id` discriminator; in-memory registry, admin-introspectable via `listFocusConfigs()`
- `frontend/src/contexts/peek-context.tsx` parallels the shape but is a different verb (see 2.5)
- Existing consumers: `open-funeral-scheduling-focus` button registration at `buttons.ts:139`

**Per-tenant scoping**: FocusProvider mounted only in tenant tree (`App.tsx`); admin tree (`BridgeableAdminApp.tsx`) does NOT mount it. `useFocusOptional` returns null in admin; `RegisteredButton.tsx:243` falls back to `(() => undefined)` for the dispatcher. **This means WB-7 canvas preview cannot actually open a Focus** — the preview is structural; opening only works in tenant-runtime placement.

**API/endpoint state**: N/A — pure client-side Focus orchestration.

**Focus catalog discoverability**: `listFocusConfigs()` returns all in-memory registrations. The admin action picker can enumerate this for the operator. Concrete production focuses: `funeral-scheduling`, `arrangement-scribe`, etc. (registry seeded via `registerFocus(...)` calls at module-import time).

**WB-7 implication**: zero substrate construction. WB-7 picker enumerates `listFocusConfigs()` for the operator. action_config.focusId stored on the BlobButton's action_config. RegisteredButton's `useFocusOptional` admin-tree path is the canonical pattern; ButtonRenderer at the widget-builder canvas adopts it.

### 2.5 Verb 3: `open_peek`

**Maturity**: BUILT-BUT-DORMANT — substrate exists with the full context API, but R-4.0 did not wire it.

**Substrate citations**:
- `frontend/src/contexts/peek-context.tsx:66` — `PeekContextValue.openPeek({...})` API
- `frontend/src/contexts/peek-context.tsx:174` — `openPeek` callback in PeekProvider
- `frontend/src/contexts/peek-context.tsx:257-272` — `usePeek()` strict + `usePeekOptional()` null-safe variants (same architectural pattern as Focus)
- `frontend/src/App.tsx:564-572` — `<PeekProvider>` mounted in tenant tree only
- 6 entity-type peek renderers per CLAUDE.md §4 "Peek panels (follow-up 4, April 2026)": `fh_case | invoice | sales_order | task | contact | saved_view`
- Per-entity backend dispatcher at `backend/app/services/peek/builders.py` (`GET /api/v1/peek/{entity_type}/{entity_id}`)

**Per-tenant scoping**: peek substrate is tenant-scoped via `company_id` filter in each per-entity builder; PeekProvider is tenant-tree-only.

**API/endpoint state**: GET endpoint mature; consumed today by 4 trigger surfaces (command bar tiles, briefing pending_decisions, SavedViewRenderer, triage related_entities panel).

**WB-7 implication**: substrate is fully mature on the consumer side. WB-7 adds an `open_peek` dispatcher handler that calls `peek.openPeek({ entityType, entityId, ... })`. Admin-tree fallback follows the R-4.0 useFocusOptional pattern (`usePeekOptional` exists; same shape). action_config carries `entity_type` + `entity_id`-binding (resolved from current row).

### 2.6 Verb 4: `mutate`

**Maturity**: MISSING (generic) / MATURE (per-entity).

**Substrate citations**:
- Per-entity PATCH endpoints exist for at least 14 routes: `tasks.py:187`, `sales.py:446`, `sales.py:527`, `cases.py:335`, `cases.py:354` (status), `vault.py:157`, etc.
- Bounded-state-flip canonical primitive: `backend/app/api/routes/widget_data.py:353` — `POST /api/v1/widget-data/anomalies/{anomaly_id}/acknowledge`. This is the §12.6a reference implementation. Audit-logged (`anomalies_widget_service.py:209` calls `audit_service.log_action`). Tenant isolation re-validated (`anomalies_widget_service.py` per docstring).
- NO generic "patch row by saved_view_id + row_id + field" endpoint exists. No `MutateRef` substrate; no abstraction over per-entity endpoints.

**Per-tenant scoping**: per-entity. Each PATCH endpoint enforces `current_user.company_id` filter.

**API/endpoint state**: per-entity mature; generic substrate missing.

**Critical observation — §12.6a discipline**: `DESIGN_LANGUAGE.md §12.6a` (per the original WB Q-17 cross-check) bounds widget mutates to "bounded state flips" (acknowledge anomaly, mark read). Anything more complex routes to Focus. The mutate verb's substrate question is therefore NOT "build a generic field-patch endpoint" — it is "wire the small set of canonical state-flip endpoints (acknowledge anomaly, mark-read, status-flip) into a dispatcher contract."

**WB-7 implication**: the mutate verb has substrate shape but no canonical authoring surface. Three responses, see Area 9:
- **(a) Phase 1 ships acknowledge-anomaly only** — single concrete handler that calls the existing endpoint. Operator picks "anomaly_acknowledge" from a small list of declared mutate kinds. Substrate-shape compatibility with future state-flip endpoints (mark-read, status-flip) trivial.
- **(b) Defer mutate verb entirely to WB-7.x** — Phase 1 ships 4 verbs (navigate, open_focus, open_peek, trigger_workflow); mutate dispatcher activates post-staging when concrete operator demand surfaces.
- **(c) Ship a generic mutate substrate with per-saved-view writeback semantics** — over-scoped for Phase 1; punts to a separate substrate arc.

The Pydantic + TypeScript shapes for mutate are already in place (action_kind Literal allows `"mutate"`; action_config is `Dict[str, Any]`). Phase 1 dispatcher decision is separable from the schema decision.

### 2.7 Verb 5: `trigger_workflow`

**Maturity**: MATURE — covered verbatim by R-4.0 `handleTriggerWorkflow`.

**Substrate citations**:
- `frontend/src/lib/runtime-host/buttons/action-dispatch.ts:115-145` — handler implementation
- `backend/app/api/routes/workflows.py:379-404` — `POST /api/v1/workflows/{workflow_id}/start` endpoint; validates tenant availability via `workflow_engine.get_active_workflows_for_tenant`; passes `trigger_context` + `initial_inputs`; returns serialized run + run_steps
- Workflow registry: `workflows` table (~50+ rows across tier 1 / 2 / 3 / 4 — accounting agents migrated into workflows in Phase 8b-8d.1; FH-vertical workflows; manufacturing-vertical workflows). All tenant-scope-aware via `scope ∈ {core, vertical, tenant}` (Workflow Arc Phase 8a)
- Existing R-4 consumer: `trigger-month-end-close-workflow` button registration at `buttons.ts:168`

**Per-tenant scoping**: backend `workflow_engine.get_active_workflows_for_tenant(db, company_id, vertical=vert)` enforces visibility. 404 returned for unavailable workflows.

**API/endpoint state**: production-mature endpoint. ~50 active workflows per tenant.

**Workflow catalog discoverability**: WB-7 picker needs to enumerate workflows the operator can trigger. Question: which workflows are "user-triggerable" vs. only scheduled-trigger workflows? Per `workflow_engine.get_active_workflows_for_tenant`, the result is "available to tenant" — but a workflow whose trigger_type is `time_of_day` may not make sense as a button target. WB-7 picker could filter to `trigger_type ∈ {manual, event, ...}` OR show all and trust operator to pick a sensible one.

**WB-7 implication**: zero substrate construction. WB-7 picker enumerates available workflows via `GET /workflows?...` (existing list endpoint). action_config carries `workflowId`. Parameter bindings carry the workflow's input shape (today best-effort; long-term, workflow input schema introspection could power the picker).

### 2.8 Per-verb maturity matrix

| Verb | Maturity | R-4.0 dispatch | Phase 1 action |
|---|---|---|---|
| navigate | MATURE | ✓ verbatim | Consume R-4.0 |
| open_focus | MATURE | ✓ verbatim | Consume R-4.0 |
| open_peek | BUILT-BUT-DORMANT | ✗ NEW handler | Add handler (~30 LOC); consume PeekContext |
| mutate | MISSING-GENERIC / MATURE-PER-ENTITY | ✗ Phase 1 ships acknowledge-anomaly only | NEW handler (~50 LOC) calling existing acknowledge endpoint |
| trigger_workflow | MATURE | ✓ verbatim | Consume R-4.0 |

**Audit conclusion**: Phase 1 ships **all 5 verbs** with minimal NEW substrate (~80 LOC of dispatcher additions). R-4.0's existing 3 verbs consumed verbatim; open_peek + mutate (anomaly-acknowledge variant) ship as new R-4.x-equivalent handlers. The mutate verb's other state-flip handlers (mark-read, status-flip) defer to WB-7.x.

---

## 3. Area 2 — ActionRef substrate shape (LOAD-BEARING)

### 3.1 Current state

Backend Pydantic `ButtonConfig` (`widget_composition.py:353-383`) declares:

```python
class ButtonConfig(BaseModel):
    label: Optional[str] = None
    variant: Optional[Literal["primary", "secondary", "ghost", "destructive"]] = "secondary"
    size: Optional[Literal["sm", "md", "lg"]] = "md"
    icon_name: Optional[str] = None
    action_kind: Literal["navigate", "open_focus", "open_peek", "mutate", "trigger_workflow"] = "navigate"
    action_config: Dict[str, Any] = Field(default_factory=dict)
    action_ref: Optional[str] = None  # WB-7 action picker placeholder
```

TypeScript `ButtonConfig` (`composition-blob.ts:231-242`) mirrors. The current shape stores `action_kind` + free-form `action_config: Dict` + optional `action_ref: str`.

### 3.2 The structural decision

The locked Q-17 + Q-18 contract says actions carry "a structured action ref similar to Q-7's BindingRef." This is the symmetry question — should `ActionRef` mirror `BindingRef`'s patterns (canonical primitive + discriminator) or stay inline on the button config?

**4+ options enumerated:**

- **A — Inline discriminated union on ButtonConfig** (current default if action_config is given per-verb shape). `action_kind` is the discriminator; `action_config` per kind enforced via Pydantic `model_validator`. No separate `ActionRef` primitive. action_ref field deleted.
- **B — Catalog-keyed ActionRef matching BindingRef shape**. New `actions_catalog: Record<actionId, ActionRef>` on CompositionBlob (parallel to `bindings_catalog`); button config carries `action_ref: actionId`. Each ActionRef is a tagged union per `action_kind`. Inline action_kind + action_config on the button retired in favor of catalog.
- **C — Inline + per-action-type TypeScript discriminated unions + per-kind Pydantic models** (hybrid of A's location with B's per-kind schemas). ActionConfig stays on ButtonConfig but is typed by `NavigateActionConfig | OpenFocusActionConfig | OpenPeekActionConfig | MutateActionConfig | TriggerWorkflowActionConfig` discriminated unions.
- **D — Action chain (Array<ActionRef>)** — one button fires multiple actions in sequence. Catalog-keyed.
- **E — Single ActionRef + reusable action library** (actions defined separately like saved views; button references action by ID). Adds an `actions` substrate parallel to saved_views.

### 3.3 Tradeoffs

**A (inline discriminated union)**:
- (+) Minimum LOC. Pydantic `model_validator` per action_kind narrowing.
- (+) Backward-compat with current shape (which already ships `action_kind` + `action_config` inline).
- (+) Mirrors `chrome` field's "everything inline" convention per the F-3.1a discovered canon (DECISIONS 2026-05-19 PM, off-by-one column index entry's adjacent ChromeBlob canon).
- (−) action_kind + action_config split is awkward for picker UX (operator changes verb → must clear action_config).
- (−) Diverges from BindingRef's catalog-keyed shape. Symmetry argument loses.

**B (catalog-keyed ActionRef)**:
- (+) Symmetric with BindingRef per the original WB Q-17 lock's stated intent.
- (+) Future-proof for action chains (catalog reuse).
- (+) Two buttons can share the same action definition (e.g. "open invoice peek" used in 3 atoms across a widget).
- (−) More LOC: new ActionRef primitive + catalog field + atom_ref-style indirection.
- (−) Operator authoring surface needs to navigate catalog (find action by id, edit-in-place, etc.).
- (−) Migration cost: existing `action_kind` + `action_config` inline fields would need backfill OR coexist forever.

**C (inline + per-kind discriminated unions)**:
- (+) Type-safe per-kind config without catalog overhead.
- (+) Backward-compat with current Dict[str, Any].
- (−) Verbose Pydantic / TypeScript declarations.
- (−) Doesn't deliver BindingRef-style symmetry; symmetry argument still loses.

**D (action chain)**:
- (+) Powerful for compound interactions.
- (−) ZERO operator demand surfaced in WB-original or WB-6 investigations. Premature substrate per WB-6 lesson (3-flavor discriminator overgeneralization).
- (−) Substrate-shape forking risk per Area 11.

**E (reusable action library)**:
- (+) Maximum reuse + DRY.
- (−) Massive scope expansion; net-new admin authoring surface (manage Action records).
- (−) Premature for Phase 1 — operator demand absent.

### 3.4 LOCK 2a — Option C (inline + per-kind discriminated unions) for Phase 1

**Decision**: WB-7 ships **inline `action_config` typed by discriminated union per `action_kind`**. The `action_ref?: str` placeholder field is RETIRED (`action_ref` was a WB-3/4b forward-compat slot; never populated in production; can be deleted from both TypeScript + Pydantic + atom-tree-helpers in WB-7).

**Per-kind action_config shapes** (matching R-4.0 ActionConfig where verbs overlap):

```ts
// TypeScript
type ActionConfig =
  | { kind: "navigate"; route: string; params?: ParameterBinding[] }
  | { kind: "open_focus"; focus_id: string; params?: ParameterBinding[] }
  | { kind: "open_peek"; entity_type: PeekEntityType; entity_id_binding: string }
  | { kind: "mutate"; mutate_kind: "anomaly_acknowledge"; target_id_binding: string }
  | { kind: "trigger_workflow"; workflow_id: string; params?: ParameterBinding[]; confirm?: boolean; confirm_copy?: string }
```

Pydantic mirror as a `Annotated[Union[...], Discriminator("kind")]` (Pydantic 2.x supports). The `kind` field on action_config matches `action_kind` on the button config — redundant but kept for Pydantic's discriminator inference (drop one if cleaner).

**Rationale for Option C over Option B**:
- BindingRef-style catalog-keyed indirection serves a real need for bindings: many atoms reference the same field_path; catalog deduplicates. Actions exhibit different cardinality — each button has at most one action; reuse across buttons is rare in Phase 1 widgets.
- The original WB Q-17 lock says "structured action ref similar to Q-7's BindingRef" — "similar to" means typed + discriminated, not necessarily catalog-keyed. Option C is structurally faithful without paying the indirection cost.
- BackCompat: existing TypeScript / Pydantic `action_kind` + `action_config: Dict[str, Any]` validates today against Option C's narrower types via Pydantic model_validator. Migration is type-tightening, not schema change.

**Symmetry cross-substrate check** (per the WB-6 lock 3a + DECISIONS entry 28 cross-substrate HOC audit):

| Layer | Where it lives | Phase 1 shape |
|---|---|---|
| TypeScript runtime | `frontend/src/lib/widget-builder/types/composition-blob.ts:215-242` | Discriminated union per kind; lock 2a |
| Pydantic backend | `backend/app/schemas/widget_composition.py:353-383` | Discriminated union via `Annotated[Union, Discriminator("kind")]`; lock 2a |
| Backend validator | `backend/app/services/widget_definitions/...` | Per-kind validation (focus_id must exist in registry mirror; workflow_id must be available to tenant; mutate_kind must be in canonical list; entity_type must be one of 6 peek types) |

All three must agree per WB-2 + WB-4b + WB-6 symmetry canon. WB-7 ships the symmetry audit as a build-deliverable.

### 3.5 Operator-validation-sensitive tag

Lock 2a is **NOT** operator-validation-sensitive — it's architecturally determined. Pre-staging operator feedback on the picker UX (Area 4) may surface that operators want shared actions across multiple buttons (Option B's intent), at which point Phase 2 can layer a catalog on top WITHOUT breaking Phase 1 shapes (the catalog becomes an alternative authoring path; inline stays canonical for single-use).

### 3.6 Action chain — KNOWN GAP for Phase 1

Option D (action chains) is **explicitly out of scope** for Phase 1 per the per-button-at-most-one-action default. If chain demand surfaces post-staging, the substrate change is:
- Replace `action_config: ActionConfig` with `action_chain: ActionConfig[]`
- Pydantic + TypeScript narrow the chain to `len ∈ [1, N]`
- Runtime dispatcher invokes handlers sequentially; aborts on first error

Phase 1 dispatcher does NOT need to know about chains; that's a non-breaking forward extension.

---

## 4. Area 3 — Action dispatch runtime substrate (LOAD-BEARING)

### 4.1 The structural decision

When a button is clicked, where does dispatch happen and what context flows? Three sub-questions:

**(a) Dispatch location**: ButtonRenderer-internal? AtomRenderer? ComposedWidget? Centralized at widget root?
**(b) Reuse R-4.0 dispatch vs. ship WB-scoped dispatch**: does WB-7 import `dispatchAction` from `runtime-host/buttons/action-dispatch.ts`, OR ship a parallel dispatcher inside `lib/widget-builder/runtime/`?
**(c) Action context flow**: what reaches the dispatcher at click-time (the current row dict from `dataContext`, the binding context for parameter resolution, the React-hook deps)?

### 4.2 Audit findings

**ButtonRenderer's current onClick** (`atoms/index.tsx:562-566`):
```tsx
onClick={(e) => {
  e.stopPropagation()
  // WB-7: dispatch config.action_kind + action_config / config.action_ref. No-op in Phase 1.
}}
```

It has access to `atom`, `config`, `resolvedBindings`. It does NOT have access to `dataContext` — per `AtomRenderer.tsx:320-323`:

```tsx
const baseProps = {
  atom,
  resolvedBindings,
}
```

`baseProps` does NOT propagate `dataContext`. This is a **substrate gap for WB-7**: the click handler needs the row dict for parameter resolution (e.g. `entity_id_binding: "{row.id}"` → resolve against the current per-row context). WB-7 must extend `baseProps` to pass `dataContext` through to ButtonRenderer (and potentially to other atoms that might benefit later).

**R-4.0's dispatch flow** (`RegisteredButton.tsx:183-277`):
1. Click handler builds `BindingContext` from React hooks (`useAuth`, `useParams`, `useSearchParams`, `useFocus`).
2. `resolveBindings(contract.parameterBindings, ctx)` → `Record<paramName, ResolvedValue>`.
3. `dispatchAction(actionType, actionConfig, resolved, { navigate, openFocus })` → `Promise<R4DispatchResult>`.
4. Success/error toast + successBehavior + edge-panel close coordination.

R-4.0's resolver reads from React hooks at click-time. The 7 binding sources (literal / current_user / current_tenant / current_date / current_route_param / current_query_param / current_focus_id) cover all R-4 verbs. **None of them is `current_row`** — R-4.0 buttons were not designed for row-iterated contexts (the example registrations are page-level buttons like "Open funeral scheduling focus" with no row context).

WB-7 adds an **8th binding source**: `current_row` — resolves against the per-row dataContext synthesized by the repeater atom (per WB-5 dataContext flavors). This is the substrate extension for embedded buttons in lists.

### 4.3 Options enumerated

**Option A — Reuse R-4.0 dispatcher; extend it with open_peek + mutate handlers + current_row binding source.**
- (+) Single dispatcher across runtime-host buttons + widget-builder buttons.
- (+) Open_peek + mutate handlers benefit the runtime-host substrate too.
- (+) ~80 LOC of new handlers + 1 new binding source.
- (−) Cross-substrate coupling: WB depends on `lib/runtime-host/buttons/` directly.
- (−) Some R-4 contract fields (closePanelAfterFire, edge-panel coordination) are extraneous for WB-7 (composed widgets don't sit inside edge panels by default, though they can).

**Option B — Ship a parallel WB-scoped dispatcher.**
- (+) Substrate independence; no coupling.
- (−) ~250 LOC of duplication for the 3 overlapping verbs.
- (−) Diverging code paths to maintain.
- (−) When R-4.x or WB-7.x adds a new verb, both substrates need the patch.

**Option C — Refactor R-4.0 into a shared library; both runtime-host buttons + widget-builder buttons consume.**
- (+) Long-term canonical shape.
- (+) Single source of truth.
- (−) Refactor scope. R-4.0's RegisteredButton is the click target wrapper + button-registry consumer; widget-builder's ButtonRenderer is the composition-blob consumer. Both need the dispatcher but with different upstream component shapes.
- (−) Significant WB-7 scope expansion; touches R-4.0 and WB-7 simultaneously.

**Option D — Reuse R-4.0 dispatcher; WB-7 button atom maps composition-blob ButtonConfig → R4ButtonContract at click-time.**
- (+) Zero coupling at the data layer; conversion at the runtime layer.
- (+) Existing R-4 dispatcher consumed unchanged where the 3 verbs overlap.
- (+) New handlers (open_peek, mutate) added to R-4 dispatch table; benefits both substrates additively.
- (+) Composition blob shape stays WB-canonical; R-4 contract is an internal lifting target.
- (−) Slight cognitive overhead: "ButtonConfig is not an R-4 contract but is converted to one."

### 4.4 LOCK 3a — Option D (lift to R-4 contract at click-time)

**Decision**: WB-7's `ButtonRenderer` builds an R-4 dispatch invocation at click-time, NOT a parallel dispatcher. The mapping:

```ts
// ButtonRenderer onClick (sketch):
const r4Action = liftCompositionBlobButtonToR4(config, dataContext, resolvedBindings)
const ctx: BindingContext = { ...buildR4Ctx(useAuth, useParams, ...), current_row: dataContext }
const resolved = resolveBindings(r4Action.parameterBindings, ctx)
const result = await dispatchAction(r4Action.actionType, r4Action.actionConfig, resolved, deps)
```

WB-7 builds the lift helper at `frontend/src/lib/widget-builder/runtime/action-lift.ts` (~80 LOC). R-4.0's `dispatchAction` + `resolveBindings` consumed verbatim. The two NEW handlers (open_peek + mutate) ship as additions to R-4.0's `DISPATCH_HANDLERS` map at `runtime-host/buttons/action-dispatch.ts`. WB-7 adds:

```ts
// runtime-host/buttons/action-dispatch.ts — extended in WB-7
async function handleOpenPeek(config, resolved, deps): Promise<R4DispatchResult> { ... }
async function handleMutateAnomalyAck(config, resolved, deps): Promise<R4DispatchResult> { ... }

DISPATCH_HANDLERS = {
  navigate: handleNavigate,
  open_focus: handleOpenFocus,
  open_peek: handleOpenPeek,           // NEW in WB-7
  mutate: handleMutateAnomalyAck,      // NEW in WB-7 (anomaly_acknowledge only)
  trigger_workflow: handleTriggerWorkflow,
  create_vault_item: handleCreateVaultItem,
  run_playwright_workflow: handleRunPlaywrightWorkflow,
}
```

`R4ActionType` extended to include `open_peek | mutate`. Other R-4 verbs unchanged.

**`current_row` 8th binding source** added to `runtime-host/buttons/parameter-resolver.ts` + types.ts: `BindingContext.currentRow?: Record<string, unknown>` populated by ButtonRenderer at click-time from `dataContext` (when it's a per-row context) or null otherwise.

**deps extended**: `DispatchDeps.openPeek?: (args: { entityType, entityId, ... }) => void` added; nullable for admin tree previews (matching the `openFocus` null-safe pattern at R-5.0.3). Mutate handler reaches `apiClient` directly (no new deps slot needed).

**Cross-substrate coordination**: this lock means R-4.0 substrate evolves alongside WB-7. The R-4.0 file at `frontend/src/lib/runtime-host/buttons/` becomes the canonical action dispatch substrate. WB-7's contribution is additive: 2 new handlers, 1 new binding source, 0 breaking changes to R-4.0 existing consumers.

### 4.5 LOCK 3b — `dataContext` propagated to ButtonRenderer via `baseProps` extension

**Decision**: `AtomRenderer.tsx:320-323` `baseProps` extended to include `dataContext`:

```ts
const baseProps = {
  atom,
  resolvedBindings,
  dataContext,  // NEW WB-7
}
```

`AtomRendererProps` already declares `dataContext?: unknown` (`AtomRenderer.tsx:142`). Atoms that don't need it (text_label, value_display, icon, status_badge, divider, image, conditional_container) ignore it. Only ButtonRenderer reads it for action context. Per-row context is synthesized by the repeater branch at `AtomRenderer.tsx:303` and flows down naturally.

This is a non-breaking extension: existing atom renderers continue working unchanged.

### 4.6 Result handling per verb

Per R-4.0 `R4DispatchResult` shape (`status: 'success' | 'error' | 'skipped'`):

| Verb | Success | Error |
|---|---|---|
| navigate | URL changes via react-router | Toast "navigate action missing actionConfig.route" |
| open_focus | Focus modal opens | Toast error if focus_id missing |
| open_peek | Peek panel opens | Toast error if entity_type / entity_id missing |
| mutate | Toast "Acknowledged" (per the anomaly handler) + canvas-preview optimistic refetch (POST-staging concern; Phase 1 fires + relies on user to refresh) | Toast error message |
| trigger_workflow | Toast "Workflow started" + run_id | Toast error |

Phase 1 mutate does NOT auto-refetch the saved view post-mutation. Operator clicking acknowledge sees toast; the row reappears on next canvas re-fetch (debounced 200ms after next edit) or page refresh. Auto-refetch deferred per Area 9.

---

## 5. Area 4 — Action picker UX

### 5.1 Options enumerated

The picker activates the disabled WB-4b placeholder at `AtomInspectorDispatch.tsx:780-786`.

**Picker shape**:
- (a) Single dropdown of 5 verbs; per-verb config form appears below.
- (b) Categorized verb picker (Navigate / Show / Mutate / Trigger groups).
- (c) Search across all verbs + per-verb config form.
- (d) Two-step modal (Step 1: pick verb; Step 2: configure).
- (e) BindingPicker pattern reused — Combobox with per-verb config below in same panel.

**Per-action-type config UI**:
- Each verb has its own config shape (Area 2). Picker renders different forms.
- navigate: text input for route + ParameterBinding[] editor for `{paramName}` placeholders.
- open_focus: combobox listing focuses from `listFocusConfigs()` + params editor.
- open_peek: entity_type select (6 options) + entity_id binding picker (reuses WB-6 BindingPicker for field_path).
- mutate: mutate_kind select (Phase 1: single option "anomaly_acknowledge") + target_id binding picker.
- trigger_workflow: combobox listing tenant-available workflows + params editor + confirm toggle + confirm copy text.

**Picker preview**:
- (a) None — operator commits then sees runtime behavior.
- (b) "Action preview card" — synthetic preview showing what'll happen (e.g. "Will navigate to /cases/abc-123 when row.id=abc-123").
- (c) Verify-action button — fires the action in a sandboxed dry-run mode.

**Multi-action authoring**:
- N/A — Option D from Area 2 deferred. Picker handles exactly one action per button.

### 5.2 LOCK 4a — Single verb dropdown + per-verb config form (option a)

**Decision**: simplest path. Verb dropdown at the top of the "Action" inspector section (the slot where the WB-4b placeholder lives today). Per-verb config form renders below; form swaps based on verb selection.

**Authoring flow** (per WB-6 picker discipline of "operator-as-platform-builder; sophisticated authoring user assumed"):
1. Operator selects verb from dropdown.
2. Form below renders verb-specific config controls.
3. ParameterBindings (for verbs that have them: navigate, open_focus, trigger_workflow) editable via inline list — add binding, name it, pick source (literal / current_row / current_user / current_tenant / current_date / current_focus_id / current_route_param / current_query_param), set per-source extras.
4. Switching verb clears the prior action_config (with a confirm-modal if any non-default fields are set, per the WB-6 binding-picker error-state Lock 6e parallel).

**Categorization** (option b) and **two-step modal** (option d) rejected — 5 verbs is small enough that a flat dropdown is faster than navigation.

**Search** (option c) rejected — operators authoring widgets know which verb they want; verb is a domain-level decision, not a search affordance.

**BindingPicker reuse** (option e) rejected for the verb selection itself — verb picker has materially different semantics from binding picker (verb is enum; binding is reference). But Field-binding pickers used INSIDE the action config (open_peek's entity_id_binding, mutate's target_id_binding) DO reuse `BindingPicker` from WB-6 — consistent inspector affordance for "pick a binding from the catalog."

### 5.3 LOCK 4b — Action preview card (option b for verbs that admit it)

**Decision**: ship an "Action preview card" inside the inspector that surfaces what the action will do at runtime. Shape parallels WB-6's `BindingPreviewTooltip` (consistent inspector affordance).

Per-verb preview content:
- navigate: "Navigates to: `/cases/{caseId}`" → with sample-record-derived resolution: "Navigates to: `/cases/abc-123`" (using WB-5's first-row sample).
- open_focus: "Opens focus: `funeral-scheduling` (Funeral Scheduling — display name from registry)".
- open_peek: "Opens peek: invoice for id `inv-456`" (sample-derived).
- mutate: "Acknowledges anomaly id `anom-789`" (sample-derived).
- trigger_workflow: "Triggers workflow: `wf_sys_month_end_close` (Month-End Close — display name)".

Preview shape: simple card with the verb + bound display + resolution status (success / pending / error). Errors surface ("Cannot preview — entity_id_binding references missing field `id` on saved view rows"). Card refreshes when the operator edits the form.

**Verify-action button** (option c) — explicit "Run this action now" affordance — deferred to Phase 2. Phase 1 ships preview only.

### 5.4 LOCK 4c — Switching verb clears prior config (with confirm)

**Decision**: when operator changes verb selection AND prior action_config has non-default values, surface a confirm modal: "Switching from `navigate` to `open_focus` will clear the current action settings. Continue?" Inspired by WB-6 binding error-state Lock 6e.

Phase 1: simple modal. Phase 2 may preserve compatible fields across verb switches (e.g. parameter bindings shared between navigate and trigger_workflow), but Phase 1 wipes the slate to avoid mixed-shape action_config records.

### 5.5 LOCK 4d — Empty-state surfaces inline "Pick a verb"

**Decision**: when no action_kind has been chosen (or when action_kind is the default `navigate` with empty config), the inspector renders an empty-state CTA: "Pick an action verb to wire this button." Inline tip; no modal.

### 5.6 Operator-validation-sensitive tag

Locks 4a (flat dropdown vs. categorized) + 4b (preview card content) are **TAGGED for operator validation post-staging** per DECISIONS entry 35. If operators on staging surface that:
- Verb categories aid discoverability → re-shape into option b (categorized).
- Preview card lacks signal → expand to inline result preview (option c verify-action variant).
- Verb switching with wipe is frustrating → add cross-verb field preservation.

These are not load-bearing for shipping the substrate. Revisit per operator hand-validation.

---

## 6. Area 5 — Action permissions + safety

### 6.1 Audit findings

The action dispatch substrate today (R-4.0) does NOT enforce permissions at dispatch time. Per-verb permission cascades:

- **navigate**: no permission check (URL access; routes themselves enforce). React-router's route-level guards handle.
- **open_focus**: no permission check at FocusContext.open. The Focus implementation may itself check permissions when it renders.
- **open_peek**: backend `GET /api/v1/peek/{type}/{id}` enforces tenant + per-entity permission per the existing peek substrate.
- **mutate**: per-endpoint permission. Anomaly-acknowledge endpoint (`widget_data.py:353`) enforces via `current_user.company_id` filter + `invoice.approve`-or-equivalent role check (in the underlying service layer).
- **trigger_workflow**: backend `POST /workflows/{id}/start` validates `workflow_engine.get_active_workflows_for_tenant` — workflows not available to the tenant return 404.

The action-handler-fires-then-the-backend-may-reject pattern means **errors surface as toasts**, not as pre-fire denials. This is acceptable for Phase 1 but has UX consequences (operator clicks → button shows pending state → toast "Permission denied" after server roundtrip).

### 6.2 Options

**Authoring-time permission semantics**:
- (a) No authoring-time check. Authors create any action; runtime enforces.
- (b) Authoring-time hint — picker shows "This action requires permission X; current operator can fire it" / "current operator cannot fire it" based on the authoring user's permissions.
- (c) Authoring-time gate — picker rejects actions the authoring user can't fire.

**Runtime permission check before dispatch**:
- (a) None — handlers fire optimistically; errors surface as toasts.
- (b) Client-side check (read user role / permissions from auth context; compare to declared per-action required_permission); 403 toast before fire.
- (c) Server-side check (handlers call `GET /permissions/check` first; abort on denial).

**Confirmation UX for destructive actions**:
- (a) None — confirm-before-fire is per-button (R-4.0's `confirmBeforeFire`).
- (b) Per-verb default — mutate verb defaults to confirm-required, navigate to no-confirm.
- (c) Per-tenant policy — admin chooses whether each verb requires confirm.

**Cross-tenant action scope**:
- (a) Actions fire against the operator's current tenant only.
- (b) Bridgeable-canonical widget actions can declare cross-tenant scope (rare; would require widget metadata + cross-tenant permission cascade).

### 6.3 LOCK 5a — Runtime-only permission check (option a + a + a, simplest path)

**Decision**: Phase 1 ships **runtime-enforced permissions only**. Authoring time accepts any action; backend/runtime endpoints enforce. Errors surface as toasts. NO authoring-time permission visualization in Phase 1.

**Rationale**:
- The 5 verbs differ in their permission models (navigate has none; mutate is per-endpoint; trigger_workflow is per-workflow). Authoring-time checks would require enumerating per-verb permission contracts; Phase 1 doesn't surface them.
- The R-4.0 substrate has been in production through R-5.0.x without authoring-time permission checks; the canvas preview never actually fires actions (admin tree no-ops focus / peek), so authoring-time checks would surface false positives.
- The cost of "fire then toast on 403" is small (one round trip; ≤500ms typical); operators learning the platform iterate on action design.

### 6.4 LOCK 5b — Per-button confirm-before-fire (option a; per-button toggle)

**Decision**: WB-7 reuses R-4.0's `confirmBeforeFire` field per-button. The action picker exposes it as a checkbox in the per-verb config form: "Confirm before firing" + optional confirm copy text. Defaults: false for navigate / open_focus / open_peek; **true for trigger_workflow** (workflows are operationally consequential per Workflow Arc canon) + **true for mutate** (state changes per §12.6a discipline).

Per-verb defaults but operator-overrideable. NO per-tenant policy (option c — defers; Phase 2 if operator demand surfaces).

### 6.5 LOCK 5c — Audit logging delegated to backend handlers

**Decision**: WB-7 does NOT add a frontend audit-logging layer in the dispatcher. The backend handlers each do their own audit logging (anomaly_acknowledge audit-logs per `anomalies_widget_service.py:209`; workflow_engine.start_run audit-logs per existing pattern; vault items via vault_service). navigate + open_focus + open_peek are user-experience actions; nothing to audit beyond standard request logging.

If WB-7 surfaces a need for "button-click audit" (operator demand surfacing as "show me which operators clicked which button on which case"), that's a separate substrate arc — `button_click_log` table or equivalent. Phase 1: do not.

### 6.6 LOCK 5d — Cross-tenant scope NOT in scope for Phase 1

**Decision**: actions fire against the operator's current tenant. Per the WB-6 Lock cross-tenant Area 6 deferral, cross-tenant binding scope is not in Phase 1 substrate. Cross-tenant actions inherit the deferral — actions can only target the operator's tenant.

This matches the R-4.0 substrate's implicit assumption (no `tenant_id` field on `R4ButtonContract`; all dispatch goes through `apiClient` which carries the current-tenant JWT).

### 6.7 Operator-validation-sensitive tag

Lock 5a (no authoring-time permission viz) and Lock 5b (per-verb confirm defaults) are **TAGGED for operator validation post-staging** per DECISIONS entry 35. If operators surface:
- Frequent fire-and-403 cycles → Phase 2 adds authoring-time hints (option 5a-b).
- Confirm-on-trigger-workflow is friction → Phase 2 makes it operator-overridable per-button per-tenant.

---

## 7. Area 6 — Action context substrate

### 7.1 What needs to flow to the dispatcher

Per Area 3 + Area 4, the dispatcher receives these contexts at click-time:

1. **Row context** (from `dataContext` when ButtonRenderer is inside a repeater_atom). The per-row dict synthesized at `AtomRenderer.tsx:303` is the source. Stored as `BindingContext.currentRow`.
2. **Saved-view context** (rare; the saved_view_id the widget binds to — for actions that need to know "which view's row" or "which view's filter is in effect"). Phase 1 likely irrelevant; punt unless Area 11 surfaces a corner.
3. **Tenant context** (JWT-derived per WB-5 Lock 2a). `BindingContext.tenant: { id, slug, vertical }`. From `useAuth.company`.
4. **Operator context**: `BindingContext.user: { id, email, role }`. From `useAuth.user`.
5. **Widget instance context** (which widget; which atom). Phase 1: NOT propagated to handlers. Audit-logging at the backend already captures the operator + entity; widget-instance attribution is Phase 2 if operator demand surfaces ("filter audit log by widget_definition_slug" — out of scope).
6. **Route + query params** (R-4.0 already covers via `current_route_param` + `current_query_param`).
7. **Focus context** (the focus ID if WB-7 button is rendered inside a Focus surface). R-4.0's `current_focus_id` covers.

### 7.2 LOCK 6a — `current_row` 8th binding source

Already locked in Area 3 Lock 3a. ParameterBinding source enum extends:

```ts
type ParameterBindingSource =
  | "literal"
  | "current_user"
  | "current_tenant"
  | "current_date"
  | "current_route_param"
  | "current_query_param"
  | "current_focus_id"
  | "current_row"           // NEW in WB-7
```

With per-binding `rowField?: string` specifying which row field to read. Resolver navigates `BindingContext.currentRow[rowField]`. Null-safe when not in a per-row context.

### 7.3 LOCK 6b — `dataContext` propagation chain

Already locked in Area 3 Lock 3b: `AtomRenderer.tsx baseProps` extended; ButtonRenderer reads `dataContext` and lifts it into `BindingContext.currentRow` when shaped as per-row.

Shape contract (WB-6 Lock + WB-5 Lock):
- `{ __row: true, __index: number, ...rowDict }` per-row → currentRow = rowDict.
- `{ __summary: true, aggregations?: object, total_count?: number }` summary → currentRow = null (action context lacks per-row info).
- `{ __canvas_preview: true, byView: {...} }` canvas-preview map → currentRow = null at top level; only the repeater's per-row sub-context establishes currentRow.
- `undefined` → currentRow = null.

### 7.4 LOCK 6c — Widget context not propagated to handlers

**Decision**: handlers do NOT receive widget_definition_slug or atom_id. The backend dispatch endpoints (anomaly_acknowledge, workflow start, peek GET) carry sufficient context via the resolved bindings (entity_id, workflow_id, etc.). Widget attribution adds noise to handler signatures + creates a coupling between handlers and the WB-7 substrate. Phase 2 may revisit if "audit by widget" demand surfaces.

### 7.5 Cross-substrate dependency

WB-7 dataContext substrate is a **read-only extension** of WB-5 + WB-6 dataContext flows. WB-5's 3-flavor discriminator + WB-6's binding catalog are not modified by WB-7. WB-7 adds:
- `baseProps.dataContext` propagation in `AtomRenderer.tsx`
- `BindingContext.currentRow` in `parameter-resolver.ts`
- `current_row` ParameterBindingSource enum extension

All additive. No breaking changes to WB-5 or WB-6 substrate.

---

## 8. Area 7 — WB-5 dataContext substrate interaction verification

Per the investigation prompt's Area 7: "Verify WB-5 substrate enables WB-7 mutate substrate without modification."

### 8.1 Audit

WB-5's `dataContext` is the canvas-preview map at the canvas root + the per-row context at each repeater iteration. Per `AtomRenderer.tsx:303`, the repeater synthesizes:

```ts
const rowContext = { __row: true, __index: idx, ...row }
```

This is the per-row substrate that WB-7's button needs for parameter resolution (e.g. `entity_id_binding` with `source: "current_row", rowField: "id"` resolves against this).

### 8.2 Mutate action row-scope check

A button atom inside a repeater for a saved view of fh_case rows; action_kind=mutate, action_config.target_id_binding bound to `current_row.id`. When operator clicks:

1. ButtonRenderer reads `dataContext` from `baseProps` (per Lock 3b). It's `{ __row: true, __index: 2, id: "anom-789", severity: "warning", ... }`.
2. ButtonRenderer builds `BindingContext.currentRow = rowDict (the `dataContext` minus the `__row`/`__index` markers per a thin helper).
3. `resolveBinding({ source: "current_row", rowField: "id" }, ctx)` → `"anom-789"`.
4. `dispatchAction("mutate", { mutate_kind: "anomaly_acknowledge", target_id: "anom-789" }, deps)` → backend acknowledge.

**Verification**: WB-5's substrate supports this verbatim. The per-row context is exactly the shape WB-7 needs. The WB-5 Area 9.2 check ("WB-5 does NOT block WB-7") is **empirically confirmed**.

### 8.3 ActionRef shape compatibility with dataContext

The Area 2 Lock 2a discriminated-union ActionConfig has fields that may bind to per-row data (entity_id_binding, target_id_binding, route templates with `{...}` placeholders). All of these are `ParameterBinding` shapes that the WB-5 dataContext can populate via current_row.

**Verification**: shape-compatible without modification.

### 8.4 Cross-flavor handling

WB-5's 3 flavors (success / loading / error per saved-view, + the canvas-preview discriminator at top level):

- **success**: per-row context fully populated → all bindings resolve to actual values. Buttons fire with real arguments.
- **loading**: per-row context is the previous (optimistic-stale) row OR null. Buttons CAN fire — Phase 1 doesn't block clicks during loading. The bound values may be stale by one debounce cycle; consequences are bounded (operator acknowledges based on previous data; backend handler uses fresh data).
- **error**: per-row context unavailable. Phase 1: button's bound action_config has null bindings → handler returns error → toast. UX is degraded but bounded.

**Lock 7a — Phase 1 click-during-loading is allowed**; click-during-error fires the action but most bindings resolve null. Operator sees error toast. Phase 2 may add per-atom click-disable when dataContext.status is error (consistent with WB-5 Lock 4a's atom error chrome).

---

## 9. Area 8 — Cross-substrate dependency enumeration

WB-7 touches these substrates. Each row classifies the touch as additive / coordinating / extending.

| Substrate | File / path | Touch type | What WB-7 does |
|---|---|---|---|
| WB-1 composition blob | `frontend/src/lib/widget-builder/types/composition-blob.ts:215-242` | Extending | Narrow `action_config: Dict` → discriminated union per kind; retire `action_ref?: string` field |
| WB-1 Pydantic | `backend/app/schemas/widget_composition.py:353-383` | Extending | Add per-kind action_config models + `Annotated[Union, Discriminator]`; retire `action_ref` |
| WB-2 atom defaults | `frontend/src/bridgeable-admin/components/widget-builder/atom-tree-helpers.ts:65-74` | Extending | Default `action_config: { kind: "navigate", route: "" }` |
| WB-3 ButtonRenderer | `frontend/src/lib/widget-builder/runtime/atoms/index.tsx:526-572` | Extending | Replace onClick no-op with dispatch lifting per Lock 3a; consume `dataContext` from baseProps |
| WB-4b ButtonInspector | `frontend/src/bridgeable-admin/components/widget-builder/inspectors/AtomInspectorDispatch.tsx:710-789` | Extending | Replace `BindingPlaceholderField` with verb dropdown + per-verb config forms |
| WB-4b BindingPlaceholderField | `inspector-primitives.tsx:184-203` | Extending | Phase 1 path retires the "WB-7" alias; primitive may still be used for future placeholders |
| WB-5 dataContext | `frontend/src/lib/widget-builder/runtime/AtomRenderer.tsx:320-323` | Extending | `baseProps.dataContext` added (Lock 3b) — non-breaking additive |
| WB-6 BindingPicker | `frontend/src/bridgeable-admin/components/widget-builder/binding-picker/BindingPicker.tsx` | Coordinating | Reused inside action_config UIs for per-binding row-field selection (open_peek entity_id_binding, mutate target_id_binding) |
| WB-6 BindingPreviewTooltip | `BindingPreviewTooltip.tsx` | Coordinating | Action preview card per Lock 4b mirrors its shape |
| R-4.0 button substrate | `frontend/src/lib/runtime-host/buttons/types.ts:101-141` + `action-dispatch.ts` + `parameter-resolver.ts` | Extending | Add 2 new handlers (open_peek, mutate); add 1 new ParameterBindingSource (current_row); add 1 deps slot (openPeek) |
| Focus context | `frontend/src/contexts/focus-context.tsx` | Consuming | `open_focus` handler calls `useFocus.open(focusId, { params })` (already done in R-4.0) |
| Focus registry | `frontend/src/contexts/focus-registry.ts` | Consuming | Action picker enumerates `listFocusConfigs()` for the open_focus picker |
| Peek context | `frontend/src/contexts/peek-context.tsx` | Consuming | `open_peek` handler calls `usePeek.openPeek(...)`; admin tree fallback via `usePeekOptional` |
| Workflow start endpoint | `backend/app/api/routes/workflows.py:379-404` | Consuming | `trigger_workflow` handler calls existing endpoint (R-4.0 already does) |
| Anomaly acknowledge endpoint | `backend/app/api/routes/widget_data.py:353-389` | Consuming | `mutate` handler (Phase 1: anomaly_acknowledge variant) calls existing endpoint |
| Saved-views service | `backend/app/services/saved_views/` | Read-only (no mutation in WB-7) | Action picker queries `GET /api/v1/saved-views` for view-related action targets if any; Phase 1 likely no calls — saved-view mutate not in scope |
| AppLayout / FocusProvider mount | `frontend/src/App.tsx` | Consuming | RegisteredButton-style null-safe context use (already in R-4.0) |
| AdminAuthProvider | `frontend/src/bridgeable-admin/lib/admin-auth-context.tsx` | Consuming | Admin-tree preview uses useAuthOptional fallback (already in R-4.0 R-5.0.4) |
| Sonner toast | `frontend/src/components/ui/sonner.tsx` (or equivalent) | Consuming | Success/error toasts (R-4.0 already wires) |

**No new tables. No new migrations. ZERO backend schema changes** — the existing `widget_definitions` table's published_blob JSONB carries the action_config; Pydantic validation tightens types but accepts the existing shape.

---

## 10. Area 9 — Phase 1 scope boundaries

### 10.1 Ships in WB-7

- **ActionRef shape** per Area 2 Lock 2a (inline discriminated union; `action_ref` field retired).
- **Per-kind Pydantic + TypeScript types** mirroring (5 action kinds).
- **ButtonRenderer dispatch wiring** per Area 3 Lock 3a (lifting to R-4 contract; consuming `dataContext` per Lock 3b).
- **R-4.0 substrate extensions**:
  - `handleOpenPeek` handler (new in `runtime-host/buttons/action-dispatch.ts`)
  - `handleMutateAnomalyAck` handler (new; calls existing acknowledge endpoint)
  - `current_row` ParameterBindingSource enum + resolver (new)
  - `R4ActionType` extended with `open_peek | mutate`
  - `DispatchDeps.openPeek` optional slot
- **ButtonInspector action picker UI** per Area 4 Lock 4a (verb dropdown + per-verb forms).
- **Action preview card** per Lock 4b (per-verb preview reading sample-record-derived bindings).
- **Per-verb confirm defaults** per Lock 5b (true for trigger_workflow + mutate).
- **Cross-side test gates** following WB-2/4b/6 symmetry canon: Pydantic narrowing + TypeScript types + backend validator agree on per-verb config shape.
- **Source-shape regression gate** per DECISIONS entry 31 — assert `ButtonRenderer.tsx` consumes `dataContext` from baseProps (catches future "let me clean this up" patches removing the propagation).
- **Playwright pointer-event coverage** per DECISIONS entry 30 — button click in canvas preview, dispatch fires, toast renders.
- **Integration test** (per DECISIONS 2026-05-19 evening lineage on data↔render boundaries) — operator-flow scenarios for each of 5 verbs: pick verb → configure → save → preview fires correctly.

**Verb dispatch in Phase 1**: all 5 verbs ship.

### 10.2 Defers to WB-7.x / WB-8 / post-September

- **Mutate verb's other kinds**: only `anomaly_acknowledge` ships; `mark_read`, `status_flip`, etc. defer. Substrate accommodates additively.
- **Action chains** (Area 2 Option D): out of scope; non-breaking forward extension.
- **Catalog-keyed ActionRef** (Area 2 Option B): out of scope; non-breaking forward extension if operator demand for reuse surfaces.
- **Authoring-time permission visualization** (Area 5 Lock 5a): out of scope; runtime-only enforcement.
- **Auto-refetch on mutate** (Area 4.6): out of scope; operator sees toast, refreshes manually.
- **Per-tenant confirm policy** (Area 5 Lock 5b): out of scope.
- **Widget-instance audit logging** (Area 6 Lock 6c): out of scope.
- **Verify-action button** (Area 5 picker option c): out of scope; preview-card only.
- **Cross-verb field preservation on switch** (Area 5 Lock 4c): out of scope; wipe + confirm.
- **Saved-view mutate verb** (generic patch row by field): out of scope; mutate restricted to declared canonical state-flip endpoints.
- **Cross-tenant action scope**: out of scope per Lock 5d.
- **Operator-validation-sensitive revisits** (4a / 4b / 5a / 5b tags): post-staging.

### 10.3 Explicit non-goals

- WB-7 does NOT refactor R-4.0 into a shared library (Area 3 Option C rejected).
- WB-7 does NOT introduce per-button audit logging at the frontend.
- WB-7 does NOT add a `Action` substrate table parallel to saved views (Area 2 Option E rejected).
- WB-7 does NOT alter the workflow start endpoint or the anomaly acknowledge endpoint.
- WB-7 does NOT add a new `bindings_catalog`-style `actions_catalog` field on the composition blob.

---

## 11. Area 10 — Architectural risks + mitigations

### 11.1 Risk 1 — R-4.0 substrate coupling

**Description**: WB-7 ships handlers + binding source extensions IN R-4.0 (`runtime-host/buttons/action-dispatch.ts`, `parameter-resolver.ts`). Future R-4.x increments to R-4.0 (e.g., new ParameterBindingSource for "current_org" or new handler for "send_email") would touch the same file that WB-7 owns handlers in. Cross-substrate ownership confusion.

**Severity**: Low. Both substrates evolve naturally additively; conflicts are line-level merge events at most.

**Mitigation**:
- Document the R-4.0 file as **the canonical action substrate**. WB-7 contributions live in R-4.0's tree; the file header gets a Doc note: "R-4.x + WB-7 both contribute handlers; coordinate additions."
- Source-shape regression gate: assert `DISPATCH_HANDLERS` contains all 7 expected verbs (navigate, open_focus, open_peek, mutate, trigger_workflow, create_vault_item, run_playwright_workflow). Catches accidental removal.

### 11.2 Risk 2 — Pydantic discriminated-union complexity

**Description**: Pydantic 2.x discriminated unions with `Annotated[Union[...], Discriminator(key)]` work, but the per-kind action_config models must precisely mirror the TypeScript discriminated union shape. Drift risk is real per WB-2/4b/6 lineage.

**Severity**: Medium. Drift would produce 422s in dev that pass mock-only frontend tests (per DECISIONS 2026-05-19 late PM "Mock-only tests verify one side of frontend↔backend contracts" canon).

**Mitigation**:
- Cross-side integration test that builds each of 5 valid action_configs in TypeScript, sends through the real PUT endpoint, asserts backend acceptance.
- Cross-side negative test: build each of 5 invalid action_configs (missing required field per kind), sends through, asserts 422 with field-level error.
- Source-shape regression gate on the Pydantic file: assert `ButtonConfig.action_config` model fields match the 5-kind enumeration verbatim.

### 11.3 Risk 3 — Workflow start endpoint exposes any workflow

**Description**: `workflow_engine.get_active_workflows_for_tenant` returns every active workflow. A trigger_workflow button authored against `wf_sys_month_end_close` (a Tier-1 cross-vertical workflow with consequential side effects) can fire from any tenant.

**Severity**: Low for Phase 1 — operators authoring widgets are platform-admin / tenant-admin per the WB-original Q-14 lock + Phase 8a permission model. The wider concern is if widgets are shared across tenants or non-admin operators publish widgets. Out of Phase 1 scope.

**Mitigation**:
- Lock 5b makes confirm-before-fire true by default for trigger_workflow.
- Audit trail: workflow_engine.start_run already audit-logs via existing pattern.
- Phase 2 may surface "this workflow is destructive — explicit author confirmation required" UX.

### 11.4 Risk 4 — Action picker enumerates workflow list per click

**Description**: The picker fetches available workflows on open. Tenants with 50+ workflows produce a long combobox.

**Severity**: Low. Combobox is search-filterable; existing WB-6 BindingPicker handles similar saved-view cardinality (per WB-6 Section 6.1 LOCK 6a).

**Mitigation**:
- Same combobox primitive as WB-6 BindingPicker.
- Optional filter: trigger_type ∈ {manual, event-immediate} (exclude scheduled-only workflows that wouldn't make sense as button targets). Phase 1 may ship without this filter and add post-staging.

### 11.5 Risk 5 — current_row binding source crashes outside repeater context

**Description**: An operator authors a button OUTSIDE a repeater_atom with action_config binding to `current_row.id`. At click-time, dataContext is not a per-row context. Resolver returns null. Backend gets null entity_id → 400 / 422.

**Severity**: Medium. UX is degraded but bounded.

**Mitigation**:
- Picker authoring-time check: if button atom is not a descendant of a repeater, the `current_row` binding source is grayed in the binding source dropdown with explanation "Only available inside a repeater."
- Atom-tree-helpers / inspector verify when serializing.
- Runtime defense-in-depth: resolver returns null; backend handler surfaces error toast.

### 11.6 Risk 6 — Verb switching loses operator work

**Description**: Operator authoring a navigate action with detailed parameter bindings; flips to trigger_workflow; per Lock 4c, action_config wipes. Operator loses ~5 min of binding setup.

**Severity**: Medium for authoring throughput.

**Mitigation**:
- Confirm modal per Lock 4c.
- Phase 2 may preserve cross-verb-compatible fields (parameter bindings, confirm settings).

### 11.7 Risk 7 — Mutate action staleness

**Description**: Operator clicks acknowledge on row at index 2. Canvas preview's dataContext is from a fetch 200ms ago. Underlying anomaly_id may already be resolved. Backend returns idempotent response (per `anomalies_widget_service` idempotency guarantee). Operator sees no error but UI doesn't reflect the resolution until next debounce cycle.

**Severity**: Low. UX expectation matches reality after refresh.

**Mitigation**:
- Phase 1: accept the delay. Toast says "Acknowledged."
- Phase 2: auto-refetch the relevant saved view post-mutate (call to `useCanvasPreviewData`'s refetch).

### 11.8 Risk 8 — Action preview card complexity exceeds inspector budget

**Description**: Per-verb preview rendering plus per-binding resolution preview compounds. Inspector real estate is small.

**Severity**: Low.

**Mitigation**:
- Compact preview card (~3 lines max).
- Tooltip / expandable affordance for full preview if needed.

### 11.9 Risk 9 — JSDOM-vs-chromium fidelity for confirm Dialog

**Description**: WB-7 ships confirm-before-fire (R-4.0 substrate already does). JSDOM tests assert click-fires-then-Dialog-renders; but Dialog focus management, escape-key, click-outside-to-dismiss are chromium-only per DECISIONS entry 30.

**Severity**: Low — R-4.0 ships Playwright coverage already.

**Mitigation**:
- WB-7 Playwright spec exercises confirm + reject paths for trigger_workflow.

### 11.10 Risk 10 — 3-flavor discriminator generalization candidate (WB-5-α)

**Description**: WB-5 introduced the canvas-preview map with 3 flavors (success / loading / error). WB-7's action result may inherit a similar 3-flavor shape (R4DispatchResult already has 3 statuses: success / error / skipped). Whether the dispatcher result substrate gets reshaped into a discriminator inheriting WB-5's pattern is a process canon question.

**Severity**: Low — R-4.0's R4DispatchResult is already a discriminator; no reshape needed.

**Mitigation**:
- Note for canon-update arc: R-4.0's R4DispatchResult is the canonical "action-result discriminator" alongside WB-5's "data-flavor discriminator." Three-status discriminators are a recurring pattern.

---

## 12. Area 11 — WB-8 substrate-shape compatibility

WB-8 (variant authoring) is next sub-arc. Does WB-7 paint WB-8 into a corner?

### 12.1 Variant-specific actions

WB-8 introduces per-variant atom visibility (atom.visible_in_variants). A button authored on a widget may be visible in variant `glance` but hidden in `deep` (or vice versa). Two extension questions:

- **(a) Variant-specific action_config**: same button atom, different actions in different variants?
- **(b) Variant-scoped action picker**: when authoring variant X, action picker shows only actions valid for that variant?

**Phase 1 lock**: WB-7 ships one action_config per button atom. WB-8 atom-level visibility filtering (visible_in_variants) inherits from WB-1 schema unchanged. **A button atom in variant glance fires the same action as the same button atom in variant deep — different buttons would be authored as separate atoms with different visible_in_variants.**

This is shape-compatible with WB-8 because:
- The atom is the action-binding unit. Variant filtering happens at render time; action attribute survives.
- Operators wanting "different action per variant" author two button atoms with different visible_in_variants.

### 12.2 Cross-surface rendering (Glance / Brief / Detail / Deep)

WB-8 ships variant authoring across the 4 surface variants. WB-7 button dispatch must work on every surface where the widget renders:

- **Pulse / Spaces**: tenant tree; full PeekProvider / FocusProvider / AuthProvider. All 5 verbs fire correctly.
- **Focus canvas (embedded widgets on a Focus)**: tenant tree; same providers. All 5 verbs fire.
- **Palette preview (admin tree)**: providers absent or partial. R-4.0's null-safe useFocusOptional / useAuthOptional + Lock 3a admin-tree dispatch fallbacks (no-op for open_focus, no-op for open_peek). navigate works (admin tree has useNavigate). trigger_workflow + mutate make HTTP calls; admin-tree fires would hit backend with admin JWT realm (per CLAUDE.md §4 cross-realm boundary). Backend `get_current_user` rejects platform JWT → 401.

**WB-7 Phase 1 dispatch behavior in admin preview**:
- navigate: SKIP (don't actually navigate; preview is non-interactive). Or: navigate works as preview shows the eventual destination URL.
- open_focus / open_peek: SKIP (no provider).
- trigger_workflow / mutate: SKIP (no tenant JWT).

**LOCK 11a — Admin preview button clicks are non-dispatching (skipped)**. ButtonRenderer in the canvas-preview path detects admin-tree absence (via useAuthOptional + useFocusOptional + null-check on dataContext's tenant marker) and renders a "Preview mode — action would fire on tenant runtime" toast. Operator's click is acknowledged visually but does not actually fire.

Trade-off: WB-5's "operator-selected sample record" goal of "preview as close to reality as possible" is intentionally not 100% in WB-7. Actions firing in admin preview would mutate tenant state, send navigation events to admin URLs, etc.

### 12.3 Variant authoring inspector compatibility

WB-8 inspector adds variant toggles to atoms. WB-7's per-verb config forms must coexist with the variant toggle UI in the same atom inspector panel. Both are inspector sections; structural compatibility good.

### 12.4 Operator-validation-sensitive tag

Lock 11a (admin preview non-dispatching) is **TAGGED** per DECISIONS entry 35. Operator feedback may surface: "I want navigate to actually preview the destination URL." If so, Phase 2 makes navigate a special case (actually navigates in preview within the admin tree).

### 12.5 Corner check verdict

WB-7 does NOT paint WB-8 into a corner. Variant authoring on visible_in_variants + per-atom action_config is shape-compatible.

---

## 13. WB-7 sub-arc execution plan + LOC estimate

### 13.1 Files touched (production code)

| File | Type | Estimated LOC | Description |
|---|---|---|---|
| `frontend/src/lib/widget-builder/types/composition-blob.ts` | Modify | ~50 | Per-kind discriminated union for ActionConfig; retire `action_ref?: string` |
| `backend/app/schemas/widget_composition.py` | Modify | ~80 | Per-kind Pydantic models; `Annotated[Union, Discriminator]`; retire `action_ref` |
| `backend/app/services/widget_definitions/...` (validator) | Modify | ~60 | Per-verb config validators (focus_id exists in registry; workflow_id available; mutate_kind in canonical list; peek entity_type valid) |
| `frontend/src/bridgeable-admin/components/widget-builder/atom-tree-helpers.ts` | Modify | ~10 | Default action_config shape |
| `frontend/src/lib/widget-builder/runtime/action-lift.ts` | NEW | ~80 | Lift composition-blob ButtonConfig → R-4 dispatch invocation |
| `frontend/src/lib/widget-builder/runtime/atoms/index.tsx` | Modify | ~40 | ButtonRenderer onClick wiring; replace no-op |
| `frontend/src/lib/widget-builder/runtime/AtomRenderer.tsx` | Modify | ~10 | `baseProps.dataContext` propagation |
| `frontend/src/lib/runtime-host/buttons/types.ts` | Modify | ~30 | R4ActionType extended; ParameterBindingSource extended; DispatchDeps.openPeek slot |
| `frontend/src/lib/runtime-host/buttons/action-dispatch.ts` | Modify | ~80 | New handlers: handleOpenPeek + handleMutateAnomalyAck; DISPATCH_HANDLERS extended |
| `frontend/src/lib/runtime-host/buttons/parameter-resolver.ts` | Modify | ~30 | `current_row` binding source resolver |
| `frontend/src/lib/runtime-host/buttons/RegisteredButton.tsx` | Modify | ~15 | Pass `currentRow` through to BindingContext if available |
| `frontend/src/bridgeable-admin/components/widget-builder/inspectors/AtomInspectorDispatch.tsx` | Modify | ~120 | Replace BindingPlaceholderField with ActionPicker section |
| `frontend/src/bridgeable-admin/components/widget-builder/inspectors/ActionPicker.tsx` | NEW | ~250 | Verb dropdown + per-verb config forms; reuse BindingPicker for inner field bindings |
| `frontend/src/bridgeable-admin/components/widget-builder/inspectors/ActionPreviewCard.tsx` | NEW | ~120 | Per-verb preview card |
| `frontend/src/bridgeable-admin/components/widget-builder/inspectors/inspector-primitives.tsx` | Modify | ~5 | Retire WB-7 alias in BindingPlaceholderField type (or delete if no consumer) |

**Production LOC subtotal: ~990 LOC** (~840 in admin-side authoring + ~150 in shared runtime).

### 13.2 Tests + gates

| File | Type | Estimated LOC | Description |
|---|---|---|---|
| `frontend/src/lib/widget-builder/runtime/action-lift.test.ts` | NEW | ~150 | Per-verb lift translations (5 verbs); edge cases (missing config, null bindings) |
| `frontend/src/lib/runtime-host/buttons/action-dispatch.test.ts` | Modify | ~80 | handleOpenPeek tests; handleMutateAnomalyAck tests; updated DISPATCH_HANDLERS keys |
| `frontend/src/lib/runtime-host/buttons/parameter-resolver.test.ts` | Modify | ~50 | current_row resolution; null contexts |
| `frontend/src/lib/widget-builder/runtime/atoms/atoms.test.tsx` (ButtonRenderer) | Modify | ~80 | Click triggers dispatch; admin preview skip path; row context propagation |
| `frontend/src/lib/widget-builder/runtime/AtomRenderer.test.tsx` | Modify | ~30 | dataContext propagation through baseProps |
| `frontend/src/bridgeable-admin/components/widget-builder/inspectors/ActionPicker.test.tsx` | NEW | ~200 | Verb dropdown; per-verb forms; switch confirm; preview card integration |
| `frontend/src/bridgeable-admin/components/widget-builder/inspectors/ActionPreviewCard.test.tsx` | NEW | ~100 | Per-verb preview rendering; sample-record-derived resolution; error states |
| `frontend/src/bridgeable-admin/components/widget-builder/inspectors/AtomInspectorDispatch.test.tsx` | Modify | ~30 | Replace WB-7 placeholder test with ActionPicker integration |
| `frontend/src/bridgeable-admin/components/widget-builder/source-shape.test.ts` | Modify | ~10 | Update WB-7 inspector expectation |
| `frontend/src/bridgeable-admin/components/widget-builder/integration.test.tsx` (or equivalent) | NEW or Extend | ~250 | End-to-end: author button → save → canvas preview renders → click fires → toast |
| `backend/tests/test_widget_composition_actions.py` | NEW | ~180 | Pydantic per-verb validation (positive + negative for each of 5 kinds) |
| `tests/e2e/widget-builder-action-dispatch.spec.ts` | NEW | ~200 | Playwright: author action; deploy; tenant runtime; click; verb-by-verb |
| `tests/e2e/widget-builder-action-confirm.spec.ts` | NEW | ~80 | Confirm-before-fire UX for trigger_workflow + mutate |

**Tests LOC subtotal: ~1,440 LOC** (~1,160 vitest + ~280 Playwright + backend).

### 13.3 Total LOC estimate

**Total: ~2,430 LOC** (~990 production + ~1,440 tests).

Per WB-6 calibration discipline: this estimate reflects substrate implications, not feature surface. Specifically:
- ActionPicker is the LARGEST single component (~250 LOC) because 5 verbs × variable config shapes × inner BindingPicker reuse compounds.
- Pydantic per-verb validators (~80 LOC) + frontend per-verb lift (~80 LOC) carry the cross-side symmetry cost per WB-2/4b/6 canon.
- Tests are larger than production code by ~50% — matches WB-5 + WB-6 ratios (the integration tests for cross-side contracts per DECISIONS 2026-05-19 late PM are load-bearing).

**Calibration check against WB-6 (saved-view binding picker activation + field_path runtime + iteration_mode runtime + validator extensions + in-inspector preview)**: WB-6 was ~3,800 LOC per the build report. WB-7's scope is comparable: 5 verb forms (≈ analogous to WB-6's 4 binding triad fields × picker), plus cross-side validators + per-kind dispatchers. WB-7 estimate at ~2,430 is LOWER than WB-6 because R-4.0 substrate is consumed verbatim for 3 of 5 verbs (no new dispatcher invention for navigate / open_focus / trigger_workflow). The savings are real.

**WB-5 calibration sanity-check**: WB-5 was ~2,200 LOC. WB-7 at ~2,430 is ~10% higher; WB-7's admin authoring surface (ActionPicker) is the largest single component and explains the delta. WB-5 had no equivalent admin surface — it was pure runtime + 1 hook.

### 13.4 Sequenced execution order

1. **Shape symmetry** (Pydantic + TypeScript types + atom-tree-helpers defaults + retire action_ref) — substrate gate.
2. **R-4.0 extensions** (types.ts + action-dispatch.ts + parameter-resolver.ts + RegisteredButton.tsx) — substrate gate.
3. **WB-7 runtime** (action-lift.ts + AtomRenderer.tsx baseProps + ButtonRenderer onClick) — runtime gate.
4. **WB-7 authoring** (AtomInspectorDispatch.tsx + ActionPicker.tsx + ActionPreviewCard.tsx) — authoring gate.
5. **Tests + Playwright + source-shape regression gates** — verification gate.
6. **WB-7 build report + STATE.md update**.

Each gate ships in order. Cross-side integration test (per DECISIONS 2026-05-19 late PM) covers gates 1+2+3+4 simultaneously after gate 4.

### 13.5 Migration head

UNCHANGED at `r106_widget_definitions_published_blob`. ZERO new migrations.

### 13.6 Canon state

UNCHANGED at 42 (per the WB-5 STATE.md tally). WB-7 does not introduce new canon entries; canon-update arc batches WB cycle additions at end.

---

## 14. Operator-validation-sensitive locks tagged

Per DECISIONS entry 35, the following locks are TAGGED for revisit-after-staging:

| Lock | Tag | Revisit trigger |
|---|---|---|
| 4a (flat verb dropdown vs. categorized) | Operator-validation-sensitive | Discoverability complaints during authoring throughput tests |
| 4b (action preview card content) | Operator-validation-sensitive | "I want to see exact resolved values" → expand or add verify-action button |
| 4c (verb switch confirm + wipe) | Operator-validation-sensitive | "I lost my parameter bindings" → Phase 2 cross-verb preservation |
| 5a (runtime-only permission enforcement) | Operator-validation-sensitive | Frequent fire-and-403 cycles → Phase 2 authoring-time hints |
| 5b (per-verb confirm defaults) | Operator-validation-sensitive | Operator-reported friction on trigger_workflow confirm-always-on |
| 7a (click-during-loading allowed) | Operator-validation-sensitive | "I clicked but it didn't fire correctly" → click-disable per atom error chrome |
| 11a (admin preview non-dispatching) | Operator-validation-sensitive | "I want navigate to actually preview destination URL" → relax for navigate verb |

Locks that are **architecturally determined** and NOT operator-validation-sensitive:
- 2a (inline discriminated union ActionConfig)
- 3a (lift to R-4 contract at click-time)
- 3b (baseProps.dataContext propagation)
- 5c (audit logging delegated to backend handlers)
- 5d (no cross-tenant scope)
- 6a (current_row 8th binding source)
- 6b (dataContext propagation chain)
- 6c (no widget-instance audit context)

---

## 15. Process canon candidates surfaced

For end-of-cycle canon-update arc consideration. **NOT filed into DECISIONS.md by this investigation.**

### 15.1 Candidate A — Substrate reuse over substrate parallelism canon

Surfaced by R-4.0 audit. WB-7 could have built a parallel dispatcher; instead consumes + extends R-4.0. The pattern is: when an existing substrate covers ≥50% of the new surface's verbs, consume + extend rather than fork. Specific shape: lift the new surface's data shape into the existing substrate's contract at click-time (Area 3 Lock 3a — Option D). Avoids the duplication + drift cost that Area 3 Option B would incur.

The lesson generalizes beyond WB-7. Future builder UIs (Page Builder, Document Builder, Workflow Builder) likely emit buttons with action contracts; consuming R-4.0 (or its successor) per the same lift-pattern keeps action substrate canonical.

### 15.2 Candidate B — Verb-vocabulary asymmetry canon for cross-substrate action authoring

Surfaced by R-4.0 ↔ WB-7 audit. R-4.0 ships 5 verbs (one set); WB-7 ships 5 verbs (a different set with 3 overlap). The asymmetry is canonical — different authoring surfaces (runtime-host buttons vs. composed widgets) emit subtly different verb needs. R-4.0 has create_vault_item + run_playwright_workflow (administrative operations) but not open_peek + mutate. WB-7 needs the latter because composed widgets exist in row contexts.

The substrate must allow asymmetric vocabularies WITHOUT one substrate constraining the other's vocabulary. Lock 3a's "add new handlers to R-4.0's DISPATCH_HANDLERS" pattern lets both substrates coexist. Process canon: when adding a verb to action substrate, the verb's authoring surfaces are independent decisions from the verb's dispatcher implementation.

### 15.3 Candidate C — Admin-preview non-dispatching pattern

Surfaced by Lock 11a. Admin-tree previews of action-firing surfaces should NOT actually fire actions (no Provider mounts, would 401 backend, would mutate tenant state). The pattern: render a visible "Preview mode" affordance + suppress dispatch. Inherits from R-4.0's null-safe useFocusOptional / useAuthOptional canon (R-5.0.3 + R-5.0.4) and extends it to "any dispatcher invocation."

Future builder UIs displaying action targets in admin preview should adopt the same pattern.

### 15.4 Candidate D — Single-dispatcher-multiple-authoring-surfaces canon

Surfaced by R-4.0 substrate becoming canonical-action-dispatch. The R-4.0 file at `frontend/src/lib/runtime-host/buttons/` was originally authored for runtime-host registered buttons (R-4.0); WB-7 promotes it to canonical-action-substrate. The file's owner header should reflect: "This is the canonical action dispatch substrate; multiple authoring surfaces contribute handlers + binding sources."

Process canon: when a substrate originally authored for one consumer is promoted to canonical for multiple consumers, update file-header ownership notes to reflect.

### 15.5 Candidate E — `current_row` binding source as the first row-iterated context binding

Surfaced by Lock 6a. The 8 binding sources (literal / current_user / current_tenant / current_date / current_route_param / current_query_param / current_focus_id / current_row) span four context categories: literal, identity (user / tenant), URL (route / query), execution (focus / row). Future expansions (current_org, current_workspace, current_record_from_focus) plug into the same enum + resolver pattern. Process canon: ParameterBindingSource enum grows additively; each addition specifies its null-safety semantics for absent context.

### 15.6 Candidate F — Mutate verb's per-kind narrowing as bounded-state-flip canon

Surfaced by Area 2.6. The mutate verb's substrate question (per-entity endpoints vs. generic substrate) resolved as "mutate carries a `mutate_kind` enum; each kind maps to a canonical state-flip endpoint." Phase 1 ships `anomaly_acknowledge` only. Phase 2 adds `mark_read`, `status_flip`, etc. as the enum grows.

The pattern: §12.6a "bounded state flip" canon is operationalized as enum-narrowing on the mutate verb. NOT a generic field-patch substrate. NOT a saved-view-mutation substrate. Process canon: when DESIGN_LANGUAGE establishes a bounded interactivity discipline (§12.6a), the substrate that implements it should narrow its action surface to enumerable canonical kinds, not generalize.

---

## 16. Architectural surprises

### 16.1 Surprise 1 — R-4.0 substrate completeness

WB-original Q-17 lock + WB-4b's `BindingPlaceholderField` "WB-7" caption suggested WB-7 builds an action dispatcher from scratch. The audit surfaced R-4.0 has shipped a substantially similar substrate already with mature production deployment (R-5.0.x edge-panel coordination, null-safe context handling). WB-7's actual scope is materially smaller than the original WB doc anticipated.

### 16.2 Surprise 2 — `baseProps` does NOT propagate `dataContext`

AtomRenderer.tsx:320-323 — `baseProps` excludes `dataContext`. ButtonRenderer's onClick has access to `resolvedBindings` but not the row dict. The substrate gap was invisible until the action context substrate audit (Area 6).

### 16.3 Surprise 3 — Verb vocabulary asymmetry between R-4.0 and WB-7

R-4.0 has 5 verbs; WB-7 has 5 verbs; only 3 overlap. The asymmetry is not coincidental — R-4.0 buttons are page-level admin buttons (create_vault_item, run_playwright_workflow are administrative); WB-7 buttons are widget-level row-context buttons (open_peek + mutate are list-row affordances). Surfacing this is one of the most generative findings of the investigation.

### 16.4 Surprise 4 — `action_ref?: string` field on ButtonConfig is dead

The WB-3/4b forward-compat slot was never populated. Phase 1 retires it. The slot's intent (catalog-keyed action reference) is rejected per Area 2 Lock 2a.

### 16.5 Surprise 5 — Anomaly acknowledge is the §12.6a reference implementation

Surfaced during Area 1.6 audit. `backend/app/api/routes/widget_data.py:353` was authored as the W-3a Phase interactivity discipline test case. WB-7 mutate verb's Phase 1 narrowing to `anomaly_acknowledge` consumes this canonical primitive directly.

### 16.6 Surprise 6 — No admin authoring UI exists for R-4 button contracts today

All R-4 button registrations live in code at `frontend/src/lib/visual-editor/registry/registrations/buttons.ts`. WB-7's ActionPicker is the FIRST admin-authored action substrate on the platform. This has implications beyond WB-7: future builder UIs that author action contracts via admin UI consume the same pattern.

### 16.7 Surprise 7 — workflow start endpoint has 50+ active workflows per tenant

Tier 1 / 2 / 3 / 4 workflows post-Phase-8a accumulate. WB-7 picker UX needs to handle this cardinality. The same shape WB-6 BindingPicker handles for saved views (combobox + search). Not a corner; just a UX scale to verify.

### 16.8 Surprise 8 — Peek substrate has 6 entity types but only 3 wired stubs

Per CLAUDE.md §4: wired = `document_preview` (Phase 5), `ai_question` (follow-up 2), `related_entities` (follow-up 4). Other peek entity types may have GET endpoints + renderers but limited interactive stubs. WB-7's open_peek picker should enumerate the wired set, not the declared 6, for accurate authoring.

---

## 17. Summary — WB-7 substrate-shape verdict

**Investigation conclusion**: WB-7 ships **all 5 action verbs in Phase 1** with **~2,430 LOC** total — production code (~990 LOC) + tests (~1,440 LOC). ZERO new migrations. ZERO new database tables. ZERO new backend endpoints. Substrate decisions:

- ActionRef shape: **inline discriminated union per `action_kind`** (Lock 2a).
- Dispatch runtime: **lift composition-blob ButtonConfig → R-4.0 dispatch invocation at click-time** (Lock 3a). R-4.0 substrate extended with `open_peek` + `mutate` handlers + `current_row` ParameterBindingSource.
- `baseProps.dataContext` propagated through AtomRenderer (Lock 3b).
- Picker UX: **flat verb dropdown + per-verb config form + action preview card** (Locks 4a + 4b + 4c).
- Permissions: **runtime-enforced only** (Lock 5a); per-verb confirm defaults (Lock 5b); audit logging at backend handlers (Lock 5c); no cross-tenant action scope (Lock 5d).
- Context: `current_row` binding source (Lock 6a); no widget-instance audit (Lock 6c).
- Admin preview non-dispatching (Lock 11a).

WB-5 substrate compatibility: **verified** (Area 7). WB-8 substrate compatibility: **verified** (Area 11). Cross-substrate ownership of R-4.0 is documented; both R-4.x and WB-7.x evolve additively.

Operator-validation-sensitive tags: 7 locks (4a, 4b, 4c, 5a, 5b, 7a, 11a). Architecturally-determined locks: 8 locks.

Process canon candidates surfaced: 6 (A through F). NOT filed by this investigation; canon-update arc at end of WB cycle reviews + accepts/rejects.

WB-7 dispatch is ready.
