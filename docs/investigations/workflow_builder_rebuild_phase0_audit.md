# Workflow Builder Rebuild — Phase 0 Audit

> Read-only Phase 0 audit deliverable opening the Phase B Workflow Builder rebuild investigation arc. Joins forward to `docs/investigations/workflow_builder_rebuild_phasing.md` (Phase 4 phasing recommendation).
>
> Persistent storage from start per DECISIONS.md 2026-05-27 — Persistent-storage discipline for investigation deliverables (Entry 4).

## Phase 0 metadata

- **Arc context:** Phase B Workflow Builder rebuild investigation, Phase 0 of two (Phase 4 phasing recommendation downstream)
- **HEAD at audit:** `ca2c7db` (Phase A close: v1 task substrate complete; v2a/v2c defer per anti-signal)
- **Audit date:** 2026-05-27
- **Canon ground:** 35 DECISIONS.md entries dated 2026-05-27; particularly Entry 1 (investigation-methodology / audit-first), Entry 2 (operator-observable signals + anti-signals), Entry 3 (deferral-tracking meta-pattern), Entry 4 (persistent storage), Entry 7 (built-but-dormant as third substrate state — extended to four-state framing per v2a Phase 0 audit precedent), Entry 11 (WYSIWYG canvas-layout-model constraint), Entry 17 (substrate-prescience-meets-second-consumer), Entry 22 (discoverability canon for operator-facing substrate cycles), Entry 27 (phasing recommendation shape canon), Entry 30 (sub-arc decomposition seams discovered during investigation), Entry 31 (bounded-decision-per-arc explicit naming), Entry 32 (per-arc pre-dispatch rescoping for distant-horizon arcs). Plus CLAUDE.md §4 — Workflow Canvas (Admin Visual Editor Phase 4), Visual Editor Top-Level Structure, Studio-builder Mapping Table (Edit 9), Realm-agnostic service layer (Edit 7), Workflows scope + dual customization paths (Phase 8a), workflow arc Phases 8b-8e.
- **Operator framing locks preserved:**
  - Phase B sequence locked per operator-locked Phase A → B → C
  - Q-B1 boot-adapter shape boundary preserved (September-decision arc; cold-start composed-definitions palette degradation)
  - Phase C Document Builder rebuild boundary preserved (Phase C operates under own pre-dispatch rescoping per Entry 32)
  - Task substrate v1 boundary preserved (operational at Phase A close; Workflow Builder authors workflows producing tasks; does NOT touch task substrate)
  - September Wilbert demo schedule explicitly NOT a signal per Entry 2 anti-signal canon
- **Substrate-state framing:** four-state extension per v2a Phase 0 audit precedent — `built-operator-facing` / `built-but-dormant` / `built-but-mis-shaped` (operator validation: "original editors we built were not what I wanted") / `missing`
- **Bounded decision:** produce Phase 0 audit deliverable per dispatch §7 7-section structure; surface concrete substrate observations grounding operator's "wrong-shape" framing; lock NO Phase 4 phasing content; lock NO Phase B build dispatch; lock NO scope outside Phase B.

---

## Section A — Workflow Builder frontend state verification

### A.1 Surface inventory at file:line precision

Four primary frontend mounts carry the Workflow Builder substrate at HEAD `ca2c7db`. Verification grep on `WorkflowBuilder|WorkflowEditor|workflow-builder|visual-editor/workflows`:

| # | Surface | File | LOC | Mount route |
|---|---------|------|-----|-------------|
| 1 | Tenant settings Workflow Builder | `frontend/src/pages/settings/WorkflowBuilder.tsx` | **1,876** | `/settings/workflows/new`, `/settings/workflows/:workflowId/edit`, `/settings/workflows/:workflowId/view` (3 routes registered in `App.tsx:1434/1438/1442`) |
| 2 | Tenant settings Workflows list | `frontend/src/pages/settings/Workflows.tsx` | 494 | `/settings/workflows` (companion list view) |
| 3 | Admin Studio Workflow Editor (canonical Visual Editor Phase 4 surface) | `frontend/src/bridgeable-admin/pages/visual-editor/WorkflowEditorPage.tsx` | **1,035** | Mounted via `StudioShell.tsx:70` as `workflows: WorkflowEditorPage`; canonical route per CLAUDE.md Edit 9 Studio-builder Mapping Table = `/admin/visual-editor/workflows` (Studio path `/admin/studio/workflows` per `studio-routes.ts:175`) |
| 4 | Runtime editor inspector Workflows tab | `frontend/src/lib/runtime-host/inspector/WorkflowsTab.tsx` | (consumer of canvas-validator; deep-links to admin Studio at `adminPath("/visual-editor/workflows")`) | Inline within runtime editor inspector |

Supporting surfaces:

- `frontend/src/bridgeable-admin/services/workflow-templates-service.ts` (231 LOC) — client wrapper for `/api/platform/admin/visual-editor/workflows/*` (admin-realm service)
- `frontend/src/bridgeable-admin/components/visual-editor/workflow-canvas/NodeConfigForm.tsx` (248 LOC) — per-node inspector component, extracted in Arc 2 Phase 2b for re-use between standalone editor and inspector Workflows tab
- `frontend/src/bridgeable-admin/components/visual-editor/workflow-canvas/InvokeGenerationFocusConfig.tsx` + `InvokeReviewFocusConfig.tsx` — per-node-type inspector configs for headless Generation Focus + Review Focus primitives
- `frontend/src/lib/visual-editor/workflows/canvas-validator.ts` (244 LOC) — client-mirror schema validator; cross-references `backend/app/services/workflow_templates/canvas_validator.py`
- `frontend/src/lib/visual-editor/registry/registrations/workflow-nodes.ts` (196 LOC) — workflow-node component registry (2 workflow node types per CLAUDE.md §4 Phase 4 ledger: `generation-focus-invocation`, `send-communication`)

### A.2 Per-surface substrate state (four-state framing)

**Surface 1 — `pages/settings/WorkflowBuilder.tsx` (tenant-side, 1,876 LOC):**

