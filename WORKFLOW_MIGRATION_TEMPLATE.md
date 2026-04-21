# Workflow Migration Template

**Audience:** Phase 8c–8f migrators (month-end close, AR collections, expense categorization, and the 9 remaining accounting agents).

**Purpose:** This document is the **checklist** that each agent-to-workflow migration audit compares its target against. Cash Receipts Matching (Phase 8b) is the working example throughout — when this template says "like cash receipts did X," that's the concrete reference implementation to read.

**Non-goal:** this is not a copy-paste template. Each agent has its own write-timing semantics, anomaly taxonomy, approval type, and scheduler relationship. The template lists the questions each migration must answer and the patterns that will look familiar.

---

## 0. Before you start: what makes a migration reconnaissance vs. routine

Phase 8b was reconnaissance — one carefully-chosen agent where we **discovered** the migration template. 8c–8f are routine migrations where the patterns are known. The difference:

- **Reconnaissance (8b):** budget for "we'll find patterns we didn't predict." Single migration. Template as deliverable alongside the shipped migration.
- **Routine (8c–8f):** budget for "apply the template + document divergences." Multiple migrations per phase. Template updates happen at the END of a phase (accumulate learnings) not during.

Cash receipts was chosen as reconnaissance because: cross-vertical, SIMPLE approval (no period lock), no existing scheduler entry (net-new insertion), mid-complexity anomaly taxonomy. Month-end close was deliberately NOT first — its period lock + statement run makes it higher-risk.

---

## 1. Pre-migration audit checklist

Every audit answers these **nine questions** about the target agent. Divergences from cash receipts get documented; shared patterns get reused.

### 1.1 Write timing pattern

- **Immediate (cash receipts pattern):** agent writes `X` inline during step N. Triage actions replicate that write per-item.
- **Deferred (month-end close pattern expected):** agent reads + reports during steps 1–N; actual financial writes (statement run, period lock) fire on approval.
- **None (AR collections pattern expected):** agent drafts emails; approval sends them. No financial writes at all.

**Why it matters:** The parity adapter's shape hinges on this. Immediate-write agents need per-item approve helpers (`approve_match`). Deferred-write agents need an approval-fires-the-writes step in the workflow (`approve_and_commit`). None-write agents need send/dispatch helpers.

Cash receipts example: `cash_receipts_adapter.approve_match()` → writes `CustomerPaymentApplication` + mutates `Invoice.amount_paid` + resolves anomaly, all in one transaction. Mirrors the agent's CONFIDENT_MATCH branch (agent file line 223–238).

### 1.2 Anomaly category structure

- How many anomaly types does the agent emit? (Cash receipts: 4 — 1 INFO + 2 WARNING-or-CRITICAL-by-age + 1 aggregate ratio.)
- Are they per-entity (hang off a payment) or global (tenant-wide like `high_unmatched_ratio`)?
- Does the triage queue show individual anomalies, individual entities, or aggregates? (Cash receipts: individual anomalies. The `_DIRECT_QUERIES` builder returns `AgentAnomaly` rows, not `CustomerPayment` rows.)

**Why it matters:** The `source_direct_query_key` builder must emit the right grain. `item_entity_type` reflects that grain (cash receipts: `"cash_receipt_match"` — an anomaly that represents a possible/unresolvable match). Context panels then enrich the display with the related payment + customer + candidate invoices.

### 1.3 Existing scheduler invocation

- Already scheduled via APScheduler? (Cash receipts: **no** — we added it from scratch.)
- Already scheduled as a workflow? (None of the Phase 8a agent-backed stubs are — their declared `trigger_type="scheduled"` is a latent bug — see `wf_sys_ar_collections` note at bottom.)
- Not scheduled at all, manual only? (Cash receipts was in this bucket.)

**Two sub-templates** for the migration shape:

- **"Add from scratch" (cash receipts):** pick a `trigger_type="time_of_day"` + `trigger_config.time` slot that doesn't collide with adjacent nightly jobs. Workflow scheduler sweep (every 15 min) fires it.
- **"Reuse existing" (month-end close expected — triggered by user today, not scheduled; keeps manual trigger):** set `trigger_type="manual"`; workflow remains user-invoked via `POST /api/v1/workflows/{id}/start`.

Neither path requires modifying `backend/app/scheduler.py` — the workflow engine's 15-min polling sweep dispatches `time_of_day` triggers automatically.

