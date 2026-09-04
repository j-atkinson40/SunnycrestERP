# The 8,192-row approval queue

**Date:** 2026-09-04 · **Read-only against production.** Connection-level guard
(`-c default_transaction_read_only=on`), connection string redacted via
`urlparse`. No writes, no bulk resolution, no deletion, nothing touched on
`hopkins-fh`. Every remedy in §6 is a production write and is James's.

---

## 0. Headline, and a correction to a claim I made this morning

**The queue is not 8,192 decisions. It is on the order of ~50 distinct
actionable conditions, plus ~8,140 rows that are either re-raises of two
conditions or residue from a bug fixed in July.**

⚠️ **AND I WAS WRONG ABOUT NOTIFICATIONS.** STATE.md (977d64f3, this morning)
says *"nothing reports it: all eleven triage queues fire zero notifications
(STATE 2026-05-26), so 2,046 pending approvals on the live tenant have
accumulated unannounced."* Measured today:

```
notifications, category='agent_anomaly_pending'   2,643   2026-05-23 → 2026-09-03
sunnycrest unread notifications                   2,179
task_details, provenance_kind='anomaly_detection' 2,333
```

They were announced. **2,643 times.** Nobody read them.

I inherited "11/11 fire zero notifications" from a 2026-05-26 STATE entry
without checking whether a later entry closed it — and one did, dated **the same
day**, recording that the (c) build arc wired producer-site notifications. This
is the failure the "when did this last work?" rule exists to prevent, committed
while writing the rule down. The correction is landed in STATE.md alongside this
document.

The real finding is worse than silence: the system told someone 2,643 times
about the same two conditions, which is how a channel becomes unreadable.

---

## 1. Q1 — why the sweep manufactures jobs, and whether its condition satisfies the contract

### The sweep

`wf_sys_expense_categorization` (`app/data/default_workflows.py:1485`):

```python
"trigger_type": "scheduled",
"trigger_config": {
    "cron": "*/15 * * * *",
    "timezone": "America/New_York",
},
```

**Every 15 minutes = 96 runs/day, per tenant.** `scheduler._run_per_tenant`
(`app/scheduler.py:89-108`) iterates `_get_active_tenant_ids()` unconditionally
— there is no data-presence predicate, so a tenant with nothing to categorize is
swept identically to one with a full ledger.

CLAUDE.md records the cron as a deliberate workaround, not an accident: the
trigger was changed from `event` + `expense.created` because "the event dispatch
system doesn't exist today (no event subscription registry, no publish-event
hooks)." The polling interval is the cost of that absence.

### Its condition, and what it yields instances over

**It yields one job per RUN, not one per condition needing attention.** That is
the whole defect, and it is visible in the identity it writes
(`base_agent.py:422`):

```
provenance_ref_type = "agent_job"
provenance_ref_id   = self.job_id     ← the RUN's id
```

CLAUDE.md states the task substrate's idempotency key is
`(provenance_kind + provenance_ref + event_kind)`, partial-unique. Because
`provenance_ref` is the run, **every run is a distinct key**, so idempotency
cannot fire. The same uncategorized vendor-bill line produces a new job, a new
anomaly, a new task and a new notification every fifteen minutes, indefinitely.

### ⚠️ Contract-satisfaction assessment: IT FAILS, and it fails on identity

Against the fragment contract as landed (`d50094de`), declaration (2) requires
"a predicate that yields zero or more fragment instances, each carrying scope,"
with `condition_inputs` "enumerable and snapshottable, because the surface arc's
deferral machinery wakes a deferred prompt on divergence of those inputs."

| Requirement | Sweep as written |
|---|---|
| yields zero or more instances | ✅ yields 0 or 1 per run — the `anomaly_count == 0 → return` guard at `base_agent.py:397` already suppresses quiet runs |
| each carrying scope | ⚠️ partial — the job carries a tenant and a period, but not the entity the decision is about |
| `condition_inputs` enumerable | ✅ the uncategorized lines are enumerable |
| **`condition_inputs` snapshottable, so deferral wakes on divergence** | ❌ **FAILS** |

**The specific failure:** the contract keys an instance on the CONDITION; the
sweep keys it on the RUN. A user who defers this prompt is deferring
`instance_key = <job_id>`. Fifteen minutes later the same underlying line
produces a *different* job id, so the deferral matches nothing and the prompt
returns — not because its inputs diverged, which is the only sanctioned wake, but
because its identity was never stable. **Deferral is unimplementable against a
run-keyed condition.**

