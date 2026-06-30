# MoC Workflow Backfill — Inventory + Build Scoping (read-only)

**HEAD:** `1f4ee81` · **Date:** 2026-06-30 · **Status:** triaged inventory (banked) + phased
build plan. NOT a build.

Goal: bring existing early-development workflows into the manufacturing MoC as
(1) FAITHFUL `workflow_template` canvas mirrors on the Workflows card, and (2)
EDITABLE `moc_task_catalog` rows referencing them. Context: the early-dev
workflows are runtime `workflows` (executable, step rows); the MoC references
`workflow_templates` (canvas/design) — the canvas-vs-runtime split
(DECISIONS 2026-06-30). The mirrors bridge that by snapshotting runtime steps into
canvas templates.

---

## TL;DR — the sizing finding

**Runtime → canvas is a CLEAN MECHANICAL SCRIPT, not hand-translation.** Verified
against the real step rows: every target workflow is **linear** (no `next_step_id`
branching), has **no duplicate step_keys**, and uses only **`action` / `input` /
`output`** step_types — all in `VALID_NODE_TYPES`. The transform is one node per
step (`id`=step_key, `type`=step_type, `config` carried verbatim, `position` from
step_order) + edges by consecutive order + trigger from `trigger_type`. The
validator only requires `{version, nodes, edges}` and accepts this shape. So
faithful-mirroring ~18 workflows is a **~100-line script run once**, not 18
hand-authored canvases. This is the cheap path — Build 1 is small.

The real new capability is **Build 2 (the editable task table)** — `moc_task_catalog`
is read-only via API today; making it author-editable (write API + inline edit +
the workflow/focus relationship picker) is where the weight is.

---

## 1. The triaged inventory (banked)

From the deduplicated, test-fixture-stripped runtime `workflows` (canonical source
is `default_workflows.py`; `bridgeable_dev` is test-polluted — 936 rows, ~28 fixture
names, 2089 tenants).

### MIRROR these — manufacturing-vertical, real, non-overlapping (12)

| Workflow | tier | steps |
|---|---|---|
| Bridgeable Compose | 2 | 7 |
| New Order | 2 | 7 |
| Order Gloves from Uline | 3 | 6 |
| Add Team Certification | 2 | 5 |
| Safety Program Generation | 1 | 5 |
| Vault Order Fulfillment | 1 | 5 |
| Log Production Pour | 2 | 4 |
| Schedule Delivery | 2 | 4 |
| Social Service Certificate | 1 | 3 |
| Start Disinterment Workflow | 2 | 3 |
| Wilbert Catalog Auto-Fetch | 1 | 3 |
| Document Review Reminder | 1 | 2 |

### MIRROR — core/cross-vertical, real (6) — *if* the manufacturing MoC surfaces shared workflows

| Workflow | tier | steps | note |
|---|---|---|---|
| Month-End Close | 1 | 10 | agent-backed (thin mirror — see caveat) |
| AR Collections | 1 | 5 | agent-backed (thin mirror) |
| Compliance Sync | 1 | 4 | |
| Monthly Statement Run | 1 | 4 | |
| Expense Categorization | 1 | 3 | agent-backed (thin mirror) |
| Training Expiry Monitor | 1 | 2 | |

### EXCLUDE — demo-artifact overlap (4) — the demo `workflow_templates` already cover these
- **Create Invoice** + **Send Statement** ≈ the demo **Invoice and Statement Run** template.
- **Legacy Print — Proof** + **Legacy Print — Final** ≈ the demo **Legacy Order** template.

### EXCLUDE — operator-triaged out (3)
- **Create Vault Order (legacy)** (legacy in its own name).
- **Auto-Delivery Eligibility Check** (1-step stub) · **End of Day Delivery Review** (1-step stub).

### EXCLUDE — other vertical (12 funeral_home) + test fixtures (~28). Not manufacturing / pollution.

