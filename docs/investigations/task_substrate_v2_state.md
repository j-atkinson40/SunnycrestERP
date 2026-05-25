# Task Substrate Investigation — Consolidated State Document

> **Document purpose.** This document is the canonical reference for the task substrate architectural lineage spanning May 21–22, 2026 through the v2 investigation Phase 3 close on May 24, 2026. It exists because `/tmp/` rotation at 20:12 on May 24 wiped all investigation deliverables (~35,500 words across the v1 investigation + (c) investigation + v2 investigation Phases 0–3) before Phase 4 could dispatch.
>
> The document is broad-scope by operator decision: it captures the full task substrate arc lineage rather than only the v2 investigation's recoverable state. Where deliverables survive elsewhere (STATE.md entries, git commits, conversation transcripts), this document references them; where deliverables are lost, this document preserves substantive conclusions at the fidelity that survived in session transcript.
>
> This is not a regenerated Phase 1/2/3 deliverable. It is a different artifact serving a different purpose — forward-flow state capture for Phase 4 dispatch and downstream arcs. Implementable specifics (full file:line citations from Phase 1 audit, exact schema column inventory from Phase 3 design, exact plugin contract text) are out of scope for this consolidation; they are re-derived in Phase 5 v1 build prompt against current code state.
>
> **Going-forward discipline established by the loss event:** investigation deliverables ship to persistent storage (this document's location pattern, `docs/investigations/`), not to `/tmp/`. `/tmp/` remains appropriate for transient computation; deliverables that future arcs cite back to require git-tracked persistence. Filed forward to canon-update arc.

---

## 1. Primary source

The May 21–22, 2026 conversation that originally surfaced the task substrate architectural insight is the anchor for everything that follows. The full verbatim text of that conversation, including operator turns and Claude responses, was captured by operator at the start of the v2 investigation and originally lived at `/tmp/task_substrate_v2_primary_source.md` (~6,500 words; two operator turns + two Claude responses across two dates).

The conversation's substantive architectural claims, distilled from the full text but with the full text remaining the authoritative source:

**Operator's framing (May 21):** "Your example suggesting a reminder based on time in shelf makes me think we might need to build somewhat of a task manager. That would be useful for the coaching idea too so users know what they need to do. The briefings can pull from it too."

**Operator's recognition (May 22):** "Okay that was definitely the missing piece. I've been trying to think about how I am going to tie everything I'm building together and tasks is how. All the accounting automations that we made are routine task triggered. All triage review focuses are tasks created by an event in the platform (funeral order with personalization triggers a review triage for the personalization via tasks). Everything just fell into place in my mind. A task triggers a workflow which triggers a task to review something which opens a focus. It all works together."

**Architectural claims from Claude's responses** — these are the load-bearing claims that v2 investigation tested:

1. **Tasks as foundational substrate, not feature.** Substrate that other capabilities consume — not a capability among many.
2. **Tasks as Vault items, conceptually.** Same Vault substrate that holds cases, customers, documents, everything else. Vault-as-foundation principle extends naturally.
3. **Universal operational pattern.** Operations follow: event creates need for attention → task creation → task routing → task work (Focus pattern handles bounded decisions) → task completion → completion triggers more tasks. Universal across verticals.
4. **Tasks have properties:** provenance (manual / workflow / Intelligence / integration), associations (case, customer, document, vault item), lifecycle (created, assigned, in-progress, blocked, complete, cancelled), routing (role-based, capacity-aware, escalation-aware), timing (urgent, deadline-bound, flexible-window).
5. **Vault items are the things tasks are about.** Tasks aren't isolated; contextually connected to operational entities.
6. **Workflows are task automation.** Create tasks at appropriate steps; wait for completion; route based on outcomes.
7. **Focuses are task work environments.** Different Focus types for different task types. Scheduling Focus enables scheduling decision tasks; arrangement scribe Focus enables arrangement creation tasks; triage Focus enables triage decision tasks.
8. **Documents are task outputs.** Many tasks produce documents — quotes, invoices, contracts, reports. Task completion triggers document generation.
9. **Communications are task triggers and task outputs.** Incoming communications create tasks for response; task completion often triggers outgoing communications.
10. **Intelligence creates tasks.** Observations that need human attention become tasks rather than fleeting notifications. Tasks persist; can be tracked; can be reviewed when user is ready.
11. **Pulse Personal layer IS canonical task list view** for the viewing user, not just "a view that shows tasks." Operational layer includes domain-wide task statistics. Anomaly layer surfaces blocked/overdue tasks.
12. **Briefings draw from tasks as canonical source.** "Here's what needs attention this week" pulls from incomplete tasks. "Here's what got resolved" pulls from recently-completed tasks. "Here's what's coming up" pulls from upcoming deadlines.
13. **Coaching produces tasks.** Observe-and-offer pattern materializes as task creation with appropriate framing.
14. **Shelf parking produces tasks.** "You parked the Jones case 30 minutes ago, want to follow up?" The shelf becomes a source of tasks.
15. **Customer-facing tasks via portals.** Family portals show family-appropriate tasks ("select photos for obituary"). Contractor portals show contractor tasks ("approve quote"). Same substrate, scoped visibility, customer-appropriate UX.
16. **Visual editor authors task surfaces.** Task lists, task details, task creation forms — all visual editor compositions of registered components.
17. **Three-tier scope inheritance.** Platform default task patterns, vertical-specific patterns, tenant customization.
18. **Plugin pattern for task type-specific behaviors.** Different task types have different lifecycle behaviors, different displays, different automations. Plugins register against generic substrate.
19. **Strategic positioning:** "Your business runs more efficiently because Bridgeable knows what needs doing and tells you, instead of you tracking everything in your head." Task substrate enables the one-person-office thesis by handling cognitive tracking burden.

Claude's original honest scoping: 8–12 weeks for comprehensive v1 task substrate; option three (minimum pre-September with comprehensive post-September expansion) was the recommended pacing at the time of the conversation. Note that this estimate predates Bridgeable's demonstrated AI-executed velocity; v2 investigation Phase 2 audit-locked v1 envelope at ~8,000 LOC and Phase 3 at ~8,980 LOC, which against Bridgeable's actual pacing translates to substantially less calendar time than 8–12 weeks.

The full text remains the authoritative source. If future arcs need primary-source citation, the full conversation text should be re-captured from operator's records and stored at `docs/investigations/task_substrate_primary_source_may_21_22.md` (separate file from this consolidation).

---

## 2. Lineage timeline

Chronological trace of arcs in the task substrate lineage. Each arc had its own scope, deliverables, and operator-decision outputs.

### 2.1 May 21–22, 2026 — Primary source conversation

Operator surfaces the task substrate insight to Claude across two dates. Claude responds with substantive architectural exploration. The conversation establishes 19 architectural claims (enumerated in §1) and proposes 8–12 weeks comprehensive v1 + four-option phasing recommendation. No code work dispatches from this conversation.

The conversation predates: (c) build arc, R-6.2a/b intake substrate, Phase 8b–d.1 workflow migrations, GenerationFocusInstance, the Studio shell reorganization, V-1 Vault, the Documents arc landing in current shape, the briefings substrate landing in current shape. Substantial substrate has shipped since.

### 2.2 May ~23, 2026 — Task substrate investigation v1 (`57d8210`)

First investigation arc. Five phases (Phase 0 scope lock → Phase 1 inventory → Phase 2 pattern analysis → Phase 3 restraint check → Phase 4 recommendation). Five `/tmp/task_substrate_*.md` deliverables (~17,000 words total). The investigation's purpose was to adjudicate whether the platform needed task substrate.

**Bounded decision the v1 investigation closed:** "Does Bridgeable adopt a task substrate, and if so, in what shape?"

**Hypothesis adjudication structure:**
- H1: Task substrate is real architectural connective tissue requiring its own row type.
- H2: Task substrate is a rhetorical overlay; existing pieces are correctly shaped under their existing names.

**Phase 1 inventory:** 31 task-shaped surfaces enumerated. 11 triage queues + 5 cross-cutting substrates (AgentJob awaiting_approval, SafetyProgramGeneration, AgentAnomaly, WorkflowRun, FocusSession) + 5 intake/document/VaultItem/onboarding + 1 scheduled-jobs meta + 9 audit-added.

**Phase 2 verdict:** Partial H2 with H1-shaped projection-view warranted. NOT warranted at substrate / row-type layer. Reasoning anchored on: 22/31 surfaces irreversible on close vs 9/31 reversible; only 3-4/31 VaultItem-resident; 6 distinct cardinality semantics per WORKFLOW_MIGRATION_TEMPLATE §10; OrderPersonalizationTask shape-distinct from other 30 surfaces. The notification grep finding (11/11 silent-by-default triage queues firing zero notifications) was the load-bearing operational gap.

**Phase 3 restraint check:** Six candidate moves evaluated. (a) `tasks` table rejected (~6,000-10,000 LOC; no need not closeable by smaller moves). (b) `task` VaultItem item_type rejected (~3,000-5,000 LOC + canon edits). (c) notification-shared-discipline warranted (~300-500 LOC, days not weeks). (d) projection-view / Pulse Personal layer resolver warranted as canon-completion. (e) cardinality-matrix shared library already canonical via WORKFLOW_MIGRATION_TEMPLATE §10. (f) vocabulary-only absorbed into (d)'s presentation layer.

**Phase 4 recommendation:** Sequenced (c)→(d) — (c) ships immediately; (d) defers pending operator-observable Monday-morning workflow signal.

**Operator decision at v1 close:** Dispatch (c) immediately. Defer (d). The "complete the task substrate arc" framing operator surfaced later in the May 24 session reframed (after September forcing function dropped) to "(c) only; (d) genuinely deferred-pending-signal."

**Critical retrospective finding** (surfaced by v2 investigation Phase 2, recorded here for lineage):

The v1 investigation Phase 1 inventory **did not surface the existing `Task` model + `task_service.py` + `task_triage` queue + `_build_tasks_item` stub + `task_assigned` notification category**. These were in code at the time of the v1 investigation but did not appear in the 31-surface inventory. The H2 verdict ("no tasks table; no task VaultItem item_type") was empirically false at the time it was made — there is a `tasks` table. The investigation looked at 31 surfaces and concluded substrate didn't exist; it missed surface #32, which is the actual task substrate that has been in code, scaffolded but partially-deferred, the whole time.

This was an audit-completeness failure at the v1 investigation's inventory phase. It propagated through every subsequent v1 investigation phase and into (c)'s scope-locking work. (c) shipped correctness regardless (notification dispatch gap was real and the producer-site cohort was correctly identified), but the architectural mental model the v1 investigation produced was wrong-shaped. The May 21-22 conversation's "tasks as foundational substrate" claim is the right shape; v1's H2 verdict was the wrong-shape verdict against incorrect inventory data.

### 2.3 May ~23, 2026 — (c) investigation arc (`dfd876c`)

Second investigation arc. Three deliverables (Phase 0 scope lock → Phase 1 audit → Phase 2 build prompt draft). Locked scope against v1 investigation's operator decision: (c) producer cohort, §19 categories, helper substrate, migration scope, test coverage.

**Phase 1 audit findings:** Substrate gap surfaced on `notify_tenant_admins` (admin-only hardcode at `notification_service.py:88-152` line 122; no permission-filter parameter). 11 producer sites locked; 4 AgentAnomaly-backed queues converge at canonical dispatch point `base_agent.py:102 _set_status(AWAITING_APPROVAL)`. 9 §19 categories proposed (aftercare initially folded into `agent_anomaly_pending` then split to `funeral_followup_pending` for recipient-grain correctness). Zero alembic migration (categories are frozen module constant at `category_types.py:43-143`).

**Operator refinements during (c) investigation Phase 2:**
- Lock 1 refinement: 9 §19 categories (was 8), aftercare splits to dedicated funeral-followup category for recipient-cohort grain correctness
- Phase A.0 scope absorbed into build arc opening turn as inline scoping section (one round-trip), not separate document round-trip

**Build prompt ready at `dfd876c` close.**

### 2.4 May 24, 2026 — (c) build arc (`868fec3`)

Build execution arc. Two phases (Phase A.0 inline scoping + Phase A substrate + Phase B producer integration) + single commit + push.

**Phase A.0 inline scoping resolution:**
- `funeral_followup_pending` audience → **new `fh_cases.aftercare`** permission slug (operator refined from agent's proposed reuse of `fh_cases.edit`, citing recipient-grain correctness — broad `fh_cases.edit` cohort would include users who don't specifically action aftercare)
- `workflow_review_pending` audience → existing `admin` permission slug (reuse, no new permission)

**Phase A substrate shipped:**
- New `notify_users_with_permission` helper at `notification_service.py:155` (~75 LOC; slight overshoot from ~30-50 envelope due to docstring + circular-import safeguard via local import; operator-approved as honest overshoot)
- 9 new §19 categories appended to `category_types.py`; registry count 19 → 28
- `fh_cases.aftercare` permission slug registered with operator-specified comment
- Phase A tests: helper unit tests (10), substrate regression tests (10), category types regression (14), V-1d notifications regression (21); all 55 in-scope tests green

**Key Phase A finding:** `fh_cases.aftercare` automatically inherits via FH-director role's dynamic computation `MANAGER_DEFAULT_PERMISSIONS = get_all_permission_keys() - {users.delete, roles.delete}`. No additional role-seed file edits needed. Filed forward as canon candidate (dynamic permission inheritance pattern).

**Phase B producer integration shipped:**
- 8 net file touches at canonical state-transition points:
  - `task_service.py:164` (`create_task` → `task_assigned`)
  - `social_service_certificate_service.py:160`
  - `base_agent.py:103` (3 accounting AgentAnomaly producers + month_end_close via `_dispatch_pending_attention_notification`)
  - `aftercare_adapter.py:204` (`funeral_followup_pending` / `fh_cases.aftercare` with staged > 0 guard)
  - `catalog_fetch_adapter.py:256`
  - `safety_program_generation_service.py:177`
  - `workflow_engine.py:812`
  - `classification/dispatch.py:377`
- Defensive try/except in all 8 dispatches per V-1d pattern
- Backfill script `seed_pending_attention_backfill.py` (~440 LOC; Option A idempotent; ENVIRONMENT=production refusal guard; honest scope vs ~120-180 prefigured due to per-substrate handler scaffolding across 7 substrate cohorts)
- Phase B tests: 17 new (parity + idempotency + integration + backfill regression); plus aftercare end-to-end recipient resolution test verifying full inheritance chain

**Total (c) build LOC:** ~1,535 (Phase A ~155 production + Phase B production ~360 + backfill ~440 + Phase B tests ~580). Production-proper Phase A+B = ~515 vs Phase 4 §3 prefigurement of 300-500 production LOC — 3% over upper bound, honest absorption.

**(c) bounded decision closed:** Notification correctness shipped; 11/11 silent-by-default triage queue gap closed; permission-gated dispatch with self-suppression default.

### 2.5 May 24, 2026 — Task substrate investigation v2 (this arc)

Third investigation arc, opened after operator surfaced the May 21-22 primary source post-(c)-build-close, recognizing that the v1 investigation's H2 verdict had answered a narrower question than the May 21-22 conversation had asked. The forward-looking question (does the platform need task substrate to make the May 21-22 conversation's enumerated capabilities possible) was never asked by the v1 investigation; v2 exists to ask it.