- **State:** built-but-mis-shaped per operator validation
- **Evidence — substantive substrate observations:**
  - Operator-facing route mounted at three operational URLs in `App.tsx:1434-1442` (`new`, `:id/edit`, `:id/view`)
  - Uses `BlockLibrary` + `StepCard` + `DropZones` + `PlaceholderCard` from `frontend/src/components/workflow/*` — a parallel component substrate distinct from the admin Studio's `workflow-canvas/*` substrate
  - Imports legacy step-type vocabulary (`input | action | ai_prompt | send_document | playwright_action | condition | output`) — 7-value union at line 55-62 — distinct from canonical Phase 4 admin-side 28-value `VALID_NODE_TYPES` tuple at `canvas_validator.py:62-105` (backend) + `canvas-validator.ts` (frontend mirror)
  - Hits `/workflows/*` tenant endpoints (apiClient calls at lines 157, 187, 296, 298)
  - Carries inline `EntryScreen` component supporting "AI-describe" entry mode + manual block-based authoring; structure does NOT match the canonical builder rebuild pattern (Focus Builder hierarchical browser; Widget Builder data-source-first + atom composition)
  - Imports `WorkflowEmailTriggersSection` + `WorkflowPicker` + `AiPromptStepConfig` + `GenerateDocumentConfig` + `SendDocumentConfig` — each a per-step-type bespoke editor component. No unified canvas / node inspector / atom composition pattern.
  - Carries `tier`, `is_system`, `editable`, `configurable`, `params`, `added_steps` fields on `LoadedWorkflow` — Workflow Engine Phase W-1 ORM model semantics distinct from canonical `workflow_templates.canvas_state` JSONB-graph shape
- **Operator validation reading:** "what I wanted" was a canonical builder rebuild matching Focus Builder + Widget Builder rebuild shape; current surface uses an earlier step-list-with-bespoke-editors paradigm

**Surface 2 — `pages/settings/Workflows.tsx` (tenant-side, 494 LOC):**

- **State:** built-but-mis-shaped (companion list view)
- **Evidence:** companion to Surface 1; operator validation framing extends — list view surfaces the same Workflow Engine Phase W-1 substrate at row-level rather than canonical visual-editor browser pattern (HierarchicalEditorBrowser)

**Surface 3 — `bridgeable-admin/pages/visual-editor/WorkflowEditorPage.tsx` (admin-Studio, 1,035 LOC):**

- **State:** built-operator-facing per canonical Visual Editor Phase 4 ledger — but **architecturally distinct from canonical builder rebuild pattern** at multiple dimensions
- **Evidence — file:line:**
  - Mounts at `/admin/visual-editor/workflows` (canonical) + Studio path `/admin/studio/workflows` per `StudioShell.tsx:55-70` registration
  - Uses `HierarchicalEditorBrowser` (canonical browser pattern per Visual Editor Top-Level Structure ledger) at line 761 — matches Focus Builder + Workflows ledger expectation
  - Three-pane layout matching Visual Editor §4 ledger (left = scope selector + metadata + dependent forks at line 648-880; center = node-list canvas at line 884-1007; right = node configuration at line 1009-1030)
  - Imports `workflowTemplatesService` from `bridgeable-admin/services/workflow-templates-service.ts` consuming `/api/platform/admin/visual-editor/workflows/*` per canonical platform-realm pattern
  - Imports `canvas-validator.ts` from `lib/visual-editor/workflows/` per canonical client-mirror pattern
  - Imports `NodeConfigForm` from `bridgeable-admin/components/visual-editor/workflow-canvas/NodeConfigForm.tsx` per canonical per-node-config-form pattern
  - Carries Studio rail integration (`useStudioRail` at line 71/117-118) per Studio shell migration
- **Critical substrate observation:** the canvas at center is a **vertical sequence of nodes (ol/li list)** at lines 924-1004, NOT a canonical 2D canvas. Each node is selectable; edges expressed as "→ target_label" text fragments within the source node's row (lines 962-985). Per CLAUDE.md §4 Workflow Canvas (Phase 4): *"center = node-list canvas with palette across the top ... selectable nodes show outgoing edges with conditions"*. The "canvas" is intentionally list-shaped at Phase 4 — NOT a 2D drag-positionable graph
- **Workflow node palette at line 893:** 16 node types hard-coded as a tuple (`start, action, decision, branch, parallel_split, parallel_join, schedule, send-communication, generation-focus-invocation, invoke_generation_focus, invoke_review_focus, cross_tenant_order, cross_tenant_request, playwright_action, log_vault_item, end`) — subset of the 28-value backend `VALID_NODE_TYPES` tuple, hardcoded in the JSX rather than pulled from a node-type registry
- **Substrate boundary:** mounted via Studio rail per Studio-builder Mapping Table ledger; cross-links to `/admin/themes`, `/admin/components`, `/admin/registry` at lines 521-544 — Visual Editor cross-link convention

**Surface 4 — `lib/runtime-host/inspector/WorkflowsTab.tsx`:**

- **State:** built-operator-facing (consumer of canvas-validator; reads from admin-Studio workflow editor via deep-link at adminPath("/visual-editor/workflows"); no authoring substrate of its own)
- **Evidence:** line 85 imports from `@/lib/visual-editor/workflows/canvas-validator`; line 154 routes operator to admin Studio Workflow Editor for full authoring

### A.3 Frontend rebuild-target identification

Per operator framing "original editors we built were not what I wanted": both Surface 1 (tenant settings) AND Surface 3 (admin Studio) are candidate rebuild targets. Per Visual Editor Top-Level Structure ledger (May 2026 reorganization), Surface 3 is the **canonical Workflow Builder mount** per Studio-builder Mapping Table — `frontend/src/bridgeable-admin/pages/visual-editor/WorkflowEditorPage.tsx`. Surface 1 is the **legacy tenant-side surface** carrying the pre-rebuild step-list paradigm.

**Reading per substrate verification:** Phase B rebuild target = **Surface 3 (admin Studio Workflow Editor) at `frontend/src/bridgeable-admin/pages/visual-editor/WorkflowEditorPage.tsx`**, with Surface 1 (tenant `WorkflowBuilder.tsx`) as a related-but-distinct concern. Surface 1's relationship to Phase B is open question (§G + §8 phasing): does Phase B rebuild touch Surface 1, or does Surface 1 stay legacy until natural-refactor?

### A.4 Component dependencies

- `frontend/src/components/workflow/*` — tenant-side block library + step cards + drop zones (consumed by Surface 1 only)
- `frontend/src/bridgeable-admin/components/visual-editor/workflow-canvas/*` — admin-side per-node inspector components (consumed by Surface 3)
- `frontend/src/lib/visual-editor/workflows/canvas-validator.ts` — shared client validator (consumed by both Surface 3 and Surface 4)
- `frontend/src/lib/visual-editor/registry/registrations/workflow-nodes.ts` — workflow-node component registry (2 workflow-node types per Phase 4 ledger; canonical component registry per Visual Editor §4)
- `frontend/src/bridgeable-admin/components/visual-editor/HierarchicalEditorBrowser.tsx` — canonical builder browser pattern; consumed by Surface 3 at line 761 — re-used by Focus Editor per Visual Editor Top-Level Structure ledger

