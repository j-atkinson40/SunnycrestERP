# Task Substrate v2a + v2c — Phase 0 Audit

> Read-only audit deliverable at the close of Phase 0 of the v2a+v2c task substrate completion investigation. Joins canon-update arc forward-reference for Phase 4 phasing recommendation (`docs/investigations/task_substrate_v2a_v2c_phasing.md` — Phase 4 deliverable).
>
> Persistent storage from start per DECISIONS.md 2026-05-27 — Persistent-storage discipline for investigation deliverables.

## Phase 0 metadata

- **Arc context:** v2a + v2c task substrate completion investigation; Phase 0 of two (Phase 4 phasing recommendation downstream)
- **HEAD at audit:** `cce834d` (Canon-update arc close: 35 DECISIONS.md entries + 10 canon-doc edits)
- **Audit date:** 2026-05-27
- **Canon ground:** 35 DECISIONS.md entries dated 2026-05-27 at HEAD `cce834d`; CLAUDE.md §4 Task Substrate H3; PLUGIN_CONTRACTS.md §25-27; STATE.md Recently-shipped log
- **Phasing doc anchor:** `docs/investigations/task_substrate_v2_phasing.md` §3.1 v2a (10 enumerated queues) + §3.3 v2c (5 refinement deliverables) + §5 signal patterns + §6 cross-version
- **State doc anchor:** `docs/investigations/task_substrate_v2_state.md` (locked architecture; locked sequence broad shape; operator locks)
- **v1 completion artifact:** `docs/investigations/task_substrate_v1_completion.md` (v1 arc close; 15 disciplines; 8 producer sites)
- **Operator framing locks:** v2a+v2c as Phase A (task substrate completion); v2b OUT-OF-SCOPE; September anti-signal acknowledged; building-correctness-over-schedule-pressure per Entry 2 anti-signal canon
- **Substrate-state framing:** four-state extension introduced — `built-operator-facing` / `built-but-dormant` / `built-but-mis-shaped` (operator-introduced fourth state) / `missing`

---

## Section A — v1 task substrate operational state verification

### A.1 8 producer sites flow through `create_task_with_provenance`

The 8 producer sites enumerated in v1 completion artifact §2 are verified operational at HEAD `cce834d`. The expected paths in the build prompt (e.g. `backend/app/services/workflow/workflow_step_completion.py:154`) did NOT match the as-built layout — actual sites are at flatter paths under `backend/app/services/`. Each site carries a `v1 task substrate B2 — producer site #N` inline comment marking the (c) refactor lineage.

| # | Site | Producer | Provenance dispatch |
|---|------|----------|---------------------|
| 1 | `task_service.py:184–198` | Manual task creation | `provenance_kind="manual_creation"` (canonical entrypoint) |
| 2 | `social_service_certificate_service.py:162–169` | SS cert pending-approval | `integration_event` / `social_service_certificate` |
| 3 | `agents/base_agent.py:330–376` | AgentAnomaly + AgentJob (cash_receipts / ar_collections / expense_categorization / month_end_close) | `anomaly_detection` for anomaly cohort; `workflow_step` for month_end_close |
| 4 | `workflows/aftercare_adapter.py:206–214` | Aftercare follow-up | `workflow_step` / `agent_job` (job_type=`fh_aftercare_7day`) |
| 5 | `workflows/catalog_fetch_adapter.py:258–268` | Urn catalog sync pending review | `integration_event` / `urn_catalog_sync_log` |
| 6 | `safety_program_generation_service.py:179–189` | Safety program AI generation pending review | `workflow_step` / `safety_program_generation` |
| 7 | `workflow_engine.py:828–835` | Workflow review pause (invoke_review_focus) | `workflow_step` / `workflow_review_item` |
| 8 | `classification/dispatch.py:379–390` | Email classification cascade fall-through | `communication_inbound` / `workflow_email_classification` |

A 9th in-tree caller (`workflow_engine.py:1219–1234`) is the `create_task` workflow-engine action handler — not a producer site per the (c) categorization but a consumer of the substrate via workflow node dispatch.

**Finding:** All 8 (c)-refactored producer sites operational. Provenance vocabulary use is consistent with the 12-value `PROVENANCE_KINDS` tuple at `task_details.py:187–199`.

### A.2 6 v1 subscribers operational

Subscriber registry at `backend/app/services/tasks/subscribers/registry.py` exposes `register_subscriber()` + a 7-event-type vocabulary (`task_created` / `task_assigned` / `task_status_changed` / `task_completed` / `task_blocked` / `task_unblocked` / `task_cancelled`). All 6 v1 subscribers register:

| Subscriber | Module | Registration line |
|------------|--------|-------------------|
| `audit_writer` | `audit_subscriber.py` | line 77 |
| `notification_dispatcher` | `notification_subscriber.py` | line 217 |
| `briefings_invalidator` | `briefings_subscriber.py` | line 80 |
| `pulse_invalidator` | `pulse_subscriber.py` | line 75 |
| `focus_closer` | `focus_subscriber.py` | line 93 |
| `workflow_resumer` | `workflow_subscriber.py` | line 134 |

**Finding:** 6 v1 subscribers operational. Dispatch is sync per state doc §5.7 v1 lock; persistent log is v2c deferred.

### A.3 5 task type behavior plugins

`backend/app/services/tasks/plugins/types/` contains exactly the 5 v1 plugins:

- `generic_task.py`
- `review_approval_task.py`
- `scheduled_recurring_task.py`
- `customer_communication_task.py`
- `anomaly_resolution_task.py`

