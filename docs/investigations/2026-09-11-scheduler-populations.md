# Item (c) preliminary — there is no single scheduler substrate

> ## ⚠️ CORRECTED 2026-09-11, SAME DAY — THE COUNTS BELOW WERE WRONG
>
> This document reported **28 scheduled jobs**, **15 through a wrapper**, and
> **10 with no record**. All three were undercounts, and the cause is the defect
> the document itself is about.
>
> `scheduler.py` registers ten jobs in a LOOP over a `nightly_jobs` table. A
> static count of `add_job` CALL SITES sees that as one. Counting call sites
> instead of registrations is the wrong unit — reported while committing it.
>
> **Corrected, by expanding the loop:**
>
> ```
> scheduled REGISTRATIONS ........ 37   (27 static + 10 from the loop)
> JOB_REGISTRY entries ........... 29
> through a wrapper .............. 25   ← 0a covers these
> hand-rolled (_log_job_run) ......  3   ← 0a does NOT reach
> no job_runs row at all .......... 9   (4 in-file + 5 calendar/email sweeps)
> ```
>
> **And there is NO registry discrepancy.** Every one of the 29 registry entries
> IS scheduled. Eight scheduled jobs are absent from the registry — the moc,
> workflow-time-check, calendar and email sweeps, none of which is meant to be
> hand-fired. 37 − 8 = 29, exactly.
>
> ⚠️ **The ten I listed as "in the registry, never scheduled" are the loop's ten**,
> `ar_aging_monitor` among them — which production shows running 264 times. That
> alone should have stopped the claim: a job cannot be unscheduled and running.
>
> The findings below SURVIVE with different denominators. Ten of twenty-eight
> becomes nine of thirty-seven; the hand-rolled three and the
> highest-traffic-job-on-an-uncovered-path finding are unchanged.


**Date:** 2026-09-11 · **HEAD:** `b69d9c73` · **Read-only. No code changed.**

Two answers. §0b first, because it was the one asked for first.

---

## §0b — `_run_global` is fine, and 0a's report was not a false claim

**`_run_global` consults `_reported_error`, and it did from the start.**
`292d8662`'s diff adds two call sites, one per wrapper, and
`test_scheduler_reported_errors.py` carries
`test_global_records_FAILED_when_the_target_reports` and
`test_global_still_completes_on_a_normal_return` — both passing.

The visibility fix was not half-landed and the record is accurate.

---

## §0 — STOP. The population the dispatch names does not exist

The preliminary asks for each wrapped job's natural unit. That cannot be answered
yet, because **"the wrapped jobs" is not the set of scheduled jobs**, and the
difference is most of the problem.

### Four populations, and none of them is 13 or 25

```
JOB_REGISTRY entries ................ 29    (manual-trigger registry)
scheduler.add_job() calls ........... 28    (what actually runs on a schedule)
functions wrapping a runner ......... 25    (what the 2026-09-11 sweep counted)
scheduled AND through a wrapper ..... 15    (what 0a actually covers)
```

⚠️ **`CLAUDE.md:1281` says "13 registered jobs" and §10's heading says
"Scheduled (13 total)" over a table with 14 rows.** The heading disagrees with
the list beneath it — a count travelling separately from its list, which is the
same defect found at `:728` and fixed in `8cd23fb3`.

The dispatch was right to say *count them*. Every figure in circulation is a
count of a different thing.

### How the 28 scheduled jobs report

```
wrapper         15   through _run_per_tenant / _run_global   ← 0a covers these
hand-rolled      3   call _log_job_run / _complete_job_run directly
no job_runs      4   no logging of any kind
defined elsewhere 6  calendar ×2, email ×3, plus one dynamic `func`
```

**Hand-rolled (3):** `job_dispatch_auto_finalize`,
`job_platform_health_recalculate`, `job_platform_incident_dispatcher`. They open
their own `_log_job_run`, run, and complete it themselves. **0a's fix does not
reach them** — there is no wrapper to read a returned error.

⚠️ `DISPATCH_AUTO_FINALIZE` holds **10,268 `job_runs` rows**, the largest volume
of any job type on production. The highest-traffic scheduled job in the platform
is on the path 0a did not touch.

**No `job_runs` at all (4):** `_run_moc_event_matcher`, `_run_moc_schedule_sweep`,
`_run_workflow_time_check`, `job_onboarding_pattern`.

**Defined elsewhere (6):** the calendar and email sweeps live in
`services/calendar/sweeps.py` and `services/email/sweeps.py`. Grepped for
`_log_job_run` and `JobRun` in both files: **zero references.** They write no
`job_runs` row either.

### ⚠️ So ten of twenty-eight scheduled jobs leave no record at all

Not a false green — **no row**. For those, "did this run last night?" has no
answer from any durable store, which is the condition the `job_runs` work was
supposed to end. The 11-of-25 swallow enumeration in `c57ec672` measured a real
thing and measured it over the wrong population: it asked which *wrapped* targets
swallow, and wrapped targets are 15 of 28.

---

## Why this blocks §0's actual question

The natural-unit survey presumes a set of jobs whose results a wrapper will
interpret. Before that survey means anything, someone has to decide whether (c)
is:

- **the wrapper path only** — 15 jobs, coherent, and leaves 13 scheduled jobs
  outside the substrate it claims to fix; or
- **every scheduled job** — 28, which means bringing 3 hand-rolled and 10
  unlogged jobs onto a common path first, and that is a different and larger
  build than a result-shape change; or
- **the wrapper path plus a ratchet** — fix 15, and add a check that no new
  `add_job` target bypasses the wrappers, so the remaining 13 are a bounded
  backlog rather than a growing one.

Reporting, not choosing. ⚠️ But the third is the shape this project has used
before, and it is the only one of the three that makes the current state stop
getting worse while the rest is decided.

**The per-job natural-unit survey is not done.** It was the dispatch's §0 and I
did not complete it, because its premise failed first and surveying the wrong 25
would have produced a table that looked like an answer.

---

## Method notes

- The three populations were counted by AST over `scheduler.py`, separately, and
  compared — not by grepping one and trusting it. The disagreement between them
  is the finding, and a single count would have hidden it.
- Classification of the 28 was by *what each function calls*, not by name.
  `job_dispatch_auto_finalize` and `job_briefing_sweep` are named alike and are
  on different paths.
- The calendar/email absence is from grepping the files those functions are
  defined in, after locating them by definition rather than assuming a path.