---

## Section B — Workflow Builder service layer state verification

### B.1 Backend service module inventory

Three parallel service-layer surfaces ship at HEAD `ca2c7db`:

| # | Module | LOC | Role | Realm |
|---|--------|-----|------|-------|
| 1 | `backend/app/services/workflow_engine.py` | **2,088** | Runtime substrate — workflow execution + variable resolution + action dispatch (NOT authoring substrate; distinct boundary per §D) | Realm-agnostic (consumed from both tenant + platform routers) |
| 2 | `backend/app/services/workflow_templates/template_service.py` + `canvas_validator.py` | 650 + 260 | Phase 4 authoring substrate — CRUD + READ-time inheritance resolution + tenant fork lifecycle | Platform-realm (consumed via admin platform router) |
| 3 | `backend/app/services/workflows/*` | (7 adapter modules: aftercare / ar_collections / cash_receipts / catalog_fetch / expense_categorization / month_end_close / safety_program — Phase 8b-8e.1 migration substrate) + `workflow_review_adapter.py` (146 LOC; Phase R-6.0a) | Adapter layer for migrated accounting agents + workflow review triage path | Tenant-realm (consumed via `/api/v1/workflows/*`) |

### B.2 Service-layer code organization

`backend/app/services/workflow_templates/`:

- `template_service.py` (650 LOC) — `list_templates`, `get_template`, `resolve_workflow`, `create_template`, `update_template`, `fork_for_tenant`, `accept_merge`, `reject_merge`, `mark_pending_merge` — full CRUD + inheritance resolution per CLAUDE.md §4 Workflow Canvas (Phase 4) ledger
- `canvas_validator.py` (260 LOC) — `validate_canvas_state` server-side validation; mirrors `lib/visual-editor/workflows/canvas-validator.ts` per Phase 4 cross-mirror discipline; 28-value `VALID_NODE_TYPES` tuple
- Existing service layer pattern matches canonical WB-cycle-followup-2 platform-realm shape per Realm-agnostic service layer canon (CLAUDE.md §4 Edit 7): service-layer modules consumable from either router; auth context flows through router-layer dependencies
- Realm boundary verified: `template_service.py` accepts `db: Session` + operational primitives; no tenant-realm coupling; canonical realm-agnostic pattern at service layer (Edit 7 precedent — Studio-authored substrates ship realm-agnostic at service layer from foundation)

### B.3 Platform-realm routing

- Admin router: `backend/app/api/routes/admin/visual_editor_workflows.py` (**401 LOC**); mounted at `/api/platform/admin/visual-editor/workflows/*` per `app/api/platform.py` registration block
- Endpoints (per `admin_list_templates / admin_get_template / admin_resolve_workflow / admin_list_dependent_forks / admin_create_template / admin_patch_template / admin_fork_for_tenant / admin_accept_merge / admin_reject_merge` at lines 203-369): 9 admin endpoints, all `Depends(get_current_platform_user)` per Studio-builder Mapping Table canonical pattern
- Frontend consumes via `adminApi` client per Studio-builder Mapping Table — verified at `workflow-templates-service.ts:129/137/146`

### B.4 Tenant-realm routing

- Tenant router: `backend/app/api/routes/workflows.py` (**1,110 LOC**); mounted at `/api/v1/workflows/*` per `app/api/v1.py` registration
- Tenant routes carry the **Workflow Engine Phase W-1 surface** (list workflows; library; start/advance runs; settings; enrollment) — consumed by Surface 1 (tenant `WorkflowBuilder.tsx`) at lines 161-298
- This is a separate router from the admin Studio Workflow Editor's platform-realm route

### B.5 workflow_review_adapter scope (v1 task substrate consumer)

`backend/app/services/workflows/workflow_review_adapter.py` (146 LOC) — Phase R-6.0a substrate; the v1 task substrate B3 `workflow_subscriber` at `backend/app/services/tasks/subscribers/workflow_subscriber.py` resumes parent WorkflowRuns when a task with `provenance_kind='workflow_step'` transitions to a terminal state (file header lines 1-25). This is the **canonical workflow ↔ task substrate boundary** — workflows author tasks via the `create_task` action_type (workflow_engine.py:1173-1241); tasks complete; subscriber resumes the workflow. **Workflow Builder rebuild does NOT touch this substrate** (Phase B boundary preservation).

### B.6 Section B summary

Service layer carries the canonical Phase 4 admin-side substrate (`workflow_templates/*`) at platform-realm with full inheritance resolution + fork lifecycle. Tenant-realm `workflows.py` carries the **distinct Workflow Engine Phase W-1 surface** for runtime execution + tenant-side workflow CRUD. The two substrates coexist and serve different concerns; Phase B rebuild target is the **admin-side Phase 4 substrate** (per §A.3 rebuild-target identification).

---

## Section C — workflow_definitions schema state verification

### C.1 Model location enumeration

Three models carry workflow-shaped schema at HEAD `ca2c7db`:

| # | Model | File | Migration head | Purpose |
|---|-------|------|----------------|---------|
| 1 | `WorkflowTemplate` + `TenantWorkflowFork` | `backend/app/models/workflow_template.py` (193 LOC) | `r82_workflow_templates` (canonical Phase 4 substrate) | Admin-authored workflow definitions at `platform_default` / `vertical_default` scope; tenant forks via `TenantWorkflowFork` |
| 2 | `Workflow` + `WorkflowStep` + `WorkflowRun` + `WorkflowRunStep` + `WorkflowEnrollment` + `WorkflowStepParam` + `WorkflowSchedule` | `backend/app/models/workflow.py` (165 LOC) | Workflow Engine Phase W-1 + r36 (scope column) + r38 (scope backfill fix) | Runtime + tenant-customized workflow definitions; consumed by `workflow_engine.py` execution path |
| 3 | `WorkflowReviewItem` | `backend/app/models/workflow_review_item.py` (83 LOC) | Phase R-6.0a | Review-focus pause substrate; consumed by `workflow_review_adapter.py` |

### C.2 Canonical Phase 4 schema (Surface 3 substrate)