Each registers via the `task_type_behaviors` plugin contract (PLUGIN_CONTRACTS.md §27). 6th plugin (`scheduled_audit_task` per state doc §4.7) is v2c-deferred.

### A.4 Pulse Personal layer + briefings + Focus integration

- **Pulse Personal layer:** `_build_tasks_item` wired at `backend/app/services/pulse/personal_layer_service.py:91–95` (TASKS_ASSIGNED_KEY at line 91; function body returns a `LayerItem` rather than `None`; v1 B3 inline comment at line 3 marks the wire commit).
- **Briefings:** `backend/app/services/briefings/data_sources.py:139–149` consumes three task-shape summaries (`pending_tasks` / `recent_task_completions` / `upcoming_task_deadlines`) via the `_collect_pending_tasks_summary` helper at line 293. Defensive try/except per v1 B3 discipline.
- **Focus session linkage:** `backend/app/models/focus_session.py:76–77` declares the `task_id` nullable FK column added by migration `r108_focus_session_task_extension.py`. `focus_subscriber.py` handles the `task_completed` → focus closure path.

### A.5 Test cohort

214 test functions across `backend/tests/test_task_and_triage.py` + `backend/tests/tasks/*.py` (10 task substrate test modules: `test_backfill.py` / `test_facade.py` / `test_lifecycle_action.py` / `test_lifecycle_reminder.py` / `test_plugin_creators.py` / `test_plugin_surfaces.py` / `test_plugin_type_behaviors.py` / `test_r108_migration.py` / `test_subscribers.py` / `test_substrate_schema.py` + `test_b2_notification_dispatcher.py` / `test_b3_consumer_integration.py`). Test count consistent with the ~150-200 estimate at v1.0 specification + B2 + B3 expansion.

### A.6 Section A summary

**v1 task substrate operational state verified.** All 8 producer sites + 6 subscribers + 5 task type plugins + Pulse Personal wire + briefings consumption + Focus linkage + r108/r109 migrations operational at HEAD `cce834d`. No regressions surfaced. No material-divergence trigger fires from Section A.

---

## Section B — v2a triage adapter scope enumeration

### B.1 Substrate-state framing reframe

The Phase 0 audit surfaces a **substantive substrate-state finding** that reshapes v2a scope. Per phasing doc §3.1, v2a was scoped as "10 non-task triage queue adapters" using **adapter-substrate pattern** — adapter observes existing substrate's state transitions and creates a task; original substrate row stays as authoritative business state; task is the visibility surface.

**At HEAD `cce834d`, all 10 enumerated v2a triage queues are already operational at BOTH the producer-side AND consumer-side substrate layers**, but in **distinct substrate states**. Specifically:

1. **All 10 queues have producer-side task creation paths.** The (c) build arc refactor at v1 B2 (commit `a400d1b`) wired notification dispatch through `create_task_with_provenance` for the 8 producer sites enumerated in Section A. Each of the 10 v2a queues maps to one or more producer-site call paths. Tasks ARE being created for every queue's business-state transition.

2. **All 10 queues have consumer-side direct-query builders.** `backend/app/services/triage/engine.py:1432–1450` registers `_DIRECT_QUERIES` with handlers for every v2a queue (`cash_receipts_matching_triage` / `ar_collections_triage` / `expense_categorization_triage` / `month_end_close_triage` / `safety_program_triage` / `aftercare_triage` / `catalog_fetch_triage` / `ss_cert_triage` / `workflow_review` / `email_unclassified`).

3. **Consumer-side direct-query builders read from ORIGINAL substrate (AgentAnomaly / SafetyProgramGeneration / UrnCatalogSyncLog / SocialServiceCertificate / WorkflowReviewItem / WorkflowEmailClassification), NOT from task substrate.** Example: `_dq_cash_receipts_matching_triage` at `engine.py:720–770` queries `AgentAnomaly` joined to `AgentJob`; it does not consult `task_details`.

**This is a dual-write transitional substrate state per Entry 14 — Substrate-transition discipline.** Producer side dual-writes (original substrate row PLUS task); consumer side single-reads (original substrate). The transition from dual-write to canonical-task-read is the v2a scope.

### B.2 Per-queue audit findings × 10 queues

