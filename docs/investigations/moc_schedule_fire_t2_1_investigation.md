# MoC Schedule-Fire (Canvas↔Runtime Bridge T-2.1) — Scoping Investigation (read-only)

**HEAD:** `a801ff5` (the T-2.0b engine-dry-run push) · **Date:** 2026-07-01 · **Read-only** — no code, no migration, no seed. The plan is the deliverable, and it may conclude the first real fire needs its own tightly-scoped sub-phase.

**Target (operator intent):** the FIRST LIVE CALLER — a sweep that fires MoC schedule-triggers through the now-dry-run-safe engine (T-2.0b: engine defaults dry-run; live requires explicit `go_live=True`). T-2.1 fires scheduled tasks **defaulting to dry-run**, with **per-trigger `is_live` promotion** for the first real fire. The descriptive schedule-triggers built in T-1a/T-1b get their first execution — safely.

**Method:** first-hand reads of `workflow_scheduler` (the loop, matchers, idempotency, tz, catch-up window), `scheduler.py` (the cadence), the `moc_task_trigger` model + `triggers.py` schedule config, and the T-2.0b `execute_template` contract. Every claim is cited.

---

## TL;DR — the verdicts (two of them reshape the arc)

1. **Scheduler reuse = a PARALLEL sweep, reusing the matcher HELPERS (not an arm on the workflow loop).** The existing `check_time_based_workflows` iterates `workflows × companies`; a MoC sweep iterates a *different* entity (`moc_task_trigger` schedule rows × companies), so bolting it into that function is messier than a sibling `check_moc_task_schedules()` that reuses `_matches_time_of_day` / `_intended_scheduled_fire` / `_resolve_tenant_tz` / the idempotency pattern as shared helpers. Cleaner as a parallel sweep; still "mostly wiring" (helper reuse), slightly more than "an arm."
2. **Correctness traps are MOSTLY INHERITED — one is an inherited BUG.** Idempotency (WorkflowRun.trigger_context pattern, re-keyable on the trigger — no table), catch-up (15-min window → backlog is SKIPPED, the safe behavior), and cron tenant-tz are all inherited clean. **The one trap: `time_of_day` fires at UTC wall-clock, not tenant-local** (a documented pre-existing scheduler bug) — a MoC sweep that reuses `_matches_time_of_day` inherits it. Recommend a tz-aware MoC time_of_day evaluation (small net-new) or prefer the `cron` spec.
3. **⚠ NEW FINDING — the RE-POINT fire path DOUBLE-FIRES for mirror-tasks whose source is independently scheduled.** Re-point runs the mirror's *runtime source*, and many of those sources (wf_sys_*) are ALSO fired by the existing scheduler on their own cron. A live MoC schedule-fire of such a mirror-task = the source runs twice (once via the existing scheduler, once via the MoC sweep). **This reshapes the live phase: the first REAL fires should target COMPILED (single-owner) workflows; mirror-task live-scheduling needs a source-schedule dedupe, deferred.** Detail in §6 — this is the finding the operator most needs.
4. **⚠ NEW FINDING — compile-on-demand row accumulation becomes LOAD-BEARING at sweep scale.** T-2.0b deferred the compiled-workflow caching decision. A sweep firing on a cadence *repeatedly compiles* draft-task canvases → a fresh `workflows`+`workflow_steps`+`WorkflowRun` set per fire → real row bloat. Recommend a compiled-workflow cache (compile once per `template_id`+`version`, reuse) lands in T-2.1a. Detail in §7.

Everything else (fan-out, the fire path, the is_live gate, observability) is clean.

---

## 1. THE SCHEDULER-REUSE — a parallel sweep, helper-level reuse

### What exists (the cadence + the loop)
- **Cadence:** APScheduler `interval, minutes=15, misfire_grace_time=300` runs `_run_workflow_time_check` (`scheduler.py:689`) → `workflow_scheduler.check_time_based_workflows()`. So the sweep tick is **every 15 min**.
- **The loop** (`check_time_based_workflows`, `:245–367`): loads active `Workflow`s with `trigger_type ∈ {time_of_day, time_after_event, scheduled}`, iterates **`workflows × active companies`**, gates each pair by `w.vertical == company.vertical` (vertical fan-out) + `w.company_id == company.id` (tenant) + tier-3 `WorkflowEnrollment`. Fires via `start_run(trigger_source="schedule", trigger_context={intended_fire})`.

