# Workflow Builder Rebuild — Phase B Build Prompt

> Read-only Phase 5 deliverable closing the Phase B Workflow Builder rebuild investigation arc. Dispatches against Phase 4 phasing recommendation at `docs/investigations/workflow_builder_rebuild_phasing.md` (HEAD `fe58e3c`, 2026-05-27) and Phase 0 audit at `docs/investigations/workflow_builder_rebuild_phase0_audit.md`. Locks per-sub-arc execution context for downstream B-1 → B-5 build dispatch.
>
> Persistent storage from start per DECISIONS.md 2026-05-27 — Persistent-storage discipline for investigation deliverables (Entry 4).

## Phase 5 metadata

- **Arc context:** Phase B Workflow Builder rebuild investigation, Phase 5 of 5 (Phase 0 audit closed → Phase 4 phasing closed + adjudications locked at `fe58e3c` → Phase 5 build prompt drafting → per-sub-arc downstream build dispatch).
- **HEAD at drafting:** `fe58e3c` (Phase B investigation close: 2 investigation deliverables landed; canon at `cce834d` state preserved; 114 stale Playwright screenshot/video deletions in working tree stay UNTOUCHED throughout Phase B).
- **Drafting date:** 2026-05-27
- **Bounded decision (Entry 31):** produce Phase B build prompt deliverable locking per-sub-arc execution context across the 5 substrate-phase sub-arc identities (B-1 → B-5); surface cross-sub-arc invariants; surface material-divergence protocol; surface acknowledgement format; lock NO production code; lock NO canon edits; lock NO STATE.md edits; lock NO build dispatch (per-sub-arc downstream dispatch follows operator confirmation).
- **Adjudications locked at Phase 4 close (operator-confirmed at `fe58e3c`):**
  - **Adjudication 1 (Surface 1 disposition):** `pages/settings/WorkflowBuilder.tsx` (1,876 LOC built-but-mis-shaped legacy) stays legacy at Phase B; disposition deferred post-Phase-B per Entry 3 deferral-tracking. Phase B rebuild target = Surface 3 admin-Studio (`bridgeable-admin/pages/visual-editor/WorkflowEditorPage.tsx`) per Studio-builder Mapping Table canonical mount.
  - **Adjudication 2 (auto-save semantics):** auto-save with locked-to-fork merge semantics preserved at Surface 3 (current 1.5s debounce at lines 354-372; rendered-shared substrate operationally safe via locked-to-fork — distinct from widget-definition clone-vs-shared canon per Entry 9 nuance).
  - **Adjudication 3 (B-8 trigger-variant authoring):** defers post-Phase-B per Entry 2 anti-signal canon. Phase B substrate phase ships single-trigger authoring per current substrate.
  - **Adjudication 4 (sub-arc count):** 5 sub-arcs locked B-1 → B-5 per Entry 30 substrate-similarity clusters seam decomposition. Substrate phase only; integration phase (B-6 / B-7 / B-8) signal-driven post-Phase-B.
  - **Audit-item 1 (four-state substrate framing):** built-operator-facing / built-but-dormant / built-but-mis-shaped / missing files forward to post-Phase-B canon-update arc per deferral-tracking. Phase B does NOT dispatch canon-update arc mid-arc.
  - **Audit-item 2 (September anti-signal):** September Wilbert demo schedule lock holds per Entry 2 anti-signal canon. Phase B substrate phase ships against substrate-correctness, NOT schedule pressure.
- **Operator framing locks preserved:** Phase A → B → C operator-locked sequence; Phase C Document Builder rebuild operates under own pre-dispatch rescoping per Entry 32; Q-B1 boot-adapter shape preserved per Entry 3 deferral-tracking (September-decision arc); task substrate v1 boundary preserved (workflow → task is producer-only at `create_task` action_type per `workflow_engine.py:1173-1241`); v2a / v2c / v2b out-of-scope at Phase B.
- **Lineage reference:** Phase 0 audit + Phase 4 phasing are upstream deliverables; this build prompt is the downstream-dispatch substrate. Per-sub-arc dispatch wrappers (~200-400 words each) draft against this durable build prompt when each sub-arc dispatches per Entry 32 per-arc pre-dispatch rescoping.

---

## §1. Phase B overview + sub-arc sequencing

### 1.1 Phase B substrate phase bounded decision (Entry 31)

Phase B substrate phase's bounded decision = **rebuild Surface 3 admin-Studio Workflow Editor authoring substrate from current step-list-with-bespoke-editors paradigm to canonical builder-rebuild shape (graph canvas + node-type registry + per-type inspector configs + always-visible preview substrate + selection-driven inspector chrome) matching Focus Builder + Widget Builder rebuild precedent.** Phase B substrate phase closes when all 5 sub-arc commits land, Surface 3 substrate at built-operator-facing canonical state per Phase 0 audit §A.2 four-state framing, all 8 Phase 0 audit §E wrong-shape observations addressed via locked sub-arc coverage, 7 cross-arc boundaries preserved per Phase 0 audit §G, STATE.md close note appends at B-5 final commit.

### 1.2 Sub-arc dispatch sequence

Per Adjudication 4 locked decomposition + Phase 4 §3.1 substrate-similarity clusters per Entry 30:

```
B-1  →  B-2  →  B-3  →  B-4  →  B-5
```

Sequencing rationale:
- **B-1 first** — graph canvas foundation establishes the DAG-shaped authoring substrate that B-2 through B-5 layer on top. First-of-kind canvas model (DAG distinct from Monitor grid + Decide free-form per Phase 0 audit §E.3 finding); widest calibration band per Entry 24 (first-of-kind substrate); cannot dispatch B-2 onward until canvas shape is settled.
- **B-2 second** — node-type registry expansion 2→28 establishes the per-type registration substrate that B-3 inspector configs reference via `getByType()` registry introspection (per CLAUDE.md §4 Component Registry canon). Registry expansion mechanically scaffolds 26 new entries; smaller and tighter calibration band per Entry 24.
- **B-3 third** — per-type inspector configs ship 14-26 new inspector components against the locked registry shape (B-2). Sub-arc cohort largest by component count; benefits from registry stability landed in B-2.
- **B-4 fourth** — always-visible preview substrate ships execution-trace visualization. Independent of inspector substrate (B-3); could in principle ship before B-3 but preserves "canvas → registry → per-type configs → preview" cognitive grouping per Entry 30 substrate-similarity. Could be re-sequenced if material-divergence surfaces; default sequencing preferred for substrate-shape coherence.
- **B-5 fifth** — selection-driven inspector chrome ships cross-cutting selection-context refactor. Smallest sub-arc; closes substrate phase by integrating background-click + edge-click + workflow-level chrome editing with the per-type inspector substrate from B-3.

### 1.3 Phase B substrate phase close criterion

- All 5 sub-arc commits land at HEAD (single-commit-at-arc-close per Entry 26; ≤ ~2,500 LOC per sub-arc fits default regime; B-1 first-of-kind canvas substrate may earn 2-commit-within-arc-identity per WB-4 precedent if seam surfaces at audit-first phase).
- Surface 3 at `frontend/src/bridgeable-admin/pages/visual-editor/WorkflowEditorPage.tsx` rebuilt to canonical builder-rebuild shape:
  - Graph canvas replaces `<ol><li>` rendering currently at lines 924-1004 per Phase 0 audit §A.2 evidence
  - Hardcoded 16-tuple palette JSX currently at lines 893-905 replaced with registry-driven palette consuming `workflow-nodes.ts` 28-entry expansion from B-2
  - All 28 canonical `VALID_NODE_TYPES` (`canvas_validator.py:62-105`) carry component registry entries with ≥3 `configurableProps` per Component Registry canon (CLAUDE.md §4)
  - All 28 canonical node types have per-type inspector configs (extending current 2: `InvokeGenerationFocusConfig.tsx` + `InvokeReviewFocusConfig.tsx`)
  - Always-visible execution-trace preview pane operational per Entry 14
  - Selection state extended: empty / node / edge / background-click selection contexts; per-selection chrome editing
- WorkflowTemplate + TenantWorkflowFork schema unchanged (no Phase B migration per Phase 0 audit §C.4; migration head r109 stays)
- `workflow_engine.py` substrate unchanged (out-of-scope per Phase 0 audit §D + Adjudication invariant)
- 9-endpoint platform-realm router at `backend/app/api/routes/admin/visual_editor_workflows.py` (lines 203-369) unchanged
- Auto-save with locked-to-fork merge semantics preserved (current 1.5s debounce at lines 354-372 per Adjudication 2)
- 7 cross-arc boundaries preserved per Phase 0 audit §G
- Test cohort accumulation per sub-arc per Entry 24 (~30-80 new tests across substrate phase per WB cycle precedent)
- STATE.md update appends at B-5 final commit (per Phase 4 §6.2 narrative discipline)

### 1.4 Canon-anchor

HEAD `fe58e3c` at Phase 5 drafting. Per-sub-arc downstream builds anchor against their own dispatch HEAD (which may advance per intermediate sub-arc commits). Phase B substrate phase operates entirely against the canon state at HEAD `cce834d` (canon at canon-update arc close; Phase B investigation arc-close at `fe58e3c` introduced no canon edits) plus its own accumulating sub-arc commits.