All 10 queues classified as **built-operator-facing** (substrate AND UI surface AND producer-side task creation all operational) — with the qualification that the **canonical-substrate adjudication** for read path defaults to original substrate, not task substrate. None classified as `built-but-mis-shaped` (no operator-validated wrong-shape signal surfaces in the audit; if operator surfaces such a signal at gate review, that's material divergence). None classified `missing`. None classified `built-but-dormant` (every queue has UI surface registration via `register_platform_config` in `platform_defaults.py`).

**Per-queue inventory:**

#### 1. `cash_receipts_matching_triage`
- **Queue config:** `platform_defaults.py:251` — manufacturing/cross-vertical, `invoice.approve` permission
- **Producer site:** `agents/base_agent.py:330` (#3); job_type=`cash_receipts_matching`
- **Consumer direct-query:** `engine.py:720` `_dq_cash_receipts_matching_triage` reads `AgentAnomaly` (CRITICAL/WARNING/INFO sort)
- **Cardinality:** per-anomaly
- **Producer-supplied context (metadata):** `notification_permission_key="invoice.approve"`, `notification_category="agent_anomaly_pending"`, `notification_link`, `notification_source_reference_{type,id}`
- **Substrate state:** built-operator-facing; producer dual-writes; consumer reads original
- **Substrate-similarity grouping:** AgentAnomaly-shaped per-anomaly cluster
- **Adapter scope estimate:** ~250–400 LOC for consumer-side read-path migration (the producer side is already done)

#### 2. `ar_collections_triage`
- **Queue config:** `platform_defaults.py:484`
- **Producer site:** `agents/base_agent.py:330` (#3); job_type=`ar_collections`
- **Consumer direct-query:** `engine.py:905` `_dq_ar_collections_triage` reads `AgentAnomaly` joined to `Customer` (per-customer fan-out)
- **Cardinality:** per-customer (per phasing §3.1 + B2 (c) build arc fan-out fidelity discipline)
- **Producer-supplied context:** same notification metadata cohort as #1
- **Substrate state:** built-operator-facing; producer dual-writes; consumer reads original
- **Substrate-similarity grouping:** AgentAnomaly-shaped per-customer cluster (distinct cardinality from #1)
- **Adapter scope estimate:** ~300–450 LOC (per-customer fan-out logic needs preservation in read-path migration)

#### 3. `expense_categorization_triage`
- **Queue config:** `platform_defaults.py:591`
- **Producer site:** `agents/base_agent.py:330` (#3); job_type=`expense_categorization`; conditional quiet-runs (anomaly_count==0 → no task)
- **Consumer direct-query:** `engine.py:1016` `_dq_expense_categorization_triage`
- **Cardinality:** per-line (one AgentAnomaly per expense line)
- **Producer-supplied context:** same notification metadata cohort as #1; quiet-run gating preserved in task creation
- **Substrate state:** built-operator-facing; producer dual-writes; consumer reads original
- **Substrate-similarity grouping:** AgentAnomaly-shaped per-line cluster
- **Adapter scope estimate:** ~250–400 LOC

#### 4. `month_end_close_triage`
- **Queue config:** `platform_defaults.py:381`
- **Producer site:** `agents/base_agent.py:330` (#3); job_type=`month_end_close`
- **Consumer direct-query:** `engine.py:839` `_dq_month_end_close_triage` reads `AgentJob` in `awaiting_approval` state
- **Cardinality:** per-job (the whole AgentJob is the decision; anomalies are sub-context per Phase 8c canon)
- **Producer-supplied context:** `notification_permission_key="invoice.approve"`, `category="agent_job_awaiting_approval"`, period_label
- **Substrate state:** built-operator-facing; producer dual-writes; consumer reads original
- **Substrate-similarity grouping:** AgentJob-per-job cluster (distinct cardinality)
- **Adapter scope estimate:** ~300–450 LOC (period-lock + approval semantics preserved)

#### 5. `safety_program_triage`
- **Queue config:** `platform_defaults.py:890`
- **Producer site:** `safety_program_generation_service.py:179` (#6); only fires when `gen.status == "pending_review"`
- **Consumer direct-query:** `engine.py:1250` `_dq_safety_program_triage` reads `SafetyProgramGeneration` directly via `status` enum (`draft / pending_review / approved / rejected`)
- **Cardinality:** per-run (per-run cardinality, sixth variant per Phase 8d.1 canon — pre-existing state-machine substrate, not AgentJob-backed)
- **Producer-supplied context:** topic title, OSHA standard reference
- **Substrate state:** built-operator-facing; producer dual-writes; consumer reads original
- **Substrate-similarity grouping:** per-run-cardinality with pre-existing-status-enum cluster
- **Adapter scope estimate:** ~300–500 LOC (per-run + AI-generation-content-invariant parity discipline per Phase 8d.1)

#### 6. `aftercare_triage`
- **Queue config:** `platform_defaults.py:697`
- **Producer site:** `workflows/aftercare_adapter.py:206` (#4); job_type=`fh_aftercare_7day`; (c) refactor to `funeral_followup_pending` cohort applied
- **Consumer direct-query:** `engine.py:1134` `_dq_aftercare_triage`
- **Cardinality:** per-case (one AgentAnomaly per eligible case)
- **Producer-supplied context:** distinct cohort from accounting anomalies — `customer_communication_task` task_type_key + funeral-director-cohort permission gate
- **Substrate state:** built-operator-facing; producer dual-writes; consumer reads original
- **Substrate-similarity grouping:** AgentAnomaly-shaped per-case (distinct from #1/#2/#3 by cohort + task_type_key)
- **Adapter scope estimate:** ~250–400 LOC

#### 7. `catalog_fetch_triage`
- **Queue config:** `platform_defaults.py:786`
- **Producer site:** `workflows/catalog_fetch_adapter.py:258` (#5)
- **Consumer direct-query:** `engine.py:1320` `_dq_catalog_fetch_triage` reads `UrnCatalogSyncLog` in `publication_state="pending_review"`
- **Cardinality:** per-sync-log (one task per fetch); supersede semantics flip older pending-review rows
- **Producer-supplied context:** product changes preview count
- **Substrate state:** built-operator-facing; producer dual-writes; consumer reads original
- **Substrate-similarity grouping:** per-record-shaped pending-state-column cluster
- **Adapter scope estimate:** ~300–450 LOC (supersede semantics preservation important)

#### 8. `ss_cert_triage`
- **Queue config:** `platform_defaults.py:149`
- **Producer site:** `social_service_certificate_service.py:162` (#2)
- **Consumer direct-query:** `engine.py:664` `_dq_ss_cert_triage` reads `SocialServiceCertificate` joined to `SalesOrder`/`Customer`
- **Cardinality:** per-cert (one task per pending cert)
- **Producer-supplied context:** cert number + sales-order number
- **Substrate state:** built-operator-facing; producer dual-writes; consumer reads original
- **Substrate-similarity grouping:** per-record-shaped (clusters with #7)
- **Adapter scope estimate:** ~250–400 LOC

#### 9. `workflow_review` (`workflow_review_triage` per phasing §3.1 enumeration)
- **Queue config:** `platform_defaults.py:992`
- **Producer site:** `workflow_engine.py:828` (#7)
- **Consumer direct-query:** `engine.py:1378` `_dq_workflow_review` reads `WorkflowReviewItem` in awaiting-decision state
- **Cardinality:** per-review-item (review_focus_id discriminator)
- **Producer-supplied context:** review_focus_id; admin permission cohort fallback (per-Focus-template recipient resolution deferred)
- **Substrate state:** built-operator-facing; producer dual-writes; consumer reads original
- **Substrate-similarity grouping:** per-record cluster with #7/#8 — pre-existing pending-state column on a domain table
- **Adapter scope estimate:** ~300–500 LOC

#### 10. `email_unclassified` (`email_unclassified_triage` per phasing §3.1 enumeration)
- **Queue config:** `platform_defaults.py:1082`
- **Producer site:** `classification/dispatch.py:379` (#8); fires when classification cascade exhausts all 3 tiers (Tier 1 rule → Tier 2 LLM → Tier 3 LLM) without confident routing
- **Consumer direct-query:** `engine.py:1363` `_dq_email_unclassified_triage` reads `WorkflowEmailClassification` audit row
- **Cardinality:** per-classification-audit-row (re-fires per replay attempt as new audit row)
- **Producer-supplied context:** subject (truncated 80ch); cascade-exhausted reason
- **Substrate state:** built-operator-facing; producer dual-writes; consumer reads original
- **Substrate-similarity grouping:** communications-typed adapter (distinct substrate shape — classification cascade, not anomaly/job/cert/record)
- **Adapter scope estimate:** ~300–500 LOC

### B.3 Section B summary

**v2a scope is consumer-side read-path migration, not producer-side adapter construction.** Producer-side adapter work shipped at v1 B2. The remaining work is:

- Migrate `_DIRECT_QUERIES` handlers from reading original-substrate rows to reading task substrate (`task_details` + `vault_items` join)
- Preserve cardinality semantics per queue (per-anomaly / per-customer / per-line / per-job / per-run / per-case / per-sync-log / per-cert / per-review-item / per-classification-audit-row)
- Preserve denormalized display fields (each queue currently denormalizes business-state-specific fields at query time)
- Adjudicate canonical-substrate per name-collision (Section E)
- Determine whether to delete original-substrate query path or preserve as forensic-fallback per Phase 8b operational coexistence canon

**Cumulative B-scope LOC estimate:** ~2,800–4,400 LOC across 10 queues (lower than the phasing doc's ~3,000–5,000 because producer-side already shipped). Within calibration band.

**No `built-but-mis-shaped` findings.** No material-divergence triggers from Section B.

---

## Section C — v2c substrate refinement scope enumeration

### C.1 Five-candidate enumeration from phasing §3.3

#### 1. Escalation routing mode
- **Substrate location:** `backend/app/services/tasks/routing.py` (resolver) + `backend/app/models/task_routing_rule.py` (CHECK constraint extension to `('direct_user','round_robin','escalation_chain')`)
- **Dependencies on v1 substrate:** consumes v1 `task_routing_rule` table + `resolve_routing` resolver entry point; extends three-tier inheritance unchanged
- **Plugin-contract impact:** **none** — escalation_chain is a routing_mode value, not a plugin contract extension; `routing_config` JSONB column at r109 already forward-compat for v2 modes per migration doc
- **Adapter-vs-absorbed adjacency:** purely substrate-internal; no v2a interaction
- **LOC estimate:** ~400–700 LOC (resolver + CHECK constraint extension + tests; chain definition + tick-over logic)

#### 2. Additional workflow nodes (cancel_task / update_task / query_tasks)
- **Substrate location:** `backend/app/services/workflow_engine.py` (action handlers) — existing `create_task` handler at line 1219 is the precedent
- **Dependencies on v1 substrate:** consumes `task_details` + `vault_items` + the routing resolver; service-method-registry pattern per Phase 8b canon
- **Plugin-contract impact:** **none** — workflow nodes are action types in `workflow_engine`, not task-substrate plugin contracts
- **Adapter-vs-absorbed adjacency:** none
- **LOC estimate:** ~600–1,000 LOC (3 handlers × ~150-250 LOC + parity tests per Phase 8b adapter discipline)

#### 3. 6th task type plugin (`scheduled_audit_task` or similar per state doc §4.7 deferred)
- **Substrate location:** `backend/app/services/tasks/plugins/types/scheduled_audit_task.py` (new) joining the existing 5
- **Dependencies on v1 substrate:** consumes the `task_type_behaviors` plugin contract; registration mechanism unchanged
- **Plugin-contract impact:** **none** — plugin contracts are stable; this is a contract consumer instance
- **Adapter-vs-absorbed adjacency:** none
- **LOC estimate:** ~150–300 LOC (one plugin file + tests; per Entry 24 calibration band)

#### 4. Subscriber registry persistent log
- **Substrate location:** new table (likely `task_subscriber_dispatches` or similar); subscriber registry at `subscribers/registry.py` dispatches a log row alongside subscriber invocation
- **Dependencies on v1 substrate:** wraps `_REGISTRY` dispatch loop with append-to-log; consumes 7-event-type vocabulary unchanged
- **Plugin-contract impact:** **none** — subscriber substrate is in `backend/app/services/tasks/subscribers/` not plugin contracts directory; persistent log is internal substrate refinement
- **Adapter-vs-absorbed adjacency:** none
- **LOC estimate:** ~400–600 LOC (table + service layer + replay path + tests); needs new migration (likely r110 per phasing §3.3 note)

#### 5. Task templates via visual editor
- **Substrate location:** new substrate altogether — `backend/app/services/visual_editor/task_templates/` (or similar) + Studio admin UI under `frontend/src/bridgeable-admin/pages/visual-editor/`
- **Dependencies on v1 substrate:** authors create task-creation templates; workflow engine + manual creation paths consume; threads through the `task_creators` plugin contract
- **Plugin-contract impact:** **POSSIBLE** — depending on shape, task templates may introduce a new plugin contract (task templates as a fifth plugin category) OR extend `task_creators` plugin contract with a new instance type. Phase 4 should adjudicate. **Per Entry 13 substrate-transition discipline + this audit's Section C surface, if task templates require plugin contract extension that's consolidation work outside v2c scope** (plugin contracts are v1-locked; promotion is consolidation arc).
- **Adapter-vs-absorbed adjacency:** none direct; some v2a adapter targets (especially scheduled_recurring task type) may benefit from templates if shipped first
- **LOC estimate:** ~1,200–1,800 LOC (substrate + Studio editor + tests); largest candidate; possibly its own sub-arc

### C.2 Additional v2c refinement candidates surfaced at audit

The audit surfaced two candidates not enumerated in phasing §3.3 that should be considered:

#### 6. Dual-write unification candidates (consumer-side migration completion)
This is the natural extension of Section B's finding. v2a closes the consumer-side migration for the 10 enumerated queues. **A v2c-scope follow-on is to retire original-substrate query paths once consumer-side migration is stable.** Specifically: AgentAnomaly's `resolved` flag + `_dq_*` original-substrate query paths in `engine.py` become redundant if v2a's task-substrate read paths fully replace them. Operational coexistence per Phase 8b canon argues for preserving as forensic-fallback; v2c-scope decision should adjudicate retirement timing.

- **Substrate location:** `engine.py` `_DIRECT_QUERIES` registrations + adjacent `_dq_*` functions
- **Dependencies:** requires v2a's read-path migration stable across all 10 queues
- **LOC estimate:** ~300–500 LOC (per-queue cleanup; not net-new substrate)

#### 7. Plugin-field promotion candidates
Per Entry 13 metadata-extension discipline, certain `metadata` JSONB fields have stabilized usage at v1 + v2a and warrant **first-class plugin contract field promotion**. Audit surfaces these candidates:

- `notification_permission_key` — used at all 8 producer sites; stable shape; promotion candidate
- `notification_category` — used at 6/8 producer sites; stable shape; promotion candidate
- `notification_link` — used at 7/8 producer sites; stable shape; promotion candidate
- `notification_source_reference_type` / `notification_source_reference_id` — used at 6/8 producer sites; carries provenance backreference

**Per Entry 13 + Phase 0 audit discipline**, plugin-field promotion **touches the plugin contract surface**. This is **consolidation work, NOT v2c scope** — plugin contracts are v1-locked; field promotion requires plugin contract version bump + consumer migration. Audit surfaces these for operator decision; v2c should NOT ship plugin-field promotion. A separate consolidation arc (v3-era candidate or substrate-cleanup sub-arc) is the canonical home.

### C.3 Section C summary

**v2c refinement candidates:** 5 from phasing §3.3 + 2 surfaced at audit. Of the 7, **6 are v2c-shape** (no plugin contract touch) and **1 is consolidation-shape** (plugin-field promotion at #7). The 6 v2c-shape candidates total ~3,050–4,900 LOC envelope (well within phasing §3.3's ~1,500–2,500 if v2c ships subset only; over-envelope if all 6 ship). **Per phasing §3.3 "selected based on signals; not all ship at v2c if integration surfaces don't need" the sub-arc canonical-shape is select-by-signal, not ship-all-at-once.**

**Material-divergence trigger potential:** if operator wishes to include plugin-field promotion in v2c, that's material divergence — surface and decide. Audit recommendation: defer plugin-field promotion to consolidation arc.

**No `built-but-mis-shaped` findings in Section C (substrate-internal refinement work, no operator-facing UX to mis-shape).**

---

## Section D — Sub-arc decomposition discovery

### D.1 Substrate-shape grouping principle (Entry 30 + Entry 29)

Per Entry 30 (investigation discovers seams; build executes against locked decomposition) + Entry 29 (substrate-extending arcs adjudicate per substrate-shape distinctions). The 10 v2a queues + 6 v2c candidates partition by substrate-shape into the following candidate sub-arcs:

### D.2 Candidate decomposition

#### v2a-α: AgentAnomaly-shaped consumer-read-path cluster (4 queues)
- **Members:** cash_receipts_matching_triage (#1) / ar_collections_triage (#2) / expense_categorization_triage (#3) / aftercare_triage (#6)
- **Shared substrate-shape:** AgentAnomaly producer → task_details with `provenance_kind="anomaly_detection"` (or `workflow_step` for aftercare)
- **Cardinality variance within cluster:** per-anomaly (#1, #3), per-customer fan-out (#2), per-case (#6) — distinct enough to require per-queue test cohorts but shared adapter substrate shape
- **Estimate:** ~1,050–1,650 LOC (4 queues × ~250–400 each)
- **Commit-shape (per Entry 26):** likely single-commit-at-arc-close — adapter shape ships uniformly across the 4; parity tests gate each queue independently but ship together

#### v2a-β: per-record-with-pending-state-column cluster (3 queues)
- **Members:** ss_cert_triage (#8) / catalog_fetch_triage (#7) / safety_program_triage (#5)
- **Shared substrate-shape:** producer writes to a domain table with a pre-existing `status` or `publication_state` enum (`pending_review` / `pending_approval` / `pending`); task is dual-write parallel surface
- **Cardinality:** per-record (per-cert / per-sync-log / per-run)
- **Estimate:** ~850–1,350 LOC (3 queues × ~250–500 each); safety_program upper-bound due to AI-generation-content-invariant parity discipline
- **Commit-shape:** likely multi-commit-within-arc-identity — safety_program AI-parity gate is heavier than ss_cert / catalog_fetch; defensible to ship safety_program in its own commit

#### v2a-γ: per-job/per-review-item cluster (2 queues)
- **Members:** month_end_close_triage (#4) / workflow_review (#9)
- **Shared substrate-shape:** per-job-cardinality (AgentJob.awaiting_approval) and per-review-item-cardinality (WorkflowReviewItem.awaiting); decision-shape rather than anomaly-shape
- **Estimate:** ~600–950 LOC (2 queues × ~300–500 each)
- **Commit-shape:** single-commit-at-arc-close defensible

#### v2a-δ: communications-cascade-typed adapter (1 queue)
- **Members:** email_unclassified (#10)
- **Shared substrate-shape:** distinct from #1–#9 — classification cascade audit row producer; per-classification-audit-row cardinality; replay semantics
- **Estimate:** ~300–500 LOC (1 queue)
- **Commit-shape:** single-commit defensible (small scope, distinct shape)

#### v2c-α: routing + workflow-node refinement sub-arc
- **Members:** Escalation routing mode (#1) + Additional workflow nodes (#2)
- **Shared substrate-shape:** workflow-engine-touching refinements; both extend the routing/workflow-action surface
- **Estimate:** ~1,000–1,700 LOC
- **Commit-shape:** likely multi-commit-within-arc-identity (escalation_chain + each workflow node ship as separable units)

#### v2c-β: 6th task type plugin
- **Members:** scheduled_audit_task (#3)
- **Standalone candidate** — small scope, distinct from other v2c work; could ship as build-only refinement
- **Estimate:** ~150–300 LOC
- **Commit-shape:** single-commit

#### v2c-γ: subscriber persistent log + dual-write unification
- **Members:** Subscriber registry persistent log (#4) + Dual-write unification (#6)
- **Shared substrate-shape:** internal substrate hygiene; both rely on v2a completion to be safe
- **Estimate:** ~700–1,100 LOC (incl. r110 migration)
- **Commit-shape:** single-commit-at-arc-close

#### v2c-δ: Task templates via visual editor (deferred-candidate)
- **Members:** Task templates (#5)
- **Standalone candidate** with potential plugin-contract surface impact (per Section C.1 #5 caveat)
- **Estimate:** ~1,200–1,800 LOC
- **Commit-shape:** likely own sub-arc; possibly defers to consolidation arc if plugin contract impact materializes

### D.3 Sub-arc count + shape rationale

**Total: 7 candidate sub-arcs** (4 v2a + 3 v2c + 1 v2c-δ deferred-candidate).

**Audit-shape signal:** 7 is slightly above the 2–6 anchor range from the audit-shape signals. The 4-v2a / 3-v2c split is shape-grounded (substrate-shape distinctions are real per Section B + C) but signals over-decomposition risk. **Phase 4 phasing recommendation should adjudicate:**

- Option (a): collapse v2a-γ (per-job/per-review-item) into v2a-α (AgentAnomaly cluster) — both consume AgentJob-shape upstream → 3 v2a sub-arcs + 3 v2c = 6 total
- Option (b): collapse v2a-δ (email_unclassified) into v2a-β (per-record) — both per-record cardinality, distinct producer-shape → 3 v2a sub-arcs + 3 v2c = 6 total
- Option (c): preserve 4 v2a sub-arcs; collapse v2c-β into v2c-α (workflow nodes + routing + 6th plugin all engine-adjacent) → 4 v2a + 2 v2c = 6 total
- Option (d): preserve 7 sub-arcs; defend on substrate-shape distinctness per Entry 30; Phase 4 commits to operator-confirm gate per sub-arc

Audit recommends Phase 4 surface options (a–d) for operator decision rather than locking sub-arc shape unilaterally. **Per Entry 31 bounded-decision discipline, decomposition shape is Phase 4 decision, not Phase 0 decision.**

---

## Section E — Name-collision audit per Entry 29

### E.1 Methodology

For each v2a adapter target, audited substrate field names against task substrate field names (task_details + VaultItem). Substrate field surveys conducted via SQLAlchemy model headers at `backend/app/models/*.py`.

### E.2 Per-substrate collision findings

#### AgentAnomaly (members #1/#2/#3/#6)
| AgentAnomaly field | task_details counterpart | Collision shape | Canonical-substrate recommendation |
|--------------------|--------------------------|-----------------|-----------------------------------|
| `severity` (str: CRITICAL/WARNING/INFO) | `priority` (str: low/normal/high/urgent) | semantic overlap, different vocabularies | **Original-substrate authoritative for source-business-state; task carries mapped value in `priority`.** Adapter maps CRITICAL→urgent, WARNING→high, INFO→normal |
| `anomaly_type` (str) | None | task substrate has no anomaly_type | Preserve in metadata as `metadata.anomaly_type` for downstream consumers |
| `resolved` (bool) | `current_state` ∈ action lifecycle | semantic equivalent for "done" | **Task substrate's `current_state="done"` authoritative going forward.** Adapter mirrors during transition window |
| `resolved_by` (FK→users) | `current_state` doesn't carry actor; subscriber log captures | actor attribution | Subscriber log captures actor; AgentAnomaly's `resolved_by` becomes legacy attribution column |
| `resolved_at` (datetime) | `completed_at` on `task_details` | timing of resolution | **Task substrate's `completed_at` authoritative.** Adapter mirrors |
| `description` (text) | `description` (text on `vault_items.description_or_similar`) | direct collision, same field name | **Adjudication needed** — task substrate's description likely authoritative; AgentAnomaly.description carries the producer-side composed message which task substrate inherits at create time |

#### SafetyProgramGeneration (member #5)
| SafetyProgramGeneration field | task_details counterpart | Collision shape | Canonical-substrate recommendation |
|-------------------------------|--------------------------|-----------------|-----------------------------------|
| `status` (str: draft/pending_review/approved/rejected) | `current_state` (str: dual-shape) | **direct enum collision** | **Original-substrate authoritative for source-business-state.** SafetyProgramGeneration.status remains canonical; task substrate's `current_state` mirrors the approval gate (pending_review→assigned, approved→done) per Phase 8d.1 canon |
| `reviewed_by` (FK→users) | None at task_details column level; subscriber log captures | actor attribution | Original substrate keeps |
| `reviewed_at` | `completed_at` | timing | Task substrate's `completed_at` authoritative going forward |
| `generation_status` | None | distinct field (Claude API status) | Preserve in original substrate only |

#### UrnCatalogSyncLog (member #7)
| UrnCatalogSyncLog field | task_details counterpart | Collision shape | Canonical-substrate recommendation |
|-------------------------|--------------------------|-----------------|-----------------------------------|
| `status` (str: implied) | `current_state` | enum collision | Original-substrate authoritative (publication_state enum + supersede semantics) |
| `publication_state` (str: pending_review/published/rejected/superseded) | `current_state` | enum collision | **Original-substrate authoritative.** Supersede semantics flip older pending-review rows; task substrate's `current_state="cancelled"` mirrors `superseded` |

#### SocialServiceCertificate (member #8)
| Cert field | task_details counterpart | Collision shape | Canonical-substrate recommendation |
|------------|--------------------------|-----------------|-----------------------------------|
| `status` (str: pending/approved/rejected) | `current_state` | enum collision | Original-substrate authoritative |
| `approved_by_id` | None | actor attribution | Original substrate keeps |

#### WorkflowReviewItem (member #9)
| WorkflowReviewItem field | task_details counterpart | Collision shape | Canonical-substrate recommendation |
|--------------------------|--------------------------|-----------------|-----------------------------------|
| `decision` (str: approve/reject/edit_and_approve) | `resolution_outcome` (NEW on task_details per state doc §5.1) | semantic equivalent | **Task substrate's `resolution_outcome` authoritative going forward.** Adapter mirrors during transition |
| `review_focus_id` | `metadata.review_focus_id` | no collision; producer carries forward | Preserve in metadata |

#### WorkflowEmailClassification (member #10)
No significant collisions. Audit row is immutable; task substrate carries its own lifecycle on top.

### E.3 Canonical-substrate adjudication summary

**Pattern:** for each v2a queue, **original-substrate stays authoritative for source-business-state semantics**; **task substrate becomes authoritative for task-lifecycle semantics (assignment, completion timing, lifecycle state).** Adapter mirrors during transition window per Entry 13 dual-write discipline.

**No collision warrants canonical-substrate decision outside v2a scope** — all collisions adjudicable by canonical adapter pattern. **No material-divergence trigger fires from Section E.**

**One latent risk:** `description` field on AgentAnomaly vs `description` on VaultItem (task row). Same field name, semantically overlap. Audit recommends Phase 4 surface this for operator review — likely producer composes task description from anomaly description verbatim at create time, but ongoing edits should be adjudicated.

---

## Section F — Cross-arc dependency audit

### F.1 v2a depends on Section A v1 substrate operational state

**Verified.** Section A confirms v1 substrate operational across all 8 producer sites + 6 subscribers + 5 plugins + Pulse/briefings/Focus integration. v2a's consumer-side read-path migration depends on:

- `task_details` schema stable (✓ — r107 shipped)
- `create_task_with_provenance` API stable (✓ — 8 producer sites use it)
- Provenance vocabulary stable (✓ — 12-value PROVENANCE_KINDS tuple frozen at v1)
- Subscriber registry stable (✓ — 6 subscribers operational, sync dispatch)
- Routing resolver stable (✓ — direct_user + round_robin at r109)

No v1 substrate gaps that v2a work would expose. v2a can dispatch against current v1 substrate without v1 supplement.

### F.2 v2c absorbed candidates dependent on v2a adapter scope

Per Section C.2 candidate #6 (dual-write unification): explicit v2c → v2a dependency. **Dual-write unification CANNOT ship until v2a's consumer-side read-path migration is stable across all 10 queues.** If v2c-γ (subscriber log + dual-write unification per Section D.2) ships before v2a completes, dual-write retirement is premature.

Per Section C.1 candidate #5 (task templates): potential v2a-template-consumer dependency. If task templates allow scheduled_recurring_task or anomaly_resolution_task patterns to be authored via Studio, the templates substrate consumes adapter-substrate output. v2c-δ should defer until v2a stable OR scope template substrate to non-adapter task types only.

### F.3 Q-B1 boundary preservation per Entry 3

**Q-B1 (boot-adapter-takes-client substrate decision) is admin-realm Studio-builder boot adapter shape** per the deferral-tracking meta-pattern. Audit verifies:

- No v2a queue substrate touches admin-realm Studio-builder boot
- No v2c refinement touches admin-realm Studio-builder boot (task templates via visual editor MIGHT touch Studio admin shell per Section C.1 candidate #5, but the boot adapter substrate is distinct from task templates substrate)
- v2a + v2c operate at tenant-realm task substrate layer; Q-B1 operates at admin-realm Studio-builder boot layer

**Q-B1 boundary preserved.** v2a+v2c work does NOT lock or resolve Q-B1 substrate decision. Q-B1 carries forward to the September-decision arc per Entry 3.

### F.4 Phase B (Workflow Builder rebuild) + Phase C (Document Builder rebuild) boundary

**Workflow Builder substrate:** lives at `backend/app/services/workflow_templates/` + `frontend/src/lib/visual-editor/workflows/` + admin Studio editor at `/admin/visual-editor/workflows`. v2c candidate #2 (additional workflow nodes) touches `workflow_engine.py` action handlers — NOT Workflow Builder substrate. The action-handler-registry is the runtime substrate; Workflow Builder is the authoring substrate. **Boundary preserved.**

**Document Builder substrate:** lives at `backend/app/services/documents/block_*` + admin Studio editor. v2a+v2c work does not touch document substrate. **Boundary preserved.**

**No cross-arc dependency between v2a+v2c and Phase B/C substrate-rebuild arcs.**

---

## Audit-shape notes

### Material-divergence triggers fired

**None.**

Section A surfaced no regressions. Section B surfaced no `built-but-mis-shaped` queues but did surface a substrate-state framing reframe (consumer-side read-path migration vs producer-side adapter construction) — this is **scope refinement, not material divergence**. The reframe is fully consistent with Entry 14 substrate-transition discipline.

Section C surfaced 2 additional candidates beyond phasing §3.3's 5 (dual-write unification + plugin-field promotion). Plugin-field promotion flagged as out-of-scope (consolidation work). No material-divergence trigger.

Section D surfaced 7 candidate sub-arcs against the 2–6 anchor range — over-decomposition risk surfaced for Phase 4 adjudication, but **Phase 0 does not lock decomposition shape** (Entry 31).

Section E surfaced one latent risk (`description` field collision) for operator review at Phase 4 gate but no canonical-substrate decision outside v2a scope.

Section F surfaced no boundary violations.

### Audit-shape signals

- Section B count: **10 queues (matches anchor exactly)**
- Section B 4-state distribution: 10 built-operator-facing / 0 built-dormant / 0 built-but-mis-shaped / 0 missing
- Section C count: **6 v2c-shape + 1 consolidation-shape (plugin-field promotion)** — within anchor range
- Section D sub-arc count: **7** (slightly above 2–6 anchor; surfaced for Phase 4)
- Section E collision count: **6 collision tables across 6 substrate types** — all adjudicable inside v2a scope
- Section F: **all boundaries preserved**

### Operator decision items surfaced

1. **Section D sub-arc decomposition:** 7 candidates vs Phase 4 collapse options (a/b/c/d) — operator decides at Phase 4 review
2. **Section C candidate #7 (plugin-field promotion):** scope adjudication — audit recommends defer to consolidation arc; operator confirms or escalates
3. **Section C candidate #5 (task templates):** plugin contract impact unknown until Phase 4 investigation — operator confirms Phase 4 scope
4. **Section E `description` collision:** AgentAnomaly.description vs VaultItem.description name-overlap — operator confirms canonical-substrate at Phase 4
5. **v2a operational coexistence retirement timing:** per Phase 8b canon, original-substrate query paths persist as forensic-fallback during v2a transition window; retirement timing is v2c-γ scope but needs operator confirmation

### Cumulative LOC envelope estimate

- **v2a total:** ~2,800–4,400 LOC (4 sub-arc clusters; consumer-side read-path migration; below phasing §3.1's ~3,000–5,000 because producer-side already shipped at v1 B2)
- **v2c total:** ~3,050–4,900 LOC if all 6 v2c-shape candidates ship; ~1,500–2,500 LOC if select-by-signal subset (per phasing §3.3 canonical-shape)
- **Combined v2a+v2c:** ~4,300–9,300 LOC if all ship; ~4,300–6,900 LOC if v2c select-by-signal

Per Entry 24 LOC calibration: combined envelope **exceeds 6,000 LOC single-phase trigger** if all v2c ships; **stays under 6,000 if v2c select-by-signal**. Phase 4 phasing recommendation should adjudicate v2c subset-vs-full per signal patterns at §5 of phasing doc.

---

## Next-phase handoff

Phase 4 phasing recommendation dispatches against Phase 0 audit findings + operator confirmation. Phase 4 deliverable at `docs/investigations/task_substrate_v2a_v2c_phasing.md` per Entry 27 8-section structure (substrate phase final-lock / integration phase final-lock / sub-arc grouping / arc shape / upgrade signals / cross-version / honest cost / open questions).

**Open questions for Phase 4 to resolve:**

1. Sub-arc decomposition shape (Section D options a/b/c/d)
2. v2c subset (which 1–6 candidates ship) + signal patterns triggering each
3. v2a operational coexistence retirement timing + canonical-substrate cleanup window
4. Description-field collision adjudication (Section E latent risk)
5. Task templates plugin contract impact (Section C #5)
6. Per-sub-arc commit-shape (single-commit-at-arc-close vs multi-commit-within-arc-identity per Entry 26)
7. v2a investigation-first vs build-only per phasing §3.5 (phasing recommends investigation-first; Phase 4 confirms or revises)

**C42 boot-adapter shape carries forward** to September-decision arc per Entry 3 deferral-tracking meta-pattern; **v2a+v2c work does NOT lock Q-B1 substrate decision.**

**Phase 0 bounded decision closed.** Audit deliverable shipped at named path. Phase 4 awaits operator review of Phase 0 + dispatch.