`workflow_templates` table per `WorkflowTemplate` ORM model:

- `id` (UUID PK), `scope` (CHECK: `platform_default | vertical_default`), `vertical` (nullable; CHECK enforces scope-vertical coherence), `workflow_type` (96-char identifier), `display_name`, `description`
- `canvas_state` — **JSONB graph** (nodes + edges + trigger + version per `canvas_validator.py:6-39` schema spec); empty `{}` permitted
- `version` (int; write-side versioning per Phase 4 pattern), `is_active` (partial-unique on `is_active=true`)
- `created_at` / `updated_at` / `created_by` / `updated_by` (FK to users.id)

`tenant_workflow_forks`:

- `tenant_id` (FK companies.id), `workflow_type`, `forked_from_template_id` / `forked_from_version`, `canvas_state` (full graph clone), `pending_merge_available` flag, `pending_merge_template_id`, `version`, `is_active`
- Locked-to-fork merge semantics per CLAUDE.md §4 Workflow Canvas (Phase 4) ledger

### C.3 Composition/definition payload shape

Canvas state per `canvas_validator.py:6-39`:

```
{
  "version": 1,
  "trigger": { "trigger_type": ..., "trigger_config": {...} },
  "nodes": [
    { "id": "n_<slug>", "type": "<node_type>", "position": {x, y}, "config": {...}, "label": "..." }
  ],
  "edges": [
    { "id": "e_<slug>", "source": "<node id>", "target": "<node id>", "condition": "...", "label": "..." }
  ]
}
```

**28-value `VALID_NODE_TYPES` tuple at `canvas_validator.py:62-105`:** subsumes engine step types (input/action/ai_prompt/send_document/playwright_action/condition/output/notification) + action types (create_record/update_record/open_slide_over/show_confirmation/send_notification/send_email/log_vault_item/generate_document/call_service_method) + Phase R-6.0a Generation Focus + Review Focus invocations + Phase 1 registry workflow-node names (generation-focus-invocation; send-communication) + Phase 4 cross-tenant primitives (cross_tenant_order/cross_tenant_request/cross_tenant_acknowledgment) + composition primitives (decision/branch/parallel_split/parallel_join/wait/schedule) + start/end.

### C.4 Migration history

Workflow-related migrations:

- `r82_workflow_templates` — Phase 4 schema (workflow_templates + tenant_workflow_forks; CHECK constraints; partial unique on active rows)
- `r36_workflow_scope` — Phase 8a scope column on `workflows` table
- `r38_fix_vertical_scope_backfill` — Phase 8d corrective backfill (vertical-specific tier-1 workflows mis-classified)
- `r37_approval_gate_email_template` — Phase 8b.5 approval gate email migration
- `r39_catalog_publication_state` — Phase 8d catalog_fetch staging substrate
- `r40_aftercare_email_template` — Phase 8d aftercare migration

Migration head at HEAD `ca2c7db` (per CLAUDE.md §5 + r108/r109 from v1 task substrate): r109 is current head per v1 task substrate B3 close. Phase B rebuild does NOT touch migration head per scope.

### C.5 Schema relationship clone-vs-shared shape

Per DECISIONS.md 2026-05-27 — Auto-save semantics depend on substrate clone-vs-shared shape (Entry 9):

- `WorkflowTemplate` rows at `platform_default` / `vertical_default` scope: **rendered-shared** (every tenant in the vertical sees the same template; edits affect all consumers). Save semantics = manual-save / publish-style per WB-cycle precedent.
- `TenantWorkflowFork` rows: **cloned-per-instance** (one fork per tenant per workflow_type). Could earn auto-save per Focus Builder precedent IF Phase B rebuilds tenant-side authoring; but Surface 3 (admin-side rebuild target per §A.3) operates on rendered-shared `WorkflowTemplate` rows.

**Reading:** Phase B rebuild target operates on rendered-shared substrate → manual-save canonical per Widget Builder precedent + clone-vs-shared canon Entry 9.

### C.6 Section C summary

Phase 4 canonical schema (`workflow_templates` + `tenant_workflow_forks` + canvas_state JSONB graph) is operational + canonical per CLAUDE.md §4 ledger. The 28-value VALID_NODE_TYPES vocabulary subsumes engine action types + Phase 1 registry workflow-node names + Phase 4 cross-tenant primitives. **No schema migration required for Phase B rebuild** (substrate is in place; rebuild targets the authoring surface). Schema substrate is **substrate-prescience-meets-second-consumer** ripe per Entry 17 — schema exists; rebuild operationalizes the second consumer (canonical builder rebuild authoring surface) on top.

---

## Section D — workflow_engine substrate verification (distinct from authoring)

### D.1 Module structure

`backend/app/services/workflow_engine.py` (**2,088 LOC**) — single-file engine per CLAUDE.md §4 Realm-agnostic service layer canon (Edit 7) precedent. The module is operational runtime execution substrate; structurally distinct from `workflow_templates/template_service.py` authoring substrate.

### D.2 Definition consumption pattern

Engine consumes definitions from the runtime `Workflow` + `WorkflowStep` ORM models (file imports at lines 22-28), NOT from `WorkflowTemplate` directly. Pattern at HEAD: tenants enroll in or fork platform/vertical-default workflows; runtime execution reads from `workflows.id` → `workflow_steps.workflow_id`. Phase 4 `workflow_templates` substrate is authoring-layer; tenant adoption maps templates into runtime `workflows` via fork or enrollment.

### D.3 Action dispatch vocabulary

`_execute_action` at line 635-693 routes by `action_type` config field. 17 supported action types per grep at lines 646-691:

- `create_record`, `update_record`, `open_slide_over`, `show_confirmation`, `send_notification`, `send_email`, `log_vault_item`, `generate_document`, `playwright_action`, `call_service_method`, `create_task`, `wait_for_task_completion`, `route_on_task_outcome`, `invoke_generation_focus`, `invoke_review_focus`
- Final 5 (`create_task` + `wait_for_task_completion` + `route_on_task_outcome` + `invoke_generation_focus` + `invoke_review_focus`) are Phase R-6.0a + v1 task substrate integration points
- `unknown_action_type` fall-through at line 693 returns diagnostic status

### D.4 Builder-engine contract

Authoring substrate (Phase B rebuild target) produces `canvas_state` JSONB graph; engine substrate consumes `workflow_steps.config[action_type]` dispatching to handlers. The two vocabularies overlap:

