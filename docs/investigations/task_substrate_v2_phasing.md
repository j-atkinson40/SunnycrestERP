# Task Substrate v2 — Phase 4 Phasing Recommendation

> **Document purpose.** Closes the bounded decision: *"How does the locked task substrate architecture (per state doc §5) sequence into shippable arcs (per state doc §6 broad shape), with operator-observable upgrade signals between phases?"*
>
> Phase 4 is decision-shaped against locked architecture. Phase 3 produced the substantive design (~8,980 LOC v1 surface; thirteen sections; schema + lifecycle + plugins + integration + coexistence + customer-facing forward-compat). Phase 4 does not relitigate that design; it sequences shippable arcs against it and specifies the upgrade signals between phases. Phase 5 v1 build prompt dispatches against Phase 4 + state doc + current code state.
>
> **Authority basis.** Every Phase 4 decision cites a numbered state doc section. Architecture is locked per state doc §5; sequence broad shape is locked per state doc §6; operator locks are enumerated in state doc §4.7. Phase 4 refines (does not override) within those locks.
>
> **Discipline.** Operator-observable workflow signals between phases — not architecture-observable thresholds (LOC accumulated, time elapsed, count remaining, engineer signal). The discipline was canonical-locked at v1 investigation close (state doc §4.1) and held across (c)'s ship + v2 investigation's reframing; this Phase 4 honors it.
>
> **Date:** May 25, 2026. **HEAD:** bc7c4ba (state doc commit). **Methodology:** State doc §5 (locked architecture) + state doc §6 (locked sequence broad shape) + state doc §4.7 (Phase 3 → Phase 4 operator decisions) cited per Phase 4 section; production code anchors (`backend/app/models/task.py`, `backend/app/services/task_service.py`, `backend/app/services/pulse/personal_layer_service.py:87-168`) verified current; no code or canon doc edits this phase.

---

## §1. v1.0 substrate phase final-lock

**Scope basis:** state doc §6 v1.0 scope; state doc §5.7 v1.0 substrate phase enumeration; state doc §4.7 operator locks (substrate-clean / net-new additive / no existing surface changes / r107 + backfill same-commit at v1.0 close / five task type plugins / two routing modes locked but routing implementation defers to v1.5).

### 1.1 Exact deliverables

v1.0 ships substrate that is **net-new additive** — zero existing-surface behavior changes. Eight deliverables:

1. **Schema extension.** VaultItem `item_type` enum gains 12th value `'task'` (per state doc §5.1; Phase 3 §1; operator Q1 lock at state doc §4.6). New `task_details` join table 1:1 with VaultItem rows of `item_type='task'`. Column inventory follows Phase 3 §1: `assignee_realm` / `assignee_user_id` / `assignee_portal_user_id` (forward-compat per state doc §5.9), `lifecycle_shape` enum (action / reminder per state doc §5.2), provenance polymorphic FK (12 `provenance_kind` values per state doc §5.3), visibility enum (5 values per state doc §5.5), standard task fields (priority, due_date, due_datetime, status, assigned_at, completed_at, resolution_outcome, suppression_key). FK CASCADE on company_id; SET NULL on user FKs. Six indexes specified at Phase 5 build-prompt time against current code.

2. **Alembic migration r107 + backfill script.** Single commit, same-commit ship per (c) build arc pattern at state doc §2.4; idempotent Option A per Phase 6 / 8b / 8d.1 / R-6.1a / R-6.2a canon. r107 creates `task_details` table + adds `task` to VaultItem `item_type` enum check constraint + adds composite partial-unique index `(provenance_kind, provenance_ref, event_kind)`. Backfill walks existing 138-row `tasks` table (current code state; will re-verify at Phase 5), creates corresponding VaultItem row per existing Task, populates task_details per Task fields, maps existing 5-state lifecycle (`open → in_progress → blocked → done | cancelled`) to action-shape per state doc §5.2 backward-compat mapping. ENVIRONMENT=production refusal guard per (c) backfill canon.