### 1.5 Integration phase relationship

Per Phase 4 §2 integration phase final-lock + Phase 4 §5.2 substrate-phase → integration-phase signal pattern:

- B-6 (UX refinements 1-3 sub-arcs depending on signal) dispatches on operator-observable workflow signal **during/after substrate-phase operator validation** — not part of Phase B substrate phase scope.
- B-7 (Surface 1 disposition) dispatches on §8.1 operator decision per Entry 32 — not part of Phase B substrate phase scope.
- B-8 (trigger-variant authoring) defers post-Phase-B per Adjudication 3 + Entry 2 anti-signal canon.

Integration phase signals NOT triggered by substrate-phase close per Phase 4 §5.4 anti-signals (LOC threshold rejected; count threshold rejected; September Wilbert demo rejected; engineering preference rejected; aesthetic-completeness rejected; sunk-cost rejected; substrate-mature-signal-for-downstream rejected).

---

## §2. Per-sub-arc execution context

### §2.A — Sub-arc B-1 (Graph canvas foundation)

#### §2.A.1 Bounded decision (Entry 31)

**Replace the current `<ol><li>` vertical-list canvas rendering at `WorkflowEditorPage.tsx:924-1004` with a graph-canvas authoring substrate matching the runtime DAG layout model per Entry 11 WYSIWYG discipline; node positioning consumes existing `canvas_state.nodes[].position: {x, y}` field (already in canvas-state schema per `canvas_validator.py:6-39`); edge rendering replaces the current "→ target_label" text fragments (lines 962-985) with visible graph edges; branching + parallel split/join visualized as multi-edge fan-out / fan-in. B-1 closes when graph-canvas substrate operational at Surface 3, current vertical-list rendering removed, position-field consumption preserved through canvas-state JSONB roundtrip, all existing edit affordances (node selection, edge add/remove via NodeConfigForm) carry forward bit-for-bit, server canvas-validator at `canvas_validator.py` + frontend mirror at `lib/visual-editor/workflows/canvas-validator.ts:244 LOC` schema contracts unchanged.**

#### §2.A.2 Substrate scope

**What changes:**
- **NEW canvas substrate component:** `frontend/src/bridgeable-admin/components/visual-editor/workflow-canvas/GraphCanvas.tsx` (new file; ~600-900 LOC) — purely-presentational graph-canvas renderer consuming `canvas_state.nodes[]` + `canvas_state.edges[]` from the existing canvas-state JSONB; renders nodes at `position: {x, y}` coordinates; renders edges as SVG path elements between source/target node positions; handles node drag-positioning via @dnd-kit (precedent: Focus Builder FF-2 free-form canvas at `frontend/src/components/focus-builder/*` per `2026-05-20-free-form-focus-canvas.md` deliverable); emits canvas-state mutations to parent `WorkflowEditorPage.tsx` via callback API (parent owns persistence + auto-save debounce per Adjudication 2).
- **NEW canvas helper:** `frontend/src/lib/visual-editor/workflows/canvas-layout.ts` (new file; ~150-250 LOC) — pure functions for canvas coordinate helpers: `computeNodeDefaultPosition()` (auto-place new nodes when palette adds; collision-avoidance against existing positions), `computeEdgePath()` (SVG path from source→target with branching/parallel coordinates), `bbox()` (canvas bounding box for auto-fit), `clampToCanvas()` (canvas-bounded drag clamp). Unit-testable in vitest without JSDOM/dnd-kit pointer-gesture limitation per Q-40 canon.
- **WorkflowEditorPage.tsx canvas section refactor** at lines 924-1004 — replace `<ol><li>` rendering with `<GraphCanvas>` mount; preserve scope selector at lines 648-880 + node configuration form at lines 1009-1030 verbatim; preserve HierarchicalEditorBrowser browser at line 761 verbatim; preserve top palette at lines 884-905 (hardcoded 16-tuple JSX) verbatim **at B-1** — palette migrates to registry-driven at B-2, not B-1.
- **Canvas-state schema extension:** existing `position: {x, y}` field per `canvas_validator.py:6-39` interface IS the canvas position substrate; **no schema change needed**. Existing 28-value `VALID_NODE_TYPES` (`canvas_validator.py:62-105`) preserved verbatim.

**What stays unchanged:**
- Backend `workflow_templates/template_service.py:650 LOC` + `canvas_validator.py:260 LOC` (zero LOC; substrate already supports position field).
- Platform-realm router `backend/app/api/routes/admin/visual_editor_workflows.py:401 LOC` (zero LOC; 9 endpoints unchanged).
- WorkflowTemplate + TenantWorkflowFork schema at `r82_workflow_templates` (zero LOC; no migration).
- `frontend/src/lib/visual-editor/registry/registrations/workflow-nodes.ts:196 LOC` (B-2 scope; B-1 leaves 2-of-28 registration count unchanged).
- `bridgeable-admin/components/visual-editor/workflow-canvas/NodeConfigForm.tsx:248 LOC` + `InvokeGenerationFocusConfig.tsx` + `InvokeReviewFocusConfig.tsx` (B-3 scope; B-1 leaves per-type configs unchanged).
- `workflow-templates-service.ts:231 LOC` admin client (zero LOC; canvas-state payload shape unchanged).
- Surface 1 + Surface 2 tenant-side surfaces (per Adjudication 1).
- Auto-save debounce at `WorkflowEditorPage.tsx:354-372` (per Adjudication 2; canvas-state mutations from `GraphCanvas` flow through existing auto-save path).
- Studio rail integration at `StudioShell.tsx:70` (zero LOC; mount path unchanged).

#### §2.A.3 Addresses Phase 0 audit §E observation #1

Phase 0 audit §E.5 observation #1 — "Canvas rendering as vertical list rather than graph (Entry 11 WYSIWYG violation)" — closes at B-1 via `<GraphCanvas>` replacement of `<ol><li>` rendering. Per Phase 0 audit §E.3 finding: workflows are a **third canvas model distinct from Decide (free-form per Entry 11) and Monitor (grid per 2026-05-20 Monitor-vs-Decide canon)** — DAG-shaped. B-1 substrate ships this third canvas model; future canvas substrates (e.g., Phase C document block canvas) operate under own decompositional discipline per Entry 32.

#### §2.A.4 LOC envelope per Entry 24

Per Phase 4 §3.1 + §7.1 wide calibration band for first-of-kind substrate:

- GraphCanvas.tsx: ~600-900
- canvas-layout.ts: ~150-250
- WorkflowEditorPage.tsx canvas-section refactor: ~150-300 (delta against existing 924-1004 block)
- Tests: ~600-1,000 (vitest unit + integration; Playwright deferred per Q-40 dnd-kit limitation)

**B-1 envelope: ~1,500-2,500 LOC.** Per Phase 4 §7.1 wide calibration band: first-of-kind canvas substrate may exceed band per WB-4 precedent (canvas sub-arc historically widest variance). If sub-arc surfaces 2-commit seam at audit-first phase (e.g., GraphCanvas substrate + WorkflowEditorPage integration cleanly separable), 2-commit-within-arc-identity per Entry 26 multi-commit regime is acceptable.

#### §2.A.5 Test cohort shape

