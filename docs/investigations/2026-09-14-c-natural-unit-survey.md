# Item (c) — the survey. Population is 12, not 27, and the STOP does not fire.

**Date:** 2026-09-14 · **HEAD:** `5bb6f64a` · **Read-only. No build.**

The natural-unit survey, attempted twice before and blocked both times on the
population. Nothing inherited — 27, 37 and 10 were re-enumerated at runtime.

---

## 0. Headline

**(c) applies to 12 of the 27 wrapped jobs.** The other 15 **raise** on failure,
so `_run_per_tenant` / `_run_global` already records `failed` and their results
are already unambiguous. Migrating them would be churn against no defect.

**The STOP does not fire.** Of the 12, eleven have a natural item unit. One —
`run_reorder_suggestion_job` — does one thing per tenant, and already says so
richly.

⚠️ **And the third state already exists, in four incompatible spellings.** (c)
is not inventing "no work was needed"; it is unifying something four targets
already express and no caller reads.

---

## 1. The population, re-enumerated

37 registered · 27 wrapped · 10 on the ratchet's exception list. Return
annotations across the 27: **21 `dict`, 4 `int`, 1 `None`, 2 unannotated.**

### ⚠️ The discriminator is whether the target SWALLOWS, not what it returns

"All items failed" can only masquerade as "nothing to do" where failures are
caught. Where they propagate, the wrapper records `failed` and the ambiguity
never arises.

**(c) applies — target swallows (12):**
`activate_scheduled_versions` · `check_time_based_workflows` ·
`enrich_payment_patterns` · `raise_tasks_for_health_findings` ·
`run_ap_upcoming_payments` · `run_ar_aging_monitor` · `run_collections_sequence` ·
`run_discount_expiry_monitor` · `run_reorder_suggestion_job` ·
`run_uncleared_check_monitor` · `sweep_briefings_to_generate` ·
`sweep_notes_to_settle`

**Already unambiguous — target raises (15):** the rest.

⚠️ This corrects a framing I have used all along, including in the dispatch
that asked for this survey. The `int` returners looked like (c)'s clearest
case — `return 0` meaning both "none to do" and "all failed". Measured, only
**one of the four** (`activate_scheduled_versions`) swallows. For
`expire_stale_quotes`, `enrich_funeral_home_profiles` and `detect_all_insights`,
`return 0` already means exactly one thing.

---

## 2. The natural unit, per job

**Eleven of the twelve iterate a real unit** — bills, invoices, customers,
users, notes, workflows, findings, versions. A count of attempted items is
meaningful for each.

**One does not.** `run_reorder_suggestion_job` produces at most one suggestion
per tenant. An "attempted items" count would be 1 or 0 and would mean nothing
the wrapper's own tenant count does not already say.

⚠️ **And for every per-tenant job, `_run_per_tenant` ALREADY counts the unit.**
It records `tenant_count`, `success_count`, `error_count`. So a target that does
one thing per tenant does not need to report a count at all — it needs to report
a **state**. That is the survey's shape finding: counts alone do not fit, and
neither does a state alone.

**One job with no report at all:** `generate_draft_invoices(db, tenant_id) -> None`,
annotated `-> None`, processing N orders per tenant. "20 created", "all failed"
and "nothing to do" are the same value. It is in the raising group, so the
wrapper catches a hard failure — but a *silent* no-op is indistinguishable from
a successful run.

---

## 3. ⚠️ The third state already exists, four ways

```
run_incomplete_customer_profile_job   {"alerted": False}
run_tax_filing_prep                   {"skipped": True, "reason": "reminders_disabled"}
run_reorder_suggestion_job            {"suggestions": 0, "status": "stock_ok"}
suggest_cemetery_connections…         {"created": n, "skipped": n}
```

**And `skipped` already means two different things.** In `run_tax_filing_prep`
it is a boolean: *the whole run was skipped*. In
`suggest_cemetery_connections_for_new_tenants` it is a count: *n items were
skipped*. One key, two questions — the conflation shape, already present in the
return vocabulary.

**Consequence for the shape: whatever (c) chooses must not reuse `skipped`.**
Adopting it would inherit an ambiguity rather than remove one.

---

## 4. §2 — what `job_runs` should record. Options, not a choice.

Re-verified rather than inherited: **one reader**, `GET /internal/jobs/runs`
(`internal.py:88`), recency-ordered, `limit=50`, no count or sum anywhere. So
whatever is recorded changes what the table means going forward and moves no
computed number.

For an all-items-failed run:

- **`failed`** — truthful and loud. But it is not the same as a crash, and
  conflating them costs the distinction the wrapper currently makes between
  "raised" and "reported".
- **`completed` with `error_count = n`** — preserves that distinction and relies
  on a reader noticing the count. `error_count` is already a column and already
  populated by 0a's path.
- **A third status** (`degraded` / `completed_with_errors`) — most precise, and
  the only option that changes the status vocabulary, which is the one thing the
  single reader displays verbatim.

⚠️ STOP per the dispatch. Not picked.

---

## 5. §3 — what (c) makes stale

**`CLAUDE.md:1682-1683`, "### Nightly Agent Jobs":**

> Add function in the appropriate service file. Add wrapper in
> `backend/app/scheduler.py`. Add to `JOB_REGISTRY`. Per-tenant jobs use
> `_run_per_tenant()`.

Four instructions, none of which mentions a return value. After (c) it needs a
fifth — what the function returns, and that returning `None` will not be valid.

⚠️ It is also **already incomplete**, before (c): it does not say that a new
scheduled job must route through a wrapper or be declared on the ratchet's
exception list. A reader following this recipe today produces a job that passes
the ratchet only because `_run_per_tenant` is mentioned in the last sentence as
an option rather than a requirement.

Not edited — canon, and James's.

---

## 6. Method notes

- Population enumerated at runtime (`register_all_jobs()` then `get_jobs()`),
  not from `add_job` call sites, which report 28 and miss ten registered in a
  loop.
- Swallow classification by AST over each resolved target — all 27 resolved, no
  target unlocated.
- ⚠️ **The `int`-returner correction came from checking, not from reading.** The
  four looked identical in the return survey. Only running the handler analysis
  over them separated one from three.
