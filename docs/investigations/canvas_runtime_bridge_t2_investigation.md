# Canvas↔Runtime Execution Bridge (T-2) — Scoping Investigation (read-only)

**HEAD:** `5ea8dd7` (the MoC Task Triggers T-1b push) · **Date:** 2026-07-01 · **Read-only** — no code, no migration, no seed, no canon, no dispatch. The plan is the deliverable, and it is allowed to conclude "this is N sessions, here is the map."

**Target (operator intent, scoped-against not redesigned):** ONE bridge that makes the platform's **design layer executable** — MoC task triggers FIRE, the 18 workflow mirrors EXECUTE, and AI-drafted canvases RUN. The three debts converge at one seam by design. This is the biggest, most net-new arc: event emission + schedule execution + canvas→runtime compilation, three systems that mostly don't exist yet.

**Method:** three parallel witnessed sweeps of `backend/` (the workflow-engine execution model + demo-artifact bridging; the scheduler wiring; event-emission near-misses + the safety substrate) + first-hand reads of the engine dispatch, the canvas validator's node vocabulary, the runtime step model's branching columns, and the MoC trigger config shapes. Every claim is grounded in cited code.

---

## TL;DR — the shape of the arc (four load-bearing findings)

1. **The central seam does NOT exist — and it's the shared spine all three systems need.** The workflow engine executes `workflows` + `workflow_steps` (runtime) **only**; it *never* reads `workflow_templates.canvas_state` (verified — zero `canvas_state` references in `workflow_engine.py`). So the mirrors + AI-drafts are genuinely inert. **No canvas→runtime compiler exists** (grep confirms). Even the demo-artifact workflows that "executed end-to-end" did so by **hand-building runtime rows in the assembly test** (`test_legacy_order_end_to_end.py::_build_workflow`), not via any compiler. Every path to "execute the task's workflow" flows through this missing seam.

2. **Canvas→runtime is a clean reverse of the backfill ONLY for the linear + simple-conditional subset (finding (a) confirmed).** The runtime engine walks one current step at a time via `next_step_id` (linear) + `condition_true/false_step_id` (binary branch). The canvas vocabulary (`canvas_validator.VALID_NODE_TYPES`, ~35 types) is **richer**: `decision`/`branch`/`parallel_split`/`parallel_join`/`wait`/`schedule`/`cross_tenant_*` have **no clean runtime equivalent**. The 18 mirrors are all linear → clean. But an AI-draft with a `parallel_split` has **no runtime home** without lowering to the task-substrate fan-out (`create_task` + `wait_for_task_completion`). The reverse is not uniformly mechanical.

3. **The three systems are radically different sizes.** Schedule execution is **mostly a wiring job** (the scheduler substrate is real, the MoC config mirrors it, the tenant fan-out has precedent). Event emission is a **net-new system** (no bus, no outbox, no emission hooks — plus the hard distributed-systems parts: durability/ordering/tenant-scoping). The compiler-spine sits under both. This is **not one dispatch** — it's a multi-session arc (estimate **~6–9 sessions**, below).

4. **The safety substrate mostly EXISTS — reuse it, don't rebuild — but there are two real gaps.** Dry-run (`guard_write`/`DryRunGuardError`), the approval gate (token-email, 72h, single-use), the `WorkflowRun`/`WorkflowRunStep` execution audit, and two idempotency patterns (the task composite key + the scheduler's `_already_fired_scheduled`) are all in-tree. **Gap 1: workflows have NO approval gate** (agents do) — a workflow step can post to the GL with no human gate. **Gap 2: a failed run sits with `status="failed"` until POLLED** — no auto-escalation. Crossing descriptive→executable at financial scale must close both.

---

## SYSTEM 1 — SCHEDULE EXECUTION (the cheapest; the scheduler substrate is REAL)

