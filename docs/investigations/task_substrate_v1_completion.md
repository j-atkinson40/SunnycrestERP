# Task Substrate v1 Completion

> **Document purpose.** This document captures the v1 task substrate arc closure at commit `1c8dbbd`. It exists as a forward-reference for future arcs (canon-update, v2 sub-arcs) reading the v1 lineage to understand what shipped, what's deferred, what disciplines emerged, and what the canon-candidate filing pool contains.
>
> This is not investigation-recovery work (the v2 state doc at `bc7c4ba` handled that). This is post-arc-close completion documentation, written while the architectural reasoning is fresh in working memory, before context decay across session boundaries.
>
> **Persistent storage from start** per the discipline established by the `/tmp/` rotation loss event during v2 investigation Phase 0-3. Future v2 and v3 sub-arcs that close on substantial substrate work should produce equivalent closure artifacts at this directory.

---

## 1. v1 arc shape and commits

Task substrate v1 shipped as a single arc with three internal phases, single commit per phase, all commits within v1 arc identity per Lock A revision.

**Lock A original specification:** "Single commit at v1.5 close" (per v2 investigation Phase 3 → 4 operator lock).

**Lock A revised this session:** "Three commits within v1 arc; v1 closes after B3 lands."

**Reason for revision:** Phase B execution surfaced that ~3,500 LOC + 8-site refactor + parity discipline didn't safely fit single-shot agent execution + single-commit-no-rollback window. Agent surfaced honestly; operator revised the lock; v1 shipped three coherent commits rather than one big-bang.

**The three commits:**

| Commit | Phase | Scope | LOC | Tests added |
|---|---|---|---|---|
| `2fba161` | B1 — Foundation | Phase A v1.0 substrate + r108 Focus extension migration | ~2,880 production + 133 (126 Phase A + 7 r108) | 133 |
| `a400d1b` | B2 — (c) refactor | 8 producer sites refactored to task-creation-event-driven dispatch with parity discipline; subscriber notification_dispatcher body substantive | ~1,000 (+1,122/-154) | 19 |
| `1c8dbbd` | B3 — Consumer integration; closes v1 | Pulse wire + briefings + 4 subscriber bodies + 3 workflow nodes + Focus linkage + Intelligence canonical entry + customer_communication_task dispatch + routing rules (r109) + visibility enforcement | ~2,500 | 31 |

**v1 arc totals:** ~8,200 LOC across 3 commits; ~284 task-substrate-specific tests (Phase A 126 + B1 7 + B2 19 + B3 31 + ~101 verified through B3); migration heads r106 → r107 → r108 → r109; ~8 hours of substantive build agent execution + operator decision time.

**Calibration band:** Phase 3 design estimated ~8,980 LOC for v1; Phase 4 phasing distributed across two phases (~5,500 + ~3,500); execution landed at ~8,200 (~9% under estimate). Within calibration discipline ("WB-8 ±5% pattern"; v1 lands at WB-8-band given investigation-locked + substrate-maturity-findings + restraint-discipline).

---

## 2. What's in the substrate

The May 21-22, 2026 conversation's claims that became substrate code at v1 close:

### Foundation (B1)