### Arm vs parallel — recommend PARALLEL
- **An ARM** (a second iteration inside `check_time_based_workflows`) fights the function's workflow-centric shape — it iterates `Workflow` rows; MoC triggers are a different entity (`moc_task_trigger` joined to `moc_task_catalog`).
- **A PARALLEL sweep** — a sibling `check_moc_task_schedules()` (registered as its own 15-min APScheduler job, OR appended to `_run_workflow_time_check` so one tick runs both) — iterates `moc_task_trigger WHERE kind='schedule' AND is_active` (joined to `moc_task_catalog` for scope/vertical/workflow_template_id) `× active companies`, **reusing the matcher helpers** (`_matches_time_of_day`, `_intended_scheduled_fire`, `_resolve_tenant_tz`) and the idempotency pattern. The loop is new; the correctness helpers are reused. **Recommend parallel** — cleaner separation, helper-level reuse keeps it "mostly wiring."

### Fan-out — the precedent applies (confirmed)
A MoC task's scope drives the fan-out, mirroring `w.vertical == company.vertical`:
- `platform_default` (vertical NULL) → every active company.
- `vertical_default` → companies where `company.vertical == task.vertical`.
- `tenant_override` → the one `company.id == task.tenant_id`.
The vertical fan-out precedent (a vertical workflow fires per-company-in-vertical) transfers directly. `start_run`'s required `company_id` is the fanned-out company.

---

## 2. DUE-EVALUATION CORRECTNESS — inherited vs net-new per trap