### What exists
- **The dispatch loop** (`workflow_scheduler.check_time_based_workflows`, `:245–367`): every 15 min (APScheduler `_run_workflow_time_check`, `scheduler.py:681`) it loads active `Workflow`s with `trigger_type ∈ {time_of_day, time_after_event, scheduled}` and iterates **`workflows × companies`** (nested), firing per matching tenant. Matching gates (verified first-hand, `:280–333`): `w.vertical == company.vertical` (vertical fan-out), `w.company_id == company.id` (tenant-scoped), tier-3 `WorkflowEnrollment` opt-in.
- **The matchers**: `_matches_time_of_day({time, days})`, `_matches_time_after_event({record_type, field, offset_days})` (a daily poll, hardcoded `funeral_case` table_map), `_intended_scheduled_fire(cron)` (APScheduler `CronTrigger.from_crontab`, tenant-tz-aware).
- **"Fire"** = `workflow_engine.start_run(workflow_id, company_id, trigger_source="schedule", trigger_context={intended_fire})`.
- **Idempotency**: `_already_fired_scheduled` dedups on `WorkflowRun.trigger_context.intended_fire` — self-healing across restarts.
- **The per-user sweep template** (briefings, `scheduler_integration.py`): single global cron + query-by-per-user-preference + per-day-unique — the exact shape a per-MoC-task sweep would follow.

### What's net-new
- **A `moc_task_trigger` schedule sweep** paralleling `check_time_based_workflows`: iterate active `kind='schedule'` triggers (joined to `moc_task_catalog` for scope/vertical) × companies, match via the SAME matchers, fire.
- **The config mapping is a thin adapter, not literally 1:1** (finding surfaced): the MoC config uses `spec_kind ∈ {time_of_day, cron, time_after_event}` with **identical payloads** to the scheduler (`{time,days}` / `{cron}` / `{record_type,field,offset_days}`), but the scheduler's outer discriminator is `trigger_type="scheduled"` for cron (vs MoC `spec_kind="cron"`). The mapping is trivial (`time_of_day→time_of_day`, `cron→scheduled`, `time_after_event→time_after_event`) — a ~3-line switch, not a re-model. The banked "mirrors 1:1" claim holds at the payload level.

### The risks / gaps
- **Tenant-scoping — RESOLVED by precedent, not a blocker.** A `vertical_default` MoC task-catalog trigger isn't tenant-scoped, but `start_run` needs a `company_id`. The existing loop already fans a `vertical` workflow to every company in that vertical — a `vertical_default` MoC task fires the same way (per-company-in-vertical). `tenant_override` tasks fire for their one tenant. No new scoping model needed; reuse the workflow fan-out.
- **"Fire" depends on the compiler-spine.** A MoC task's `workflow_template_id` points at a **canvas template** (`moc_task_catalog.workflow_template_id` FK → `workflow_templates`, verified) — NOT a runtime `workflows` row. So schedule-fire can't call `start_run` directly; it must first resolve the template → an executable runtime workflow (System 3). **Schedule execution is cheap ONLY once the spine exists.**

**Verdict:** ~1–2 sessions *after* the spine. The safest system to prove fire→execute on (deterministic timing, no external match, easy dry-run).

---

## SYSTEM 2 — EVENT EMISSION (the NET-NEW one; no bus exists)

### What exists (near-misses, none a general bus)
- **The task-lifecycle subscriber registry** (`tasks/subscribers/registry.py`) — the **closest event-bus prototype**: `emit_event` synchronously dispatches to an `OrderedDict` of subscribers with per-subscriber try/except, in-transaction. 7 task events × 6 subscribers. **Generalizable** in shape (registration + isolated dispatch); **task-scoped** in vocabulary + payload + the fact that it fires only from task lifecycle, not domain mutations.
- **The intake classification cascade** (`classification/dispatch.py::classify_and_fire`) — a **working "event → fire workflow" path**, but inbound-intake-only (email/form/file → classify → `start_run(trigger_source="…_classification")`). The generalizable kernel: match an inbound thing → fire a workflow + write an audit row.
- **A service-layer seam precedent**: `sales_service` calls `order_integration_service.on_order_confirmed(db, order)` on status change — a pull-based callback, not an emission.