- **Tasks as Vault items.** VaultItem `item_type='task'` (12th value added to existing 11-value enum) + `task_details` join table with 21 columns + 6 indexes + composite partial-unique idempotency constraint. Q1 (d) hybrid schema shape; existing `tasks` table preserved with dual-write transitional state pattern.
- **Provenance.** 12 `provenance_kind` values (workflow_step, intelligence_observation, manual_creation, communication_inbound, integration_event, shelf_parking, coaching_observation, scheduled_recurring, triage_event, focus_completion, anomaly_detection, system_internal). Polymorphic ref via `(provenance_kind, provenance_ref_type, provenance_ref_id)`. Composite idempotency key `(provenance_kind + provenance_ref + event_kind)` partial-unique.
- **Dual lifecycle state machine.** Action shape: `created → assigned → in_progress ↔ blocked → done | cancelled`. Reminder shape: `informational → acknowledged | dismissed`. Backward-compat mapping from existing 5-state for backfill.
- **Focus extension** (r108). `focus_session.task_id` FK → `vault_items.id` ON DELETE SET NULL, nullable, indexed. Forward-only; existing focus_sessions retain task_id=NULL.
- **Subscriber registry substrate.** 7 event types × 6 v1 subscribers; sync dispatch with isolated try/except per subscriber. v1.0 ships registration + scaffolding; handler bodies fill in across B2 + B3.
- **3 plugin contracts** via Python Protocol pattern. Task creators (TaskCreatorProtocol), task surfaces (TaskSurfaceProtocol — forward-compat for visual-editor work v2+), task type behaviors (TaskTypeBehaviorProtocol).
- **5 task type behavior plugins.** generic_task (catch-all), review_approval_task (active on_status_change reading metadata.outcome → resolution_outcome), scheduled_recurring_task (round_robin routing override + on_created hook), customer_communication_task (v1.0 stub for outbound dispatch, wired in B3), anomaly_resolution_task (marks AgentAnomaly.is_resolved=True on done with best-effort try/except).
- **Task service layer + Task façade.** Preserves 8 existing Task consumers via atomic VaultItem + task_details creation in single transaction. Service-layer abstraction means consumers query through façade rather than direct table access.
- **Backfill script.** Option A idempotent + ENVIRONMENT=production guard. Legacy 5-state → action-shape mapping. Catches existing `tasks` table content cleanly on first deploy.

### Producer refactor (B2)

- **(c)'s 8 producer sites refactored to task-creation-event-driven dispatch.** Producer call-sites shift from direct `notify_users_with_permission` calls to `task_service.create_task` calls. Task creation fires `TaskCreated` event → subscriber registry's `notification_dispatcher` handler dispatches notification via `notify_users_with_permission` from inside the event handler.
- **(c)'s `notify_users_with_permission` helper unchanged.** Call surface preserved; only the call-site location shifts.
- **Parity discipline verified.** 19 parity tests cover all 8 producer sites with recipient cohort + category + payload + self-suppression + idempotency parity. Existing notification dispatch behavior preserved bit-for-bit at recipient side.
- **Dual-write at site #1.** Legacy `task_service.create_task` keeps writing legacy Task row + calls `create_task_with_provenance` for substrate side. Inline `create_notification` removed from legacy path. Consolidation deferred to v2+ post-substrate-maturation arc.
- **Metadata-based notification_permission_key.** Producer sites pass `metadata={"notification_permission_key": "...", ...}` to `create_task_with_provenance`. Phase A plugin contracts unchanged. Plugin-field promotion target for v2+ consolidation.
- **Metadata-presence discriminator with defensive assertion.** Subscriber checks `metadata.notification_permission_key`; if present → cohort dispatch; if absent → direct-user dispatch. Defensive assertion checks task_type against cohort-allowlist (review_approval_task, scheduled_recurring_task, customer_communication_task, anomaly_resolution_task); if mismatched, log error + raise.

The 1:1 mapping table of 8 producer sites:

| Producer site | provenance_kind | task_type_key | category |
|---|---|---|---|
| `task_service.create_task` (legacy dual-write) | manual_creation | generic_task | task_assigned |
| `social_service_certificate_service.py:160` | system_internal | review_approval_task | ss_cert_pending_approval |
| `base_agent.py:103` (3 accounting AgentAnomaly) | anomaly_detection | anomaly_resolution_task | agent_anomaly_pending |
| `base_agent.py:103` (month_end_close) | system_internal | review_approval_task | agent_job_awaiting_approval |
| `aftercare_adapter.py:204` | scheduled_recurring | scheduled_recurring_task | funeral_followup_pending |
| `catalog_fetch_adapter.py:256` | system_internal | review_approval_task | catalog_sync_pending_review |
| `safety_program_generation_service.py:177` | system_internal | review_approval_task | safety_program_pending_review |
| `workflow_engine.py:812` | workflow_step | review_approval_task | workflow_review_pending |
| `classification/dispatch.py:377` | communication_inbound | customer_communication_task | email_unclassified_pending |