To satisfy the contract this condition must key on the thing needing attention —
the vendor-bill line — so that one unresolved line is one instance for as long as
it stays unresolved, regardless of how often the sweep runs.

**This is the contract's first live test against pre-existing code, and it
catches a real defect that four months of production did not surface.** Worth
recording as evidence the discipline does work, before five sessions are built
on it.

---

## 2. Q2 — what is actually in the queue, enumerated

By tenant × job type × whether the job carries any finding. Counts are rows from
`agent_jobs`, bounded by the full table, not by a page of results.

| tenant | job_type | rows | of which `anomaly_count=0` | first | last |
|---|---|---:|---:|---|---|
| hopkins-fh | expense_categorization | 5,855 | **5,855** | 2026-05-06 | 2026-07-17 |
| sunnycrest | expense_categorization | 2,018 | 0 | 2026-08-10 | 2026-08-31 |
| hopkins-fh | cash_receipts_matching | 122 | **122** | 2026-05-07 | 2026-07-16 |
| st-marys | expense_categorization | 92 | **92** | 2026-07-16 | 2026-07-17 |
| hopkins-fh | ar_collections | 60 | **60** | 2026-05-07 | 2026-07-16 |
| sunnycrest | ar_collections | 25 | 0 | 2026-08-10 | 2026-09-03 |
| testco | ar_collections | 14 | 0 | 2026-08-21 | 2026-09-03 |
| sunnycrest | cash_receipts_matching | 2 | 0 | 2026-08-03 | 2026-08-10 |
| st-marys | cash_receipts_matching | 2 | 0 | 2026-07-16 | 2026-07-16 |
| st-marys | ar_collections | 1 | 0 | 2026-07-16 | 2026-07-16 |
| sunnycrest | month_end_close | 1 | 1 | 2026-08-10 | 2026-08-10 |

All 8,192 are `dry_run = false`. 8,188 are `trigger_type = 'workflow'`; 4 manual.

### Two populations, and neither is a backlog of decisions

**Population A — 6,130 jobs with nothing in them.** Every `anomaly_count=0` row
above, all on `hopkins-fh` / `st-marys`, all stopping between 2026-07-16 and
07-17. A job with zero anomalies has, by definition, no decision to present.
`base_agent._nothing_to_approve()` (`:105-110`) now returns True for exactly
this case and the guard at `:397` suppresses it — so the bug that parked
empty jobs in `awaiting_approval` was fixed around 2026-07-17, and **these
6,130 rows are orphaned residue predating the fix.** hopkins-fh's post-fix jobs
land in `completed` (483 of them, running through 2026-09-03), which confirms
the sweep still runs there and now terminates correctly.

**Population B — 2,062 jobs that DO carry a finding, over almost nothing.**
Sunnycrest's 2,018 expense_categorization jobs each have `anomaly_count = 1`.
Exactly one. All 2,018. Resolving what those anomalies actually are:

```
unresolved agent_anomalies, platform-wide, by type:
  expense_no_gl_mapping           1,825 rows   1 distinct description
  expense_classification_failed     192 rows   1 distinct description
  collections_critical               24 rows  24 distinct descriptions
  collections_follow_up              23 rows  23 distinct descriptions
  ar_balance_drift                    5 rows   3 distinct
  payment_unmatched_stale             4 rows   2 distinct
  … remainder single-digit
```

**1,825 rows, one description.** One vendor-bill line with no GL mapping,
re-raised every fifteen minutes for three weeks. Another 192 rows are a second
single condition.

**So the actionable content of the entire 8,192-row queue is approximately 50
distinct conditions** — 24 `collections_critical` + 23 `collections_follow_up`,
which have distinct descriptions per row and are therefore genuinely separate
decisions, plus a handful of single-digit types. Everything else is duplication
or residue.

⚠️ Measured: the row counts and distinct-description counts. **Inferred:** that
one description means one underlying line. Two different lines could share a
description string. Confirming requires reading `entity_id` per row, which this
pass did not do because it means reading tenant financial records.

---

## 3. Q3 — the twelve queues and their notifications