### What's net-new (this is a whole system)
1. **Emission hooks.** Domain mutations do **not** emit. `create_sales_order` commits with no post-commit callback; **no outbox / domain_event / event_log table exists** (grep confirms); **only ONE SQLAlchemy listener** in the codebase (`integrity_monitor.py` `handle_error` — a precedent that SA events *can* be used, but not for domain events). Emission must be built: either (a) explicit `emit("order.created", payload)` calls at mutation sites (like the onboarding hooks pattern — simple, but must be hand-placed at every site), or (b) SQLAlchemy `after_insert`/`after_commit` listeners (automatic, but blunt — fires on every insert, no domain semantics), or (c) an **outbox row** written in the same transaction as the mutation, drained async (durable, ordered — the financial-grade option).
2. **The matcher.** An emitted event payload must be matched against each MoC task's **structured conditions list** (`config.conditions: [{field, operator, value}]` — the T-1a shape). This is a small rules-evaluator (field lookup in the payload + operator apply), and the descriptive layer already constrained conditions to the event's real `filterable_fields` — so the matcher's vocabulary is bounded. Straightforward *given* a payload.
3. **The delivery/reliability model — the hard design space (finding (b)).** Honest hard parts: **durability** (in-transaction sync-dispatch loses events on a mid-run restart; an outbox + drain is at-least-once but needs a dedup key); **ordering** (multi-worker prod has no per-tenant FIFO without a log-structured outbox); **tenant-scoping** (the subscriber registry is app-global; per-tenant match needs company_id filtering in the matcher — mechanically easy but must be deliberate); **idempotency** (an event that fires a task-workflow must fire it once — reuse the task composite key `provenance_kind+ref+event_kind`). "Just emit" is a trap: the reliability model is most of the work.

### The risks / gaps
- **This is the biggest single piece of T-2** — realistically **3+ sessions** on its own (emit → outbox+drain → match → fire → idempotency + the reliability hardening). It should be **decomposed into its own sub-arc**, not attempted whole.
- **Curated-vocabulary reality (from T-1a):** the event catalog (`moc_trigger_event_catalog`, 8 seeded events) is honest metadata — but nothing emits `order.created` yet. Emission must be wired **per event key**, grounded in the real mutation site each catalog event names (`order.created` → `create_sales_order`; `invoice.sent` → the send path; etc.). The catalog is the checklist; each row is an emission-site to wire.

**Verdict:** the net-new system. Recommend a dedicated multi-session sub-arc (T-2.2.x), sequenced AFTER schedule proves the fire→execute path on the safe system.

---

## SYSTEM 3 — CANVAS→RUNTIME COMPILATION (the CENTRAL seam; what "execute" means)

### What exists
- **The runtime execution model** (`workflow_engine.py`): `start_run → _drive_run → _execute_step`, walking `workflow_steps` by `step_order` / `next_step_id` / `condition_true|false_step_id`, one current step at a time. `WorkflowRun` tracks `status`/`current_step_id`/`error_message`/`trigger_context`. Rich action dispatch (`_execute_action`): `create_record`, `call_service_method` (the Phase-8b whitelisted registry — 9 adapters incl. `invoice_statement.*`, `month_end_close.*`), `invoke_generation_focus`, `invoke_review_focus`, `notify_via_contact_preference`, `create_task`/`wait_for_task_completion`/`route_on_task_outcome` (the task-substrate fan-out), etc.
- **The reverse transform** (`seed_moc_backfill_workflow_mirrors._mirror_canvas`): runtime steps → canvas — clean/mechanical/linear (node per step, edges consecutive, config verbatim). This is the transform whose **inverse** the compiler needs.
- **The retirement handle**: `workflow_templates.mirrored_from_workflow_id` (nullable FK → `workflows.id`) — every mirror knows its runtime source.

### What's net-new
- **The compiler itself** — `canvas_state → workflow + workflow_steps`. Does not exist. For a **linear** canvas it's the clean inverse of `_mirror_canvas`: node → `WorkflowStep(step_type=node.type or "action", config=node.config, step_order=topological index)`, edges → `next_step_id`. For a **conditional** canvas: canvas `decision`/`condition` + condition-edges → runtime `condition` step + `condition_true/false_step_id` (doable, not trivial — must read edge conditions).
- **The unmappable node types (finding (a)):** `parallel_split`/`parallel_join` (the engine is single-current-step — no concurrency), `branch` (n-way — the engine has binary condition only), `wait`/`schedule` (no engine equivalent), `cross_tenant_*` (Phase-4 primitives, no engine impl). A canvas using these **cannot compile to steps** without either (i) lowering `parallel_*` to the task-substrate fan-out (`create_task` × N + `wait_for_task_completion` + join) — a real but substantial future capability, or (ii) rejecting non-linear canvases at compile time with a clear "this canvas uses unsupported nodes" error (the honest v1 boundary).