**Bounded decision v2 investigation closes:** *"Given the May 21-22 conversation's forward-looking architectural claims, what task substrate work makes those claims possible, and in what phased sequence (v1/v2/v3) does it ship?"*

**What's locked at v2 investigation open:**
- The May 21-22 conversation's primary architectural claims are working assumptions, not subjects of relitigation. Investigation tests *how* claims realize in substrate, not *whether* they're correct.
- (c) is not being undone. Notification correctness shipped; task substrate work doesn't replace it.
- v1 investigation's 31-surface inventory and audit findings are input material — read for grounding; conclusions stand or get refined under the new question.
- Zero production code this investigation.

**What's open at v2 investigation open:**
- Schema shape (VaultItem `item_type` extension vs new `tasks` table vs hybrid)
- v1/v2/v3 scope boundaries
- Phasing dependencies and sequence
- LOC envelope per phase
- Whether existing surfaces refactor to consume task substrate or sit alongside
- Specific consumer wiring (briefings, Pulse, Focus, Intelligence, workflows)

**Phase 0 scope lock confirmed.** Three operator confirmation items resolved with defaults stood. Pre-Phase-0 honest flag from agent: "Phase 2 gap analysis will likely surface that the gap is smaller than the May 21-22 conversation assumed" — empirically confirmed at Phase 2.

