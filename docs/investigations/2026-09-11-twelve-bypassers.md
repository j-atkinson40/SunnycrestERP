# The twelve bypassers — three STOPs, and "instrumentation gap" is wrong for seven

**Date:** 2026-09-11 · **HEAD:** `2e268934` · **Read-only. No build.**

Nothing inherited — 37, 12, 9, 3, 10,268 and 62,788 were all re-measured.

---

## 0. Headline

**Three STOPs, and the middle one is the finding.**

- **§0b does NOT fire.** None of the three hand-rolled jobs has 0a's
  discarded-return-value defect. `dispatch_auto_finalize`'s 10,268 rows are not
  unexamined completion claims.
- **§0 FIRES, at seven of nine.** "Should log every run" is wrong for seven. Two
  are dry-run and do not act; five iterate empty sets on production and always
  will until someone connects an account.
- **§0c does NOT fire.** Nothing reads `job_runs` in aggregate. One listing
  endpoint, `limit=50`.

⚠️ **And the one job that genuinely deserves a row is the one nobody flagged.**
`workflow_time_based_check` does real work every 15 minutes, and its target
`check_time_based_workflows` **raises `RuntimeError` on partial failure** —
documented as *"a partial sweep is never reported as clean."* The scheduler
function catches that raise, logs it, and writes nothing durable. A target
designed to refuse silent partial success is wrapped by a function that silences
it.

---

## 1. §0b — the three hand-rolled jobs are fine

All three assign their target's return value and hardcode `status="completed"` on
the success path. That looks like 0a's defect and is not, because **none of their
targets ever returns an error marker**:

| job | target | how a failure travels |
|---|---|---|
| `platform_incident_dispatcher` | `dispatch_pending_incidents` | **no broad except** — propagates to the job's own handler → `status="failed"` |
| `dispatch_auto_finalize` | `auto_finalize_pending_schedules` | two broad handlers, both **per-item inside loops** (coverage 0.14, 0.05) |
| `platform_health_recalculate` | `calculate_all_tenant_health` | one broad handler, **per-item in a loop** (0.17) |

0a's fix mattered because `run_ar_aging_monitor` and its two siblings *return*
`{"error": str(e)}`. These targets return `results`. There is nothing to read.

They do share (c)'s residual — every-item-failed returns normally — but that is
(c), not a separate defect. ⚠️ Note `dispatch_auto_finalize` records
`success_count=sum(len(r.finalized_dates) …)`, so an all-failed run is at least
*distinguishable in the data* as `success_count=0`. The wrapper path records less.

---

## 2. §0 — what the nine should actually do

Frequencies read from the registered triggers at runtime:

| job | fires | per day |
|---|---|---|
| `moc_event_matcher` | every 1 min | 1,440 |
| `email_imap_polling_sweep` | every 5 min | 288 |
| `moc_schedule_sweep` | every 15 min | 96 |
| `workflow_time_based_check` | every 15 min | 96 |
| `calendar_token_refresh_sweep` | hourly | 24 |
| `email_token_refresh_sweep` | hourly | 24 |
| `email_subscription_renewal_sweep` | hourly | 24 |
| `calendar_subscription_renewal_sweep` | hourly | 24 |
| `onboarding_pattern` | monthly | ~0.03 |

⚠️ **Logging every run would add ~2,016 rows/day — about 736,000 a year, into a
table that currently holds 63,837 rows in total.** Eleven times the existing
table, every month, and `moc_event_matcher` alone would fill the `limit=50`
listing endpoint's most recent page with 35 minutes of itself.

### They are four different things, not one gap

**(a) An open-coded wrapper — 1 job. `onboarding_pattern`.**
21 lines that call `_get_active_tenant_ids()`, loop per tenant with its own
`SessionLocal`, and count success/errors — `_run_per_tenant` reimplemented minus
`_log_job_run`. **Should use the wrapper.** Monthly, so no volume concern, and
it is the cheapest of the nine by a distance.

**(b) Real work, deserves a row — 1 job. `workflow_time_based_check`.**
Dispatches `time_of_day`, `time_after_event` and `scheduled` workflows. Its
target raises on partial failure by design; the job swallows the raise. 96/day is
tolerable. **Should log every run**, and this is where the value is.

**(c) Dry-run, does not act — 2 jobs.** `moc_event_matcher`,
`moc_schedule_sweep`. Both log literally `"(dry-run)"`. `moc_event_matcher`
already logs only `if result.get("processed")`. **Should log nothing**, because a
`job_runs` row asserts a job ran and did its work, and these do not have work to
do yet. Re-annotate as design, not debt.

**(d) No input in production — 5 jobs.** Measured read-only:

```
calendar_accounts .............................. 0
  ...active with credentials ................... 0
email_accounts ................................. 0
  ...active .................................... 0
```

All five iterate empty sets, every run, and will until someone connects an
account. **Should log only runs that did work** — which today is none, so they
write nothing and the absence is correct rather than missing.

⚠️ This is the unprovisioned-entrance shape: the machinery is built and correct
and nothing produces its input. The right response is not to instrument the
silence.

---

## 3. §0c — nothing reads `job_runs` in aggregate

One reader: `GET /api/v1/internal/jobs/runs` (`internal.py:62`). Ordered by
`started_at desc`, `limit=50`, optional `job_type` filter. No count, no sum, no
dashboard, no alert.

So adding job types moves **no computed number anywhere**. The STOP does not
fire.

⚠️ **But the default listing would be crowded out.** At 50 rows ordered by
recency, a job firing every minute owns the page. That is a usability
consequence, not a correctness one, and it argues for (c) and (d) above
independently of volume.

⚠️ And a third population claim is exposed by API: `internal.py:58` returns
`{"jobs": sorted(JOB_REGISTRY.keys()), "count": len(JOB_REGISTRY)}` — **29**,
the manually-triggerable subset, presented as "the jobs".

---

## 4. Per-job summary — all twelve

| job | reports today | should | cost |
|---|---|---|---|
| `dispatch_auto_finalize` | hand-rolled row | unchanged | — |
| `platform_health_recalculate` | hand-rolled row | unchanged | — |
| `platform_incident_dispatcher` | hand-rolled row | unchanged | — |
| `onboarding_pattern` | nothing | **use `_run_per_tenant`** | ~10 lines deleted |
| `workflow_time_based_check` | nothing | **log every run** | small; 96/day |
| `moc_event_matcher` | nothing | **nothing** (dry-run) | re-annotate |
| `moc_schedule_sweep` | nothing | **nothing** (dry-run) | re-annotate |
| `calendar_token_refresh_sweep` | nothing | only when work | no-op today |
| `calendar_subscription_renewal_sweep` | nothing | only when work | no-op today |
| `email_imap_polling_sweep` | nothing | only when work | no-op today |
| `email_subscription_renewal_sweep` | nothing | only when work | no-op today |
| `email_token_refresh_sweep` | nothing | only when work | no-op today |

**Two jobs to change, two to re-annotate, five to leave and revisit when an
account exists, three already correct.** The item is much smaller than "nine
jobs need instrumentation".

---

## 5. Method notes

- Frequencies came from the **registered trigger objects** at runtime, not from
  reading cron strings in source.
- Routing classification used `fn.__code__.co_names` on the registered callable.
- ⚠️ **One constructed table name.** I probed `calendar_account_sync_states`; it
  does not exist. `calendar_accounts` returning 0 already settled the question,
  so the error changed nothing — but it is the filename-shaped guess again, and
  the real sync-state table's name was never established.
- One statement per connection; production read through a connection-level
  read-only guard.