### The mirror-retire-vs-compile SPLIT (the key architectural call)
The two populations diverge:
- **Mirrors (have a runtime source):** do **NOT compile**. Re-point via `mirrored_from_workflow_id` → execute the runtime `workflows` row they mirror. This RETIRES the mirror per the deliberate-debt exit (the mirror was always an inert snapshot; the runtime workflow is the source of truth). Cheap, exact, no compile risk. **But** the mirror may have DRIFTED from its source (the backfill flagged this) — re-pointing executes the *current* runtime workflow, which is correct-by-definition (the runtime is the truth), but the operator's edits to the *mirror canvas* (if any) are discarded. Flag: **decide whether re-point ignores mirror-canvas edits** (recommended: yes — a mirror is a snapshot, not an authoring surface; editing a mirror should fork it into a non-mirror template first).
- **AI-drafts + authored canvases (no runtime source):** **MUST compile** (no source to re-point at). Clean for linear+conditional; rejected/deferred for parallel. This is where the compiler earns its keep.

### The risks / gaps
- **The compiler is the spine BOTH other systems block on** — schedule-fire and event-fire both end at "execute the task's workflow_template," which is either a re-point (mirror) or a compile (draft). Build the spine first.
- **Compile-when? (substrate question):** compile-on-demand (ephemeral runtime rows per run — simplest, no new table, but recompiles every fire) vs compile-and-cache (a `compiled_workflow_id` on the template + a materialized runtime workflow — faster, but a cache-invalidation surface when the canvas edits). Recommend **compile-on-demand for v1** (correctness over speed; the fire rate is low — scheduled/event, not hot-path), revisit caching only if profiling demands.

**Verdict:** the shared foundation. ~1–2 sessions for the linear+conditional compiler + the re-point path; parallel-lowering is a deferred capability.

---

## HOW THE THREE COMPOSE INTO ONE BRIDGE — the unified execution path

All three converge at a single spine:

```
    trigger fires (schedule sweep  OR  event match)
                 │
                 ▼
    resolve the MoC task  →  moc_task_catalog.workflow_template_id (canvas)
                 │
                 ▼
    ┌─ SPINE: template → executable runtime workflow ─┐
    │   mirror (mirrored_from_workflow_id) → RE-POINT │
    │   draft/authored (no source)          → COMPILE │
    └──────────────────────┬──────────────────────────┘
                 ▼
    start_run(runtime_workflow_id, company_id, trigger_source, trigger_context)
                 │
                 ▼
    _drive_run → steps execute (with the safety surface: dry-run / approval gate / audit / idempotency)
```

- **Where they SHARE:** the spine (`template → runnable`) + `start_run` + the safety surface + the execution audit (`WorkflowRun`). Build these once.
- **Where they DIVERGE:** only the *trigger detection* — schedule = a cron sweep over `moc_task_trigger` rows; event = an emission + a condition-matcher. Two thin front-ends over one shared execution back-end.
- **The retirement is designed in:** the spine re-points mirrors at their runtime source (retiring the mirror as an execution stand-in) and compiles only where no source exists — so the bridge doesn't compile duplicates of workflows that already run.

---

## RECOMMENDED BUILD-PHASING — unified target, safest sequencing

The end-state is the ONE bridge. But a three-system descriptive→executable arc in one dispatch is the four-things-at-once anti-pattern at maximum stakes. Sequence to prove the shared spine on the safest system first, then add the hard net-new system.

- **T-2.0 — THE SPINE (canvas→runtime resolution). The foundation both fire-paths block on.**
  - Build `resolve_executable_workflow(db, template_id, company_id) → runtime workflow_id`: re-point (mirror) OR compile-on-demand (linear+conditional canvas → runtime workflow+steps); reject non-linear canvases with a clear error.
  - **Assembly-test-first (JCF-1):** compile a linear demo-artifact canvas (Invoice & Statement Run) → runtime steps → `start_run` → assert the SAME side effects the hand-built `test_legacy_order_end_to_end` proves today. This replaces the hand-built bridge with a real compiler and is independently witnessable (a canvas template runs).
  - Migration: none required for compile-on-demand (ephemeral runtime rows) — or a small `compiled_workflow_id` cache column if caching is chosen. Flag as a decision.
  - ~1–2 sessions.