- 28-value `VALID_NODE_TYPES` (authoring vocabulary at `canvas_validator.py:62-105`)
- 17-value engine action_type dispatch (runtime vocabulary at `workflow_engine.py:646-691`)
- 5 step_type values in `workflow_steps.step_type` column (per `workflow.py:80`) used at engine layer for pause/resume semantics
- Trigger-type vocabulary: 5 values (`manual | event | scheduled | time_after_event | time_of_day`) at `canvas_validator.py:8` + `CanvasTrigger` interface at frontend service

**Substrate boundary observation:** authoring substrate vocabulary (28) is broader than runtime substrate vocabulary (17) because authoring substrate covers composition primitives (start/end/decision/branch/parallel_split/parallel_join/schedule/wait) that don't require runtime action_type dispatch + canonical Phase 1 registry names (generation-focus-invocation; send-communication) that map to multiple runtime action_types. The vocabulary asymmetry is **architecturally canonical** per Edit 7 service-layer pattern (authoring is realm-agnostic broader vocabulary; runtime is realm-bound narrower dispatch set).

### D.5 workflow_scheduler / workflow_fork / workflow_run_logger boundaries

Three sibling runtime modules:

- `workflow_scheduler.py` (367 LOC) — APScheduler-driven trigger dispatch (`scheduled` / `time_of_day` / `time_after_event`); Phase 8b.5 + Phase 8c migration touches
- `workflow_fork.py` (284 LOC) — Phase 8a fork-to-tenant runtime substrate (distinct from Phase 4 `tenant_workflow_forks`; this is the soft + hard customization runtime path)
- `workflow_run_logger.py` (112 LOC) — execution audit log

**All three are runtime substrate** — distinct from Phase B rebuild authoring substrate. **Phase B does NOT touch any of these modules** per scope.

### D.6 Section D summary

workflow_engine + workflow_scheduler + workflow_fork + workflow_run_logger compose the **runtime substrate boundary**. The authoring substrate (Phase 4 `workflow_templates`) produces canvas_state graphs; the runtime substrate consumes step-shaped + action_type-shaped configurations. The two substrates are decoupled at the data-model level (separate tables; separate ORM models; separate service layers). **Phase B rebuild stays on the authoring side**; no engine substrate work required. This is a **canonical reuse pattern** per DECISIONS.md 2026-05-27 — Substrate-prescience-meets-second-consumer (Entry 17): the engine substrate exists; the authoring substrate operationalizes the second consumer on top of it.

**No material-divergence trigger fires from §D.** The substrate contract is clean for Phase B rebuild.

---

## Section E — "Wrong-shape" enumeration per operator validation

This section grounds the operator's "original editors we built were not what I wanted" framing in concrete substrate observations against the canonical builder rebuild pattern from Focus Builder + Widget Builder rebuild lineages.

### E.1 What canonical builder rebuild provides

Per Focus Builder rebuild + Widget Builder rebuild deliverables at `docs/investigations/2026-05-18-focus-builder.md` + `docs/investigations/2026-05-21-widget-builder.md`:

1. **Three-region authoring canvas** — left rail (browser / data-source picker), center canvas (composition surface), right rail (selection-driven inspector)
2. **HierarchicalEditorBrowser** as canonical browser pattern at `frontend/src/bridgeable-admin/components/visual-editor/HierarchicalEditorBrowser.tsx` — purely-presentational; categories with child templates underneath; Focus Editor + Workflows ledger both consume
3. **Selection-driven inspector** — empty canvas selection → "nothing selected" state; click background → substrate + theme editing; click node/widget/atom → per-selection chrome editing
4. **Live preview** per always-visible preview substrate canon (DECISIONS.md 2026-05-27 — Always-visible preview substrate for operator-as-platform-builder authoring, Entry 14)
5. **Canvas-layout-model coherence** per WYSIWYG canon (Entry 11) — authoring canvas matches runtime canvas layout model
6. **Variant authoring substrate** per WB-8 + DESIGN_LANGUAGE §12 — surface availability declarations + per-variant overrides
7. **Per-node/per-atom inspector configs** registered against a canonical node-type registry — not hard-coded JSX palette tuples
8. **Auto-save vs manual-save canonical per clone-vs-shared substrate shape** (Entry 9)
9. **Variant + composition browser** wired into Studio rail per Discoverability canon (Entry 22)
10. **Realm-agnostic service layer at platform-realm route prefix** per Edit 7 + Edit 9 (Studio-builder Mapping Table)

### E.2 What current Workflow Builder substrate provides

Per §A.2 Surface 3 evidence:

- Three-region layout (left/center/right) ✓ partial — present but center is a vertical list, not a canvas per Phase 4 ledger
- HierarchicalEditorBrowser ✓ — consumed at line 761 per Visual Editor §4 ledger
- Selection-driven inspector ✓ partial — NodeConfigForm at right rail; no background-click substrate editing
- Live preview ✗ — no canvas preview pane; canvas is the authoring surface (no preview-of-render)
- Canvas-layout-model coherence ⚠ — runtime substrate is graph-shaped (nodes + edges + trigger); authoring substrate renders as a vertical list-with-text-arrows
- Variant authoring substrate ✗ — workflows don't have variants per DESIGN_LANGUAGE §12 (variant axis is for widgets / focus templates); not a deficiency
- Per-node inspector configs registered against canonical registry ✓ partial — 2 of the workflow-node types have dedicated config components (`InvokeGenerationFocusConfig`, `InvokeReviewFocusConfig`); the other 14 fall through to a generic JSON textarea
- Manual-save vs auto-save canonical per clone-vs-shared ⚠ — Surface 3 auto-saves at 1.5s debounce (line 354-372) against `WorkflowTemplate` which is **rendered-shared** substrate; per Entry 9 this is hazardous (operator edits affect all tenants in the vertical immediately). Phase 4 ledger explicitly notes "Save and notify forks" as the explicit alias of save — auto-save fires `notify_forks=true` per the debounce path (line 364). The auto-save semantics are operationally correct via locked-to-fork merge (forks see `pending_merge_available=true` not auto-overwrite) but the substrate-shape is **rendered-shared with auto-save** which doesn't match WB-cycle clone-vs-shared canon (Entry 9 calls out widget definitions as canonical manual-save under rendered-shared)
- Variant + composition browser wired into Studio rail ✓ — per `StudioShell.tsx:70` registration
- Realm-agnostic service layer at platform-realm route prefix ✓ — `template_service.py` at `/api/platform/admin/visual-editor/workflows/*`