**Phase 1 capability-demand mapping shipped** at original `/tmp/task_substrate_v2_capability_demand.md` (~8,200 words). 22 rows total: 18 in-vision capability rows from May 21-22 conversation + 4 audit-additional surfaced from current platform context. Each row carried 8-field uniform structure: capability name, May 21-22 source citation, functional description, what task substrate it consumes, schema fields it requires, dependencies on other capabilities, current state, customer-facing scope.

**18 in-vision capabilities enumerated** (names only; full row content lost to `/tmp/` rotation but capabilities are recoverable from the May 21-22 conversation):

1. Task list / detail / creation UI substrate
2. Briefings as task-substrate consumers (canonical "what needs attention this week" source)
3. Coaching produces tasks (observe-and-offer pattern materializes as task creation)
4. Shelf parking produces tasks (time-in-shelf reminder pattern)
5. Workflow create-task node type / workflow waits on task completion / route on outcome
6. Intelligence creates persistent tasks rather than fleeting notifications
7. Pulse Personal layer as canonical task list view (the `_build_tasks_item` stub's eventual implementation)
8. Focus integration — tasks say "decide this"; Focus is where decision gets made; entering Focus from task
9. Family portal task surfaces (customer-facing, scoped visibility)
10. Contractor portal task surfaces (customer-facing, scoped visibility)
11. Workshop UI task management (tenant-facing operational team management)
12. Recurring accounting tasks (monthly close, etc.)
13. Triage review focuses as event-created tasks (the May 22 example: funeral order personalization triggers review triage task)
14. Documents as task outputs (quote generation, invoice generation, contract generation triggered by task completion)
15. Communications as task triggers and outputs (incoming email/SMS/voicemail produce tasks; task completion triggers outbound)
16. Notification preferences scoped per task type
17. Three-tier scope inheritance for task patterns (platform default / vertical / tenant customization)
18. Visual editor authors task surfaces (registered widget types)

**4 audit-additional capabilities** (surfaced from current platform context, not explicitly in May 21-22 conversation):
- Task-task chaining via automation (completion triggers followup tasks)
- Escalation rules (task escalates if unresolved by deadline)
- Per-user notification preferences for task categories (different verbosity per task type)
- Task analytics / reporting (volume, throughput, blocked-task patterns)

**Phase 1 closing observations:**
1. Six rows (2, 5, 7, 13, 14, 15) had substantial existing substrate from post-May-21-22 work; the gap was smaller than May 21-22 conversation assumed
2. (c) overlap with 5 capability rows was substantial; Lock 1's operationally-idempotent requirement made concrete via `(producer_module + record_id + event_kind)` composite key
3. Reminders-shape concentration in rows 3, 4, 12 + secondary in 1, 2, 6, A2 — data-supported the Reminders-fold-into-tasks v1 option that operator subsequently locked
4. Customer-facing rows 9, 10, partial 14, 16 carried cross-realm architectural weight (PortalUser vs User identity, visibility scoping, cross-task linkage)

**Phase 2 gap analysis shipped** at original `/tmp/task_substrate_v2_gap_analysis.md` (~9,597 words). Each of the 22 capability rows gap-analyzed with 6-field shape + 4-way tag (`build_new` / `wire_existing` / `refactor_existing` / `refactor_against_revised_lock_1`). Cross-cutting substrate items section identified foundation work shared across capabilities.

**Phase 2 headline finding (load-bearing for everything subsequent):** Task substrate is MORE PRESENT than Phase 1 surfaced. Concrete artifacts already in code:
- Complete `Task` model at `backend/app/models/task.py:38-95`
- `task_service.py` with full CRUD + 5-state lifecycle
- `/api/v1/tasks/*` routes
- NL creation extractor + Peek builder + Triage action handlers
- Scaffolded-but-deferred `_build_tasks_item` in `pulse/personal_layer_service.py:87-168` (returns `None` pending wire decision)
- `task_triage` queue is first registered platform-default with `_dq_task_triage` direct query
- `task_assigned` category already in (c)'s registry
- `task_service.create_task` itself fires the notification at line 174 — (c) producer site #1 IS the task creation site itself

The "gap is smaller than May 21-22 conversation assumed" Phase 0 honest flag was understating it. Task substrate at the model + service + route + lifecycle layer already exists. What's missing is: Pulse Personal layer consumption, briefings consumption, broader producer integration, customer-facing portal extension, and the systematic plugin contract.

**Phase 2 Revised Lock 1 verification:** Operator's revised Lock 1 from Phase 1 review (treating (c)'s 8 producer sites as task-creation hooks rather than notification-only-event-firers) verified against code. ~250-300 LOC total estimated (8 producer-site refactors at ~15-20 LOC each + ~150 LOC subscriber substrate). Above operator's ~100-150 LOC envelope but well under 300 LOC material-divergence trigger. No schema changes to Notification table required. (c)'s idempotency story preserved via `(provenance, source_record_type, source_record_id)` keying.