### Consumer integration (B3)

- **Pulse Personal layer wired.** `_build_tasks_item` at `personal_layer_service.py:111` no longer returns None; queries VaultItem WHERE item_type='task' joined task_details, filtered by user assignment + visibility + non-terminal lifecycle states.
- **Briefings 3 new helpers.** `_collect_pending_tasks_summary` + `_collect_recent_completions_summary` + `_collect_upcoming_deadlines_summary`. Briefings consume task substrate as canonical "what needs attention" source.
- **4 subscriber handler bodies substantive.** briefings_invalidator + pulse_invalidator + workflow_resumer + focus_closer all fill the v1.0 no-op stubs with real implementations following B2's notification_dispatcher pattern.
- **3 workflow node types.** create_task (workflow step creates task with current workflow run as provenance), wait_for_task_completion (workflow suspends until task reaches terminal state; workflow_resumer subscriber wires the resume), route_on_task_outcome (branches on resolution_outcome).
- **Focus task linkage active.** r108's task_id column populated at task creation when provenance is focus-relevant; focus_closer subscriber closes focus_sessions on task completion.
- **Intelligence canonical entry point.** Shipped as `tasks/intelligence_integration.py` + contract tests. Material-divergence finding: build prompt §7.6 anticipated 3-5 Intelligence call sites to refactor; grep returned zero. Agent shipped the entry point as forward-compat substrate rather than refactoring nonexistent callers.
- **customer_communication_task outbound dispatch wired.** Phase A v1.0 stub (logger.info only) replaced; plugin fires delivery_service on appropriate lifecycle transition. Closes the deferred-handler-body pattern for the 5th subscriber lineage.
- **task_routing_rules table** (r109). Three-tier scope resolver (platform default → vertical default → tenant customization). Two routing modes shipped: direct_user + round_robin.
- **Visibility enforcement.** 5-value enum (private, team, tenant, shared, public). v1 enforces operator-only (private, team, tenant); cross-tenant shared + public defer to v2/v3 portal work. Query-filter layer applied at Pulse + briefings + route handlers.

### Discipline verifications across all 3 commits

- **8 existing Task consumers verified working unchanged.** `test_task_and_triage.py` 31/31 green at every commit checkpoint. Service-layer + Task façade backward-compat held across all 3 sub-arcs.
- **Phase A substrate locked-as-shipped.** B2 and B3 didn't modify task model, lifecycle module, plugin contracts, or plugin implementations (except customer_communication_task's documented deferred outbound dispatch).
- **`notify_users_with_permission` helper unchanged.** v1 didn't touch the helper; subscribers + producers do their work without modifying the helper.
- **Forward-only discipline.** No backfill for B2 or B3. Pre-B2 notifications remain historical fact; substrate represents go-forward operation.

---

## 3. What's deferred to v2/v3 (forward-compat substrate ships at v1; wiring later)

Per phasing doc §3-§4 with upgrade-signal specifications per §5:

### v2 sub-arcs (operator-observable signal triggers)

- **v2a — 10 non-task triage queue task-creation adapters.** Each of the 10 non-task triage queues (cash_receipts_matching, ar_collections, expense_categorization, month_end_close, aftercare, catalog_fetch, safety_program, ss_cert, workflow_review, email_unclassified — note month_end_close + aftercare + catalog_fetch + safety_program + ss_cert + workflow_review + email_unclassified already covered by B2's producer refactor; the v2a work specifically targets queues whose underlying substrate isn't yet task-creation-event-driven). Adapter pattern translates queue-item-creation events to task entities. ~3,000-5,000 LOC. Investigation-first per §8.3 lock.
- **v2b — Family portal task surfaces.** PortalUser visibility + magic-link consent + family-portal task surfaces. ~1,500-2,500 LOC.
- **v2c — Substrate refinements.** escalation_chain routing mode + additional workflow nodes (cancel_task, update_task, query_tasks) + 6th task type plugin if integration surfaces need + persistent subscriber log + task templates / authored task creators via visual editor. ~1,500-2,500 LOC.