- **T-2.1 — SCHEDULE EXECUTION (prove fire→execute on the safe system).**
  - A `moc_task_trigger` schedule sweep (parallels `check_time_based_workflows`; reuses the matchers + the `spec_kind→trigger_type` adapter + the vertical/tenant fan-out + `_already_fired_scheduled` idempotency). Fire → the T-2.0 spine → `start_run`.
  - **Safe-fire first:** every scheduled MoC-task run defaults to **dry-run** (reuse `guard_write`) until the operator promotes a trigger to live — the descriptive→executable gate (below).
  - Witness: a scheduled MoC task fires on cron and executes (dry-run report → then live) on staging.
  - ~1–2 sessions.

- **T-2.2 — EVENT EMISSION (the net-new system; its own multi-session sub-arc).**
  - **T-2.2a — emission substrate:** the outbox table + the emit API + drain; wire the FIRST catalog event (`order.created` at `create_sales_order`) end-to-end. Prove durability + idempotency on one event.
  - **T-2.2b — the matcher + fire:** evaluate an emitted payload against MoC tasks' structured `conditions` lists → the T-2.0 spine → `start_run`. Reuse the classification-cascade fire pattern.
  - **T-2.2c — the remaining catalog events + reliability hardening** (ordering, tenant-scoping, replay).
  - ~3+ sessions.

- **CROSS-CUTTING (lands alongside T-2.1, not deferred) — the safe-firing surface** (its own weight; see next section).