Per WB cycle test cohort precedent + Q-40 canon (operator-observable canon: assert against rendered inline-style + DOM attributes; pure-function unit tests cover dnd-kit interaction logic that JSDOM can't exercise):

- `GraphCanvas.test.tsx` — render with empty canvas-state / single-node / multi-node / multi-edge / branching shape / parallel split-join shape (~8-12 tests)
- `canvas-layout.test.ts` — pure-function tests for `computeNodeDefaultPosition` / `computeEdgePath` / `bbox` / `clampToCanvas` (~10-15 tests)
- `WorkflowEditorPage.test.tsx` extension — integration test asserting GraphCanvas mounts; canvas-state mutations propagate to auto-save path (~3-5 tests)
- Playwright `workflow-canvas-graph.spec.ts` — operator-observable assertions on rendered graph at staging deploy (drag node; verify edge re-routes; verify canvas-state JSONB roundtrip); dnd-kit drag gesture deferred to natural-refactor per Q-40 if integration test sufficient (~2-4 specs, optional)

**B-1 test cohort: ~25-40 new tests.**

#### §2.A.6 Material-divergence triggers per Entry 23

- GraphCanvas substrate surfaces graph-rendering complexity beyond SVG-path-between-nodes (e.g., edge routing requires `dagre` or `elkjs` algorithm package; if so, surface for scope adjustment vs in-house simple routing).
- `position: {x, y}` field surfaces as insufficient for graph layout (e.g., canvas-state requires curve control points; if so, this is canvas-state schema extension and surfaces canon-update arc trigger).
- Existing 16-of-28 hardcoded palette types lack `position` defaults causing positionless nodes (palette migration is B-2 scope; if B-1 surfaces palette-coupled position requirement, scope-creep flag).
- Auto-save debounce flow doesn't cleanly accept canvas-state mutations from `GraphCanvas` (mutation API shape mismatch; surface for re-shape).
- LOC envelope exceeds 2,500 by >20%.
- dnd-kit interaction substrate surfaces JSDOM testability gap beyond Q-40 canon known limitation (defer Playwright; flag for staging-environment verification).
- Material-divergence STOPs before commit; surface to operator per Entry 23 protocol verbatim.

#### §2.A.7 Acknowledgement format

B-1 sub-arc dispatch wrapper acknowledges per Entry 32 per-arc pre-dispatch rescoping. Acknowledgement reads:
- This Phase 5 build prompt §2.A
- Phase 0 audit §A (substrate state) + §E (wrong-shape observation #1) + §F (WB / Focus Builder precedent)
- Phase 4 phasing §1 + §3.1 + §7.1
- Current `WorkflowEditorPage.tsx` lines 924-1004 (canvas rendering at HEAD `fe58e3c`)
- Current `canvas_validator.py:6-39` (canvas-state schema) + `canvas_validator.py:62-105` (VALID_NODE_TYPES)
- DECISIONS.md 2026-05-27 Entries 11 (WYSIWYG canonical), 14 (always-visible preview substrate — referenced for B-4 sub-arc; B-1 awareness only), 30 (substrate-similarity clusters), 31 (bounded-decision), 32 (per-arc pre-dispatch rescoping)

Then verifies: substrate state at file:line precision; B-1 LOC envelope within Entry 24 band; cross-sub-arc invariants per §3; material-divergence triggers explicit per §2.A.6. Operator confirms before B-1 build sub-agent dispatches.

---

### §2.B — Sub-arc B-2 (Node-type registry expansion 2→28)

#### §2.B.1 Bounded decision (Entry 31)

**Expand `frontend/src/lib/visual-editor/registry/registrations/workflow-nodes.ts` from current 2 registered node types (`generation-focus-invocation` + `send-communication` per CLAUDE.md §4 Component Registry Phase 1 ledger) to all 28 canonical types enumerated in `canvas_validator.py:62-105` `VALID_NODE_TYPES` tuple. Each registration carries identity (type + name + displayName + category), token consumption (`consumedTokens`), `configurableProps` (≥3 per Component Registry canon at CLAUDE.md §4 + DECISIONS.md 2026-05-19 ≥3 configurableProps canon), `schemaVersion`, `componentVersion`. Hardcoded 16-tuple palette JSX at `WorkflowEditorPage.tsx:893-905` migrates to registry-driven palette consuming `getAllRegistered({type: 'workflow-node'})` from `lib/visual-editor/registry/`. B-2 closes when 28-entry registration count operational, palette JSX renders from registry introspection, registry introspection helpers (`getByType` / `getByName`) verified for workflow-node category, registration vitest backfill validation suite green (per Phase 3 Component Configuration canon at CLAUDE.md §4 Component Registry).**

#### §2.B.2 Substrate scope

**What changes:**
- **NEW 26 registrations in `frontend/src/lib/visual-editor/registry/registrations/workflow-nodes.ts`** — expand from current 2 entries to 28. Net additions: 26 new `registerComponent()` HOC invocations covering all `VALID_NODE_TYPES` canonical-vocabulary entries minus the 2 already registered. Per-entry shape per Component Registry canon (CLAUDE.md §4):
  - `type: 'workflow-node'`
  - `name: '<canonical_node_type>'` (matches `VALID_NODE_TYPES` string)
  - `displayName: '<human-readable>'`
  - `category: '<lifecycle | data | branch | parallel | trigger | task | document | focus | cross-tenant | misc>'` (curated taxonomy for palette grouping)
  - `verticals: ['*']` (cross-vertical workflows are platform-shaped per Phase 0 audit §C)
  - `userParadigms: ['admin']` (Phase B target is admin-Studio Workflow Editor)
  - `consumedTokens: [<DESIGN_LANGUAGE token names>]`
  - `configurableProps: [<≥3 prop schemas with type / default / bounds / displayLabel>]`
  - `schemaVersion: 1`
  - `componentVersion: 1`
- **WorkflowEditorPage.tsx palette refactor** at lines 884-905 — replace hardcoded 16-tuple JSX (`start, action, decision, branch, parallel_split, parallel_join, schedule, send-communication, generation-focus-invocation, invoke_generation_focus, invoke_review_focus, cross_tenant_order, cross_tenant_request, playwright_action, log_vault_item, end`) with iteration over `getAllRegistered({type: 'workflow-node'})` keyed by `category` for palette grouping; node-type icon resolution via existing `ICON_MAP` pattern from DotNav (or analog `WORKFLOW_NODE_ICON_MAP`) with fallback to colored category dot.
- **Auto-register barrel update at `frontend/src/lib/visual-editor/registry/auto-register.ts`** — verify all 28 workflow-node registrations imported; backfill registration count.
- **Vitest backfill validation suite extension at `frontend/src/lib/visual-editor/registry/registry.test.ts`** (or equivalent) — assert `getAllRegistered({type: 'workflow-node'}).length === 28`; assert each canonical `VALID_NODE_TYPES` value has registration; assert ≥3 configurableProps per registration; assert per-registration consumedTokens declares valid tokens against `tokens.css` (per Phase 3 backfill validation precedent).

**What stays unchanged:**
- Backend `workflow_templates/canvas_validator.py:62-105` `VALID_NODE_TYPES` tuple (zero LOC; serves as canonical vocabulary input to B-2 registry expansion).
- Backend `workflow_engine.py` `_execute_action` dispatch at lines 635-693 (zero LOC; 17-value runtime vocabulary unchanged per Phase 0 audit §D + cross-sub-arc invariant per §3).
- `bridgeable-admin/components/visual-editor/workflow-canvas/NodeConfigForm.tsx:248 LOC` (B-3 scope; B-2 leaves inspector dispatch unchanged — palette renders from registry; per-type inspector configs land at B-3).
- `GraphCanvas.tsx` from B-1 (B-2 doesn't modify; palette-to-canvas drop logic in WorkflowEditorPage.tsx handles registry-typed nodes via existing canvas-state shape).
- Surface 1 + Surface 2 (per Adjudication 1; Surface 1's parallel step-type vocabulary at lines 55-62 stays separate from canonical 28-vocabulary).
- WorkflowTemplate + TenantWorkflowFork schema (no migration).
- 9-endpoint admin platform router (zero LOC).
- Per-node-type inspector substrate (`InvokeGenerationFocusConfig.tsx` + `InvokeReviewFocusConfig.tsx`) — preserved verbatim; B-3 expands.

#### §2.B.3 Addresses Phase 0 audit §E observation #6

Phase 0 audit §E.5 observation #6 — "26-of-28 canonical node types unregistered in component registry" — closes at B-2 via 26 new registrations. Per Phase 0 audit §E.4 concrete gap: every new registration carries `configurableProps` per Component Registry canon. The registry expansion is **mechanical substrate scaffolding** analogous to Widget Builder atom-catalog Phase 1 (8 atoms locked) + Phase 1 expansion candidates pattern per CLAUDE.md §4 Component Registry. Per Phase 4 §3.3 substrate-similarity clusters: B-2 + B-3 form **registry + per-registry-entry-config pair** (analogous to WB-2 atom catalog + WB-3 atom registry pattern). B-2 ships the registry; B-3 ships the per-entry inspector configs.

#### §2.B.4 LOC envelope per Entry 24

Per Phase 4 §7.1 narrow calibration band (mechanical substrate-cohort scaffolding):

- Net 26 new registrations × ~30-60 LOC per registration (per Component Registry canon registration shape complexity): ~800-1,500 LOC
- WorkflowEditorPage.tsx palette refactor at lines 884-905: ~50-100 LOC delta
- Auto-register barrel + vitest backfill: ~50-100 LOC
- Tests: ~200-400 LOC

**B-2 envelope: ~800-1,500 LOC.** Narrow calibration band per Entry 24 (mechanical scaffolding; per-entry complexity bounded by Component Registry canon shape).

#### §2.B.5 Test cohort shape

- `workflow-nodes-registry.test.ts` — assert `getAllRegistered({type: 'workflow-node'}).length === 28`; per-name registration coverage check (28 individual asserts); ≥3 configurableProps per registration; consumedTokens validity against tokens.css catalog; schemaVersion + componentVersion present (~10-15 tests)
- `WorkflowEditorPage.test.tsx` palette extension — assert palette renders all 28 types; assert category grouping; assert click-to-add node populates canvas with correct node type (~5-8 tests)
- `auto-register.test.ts` extension — verify all 28 workflow-node registrations imported at module load (~2-3 tests)

**B-2 test cohort: ~15-25 new tests.**

#### §2.B.6 Material-divergence triggers per Entry 23

- VALID_NODE_TYPES count diverges from 28 (e.g., earlier sub-arc commit advances vocabulary; if so, B-2 dispatch wrapper re-verifies count at sub-arc HEAD).
- Per-node-type `configurableProps` ≥3 requirement surfaces canonical-vocabulary ambiguity (e.g., `start` and `end` lifecycle markers have no meaningful configurable props beyond `label`; if so, surface for either node-type-specific minimum-props override OR canonical vocabulary refinement).
- Category taxonomy surfaces ambiguity (e.g., `schedule` is `trigger` or `lifecycle`; if material-divergence, surface for operator adjudication).
- Token consumption surfaces gaps (e.g., new node type needs new token; canon-update arc trigger; STOP).
- LOC envelope exceeds 1,500 by >20% (e.g., per-registration complexity higher than estimated per Entry 24).
- B-2 work surfaces canvas-state schema extension requirement (canon-update arc trigger; STOP).
- Material-divergence STOPs before commit; surface to operator per Entry 23 protocol verbatim.

#### §2.B.7 Acknowledgement format

B-2 sub-arc dispatch wrapper acknowledges per Entry 32 per-arc pre-dispatch rescoping. Acknowledgement reads:
- This Phase 5 build prompt §2.B
- Phase 0 audit §E.4 + §E.5 (registry coverage gap)
- Phase 4 phasing §3.1 + §3.3 (B-2/B-3 substrate-similarity cluster pair)
- B-1 sub-arc commit at sub-arc-HEAD (if B-1 already shipped; verify GraphCanvas operational + canvas-state position field consumed correctly)
- Current `workflow-nodes.ts:196 LOC` (2-of-28 baseline)
- Current `VALID_NODE_TYPES` at `canvas_validator.py:62-105`
- CLAUDE.md §4 Component Registry canon (Phase 1 + Phase 3 + Component Classes ledger)
- DECISIONS.md 2026-05-27 Entry 30 (substrate-similarity clusters)

Then verifies: substrate state at file:line precision; B-2 LOC envelope within band; cross-sub-arc invariants per §3; material-divergence triggers explicit per §2.B.6. Operator confirms before B-2 build sub-agent dispatches.

---

### §2.C — Sub-arc B-3 (Per-type inspector configs 14-26 new)

#### §2.C.1 Bounded decision (Entry 31)

**Ship 14-26 new per-node-type inspector configs at `frontend/src/bridgeable-admin/components/visual-editor/workflow-canvas/` covering all 28 canonical `VALID_NODE_TYPES` (`canvas_validator.py:62-105`) — extending the current 2 inspector configs (`InvokeGenerationFocusConfig.tsx` + `InvokeReviewFocusConfig.tsx`). NodeConfigForm.tsx (currently 248 LOC at `workflow-canvas/`) dispatches by node type to dedicated inspector components instead of falling through to generic JSON textarea for 14-of-16 types (Phase 0 audit §A.2 evidence at WorkflowEditorPage.tsx:1019-1028). Each new inspector consumes node `config: {...}` JSONB shape from canvas-state and emits typed mutations back to parent via callback API matching existing inspector pattern. B-3 closes when all 28 canonical node types have dedicated inspector configs operational, NodeConfigForm dispatch covers full vocabulary, generic JSON textarea fallback removed (canonical builder rebuild pattern violation closed per Phase 0 audit §E.3), per-inspector vitest unit coverage green.**

#### §2.C.2 Substrate scope

**What changes:**
- **NEW 14-26 inspector config components in `frontend/src/bridgeable-admin/components/visual-editor/workflow-canvas/`** — one per canonical `VALID_NODE_TYPES` entry minus the 2 already shipped + minus the 2 lifecycle markers (`start`, `end`) which may carry minimal `LifecycleMarkerConfig.tsx` shared inspector if `configurableProps` minimum permits (per B-2 material-divergence trigger resolution). Estimated 14 new dedicated configs + 12-14 grouped configs (e.g., `BranchConfig` for `branch`/`decision`; `ParallelSplitJoinConfig` for `parallel_split`/`parallel_join`; `CrossTenantConfig` for `cross_tenant_order`/`cross_tenant_request`/`cross_tenant_acknowledgment`). Per-inspector shape:
  - Consumes `node.config: Record<string, unknown>` from canvas-state JSONB
  - Renders form controls per `configurableProps` from B-2 registry registration (`getByType('workflow-node').configurableProps.find(p => p.name === ...)` introspection)
  - Emits typed `onChange(node.id, config_patch)` callback to parent (`NodeConfigForm` proxies to `WorkflowEditorPage`)
  - Uses DESIGN_LANGUAGE token vocabulary verbatim (no new tokens)
  - Pattern matches existing `InvokeGenerationFocusConfig.tsx` + `InvokeReviewFocusConfig.tsx`
- **NodeConfigForm.tsx dispatch table extension** at line 1019-1028 — extend the per-node-type dispatch from 2 entries to 28; remove generic JSON textarea fallback (formerly lines ~1015-1027 — exact lines verify at B-3 dispatch HEAD); keep "unknown node type" fallback only as defensive shape for future canon-vocabulary changes.
- **Per-inspector vitest coverage** at `workflow-canvas/__tests__/<NodeType>Config.test.tsx` — render with empty config / full config / partial config; assert form controls render per registry configurableProps; assert onChange propagates typed mutations.

**What stays unchanged:**
- `workflow-nodes.ts:196 LOC` (B-2 scope; B-3 consumes registry but doesn't extend it).
- `GraphCanvas.tsx` from B-1 (canvas substrate; B-3 inspector layer is right-rail orthogonal).
- `canvas_validator.py:62-105 VALID_NODE_TYPES` (canonical vocabulary unchanged).
- Backend service layer (zero LOC).
- WorkflowTemplate + TenantWorkflowFork schema (no migration).
- 9-endpoint admin platform router (zero LOC).
- WorkflowEditorPage.tsx outside NodeConfigForm dispatch (auto-save path unchanged; canvas-state mutation flow unchanged).
- Surface 1 + Surface 2 (per Adjudication 1).
- B-4 preview substrate (lands at B-4 sub-arc).
- B-5 selection chrome (lands at B-5 sub-arc; B-3 per-type inspectors render inside existing right-rail selection-context unchanged).

#### §2.C.3 Addresses Phase 0 audit §E observations #2 + #3

Phase 0 audit §E.5 observation #2 — "Hardcoded palette → node-type registry-driven palette" — closes via B-2 registry expansion + WorkflowEditorPage palette refactor. B-3 closes Phase 0 audit §E.5 observation #3 — "Generic JSON textarea fallback → per-node-type config components" — via dedicated inspector components covering all 28 canonical types. Per Phase 4 §3.3 substrate-similarity clusters: B-2 + B-3 form the **registry + per-registry-entry-config pair**.

#### §2.C.4 LOC envelope per Entry 24

Per Phase 4 §7.1 narrow calibration band (per-inspector ~100-200 LOC × ~14-26 components):

- 14 dedicated inspector configs × ~100-200 LOC = ~1,400-2,800
- 6-8 grouped inspector configs × ~120-220 LOC = ~720-1,760 (estimated lower than dedicated since grouped configs share substrate)
- NodeConfigForm.tsx dispatch table extension: ~30-60 LOC
- Per-inspector vitest tests: ~50-100 LOC × 14-26 = ~700-2,600 LOC

**B-3 envelope: ~1,500-2,500 LOC** (refinement of Phase 4 §7.1 estimate; per-inspector complexity bounded by existing `InvokeGenerationFocusConfig.tsx` precedent at ~150-200 LOC).

Per Entry 24 four-instance calibration pattern + B-1/B-2 precedent (if shipped): B-3 calibration band tighter; substrate-cohort is well-bounded by registry shape from B-2.

#### §2.C.5 Test cohort shape

- 14-26 new `<NodeType>Config.test.tsx` files — render with empty/full/partial config; form controls per registry configurableProps; onChange typed mutations (~4-8 tests per file × 14-26 files = ~56-208 tests)
- `NodeConfigForm.test.tsx` extension — dispatch coverage for all 28 canonical types; unknown-type fallback (~5-8 tests)
- Playwright `workflow-inspector-coverage.spec.ts` — assert each canonical node type has dedicated inspector; staging verification (~1-3 specs)

**B-3 test cohort: ~60-150 new tests** (large because per-inspector test files are independent units).

#### §2.C.6 Material-divergence triggers per Entry 23

- B-2 registry expansion surfaces canonical configurableProps shape ambiguity that B-3 dispatch-time discovers (e.g., per-prop type/default/bounds incomplete; STOP and surface).
- Per-type inspector renders surface canvas-state schema gap (e.g., `cross_tenant_order` needs additional canvas-state field beyond `node.config`; STOP for canon-update arc trigger).
- Grouped vs dedicated inspector decomposition surfaces seam misalignment (e.g., `branch` and `decision` differ enough that they earn dedicated configs; or conversely, more types can be grouped than estimated; surface for re-decomposition).
- LOC envelope exceeds 2,500 by >20% per Entry 24.
- B-3 work surfaces requirement for plugin-shaped contract per Phase 4 §6.4 (workflow node inspector configs canonical contract; canon-update arc trigger).
- Material-divergence STOPs before commit; surface to operator per Entry 23 protocol verbatim.

#### §2.C.7 Acknowledgement format

B-3 sub-arc dispatch wrapper acknowledges per Entry 32 per-arc pre-dispatch rescoping. Acknowledgement reads:
- This Phase 5 build prompt §2.C
- Phase 0 audit §A (Surface 3 NodeConfigForm at 248 LOC + 2 existing per-type configs) + §E.5 observations #2 + #3
- Phase 4 phasing §3.1 + §3.3
- B-2 sub-arc commit at sub-arc-HEAD (verify 28-entry registration count; ≥3 configurableProps per entry)
- Current `NodeConfigForm.tsx` dispatch shape at HEAD
- Existing per-type config precedent (`InvokeGenerationFocusConfig.tsx` + `InvokeReviewFocusConfig.tsx`)
- CLAUDE.md §4 Component Registry canon
- DECISIONS.md 2026-05-27 Entries 23, 24, 30

Then verifies: substrate state at file:line precision; B-3 LOC envelope within band; cross-sub-arc invariants per §3; material-divergence triggers explicit per §2.C.6. Operator confirms before B-3 build sub-agent dispatches.

---

### §2.D — Sub-arc B-4 (Always-visible preview substrate)

#### §2.D.1 Bounded decision (Entry 31)

**Ship always-visible preview substrate at Surface 3 — `frontend/src/bridgeable-admin/components/visual-editor/workflow-canvas/WorkflowPreviewPane.tsx` (new) — rendering execution-trace visualization of the authored canvas-state per Entry 14 always-visible preview substrate canon. Preview substrate operates at design-time without invoking the runtime `workflow_engine.advance_run` path (engine is out-of-scope per Phase 0 audit §D + cross-sub-arc invariant per §3); preview computes a simulated execution trace via canvas-state graph traversal (DFS over `nodes` + `edges` from `start` node) showing per-node "would-execute-with-config" state at each step. Distinct from WB cycle preview substrate (widget composition tree render at WB-5 per `2026-05-23-widget-builder-canvas-preview.md`) because workflows are DAG-shaped — preview shape is execution-trace + per-node state visualization, not rendered-component preview. B-4 closes when preview pane operational at WorkflowEditorPage right rail OR overlay-shaped per operator-decision-at-acknowledgement, canvas-state edits propagate live to preview within one render frame, simulated execution trace verifiable against canonical workflow shapes (linear / branching / parallel split-join).**

#### §2.D.2 Substrate scope

**What changes:**
- **NEW preview substrate component:** `frontend/src/bridgeable-admin/components/visual-editor/workflow-canvas/WorkflowPreviewPane.tsx` (~400-700 LOC) — purely-presentational preview pane consuming canvas-state from parent; computes simulated execution trace via pure-function `simulateExecutionTrace(canvas_state)` helper; renders per-node simulated state (would-execute / branch-skipped / parallel-active / waiting / terminal); renders per-edge state (would-follow / skipped). Pattern matches Phase 2 + Phase 3 visual-editor preview substrate (`/visual-editor/themes` + `/visual-editor/components` live preview).
- **NEW execution-trace helper:** `frontend/src/lib/visual-editor/workflows/simulate-trace.ts` (~200-400 LOC) — pure functions for trace simulation. Key functions:
  - `simulateExecutionTrace(canvas_state: CanvasState): ExecutionTrace` — DFS from `start` node; resolves branching via configurable preview-mode (e.g., always-take-first-branch; user-toggles-per-decision); fan-out at parallel_split; fan-in at parallel_join; terminates at `end`.
  - `nodeStateAtTrace(trace: ExecutionTrace, node_id: string): NodeSimulatedState` — per-node would-execute/skipped/parallel-active/terminal lookup.
  - `edgeStateAtTrace(trace: ExecutionTrace, edge_id: string): EdgeSimulatedState` — per-edge would-follow/skipped lookup.
- **WorkflowEditorPage.tsx layout extension** — preview pane integration per operator-decision-at-acknowledgement-time on substrate shape. Default recommendation: right rail bottom section (below NodeConfigForm) at fixed-height; alternative: collapsible overlay pane; alternative: separate `/preview` route. Decision pivot surfaced as material-divergence trigger at B-4 dispatch acknowledgement.
- **Auto-save debounce orchestration unchanged** (per Adjudication 2); preview pane consumes canvas-state via existing parent-managed state — preview updates live as auto-save debounce captures mutations.

**What stays unchanged:**
- Backend `workflow_templates/*` (zero LOC; preview is frontend-only substrate).
- Backend `workflow_engine.py` (zero LOC; preview does NOT invoke runtime engine per cross-sub-arc invariant; preview is frontend pure-function simulation).
- WorkflowTemplate + TenantWorkflowFork schema (no migration).
- 9-endpoint admin platform router (zero LOC).
- `canvas_validator.py:62-105 VALID_NODE_TYPES` (preview consumes vocabulary; doesn't extend).
- `workflow-nodes.ts` from B-2 (preview consumes registrations for per-node visualization labeling; doesn't extend).
- Per-type inspector configs from B-3 (preview is orthogonal to inspector — preview displays simulated execution; inspector edits config).
- `GraphCanvas.tsx` from B-1 (preview is separate pane; canvas remains primary authoring surface).
- B-5 selection chrome (B-5 selection-state extension may enhance preview-pane interactivity; B-4 ships preview at non-selection-bound substrate).

#### §2.D.3 Addresses Phase 0 audit §E observation #4

Phase 0 audit §E.5 observation #4 — "No live render preview" — closes at B-4 via always-visible preview substrate. Per Entry 14 (always-visible preview substrate for operator-as-platform-builder authoring): canonical builder rebuild ships always-visible preview substrate. For workflows, preview semantics = simulated execution trace + per-node state visualization (distinct from widget composition tree per WB-5 `2026-05-23-widget-builder-canvas-preview.md` reference and from Phase 2/3 visual-editor preview which renders style/component output).

#### §2.D.4 LOC envelope per Entry 24

Per Phase 4 §7.1 wide calibration band (execution-trace visualization is novel substrate; WB-5 precedent ~1,000-1,500 LOC):

- WorkflowPreviewPane.tsx: ~400-700
- simulate-trace.ts: ~200-400
- WorkflowEditorPage.tsx layout extension: ~50-150 LOC
- Tests: ~250-450

**B-4 envelope: ~800-1,500 LOC.** Wide calibration band per Phase 4 §7.1 first-of-kind preview substrate for workflows.

#### §2.D.5 Test cohort shape

- `simulate-trace.test.ts` — pure-function tests covering linear / branching / parallel_split-join / decision / wait / iteration shape (`is_iteration=true` edges) (~15-25 tests)
- `WorkflowPreviewPane.test.tsx` — render with empty / single-node / multi-node / branching / parallel canvas-state; per-node simulated state assertions (~8-12 tests)
- `WorkflowEditorPage.test.tsx` extension — assert preview pane mounts in chosen layout; assert canvas-state mutations propagate to preview within render frame (~3-5 tests)

**B-4 test cohort: ~25-45 new tests.**

#### §2.D.6 Material-divergence triggers per Entry 23

- Preview pane layout shape decision (right rail vs overlay vs separate route) surfaces operator decision pivot at B-4 dispatch acknowledgement — surface for operator adjudication BEFORE B-4 build proceeds.
- `simulate-trace` execution-trace shape surfaces complexity beyond DFS-over-graph (e.g., conditional branching requires evaluating Jinja expressions in `edge.condition`; if so, scope-creep flag — Jinja evaluation at design-time would need frontend Jinja substrate, surface for scope adjustment).
- Per-node visualization surfaces per-node-type-specific shape requirements beyond simulated-state (e.g., `send-communication` preview should render the actual email template per D-7 template substrate; if so, scope-creep flag — preview integration with document/email substrate is post-Phase-B work).
- Preview substrate surfaces engine-invocation pressure (e.g., "preview should run real `workflow_engine.advance_run` against draft canvas-state"; STOP — engine out-of-scope per cross-sub-arc invariant; preview MUST stay frontend pure-function simulation).
- LOC envelope exceeds 1,500 by >20% per Entry 24.
- Material-divergence STOPs before commit; surface to operator per Entry 23 protocol verbatim.

#### §2.D.7 Acknowledgement format

B-4 sub-arc dispatch wrapper acknowledges per Entry 32 per-arc pre-dispatch rescoping. Acknowledgement reads:
- This Phase 5 build prompt §2.D
- Phase 0 audit §A + §E.5 observation #4
- Phase 4 phasing §3.1 + §3.3
- B-1 / B-2 / B-3 sub-arc commits at sub-arc-HEAD (canvas + registry + inspectors)
- `2026-05-23-widget-builder-canvas-preview.md` WB cycle preview substrate precedent (read for contrast: widget composition tree vs workflow execution trace)
- DECISIONS.md 2026-05-27 Entries 14 (always-visible preview substrate), 30 (substrate-similarity)
- Preview pane layout-shape decision pivot **explicit at acknowledgement** — operator confirms shape before B-4 dispatches.

Then verifies: substrate state at file:line precision; B-4 LOC envelope within band; cross-sub-arc invariants per §3 (especially engine-out-of-scope invariant); material-divergence triggers explicit per §2.D.6. Operator confirms before B-4 build sub-agent dispatches.

---

### §2.E — Sub-arc B-5 (Selection-driven inspector chrome)

#### §2.E.1 Bounded decision (Entry 31)

**Extend Surface 3 selection-context substrate to cover background-click + edge-click + workflow-level chrome editing alongside the existing node-click selection. Current `WorkflowEditorPage.tsx` carries node-click selection only (per Phase 0 audit §A.2 evidence: "Selection-driven inspector ✓ partial — NodeConfigForm at right rail; no background-click substrate editing"). B-5 ships:
- Background-click (empty canvas area) → workflow-level chrome inspector (trigger config, workflow metadata, canvas config — analogous to widget-level chrome at WB-4 + Focus Builder F-3.1b)
- Edge-click → edge-condition inspector (Jinja condition string + edge label + edge ID)
- Node-click → existing per-type inspector from B-3 (unchanged)
- Empty selection state → "Nothing selected" placeholder per Focus Builder selection-context precedent
B-5 closes when 4-state selection-context substrate operational (none / node / edge / background), per-selection chrome inspector renders, transitions between selection states preserve no-spurious-canvas-state-mutations invariant, vitest selection-context coverage green.**

#### §2.E.2 Substrate scope

**What changes:**
- **Selection-context refactor at `WorkflowEditorPage.tsx`** — current selection state (presumably `selectedNodeId: string | null` based on Phase 0 audit §A.2 evidence) extends to discriminated union: `{ kind: 'none' } | { kind: 'node', id: string } | { kind: 'edge', id: string } | { kind: 'background' }`. Pattern matches Focus Builder F-2 selection canon at `frontend/src/components/focus-builder/*` per `2026-05-18-focus-builder.md` deliverable.
- **NEW background-chrome inspector** `frontend/src/bridgeable-admin/components/visual-editor/workflow-canvas/WorkflowChromeInspector.tsx` (~150-250 LOC) — editing trigger config (trigger_type + trigger_config JSON), workflow-level metadata (display_name + description), canvas-config (existing `canvas_state` top-level fields beyond `nodes`/`edges`). Replaces or augments left-rail scope/metadata section at `WorkflowEditorPage.tsx:648-880` per operator-decision (current scope section may stay; new chrome inspector renders in right rail on background-click).
- **NEW edge-condition inspector** `frontend/src/bridgeable-admin/components/visual-editor/workflow-canvas/EdgeConditionInspector.tsx` (~100-200 LOC) — editing `edge.condition` (Jinja expression string), `edge.label`, `edge.id`. Pattern matches per-type inspector shape from B-3.
- **GraphCanvas.tsx click-handler extension from B-1** — emit selection-context mutations on background-click (canvas empty area) + edge-click; current node-click selection preserved.
- **NodeConfigForm.tsx dispatch extension from B-3** — selection-context discriminator switch: `selection.kind === 'node'` → existing per-type inspector dispatch; `selection.kind === 'edge'` → EdgeConditionInspector; `selection.kind === 'background'` → WorkflowChromeInspector; `selection.kind === 'none'` → empty-state placeholder.
- **Per-inspector vitest coverage** for new components.

**What stays unchanged:**
- B-2 registry (zero LOC).
- B-3 per-type inspector configs (consumed by selection-context dispatch; not modified).
- B-4 preview pane (selection-context extension doesn't affect preview rendering; preview consumes canvas-state directly).
- Backend service layer (zero LOC).
- WorkflowTemplate + TenantWorkflowFork schema (no migration).
- 9-endpoint admin platform router (zero LOC).
- Surface 1 + Surface 2 (per Adjudication 1).
- Auto-save debounce path (per Adjudication 2; chrome inspector + edge inspector edits flow through existing canvas-state mutation → auto-save path).

#### §2.E.3 Addresses Phase 0 audit §E observations (selection/palette pattern)

Phase 0 audit §E.5 observation #2 (palette substrate) closes at B-2; selection-substrate-pattern aspect of canonical-builder-rebuild closes at B-5. Per Phase 4 §3.3 substrate-similarity clusters: B-1 + B-5 form **canvas substrate + canvas-selection-context pair**. B-1 ships graph canvas; B-5 ships selection-context extension over the canvas.

#### §2.E.4 LOC envelope per Entry 24

Per Phase 4 §7.1 narrow calibration band (selection-state refactor; smaller substrate):

- Selection-context refactor at WorkflowEditorPage.tsx: ~80-150 LOC delta
- WorkflowChromeInspector.tsx: ~150-250
- EdgeConditionInspector.tsx: ~100-200
- GraphCanvas.tsx click-handler extension: ~30-60 LOC delta
- NodeConfigForm.tsx dispatch extension: ~30-60 LOC delta
- Tests: ~150-300

**B-5 envelope: ~500-1,000 LOC.** Narrow calibration band per Phase 4 §7.1.

#### §2.E.5 Test cohort shape

- `WorkflowEditorPage.test.tsx` selection-context extension — 4-state selection transitions; no-spurious-mutations invariant (~6-10 tests)
- `WorkflowChromeInspector.test.tsx` — trigger config edit; metadata edit; canvas-config edit (~5-8 tests)
- `EdgeConditionInspector.test.tsx` — Jinja condition edit; label edit (~3-5 tests)
- Playwright `workflow-selection-context.spec.ts` — operator-observable assertions: click background → chrome inspector renders; click edge → edge inspector; click node → per-type inspector (~2-4 specs)

**B-5 test cohort: ~15-30 new tests.**

#### §2.E.6 Material-divergence triggers per Entry 23

- Edge condition Jinja edit surfaces validation requirement (e.g., need server-side validation against Jinja substrate; if so, scope adjustment — server-side validation requires backend endpoint, may not be substrate-phase scope).
- Workflow-level chrome shape surfaces canvas-state schema requirement beyond existing `trigger` + `nodes` + `edges` + `version` fields (e.g., chrome edits land in new top-level field; canon-update arc trigger; STOP).
- Selection-context discriminated-union shape surfaces React state-management complexity (e.g., useReducer needed; surface for shape adjustment if simpler shape sufficient).
- B-5 work surfaces requirement for B-3 inspector dispatch refactor beyond locked scope (e.g., per-type configs need selection-context awareness; if so, surface seam misalignment per Entry 30).
- LOC envelope exceeds 1,000 by >20% per Entry 24.
- Material-divergence STOPs before commit; surface to operator per Entry 23 protocol verbatim.

#### §2.E.7 Acknowledgement format

B-5 sub-arc dispatch wrapper acknowledges per Entry 32 per-arc pre-dispatch rescoping. Acknowledgement reads:
- This Phase 5 build prompt §2.E
- Phase 0 audit §A + §E.5 (selection/palette pattern)
- Phase 4 phasing §3.1 + §3.3 (B-1/B-5 canvas + selection-context pair)
- B-1 / B-2 / B-3 / B-4 sub-arc commits at sub-arc-HEAD
- Focus Builder F-2 selection canon at `2026-05-18-focus-builder.md`
- DECISIONS.md 2026-05-27 Entries 30 (substrate-similarity), 31 (bounded-decision)

Then verifies: substrate state at file:line precision; B-5 LOC envelope within band; cross-sub-arc invariants per §3; material-divergence triggers explicit per §2.E.6. Operator confirms before B-5 build sub-agent dispatches.

---

## §3. Cross-sub-arc invariants

Phase B substrate phase maintains these 9 invariants across all 5 sub-arcs:

1. **WorkflowTemplate + TenantWorkflowFork schema unchanged across Phase B substrate phase.** Migration `r82_workflow_templates` operational; no Phase B migration. Per Phase 0 audit §C.4 + Adjudication invariant. Verified at each sub-arc commit via migration-head-unchanged check (migration head stays at r109 per v1 task substrate B3 close).

2. **`workflow_engine.py` substrate out-of-scope across all 5 sub-arcs.** Per Phase 0 audit §D + Edit 7 realm-agnostic-service-layer canon. The 17-value runtime action_type dispatch at `workflow_engine.py:635-693` stays unchanged. The 28-value authoring vocabulary at `canvas_validator.py:62-105` stays unchanged. Vocabulary asymmetry architecturally canonical per Edit 7; not addressed at Phase B.

3. **Service-layer canonical substrate (`workflow_templates/*`) accessed via existing platform-realm endpoints.** Per Phase 0 audit §B + Studio-builder Mapping Table Edit 9. Zero backend LOC across Phase B substrate phase. 9-endpoint admin platform router at `visual_editor_workflows.py:203-369` unchanged. `template_service.py:650 LOC` + `canvas_validator.py:260 LOC` unchanged.

4. **28-value `VALID_NODE_TYPES` authoring vocabulary preserved.** Per Phase 0 audit §C.3 + cross-mirror discipline (backend `canvas_validator.py:62-105` + frontend `lib/visual-editor/workflows/canvas-validator.ts:244 LOC`). B-2 expands registry coverage to match canonical vocabulary; does NOT extend vocabulary. Any vocabulary change is canon-update arc trigger per Entry 1.

5. **Surface 1 (`pages/settings/WorkflowBuilder.tsx:1,876 LOC`) + Surface 2 (`pages/settings/Workflows.tsx:494 LOC`) untouched at Phase B.** Per Adjudication 1; legacy step-list paradigm preserved; disposition deferred post-Phase-B. Each sub-arc commit verifies zero Surface 1/2 LOC delta.

6. **Auto-save with locked-to-fork merge semantics preserved.** Per Adjudication 2; current 1.5s debounce at `WorkflowEditorPage.tsx:354-372` unchanged. Sub-arcs may extend canvas-state mutation flow (e.g., B-1 GraphCanvas position mutations; B-5 selection-context background/edge mutations) but auto-save path stays. Each sub-arc commit verifies debounce + locked-to-fork merge invariants.

7. **7 cross-arc boundaries preserved across all 5 sub-arcs:**
   - Phase C Document Builder rebuild per Entry 32 own pre-dispatch rescoping
   - Q-B1 boot-adapter shape per Entry 3 deferral-tracking (September-decision arc)
   - Task substrate v1 producer-only at `create_task` action_type per `workflow_engine.py:1173-1241`
   - Visual Editor §4 canonical structure per CLAUDE.md
   - Edit 7 realm-agnostic service layer
   - Edit 9 Studio-builder Mapping Table inherited verbatim
   - Entry 22 discoverability canon rail-entry operational at `StudioShell.tsx:70`

8. **114 stale Playwright screenshot/video deletions stay UNTOUCHED throughout Phase B substrate phase.** Pre-existing working tree state at HEAD `fe58e3c` (114 deletions documented in `git status`). No sub-arc touches these.

9. **STATE.md updates land per sub-arc commit** per Phase 4 §6.2 narrative discipline. Phase B substrate phase close note appends at B-5 final commit (full substrate phase shipped; Surface 3 at canonical builder-rebuild shape; Phase 0 audit §E 8 wrong-shape observations addressed; 7 cross-arc boundaries preserved; B-6 / B-7 / B-8 integration-phase sub-arcs defer per Phase 4 §2.1 + §5.2 signal-driven dispatch; September Wilbert demo schedule explicitly NOT a signal).

---

## §4. 4-decision matrices (per sub-arc)

Per v2a+v2c Phase 5 precedent at `task_substrate_v2a_v2c_v1_build_prompt.md`: per-sub-arc 4-decision matrix locks build-execution dispatch shape.

### §4.A — B-1 4-decision matrix

| Decision | Lock |
|---|---|
| Substrate addition vs extension vs in-place modification | **Addition** (new GraphCanvas.tsx + canvas-layout.ts files) + **in-place modification** (WorkflowEditorPage.tsx canvas-section refactor at lines 924-1004) |
| Test cohort shape | **Functional + unit** (no parity tests — no pre-existing graph canvas to parity against; integration tests cover canvas-state roundtrip; Playwright optional per Q-40 dnd-kit limitation) |
| Migration shape | **None** (no schema changes per §3 invariant 1) |
| Sub-arc commit shape | **Single commit at arc close** per Entry 26 default regime (LOC envelope ≤2,500); **2-commit-within-arc-identity** acceptable if audit-first phase surfaces canvas-substrate / WorkflowEditorPage-integration seam |

### §4.B — B-2 4-decision matrix

| Decision | Lock |
|---|---|
| Substrate addition vs extension vs in-place modification | **Extension** (workflow-nodes.ts expands 2→28 entries) + **in-place modification** (WorkflowEditorPage.tsx palette refactor at lines 884-905) |
| Test cohort shape | **Functional + backfill validation** (registry-coverage assertions per Phase 3 Component Configuration backfill validation precedent; per-registration prop schema validation) |
| Migration shape | **None** |
| Sub-arc commit shape | **Single commit at arc close** per Entry 26 default regime (LOC envelope ≤1,500) |

### §4.C — B-3 4-decision matrix

| Decision | Lock |
|---|---|
| Substrate addition vs extension vs in-place modification | **Addition** (14-26 new per-type inspector config components) + **in-place modification** (NodeConfigForm.tsx dispatch table extension at lines 1019-1028) |
| Test cohort shape | **Functional + unit** (per-inspector unit tests; NodeConfigForm dispatch coverage; Playwright operator-observable assertion of dispatch shape) |
| Migration shape | **None** |
| Sub-arc commit shape | **Single commit at arc close** per Entry 26 default regime (LOC envelope ≤2,500); **multi-commit-within-arc-identity** earnable if substrate work surfaces parity-discipline complexity (e.g., grouped vs dedicated inspector decomposition surfaces multi-commit seams during audit-first phase) |

### §4.D — B-4 4-decision matrix

| Decision | Lock |
|---|---|
| Substrate addition vs extension vs in-place modification | **Addition** (new WorkflowPreviewPane.tsx + simulate-trace.ts files) + **in-place modification** (WorkflowEditorPage.tsx layout extension for preview pane mount) |
| Test cohort shape | **Functional + unit** (pure-function simulate-trace unit coverage; preview pane integration tests) |
| Migration shape | **None** |
| Sub-arc commit shape | **Single commit at arc close** per Entry 26 default regime (LOC envelope ≤1,500) |

### §4.E — B-5 4-decision matrix

| Decision | Lock |
|---|---|
| Substrate addition vs extension vs in-place modification | **Addition** (new WorkflowChromeInspector.tsx + EdgeConditionInspector.tsx) + **in-place modification** (WorkflowEditorPage.tsx selection-context refactor + GraphCanvas.tsx click-handler extension + NodeConfigForm.tsx dispatch extension) |
| Test cohort shape | **Functional + unit** (selection-context coverage; per-inspector unit; Playwright selection-shape operator-observable) |
| Migration shape | **None** |
| Sub-arc commit shape | **Single commit at arc close** per Entry 26 default regime (LOC envelope ≤1,000) |

---

## §5. Audit-shape signals + material-divergence triggers per Entry 23

Per Entry 23 iterative-STOP protocol + Phase B investigation canon-validation evidence (0 material-divergence triggers fired across single iteration; cheap-recovery shape preserved):

**Verbatim protocol per Entry 23:**

- If build agent surfaces material that the build prompt is wrong about during execution: **STOP immediately**.
- Surface to operator with explicit rationale (what was the substrate state expected per Phase 0 audit §A-§G citations; what was found at sub-arc-HEAD; what's the divergence shape; what's the proposed revised lock).
- Await locked revision from operator.
- Proceed against revised lock only.
- Reference: Lock A revision pattern from v1 task substrate B1 commit `2fba161` + v2a+v2c v1 build prompt §2.A.3 revision is canonical example.

### §5.1 Per-sub-arc material-divergence triggers (consolidated from §2.X.6)

**B-1 (Graph canvas foundation) triggers:**
- Graph-rendering complexity beyond SVG-path-between-nodes (e.g., requires dagre or elkjs package; scope adjustment).
- `position: {x, y}` field insufficient for graph layout (canvas-state schema extension; canon-update arc trigger).
- Palette types lack `position` defaults causing positionless nodes (B-2 dependency; scope-creep flag).
- Auto-save debounce flow doesn't cleanly accept canvas-state mutations from GraphCanvas (API shape re-shape).
- LOC envelope exceeds 2,500 by >20%.
- dnd-kit JSDOM testability gap beyond Q-40 canon (defer Playwright; flag for staging verification).

**B-2 (Node-type registry expansion) triggers:**
- VALID_NODE_TYPES count diverges from 28 at sub-arc HEAD.
- ≥3 configurableProps requirement surfaces canonical-vocabulary ambiguity (e.g., `start`/`end` lifecycle markers carry no meaningful props beyond `label`; operator adjudication).
- Category taxonomy ambiguity (e.g., `schedule` ∈ `trigger` vs `lifecycle`).
- Token consumption surfaces gaps (canon-update arc trigger).
- LOC envelope exceeds 1,500 by >20%.
- B-2 work surfaces canvas-state schema extension requirement (canon-update arc trigger).

**B-3 (Per-type inspector configs) triggers:**
- B-2 registry expansion configurableProps shape ambiguity discovered at B-3 dispatch time.
- Per-type inspector renders surface canvas-state schema gap (e.g., `cross_tenant_order` needs additional canvas-state field; canon-update arc trigger).
- Grouped vs dedicated inspector decomposition seam misalignment.
- LOC envelope exceeds 2,500 by >20%.
- B-3 work surfaces requirement for plugin-shaped contract (per Phase 4 §6.4 workflow node inspector configs canonical contract; canon-update arc trigger).

**B-4 (Always-visible preview substrate) triggers:**
- Preview pane layout shape decision (right rail vs overlay vs separate route) — operator decision pivot at dispatch acknowledgement.
- simulate-trace shape requires Jinja expression evaluation in `edge.condition` (frontend Jinja substrate; scope-creep flag).
- Per-node visualization requires per-node-type-specific shape (e.g., send-communication preview should render email template via D-7 substrate; scope-creep flag — preview integration with document/email substrate is post-Phase-B work).
- Preview substrate engine-invocation pressure ("preview should run real `workflow_engine.advance_run`"; STOP per §3 invariant 2).
- LOC envelope exceeds 1,500 by >20%.

**B-5 (Selection-driven inspector chrome) triggers:**
- Edge condition Jinja edit surfaces server-side validation requirement (scope adjustment).
- Workflow-level chrome shape surfaces canvas-state schema requirement beyond existing trigger/nodes/edges/version (canon-update arc trigger).
- Selection-context discriminated-union React state-management complexity (useReducer needed; shape adjustment).
- B-5 work surfaces requirement for B-3 inspector dispatch refactor beyond locked scope (seam misalignment per Entry 30).
- LOC envelope exceeds 1,000 by >20%.

### §5.2 General Phase B substrate phase triggers

- Phase B work surfaces v1 task substrate concerns (canon-discipline question; v1 operational + canon-filed at canon-update arc close; should not revisit).
- Any locked discipline would be violated.
- Phase B scope expansion surfaces (B-6 / B-7 / B-8 dispatching during substrate phase rather than after; STOP — integration phase is signal-driven per Phase 4 §5.2).
- Phase C Document Builder rebuild scope surfaces (explicitly out-of-scope per Entry 32; STOP).
- Q-B1 boot-adapter shape surfaces (September-decision arc; STOP).
- v2a / v2b / v2c task substrate scope surfaces (explicitly out-of-scope; STOP).
- September Wilbert demo schedule surfaces as scoping pressure (explicitly NOT a signal per Entry 2 anti-signal canon; STOP).
- Substrate-mature-signal-for-downstream rejected per Phase 4 §5.4 (B-1/B-2/B-3/B-4/B-5 close does NOT auto-trigger Phase C dispatch; STOP).
- 4-state substrate framing canon-update arc dispatch trigger during Phase B substrate phase (defers post-Phase-B per Audit-item 1; STOP).

### §5.3 Investigation altitudes per Entry 23 iterative-STOP protocol

- **Acknowledgement-altitude verification:** per-sub-arc dispatch wrapper acknowledgement surfaces material-divergence at the gate BEFORE build sub-agent dispatches.
- **Investigation-altitude verification:** per-arc pre-dispatch rescoping per Entry 32; each sub-arc faces own verification at sub-arc dispatch time against then-current HEAD.
- **Execution-altitude verification:** build-execution verification against locked sub-arc scope per Entry 23 STOP protocol verbatim during build.

If any trigger fires at any altitude during build, STOP before committing the affected sub-arc; surface to operator; do NOT proceed past trigger point.

---

## §6. Honest cost per Entry 24

### §6.1 Per-sub-arc LOC envelope

Per Phase 4 §7.1 honest-cost discipline + per-sub-arc decomposition at §3.1:

| Sub-arc | Envelope | Calibration band |
|---------|----------|------------------|
| B-1 Graph canvas foundation | ~1,500-2,500 LOC | **Wide** — first-of-kind canvas model (DAG distinct from Monitor grid + Decide free-form); WB-4 precedent canvas sub-arc widest variance |
| B-2 Node-type registry expansion 2→28 | ~800-1,500 LOC | **Narrow** — mechanical substrate-cohort scaffolding; ~26 entries × ~30-60 LOC/entry per Component Registry canon |
| B-3 Per-type inspector configs 14-26 new | ~1,500-2,500 LOC | **Narrow** — ~14-26 inspector components × ~100-200 LOC each per InvokeGenerationFocusConfig.tsx precedent |
| B-4 Always-visible preview substrate | ~800-1,500 LOC | **Wide** — execution-trace visualization is novel substrate; WB-5 precedent ~1,000-1,500 |
| B-5 Selection-driven inspector chrome | ~500-1,000 LOC | **Narrow** — selection-context refactor; smaller substrate |

**Substrate phase cumulative:** ~5,100-9,000 LOC.

### §6.2 Phase B cumulative LOC envelope (substrate phase only)

- **Substrate phase only:** ~5,100-9,000 LOC
- Above 25k cumulative ceiling: not approached; well under
- Integration phase (B-6 / B-7 / B-8) signal-driven; cumulative envelope ~1,500-5,400 LOC IF integration phase dispatches; not part of Phase B substrate phase honest-cost

### §6.3 Test cohort accumulation per sub-arc

| Sub-arc | Test cohort |
|---------|-------------|
| B-1 | ~25-40 new tests |
| B-2 | ~15-25 new tests |
| B-3 | ~60-150 new tests (per-inspector independence) |
| B-4 | ~25-45 new tests |
| B-5 | ~15-30 new tests |

**Phase B substrate phase cumulative test cohort:** ~140-290 new tests.

### §6.4 Cross-version concerns

- Phase A close baseline at `ca2c7db` (task substrate v1 complete).
- Phase B investigation close at `fe58e3c` (2 investigation deliverables landed; canon at `cce834d` state).
- Phase B substrate phase ships at multiple commits (B-1 through B-5; ~5 commits per Entry 26 default regime).
- Canon at `cce834d` preserved across Phase B substrate phase (no canon edits during substrate phase per §3 invariant; canon-update arc dispatches post-Phase-B per Phase 4 §6.1).
- Migration head stays at r109 across Phase B substrate phase (no schema migration per §3 invariant 1).
- STATE.md narrative across sub-arcs per WB cycle precedent (per-sub-arc append).
- Phase C boundary preserved (per Entry 32 own pre-dispatch rescoping).
- Q-B1 carries forward to September-decision arc (per Entry 3 deferral-tracking).

### §6.5 Calibration band against WB cycle + Focus Builder rebuild precedents

Per Phase 4 §7.5 cross-arc LOC pattern + Entry 24 four-instance calibration band (WB-6 3.3× → WB-5 0.5% → WB-7 18% → WB-8 ±5%):

Phase B inherits **substrate-mature calibration band** because Workflow Builder rebuild operates against well-understood canonical builder-rebuild substrate. Expected calibration variance: **closer to WB-8 ±5% than WB-6 3.3×** — schema is in place (per Phase 0 audit §C); substrate boundaries are clean (per Phase 0 audit §B-§D); rebuild operates against canonical patterns (Focus Builder + Widget Builder rebuild precedent).

Calibration anchor between Focus Builder (5 sub-arcs ~6,500-9,500 LOC; ships shipped 2026-05-18 onwards) and WB cycle (8 substrate sub-arcs ~9,500-14,000 LOC; ships shipped 2026-05-21 onwards). Phase B substrate phase fits more cleanly under Focus Builder anchor because schema substrate is in place (no schema migration LOC; no service-layer foundation LOC; rebuild is authoring-surface focused).

### §6.6 Cross-version test cohort calibration

Per WB cycle test cohort precedent: each sub-arc ships ~5-20 unit/integration/Playwright tests. Phase B substrate phase cumulative test cohort: ~140-290 new tests (B-3 disproportionately large because per-inspector independence). Within Entry 24 calibration band given B-3's distinctive per-inspector cohort shape.

---

## Phase 5 closing

Phase 5 build prompt drafting closes. Deliverable shipped at `docs/investigations/workflow_builder_rebuild_build_prompt.md` per 6-section canonical structure inherited from v2a+v2c Phase 5 precedent. Per Entry 31 bounded-decision-per-arc explicit naming: Phase 5 bounded decision = "produce Phase B build prompt deliverable locking per-sub-arc execution context across the 5 substrate-phase sub-arc identities (B-1 → B-5); surface cross-sub-arc invariants; surface material-divergence protocol; surface acknowledgement format; lock NO production code; lock NO canon edits; lock NO STATE.md edits; lock NO build dispatch" — bounded decision satisfied.

**Next-gate handoff:** operator reviews Phase 5 deliverable; confirms per-sub-arc execution context + cross-sub-arc invariants + 4-decision matrices + material-divergence triggers + honest-cost calibration; B-1 build sub-agent dispatches against locked sub-arc scope in fresh session per Entry 32 per-arc pre-dispatch rescoping.

**No material-divergence triggers fired during Phase 5 drafting.** No canon edits. No STATE.md edits. No production code. No build dispatch. No v2a/v2b/v2c task substrate scope. No Phase C scope-lock. No Q-B1 substrate decision. No v1 substrate revisiting. No engine substrate work. No Surface 1 disposition work. No B-8 trigger-variant work.

**5 4-decision matrices locked** across 5 sub-arc identities: 1 (B-1) + 1 (B-2) + 1 (B-3) + 1 (B-4) + 1 (B-5) = 5.

**5 sub-arc execution contexts locked** per Adjudication 4 (Phase 4 phasing §3.1 substrate-similarity clusters per Entry 30):
- B-1 Graph canvas foundation (~1,500-2,500 LOC)
- B-2 Node-type registry expansion 2→28 (~800-1,500 LOC)
- B-3 Per-type inspector configs 14-26 new (~1,500-2,500 LOC)
- B-4 Always-visible preview substrate (~800-1,500 LOC)
- B-5 Selection-driven inspector chrome (~500-1,000 LOC)

**Phase B substrate phase cumulative:** ~5,100-9,000 LOC; ~140-290 new tests; ~5 sub-arc commits per Entry 26 default regime.

**9 cross-sub-arc invariants locked** per §3.

**Cross-arc boundaries preserved:** Phase C / Q-B1 / task substrate / Visual Editor §4 / Edit 7 / Studio-builder Mapping Table / discoverability canon / 114 stale screenshot deletions / canon at `cce834d` state.

**Anti-signal discipline preserved per Entry 2:** September Wilbert demo schedule explicitly NOT a signal; engineering preference rejected; aesthetic-completeness rejected; sunk-cost rejected; substrate-mature-signal-for-downstream rejected.

**Word count:** ~8,500 words (within ~7,000-10,000 envelope; ≥12,000 over-synthesis signal not fired).

**Lineage reference:** `cce834d` (canon-update arc close) → `ca2c7db` (Phase A close) → `fe58e3c` (Phase B investigation close) → THIS (Phase 5 build prompt drafted; B-1 build sub-arc dispatch downstream of operator confirmation).