**Phase 2 Lock 2 hypothesis finding:** VaultItem `item_type` enum at `vault_item.py:30` lists 11 values; **`task` is NOT among them.** Tasks live in their own `tasks` table. Lock 2's working hypothesis (VaultItem `item_type='task'` extension) doesn't match shipped reality. Phase 3 must adjudicate explicitly. This was surfaced as biggest Phase 3 architectural decision.

**Phase 2 Lock 3 (Reminders) verification:** `reminder` IS in `VaultItem.item_type` enum but unimplemented. Four-option adjudication has full degrees of freedom (subsume / coexist / become subtype / fold into task substrate v1).

**Phase 2 aggregate v1 envelope:** ~8,000 LOC. Above Phase 0 §10's 6,000 LOC v1 trigger. Phase 4 phasing must split. Breakdown: cross-cutting foundation ~2,550 LOC (~30% of v1); customer-facing extension rows 9+10 ~3,300-4,700 LOC likely v2 candidates; plus 22-row capability coverage.

**Phase 2 surfaced 8 framing questions for Phase 3:**
- Q1: Lock 2 schema shape — migrate tasks→VaultItem? Keep separate? Hybrid? (BIGGEST)
- Q2: W-4b Pulse Personal deferral — wire `_build_tasks_item` stub vs build new substrate?
- Q3: Triage queue unification — fold 10 non-task triage queues into task substrate?
- Q4: Cross-realm v1 scope — operator-only v1 + customer-facing v2/v3?
- Q5: Lock 3 Reminders — four options
- Q6: Plugin category vocabulary — task creators + task surfaces + other?
- Q7: Event substrate shape — subscriber registry vs queue-based vs direct dispatch?
- Q8: Templates priority — task templates / authored task creators in v1 or v2?

**Phase 3 substrate design shipped** at original `/tmp/task_substrate_v2_design.md` (~8,876 words / 1,267 lines). 13-section comprehensive design with implementable schema + plugin contracts + integration design. **Material-divergence trigger from Phase 2 to Phase 3 did NOT fire** — agent surveyed all 8 existing Task consumers (`_dq_task_triage`, NL extractor, Peek builder, route handlers, task_service callers, etc.). Q1 (d) hybrid migration is non-breaking via service-layer + Task façade pattern. Consumers query through service layer abstracted from table layout.

**Phase 3 thirteen sections** (full implementable specifics lost; section-level decisions captured here):

1. **Schema** — VaultItem `item_type='task'` (12th value) + `task_details` join table. Column inventory included: `assignee_realm` / `assignee_user_id` / `assignee_portal_user_id` (forward-compat per Q4); `lifecycle_shape` enum per Q5; provenance polymorphic FK; visibility enum per cross-realm extension. FK CASCADE / SET NULL specified. Six indexes. Partial-unique idempotency constraint. Migration r107 + backfill script Option A idempotent.

2. **Lifecycle** — Dual state machines per Q5:
   - Action shape: `created → assigned → in_progress ↔ blocked → done | cancelled`
   - Reminder shape: `informational → acknowledged | dismissed`
   - Transition tables specified; backward-compat mapping from existing 5-state machine for existing `tasks` content; resolution_outcome field; suppression key.

3. **Provenance** — 12 `provenance_kind` values; polymorphic ref; composite idempotency key `(provenance_kind + provenance_ref + event_kind)` per Revised Lock 1.

4. **Routing** — `task_routing_rules` table; three-tier resolver (platform / vertical / tenant); permission-gated assignment; v1 = `direct_user` + `round_robin` modes per operator lock.

5. **Visibility** — 5-value enum; tenant + portal query filters specified inline; v1 operator-only enforcement per Q4 lock; schema supports portal-shape for v2.

6. **Task creators plugin** — Full contract (input / output / guarantees / failures / registration); in-memory registration mechanism per existing Bridgeable Tier R1 pattern.

7. **Task surfaces plugin** — Full contract; 9 surface implementations mapped (existing task list/detail + Pulse stub + briefings + 6 future).