**Sequence rationale:** T-2.0 is the risk-and-surprise (the compiler that doesn't exist + the parallel-node ceiling) AND the shared foundation — build + de-risk first. T-2.1 is the cheapest *and* the safest place to prove the whole fire→execute→audit loop end-to-end with real-but-bounded side effects. T-2.2 is the biggest net-new system and should not start until the spine + the safety surface are proven on schedule. **Each phase is assembly-testable and independently witnessable** — no phase requires the next to be demonstrable.

---

## THE DESCRIPTIVE→EXECUTABLE SAFETY SURFACE (flag throughout — it's substantial (finding (c)))

Crossing from descriptive to executable means tasks start DOING things — real invoices, real notifications, firing on real orders. The safety surface is itself a real chunk of the arc, and most of it can REUSE existing substrate:

- **Test-fire without side-effects → dry-run EXISTS.** Reuse `base_agent.guard_write` / `DryRunGuardError`: a MoC-task fire in dry-run runs the workflow read-only + reports what it *would* do (the `call_service_method` adapters already thread `dry_run`). **Recommend: every trigger is dry-run by default; going live is an explicit per-trigger promotion** (a new `moc_task_trigger.is_live` bool, defaulting False — the operator arms a trigger deliberately). This is the single most important safety gate.
- **Prevent mass-firing / blast radius.** A mis-configured event condition could match every `order.created`. Mitigations: (i) dry-run-by-default (above) means a wrong match reports, doesn't act; (ii) a **per-tenant per-trigger rate/volume cap** on fires per window (net-new, small); (iii) the idempotency key prevents duplicate fires for the same event.
- **Workflow approval gate — GAP 1 (net-new for workflows).** Agents gate consequential writes behind the token-email approval; **workflows do not** — a compiled workflow's `call_service_method` to month-end-close would post with no human gate. For financial MoC-task workflows, **graft the existing `approval_gate` onto workflow execution** (the pattern exists; wiring it to `WorkflowRun` is the work). At minimum, a MoC task whose workflow touches the GL should require approval before live-fire.
- **See what fired → the audit EXISTS, the escalation does NOT (GAP 2).** `WorkflowRun` (status/trigger_source/trigger_context/error_message) + `WorkflowRunStep` (per-step status/error) already record every run — a "what fired, what it did, did it fail" log reads from these. But a **failed run sits with `status="failed"` until polled** — no notification. The silent-swallow guard at execution scale: **a MoC-task fire that fails must raise a task/notification** (reuse the `anomaly_resolution_task` producer or the notification dispatcher), not sit silent. Net-new: a failure→escalation hook on `_fail_run` for trigger-sourced runs.
- **Idempotency → EXISTS.** Schedule: `_already_fired_scheduled` (intended_fire dedup). Event: the task composite key (`provenance_kind+ref+event_kind`, partial-unique). Both reusable; the event path needs a per-event dedup ref.

**Net:** the safety surface reuses dry-run + approval-gate + audit + idempotency (all in-tree) and adds three net-new pieces (is_live promotion, the workflow approval-gate wiring, the failure→escalation hook + a rate cap). Non-trivial, but not from-scratch. It lands alongside T-2.1 so the first live fires are safe.

---

## MIGRATIONS + SUBSTRATE — flagged plainly

- **T-2.0 (spine):** none for compile-on-demand; OR a `workflow_templates.compiled_workflow_id` cache column if caching is chosen (decision, not required).
- **T-2.1 (schedule):** likely one column — `moc_task_trigger.is_live` (bool, default False — the descriptive→executable promotion gate). Plus an **idempotency-dedup decision** (crystallized): either reuse `WorkflowRun.trigger_source="moc_task_schedule"` + `trigger_context.intended_fire` (the existing `_already_fired_scheduled` pattern, no new table) OR a dedicated `moc_task_trigger_run` table keyed on `(trigger_id, company_id, intended_fire)`. Recommend the former (no migration) unless MoC-task fan-out needs its own audit surface. The matchers themselves (`_matches_time_of_day` / `_intended_scheduled_fire` / `_matches_time_after_event` / `_resolve_tenant_tz`) are **directly reusable — no code-reuse gaps** (the sweep is assemble-existing-dispatch, not re-model).
- **T-2.2 (event):** the big one — an **outbox / domain_events table** (durable emission), likely a per-event dedup index, and the emission call-sites (code, not migration) at each catalog event's real mutation source.
- **Safety:** `is_live` (above); the workflow-approval-gate wiring reuses `agent_jobs`/approval-token substrate (may need a workflow-run ↔ approval-token link); the failure-escalation hook is code (reuses the notification/task producers).
- **Execution audit:** **no new table** — `WorkflowRun` + `WorkflowRunStep` already are the execution log.

---

## HONEST SIZE — this is a MULTI-SESSION ARC

**Estimate ~6–9 sessions**, decomposed:
- T-2.0 spine (compiler + re-point + assembly test): **1–2**
- T-2.1 schedule execution + the safety surface (dry-run-by-default, is_live, failure escalation, rate cap): **2** (the safety surface is real weight)
- T-2.2 event emission (outbox + emit + drain; matcher + fire; remaining events + reliability): **3+**
- Workflow approval-gate wiring (if financial workflows go live): **~1** (can fold into T-2.1's safety surface or stand alone)

**Recommendation:** do NOT dispatch T-2 as one build. Sequence the sub-arcs, each with its own scope + assembly test + witness. Start with **T-2.0 (the spine)** — it's the foundation, the risk, and the surprise (the compiler doesn't exist; parallel nodes have no runtime home). Prove it, then **T-2.1 (schedule)** as the safe end-to-end demonstration of fire→execute→audit, with the safety surface landing alongside. Hold **T-2.2 (event)** as a distinct downstream sub-arc — it's the largest net-new system and should not begin until the spine + safety are proven.

---

## STOP-discipline answers
- **(a) Canvas→runtime is NOT a uniformly clean reverse — surfaced.** Clean for linear + simple-conditional (the 18 mirrors, the demo artifacts). `parallel_split`/`parallel_join`/`branch`(n-way)/`wait`/`schedule`/`cross_tenant_*` canvas nodes have **no runtime equivalent**; a v1 compiler rejects them (or lowers `parallel_*` to the task-substrate fan-out as a deferred capability). The reverse is mechanical only within the linear subset.
- **(b) Event emission's reliability model IS a bigger design space than "just emit" — surfaced.** No bus, no outbox, no emission hooks; durability/ordering/tenant-scoping/idempotency are the real work. Recommend its own multi-session sub-arc, decomposed emit→outbox→match→fire→harden.
- **(c) The safe-firing/dry-run surface IS substantial — surfaced.** Most reuses in-tree substrate (dry-run, approval gate, audit, idempotency), but adds dry-run-by-default + is_live promotion + the workflow approval-gate gap + failure→escalation + a rate cap. It lands alongside T-2.1, not deferred.
- **The mirror-retire-vs-compile split is the key architectural call** — mirrors re-point (retiring the snapshot), drafts compile. The bridge doesn't compile duplicates where a runtime source exists.
- **No build, no migration, no seed performed.** The plan is the deliverable — and the honest conclusion is: **this is ~6–9 sessions; here is the map and the safe sequence.**

**STOP.**