### v3 arcs (operator-observable signal triggers; per-arc pre-dispatch rescoping per §8.6)

- **v3a — Contractor portal task surfaces.** Parallel to v2b shape; PortalUser visibility for contractor cohort.
- **v3b — Coaching pattern materialization.** Coaching observations produce tasks via canonical pattern (canonical entry point ready post-v1; wiring v3b).
- **v3c — Shelf parking + communications deeper integration.** Shelf parking produces tasks (canonical entry point ready post-v1; wiring v3c).
- **v3d — Workshop UI task management.** Tenant-facing operational team management surfaces.
- **v3e — Customer-facing operational extensions.** AR-future architectural seeding preserved; spatial-UI-compatible registrations.

### Upgrade signals per phasing §5 (operator-observable, not architecture-observable)

**v1 close → v2 dispatch signal patterns:**
- Sunnycrest staff describe Monday-morning workflow as "check 10 separate queue routes" rather than "check Pulse for everything that needs attention"
- Hopkins directors describe specific friction in moving between triage queues and task surfaces
- Family-side workflow signals from Hopkins (e.g. families asking for "what's outstanding" visibility)

**v2 close → v3 dispatch signal patterns:**
- Customer-side (family or contractor) workflow descriptions indicating portal-shape tasks would meaningfully change customer workflow
- Specific friction descriptions, not architecture-observable thresholds

**Explicit anti-signals (architecture-observable rejected as triggers):** LOC thresholds, count thresholds, time thresholds, engineering preference, aesthetic-completeness, sunk-cost. Phase 4 phasing doc §5 enumerated these explicitly; v1 close inherits the same discipline.

---

## 4. Disciplines and patterns emerged

The v1 arc produced operationally-validated disciplines worth carrying forward as canon. These file alongside the ~71+ accumulated candidates the canon-update arc dispatches against post-v1.

### From v1 build arc execution

1. **Three-commit-per-substrate-arc pattern for substantively-larger arcs.** Lock A revision from single-commit-at-arc-close to three-commits-within-arc-identity is appropriate when arc scope exceeds ~3,000 LOC + parity-discipline work. Each commit independently shippable + Railway-deployable + verifiable; sub-arc commits reference parent arc identity in commit messages.

2. **Dual-write transitional state during substrate-additive arcs.** When substrate is added alongside existing implementation, dual-write keeps both write paths active during transition. Consolidation arc post-substrate-maturation unifies write paths. v1 ships dual-write at site #1 (legacy `task_service.create_task`); consolidation deferred to v2+.

3. **Metadata-based substrate extension as transitional shape.** When substrate needs producer-supplied context but plugin contracts are locked, metadata path preserves substrate-locked discipline. Plugin-field promotion is consolidation target for v2+ arcs.

4. **Subscriber discrimination via metadata-presence + defensive assertion.** When subscribers route between dispatch modes based on metadata, defensive assertion against task-type allowlist prevents failure-silent misconfigurations. Failure-loud is correct shape for substrate affecting user-observable behavior.

5. **Deferred-handler-body pattern for phased substrate.** Substrate registration ships in foundation phase; handler bodies fill in at integration phase. Pattern works for any substrate with clear consumer/producer separation where consumers can be deferred without breaking producer-side correctness. Verified across 5 subscriber handler bodies (notification_dispatcher in B2, briefings_invalidator + pulse_invalidator + workflow_resumer + focus_closer in B3).

6. **Test isolation discipline for idempotency-load-bearing substrate.** Composite-key-enforced idempotency at substrate level changes test-isolation requirements at consumer level. Tests exercising task creation use uuid-randomized provenance_ref_id per test OR explicit per-test cleanup. Hardcoded IDs across test runs collide with substrate idempotency and produce false test fragility. Filed forward to canon-update; carried as test-discipline guidance through all v1 sub-arcs.

7. **Forward-compat substrate ships when claim is real but current implementation is absent.** Build prompt §7.6 anticipated Intelligence refactor; grep revealed zero call sites to refactor; agent shipped canonical entry point as forward-compat substrate rather than absorbing scope changes silently. Capability-demand mapping should audit not just whether substrate consumes the conversation's claims, but whether substrate exists to refactor in the first place.