8. **Task type behaviors plugin** — Full Protocol; 5 v1 plugins enumerated per operator lock:
   - `generic_task` (catch-all for manual creation)
   - `review_approval_task` (covers approval-gate cohort)
   - `scheduled_recurring_task` (covers accounting recurring per May 21-22)
   - `customer_communication_task` (communications cascade)
   - `anomaly_resolution_task` (AgentAnomaly producer sites)

9. **Integration contracts** — 3 workflow node types specced (create_task, wait_for_task_completion, route_on_task_outcome per operator lock); Focus extension column; briefings 3 new helpers; Pulse re-enable (Q2 lock); Intelligence refactor; communications cascade refactor; **(c)'s 8 producer sites refactor mapped 1:1 per site → provenance_kind + task_type_key + category.**

10. **Three-tier scope inheritance** — Shared resolver; Q8 templates defer to v2 documented.

11. **Customer-facing v1/v2/v3 forward-compat** — Q4 lock honored; schema fields enable forward-compat without v1 portal implementation.

12. **Operational coexistence per existing substrate** — 12 dispositions specified per surface (AgentAnomaly → v2 adapter, SafetyProgramGeneration → v2 adapter, etc.).

13. **Subscriber registry** — Q7 lock. 7 event types; 6 v1 subscribers; sync-in-v1 + persistent log v2; idempotency per subscriber.

**Phase 3 aggregate v1 design surface:** ~8,980 LOC. Within ±15% of Phase 2's ~8,000 estimate. Confirmed Phase 4 split required (Phase 0 §10 trigger: v1 >6,000 LOC).

**Phase 3 natural split surfaced:**
- v1.0 (~5,500 LOC) = schema + lifecycle + creators + Pulse/briefings wire + (c) refactor + event substrate
- v1.5 (~3,500 LOC) = routing + visibility + 5 task type plugins + workflow nodes + Focus + Intelligence + comms cascade

Phase 4 was scheduled to adjudicate this split and ship v2/v3 phasing alongside. **`/tmp/` rotation at 20:12 wiped all deliverables before Phase 4 could dispatch.**

### 2.6 May 24, 2026 — `/tmp/` rotation loss event

Machine rebooted; tmpfs wiped. All five `/tmp/task_substrate_v2_*.md` files lost. (c) investigation's three `/tmp/c_investigation_*.md` files also lost. v1 investigation's five `/tmp/task_substrate_*.md` files also lost. Total ~35,500 words across the lineage.

Operator surfaced four recovery options + I proposed Option E (consolidated state doc + Phase 4 dispatch). Operator selected Option E with broad scope (full lineage, not just v2 investigation).

This document is the Option E deliverable.

---

## 3. What v1 investigation got right and what it missed

Captured for lineage. Future-Claude reading this document in 6+ months should understand both arcs honestly.

**v1 investigation got right:**

- The notification dispatch gap was real. 11/11 silent-by-default triage queues was empirically true and operationally consequential. The (c) work that shipped from the v1 investigation's verdict closed a genuine platform-correctness gap.
- The producer-site cohort for (c) was correctly identified. 11 producer sites at canonical state-transition points; 4-AgentAnomaly convergence at `base_agent.py:102`; aftercare at `aftercare_adapter.py:204`. Phase 1 audit during (c) investigation arc verified the cohort against actual code.
- The recipient-grain reasoning that produced the aftercare category split (`funeral_followup_pending` separate from `agent_anomaly_pending`) was correct. v2 investigation did not relitigate it.
- The bounded-decision discipline applied throughout v1 investigation produced operator-decision-shaped output, not analysis sprawl. The investigation-first arc discipline worked.

**v1 investigation missed:**

- The existing `Task` model + `task_service.py` + `task_triage` queue + `_build_tasks_item` stub + `task_assigned` notification category were not in the 31-surface inventory. These were in code at the time of v1 investigation's Phase 1 audit. The inventory was audit-incomplete.
- The H2 verdict ("no tasks table; no task VaultItem item_type") was empirically false at the time it was made — there is a `tasks` table; it just isn't VaultItem-resident yet.
- The forward-looking question (does the platform need task substrate to make planned capabilities possible) was never asked. v1 investigation only asked the backward-looking question (do existing surfaces share enough to justify substrate). The May 21-22 conversation made forward-looking architectural claims that v1's framing didn't engage with.

**Why the miss happened:**

The v1 investigation was dispatched from a compressed summary of the May 21-22 conversation rather than from the conversation itself. The compression collapsed forward-looking architectural claims into a structural restatement that lost depth. The dispatch's framing ("two competing hypotheses to test, not assume") presumed open-ended hypothesis adjudication when the May 21-22 conversation had already taken a position. Inventory phase didn't grep for existing `tasks`-related substrate explicitly because the framing didn't suggest task substrate might already exist; the framing presumed substrate either existed-as-the-31-surfaces-collectively or didn't exist as substrate at all.

This is a session-conduct learning filed forward to canon-update: when an operator surfaces an architectural framing from a parallel chat, the originating chat is primary source material. Investigations dispatched against compressed summaries inherit the compression's lossiness.

**(c) shipping correctness regardless:**

(c) was framed as "notification-shared-discipline closing the silent-by-default gap" rather than "task-creation event substrate." Same code; different mental model. The mental-model difference is what made v2 investigation necessary. (c) shipped useful platform correctness that future task substrate work builds on; it didn't ship the wrong code, it shipped the right code framed inadequately.

---

## 4. Operator locks across all phases

Captured verbatim from session transcript. These are the decisions that survive the deliverable loss and that Phase 4 + Phase 5 dispatch against.

### 4.1 v1 investigation operator decisions

- **Hypothesis adjudication accepted:** Partial H2 with H1-shaped projection-view warranted.
- **Recommendation accepted:** Sequenced (c)→(d). (c) dispatched immediately. (d) deferred-pending-operator-observable-Monday-morning-workflow-signal.
- **Architecture-observable signals explicitly rejected as (d) triggers.** Only operator-observable workflow shape signals trigger (d) dispatch.

### 4.2 (c) investigation operator decisions

- **Lock 1 refinement:** 9 §19 categories (originally 8). Aftercare splits from `agent_anomaly_pending` to dedicated `funeral_followup_pending` for recipient-cohort grain correctness.
- **Phase A.0 absorbed inline:** Single round-trip at build arc opening turn, not separate document round-trip.

### 4.3 (c) build arc operator decisions