3. **Dual lifecycle state machine.** Action shape (state doc §5.2 transition table A) + reminder shape (state doc §5.2 transition table B) implemented as service-layer transition validators. Reminder shape covers Q5 fold per state doc §4.6: reminder-typed VaultItems map to `item_type='task'` + `lifecycle_shape='reminder'`. Existing `reminder` enum value in VaultItem.item_type stays per BRIDGEABLE_MASTER §3.24 canon (deferred-not-implemented; doesn't conflict with task substrate). Backward-compat mapping for existing `tasks` content: legacy 5-state preserved as action-shape variant; resolution_outcome captures completion semantics.

4. **Subscriber registry substrate.** Per state doc §5.7 v1.0 ("subscriber registry / 7 event types / sync-in-v1 / idempotency per subscriber") + Phase 3 §13. Event types: `task_created`, `task_assigned`, `task_status_changed`, `task_completed`, `task_blocked`, `task_unblocked`, `task_cancelled`. Six v1 subscribers: notification dispatch (replaces (c)'s direct dispatch path in v1.5; v1.0 ships the substrate without flipping (c)), audit log writer, idempotency key recorder, suppression-key checker, briefings invalidator (briefings consume in v1.5), Pulse Personal invalidator (wires in v1.5). Sync execution v1.0 per state doc §6; persistent log defers to v2 per state doc §5.7 + §6.

5. **Three plugin category contracts + registration mechanism.** Per state doc §5.6 + Phase 3 §6/7/8 + operator Q6 lock at state doc §4.6. Categories: **task creators** (workflow steps, Intelligence observations, communications, shelf parking, manual creation, future triage queue adapters), **task surfaces** (list / detail / creation / Pulse / briefings / future surfaces), **task type behaviors** (5 v1 plugins per state doc §4.7). Registration mechanism follows existing Bridgeable Tier R1 in-memory plugin pattern (PLUGIN_CONTRACTS.md §"Intake adapters" + similar precedents). Contracts ship as Python Protocols with input / output / guarantees / failure modes / registration shape documented inline.

6. **Five task type behavior plugins.** Per state doc §4.7: `generic_task` (catch-all manual), `review_approval_task` (covers approval-gate cohort), `scheduled_recurring_task` (accounting recurring per May 21-22), `customer_communication_task` (communications cascade — wired in v1.5), `anomaly_resolution_task` (AgentAnomaly producer sites — wired in v1.5). Each plugin registers lifecycle behaviors, surface defaults, routing defaults. Plugin code ships v1.0; activation across producer sites ships v1.5.

7. **Task service layer + Task façade for backward-compat.** Per state doc §5.1 closing paragraph: "consumers query through service-layer + Task façade pattern that abstracts table layout. The 8 existing Task consumers continue working without rewrite." The 8 consumers per Phase 2 verification (state doc §2.5): `_dq_task_triage`, NL creation extractor, Peek builder, route handlers (`/api/v1/tasks/*`), task_service callers (production code), `_build_tasks_item` stub (deferred but present at `pulse/personal_layer_service.py:87-168`), `task_assigned` notification category producer (`task_service.create_task` at `task_service.py:164` per state doc §2.4), Triage action handlers. Façade preserves `Task` ORM-shape public API; internal implementation reads/writes VaultItem + task_details.

8. **v1.0 internal test cohort.** Schema migration tests + backfill regression (verifies existing tasks rows round-trip cleanly), façade compat tests per consumer (8 consumers × ~3-5 assertions = ~25-40 tests), subscriber registry unit tests + idempotency tests, plugin contract unit tests (5 plugins × ~3-5 = ~15-25 tests), lifecycle transition tests (action + reminder state machines), service-layer integration tests. **Estimated ~150-200 tests total.**

### 1.2 Acceptance criteria for v1.0 internal close

v1.0 closes when:

- r107 migration applies cleanly on staging (synthetic fresh-tenant + Sunnycrest data shape verified)
- Backfill catches every row in the existing `tasks` table; spot-check verifies 1:1 VaultItem creation; pre/post backfill query results identical via façade
- All 8 existing Task consumers exercised against staging (Triage workspace UI navigation, NL extractor demo creation, Peek hover on a task entity, route handler API exercise via curl, task_service callers via test suite, `_build_tasks_item` returns same `None` as before — wiring is v1.5, not v1.0)
- Synthetic scenario: create new task via service layer → VaultItem + task_details rows created 1:1 → task_triage queue picks it up → existing `task_assigned` notification fires (unchanged path; (c) refactor is v1.5)
- Real-data scenario: every pre-existing row in `tasks` queryable through new façade returns identical result pre/post backfill
- Zero existing-surface behavior changes verified via full regression test cohort (existing tests green; new tests green)
- Subscriber registry fires 7 event types correctly; idempotency composite key prevents duplicate dispatches under retry
- Five task type plugins register and resolve correctly; lifecycle transitions per plugin honored

### 1.3 Operator-confirm gate before v1.5 dispatches

Per state doc §4.7 operator lock: "Single v1 arc with two internal phases (v1.0 substrate + v1.5 integration) and explicit operator-confirm gate between phases."

What operator validates at the v1.0 → v1.5 inter-phase review:

- v1.0 acceptance criteria above all met (deploy + spot-check on staging)
- Substrate validates against staging use with no unexpected friction
- No surfaced gotchas at the façade / consumer / migration layer that would invalidate the v1.5 integration design
- Optionally: spot-check one synthetic integration scenario (e.g. manually invoke notification subscriber against a created task; verify subscriber registry's path matches what (c) refactor needs)

If gate passes: v1.5 dispatches as part of same arc, single internal phase transition (no arc-close + new-arc-open round-trip).

If gate fails or surfaces material divergence: stop v1 arc, surface findings to operator, decide whether to extend v1.0 or alter v1.5 scope.

### 1.4 LOC envelope

~5,500 LOC ±15% = **4,675-6,325 LOC** per Phase 3 calibration band (state doc §6 v1.0 ~5,500 LOC).

Within Phase 0 §10 calibration trigger threshold (which fires at >6,000 single-phase). The split that v1.0 / v1.5 produces from the original ~8,980 Phase 3 surface puts v1.0 below the trigger.

### 1.5 Test cohort

**~150-200 tests** per §1.1 deliverable 8.

### 1.6 Migration head target

**r107** per state doc §4.7 lock. Single migration; same-commit with backfill script per (c) build arc canon.

### 1.7 Dependencies on current code state

Files **touched** at v1.0 (new code added or schema extended):

- `backend/alembic/versions/r107_task_substrate.py` (new migration)
- `backend/scripts/seed_task_substrate_backfill.py` (new backfill)
- `backend/app/models/vault_item.py` (extend `item_type` enum to include `'task'`)
- `backend/app/models/task_details.py` (new model)
- `backend/app/services/task_service.py` (extend for façade — does not remove existing public API)
- `backend/app/services/tasks/` (new package — substrate, subscriber registry, plugin contracts, 5 task type plugins)
- `backend/app/services/tasks/lifecycle.py`, `subscribers.py`, `creators.py`, `surfaces.py`, `behaviors.py`, `registry.py`
- `backend/app/services/tasks/plugins/*.py` (5 plugin files)
- `backend/app/models/task.py` (extend with façade properties; preserve existing public API)
- New test files under `backend/tests/tasks/` + migration test under `backend/tests/migrations/`

Files **left alone** at v1.0 (zero behavior change):

- `backend/app/services/notification_service.py:155` (notify_users_with_permission stays unchanged; (c) helper preserved as-is; v1.5 changes call sites only)
- 8 (c) producer sites at canonical state-transition points (per state doc §2.4): `task_service.py:164`, `social_service_certificate_service.py:160`, `base_agent.py:103`, `aftercare_adapter.py:204`, `catalog_fetch_adapter.py:256`, `safety_program_generation_service.py:177`, `workflow_engine.py:812`, `classification/dispatch.py:377` — all unchanged in v1.0
- `backend/app/services/pulse/personal_layer_service.py:87-168` (_build_tasks_item stub stays returning None; wiring is v1.5)
- `backend/app/services/briefings/*` (briefings consumption is v1.5)
- `backend/app/services/triage/platform_defaults.py` (`task_triage` queue unchanged; reads through façade in v1.0 because backfill creates VaultItem 1:1)
- All 10 non-task triage queues (defer to v2 per state doc §4.6 Q3)
- VaultItem schema beyond enum extension (no new columns on VaultItem itself; task-specific concerns live in task_details per state doc §5.1)
- All other tables (10+ table changes deferred via state doc §5.8 coexistence dispositions to v2 adapters)

### 1.8 Honest scope-protection note

v1.0 is genuinely net-new additive. The five task type plugins register substrate but don't activate against producer sites; activation is v1.5. The subscriber registry fires correctly but the (c) notification subscriber's flip from "direct producer dispatch" to "task-event-driven dispatch" is v1.5. The façade preserves existing public API; consumers see no shape change.

**If v1.0 finds itself wanting to wire one consumer in (e.g. "let's also wire `_build_tasks_item` since it's right there"): defer to v1.5.** The two-phase discipline exists to validate substrate before integration. Wiring early couples substrate validation with integration validation; if a bug surfaces, it's harder to localize.

---

## §2. v1.5 integration phase final-lock

**Scope basis:** state doc §5.7 v1.5 integration phase enumeration; state doc §4.7 operator locks (routing implementation v1.5; visibility enforcement v1.5; 5 task type plugin activation v1.5; (c) refactor v1.5; 3 workflow nodes v1.5).

### 2.1 Exact integration list (8 items)

1. **Pulse `_build_tasks_item` wire.** At `backend/app/services/pulse/personal_layer_service.py:87-168` per state doc §5.7 v1.5 enumeration. The scaffolded query logic preserved in the stub function (lines 115-168) goes back in force; `return None` at line 111 removed. Query shape adjusts to post-Q1 façade pattern: read through Task façade (which internally joins VaultItem + task_details), preserve tenant isolation (`Task.company_id == user.company_id`), preserve assignee filter, preserve status filter ([open, in_progress, blocked]), preserve priority + due_date ordering. ~50-80 LOC of net change (mostly un-commenting + minor query adjustment). Composition engine's IntelligenceStream registration on dispatch side gets matched. Adds the third v1 consumer of substrate after task_triage + Triage workspace.

2. **Briefings task-substrate consumption.** Per state doc §5.7 v1.5 + Phase 3 §9 ("briefings 3 new helpers"). Three helpers: `pull_tasks_needing_attention_this_week(company_id, user_id)` (canonical "what needs attention" source), `pull_tasks_resolved_recently(company_id, user_id, since)` ("what got resolved"), `pull_tasks_upcoming_deadlines(company_id, user_id, days_ahead)` ("what's coming up"). Each returns task list shape consumable by existing briefings template substrate. Replaces ad-hoc per-domain "what needs attention" queries with task-substrate-canonical reads. **Briefings prompt template additions deferred to canon-update arc**; v1.5 ships helpers + invocation from current briefings substrate; prompt-template wording stays current shape.

3. **(c) refactor of 8 producer sites.** Per state doc §4.5 Revised Lock 1 + state doc §4.7 operator lock. Refactor pattern per site: producer code currently calls `notify_users_with_permission(...)` directly; post-refactor producer code calls `task_service.create_task(...)`; task-creation event fires from task lifecycle; notification subscriber in subscriber registry catches event and calls `notify_users_with_permission(...)` — same downstream function, different upstream invocation path.

   Per-site map (state doc §2.4 + Phase 3 §9 lock):

   | Site | Current dispatch | v1.5 task type / provenance_kind / category |
   |------|------------------|----------------------------------------------|
   | `task_service.py:164` | `task_assigned` direct fire | (no refactor — already task creation; just ensure subscriber dispatches `task_assigned`) |
   | `social_service_certificate_service.py:160` | `ss_cert_pending` direct fire | `review_approval_task` / `anomaly_detection` / `ss_cert_pending` |
   | `base_agent.py:103` | `agent_anomaly_pending` direct fire (3 producers + month_end_close) | `anomaly_resolution_task` / `anomaly_detection` / `agent_anomaly_pending` |
   | `aftercare_adapter.py:204` | `funeral_followup_pending` direct fire | `customer_communication_task` / `scheduled_recurring` / `funeral_followup_pending` |
   | `catalog_fetch_adapter.py:256` | `catalog_fetch_pending` direct fire | `review_approval_task` / `integration_event` / `catalog_fetch_pending` |
   | `safety_program_generation_service.py:177` | `safety_program_pending` direct fire | `review_approval_task` / `scheduled_recurring` / `safety_program_pending` |
   | `workflow_engine.py:812` | `workflow_review_pending` direct fire | `review_approval_task` / `workflow_step` / `workflow_review_pending` |
   | `classification/dispatch.py:377` | `intake_classification_pending` direct fire | `review_approval_task` / `communication_inbound` / `intake_classification_pending` |

   ~250-300 LOC total per state doc §4.5 Revised Lock 1 verification (8 producer sites × ~15-20 LOC each + subscriber-side dispatch wiring).

4. **3 workflow node types.** Per state doc §4.7 operator lock + Phase 3 §9. `create_task` (workflow step creates a task and continues), `wait_for_task_completion` (workflow step pauses until task transitions to `done` or `cancelled`), `route_on_task_outcome` (workflow step branches based on task's `resolution_outcome`). Each registers against workflow plugin pattern at `backend/app/services/workflows/` per existing canonical node-type registration (see existing nodes like `send_email`, `generation_focus_invocation`, etc.).

5. **Focus extension column.** Per state doc §5.7 v1.5 + Phase 3 §9. New `task_id` nullable FK on `focus_sessions` (or equivalent surface — verify at Phase 5 build-prompt time against current Focus substrate). When a Focus session is opened from a task surface (e.g. clicking "Open in Focus" on a task detail page), the linkage persists. Enables capability row 8 ("Focus integration — tasks say 'decide this'; Focus is where decision gets made; entering Focus from task") from state doc §2.5 Phase 1 enumeration.

6. **Intelligence task-creation refactor.** Per state doc §1 claim 10 + state doc §5.7 v1.5. Current Intelligence observation surfaces (`backend/app/services/intelligence/*`) produce notifications + ephemeral surfaces; refactor produces tasks (provenance_kind `intelligence_observation`, task_type `generic_task` initially with potential for specialized type in v2). Specific Intelligence sites: TBD at Phase 5 build-prompt time against current code; likely 3-5 producer sites.

7. **Communications cascade task-creation.** Per state doc §1 claim 9 + state doc §5.7 v1.5. ~5 of 18 Phase 1 capability rows touched per state doc §2.5 closing observations. Incoming email / SMS / inbound communication produces task (provenance_kind `communication_inbound`, task_type `customer_communication_task`). Refactors existing `classification/dispatch.py:377` site's downstream behavior — currently fires notification; post-refactor also creates task. May overlap with item 3's (c) refactor at that site; design at Phase 5 build-prompt time resolves.

8. **Visibility enforcement.** Per state doc §5.5 + §5.7 v1.5 + operator Q4 lock at state doc §4.6. v1 enforces operator-only at query-filter layer: task service queries filter by `visibility IN ('operator_internal', 'operator_assigned')` (visibility enum specifics resolve at Phase 5). Portal-shape (`visibility IN ('portal_family', 'portal_contractor', 'portal_partner')`) schema supports but query layer does not surface; v2 / v3 add portal query path. v1 portal users cannot see tasks even via direct API; rejection at deps layer.

**Plus two routing modes activated.** Per state doc §4.7 + §5.4. `direct_user` (manual assignment, fixed-recipient) and `round_robin` (distributes across role members). `task_routing_rules` table populated with platform-default routing for each task type; vertical / tenant tier rows add per Phase 3 §10 shared resolver pattern (resolver code ships v1.0; rules data ships v1.5 alongside producer-site activation).

### 2.2 Acceptance criteria for v1.5 close (= v1 close)

- All 8 producer sites refactored to task-event-driven dispatch; (c) parity regression green
- Pulse Personal layer renders task list for current user (the stub no longer returns None; production users see assigned tasks on their Pulse)
- Briefings consume task substrate as canonical "what needs attention" source for the 3 new helpers
- 3 workflow node types operational; can author a workflow definition using all three; round-trip test covers create_task → wait_for_task_completion → route_on_task_outcome
- Focus extension column populated when Focus opens from task surface; task→Focus relationship queryable
- Intelligence observations produce tasks at refactored sites
- Communications cascade creates tasks on inbound communication
- Visibility enforcement: operator users see tasks; portal users do not (rejection at API + filter at query layer)
- 2 routing modes active: direct_user assignment works; round_robin distributes load
- All v1.0 substrate tests + v1.5 integration tests green
- Full regression cohort (existing + new) green

### 2.3 Operational coexistence story

Per state doc §5.8 dispositions. What changes vs. doesn't:

**What changes operationally at v1.5 close:**
- 8 (c) producer sites: notification path now goes producer → task creation → subscriber → notify_users_with_permission. Operationally equivalent — same notifications fire to same cohorts at same triggering moments. Parity regression verifies. Difference is task is now persisted and surfaceable.
- Pulse Personal layer: users see assigned-task list where they previously saw nothing (stub returned None).
- Briefings: "what needs attention this week" / "what got resolved" / "what's coming up" sections pull from task substrate; per-domain ad-hoc queries that the briefings template used to invoke get retired or supplemented.
- Workflow authoring: workflow definitions can use 3 new node types.
- Intelligence: observations persist as tasks; user can navigate to a task created by Intelligence and act on it.
- Inbound communications: a task is created per inbound communication routed through the classification cascade.

**What stays unchanged at v1.5 close (deferred to v2):**
- V-1d notification dispatch helpers (`notify_tenant_admins`, `notify_users_with_permission`) themselves: signatures unchanged; only call sites shift.
- 10 non-task triage queues continue working via existing (c) pattern (folding to v2 per state doc §4.6 Q3). AgentAnomaly + SafetyProgramGeneration + WorkflowRun awaiting-state surfaces continue surfacing through current triage substrate; in v2, adapters create tasks from their state transitions.
- Customer-facing portals: no task surfaces visible to PortalUser identities in v1; v2 family portal, v3 contractor portal.
- Task templates / authored task creators: defer to v2 per state doc §4.6 Q8.
- 6th task type plugin (e.g. `scheduled_audit_task`): defer to v2 per state doc §4.7 if integration surfaces need.

### 2.4 LOC envelope

~3,500 LOC ±15% = **2,975-4,025 LOC** per state doc §6.

### 2.5 Test cohort

**~100-150 tests** (integration-heavy). Producer-site refactor parity regression (~40 tests across 8 sites); Pulse render integration tests (~10); briefings consumption tests (~15); workflow node types integration tests (~20); Focus extension tests (~5); Intelligence integration tests (~10); communications cascade integration tests (~10); visibility enforcement (~10); routing modes (~10); end-to-end task-creation-to-completion happy path (~5).

### 2.6 v1 commit pattern

**Single arc; internal phase gate (operator-confirm); single commit at v1.5 close.** Per Bridgeable build-arc canon (matches (c) build arc commit pattern at `868fec3` per state doc §2.4: single arc, multiple phases internally, single commit + push at arc close).

The single-commit-at-arc-close pattern means v1.0 ships to staging via internal phase ("dispatched" to validation) without git commit; commit lands when v1.5 closes. Operator-confirm gate at v1.0 → v1.5 is a conversation-level gate, not a git-history gate.

Practical implication: if material divergence surfaces at v1.0 → v1.5 gate, stop the arc, write-up findings, surface to operator. No half-committed substrate.

---

## §3. v2 scope shape + sub-arc grouping

**Scope basis:** state doc §6 v2 scope enumeration; state doc §4.6 Q3 + Q4 + Q8 operator locks; state doc §5.7 deferred items list.

v2 is plausibly **2-3 sub-arcs grouped under v2 banner** per state doc §6. Phase 4 recommends three sub-arcs (v2a / v2b / v2c) with explicit independence + ordering-by-signal.

### 3.1 v2a — 10 non-task triage queue adapters

**LOC envelope:** ~3,000-5,000 LOC. **Approach:** adapter-substrate pattern.

10 non-task triage queues + their producer-side state-transitions absorb into task substrate via adapter pattern. Adapter observes existing substrate's state transitions (e.g. AgentAnomaly creation, SafetyProgramGeneration → pending_review transition) and creates a corresponding task; original substrate row stays as authoritative business state; task is the visibility surface. Consumer surfaces (Pulse, briefings, Triage workspace) start reading through task substrate as canonical surface; original substrate continues for business-state operations.

Per-queue scope: ~300-500 LOC for state-transition observation + task-creation hook + task type plugin if needed. The 10 queues per state doc §5.8:

1. `cash_receipts_matching_triage` — AgentAnomaly producer
2. `ar_collections_triage` — AgentAnomaly producer
3. `expense_categorization_triage` — AgentAnomaly producer
4. `month_end_close_triage` — AgentJob awaiting_approval (per-job cardinality)
5. `safety_program_triage` — SafetyProgramGeneration (per-run cardinality)
6. `aftercare_triage` — AgentAnomaly producer (already (c)'d to `funeral_followup_pending`)
7. `catalog_fetch_triage` — UrnCatalogSyncLog pending-review
8. `ss_cert_triage` — SocialServiceCertificate pending
9. `workflow_review_triage` — WorkflowRun awaiting-state
10. `email_unclassified_triage` (or similar inbound communication queue) — classification cascade

Note: `task_triage` queue itself is v1 (already covered as the canonical task surface).

**Adapter-substrate vs absorbed-into-task-substrate decision:** Phase 4 recommends **adapter-substrate** for v2 to preserve operational continuity. Existing AgentAnomaly + SafetyProgramGeneration + WorkflowRun + UrnCatalogSyncLog + SocialServiceCertificate rows stay as business state; tasks are visibility/operations layer. Absorbed-into-task-substrate (refactor each substrate to be task-driven internally) would require deeper refactor of business-state semantics in each substrate; defer to v3+ consolidation arc if operator-validated.

Likely needs migration r108 (per-adapter denormalized FK columns to tasks; partial; specific shape resolves at v2a investigation time).

### 3.2 v2b — Family portal task surfaces + portal visibility

**LOC envelope:** ~1,500-2,500 LOC. **Approach:** activate portal-shape visibility query path; build family-shape task type plugins + surfaces; magic-link consent UX where applicable.

Per state doc §4.6 Q4 + §5.9 + state doc §6 v2 enumeration. Family portal currently exists at `/portal/:tenantSlug/personalization-studio/family-approval/:token` (PortalUser identity + magic-link auth precedent). v2b extends portal surface registrations to render task lists scoped by visibility filter, render task detail pages, render family-shape task creation forms (where the family acts as creator — e.g. "select photos for obituary" completion).

Sub-deliverables:
- Activate portal-shape visibility query path (was deferred at v1.5; portal users now see tasks where visibility matches their portal kind)
- Family-shape task type plugins (specific types TBD at v2b investigation; likely `family_decision_task`, `family_information_collection_task`, `family_approval_task`)
- Family-portal-specific surface registrations (list, detail, completion forms)
- Magic-link consent UX for task surfaces (extends existing magic-link pattern from family-approval surface)
- PortalUser identity visibility enforcement at query + API layer
- Likely needs migration r109 (portal-task-related schema; specific shape resolves at v2b investigation)

**Independence:** v2b independent of v2a; can ship before or after v2a depending on signal ordering.

### 3.3 v2c — Substrate refinements

**LOC envelope:** ~1,500-2,500 LOC. **Approach:** scoped substrate-layer additions surfaced by v1 / v2a / v2b integration needs.

Sub-deliverables (selected based on signals; not all ship at v2c if integration surfaces don't need):
- **Escalation routing mode.** `escalation_chain` routing rule type per state doc §5.4 (deferred from v1 per §4.7). Task that goes overdue without resolution escalates to next role in chain.
- **Additional workflow nodes** if integration surfaces need: `cancel_task`, `update_task`, `query_tasks` per state doc §4.7 deferred list.
- **6th task type plugin** if signaled: `scheduled_audit_task` or similar per state doc §4.7 deferred.
- **Subscriber registry persistent log.** Currently sync-in-v1 per state doc §5.7; v2c upgrades to persistent log for audit + replay per state doc §5.7.
- **Task templates via visual editor.** Per state doc §4.6 Q8 deferred. Operators author task creation templates that the workflow engine + task creators registry consume.
- Likely needs migration r110 (persistent subscriber log; escalation rule type extension; specific shape resolves at v2c investigation)

**Independence:** v2c independent of v2a + v2b; signals dictate when v2c dispatches.

### 3.4 Per-sub-arc dependencies + ordering

- **v2a independent of v2b/c** — can ship first.
- **v2b independent of v2a/c** — can ship first.
- **v2c partially dependent** — escalation routing leverages v1.5's routing substrate; task templates leverage v1.0's task creators plugin contract; both shipped pre-v2c so dependencies satisfy.

**Ordering operator-decision based on upgrade signals.** Phase 4 §5 below specifies the operator-observable signals that trigger each v2 sub-arc. If v2a's signal surfaces first (operators describe friction at 10 non-task queue routes), v2a dispatches first. If v2b's signal surfaces first (Hopkins families ask by phone instead of checking portal), v2b dispatches first.

### 3.5 Investigation-first vs build-only per sub-arc

Phase 4 recommends:
- **v2a investigation-first.** 10 adapter patterns substantive enough to warrant scope-lock investigation; per-substrate disposition decisions (adapter shape, denormalization, cardinality preservation) need substrate-design pass.
- **v2b build-only IF v2a investigation surfaces clean patterns.** Otherwise v2b investigation-first.
- **v2c build-only.** Substrate refinements scoped against specific signals; each refinement is small enough to ship build-only.

---

## §4. v3 scope shape

**Scope basis:** state doc §6 v3 scope enumeration.

v3 is largest scope; plausibly **3-5 arcs**. Phase 4 enumerates five potential arc shapes; final dispatch sequence depends on signals at v2 close.

### 4.1 v3a — Contractor portal task surfaces

**LOC envelope:** ~1,500-2,500 LOC. **Parallel to v2b family portal pattern.**

Per state doc §6 v3 enumeration + §4.6 Q4. Contractor portal (e.g. Sunnycrest's contractor customers, vendor-side portals) renders contractor-scoped task lists / details / completion. Similar architectural shape to v2b but different portal identity (contractor PortalUser) + different visibility scoping + contractor-appropriate task type plugins (`contractor_approval_task`, `contractor_quote_review_task`, etc.).

### 4.2 v3b — Coaching pattern producing tasks

**LOC envelope:** ~2,000-3,500 LOC. **Depends on Intelligence + observation substrate maturity.**

Per state doc §1 claim 13 + §6 v3 enumeration. Observe-and-offer pattern materializes as task creation with appropriate framing ("I noticed X — want me to do Y?" becomes a low-friction task surfaced via Pulse). Requires Intelligence substrate to surface observation candidates + UI for accept / dismiss / customize. Coaching depth depends on Intelligence depth at the time of dispatch.

### 4.3 v3c — Shelf parking + communications deeper integration

**LOC envelope:** ~1,500-3,000 LOC.

Per state doc §1 claim 14 + claim 9 + §6 v3 enumeration. Shelf parking: "you parked the Jones case 30 minutes ago, want to follow up?" — time-in-shelf reminder pattern; tasks created from shelf state. Communications deeper integration: incoming-message-typed task creation (different task types for "respond to inbound" vs "follow up on outbound"); task completion triggers outbound communications.

### 4.4 v3d — Workshop UI task management

**LOC envelope:** ~2,000-3,500 LOC.

Per state doc §1 claim 11 + §6 v3 enumeration. Tenant-facing operational team management UI. Operators author task surfaces for their teams; team-wide assignment / load-balancing / progress views; admin-shape task governance.

### 4.5 v3e — Customer-facing operational extensions

**Variable LOC; sub-arcs per extension.**

Per state doc §6 v3 enumeration. Specific extensions per vertical (urn sales contractor approval flows, FH family decision flows beyond what v2b covers, etc.). Each extension is its own arc.

### 4.6 Customer-facing portal sequencing decision

Phase 4 §4 makes the call: **family v2b ships first (within v2), contractor v3a ships within v3.**

Rationale: family portal substrate is already partially present (family-approval magic-link surface; state doc §5.9). Building family-portal task surfaces leverages existing portal substrate. Contractor portal is greenfield; defer to v3.

If v2b does not ship within v2 (signals don't surface), family portal moves to v3 alongside contractor v3a.

### 4.7 AR-future architectural seeding

Per state doc §6 v3 enumeration ("AR-future considerations; spatial task UI; deferred but architecturally seeded").

v3 does **NOT** build AR. v3 substrate ensures task surface registrations are spatial-UI-compatible (no architectural lock-in against eventual AR overlay). Specifically: task surface registrations should be data-shape clean (don't presume DOM layout); visibility enforcement should be query-shape clean (don't presume rectangular UI); event subscriber registry shouldn't lock in synchronous-only semantics (AR overlay might subscribe async).

Concrete forward-compat hooks land per arc as relevant; no dedicated AR-prep arc.

---

## §5. Upgrade signals between phases

**SUBSTANTIVE DELIVERABLE PER DISPATCH.** Operator-observable workflow signals (not architecture-observable thresholds) trigger phase dispatches. Anti-signals enumerated explicitly per phase.

**Discipline source:** state doc §4.1 v1 investigation operator decision ("Architecture-observable signals explicitly rejected as (d) triggers. Only operator-observable workflow shape signals trigger (d) dispatch") + state doc §6 closing ("operator-observable shape; not architecture-observable"). Phase 4 honors and extends to v1.5, v2, v3 sequencing.

### 5.1 v1.0 → v1.5 signal: internal verification gate

Per state doc §4.7 Lock A operator decision ("explicit operator-confirm gate between phases").

**Signal shape:** internal verification, not external operator-observable workflow. v1.0 substrate validates against staging use without surfaced friction; operator confirms via spot-check.

**Concrete what-operator-validates list** (subset of §1.2 acceptance criteria, surfaced specifically for the gate review):

- r107 migration applied cleanly on staging (CI gate green; manual spot-check confirms backfill caught all existing `tasks` rows)
- 8 existing Task consumers exercised manually against staging (Triage workspace renders task list; NL extractor demo creation works; Peek hover on a task entity renders; route handler API exercise via curl returns expected shape; task_service callers via test suite green; `_build_tasks_item` returns `None` as expected — wiring is v1.5)
- Synthetic scenario: create new task via service layer → verify VaultItem + task_details rows created 1:1 → verify task_triage queue picks it up → verify `task_assigned` notification fires via existing (c) path (unchanged)
- Real-data scenario: pre/post backfill query identity confirmed (sample 5 existing task rows; query through façade pre-backfill vs post-backfill returns identical results)
- Zero existing-surface behavior changes verified via regression test cohort

**What operator does NOT need to validate at this gate:**
- v1.5 wiring (Pulse, briefings, (c) refactor, workflow nodes, Focus, Intelligence, communications) — that's v1.5's own scope
- Adapter patterns for v2 — out of scope
- Customer-facing portal surfaces — out of scope

If gate passes: v1.5 dispatches within same arc, no new arc-open round-trip.

If gate fails or surfaces material divergence: stop v1 arc, write up findings, surface to operator, decide whether to extend v1.0, alter v1.5 scope, or pause.

### 5.2 v1 close → v2 dispatch signal: operator-observable workflow shape signals

Per state doc §6 closing ("Sunnycrest staff + Hopkins directors describe Monday-morning workflow shape such that 10 non-task triage queues being unfolded creates real friction").

**Concrete trigger signal patterns (any one suffices for v2a dispatch):**

- "Sunnycrest staff describe Monday-morning workflow as 'check 10 separate queue routes to see what's pending' rather than 'check Pulse for everything that needs my attention.'" — signals v2a triage queue adapter dispatch (canonical surface friction)
- "Hopkins directors describe specific friction in moving between triage queues (e.g. 'I do safety, then aftercare, then catalog review and I can't tell what I've already touched today')." — signals v2a (queue-fragmentation friction)
- "Sunnycrest accounting describes the month-end-close + cash-receipts + ar-collections triage trio as 'three separate places I have to check' rather than 'one place where my accounting decisions live.'" — signals v2a (accounting-substrate-specific friction)

**Concrete trigger signal patterns (any one suffices for v2b family portal dispatch):**

- "Hopkins families ask the funeral home about case status by phone/email rather than checking portal." — signals v2b family portal task surface dispatch (passive portal signals)
- "Hopkins directors describe spending time re-explaining family-side decision steps each conversation." — signals v2b (family workflow visibility need)
- "A specific family request surfaces: 'I want to see what I'm supposed to do next' / 'where am I in this process'." — signals v2b (explicit family agency need)

**Concrete trigger signal patterns (any one suffices for v2c substrate refinements):**

- "Sunnycrest manufactures describe wanting to delegate aftercare to specific staff (non-director) and the current permission shape doesn't support it." — signals v2c escalation routing
- "Operators describe authoring same task creation pattern three or more times across workflows" — signals v2c task templates
- "Audit / debugging surfaces request 'what subscribers fired on this task and when'" — signals v2c persistent subscriber log

**Explicit ANTI-signals (do NOT trigger v2):**

- **LOC threshold:** "v2 work has accumulated ~6,000 LOC in deferred-items list" — architecture-observable; **rejected**.
- **Count threshold:** "10 triage queues remain unfolded into task substrate" — architecture-observable; **rejected**. The deferral was deliberate; remaining count alone is not signal.
- **Time threshold:** "3 months since v1 shipped" — architecture-observable; **rejected**. Calendar elapsed time is not workflow signal.
- **Per-engineer signal:** "engineering team feels like next-thing-to-build" — not operator-observable workflow signal; **rejected**. Engineering preference doesn't establish operator need.
- **Aesthetic-completeness signal:** "task substrate feels incomplete with 10 queues outside it" — architectural-aesthetic; **rejected**. v1 was deliberately scoped against operator-observable need, not architectural-completion.
- **Sunk-cost signal:** "Phase 3 design spec'd v2 adapters; let's just ship them" — design-completion; **rejected**. v2 dispatches when v2's bounded decision warrants, not when v1 close leaves design surface unbuilt.

### 5.3 v2 close → v3 dispatch signal: customer-side workflow signals

Per state doc §6 closing ("Customer-side (family or contractor) signals that portal-shape tasks would meaningfully change their workflow").

**Concrete trigger signal patterns (any one suffices for v3a contractor portal dispatch):**

- "Sunnycrest contractor customers describe wanting visibility into quote review status / approval status / order status." — signals v3a contractor portal
- "A specific contractor surfaces: 'I want to see what's pending on my side vs Sunnycrest's side'." — signals v3a (contractor agency need)

**Concrete trigger signal patterns (any one suffices for v3b coaching pattern dispatch):**

- "Operators describe wanting platform to suggest next steps based on patterns the operator has demonstrated." — signals v3b coaching
- "Intelligence observations surfacing in current pattern + user describes wanting them as 'tasks I can act on later' rather than 'notifications I dismiss'." — signals v3b (depth-of-Intelligence + persistence need)

**Concrete trigger signal patterns (any one suffices for v3c shelf parking + communications dispatch):**

- "Hopkins family members specifically request a 'what do I need to do' checklist surface beyond just 'view case status'." — signals v3c family-side workflow surfaces
- "Hopkins directors describe parking work mid-task and not remembering to come back without prompting." — signals v3c shelf parking
- "Inbound communications surface friction: 'I get an email and it doesn't become anything; I forget'." — signals v3c communications deeper integration

**Concrete trigger signal patterns (any one suffices for v3d Workshop UI dispatch):**

- "Multiple tenants describe wanting to author task workflows for their team that the platform doesn't currently support." — signals v3d Workshop UI
- "Sunnycrest admin describes wanting team-load visibility ('who has too much, who has capacity')." — signals v3d (admin governance need)

**Explicit ANTI-signals (do NOT trigger v3):**

Same shape as v1 → v2 anti-signals:
- Architecture-observable thresholds (LOC, count, time elapsed) — **rejected**
- Engineering preference — **rejected**
- Aesthetic-completeness ("substrate should cover customer-side because it's elegant") — **rejected**
- Sunk-cost / design-completion ("Phase 3 design spec'd v3; let's just ship") — **rejected**

### 5.4 Operator-observable signal sourcing

Where do these signals come from in practice? Per Bridgeable canonical pattern (per state doc §2 retrospectives + canon at PLATFORM_PRODUCT_PRINCIPLES.md):

- Direct operator conversations (operator surfaces friction from Sunnycrest staff or Hopkins directors)
- Sunnycrest pilot launch feedback (when pilot lands)
- Hopkins pilot launch feedback (when family-facing pilot lands)
- Demos with prospective Wilbert licensees (September 2026 + onward)
- Operator's own self-observation as Sunnycrest user

Phase 4 does NOT auto-monitor for signals. Operator surfaces signals to Claude; Claude validates signal shape against this §5 vocabulary (operator-observable workflow signal vs architecture-observable anti-signal); if signal-shape valid, Claude dispatches investigation or build prompt for relevant v2 / v3 arc.

---

## §6. Cross-version concerns

### 6.1 Data migration coexistence across phases

**v1.0 backfill** (r107) catches existing `tasks` table rows. Backfill is one-time at v1.0 close.

**v2a backfill** likely needed per-adapter. Each adapter, on first ship, backfills pending-state rows in its source substrate (e.g. all unresolved AgentAnomaly rows → tasks; all pending-review SafetyProgramGeneration rows → tasks). Recommended pattern: each adapter ships its own backfill at adapter-arc-close (matches (c) build arc canon at state doc §2.4). Migration r108 likely; per-adapter backfill scripts.

**v2b backfill** likely needed for portal-visible task surfaces (e.g. backfill family-visibility tasks from existing OrderPersonalizationTask + family-approval magic-link surface). Migration r109 likely.

**v2c backfill** if persistent subscriber log lands: not strictly a backfill (log starts empty; forward-only); but persistent log table creation. Migration r110 likely.

**v3 backfills** per-arc; specifics resolve at v3 dispatch time.

### 6.2 Canon-update interleave

Per state doc §7 — currently ~51 unfiled canon candidates accumulated across lineage. Phase 4 surfaces **6 additional candidates** (see §6.5 below); cumulative count post-Phase-4 = ~57. Phase 5 v1 build prompt will surface more during build (subscriber registry shape canon, plugin contract pattern canon, façade pattern canon, etc.); estimated +6-10 candidates from v1.0 + v1.5 build arcs combined.

**Recommended canon-update dispatch timing: AFTER v1 close, BEFORE v2 dispatch.** Rationale:

- v1 close establishes the substrate that canon documents reference
- v1 close natural pause point (operator-confirm gate already exists)
- Canon-update arc dispatches against ~57-67 candidates from full lineage to date
- Canon-update arc ships canon shape that v2 + v3 dispatches against (v2 + v3 build prompts reference canon, not state docs)
- Resists canon-update piecemeal scattered across v1 / v2 / v3 arcs

The canon-update arc is its own investigation-first arc (substantive enough to warrant scope-lock investigation given ~60-candidate volume). Phase 4 surfaces this sequencing recommendation; operator confirms at v1 close → canon-update gate.

### 6.3 STATE.md narrative across phases

Per Bridgeable canon (single-commit-per-arc; STATE.md entry per arc close):

- v1.0 internal close: **no STATE.md entry** (internal-only; gate is conversation-level; no git commit at v1.0)
- v1.5 close (= v1 close): **STATE.md entry** ("task substrate v1 complete — substrate + integration; (c) refactor merged into task-event-driven dispatch; 8 producer sites refactored; Pulse + briefings + workflow nodes + Focus + Intelligence + communications consume task substrate")
- Canon-update arc close: STATE.md entry
- v2a sub-arc close: STATE.md entry
- v2b sub-arc close: STATE.md entry
- v2c sub-arc close: STATE.md entry
- Each v3 arc close: STATE.md entry

### 6.4 (c) refactor commit shape

Per state doc §4.7 lock: (c) refactor ships v1.5, not v1.0. Per state doc §2.4: (c) build arc commit shape = single arc + single commit + push at arc close.

**(c) refactor ships in v1.5 commit, not dedicated commit.** Per state doc §4.7 lock — v1 is single arc; v1.5 is one phase of that arc; commit at arc close means (c) refactor lands as one of 8 integration items inside v1.5's commit.

Operator confirms at Phase 4 close: confirmed. (Recommended; alternative would be to commit (c) refactor mid-arc which conflicts with build-arc-canon.)

### 6.5 Test cohort accumulation

- v1.0: ~150-200 tests
- v1.5: ~100-150 tests
- v2a: ~150-250 tests (10 adapter × ~15-25 tests each + integration)
- v2b: ~100-150 tests
- v2c: ~50-100 tests
- v3 arcs: ~500-1,000 tests total across 3-5 arcs

**Total ~1,050-1,850 tests across full vision.**

### 6.6 Plugin registry growth

3 new categories ship in v1.0; canon-file post-v1 via canon-update arc. Per-plugin growth:

- v1.0: 5 task type plugins land
- v2: ~6th plugin (scheduled_audit_task or similar) if signaled; ~5-10 task creators (10 adapters + family-shape creators)
- v3: ~3-5 more (contractor-shape + coaching-shape + shelf-parking-shape + Workshop-shape)

Per-plugin growth registers against v1.0 contract without canon-update needed per plugin (canon establishes the contract pattern; individual plugins are implementations).

### 6.7 Material-divergence-trigger watchpoints

Per Phase 0 §10 calibration band: triggers at >25k v1+v2+v3 ceiling, or >15% deviation from per-phase envelope.

- v1.0: trigger threshold 6,000 LOC; envelope 5,500 ±15% (4,675-6,325); upper-band touches trigger
- v1.5: trigger threshold 4,000 LOC; envelope 3,500 ±15% (2,975-4,025); upper-band touches trigger
- v2: total 6,000-10,000; threshold per sub-arc + cumulative — investigation-first for v2a per §3.5 means trigger surfaces before build
- v3: total 7,000-15,000; per-arc thresholds resolve at arc dispatch

If any v1 phase trips trigger during build: stop, surface to operator, decide (extend phase / alter scope / pause).

### 6.8 Canon candidates surfaced by Phase 4

Filing forward for canon-update arc (6 candidates from this phase):

14. Operator-observable upgrade signal vocabulary canon. The signal-shape vs anti-signal-shape distinction at §5 of this phasing recommendation is canon-worthy; future phasing recommendations should cite the vocabulary established here.
15. Phasing recommendation shape canon. This 8-section structure (substrate phase final-lock + integration phase final-lock + v2 sub-arc grouping + v3 arc shape + upgrade signals + cross-version + honest cost + open questions) is a canonical Phase 4 deliverable shape for any future multi-phase architecture sequencing.
16. Adapter-substrate vs absorbed-into-substrate decision canon. Recommended pattern: adapter-substrate preserves operational continuity; absorbed defers to consolidation arc when operator-validated. v2a is the first arc exercising this.
17. Single-arc multi-phase internal-gate canon. v1 ships single arc with v1.0 → v1.5 internal phase gate; commit at arc close. Pattern extensible to future multi-phase arcs.
18. Test cohort accumulation across multi-arc lineage canon. ~1,050-1,850 tests across the full task substrate vision is the order of magnitude; future arc lineages can use as reference.
19. Customer-facing portal forward-compat canon. Schema supports portal-shape from v1; visibility enforcement is operator-only in v1; portal query paths activate at v2/v3 per signals. Pattern extensible to future cross-realm substrate work.

---

## §7. Honest cost across v1+v2+v3

### 7.1 LOC envelope summary

| Phase | Envelope (±15%) | Range |
|-------|-----------------|-------|
| v1.0 | ~5,500 | 4,675-6,325 |
| v1.5 | ~3,500 | 2,975-4,025 |
| v2a | ~3,000-5,000 | 2,550-5,750 |
| v2b | ~1,500-2,500 | 1,275-2,875 |
| v2c | ~1,500-2,500 | 1,275-2,875 |
| v3a | ~1,500-2,500 | 1,275-2,875 |
| v3b | ~2,000-3,500 | 1,700-4,025 |
| v3c | ~1,500-3,000 | 1,275-3,450 |
| v3d | ~2,000-3,500 | 1,700-4,025 |
| v3e | variable | variable |

**Total mid-estimate (excluding v3e variable): v1 ~9,000 + v2 ~6,000-10,000 + v3 (a+b+c+d) ~7,000-12,500 = ~22,000-31,500 LOC** across the full vision (excluding v3e which is per-extension variable).

### 7.2 Calibration-band ceiling

Per Phase 0 §10 trigger: 25,000 v1+v2+v3 ceiling. **Mid-estimate ~26,750 sits above ceiling.** Upper-band ~31,500 substantively above ceiling.

**Material-divergence-trigger-adjacent surfacing:** Phase 4 §7 is honest about total. Two operator decisions:

1. **Accept 25k-31k envelope.** Total is honest; substrate genuinely covers comprehensive task vision; calibration band was set against less mature understanding of scope. Accept as cost of comprehensive task substrate.

2. **Tighten v3 scope to ship under 25k.** Cut v3d or v3e or compress v3b's coaching scope. Recommended if calibration-band-canon discipline matters more than v3-feature-completeness.

**Phase 4 recommendation: accept the envelope but flag the divergence.** Reasoning: state doc §1 (May 21-22 conversation) establishes the comprehensive vision; comprehensive vision genuinely covers ~22-31k LOC across multi-year horizon; v1+v2 ships under 16k (well under 25k for the "near-future shippable scope"); v3 is the long-horizon work that may shift in shape before any v3 arc dispatches (signals may make some v3 arcs unnecessary, may surface new v3 arcs not currently enumerated). Calibration band was set against single-arc scope; full-vision multi-arc scope is genuinely larger.

**Operator decision required at Phase 4 close.** §8 below surfaces as open question.

### 7.3 Arc count

- v1: **1 arc** (single arc with internal v1.0 / v1.5 phases)
- v2: **2-3 sub-arcs** (v2a + v2b + v2c; selected per signals)
- v3: **3-5 arcs** (v3a + v3b + v3c + v3d + v3e; selected per signals)
- Canon-update arc between v1 and v2: **1 arc**

**Total 7-10 arcs across full vision** (including canon-update arc).

### 7.4 Test count

**~1,050-1,850 tests across full vision** per §6.5.

### 7.5 Migration count

- r107 (v1.0 task_details + VaultItem enum extension + composite idempotency unique index)
- r108 likely (v2a adapter substrate — per-substrate FK columns + adapter-specific indexes)
- r109 likely (v2b portal-task visibility schema + family-shape additions)
- r110 likely (v2c persistent subscriber log table + escalation routing rule extension)
- r111+ likely (v3 portal extension + Workshop UI schema + coaching task type tables + spatial-task forward-compat columns)

**Total 5-7 migrations across phases.**

### 7.6 Honest summary

The task substrate vision is comprehensive. v1 (single arc, ~9,000 LOC, 1-2 months calendar) ships substrate that makes the May 21-22 architectural vision possible at the foundation layer. v2 (3 sub-arcs, ~6,000-10,000 LOC) extends to non-task substrate coverage + family portal. v3 (3-5 arcs, ~7,000-12,500 LOC) extends to contractor + coaching + shelf parking + Workshop UI.

The full vision is a multi-year horizon. Each phase carries operator-confirm gates; each phase dispatches against operator-observable signals; no phase auto-dispatches based on architectural completeness.

The calibration-band-ceiling overshoot is honest: substrate is comprehensive; comprehensive is genuinely larger than the calibration band was set against. Operator accepts envelope or tightens v3 scope.

---

## §8. Open questions for operator decision before v1 dispatches

Per state doc §9 ("open questions Phase 1-3 surfaced that need operator decision before v1 dispatches") + Phase 4-specific questions surfaced during this phase.

### 8.1 (c) refactor commit shape

**Question:** (c) refactor ships in v1.5 commit (not dedicated) per §6.4. Confirm?

**Phase 4 recommendation:** Confirmed by state doc §4.7 lock + state doc §2.4 (c) build arc canon. Single arc, single commit at arc close. (c) refactor lands as one of 8 v1.5 integration items inside v1.5's commit.

**Operator decision:** confirm or alter.

### 8.2 Canon-update interleave timing

**Question:** Canon-update arc dispatches when?

**Phase 4 recommendation:** post-v1 close, pre-v2 dispatch. Per §6.2 rationale.

**Operator decision:** confirm or alter.

### 8.3 v2 sub-arc ordering

**Question:** Which v2 sub-arc dispatches first (v2a triage adapters vs v2b family portal vs v2c substrate refinements)?

**Phase 4 recommendation:** operator-decision based on which §5.2 signal surfaces first. All three v2 sub-arcs independent (per §3.4); any can ship first. Phase 4 does NOT pre-commit ordering.

**Operator decision:** acknowledge signal-driven ordering or alter.

### 8.4 v3 portal sequencing

**Question:** Within v3, does contractor v3a ship first (if family v2b already shipped)? Or alter order?

**Phase 4 recommendation:** v3a (contractor) first within v3, given family v2b ships within v2. If family v2b does NOT ship within v2 (signals don't surface), family moves to v3 alongside contractor v3a — at which point family vs contractor ordering becomes a v3 signal-driven decision.

**Operator decision:** confirm or alter.

### 8.5 v2 sub-arcs investigation-first or build-only

**Question:** Each v2 sub-arc investigation-first or build-only?

**Phase 4 recommendation:** v2a investigation-first (10 adapter patterns substantive enough); v2b build-only if v2a investigation surfaces clean patterns (otherwise investigation-first); v2c build-only (substrate refinements scoped against specific signals; each small enough).

**Operator decision:** confirm or alter per sub-arc.

### 8.6 Total LOC envelope above 25k

**Question:** Accept ~22-31k full-vision envelope, or tighten v3 scope to ship under 25k?

**Phase 4 recommendation:** accept the envelope; flag the divergence honestly. Per §7.2 reasoning.

**Operator decision:** accept or tighten.

### 8.7 v1 dispatch as investigation-first or build-only

**Question:** v1 dispatches as investigation-first (one more investigation arc) or build-only?

**Phase 4 recommendation:** **build-only**. This Phase 4 IS the substantive investigation; Phase 3 IS the substrate design (lost-but-conclusions-preserved); state doc §5 captures the architectural trajectory; v1.0 / v1.5 scope is dispatch-ready post-this-Phase-4-close. Phase 5 v1 build prompt drafts against Phase 4 + state doc + current code state; ships dispatch-ready build prompt for v1.0 substrate arc.

**Operator decision:** confirm or one-more-investigation.

### 8.8 v1.0 → v1.5 operator-confirm gate format

**Question:** What format does the v1.0 → v1.5 operator-confirm gate take?

**Phase 4 recommendation:** conversational gate (Claude surfaces "v1.0 acceptance criteria met; ready to dispatch v1.5?"; operator confirms or surfaces concerns). Not a separate document round-trip; not a separate arc dispatch. Same-arc internal phase transition.

**Operator decision:** confirm conversational gate or specify format.

### 8.9 Implementable specifics re-derivation

**Question:** Phase 5 build prompt drafts implementable specifics (schema column inventory, plugin contract input/output text, migration delta) against current code, not against Phase 3 design (which is lost). Confirm?

**Phase 4 recommendation:** confirmed by state doc §8 ("Phase 5 build prompt agent reads this document + Phase 4 phasing + current code state + does substrate-design verification as part of build prompt drafting. Phase 3's lost implementable specifics aren't re-shipped as a separate Phase 3 redo; they're re-derived in service of Phase 5 build prompt against current code, which is the right discipline anyway").

**Operator decision:** confirm or specify alternate (e.g. Phase 3 redo as separate arc).

---

## Phase 4 closing observation

The bounded decision closes: locked architecture (state doc §5) sequences into shippable arcs as **v1 (single arc, two internal phases) → canon-update arc → v2 (2-3 signal-dispatched sub-arcs) → v3 (3-5 signal-dispatched arcs)**, with operator-observable workflow signals between phases per §5 of this document.

Phase 4 does NOT auto-cycle to Phase 5. Operator confirms (or alters) the 9 open questions in §8; Phase 5 v1 build prompt dispatches against the confirmed shape.

The task substrate arc remains the active arc.

---

*Document captured May 25, 2026 by Opus in service of Phase 4 phasing recommendation against state doc bc7c4ba. Closes the v2 investigation's Phase 4 bounded decision. Phase 5 v1 build prompt drafts against Phase 4 + state doc + current code state, ships dispatch-ready build prompt for v1.0 substrate arc when operator confirms §8 open questions.*