### From v2 investigation arc execution (filed forward through v1 closure)

8. **Investigation-first arc discipline applied at investigation altitude.** Audit-first phase within investigations; operator-observable upgrade signals over architecture-observable; sequenced not bundled candidate-move relationships; build-arc ownership partitioning of open questions.

9. **Investigation arcs nest cleanly when each closes its own bounded decision.** Sequence: investigation-locks-hypothesis → next-investigation-locks-scope → build-arc-executes-against-locked-scope. Resist absorbing later arcs' work into earlier arcs to save round-trips.

10. **Dynamic permission inheritance via subtraction-from-all-keys.** `MANAGER_DEFAULT_PERMISSIONS = get_all_permission_keys() - {users.delete, roles.delete}` lets new permission slugs land without per-permission role-seed updates. Pattern verified during (c) build arc Phase A.

11. **Backfill scripts servicing N distinct substrates carry roughly N × ~50-60 LOC of handler scaffolding.** Pattern observed in (c) backfill (7 substrate cohorts × ~50-60 LOC = ~440 LOC actual vs ~120-180 prefigured). Prefigure accordingly for substrate-additive arcs with multiple producer-cohort substrates.

12. **Investigation deliverables ship to persistent storage** (`docs/investigations/`), not `/tmp/`. `/tmp/` remains appropriate for transient computation; deliverables that future arcs cite back to require git-tracked persistence. Established by the `/tmp/` rotation loss event at 20:12 during v2 investigation Phase 3 close; canonized this session.

13. **When operator surfaces an architectural framing from a parallel chat, the originating chat is primary source material.** Investigations dispatched against compressed summaries inherit the compression's lossiness. Audit-completeness criterion should explicitly include "grep for existing substrate that the framing might assume doesn't exist."

### From v1 build arc dispatch-spec corrections

14. **Build-prompt-spec failure pattern: "X refactor" can hide architectural decisions when call sites use different helpers OR depend on producer-supplied context the substrate doesn't carry.** Build prompts at refactor scope should specify subscriber/consumer-side mechanics, not just producer-side mapping. v1.0 → v1.5 gate-spec correction (pre-commit staging-DB validation assumed Railway access that auto-deploy pattern doesn't provide), B2 (c)-refactor 4-decision correction (call-site mechanics required substrate-aware decisions), B3 Intelligence-refactor correction (refactor target empty; canonical entry point ships forward-compat) — three instances of one pattern.

15. **Build arc commit granularity scales with parity-discipline complexity.** Sub-arcs deserving isolated commit boundaries are those where verification (parity, idempotency, migration safety) needs to be the sub-arc's primary success criterion rather than bundled with other substantive substrate changes. v1's B1 (foundation) + B2 ((c) refactor parity-isolated) + B3 (consumer integration) shape.

---

## 5. Canon candidate filing pool

~71+ candidates accumulated across the lineage. Detailed enumeration lives in `docs/investigations/task_substrate_v2_state.md` §7 (entries 1-12) plus subsequent additions surfaced during v2 Phases 4-5 + v1 build arc B1-B2-B3 execution.

The canon-update arc dispatches next per Phase 4 phasing doc §8.5 lock ("canon-update arc dispatches post-v1, pre-v2"). Three-phase shape (Phase 0 aggregation against substantively-broad scope → Phase 1 cull against canon-worthiness criteria → Phase 2 draft entries with explicit supersession references where prior canon shifts).

Specific candidates surfaced during v1 build arc execution and filed forward:

- Three-commit-per-substrate-arc pattern (entry 14 in this artifact)
- Dual-write transitional state pattern (entry 2)
- Metadata-based substrate extension as transitional shape (entry 3)
- Subscriber discrimination via metadata-presence + defensive assertion (entry 4)
- Deferred-handler-body pattern for phased substrate (entry 5)
- Test isolation discipline for idempotency-load-bearing substrate (entry 6)
- Forward-compat substrate when implementation absent (entry 7)
- Build-prompt-spec failure pattern (entry 14)
- Build arc commit granularity scales with parity-discipline complexity (entry 15)