- **Phase A.0 slug resolution:** `funeral_followup_pending` → new `fh_cases.aftercare` permission slug (with recipient-grain rationale comment at registration site). `workflow_review_pending` → existing `admin` permission slug.
- **Helper LOC overshoot absorbed:** ~75 vs ~70 trigger threshold; docstring + circular-import safeguard honest overshoot, not scope creep.
- **Backfill scope overshoot absorbed:** ~440 vs ~120-180 prefigured; per-substrate handler scaffolding × 7 substrate cohorts at ~50-60 LOC each. Honest scaffolding over compressed cleverness.

### 4.4 v2 investigation Phase 0 operator decisions

- **(c)-integration framing:** Default (a) leaning — (c) is foundation; task substrate adds persistence + lifecycle + consumers on top. (Subsequently revised by operator at Phase 1 → Phase 2 gate; see Revised Lock 1.)
- **Schema-shape pre-commit:** VaultItem `item_type='task'` extension as working hypothesis per BRIDGEABLE_MASTER §3.24 canonical pattern.
- **Reminders coexistence:** Phase 3 surfaces options with reasoning; operator picks at Phase 3 → Phase 4 gate.

### 4.5 Revised Lock 1 (substantive Phase 1 → Phase 2 framing shift)

Operator revised at Phase 1 → Phase 2 gate based on Phase 1's surfacing that (c) overlaps with 5 of 18 in-vision capability rows. Original Lock 1 framing (notification-only-event-firers + parallel task substrate) accepted the two-sources-of-truth risk; revised framing rejects it.

**Revised Lock 1 verbatim:** (c)'s producer sites become task-creation hooks in v1. Notification dispatch fires from task-creation events via task lifecycle, not parallel to task creation. (c)'s helper unchanged; call-sites shift from producer-direct to task-event-driven. Phase 2 treats (c)'s 8 producer integration calls as refactor-existing under revised Lock 1.

This means (c) refactor is v1 scope, not parallel-substrate work.

### 4.6 v2 investigation Phase 2 → Phase 3 operator decisions

- **Q1 — Schema shape:** (d) hybrid. VaultItem with `item_type='task'` + `task_details` join table for task-specific fields. Existing `tasks` table content migrates to this shape via r107 + backfill. Phase 3 verifies 1:1 enforcement and adjudicates exact join table shape.
- **Q2 — Pulse Personal layer:** Wire existing `_build_tasks_item` stub against post-Q1 query shape (~50-80 LOC).
- **Q3 — Triage queue unification:** Defer 10-non-task-triage-queue folding to v2. v1 focuses on substrate foundation + (c) refactor + 1-2 highest-leverage consumer integrations.
- **Q4 — Cross-realm v1 scope:** Operator-only v1. v2 adds family portal tasks. v3 adds contractor portal tasks.
- **Q5 — Reminders:** Fold into task substrate v1 via lifecycle-state-pattern. `reminder` enum value in VaultItem.item_type stays per BRIDGEABLE_MASTER §3.24 canon; usage gets folded into `item_type='task'` with reminder-shaped lifecycle. Phase 3 articulates the dual lifecycle split.
- **Q6 — Plugin categories:** Three categories — task creators + task surfaces + task type behaviors.
- **Q7 — Event substrate:** Subscriber registry shape.
- **Q8 — Task templates:** Defer to v2.

### 4.7 v2 investigation Phase 3 → Phase 4 operator decisions

- **v1.0 / v1.5 split:** Single v1 arc with two internal phases (v1.0 substrate + v1.5 integration) and explicit operator-confirm gate between phases. Substrate validates against staging before integration phase dispatches. v1 closes when v1.5 lands.
- **Reminders fold pacing:** Lifecycle-state-pattern v1, as specified in design §2. Already locked at Q5; design §2 has the dual state machine specified.
- **(c) refactor sequencing:** v1.5, not v1.0. v1.0 ships substrate clean (net-new additive); v1.5 wires (c) refactor + other integration work against validated substrate.
- **Migration sequencing:** r107 + backfill same-commit at v1.0 close. Per (c) build arc pattern.
- **Five task type plugins v1:** As specified — `generic_task`, `review_approval_task`, `scheduled_recurring_task`, `customer_communication_task`, `anomaly_resolution_task`. Sixth (`scheduled_audit_task` or similar) defers to v2 if integration surfaces need.
- **Two routing modes v1:** `direct_user` + `round_robin` sufficient. `escalation_chain` / `permission_based_broadcast` / `capacity_aware` defer to v2.
- **Three workflow nodes v1:** `create_task` + `wait_for_task_completion` + `route_on_task_outcome` sufficient. `cancel_task` / `update_task` / `query_tasks` defer to v2.

### 4.8 v2 investigation post-loss operator decisions

- **Recovery option:** Option E (consolidated state doc + Phase 4 dispatch).
- **Doc location:** `docs/investigations/task_substrate_v2_state.md` (this document).
- **Consolidation scope:** Broad — full task substrate arc lineage.

---

## 5. Architectural trajectory

Synthesis of where the substrate ends up after v2 investigation Phase 3 close. Phase 4 phasing recommendation dispatches against this trajectory; Phase 5 v1 build prompt re-derives implementable specifics against current code at this trajectory.

### 5.1 Schema shape

VaultItem with `item_type='task'` (12th value added to existing 11-value enum) + `task_details` join table for task-specific fields. 1:1 enforced at model layer. Existing `tasks` table content migrates to this shape via r107 + backfill at v1.0 close.

Task-specific fields living in `task_details`:
- `assignee_realm` / `assignee_user_id` / `assignee_portal_user_id` (forward-compat for v2 customer-facing portal extension)
- `lifecycle_shape` enum (action / reminder)
- Provenance polymorphic FK (12 `provenance_kind` values + `provenance_ref` polymorphic key)
- Visibility enum (5 values; v1 enforces operator-only; schema supports portal-shape for v2)
- Idempotency key composite `(provenance_kind + provenance_ref + event_kind)` as partial-unique index
- Standard task fields (priority, due_date, status, assigned_at, completed_at, resolution_outcome, suppression_key)

VaultItem fields stay clean of task-specific concerns; consumers query through service-layer + Task façade pattern that abstracts table layout. The 8 existing Task consumers continue working without rewrite.

### 5.2 Lifecycle

Dual state machines:

**Action shape** (task that requires completion):

```
created → assigned → in_progress ↔ blocked → done | cancelled
```

**Reminder shape** (informational, dismissible):

```
informational → acknowledged | dismissed
```