> **Count reconciliation:** the explicit MIRROR set nets to **12 manufacturing + 6
> core = 18**. The triage framing said "16 manufacturing"; reconcile against the
> explicit list above (the difference is whether Create Invoice / Send Statement /
> the two Legacy Print runtime workflows are mirrored despite the demo-template
> overlap — the dispatch said exclude them, which is what's listed). **Confirm the
> exact set before Build 1 runs.**

---

## 2. The runtime → canvas transform (Build 1's core, verified mechanical)

**Runtime `workflow_steps`:** `step_order, step_key, step_type, config (JSONB),
display_name, next_step_id`.
**Canvas node:** `{id, type, label, config, position:{x,y}}`.
**Canvas `canvas_state`:** `{version, trigger, nodes[], edges[]}`.

Per-workflow transform:
```
node[i]   = { id: step.step_key,
              type: step.step_type,              # action|input|output — all VALID
              label: step.display_name || step.step_key,
              config: step.config,               # verbatim (validator treats config as opaque)
              position: { x: 0, y: step.step_order * 120 } }
edges     = [ { id: `e${i}`, source: step[i].step_key, target: step[i+1].step_key } ]
            # consecutive by step_order — all targets are LINEAR (no next_step_id)
trigger   = { type: workflow.trigger_type }      # carry trigger_config if present
canvas_state = { version: 1, trigger, nodes, edges }
```
Then `validate_canvas_state(canvas_state)` (passes: valid types, unique ids, real
edge refs, acyclic-linear, position≥0) → insert as a `workflow_template`
(scope=`vertical_default`, vertical=`manufacturing` for the 12; the 6 core are
`scope=platform_default`/`vertical=None` — decide whether they surface on a
*manufacturing* MoC at all).

**Verified preconditions (all hold across the target set):** no duplicate step_keys
(node-id uniqueness safe) · no `next_step_id` branching (pure linear edges) ·
step_types ⊆ `{action,input,output}` ⊆ `VALID_NODE_TYPES` · validator accepts the
shape (min valid = `{version,nodes,edges}`; no start/trigger node required).

**Caveats (faithful but flag):**
- **Agent-backed core (3): Month-End Close / AR Collections / Expense
  Categorization** still carry `agent_registry_key`; their steps are mostly
  `action_type=None` agent-delegating descriptors (+ one `call_service_method`).
  The mirror is faithful to the runtime steps but **thin/generic** (the real logic
  is Python, not steps). Recommend: either exclude the 3 agent-backed from
  mirroring, or accept thin mirrors with a clear provenance note.
- **Positions auto-derived** (linear x=0/y=order) — valid but not visually arranged;
  the editor lets the operator rearrange post-mirror.
- **Non-canonical action_types** (e.g. `system_job`) render as generic action nodes
  in the editor — harmless (config is opaque to the validator + it's a snapshot).

---

## 3. Drift provenance (the known divergence risk)

The mirrors are **inert snapshots** — they will NOT execute (canvas ≠ runtime) and
will **drift** as the runtime workflows change. This must be recorded so future-us
knows a mirror is a snapshot, not a source of truth.

**Recommendation (no migration):** write the provenance into the template's
`description`: *"Mirror of runtime workflow '<name>' (<workflow_id>) as of
<date> — inert snapshot for MoC navigation; the runtime workflow is the source of
truth and may have drifted."* If queryable provenance is later wanted, a small
migration adds `workflow_templates.mirrored_from_workflow_id` (FK, nullable) — flag
as optional, not blocking. Do NOT silently mirror without the note (it would read
as an authored template).

---

## 4. Build 1 — the mirror script (small)

- A one-shot seed/script: for each confirmed target, read its runtime steps →
  transform (§2) → validate → upsert a `workflow_template` (idempotent by
  `(scope, vertical, workflow_type)`; provenance in `description`).
- **1b — thin task rows:** for each mirrored template, `upsert_task` a
  `moc_task_catalog` row (name = workflow name, `workflow_template_id` pre-wired,
  descriptive fields BLANK) so the workflow lands on the Workflows card AND as a
  task row the operator then enriches via Build 2.
- Extend `seed_moc_manufacturing` to reference the mirrors on the Workflows card
  (the existing resolve-or-skip pattern).
- **No migration.** Pure `workflow_templates` + `moc_task_catalog` rows + canvas JSON.
- **Assembly test (round-trip):** a runtime workflow → faithful template
  (`validate_canvas_state` passes; node/edge count matches step count) → the
  resolver surfaces it on the card → the MoC deep-link opens it to the real shape
  (N nodes, not a hollow stub). Assert the mirror's node count == the runtime step
  count for ≥2 workflows (e.g. New Order=7, Vault Order Fulfillment=5).

---

## 5. Build 2 — the editable task table (the real new capability)

`moc_task_catalog` is **read-only via API today** — `GET /tasks` only; the sole
write is the `upsert_task` *service* (seed-only). All columns to edit already exist
(`name, frequency, task_type, description, icon, workflow_template_id,
display_order` + the `moc_task_catalog_focuses` join). **No migration.**

- **Write API** (mirror the existing page-CRUD in `app/api/routes/admin/moc.py`,
  `get_current_platform_user`): `POST /tasks` (create), `PATCH /tasks/{id}` (edit
  descriptive fields + `workflow_template_id` + the focus set), `DELETE /tasks/{id}`.
  Reuse/extend `upsert_task` (already handles all fields incl. `focus_template_ids`);
  add a delete + a single-row patch shape.
- **Inline-edit UI** on the Tasks table (the 2c read-only component): descriptive
  cells → in-place text edit (name/frequency/task_type/description); save on
  blur/Enter. Validation: name required; bounded lengths.
- **Relationship picker:** the Workflow cell → single-select over the real
  `workflow_template`s (the resolver's catalog — now including the mirrors); the
  Focuses cell → multi-select over real focus templates. This is how a task gets
  wired to a mirror. Source the options from the existing template/focus catalogs
  (the same artifacts the resolver knows).
- **States (§18):** optimistic patch with rollback-on-error (or save-then-refetch —
  pick one; optimistic is nicer for inline edit), a deliberate empty (no tasks yet),
  inline error on a failed save.
- **Weight:** the write API is small (CRUD over an existing table + existing
  service). The inline-edit + relationship-picker UI is the bulk — scoped against
  ~18 rows (small N, no virtualization needed) but the picker (searchable
  template/focus selectors) is the non-trivial piece.
- **Assembly test:** the write API creates/patches a task → the resolver
  (`GET /tasks`) returns the new/edited values + the wired workflow/focus resolve
  (artifact_id present). Round-trip a create → patch (wire a workflow_template) →
  read (the Workflow cell now resolves the mirror).

---

## 6. Composition (confirmed)

1. **Build 1** mirrors the confirmed runtime workflows → `workflow_templates` +
   Workflows-card refs (faithful, provenance-noted, validated).
2. **Build 1b** auto-creates a thin `moc_task_catalog` row per mirror
   (workflow pre-wired, descriptive fields blank).
3. **Build 2** is how the operator turns those thin rows rich (sets
   frequency/type/description, adjusts the workflow/focus wiring inline).

This is the right shape: Build 1 gets the workflows IN (cheap script); Build 2 is
the durable authoring capability the operator drives thereafter. **Sequence: Build
1+1b first (proves the mirrors render), then Build 2 (the editor over them).**

---

## 7. Migrations
- **Build 1 / 1b:** none (rows + canvas JSON over existing tables).
- **Build 2:** none (CRUD over existing `moc_task_catalog` + `_focuses`).
- **Optional:** `workflow_templates.mirrored_from_workflow_id` (queryable
  provenance) — only if `description`-based provenance proves insufficient. Not
  blocking.

## 8. Open decisions for the operator (before Build 1)
1. **Confirm the exact mirror set** (the 12 mfg ± the Create Invoice/Send Statement/
   Legacy Print overlap question; the "16 vs 12" reconciliation).
2. **Core/cross-vertical (6):** surface on the *manufacturing* MoC, or manufacturing-
   specific only? And the **3 agent-backed** (Month-End Close / AR Collections /
   Expense Categorization) — mirror as thin, or exclude?
3. **Provenance:** `description` note (recommended, no migration) vs the optional
   `mirrored_from_workflow_id` column.

No build, mirror, seed, or task created. The plan is the deliverable.