Plus v2 investigation arc's previously-filed candidates 1-13 from state doc §7.

---

## 6. Production state at v1 close

- **HEAD:** `1c8dbbd` on main; Railway deployed cleanly
- **Migration head:** r109 (`r106 → r107 task_substrate → r108 focus_session_task_extension → r109 task_routing_rules`)
- **Task substrate test cohort:** ~284 substrate-specific tests (Phase A 126 + B1 7 + B2 19 + B3 31 + neighbor verification ~101) plus existing regression suites (`test_task_and_triage` 31/31, `test_vault_v1d_notifications` 35/35, `test_briefings_phase6` 26/26) all green
- **8 existing Task consumers verified working unchanged** across all 3 commits
- **Working tree state:** clean apart from 114 stale Playwright screenshot deletions that have remained untouched across this entire session (continuing from prior sessions; substantively impressive discipline durability)
- **Tenant-specific behavior preserved:** Sunnycrest + Hopkins tenant configurations unchanged; no migration-time tenant-specific data changes
- **External notification behavior preserved bit-for-bit** at recipient side per parity discipline; internal call graph changed (producer-direct → task-creation-event-driven); user-observable behavior identical

---

## 7. What this enables that didn't exist before v1

The May 21-22 conversation framed task substrate as connective tissue tying together the platform's capabilities. v1 makes that operationally true for the v1 cohort:

- **Sunnycrest staff opening platform Monday morning see pending tasks aggregated in Pulse Personal layer** rather than scattered across 11 separate queue routes. The substrate is now the canonical "what needs attention" source.
- **Briefings draw from task substrate** as canonical source rather than synthesizing from inconsistent per-feature substrates. Morning briefings + weekly summaries surface task-shaped pending work coherently.
- **Workflow runs can create tasks at steps, suspend pending completion, and resume on outcome** via the 3 workflow node types. Task→workflow→task chain operational.
- **Focus sessions track their originating tasks** via r108 linkage; focus_closer subscriber closes focus_sessions on task completion automatically. Task→Focus chain operational.
- **Intelligence canonical entry point ready** for future Intelligence wiring that produces persistent tasks rather than fleeting notifications.
- **Communications cascade** produces customer-communication-shape tasks that wire through delivery_service for outbound dispatch.
- **(c)'s 8 producer sites flow through task substrate.** Notification dispatch is downstream consequence of task creation; substrate is single source of truth for "this needs attention."

The May 21-22 conversation's strategic positioning claim — "your business runs more efficiently because Bridgeable knows what needs doing and tells you, instead of you tracking everything in your head" — becomes operationally demonstrable at v1 close. Sunnycrest + Hopkins use post-deploy will validate (or refine via operator-observable signals) the architectural commitment.

---

## 8. Next-arc handoff

Per phasing doc §8.5 lock:

**Canon-update arc dispatches next.** Three-phase shape against ~71+ accumulated candidates. Substantively larger filing arc than typical post-arc canon-update due to candidate accumulation across the v1 + v2 investigation + (c) lineage. Phase 0 aggregation pulls candidates from this artifact's §4 + §5 plus v2 state doc §7 plus accumulated candidates from WB cycle + studio nav arc + prior investigations. Phase 1 cull applies canon-worthiness criteria. Phase 2 drafts entries with supersession references where prior canon shifts.

**v2 sub-arcs await operator-observable signal** per phasing §5. v2a (10 non-task triage queue adapters) likely first if Sunnycrest/Hopkins workflow signals surface. v2b (family portal) likely follows. v2c (substrate refinements) likely last. Signal-driven ordering means actual sequence follows signals, not phasing recommendation.

**v3 arcs subject to per-arc pre-dispatch rescoping** per phasing §8.6. v3 scope re-evaluated against then-current platform state and operator signal context.

---

*Document captured at v1 task substrate arc close, commit `1c8dbbd`. Lineage spans May 21-22, 2026 primary source through May 24-25, 2026 v1 close.*