| Trap | How the existing scheduler solves it | MoC sweep: INHERIT or BUILD? |
|---|---|---|
| **Idempotency** ("already fired this window") | `_already_fired_scheduled` (`:189`) queries `WorkflowRun WHERE trigger_source='schedule' AND trigger_context.intended_fire == X AND (workflow_id, company_id)`. Audit-trail-based, self-healing across restarts. `time_after_event` uses `_already_ran_for_record` (dedupe by `trigger_context.record.id`). | **INHERIT the pattern, RE-KEY on the trigger.** The compiled workflow is ephemeral (workflow_id varies per fire — §7), so the MoC dedupe MUST key on `trigger_context.moc_task_trigger_id + intended_fire + company_id` (NOT workflow_id), `trigger_source='moc_task_schedule'`. **No new table** — same JSONB-audit pattern. (The investigation's "new `moc_task_trigger_run` table vs reuse WorkflowRun" choice → **reuse WorkflowRun.trigger_context**, keyed on the trigger. Recommended.) |
| **Timezone** (cron) | `_resolve_tenant_tz(company.timezone)` fallback `America/New_York`; `CronTrigger.from_crontab(cron, timezone=tenant_tz)`. Tenant-tz-correct. | **INHERIT (clean).** MoC `cron` spec fires tenant-local correctly. |
| **Timezone** (time_of_day) | `_matches_time_of_day` compares against **UTC wall-clock, not tenant-local** — a documented pre-existing bug (canon Phase 8b.5). | **INHERITS THE BUG.** ⚠ A MoC `time_of_day` trigger reusing the matcher fires at UTC, not the tenant's 6pm. **Recommend:** a small tz-aware MoC time_of_day evaluation (resolve `_resolve_tenant_tz`, compare tenant-local) — net-new but tiny — OR steer MoC schedule-triggers to the `cron` spec (tenant-tz-correct). Flag in T-2.1a. |
| **Catch-up vs skip** (system was down) | `_intended_scheduled_fire` (`:157`) only fires if the cron wanted to fire in the trailing `_SWEEP_WINDOW_MINUTES = 15` window (`window_start = now - 15min`). Backlog older than 15 min is **SKIPPED** — no catch-up storm. | **INHERIT (the safe default).** A MoC task due while the system was down does NOT fire a backlog on restart — it fires only if due within the trailing 15-min window. Recommend inherit + log-skipped. This is the correct safety posture (don't fire a day's backlog at once). |
| **time_after_event record_type** | `table_map` (`:120`) is hardcoded to `funeral_case` only. | **INHERITS THE LIMITATION.** A MoC `time_after_event` trigger with any other `record_type` won't fire (returns []). **Recommend:** T-2.1 supports `cron` (fully clean) + `time_of_day` (with the tz fix) first; `time_after_event` inherits funeral_case-only — extend the table_map later if a MoC trigger needs another record type. |

**Net:** the MoC sweep INHERITS idempotency (re-keyed), catch-up (safe skip), and cron-tz — the "mostly wiring" finding holds. The two net-new correctness items are small: the tz-aware time_of_day matcher, and (later) extending time_after_event beyond funeral_case.

---

## 3. THE FIRE PATH + THE SAFETY DISCIPLINE (the T-2.0b contract)

For each due `(trigger, company)`:
```
task     = moc_task_catalog for trigger.task_catalog_id
run      = execute_template(
             db,
             template_id   = task.workflow_template_id,   # canvas → spine (re-point OR compile)
             company_id     = company.id,                   # the fanned-out tenant
             trigger_source = "moc_task_schedule",
             trigger_context= {"moc_task_trigger_id": trigger.id, "intended_fire": <iso>},
             allow_run      = True,                         # the sweep is a legitimate caller
             go_live        = trigger.is_live)              # ← NEVER hardcoded True
```

### The safety discipline (map that live is unreachable except via is_live)
- `allow_run=True` is the sweep's own opt-in (it IS a real caller).
- **`go_live` comes ONLY from `trigger.is_live`.** There is NO code path where the sweep passes `go_live=True` as a convenience. A dev who wants to "see it work" gets a **dry-run fire** (`is_live` defaults False → `go_live=False` → the engine suppresses every effect — T-2.0b), observable but harmless. **The default fire is dry-run, always** — this is the whole point of sequencing T-2.1 after T-2.0b.
- **A task with no `workflow_template_id`** (nullable FK) → skip + log (nothing to fire). A resolve/compile failure → the spine raises loudly (T-2.0); the sweep logs + continues to the next trigger (one bad trigger never blocks the sweep — the existing scheduler's per-item try/except discipline).

### The fidelity caveat (canon T-2.0b) — where it shows in the witness
A dry-run fire of a task whose branching depends on a **suppressed effect-step's output** takes a synthetic branch (the upstream effect was suppressed, so its output isn't real). **Scope of impact:** the 18 mirrors are LINEAR (no branching) → unaffected; compiled linear canvases → unaffected; only a re-pointed runtime workflow with a `condition` that reads a prior effect-step's output → affected. Narrow. **In the witness:** a dry-run preview of such a task may not perfectly predict the live branch — note it, don't block on it.

---

## 4. THE is_live PROMOTION GATE

- **Migration (T-2.1b):** `moc_task_trigger.is_live BOOLEAN NOT NULL DEFAULT FALSE`. Every existing trigger starts **unpromoted (dry-run)**. One column, one migration.
- **The sweep reads it per-trigger** → `go_live = trigger.is_live`. **Per-trigger granularity** — promoting one task's schedule-trigger to live does NOT drag its siblings live.
- **The promotion action (the write path):** extend the existing T-1a `patch_trigger` / `PATCH /triggers/{id}` to accept `is_live` (it already patches `kind`/`config`/`label`/`display_order`/`is_active` — adding `is_live` is a one-field extension). No new endpoint needed. **Recommend** the patch extension for T-2.1b; a dedicated `POST /triggers/{id}/promote` is unnecessary ceremony.
- **The UI toggle** (a "Live" switch per trigger chip in the T-1b editing surface) — its own small phase (**T-2.1c**), because the API + the sweep prove the mechanism first; the toggle is polish that rides the shipped API.

---

## 5. OBSERVABILITY — see what fired (the dry-run payoff)

A dry-run fire is only useful if you can SEE it — that's how you validate before promoting:
- **The log IS the `WorkflowRun`:** a dry-run fire produces a `WorkflowRun` with `output_data.__dry_run__ = True` (T-2.0b stamp) + `trigger_source='moc_task_schedule'` + `trigger_context.moc_task_trigger_id`, and per-step `WorkflowRunStep.output_data` carrying the `{dry_run, suppressed, would: "would execute X"}` records.
- **The operator surface:** reuse the existing `WorkflowRun` run-history (`list_runs(company_id, status)`) filtered by `trigger_source='moc_task_schedule'`, with a **dry-run badge** + the "would do X" step records expanded. "These 4 tasks fired dry-run at 6pm; here's what each would have done." **Recommend:** a thin MoC-scoped run-log view (or a filter on the existing workflow run surface) — the data already exists on `WorkflowRun`/`WorkflowRunStep`; the work is a read view, not new persistence.
- This closes the loop: **fire dry-run → inspect the "would do" trace → promote `is_live` → the next fire is real.**

---

## 6. ⚠ THE DOUBLE-FIRE FINDING (re-point vs independently-scheduled source)

**The hazard:** re-point (mirror mechanism) executes the mirror's *runtime source* workflow. Many mirror sources (wf_sys_*, some wf_mfg_*) carry their OWN `trigger_type ∈ {scheduled, time_of_day}` and are **independently fired by the existing `check_time_based_workflows`**. So a **live** MoC schedule-fire of a mirror-task whose source is independently scheduled = the source runs **twice** — once via the existing scheduler (`trigger_source='schedule'`), once via the MoC sweep (`trigger_source='moc_task_schedule'`). The two idempotency keys differ (different `trigger_source` + different `intended_fire`), so they do NOT dedupe against each other.

**Why it matters:** at LIVE, double execution = a real invoice/statement/collections run fired twice. The worst-case blast radius the whole T-2.0b net exists to prevent — reintroduced by the re-point path colliding with the source's own schedule.

**Recommendations (reshapes the live phase):**
- **T-2.1a (dry-run) is SAFE regardless** — a dry-run MoC fire produces no effect, so even if the source ALSO fires (on its own schedule), there's no double-effect from the MoC side. The double-fire hazard is a LIVE-only concern. So T-2.1a can sweep + dry-run-fire ALL schedule-triggers (mirror + compiled) safely.
- **T-2.1b (live) should target COMPILED (single-owner) workflows first.** A compiled draft canvas has NO independent trigger (compile forces `trigger_type="manual"` — T-2.0, scheduler-inert), so a live MoC fire of a compiled-task is the SOLE fire — no collision.
- **Mirror-task live-scheduling is DEFERRED** until a source-schedule dedupe is designed (options: the MoC sweep skips triggers whose source is independently scheduled + logs "the source's own schedule owns this"; OR the source's independent trigger is disabled when a MoC trigger claims it — bigger, touches the source workflow). Flag as a T-2.1b+ decision, not a T-2.1a blocker.

**Bottom line:** the dry-run sweep (T-2.1a) is safe for all triggers; the first REAL fires (T-2.1b) are for compiled-workflow tasks; mirror-task live-firing waits for the dedupe design.

---

## 7. ⚠ THE COMPILE-ACCUMULATION FINDING (caching becomes load-bearing)

T-2.0b shipped **compile-on-demand** (a fresh `workflows`+`workflow_steps` per compile) and explicitly deferred the caching decision. **At sweep scale that decision becomes load-bearing:** a draft-task schedule-trigger firing every scheduled tick recompiles its canvas each fire → a new `workflows` row + steps + a `WorkflowRun` per fire, forever. Even dry-run fires accumulate (they still compile + create runs). Re-point tasks don't accumulate (they reuse the source); only COMPILE (draft) tasks do.

**Recommend:** T-2.1a includes a **compiled-workflow cache** — compile once per `(template_id, version)`, reuse the cached runtime workflow on subsequent fires (the canvas is immutable per version; recompiling is wasted). This is a small substrate add (a lookup + a `compiled_workflow_id` on the template, OR an in-table marker) that keeps the sweep from bloating `workflows`. Without it, the dry-run sweep itself is a slow leak. Flag as required-for-T-2.1a (not deferrable once the sweep runs on a cadence).

---

## RECOMMENDED PHASING — split so the first REAL fire is its own witnessed step

- **T-2.1a — THE DRY-RUN SWEEP (fires dry-run, observable, NO promotion).**
  - The parallel `check_moc_task_schedules()` sweep (reusing the matcher helpers + tz resolver + the trigger-keyed idempotency); the tz-aware `time_of_day` fix; the fan-out; the fire path calling `execute_template(allow_run=True, go_live=False)` — **hardcoded dry-run** (no `is_live` column yet, so every fire is dry-run). The compiled-workflow cache (§7). The observability read-view (§5).
  - **Assembly-test-first:** a due trigger fires → a **dry-run** `WorkflowRun` with `__dry_run__` + "would do X" records; **no real effect** (spy on `_execute_action` — never invoked); **idempotent** across sweep ticks (a 6pm trigger fires once per 6pm intended_fire, not N times across the 15-min ticks); catch-up SKIPS backlog; fan-out fires per-company-in-vertical.
  - **Migration: NONE** (idempotency via WorkflowRun.trigger_context; no is_live yet; the compiled-workflow cache — decide if it needs a column or fits in-memory/existing).
  - **The witness:** a scheduled MoC task fires dry-run on the cadence; the run-log shows "would do X." The first fire ever — safely.

- **T-2.1b — THE is_live PROMOTION (the first REAL scheduled fire).**
  - Migration: `moc_task_trigger.is_live` (default FALSE). The sweep reads it → `go_live = trigger.is_live`. The `patch_trigger` extension (accept `is_live`). **Compiled-workflow tasks only** for live (the §6 double-fire discipline).
  - **Assembly-test-first:** `is_live=False` → dry-run (no effect); `is_live=True` (compiled task) → LIVE (the real effect happens, verified). Precedence intact (allow_run + go_live).
  - **The witness:** promote one compiled-task trigger to live → its next scheduled fire produces a REAL effect (observably), while its siblings stay dry-run. The first real scheduled execution of a descriptive trigger.

- **T-2.1c — THE UI TOGGLE (polish).** A "Live" switch per trigger chip in the T-1b editor, riding the shipped `is_live` patch API. Its own small phase.

**Sequence rationale:** T-2.1a proves the entire sweep + fire path + observability with EVERYTHING dry-run — no real effect is reachable (is_live doesn't exist). T-2.1b is the single deliberate flip: one column, the gate read, compiled-first, and the first real fire witnessed in isolation. T-2.1c is UI. Each is assembly-testable and independently witnessable; the first REAL fire is its own tightly-scoped, deliberately-witnessed step — exactly the split the operator asked for.

---

## MIGRATIONS — flagged plainly

- **T-2.1a:** NONE for idempotency (WorkflowRun.trigger_context). The **compiled-workflow cache** may want a `workflow_templates.compiled_workflow_id` column (or an in-table marker) — a decision, possibly one small column.
- **T-2.1b:** ONE — `moc_task_trigger.is_live BOOLEAN NOT NULL DEFAULT FALSE`.
- **T-2.1c:** none (UI).

---

## STOP-discipline answers
- **(a) Does the existing scheduler solve idempotency/tz/catch-up cleanly?** MOSTLY YES — idempotency (reusable pattern, re-keyed on the trigger), catch-up (15-min window skip — safe), cron-tz (correct) are INHERITED. The ONE gap: `time_of_day` UTC bug (inherited) → a small tz-aware MoC matcher. So T-2.1 stays mostly-wiring with one tiny correctness add — NOT a blow-up.
- **(b) Arm vs parallel?** PARALLEL sweep (different entity than the workflow loop), reusing the matcher HELPERS. Slightly more than "an arm," still helper-level reuse — not a re-model.
- **(c) Due-evaluation ambiguity?** `cron` is clean; `time_of_day` has the inherited UTC bug (flagged); `time_after_event` is funeral_case-only (inherited limitation). Recommend cron + time_of_day (fixed) first; defer time_after_event breadth.
- **(d) NEW — the re-point DOUBLE-FIRE hazard (§6):** live MoC firing of a mirror-task whose source is independently scheduled = double execution. Reshapes the live phase → compiled-first for T-2.1b; mirror-task live-scheduling deferred pending a dedupe. **The finding the operator most needs.**
- **(e) NEW — compile-accumulation at sweep scale (§7):** the deferred T-2.0b caching decision becomes load-bearing → a compiled-workflow cache is required in T-2.1a.
- **No build, no migration, no seed performed.** The plan is the deliverable — and the first REAL fire (T-2.1b) is its own tightly-scoped, witnessed sub-phase.

**STOP.**