### E.3 Specific authoring affordances operator validation suggests Workflow Builder needs

Grounded against concrete substrate gaps from §E.2:

1. **Canvas as canvas, not list:** the workflow canvas renders as `<ol><li>` at lines 924-1004. Per Entry 11 (WYSIWYG discipline as canvas-layout-model constraint), authoring canvas must match runtime canvas layout model. Runtime model is **graph** (nodes + edges + branching + parallel split/join + iteration). Authoring as vertical list breaks WYSIWYG. **The Decide canvas (free-form) + Monitor canvas (grid) distinction at Entry 11 + 2026-05-20 Monitor-vs-Decide canon doesn't directly map** — workflows are a third canvas model (DAG/graph). Phase B rebuild target shape requires graph-canvas authoring substrate distinct from both Decide and Monitor.
2. **Hard-coded palette → node-type registry-driven palette:** lines 893-905 hardcode 16 node types in JSX. Canonical builder rebuild pulls palette from component registry (`workflow-nodes.ts` exists at `registry/registrations/` with 2 entries; expand registry to cover all 28 vocabulary entries; palette renders from registry).
3. **Generic JSON textarea fallback → per-node-type config components:** NodeConfigForm at line 1019-1028 dispatches to dedicated components for `invoke_generation_focus` + `invoke_review_focus` only. Other 14 node types fall through to JSON textarea per the `_placeholders.tsx` registry placeholder pattern. Canonical builder rebuild ships per-node-type inspector configs for all canonical types.
4. **No live render preview:** authoring surface renders the canvas; no separate "what this workflow looks like rendered" preview. Per Entry 14 (Always-visible preview substrate), canonical builder rebuild ships always-visible preview substrate. For workflows, "preview" = simulated execution trace + node-state visualization at design time.
5. **Auto-save semantics misalignment under rendered-shared substrate:** per §E.2 finding, Surface 3 auto-saves rendered-shared substrate. Phase B rebuild target needs canonical manual-save / publish per Entry 9 OR explicit acknowledgment that locked-to-fork merge semantics (pending_merge_available flagging) make auto-save safe in the workflow-template case (distinct from widget-definition case where every tenant immediately sees the edit). This is open question for §G + phasing §8.
6. **Variant authoring substrate (per WB-8 Edit 7):** workflows don't have variants per DESIGN_LANGUAGE §12 — but they have **trigger-type variants** (manual vs scheduled vs event vs time_after_event vs time_of_day). Could be reframed: per-trigger-type authoring affordances + canvas state variants. Phase B rebuild may or may not introduce variant authoring for workflows; investigation-altitude question.
7. **Cross-tenant auth-realm verification per WB-cycle-followup-2:** `/api/platform/admin/visual-editor/workflows/*` is platform-realm per Edit 9 — verified at §B.3. No auth-realm gap visible. ✓.
8. **Phase 1 registry workflow-nodes coverage:** `workflow-nodes.ts` registers 2 of the 28 canonical types. Canonical builder rebuild pattern (Focus Builder + Widget Builder) registers full vocabulary against component registry. Phase B rebuild expands `workflow-nodes.ts` registrations to cover canonical vocabulary.

### E.4 Phase 1 registry workflow-node count vs canonical vocabulary gap

Per CLAUDE.md §4 Component Registry — Phase 1 population: "**2 workflow node types**" registered at `workflow-nodes.ts`. Per `canvas-validator.ts` + `canvas_validator.py`: **28 canonical node types**.

**Concrete gap:** **26 canonical node types lack registry registrations.** Each one would carry `configurableProps` per Component Registry canon (≥3 props per registration per DECISIONS.md 2026-05-19 ≥3 configurableProps canon).

This is a substrate-extension dimension Phase B rebuild may address — analogous to Widget Builder's atom catalog Phase 1 (8 atoms locked) + Phase 1 expansion candidates pattern.

### E.5 Section E summary

The operator's "wrong-shape" framing grounds in **eight concrete substrate observations**:

1. Canvas rendering as vertical list rather than graph (Entry 11 WYSIWYG violation)
2. Hardcoded palette in JSX instead of registry-driven (Phase 1 registry pattern violation)
3. 14 of 16 palette types fall through to JSON textarea inspector (canonical per-type config pattern violation)
4. No always-visible live preview substrate (Entry 14 violation)
5. Auto-save under rendered-shared substrate (Entry 9 nuance — operationally safe via locked-to-fork but doesn't match WB-cycle clone-vs-shared canon)
6. 26-of-28 canonical node types unregistered in component registry (registry coverage gap)
7. Trigger-type variant authoring substrate (open question — workflows aren't widget-variant axis but have trigger axis)
8. Surface 1 tenant `WorkflowBuilder.tsx` carries earlier step-list paradigm parallel to Surface 3 (parallel-surface canon: which is canonical?)

**No material-divergence trigger fires from §E.** The "wrong-shape" framing is **substrate-grounded** with observations matching Focus Builder rebuild + Widget Builder rebuild precedent gaps. Phase B rebuild proceeds against substrate-grounded gap enumeration, not against unclarified operator framing.

---

## Section F — WB cycle + Focus Builder rebuild precedent inventory

### F.1 WB cycle decomposition

Per CLAUDE.md §4 Studio-builder Mapping Table + verified `git log` at session start:

| Sub-arc | Commit | Investigation deliverable | Scope |
|---------|--------|---------------------------|-------|
| Initial investigation | (none, file-only) | `2026-05-21-widget-builder.md` (1,040 lines) | 10 Areas locked; 8 sub-arcs proposed; 40 questions enumerated |
| WB-1 Foundation | `7eb1280` | (inline) | Composition validator + schema + adapter |
| WB-2 ComposedWidget runtime | `95ddd16` | (inline) | Atom catalog + atom registry + atom inspectors |
| WB-3 atom renderers + repeater | `4b6b173` | (inline) | Widget Builder shell + data source picker + composition canvas (drop only) |
| WB-4 canvas | `7b9e19a` → `3680950` (4a) + `3d39598` (4b) | `2026-05-21-widget-builder-canvas.md` | Drag-to-reorder + per-atom selection + chrome inspector |
| WB-5 canvas preview | `1776c90` → `07b183b` | `2026-05-23-widget-builder-canvas-preview.md` (732 lines) | Always-visible preview substrate |
| WB-6 bindings | `5654671` → `0ce41df` | `2026-05-22-widget-builder-bindings.md` (828 lines) | Atom binding + behavior + permissions |
| WB-7 button actions | `cfef35e` → `7e45453` | `2026-05-24-widget-builder-button-actions.md` (1,110 lines) | R-4.0 dispatcher substrate consumption + ActionPicker + dataContext propagation |
| WB-8 variants | `ea7ad24` → `5df25a1` | `2026-05-24-widget-builder-variants.md` (753 lines) | Variant authoring UI activation + parallel-substrate adjudication |
| Followup-1 studio-nav | `3a019e1` → `537ebff` | `2026-05-25-studio-nav-widget-builder.md` (237 lines) | Studio rail entry registration |
| Followup-2 auth-realm | `1303de9` → `33d5721` | `2026-05-26-widget-builder-auth-realm.md` (304 lines) | Realm-agnostic service layer + admin platform router |

**WB cycle totals:** 8 build sub-arcs + 2 follow-up arcs = **10 arcs total**. Per CLAUDE.md §4 WB cycle ledger: estimated total LOC ~9,500-14,000 across 8 sub-arcs (initial investigation §Sub-arc decomposition; midpoint ~11,000).

### F.2 WB cycle LOC envelope calibration

Per DECISIONS.md 2026-05-27 — LOC calibration canon for substrate-additive arcs (Entry 24): WB cycle calibration band — WB-6 3.3× envelope overrun → WB-5 0.5% precision → WB-7 18% honest absorption → WB-8 ±5% predictable scoping. Calibration matures across cycle.

Per-sub-arc LOC range from investigation deliverables + commit messages: WB-1 ~500-1,000; WB-2 ~800-1,500; WB-3 ~1,200-2,000; WB-4 (split into 4a + 4b) ~2,500-3,500 combined; WB-5 ~1,000-1,500; WB-6 ~1,500-2,500 (overrun); WB-7 ~1,500-2,000; WB-8 ~800-1,200. Follow-up arcs ~170 (followup-1 audit-then-fix) + ~600 (followup-2 platform router + service shim).

### F.3 WB cycle investigation arc shape

Per `2026-05-21-widget-builder.md` structure:

1. **Context** — substrate landscape; consumed canons
2. **Canonical UX target** — three-region authoring canvas mockup
3. **Locked decisions** — Area-by-Area Q&A with locks + deferrals
4. **Architectural risks** — Q-RISK-1 through Q-RISK-4 with mitigations
5. **Sub-arc decomposition** — WB-1 through WB-8 with per-sub-arc scope + LOC envelope + dependencies
6. **Deferred for later substrate work** — explicit deferral list
7. **References** — canon-doc cites; substrate-file cites; FF-series precedent cites; commit cites
8. **Architectural surprises** — substrate observations contradicting investigation framing
9. **Operator-validation gates** — per Entry 26 canon
10. **Closing summary**

### F.4 Focus Builder rebuild decomposition

Per `2026-05-18-focus-builder.md` structure:

- 5 sub-arcs: **F-1 → F-2 → F-3 → F-4 → F-5**
- LOC envelope: ~6,500-9,500 total
- Plus FF-series UX refinement sub-arcs visible in `docs/investigations/2026-05-20-*` (3 refinement deliverables: `free-form-focus-canvas.md`, `resize-handle-ux-refinements.md`, `hover-state-staging-regression.md`)
- FF-5 commit at `be46182` ("third operator-interactive FF sub-arc; first context menu")

### F.5 Focus Builder UX refinement sub-arc precedent

Per FF-series visible at `docs/investigations/2026-05-20-*`: 3 refinement sub-arcs surfaced post-substrate work as natural operator-observable-signal triggered iterations. Pattern applies to Phase B: substrate sub-arcs ship canonical functionality; refinement sub-arcs ship per-operator-validated UX gaps.

### F.6 Cross-cycle commit-shape patterns

Per DECISIONS.md 2026-05-27 — Arc-commit-granularity canon (Entry 26):

- Single-commit-at-arc-close default for arcs ≤ ~3,000 LOC without parity-discipline complexity (Focus Builder sub-arcs each closed in single commits)
- Three-commit-within-arc-identity earned by scope + parity-discipline criteria (v1 task substrate B1/B2/B3 per `2fba161` / `a400d1b` / `1c8dbbd`)
- WB cycle sub-arcs land as 1-2 commits each per investigation lock; followups land as 2-commit (investigation deliverable + build commit)

### F.7 Section F summary

WB cycle precedent: **8 substrate sub-arcs + 2 followup arcs = 10 arcs**; LOC envelope ~9,500-14,000; per-sub-arc range ~500-2,500; commit-shape mostly 1-2 commits each; investigation arc shape 10-section canonical structure. Focus Builder precedent: 5 substrate sub-arcs + 3 UX refinement sub-arcs; LOC envelope ~6,500-9,500.

**Phase B rebuild calibration anchor:** between Focus Builder (5 sub-arcs ~6,500-9,500 LOC) and WB cycle (8 sub-arcs ~9,500-14,000 LOC). Specific Phase B sub-arc count + LOC envelope locks at Phase 4 phasing recommendation per §3 + §7 of phasing deliverable.

---

## Section G — Cross-arc dependencies + boundary preservation

### G.1 Phase C Document Builder rebuild boundary

Per Entry 32 (per-arc pre-dispatch rescoping for distant-horizon arcs): Phase C operates under its own pre-dispatch rescoping arc. Phase B rebuild does NOT lock Phase C scope. Phase 4 §4 (per phasing canon Entry 27) captures forward-reference to Phase C without locking scope.

Per CLAUDE.md §4 Visual Editor Top-Level Structure: Document Builder substrate exists in part (Documents arc Phase D-1 through D-11 shipped; block-based authoring at Phase D-10/D-11; vertical tier at Phase D-11). The Documents editor at `/visual-editor/documents` is currently placeholder per the table. Phase C rebuild scope = full document-authoring editor on top of existing Documents arc substrate. **Phase B does not pre-locks Phase C scope.**

### G.2 C42 boot-adapter shape boundary

Per Entry 3 (deferral-tracking meta-pattern): C42 boot-adapter-takes-client substrate decision was deferred from WB-cycle-followup-2 per Q-B1 lock to a dedicated September-decision arc. Phase B preserves Q-B1 boundary:

- Phase B does NOT modify the tenant `registerComposedWidgets` runtime bridge
- Phase B does NOT touch composed-definitions cold-start palette degradation
- Cold-start composed-definitions palette degradation per userMemories carries forward unchanged to September-decision arc

### G.3 Task substrate v1 boundary

Per Phase A close at HEAD `ca2c7db` + v1 task substrate canonical at Entry 13 (substrate-transition discipline):

- v1 task substrate operational at HEAD
- Workflow Builder rebuild operates on workflow_templates / workflows authoring substrate
- Workflows can author tasks via `create_task` action_type per workflow_engine.py:1173-1241
- The workflow → task substrate boundary is **producer-only at Phase B**: Phase B rebuild authors workflows that can include `create_task` nodes; this consumes existing `create_task` action_type substrate without modification
- The reverse boundary (task completion → workflow resume) lives in `tasks/subscribers/workflow_subscriber.py` per v1 B3 + is unchanged at Phase B
- **Phase B does NOT touch task substrate** per scope

### G.4 Visual editor canon preservation

Per CLAUDE.md §4 Visual Editor Top-Level Structure (May 2026 reorganization): Workflows editor at `/visual-editor/workflows` is one of 7 purpose-specific editor pages. Phase B rebuild operates **within** the canonical Visual Editor §4 structure — does NOT modify Top-Level Structure ledger.

Per CLAUDE.md §4 Studio-builder Mapping Table (Edit 9): Workflow Editor row carries (Studio path `/admin/visual-editor/workflows`; backend `/api/platform/admin/visual-editor/workflows/*`; platform realm; `adminApi` client). Phase B rebuild **inherits the canonical platform-realm + adminApi pattern verbatim** — does NOT change realm + client mappings.

Per CLAUDE.md §4 Realm-agnostic service layer canon (Edit 7): Phase B service layer follows realm-agnostic shape from foundation per canonical Studio-authored-substrate pattern. Service layer at `backend/app/services/workflow_templates/*` already shipped realm-agnostic at Phase 4 — no refactor required.

### G.5 Discoverability canon (Entry 22)

Per Entry 22 (discoverability canon for operator-facing substrate cycles): Workflow Builder rail entry already operational via `StudioShell.tsx:70` registration. Studio nav arc canon shipped at WB-cycle-followup-1 covers rail-entry registration discipline. **Phase B inherits the rail-entry shape; auth-realm reachability is verified at §B.3 + §G.4**.

### G.6 Section G summary

All boundaries preserved:

- ✅ Phase C Document Builder boundary preserved
- ✅ C42 boot-adapter shape preserved (September-decision arc)
- ✅ Task substrate v1 boundary preserved (Phase B doesn't touch)
- ✅ Visual editor canon preserved (Phase B operates within §4 structure)
- ✅ Realm-agnostic service layer canon preserved (existing service layer already canonical)
- ✅ Studio-builder Mapping Table preserved (Phase B inherits row verbatim)
- ✅ Discoverability canon preserved (rail entry shipped)

**No boundary violations surface from §G.**

---

## Phase 0 closing

Phase 0 audit closes. Deliverable shipped at `docs/investigations/workflow_builder_rebuild_phase0_audit.md` per Entry 4 persistent-storage discipline. Per Entry 31 bounded-decision-per-arc explicit naming, Phase 0 bounded decision = "produce Phase 0 audit deliverable per dispatch §7 7-section structure; surface concrete substrate observations grounding operator's 'wrong-shape' framing; lock NO Phase 4 phasing content; lock NO Phase B build dispatch; lock NO scope outside Phase B" — bounded decision satisfied.

**Audit summary by section:**

- **§A** — 4 frontend surfaces enumerated; Surface 3 (`bridgeable-admin/pages/visual-editor/WorkflowEditorPage.tsx`, 1,035 LOC) locked as Phase B rebuild target per Studio-builder Mapping Table canonical mount; Surface 1 (`pages/settings/WorkflowBuilder.tsx`, 1,876 LOC) classified built-but-mis-shaped legacy; Phase B scope-touch decision on Surface 1 surfaced as Phase 4 §8 open question.
- **§B** — 3 service-layer modules enumerated; `workflow_templates/*` (910 LOC) is canonical Phase B substrate; existing platform-realm router at `visual_editor_workflows.py` (401 LOC) operational; tenant-realm `workflows.py` (1,110 LOC) is parallel Workflow Engine Phase W-1 substrate (NOT Phase B target).
- **§C** — Phase 4 schema operational (`workflow_templates` + `tenant_workflow_forks` with JSONB canvas_state graph); 28-value VALID_NODE_TYPES vocabulary; **no schema migration required** for Phase B rebuild.
- **§D** — workflow_engine substrate at 2,088 LOC is distinct runtime substrate from authoring substrate; engine consumes 17 action_types; authoring vocabulary (28) is superset; vocabulary asymmetry is canonical per Edit 7. **Phase B stays on authoring side**; no engine work required.
- **§E** — operator "wrong-shape" framing grounded in **8 concrete substrate observations**: canvas-as-list-not-graph (Entry 11), hardcoded palette, JSON-textarea fallback for 14/16 types, no live preview substrate (Entry 14), auto-save under rendered-shared (Entry 9 nuance), 26-of-28 unregistered node types, trigger-variant authoring open question, parallel Surface 1/Surface 3 question. Substrate-grounded; **no material-divergence trigger fires**.
- **§F** — WB cycle precedent: 8 substrate + 2 followup sub-arcs; ~9,500-14,000 LOC; investigation arc 10-section canonical structure. Focus Builder precedent: 5 sub-arcs; ~6,500-9,500 LOC. Phase B calibration anchor between the two.
- **§G** — all 7 cross-arc boundaries preserved (Phase C, C42, task substrate, visual editor canon, realm-agnostic service layer, Studio-builder Mapping Table, discoverability canon).

**No material-divergence triggers fired during Phase 0 audit.** No canon edits. No STATE.md edits. No production code. No Phase 4 phasing content. No Phase B build dispatch. No Q-B1 resolution. No task substrate work. 114 stale Playwright screenshot deletions untouched.

**Next-gate handoff:** Phase 4 phasing recommendation drafted in parallel deliverable at `docs/investigations/workflow_builder_rebuild_phasing.md`; operator reviews both deliverables; confirms Phase B substrate phase + integration phase locks + sub-arc decomposition + open questions before Phase B build prompt drafting downstream.

**Word count:** ~6,200 words (within ~5,000-7,500 envelope; ≥9,500 would be over-synthesis signal — not fired).