### 1.4 Approval type (SIMPLE vs. full)

- **SIMPLE (cash receipts):** approval flips `job.status` to `complete`. No period lock. No statement run. No deferred financial writes. `SIMPLE_APPROVAL_TYPES` contains the enum value.
- **Full (month-end close):** approval triggers statement run + locks period. `approval_gate.py` has a dedicated `_finalize_month_end_close` callback.

**Why it matters:** The parity test's negative assertions differ. Cash receipts asserts **no** `PeriodLock` row written; month-end close asserts **one** `PeriodLock` row written with the right period.

### 1.5 Email template status

- **Managed template (D-7 pattern, preferred):** approval email renders via `template_key` in delivery_service. Template lives in `document_templates` table.
- **Hardcoded HTML (cash receipts, legacy):** approval email HTML is inline Python in `ApprovalGateService._build_review_email_html()`. **This is pre-existing tech debt** — don't fix it during a migration; preserve verbatim for parity. Flagged for future cleanup in Phase 8h or later.

Cash receipts example: we did NOT migrate the approval email to a managed template. The parity test would fail if we did (hashes don't match). Future session migrates approval-gate emails to D-7 managed templates platform-wide.

### 1.6 Related entities for AI question context

Each queue's `_build_{name}_related` function returns the entities the AI question prompt grounds in. Pattern:

1. The primary entity (payment, cert, journal entry, etc.)
2. The customer / FH / counterparty
3. 3–5 most-relevant records (candidate matches for cash receipts; past same-FH certs for SS cert; similar GL entries for expense categorization)
4. Tenant-aggregate context where useful (e.g., cash-receipts ratio-of-AR)

The builder return list is a flat array of `{entity_type, entity_id, context, display_label, ...entity_specific_fields}` dicts. Keep it flat — the Jinja prompt just stringifies to JSON.

### 1.7 AI prompt seed shape

Every migrated queue seeds an Intelligence prompt via **Option A idempotent pattern**:

- Fresh install → v1 active.
- Single version matching content → no-op.
- Single version differing content → deactivate v1, create v2. Changelog notes "platform update."
- Multiple versions exist (admin customization in flight) → skip with warning.

Reference: `backend/scripts/seed_triage_phase8b.py::seed_prompt()`. Copy it, change the prompt_key + system_prompt + description. Variable schema is the same shared 4-field set (`item_json`, `user_question`, `tenant_context`, `related_entities_json`).

### 1.8 Permission gate

- `invoice.approve` for write-side actions (cash receipts: approve/reject/override). Aligns with the Phase 8a legacy `/api/v1/agents/accounting/{id}` endpoint's gate.
- Non-write actions (request_review, skip) can be open to any authenticated tenant user.

Cash receipts example: 4 of 5 action palette entries carry `required_permission="invoice.approve"`. `request_review` (escalate-only) doesn't. Matches the approval-gate-level permissions the legacy UI enforced.

### 1.9 Vertical scoping

Cash receipts is cross-vertical (manufacturing + funeral_home both see it). SS cert is manufacturing-only (vertical-scoped via `required_vertical="manufacturing"` on the queue config).

Month-end close, AR collections: cross-vertical (Core).

Vertical-specific workflows (manufacturing `wf_mfg_*`, funeral_home `wf_fh_*`) are Phase 8d's job, not 8c. Don't accidentally vertical-scope a Core accounting workflow.

---

## 2. The parity adapter pattern

Every migration produces a new file at `backend/app/services/workflows/{agent_name}_adapter.py`.

### 2.1 Pipeline entry (workflow-step surface)

```python
def run_match_pipeline(
    db: Session,
    *,
    company_id: str,
    triggered_by_user_id: str | None,
    dry_run: bool = False,
    trigger_source: str = "workflow",
) -> dict[str, Any]:
    """Create + execute a {Agent} job end-to-end. Returns structured
    summary the workflow step can reference via variable resolution."""
```

Requirements:

1. Takes `db, company_id, triggered_by_user_id` positional/kw (auto-injected by `_handle_call_service_method`).
2. Creates an `AgentJob` row representing this workflow run's invocation of the agent.
3. Delegates execution to `AgentRunner.run_job(job.id, db)` — **zero logic duplication**.
4. Returns a dict with `agent_job_id` + `status` + a summary of counts. These become variables downstream workflow steps can reference as `{output.step_key.agent_job_id}`.

Cash receipts reference: `cash_receipts_adapter.py::run_match_pipeline`.

### 2.2 Per-item triage action helpers

One function per action palette entry (excluding `skip` — handled by the engine's generic `_handle_skip`).

For cash receipts:
- `approve_match(db, *, user, payment_id, invoice_id, anomaly_id, amount=None)` → writes PaymentApplication + mutates Invoice + resolves anomaly.
- `reject_match(db, *, user, payment_id, anomaly_id, reason)` → resolves anomaly with reason, no financial writes.
- `override_match(db, *, user, payment_id, invoice_id, anomaly_id, reason, amount=None)` → same writes as approve + stamps override reason.
- `request_review(db, *, user, payment_id, anomaly_id, note)` → stamps review note on anomaly without resolving (item stays in-queue).

### 2.3 Zero-duplication discipline

If the agent has an inline write pattern (like cash receipts' CONFIDENT_MATCH branch), extract a **private helper** in the adapter that both the agent-path and triage-path call. If that's too invasive, **duplicate the write pattern** in the adapter and cover it with a parity test.

Cash receipts chose duplication + parity test (the agent's code is legacy — no changes; adapter has its own `_apply_payment_to_invoice` helper). Parity test catches any drift.

### 2.4 Tenant isolation

Every adapter method that takes an `anomaly_id`, `payment_id`, or other entity id MUST scope-check via the acting user's `company_id`. See `_load_anomaly_scoped` / `_load_payment_scoped` / `_load_invoice_scoped` helpers in cash receipts. Defense-in-depth — the triage API already enforces tenant scoping at the session level, but the adapter's helpers protect against misuse from a workflow step invoked with attacker-controlled data.

---

## 3. Workflow definition structure

### 3.1 Add to `backend/app/data/default_workflows.py::TIER_1_WORKFLOWS`

Cash receipts reference block — copy this shape, change IDs + step descriptions:

```python
{
    "id": "wf_sys_cash_receipts",
    "name": "Cash Receipts Matching",
    "description": "...",
    "tier": 1,
    "vertical": None,                # or "manufacturing" / "funeral_home"
    "trigger_type": "time_of_day",   # or "manual" if user-invoked
    "trigger_config": {
        "time": "23:30",             # collision-checked against other nightly jobs
        "days": ["mon","tue","wed","thu","fri","sat","sun"],
    },
    "icon": "coins",
    "is_system": True,
    "source_service": "workflows/cash_receipts_adapter.py",
    "steps": [
        {
            "step_order": 1,
            "step_key": "run_matching",
            "step_type": "action",
            "config": {
                "action_type": "call_service_method",
                "method_name": "cash_receipts.run_match_pipeline",
                "kwargs": {"dry_run": False, "trigger_source": "workflow"},
            },
        },
    ],
    "params": [
        {"step_key": "run_matching", "param_key": "dry_run",
         "label": "Dry-run mode", "param_type": "boolean",
         "default_value": False, "is_configurable": True,
         "description": "..."},
    ],
},
```

### 3.2 `agent_registry_key` field choreography

Two-step transition (the "badge choreography"):

- **8b-alpha (insert):** add workflow row with `agent_registry_key="{agent_name}"` + placeholder steps. Visible on `/settings/workflows` Platform tab with the "Built-in implementation" badge. **(Skipped for cash receipts because no prior row existed — we jumped straight to 8b-beta.)**
- **8b-beta (activate):** clear `agent_registry_key` in the seed (omit the key entirely — the column default is NULL). Replace placeholder steps with real `call_service_method` step. Badge disappears on next frontend render.

For 8c's existing stubs (`wf_sys_month_end_close`, `wf_sys_ar_collections`, `wf_sys_expense_categorization`) the alpha→beta transition matters — those rows ALREADY exist with `agent_registry_key` set via r36 backfill, and 8c's job is the beta step: clear the field + add real steps.

Migration commit messages should say which transition step they're in.

### 3.3 Register `call_service_method` dispatch

For each adapter pipeline entry, add one line to `backend/app/services/workflow_engine.py::_SERVICE_METHOD_REGISTRY`:

```python
"{agent_name}.run_match_pipeline": (
    "app.services.workflows.{agent_name}_adapter:run_match_pipeline",
    ("dry_run", "trigger_source"),  # allowed kwargs
),
```

The allowlist prevents workflow configs from passing arbitrary kwargs. Auto-injected kwargs (`db`, `company_id`, `triggered_by_user_id`) are NEVER in the allowlist — they're special-cased by `_handle_call_service_method`.

---

## 4. Triage queue configuration

### 4.1 Three files, three registrations

For each migrated agent:

- `backend/app/services/triage/engine.py` → add `_dq_{agent_name}_triage` function + register in `_DIRECT_QUERIES`.
- `backend/app/services/triage/ai_question.py` → add `_build_{agent_name}_related` function + register in `_RELATED_ENTITY_BUILDERS`.
- `backend/app/services/triage/action_handlers.py` → add `_handle_{agent_name}_{action}` functions + register each under `"{agent_name}.{action}"` keys in `HANDLERS`.
- `backend/app/services/triage/platform_defaults.py` → add `_{agent_name}_triage = TriageQueueConfig(...)` + register via `register_platform_config(_{agent_name}_triage)`.

### 4.2 Queue config required fields

Cash receipts reference (see `platform_defaults.py::_cash_receipts_triage`):

- `queue_id` — stable string, frontend-facing (routes at `/triage/{queue_id}`).
- `item_entity_type` — free-form string. Used as handler ctx `entity_type`. For cash receipts: `"cash_receipt_match"`.
- `source_direct_query_key` — matches `_DIRECT_QUERIES` key.
- `item_display` — `ItemDisplayConfig(title_field, subtitle_field, body_fields, display_component)`. `display_component="generic"` works for most migrations; add a custom React component only if the default renderer looks bad.
- `action_palette` — list of `ActionConfig`. Every action's `handler` key MUST be registered in `HANDLERS` or the config is rejected at load time.
- `context_panels` — at minimum: one `RELATED_ENTITIES` panel + one `AI_QUESTION` panel with the new prompt key.
- `flow_controls.snooze_enabled` — true if individual items can wait; false if certs-style "decide now" urgency.
- `permissions` — typically `["invoice.approve"]` for accounting-agent queues.
- `required_vertical` — omit for cross-vertical, set for vertical-specific.

### 4.3 Suggested questions for AI panel

Four chips, no more. Questions should be **decision-oriented** ("What's the most likely invoice this payment applies to?") not informational ("What's this payment's amount?"). The user clicks a chip to prime the question box, then types + sends.

Cash receipts reference list:
- "What's the most likely invoice this payment applies to?"
- "Why is this payment hard to match?"
- "What's this customer's typical payment pattern?"
- "Should I split this across multiple invoices?"

---

## 5. Parity test requirements (BLOCKING, non-negotiable)

Every migration ships a dedicated test file at `backend/tests/test_{agent_name}_migration_parity.py`. Structure mirrors `test_cash_receipts_migration_parity.py`.

### 5.1 Required assertion categories

All five must have at least one test:

1. **Primary action identity** — the triage approve action produces the SAME row writes as the legacy agent's inline write path. Compare exact shapes (primary keys, FKs, amounts, timestamps within tolerance).
2. **Reject / negative path** — rejecting via triage produces the same anomaly-resolution state the legacy `/anomalies/{id}/resolve` endpoint writes (resolved=True, resolved_by, resolved_at, resolution_note) AND writes no financial rows.
3. **Per-anomaly resolution parity** — the anomaly's post-state (resolved + resolution_note format) matches what the legacy endpoint writes.
4. **Negative assertion (approval-type-specific):**
   - SIMPLE approval agents (cash receipts): **assert no `PeriodLock` row** written.
   - Full approval agents (month-end close): **assert exactly one `PeriodLock` row** written + **exactly one statement run triggered**.
5. **Pipeline-scale equivalence** — run the adapter's `run_match_pipeline` against the same fixture set as a legacy `AgentRunner.run_job` call; resulting financial row shapes must match (sorted by amount, FK pairs identical).

### 5.2 Shared fixture pattern

`_make_ctx()` creates a fresh tenant + admin user (`is_super_admin=True` to bypass permission gates during tests). Each parity test seeds its own fresh customer + invoice + payment + anomaly rows. Avoid fixture sharing across tests — the agent sweeps ALL rows in a tenant, so test-shared seeding causes cross-test contamination.

### 5.3 Critical fixture lesson from 8b

The CashReceiptsAgent sweeps ALL unmatched payments in a tenant. If you seed pair A + pair B in the same tenant and run the agent, the agent matches BOTH. The fix: seed pair A, run the agent, THEN seed pair B and approve via triage. Apply the same discipline for other agents that do tenant-wide sweeps (month-end close, expense categorization).

### 5.4 BLOCKING CI gate classification

Mark the test file's module docstring "BLOCKING" — CI config should fail the build on red. Phase 8b's `test_cash_receipts_migration_parity.py` module docstring is the template.

---

## 6. Latency gate requirements

Every migration extends the triage latency test family:

- `test_{agent_name}_triage_latency.py` — two BLOCKING gates:
  - `next_item` p50 < 100 ms, p99 < 300 ms.
  - `apply_action` p50 < 200 ms, p99 < 500 ms (the adapter's write pattern makes this latency-sensitive).

30 samples sequential, 3 warmups. Seed 40 pending items (enough for warmup + samples + buffer). Reference: `test_cash_receipts_triage_latency.py`.

Actual Phase 8b numbers on dev hardware:
- cash_receipts next_item: **p50=18.7ms, p99=20.1ms** (5×/15× headroom)
- cash_receipts apply_action: **p50=15.7ms, p99=22.5ms** (13×/22× headroom)

If a migration's `apply_action` is hot-path-slow (>100ms p50), the adapter is probably doing unnecessary round-trips or fetching too much related data during the action. Profile before widening the budget.

---

## 7. Scheduler transition pattern

### 7.1 From agent-invoked to workflow-invoked (the standard path)

**Pre-migration:** agent fires via direct `AgentRunner.create_job` + `run_job` call, usually from an APScheduler entry in `backend/app/scheduler.py`.

**Post-migration:** agent is still invokable directly (legacy coexistence — see §8), BUT:
- Workflow row's `trigger_type="time_of_day"` or `"scheduled"`.
- `workflow_scheduler.check_time_based_workflows()` sweep fires the workflow.
- Workflow's `call_service_method` step calls the adapter's `run_match_pipeline`.
- Adapter creates a fresh AgentJob row for this invocation.
- AgentRunner executes as before.

**Net effect:** the nightly cron is now "scheduled workflow fires adapter fires agent." The agent's side effects are unchanged. The bonus: the workflow run is tracked in `workflow_runs` + `workflow_run_steps` tables (observability + debug + audit).

### 7.2 Adding from scratch (cash receipts pattern)

Cash receipts had no scheduler entry. We set `trigger_type="time_of_day"` + `trigger_config.time="23:30"`. The workflow scheduler sweep fires it at 11:30pm ET daily.

Slot collision check against `backend/app/scheduler.py` JOB_REGISTRY + existing `wf_sys_*` rows with `time_of_day` triggers. Leave 5-min gaps where possible.

### 7.3 Reusing existing scheduler entries

If the agent already has an APScheduler cron entry that you DON'T want to remove (e.g., the job also records to `job_runs` for audit):

- Leave the APScheduler entry in place.
- Set workflow `trigger_type="manual"`.
- Have the scheduler job call `workflow_engine.start_run(wf_id, company_id, trigger_source="schedule")` instead of `AgentRunner.run_job` directly.

Neither 8b nor 8c exercises this pattern yet; document the choice when 8d or later needs it.

### 7.4 Idempotency

The workflow_scheduler sweep runs every 15 min. `_already_ran_for_record` check prevents re-firing for the same (workflow_id, record_id) within a day. For tenant-wide workflows (cash receipts — no record), the same-day check uses `workflow_id` alone. Fine for once-nightly workflows; insufficient for more frequent cadences.

---

## 8. Agent badge clearing (when + how)

### 8.1 When the badge clears

In `frontend/src/pages/settings/Workflows.tsx`, the "Built-in implementation" badge renders when `workflow.agent_registry_key !== null`. So:

- Badge present when `agent_registry_key` is set (Phase 8a stubs + Phase 8b-alpha).
- Badge absent when `agent_registry_key` is NULL (Phase 8b-beta onward).

No cache clear, no app restart. Next workflow-list render reflects the cleared field.

### 8.2 Migration path for Phase 8a stubs (8c targets)

The three existing stubs (`wf_sys_month_end_close`, `wf_sys_ar_collections`, `wf_sys_expense_categorization`) have `agent_registry_key` set via the r36 migration's hard-coded backfill. To clear it during 8c:

**Option A (preferred, seed-only):** Change the seed in `default_workflows.py` to omit `agent_registry_key`. Add a data migration that UPDATEs the column to NULL on the row + replaces placeholder steps with real ones.

**Option B (explicit migration):** Add a new migration `r37_cash_receipts_migrated` (already cleared for Phase 8b — well, cash receipts never existed so no migration needed there, but 8c will need this for month-end close etc.) that UPDATEs the `agent_registry_key` column to NULL.

8c's audit decides A vs. B. Either is fine; A is less ceremonial.

---

## 9. Coexist-with-legacy checklist (operational contract)

Phase 8b's approved operational coexistence contract applies to every migration:

### 9.1 Triage queue path is canonical for routine daily processing

The nightly scheduled workflow fires → creates AgentJob with anomalies → users process via the triage queue. This is the path users learn, the path documentation emphasizes, the path onboarding points at.

### 9.2 Legacy agent endpoint stays live for ad-hoc forensic re-runs

`POST /api/v1/agents/accounting` with `job_type="{name}"` continues to work after migration. Use cases:
- "I think last night's run missed something — let me manually re-run for the last 7 days."
- "I'm testing a new edge case — let me do a dry-run."
- "The scheduled workflow skipped for some reason — let me run it by hand."

The AgentDashboard (`/agents`) + ApprovalReview (`/agents/:id/review`) pages stay mounted in the route tree. Navigation service's `/agents` entry stays visible for users with `invoicing_ar` functional area.

### 9.3 Do NOT run both paths on the same unresolved-items set simultaneously

The triage path and the agent-runner path both read from and write to the same tables (`agent_jobs`, `agent_anomalies`, `customer_payment_applications` for cash receipts). Running them concurrently on the same unresolved payments causes duplicate-match contention.

**Convention:** workflow-triggered runs own the regular daily sweep. Ad-hoc agent-runner invocations are "pick a day the sweep didn't run" or "bounded to specific tenants with no active triage sessions."

This convention is a human-layer contract, not a code-layer invariant. When the first real race bug hits (it will eventually), the resolution is likely a row-level lock or a "processing" state on the anomaly rows. Defer that until the race happens in prod.

### 9.4 Future legacy retirement (Phase 8h or later)

When every migration is green and users have switched to the triage path:
- Deprecate `POST /api/v1/agents/accounting` — return 410 Gone.
- Remove `AgentDashboard.tsx` + `ApprovalReview.tsx` routes.
- Remove the `/agents` nav entry.

Not in scope for 8c–8f. Revisit at 8h.

---

## 10. Phase-post-migration verification checklist

Before closing a migration PR, verify each item:

- [ ] All Phase 1–current tests pass (`pytest backend/tests/ -q`).
- [ ] Parity test is GREEN (BLOCKING) — all 4–5 categories.
- [ ] Latency gates are GREEN (BLOCKING) — both next_item + apply_action.
- [ ] Unit tests cover: queue registration, `_DIRECT_QUERIES` dispatch, `_RELATED_ENTITY_BUILDERS` dispatch, handler registration, workflow engine registry entry, workflow seed shape.
- [ ] Playwright E2E covers: queue registered, workflow visible (badge status correct), legacy coexistence paths still mount.
- [ ] No tenant.preferences writes (nothing added to User.preferences JSON blob).
- [ ] No new database tables (migrations should add columns + seed data only, unless genuinely novel).
- [ ] Seed script for the AI prompt is **idempotent** (Option A pattern — runs twice produces zero writes on second run).
- [ ] Frontend `/settings/workflows` Platform tab renders the workflow WITH or WITHOUT the agent badge per the 8b-alpha/beta state.
- [ ] Legacy `/agents` + `/agents/:id/review` pages still mount (not-redirected-to-login, not 404).
- [ ] `POST /api/v1/agents/accounting` with the migrated `job_type` still works (can run ad-hoc).
- [ ] Session log entry in `FEATURE_SESSIONS.md` documents: parity assertions, latency numbers, any divergences from template, anything surprising.
- [ ] `WORKFLOW_ARC.md` marks the phase complete.

---

## 11. Open questions (tracked from Phase 8b, revisited as migrations progress)

### 11.1 ApprovalReview.tsx future

At what point does the legacy `/agents/:id/review` page retire? Options:
- Absorb into triage: the page becomes a read-only "view past runs" surface + button to open the queue.
- Stay as a forensic-debug page for re-runs (keep indefinitely).
- Remove at Phase 8h.

**Decision forcing function:** when all 13 agents are migrated (end of 8f), the `/agents` dashboard becomes a thin audit surface. Decide at 8h.

### 11.2 Mutual-exclusion guard at `workflow_engine.start_run`

When a workflow has both `agent_registry_key` set AND real steps, which executes?

Phase 8b's answer: **steps win** (agent_registry_key is informational today — no dispatch code reads it). Risk: future code may assume one or the other. Hedge: add an explicit `start_run` warning log if both are present.

**Action (deferred to 8c):** add the log line in the first 8c migration that actually does the alpha→beta transition. Until then, no one hits this case in practice.

### 11.3 Period-lock discipline for 8c+

Month-end close (8c) writes period locks. The parity test's **positive** assertion on `PeriodLock` rows is new territory. Questions:
- Does the triage approve path trigger the same lock-writing as the legacy approval-gate callback?
- If period lock fails (e.g., period already locked), does the adapter surface it cleanly?
- Should the lock fire during the workflow step (synchronously in the approve handler) or be a follow-up workflow step?

8c's audit answers these concretely.

### 11.4 `triage_approval` step type vs. input

Phase 8b uses `input` step type as the approval gate (pauses the workflow, waits for triage action to resume). Is this the right pattern long-term?

Alternatives:
- Dedicated `triage_approval` step type with first-class support for queue_id + linkage back to the run.
- Continue with `input` + convention.

**Decision:** `input` works for 8b because the workflow's single step runs the full pipeline; approval happens out-of-band in triage, not as part of the workflow's state machine. If 8c–8f hit cases where the workflow needs to branch based on approval outcome, introduce `triage_approval`.

---

## 12. Appendix — Phase 8b artifacts as reference

- **Parity adapter:** `backend/app/services/workflows/cash_receipts_adapter.py`
- **Workflow engine dispatch:** `backend/app/services/workflow_engine.py::_handle_call_service_method` + `_SERVICE_METHOD_REGISTRY`
- **Workflow seed:** `backend/app/data/default_workflows.py::TIER_1_WORKFLOWS` (entry `wf_sys_cash_receipts`)
- **Triage direct query:** `backend/app/services/triage/engine.py::_dq_cash_receipts_matching_triage`
- **Related entities:** `backend/app/services/triage/ai_question.py::_build_cash_receipts_matching_related`
- **Action handlers:** `backend/app/services/triage/action_handlers.py` (4 `_handle_cash_receipts_*` functions)
- **Platform default config:** `backend/app/services/triage/platform_defaults.py::_cash_receipts_triage`
- **Seed script:** `backend/scripts/seed_triage_phase8b.py`
- **BLOCKING parity test:** `backend/tests/test_cash_receipts_migration_parity.py`
- **BLOCKING latency test:** `backend/tests/test_cash_receipts_triage_latency.py`
- **Unit tests:** `backend/tests/test_cash_receipts_phase8b_unit.py`
- **Playwright E2E:** `frontend/tests/e2e/workflow-arc-phase-8b.spec.ts`

---

## 13. Latent bugs surfaced during Phase 8b (flagged for separate sessions)

Not 8b's scope, but discovered during the audit:

1. **`wf_sys_ar_collections` declares `trigger_type="scheduled"`** in `default_workflows.py`, but `workflow_scheduler.check_time_based_workflows()` only dispatches `time_of_day` and `time_after_event` triggers. **Consequence:** the AR collections workflow isn't actually firing on schedule today. Needs a separate cleanup session — either (a) extend the scheduler to honor `"scheduled"` + `trigger_config.cron`, or (b) change the seed to use `time_of_day` with an explicit wall-clock time (simpler, matches operational semantics). Flagged for Phase 8h or a standalone cleanup.
2. **Hardcoded approval-gate email HTML** in `backend/app/services/agents/approval_gate.py::_build_review_email_html()`. Pre-dates D-7's delivery abstraction. Should migrate to a managed template per D-7. Not 8b's to fix — parity for cash receipts requires preserving the exact email body. Platform-wide cleanup in a future session.
3. **Orphan migrations `r34_order_service_fields` → `r39_legacy_proof_fields`** (flagged in Phase 8a audit). Still unreconciled. Not affected by 8b. Still on the post-arc cleanup list.

---

## 14. Template changelog

- **2026-04-21 (Phase 8b complete):** Initial template, written alongside the cash receipts migration. Cash receipts is the working example throughout.
- _Future updates land at the end of each phase (8c, 8d, etc.) as patterns evolve._