Transition tables specified per design §2. Backward-compat mapping from existing 5-state machine in `tasks` table content (5-state maps cleanly into action-shape). Resolution_outcome captures completion semantics. Suppression key prevents re-firing.

### 5.3 Provenance + association

Tasks carry "where they came from" via polymorphic provenance and "what they're about" via polymorphic associations. 12 `provenance_kind` values enumerated in design §3 (workflow_step, intelligence_observation, manual_creation, communication_inbound, integration_event, shelf_parking, coaching_observation, scheduled_recurring, triage_event, focus_completion, anomaly_detection, system_internal). Composite idempotency key prevents duplicate task creation on retry.

### 5.4 Routing + assignment

`task_routing_rules` table; three-tier resolver (platform default / vertical-specific / tenant customization). Permission-gated assignment. v1 ships two routing modes: `direct_user` (manual assignment, fixed-recipient task creation) and `round_robin` (load-distributes across role members). Escalation and capacity-aware modes defer to v2.

### 5.5 Visibility + access

5-value enum (per design §5). Operator-only enforcement in v1. Schema supports portal-shape for v2 family portal + v3 contractor portal extension. Tenant + portal query filters specified inline for both v1 operator-only and v2/v3 portal modes.

### 5.6 Plugin architecture

Three new plugin categories registered against existing Bridgeable Tier R1 plugin pattern:

- **Task creators** (workflow steps, Intelligence observations, communications, shelf parking, manual creation, 10 triage queue adapters in v2). Contract: input shape, output guarantees, failure modes, configuration shape, registration mechanism.
- **Task surfaces** (list views, detail views, creation forms, Pulse stub, briefings consumption, 6 future surface implementations). Visual editor authors per Studio canon.
- **Task type behaviors** (5 v1 plugins: generic_task, review_approval_task, scheduled_recurring_task, customer_communication_task, anomaly_resolution_task). Plugins register lifecycle behaviors, surface defaults, routing defaults against generic substrate.

### 5.7 Integration shape

**v1.0 substrate phase:**
- VaultItem extension + `task_details` table + r107 migration + backfill
- Dual lifecycle state machine implementation
- Subscriber registry (7 event types; sync-in-v1; idempotency per subscriber)
- Three plugin category contracts + registration mechanism
- Five task type behavior plugins
- Task service layer + Task façade for backward-compat
- v1.0 internal tests + migration tests + backfill tests

**v1.5 integration phase:**
- Pulse Personal layer `_build_tasks_item` stub wired
- Briefings task-substrate consumption (3 new helpers per design §9)
- (c) refactor: 8 producer sites shift from producer-direct dispatch to task-event-driven dispatch via subscriber registry
- 3 workflow node types (create_task, wait_for_task_completion, route_on_task_outcome)
- Focus extension column (task→Focus relationship)
- Intelligence task-creation refactor
- Communications cascade task-creation
- Two routing modes (direct_user, round_robin)
- Visibility enforcement (operator-only in v1)
- v1.5 integration tests + (c) parity regression + Pulse render tests + briefings consumption tests

### 5.8 Operational coexistence

12 dispositions per existing substrate (design §12). High-level shape:
- AgentAnomaly → v2 adapter creates tasks from anomaly rows
- SafetyProgramGeneration → v2 adapter
- WorkflowRun awaiting-state → v2 adapter
- Triage queue items → v2 adapter (10 non-task queues)
- Focus sessions → v1.5 Focus extension column
- Intake adapter submissions → v2 adapter or absorbed into communications cascade in v1.5
- Document review states → v2 adapter
- VaultItem item_types other than 'task' → orthogonal; unchanged
- Calendar VaultItems → orthogonal; unchanged in v1 (reminder-shape covers some calendar-event-like patterns)
- Onboarding checklist → v2 adapter or absorbed into generic_task
- OrderPersonalizationTask → renamed/refactored in v2 task type
- Email-classification cascade → v1.5 communications integration

### 5.9 Customer-facing v2/v3

Schema supports portal-shape; v1 enforces operator-only at query-filter layer. v2 ships family portal task surfaces + visibility refinement for unauthenticated/magic-link contexts. v3 ships contractor portal task surfaces + Workshop UI task management + customer-facing operational extensions.

---

## 6. v1.0 / v1.5 / v2 / v3 sequence shape

Per operator lock at Phase 3 → Phase 4 gate. Phase 4 phasing recommendation refines and adds upgrade-signal specification.

**v1 — single arc, two internal phases:**

- **v1.0 substrate phase (~5,500 LOC):** schema + lifecycle + creators + Pulse/briefings wire + (c) refactor capability + event substrate. Net-new additive; no existing surface changes behavior. Internal operator-confirm gate before v1.5 dispatches.
- **v1.5 integration phase (~3,500 LOC):** routing + visibility + 5 task type plugins + workflow nodes + Focus extension + Intelligence refactor + communications cascade + (c) refactor execution against validated substrate.

v1 closes when v1.5 lands.

**v2 (~6,000-10,000 LOC; probably 2-3 sub-arcs grouped under v2 banner):**

- 10 non-task triage queue task-creation adapters (fold producer-side state-transitions into task substrate via adapter pattern; consumer surfaces start reading through task substrate)
- Family portal task surfaces + visibility scoping for unauthenticated/magic-link contexts
- Escalation routing mode
- Additional workflow nodes if integration surfaces need (cancel_task, update_task, query_tasks)
- Task templates / authored task creators via visual editor
- 6th task type plugin if integration surfaces need
- Subscriber registry persistent log (sync-only in v1; persistent log v2)
- AgentAnomaly + SafetyProgramGeneration + WorkflowRun adapter implementations

**v3 (largest scope; probably multiple arcs):**

- Contractor portal task surfaces + portal-specific scoping
- Coaching pattern materialization (observe-and-offer produces tasks)
- Shelf parking task creation
- Communications deeper integration (incoming-message-typed task creation)
- Workshop UI task management
- Customer-facing operational extensions
- AR-future considerations (spatial task UI; deferred but architecturally seeded)

**Upgrade signals between phases (Phase 4 specifies operator-observable shape; not architecture-observable):**

- v1.0 → v1.5: operator-confirms v1.0 substrate validates against staging use. No specific external signal; internal verification gate.
- v1 close → v2 dispatch: Sunnycrest staff + Hopkins directors describe Monday-morning workflow shape such that 10 non-task triage queues being unfolded creates real friction. Specific friction descriptions, not architecture-observable thresholds.
- v2 close → v3 dispatch: Customer-side (family or contractor) signals that portal-shape tasks would meaningfully change their workflow. Customer-side friction descriptions.