⚠️ **There are TWELVE queues, not eleven.** Enumerated from
`platform_defaults.py` — 12 distinct `queue_id` assignments, and 12 matching
`_dq_*` builders. The "11/11" figure in STATE (2026-05-26) was correct when
written; **`reconciliation_review_triage` was added 2026-08-03 (`16bd8829`)**
and has never been assessed. Do not inherit the eleven.

The notification path is not per-queue. It runs through
`tasks/subscribers/notification_subscriber.py`, which registers for
`task_created` and `task_assigned` only, and tasks come from
`base_agent._dispatch_notification`, which branches on `job_type`.

| queue | notification status | category |
|---|---|---|
| expense_categorization_triage | **FIRES** — measured, dominates the 2,643 | code, working |
| ar_collections_triage | **FIRES** — measured | code, working |
| cash_receipts_matching_triage | **FIRES** — in the allowlist | code, working |
| month_end_close_triage | **FIRES** — own branch, `agent_job_awaiting_approval` | code, working |
| catalog_fetch_triage | **FIRES** — `catalog_sync_pending_review`, 4 rows measured | code, working |
| safety_program_triage | **FIRES** — `compliance_expiry`, 2 rows measured | code, working |
| aftercare_triage | falls through `else: return` (`:415`) | **not established** |
| ss_cert_triage | falls through | **not established** |
| task_triage | falls through | **not established** |
| workflow_review_triage | falls through | **not established** |
| email_unclassified_triage | falls through | **not established** |
| reconciliation_review_triage | falls through; added after the 11/11 audit | **not established** |

### The six, closed by measurement (added after the first pass)

Production has exactly **two** `task_details.provenance_kind` values
(`anomaly_detection` 2,333; `integration_event` 2) and **five** notification
categories, none of which belong to these six. So no producer-site path among
them has fired. Classifying by whether the CONDITION ever occurred, which is the
only honest split:

| queue | source rows in production | verdict |
|---|---|---|
| `ss_cert_triage` | `social_service_certificates` = **0** | **untestable** — condition never occurred |
| `aftercare_triage` | `agent_anomalies` type `fh_aftercare_pending` = **0** | **untestable** — condition never occurred |
| `email_unclassified_triage` | `email_messages` = **0** | **untestable** — condition never occurred |
| `task_triage` | reads the task substrate itself | **fires by construction** — its rows ARE tasks, and `task_created` is what the subscriber listens for |
| `reconciliation_review_triage` | `reconciliation_exceptions` = **31** | **gap** — condition present, nothing produced |
| `workflow_review_triage` | `workflow_runs` = 17,715, **11,930 `awaiting_input`** | **gap, and the largest object in this investigation** |

⚠️ **Three of the six cannot be classified as working or broken, because their
input has never existed.** A path with no input produces the same silence
whether it works or not. Recording them as "untestable" rather than as either —
this is the absent-signal asymmetry at producer altitude.

### ⚠️ The instrumented path and the taken path are different paths

`workflow_review_triage` is worth its own finding. Two transitions exist:

- `workflow_engine.py:1096-1115` creates a `WorkflowReviewItem` and **does**
  call `create_task_with_provenance`. Production count: **8 rows.**
- `workflow_engine.py:535` sets `run.status = "awaiting_input"` and creates
  **nothing**. Production count: **11,930 rows.**

The instrumented path is taken 8 times; the path production actually takes,
11,930 times, has no instrumentation at all. **11,766 of those are "Expense
Categorization"** — the same `*/15` cron as §1, so one misconfigured trigger has
produced roughly twenty thousand stuck rows across two unrelated tables.

This is adjacent to complete-machinery-behind-an-unprovisioned-entrance but is
not it: the machinery is complete AND reachable AND reached — eight times. The
volume simply goes somewhere else. Offered as a variant — *the instrumented path
is not the taken path* — rather than forced into the existing shape or dropped.

⚠️ **This corrects the first pass of this document,** which said "No unreachable
notification-path instance was found." That remains true literally, and was too
narrow a question: nothing was unreachable, and 11,930 rows still went
unreported.

**No unreachable-notification-path instance was found**, so this is NOT a
fourth complete-machinery-behind-an-unprovisioned-entrance. The path exists, is
reachable, and fires prolifically. Reported as a negative because the dispatch
asked for it specifically.

---

## 4. Q4 — growth, and why it stopped without being fixed

`awaiting_approval` rows created per day:

```
2026-08-21   37
2026-08-22   98
…            98/day through 2026-08-31
2026-09-01    2
2026-09-02    2
2026-09-03    2
```

**96–98/day matches 96 runs/day exactly** (`*/15` = 4/hr × 24). The driver is
the cron, one job per run, one anomaly per job.

**The collapse on 2026-09-01 was not a repair.** No code shipped — the only
commits between 08-30 and 09-02 are three documentation commits. What changed is
the data:

```
expense_categorization, since 2026-08-20:
  before 09-01   awaiting_approval  1,143   (total anomalies 1,143)
  before 09-01   complete           1,069   (total anomalies 0)
  on/after 09-01 complete             684   (total anomalies 0)
```

The underlying uncategorized line was resolved around 08-31, so runs now find
nothing and terminate through the `anomaly_count == 0` guard. **The queue stopped
growing because the condition cleared, not because anything was fixed.** The
next unmapped vendor-bill line resumes growth at 96/day.

Current residual growth of 2/day is `ar_collections` on sunnycrest and testco,
which carry distinct findings and are the legitimate part.

---

## 5. What this means for the note surface

The dispatch's premise holds and is now quantified. A fragment over
`awaiting_approval` would truthfully report "8,192 items need your approval,"
of which ~50 are decisions. It would be correctly reporting a broken queue, and
no fragment-layer declaration can fix that — which is why this precedes the
surface.

It also shows the failure is already live one layer down: 2,643 notifications
fired, 3,915 sit unread across all tenants, and the note surface would be the
third channel to carry the same undifferentiated volume.

---

## 6. Remedies — every one is a production write, owned by James

**None of these were run. Commands are named, not executed.**

1. **Key the condition on the entity, not the run.** `base_agent` passes
   `provenance_ref_id=self.job_id`; it should pass the vendor-bill line so the
   substrate's `(provenance_kind, provenance_ref, event_kind)` uniqueness fires
   and one unresolved line is one task forever. Code change plus a decision
   about existing rows. **This is also what the fragment contract requires.**
2. **Retire the 6,130 zero-anomaly orphans** (hopkins-fh 6,037, st-marys 92,
   sunnycrest month_end_close 1, hopkins cash_receipts 122, hopkins
   ar_collections 60). They predate the July fix and contain nothing. A guarded
   `UPDATE agent_jobs SET status='complete' WHERE status='awaiting_approval'
   AND anomaly_count=0` would do it — **not run; the disposition of production
   rows is not the investigator's call**, and `complete` vs `completed` (§7)
   should be settled first.
3. **Deduplicate the 2,017 re-raised anomalies** down to their distinct
   conditions. DECISIONS 2026-09-01 already canonised "anomaly supersede is a
   condition of shipping any anomaly-writing fix"; this agent predates it and
   does not supersede.
4. **Decide the cron.** `*/15` exists only because event dispatch does not.
   Either build the event hook or widen the interval; at 96 runs/day per tenant
   it is a poll pretending to be a trigger.
5. **Classify the six unestablished queues** (§3) before the note surface reads
   any of them.
6. **Assess `reconciliation_review_triage`**, added after the 11/11 audit and
   never covered by it.

---

## 7. Adjacent findings, not investigated

- **`agent_jobs.status` carries both `complete` (2,464) and `completed` (804).**
  Two spellings of one terminal state. Any status filter naming one silently
  misses the other; remedy 2's `UPDATE` would inherit the ambiguity.
- **1,289 `delivery_failed` notifications**, unread, not examined here.
- **3,915 unread notifications total** across four tenants.

---

## 8. Method notes

- Read-only throughout. Two constructed column names failed loudly and were
  re-read off the models: `invoices.total_amount` (actual: `total`,
  `amount_paid`, `amount_credited`) and `agent_anomalies.job_id` (actual:
  `agent_job_id`, and `resolved` is a boolean, not `resolved_at` alone). Both
  errored rather than returning a plausible number — the good failure mode.
- Per-query rollback isolation throughout: a failed query aborts the
  transaction and makes the *next* table report an error about something never
  touched.
- Counts are rows. Growth counts are rows per `created_at::date`. Queue count is
  distinct `queue_id` assignments. Every count is bounded by the full table, not
  by a result page.
- The eleven-queue figure was NOT inherited from the dispatch; enumeration
  returned twelve.
- §2's population split is measured; the "one description = one line"
  interpretation is marked inferred.