These are the broad-strokes signal shapes; Phase 4 specifies exactly.

---

## 7. Canon candidates filed forward

Filed for the eventually-dispatching canon-update arc. Currently ~51 unfiled candidates accumulated across the lineage; this section enumerates the ones surfaced specifically by this lineage.

**From v1 investigation:**
1. Investigation-first arc discipline applied at investigation altitude (audit-first phase within investigations; operator-observable upgrade signals over architecture-observable; sequenced not bundled candidate-move relationships; build-arc ownership partitioning of open questions).

**From task substrate arc nesting:**
2. Investigation arcs nest cleanly when each closes its own bounded decision; sequence is investigation-locks-hypothesis → next-investigation-locks-scope → build-arc-executes-against-locked-scope; resist absorbing later arcs' work into earlier arcs to save round-trips.

**From (c) build arc:**
3. Dynamic permission inheritance via subtraction-from-all-keys lets new permission slugs land without per-permission role-seed updates.
4. Backfill scripts servicing N distinct substrates carry roughly N × ~50-60 LOC of handler scaffolding; prefigure accordingly.

**From v2 investigation Phase 3:**
5. CLAUDE.md task-centric statement (per May 21-22 conversation §"A canonical articulation worth adding to CLAUDE.md").
6. CLAUDE.md task substrate section.
7. PLUGIN_CONTRACTS.md: 3 new categories (task creators / task surfaces / task type behaviors).
8. BRIDGEABLE_MASTER.md §3.24 — 12th item_type ('task') ratified; relationship to deferred 'reminder' item_type documented (reminder lifecycle folds into task substrate via lifecycle-shape; reminder item_type stays in enum but usage maps to task).
9. PLATFORM_ARCHITECTURE.md §3.4 — task references in Pulse Personal layer; `_build_tasks_item` documented as canonical.
10. PLATFORM_ARCHITECTURE.md §5 — task references in Focus; task→Focus relationship documented.
11. DECISIONS.md — hybrid-schema entry (VaultItem + task_details).

**From `/tmp/` rotation loss event:**
12. Investigation deliverables ship to persistent storage (`docs/investigations/`), not `/tmp/`. `/tmp/` remains appropriate for transient computation; deliverables that future arcs cite back to require git-tracked persistence.

**From v1 investigation lineage retrospective:**
13. When an operator surfaces an architectural framing from a parallel chat, the originating chat is primary source material. Investigations dispatched against compressed summaries inherit the compression's lossiness; the audit-completeness criterion should explicitly include "grep for existing substrate that the framing might assume doesn't exist."

13 candidates from this lineage. Plus the ~38 previously accumulated across WB cycle + studio nav arc = ~51 total filed forward.

---

## 8. Honest limitations of this document

What this document preserves at high fidelity:

- All operator locks across all phases (verbatim from session transcript)
- Architectural decision shapes (schema direction, lifecycle structure, plugin categories, routing modes, workflow nodes, sequence shape)
- LOC envelopes and split shapes (numbers and proportions)
- Phase-level conclusions and findings (Phase 1 capability cohort by name; Phase 2 headline existing-substrate finding; Phase 3 13-section design by section)
- Lineage timeline and arc relationships
- Canon candidates surfaced

What this document preserves at medium fidelity:

- Capability cohort enumeration (names + brief descriptions; full Phase 1 8-field rows with file:line citations are lost)
- Gap analysis findings (headline finding + Revised Lock 1 verification + 4-way tag pattern preserved; per-row gap analysis lost)
- Substrate design section conclusions (section-level decisions; full implementable specifics — column inventory text, plugin contract input/output text, integration contract diagrams — are lost)

What this document explicitly does NOT preserve:

- Full file:line citations from Phase 1 audit (22 rows × ~5 citations = ~110 citations lost)
- Exact schema column names and types from Phase 3 design
- Exact plugin contract input/output text from Phase 3 design
- Full primary source citation patterns from Phase 1
- The four (c) investigation arc deliverables and v1 investigation arc deliverables in their original form

What gets re-derived in Phase 5 build prompt against current code rather than relying on this doc:

- Implementable schema column names and types (against existing `Task` model + VaultItem schema + new `task_details` design)
- Plugin contract input/output text (against existing Tier R1 plugin pattern + Phase 3 §6/7/8 conclusions)
- Migration r107 schema delta (against current `tasks` table shape + VaultItem schema)
- Test cohort scope (against existing test patterns in `notification_service` tests + Task model tests)
- Subscriber registry contract details (against existing similar substrate patterns + Phase 3 §13 conclusions)

The discipline going forward: Phase 5 build prompt agent reads this document + Phase 4 phasing + current code state + does substrate-design verification as part of build prompt drafting. Phase 3's lost implementable specifics aren't re-shipped as a separate Phase 3 redo; they're re-derived in service of Phase 5 build prompt against current code, which is the right discipline anyway (build prompts should ground against current code, not against potentially-stale investigation deliverables).

---

## 9. What dispatches next

Phase 4 phasing recommendation dispatches against this consolidated state document + primary source (re-pasted at start of consolidation). Phase 4 produces `docs/investigations/task_substrate_v2_phasing.md` (persistent storage per new discipline) covering:

- v1.0 scope final-lock (against Phase 3 trajectory in §5 above)
- v1.5 scope final-lock
- v2 scope shape + sub-arc grouping
- v3 scope shape
- Upgrade signals between phases (operator-observable, not architecture-observable)
- Cross-version concerns (data migration coexistence across phases; canon-update interleave; STATE.md narrative across phases)
- Honest cost (total LOC across v1+v2+v3; total arc count; total tests; total migrations)
- Open questions Phase 1-3 surfaced that need operator decision before v1 dispatches

Phase 5 v1 build prompt drafts against Phase 4 + this consolidation + current code state, ships dispatch-ready build prompt for v1.0 substrate arc.

v2 + v3 dispatch as future arcs when respective upgrade signals surface.

The task substrate arc remains the active arc. (d) projection-view from v1 investigation lineage genuinely subsumes into v1.5 Pulse Personal layer wire + briefings consumption; v1 investigation's (d)-deferred-pending-signal is closed by v2 investigation's locked v1 scope.

---

*Document captured May 24, 2026 by Opus in service of Option E recovery from `/tmp/` rotation loss event. Lineage spans May 21-22, 2026 (primary source) through May 24, 2026 (v2 investigation Phase 3 close + rotation loss + this consolidation).*
