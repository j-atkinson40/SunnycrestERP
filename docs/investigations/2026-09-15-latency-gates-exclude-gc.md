# The latency gates exclude generation-2 GC pauses

**2026-09-15.** Ruling executed: the gates EXCLUDE gen-2 collection pauses, they do not
tolerate them. This records what was measured to get there, what was ruled out and how,
and five things surfaced along the way that are not this item's to fix.

Nothing here is inherited from the dispatch. The ~450 ms, the 2.08 M, the "21", the "30"
and the affected-set claim were each re-derived; two of them came back different.

---

## 0. Scope, re-derived

| what | count | how |
|---|---|---|
| gate files named `*latency*` | **15** | filesystem enumeration |
| …same set by content | **15** | independent: files calling `statistics.quantiles` under `tests/` minus `test_arc_telemetry_percentile.py`, which tests the production helper rather than a gate |
| **timed regions rewritten** | **21** | `t0 = time.perf_counter()` sites, located from source structure, not by name |
| **gate invocations that now report an exclusion** | **31** | 30 endpoint gates + one pure-Python microbenchmark (`confidence.to_tier`) |
| distinct p99 budget constants | **21** | unchanged — this item does not touch budgets |

The preliminary's "30 gate invocations" is confirmed. The 31st is `to_tier`, which asserts
a per-call time budget without a p99 and so fell outside the preliminary's metric-based
scope. It is affected by the same pause and is treated the same way.

---

## 1. ⚠️ The central claim, verified — and one clause of it is too strong

The ruling rests on: *a gen-2 collection costs ~450 ms regardless of how much garbage
exists, because the work is proportional to the permanent heap.* Two axes, varied
independently, `probe_gc_cost.py`, Python 3.13.7, thresholds `(2000, 10, 10)`.

**Axis 2 — garbage volume, heap held fixed.** The clause holds, and holds hard:

| cyclic garbage created | objects freed | pause |
|---|---|---|
| 0 | 0 | **456.1 ms** |
| 1,000 | 2,000 | 460.6 ms |
| 10,000 | 20,000 | 457.0 ms |
| 100,000 | 200,000 | 468.3 ms |
| 500,000 | **1,000,000** | **514.2 ms** |

A million objects of garbage adds **12.7 %**. The `freed` column is the axis's positive
control: it moves 0 → 1,000,000, so the axis genuinely varied. Three consecutive forced
collections on the idle heap: 464.4, 451.8, 465.7 ms — a collection immediately after
another is not cheaper, which is the same finding from the other direction.

**Axis 1 — permanent heap, zero garbage.** The direction holds. The proportionality does
not, and that matters for how the claim should be repeated:

| heap | tracked objects | pause |
|---|---|---|
| bare interpreter | 6,675 | 0.3 ms |
| + 1.0 M tracked objects | 1,006,680 | 35.4 ms |
| + 2.0 M tracked objects | 2,006,681 | **70.4 ms** |
| after `import app.main` | **2,082,597** | **464.4 ms** |

⚠️ **2.0 M synthetic objects cost 70 ms; 2.08 M application objects cost 464 ms — 6.6×
for the same object count.** The cost is not proportional to the number of tracked
objects. It is proportional to the number of REFERENCES traversed, and the application's
objects are far denser in references than a two-attribute test object. "Proportional to
2.08 M permanent tracked objects" is directionally right and quantitatively wrong; the
honest form is *proportional to the permanent heap it must walk, which this application's
2.08 M objects make expensive.*

**⚠️ A probe defect, recorded because it is this repo's recurring shape.** v1 of the probe
built the permanent heap from dicts holding only ints, strings and tuples. CPython
UNTRACKS an all-atomic dict, so one million of them moved the tracked count from 6,666 to
6,671 and the axis never varied. It was caught by printing the heap size next to the
pause instead of assuming the allocation had worked — the same control the arc's first GC
benchmark lacked when it measured zero gen-0 collections on refcount-freed dicts.

---

## 2. ⚠️ Which gates are affected — and the answer is not a list of endpoints

Two methods, sharing no code.

**Method A, before any change.** A pytest plugin hooking `gc.callbacks` and recording
every gen-2 collection in the session with the phase it landed in (`setup` / `call` /
`teardown` / between tests). Its positive control (`control_test_gc.py`) forces one
collection in one test and none in the other; the instrument reported exactly that.

**Method B, after the change.** Each gate's own per-sample accounting, printed every run.

### Run each file ALONE — reproducible to the test, both passes

Every file shows **8 or 9 gen-2 collections during the first test's SETUP phase**, pauses
climbing 21 → 66 → 128 → 163 → 196 → 233 → 262 → 282 ms as `import app.main` and the
fixtures build the heap. Then **6 of the 15 files show exactly one further collection
inside a CALL phase**, at 357–403 ms, in the same test on both passes:

| file | gate that wore it | pause |
|---|---|---|
| `test_briefing_generation_latency` | `briefing_generate` | 362 / 386 ms |
| `test_cash_receipts_triage_latency` | `next_item` | 381 / 374 ms |
| `test_phase8c_triage_latency` | `month_end_close apply_action` | 403 / 366 ms |
| `test_safety_program_triage_latency` | `apply_action` | 370 / 357 ms |
| `test_saved_view_execute_latency` | `execute` | 357 / 372 ms |
| `test_workflow_scope_latency_phase8a` | `scope=core` | 398 / 367 ms |

The other **9 files show none**. The two the preliminary named from an entirely separate
investigation — cash-receipts `next_item` and month-end-close `apply_action` — are both in
this list, reproduced without being sought.

### Run all 15 TOGETHER — zero

**0 call-phase collections across all 30 endpoint gates, both passes.** The collections
still happen (13 per session); they land in the first file's setup and are done.

⚠️ That zero is a real zero, not a dead instrument, and the proof is accidental: the
harness's own control tests force collections, and the plugin recorded all four of them in
the same run. The instrument was demonstrably alive while reporting zero for the gates.

### ⚠️ What that means, stated carefully

**The affected set is not a property of the endpoints. It is a property of where the
process is in its allocation history when the gate happens to run.**

- Same gate, same machine, same commit: affected run alone, unaffected run together.
- The six affected gates span six unrelated endpoints and four unrelated services. No
  shared cause among them beyond "ran at the wrong moment."
- The set is unstable between runs of the SAME file: after the harness landed —
  changing the allocation history by a few thousand objects — `briefing_generate` and
  `saved_view_execute` stopped being hit and the other four still were.

**This was checked specifically because a narrower affected set would have been the better
finding and would have changed the item.** It is not narrower. Exposure is universal and
uniform; observation is sparse, arbitrary and unstable. A gate that has not been hit has
not been hit YET, which is the dispatch's own reading and is what the measurement supports.

⚠️ **And test-side frequency says nothing about production frequency.** A pytest process
lives for seconds and spends most of them growing its heap; production lives for hours on
a stable 2.08 M. The rate question is the one `arc_telemetry._gc_snapshot` exists to
answer on production, and nothing here substitutes for it.

---

## 3. The mechanism, chosen by measurement

**Measure each sample; subtract the collector's own interval from the sample it landed in.**
`tests/_gc_latency.Gen2Excluded`. Nothing is disabled, frozen or tuned.

### Why subtraction, and not "discard the affected sample"

Subtraction claims the pause is purely additive — the endpoint's own work plus an
interruption. That is a prediction, so it was tested rather than assumed: **the corrected
sample must land back inside the distribution of the uninterrupted samples.** Four
independent confirmations on real gates:

| gate | raw max | corrected | that run's p50 / min |
|---|---|---|---|
| cash-receipts `next_item` | 391.2 ms | **23.9 ms** | 20.3 / 19.3 ms |
| month-end-close `apply_action` | 399.5 ms | **12.7 ms** | 10.1 / 9.1 ms |
| safety-program `apply_action` | 401.4 ms | **8.5 ms** | 7.6 / 6.4 ms |
| workflow-scope `core` | 471.7 ms | **102.8 ms** | 93.8 / 92.1 ms |

Every corrected value lands inside its own gate's clean range. Discarding was kept as the
fallback and is not needed; it also silently shrinks the denominator, which is the defect
this repo has a standing rule about.

### Ruled out, by what they would have done rather than by taste

| candidate | why not |
|---|---|
| `gc.disable()` around the sampled region | The endpoint would execute under a runtime state that never ships, and the allocation signal would vanish along with the pause. |
| `gc.freeze()` at session start | Same objection, and worse: freezing is the candidate PRODUCTION fix. A gate that pre-applies it reports the fix as already landed. |
| discard samples containing a collection | Shrinks n invisibly. Unnecessary — subtraction was validated. |

### The end-to-end demonstration

Measured ~09:35, before the day's later runs had added more rows (see §5b — the row
count moves, so these two readings are a matched pair taken minutes apart, not a
standing claim about the gate's pass state).

`test_workflow_scope_latency_phase8a` run alone, **before**: 2 failed, 3 passed.
`workflow-scope-core` reported `p50=64.2ms … max=466.3ms`, p99 **782.2 ms** against a
300 ms budget. The plugin recorded one call-phase collection in that test at **397.8 ms**.

Run alone, **after**: 1 failed, 4 passed. `workflow-scope-core` reports
`p99=103.4ms … [gc: EXCLUDED 372.6ms across 1 gen-2 collection(s) in-sample
(raw max 471.7ms → 102.8ms)]` and passes.

⚠️ **The surviving failure is the point.** `workflow-scope-core-used-by` still fails, on
p50, with `0 gen-2 collections in-sample`. The exclusion removed a failure caused by the
runtime and left the other one exactly where it was — which is requirement three
demonstrated on a real gate rather than argued. (§5b establishes what that surviving
failure actually is, and it is not the endpoint either.)

---

## 4. The four requirements, against what was built

**It must not change what the endpoint does.** Nothing is disabled, frozen or tuned; the
only interaction with the collector is appending an observer to `gc.callbacks` and
removing it on exit. Guarded by `test_the_runtime_is_UNCHANGED_during_and_after_sampling`
(thresholds, `isenabled()`, `get_freeze_count()` — checked during AND after) and
`test_the_hook_is_REMOVED_on_exit`. Break C — inserting `gc.freeze()` into the harness —
turns the first of those red and nothing else.

**It must be visible.** Every gate prints its exclusion on **every run, including when
nothing was excluded** — `gc: 0 gen-2 collections in-sample (3 gen-0), nothing excluded`.
A note that appeared only when something happened would make the common case read as an
ordinary unqualified measurement, which is the thing this is trying not to be. The note is
embedded in the `diag` string that the assertion messages carry, so it appears in the
failure text as well as the captured stdout. Each of the 15 module docstrings states what
the file excludes and points here.

**It must not hide a real regression.** Two facts are recorded and the distinction is the
whole design:

    gen-2 pause        THE RUNTIME COLLECTED.            Excluded from the latency.
    gen-0 collections  THIS ENDPOINT MADE IT COLLECT.    Asserted, per gate.

gen-0 fires every 2,000 net container allocations, so its count over a sample loop is a
direct proxy for what the endpoint allocates — and allocation is what promotes objects
into the generation whose collection is being excluded. ⚠️ The gen-2 count could NOT have
done this job, and that was measured: in-sample gen-2 counts are 0 or 1 everywhere and are
dominated by process phase. gen-0 counts were **identical across separate processes** for
almost every gate (spread ≤ 1 over 3–4 runs), which is what lets a ceiling mean something.
Ceilings are measured × 3, per gate, because allocation per request spans two orders of
magnitude across these endpoints — 1 gen-0 collection for `catalog-fetch next_item`, 138
for `saved-view execute`. A shared number would assert nothing on most of them.

**It applies to all the affected gates.** All 21 timed regions, all 31 gate invocations,
all 15 files.

---

## 5. Five things surfaced, none of them this item's to fix

**(a) ⚠️ 13 of the 15 files call themselves "BLOCKING CI gate" and CI does not run them.**
`tests/ci_gate.txt` contains `test_command_bar_latency.py` and
`test_command_bar_portal_latency.py` and no other latency file. Established twice: an
exact-basename membership test per file, and a case-insensitive grep of the manifest for
"latency", which returns those two lines and nothing else. The docstrings are not lying
about intent, but "BLOCKING CI gate" is not true of thirteen of them today.

### (b) ⚠️ THE `workflow-scope` STOP IS A TEST-LITTER DEFECT, NOT AN ENDPOINT ONE

This is the biggest thing this item turned up and it re-scopes two of the preliminary's
four STOPs.

`test_workflow_fork_latency` creates `_SAMPLE_COUNT + _WARMUP_COUNT` = **23 global
`scope="core"` workflows per run**, each with 3 steps, with `company_id=None`, and
**never deletes any of them.** There is no teardown in the file: no `yield` fixture, no
delete, no purge call. ⚠️ Its own docstring says *"we delete the fork after
measurement"* — describing cleanup the code has never performed, which is the DotNav
shape from CLAUDE.md (a comment stating an intent the code never implemented).

`test_workflow_scope_core_latency` — a different test in the same file — then measures
`GET /api/v1/workflows?scope=core`, and the test's own comment notes that each row fires
an aggregate. **So one gate makes another gate in the same file permanently slower every
time the file runs.**

Measured directly, same database, three consecutive runs:

| | `scope='core'` rows | `companies` | `workflow-scope-core` p50 |
|---|---|---|---|
| before | 581 | 2,094 | 117.2 ms |
| after 1 run | **604** (+23) | 2,096 | 121.8 ms |
| after 2 runs | **627** (+23) | 2,098 | — |

Composition of the table at the time of writing:

| `scope='core'` rows | count |
|---|---|
| `name LIKE 'ForkSrc-%'` — litter from this one test | **621** |
| `id LIKE 'wf_sys_%'` — the real platform workflows | **16** |
| remainder | 36 |
| **total** | **673** |
| orphaned `workflow_steps` on the ForkSrc rows | **3,243** |

**The endpoint is being gated against a table 42× larger than its real population, and
the gate's own file is what inflated it.** `app/data/default_workflows.TIER_1_WORKFLOWS`
declares 17 and 16 are present — a one-row discrepancy noted, not chased.

⚠️ **And 23 of the known 34-row `global_workflows` leak now have a named producer.**
`tests/conftest.py` carries `_LEAK_CEILING = {"global_workflows": 34}`, documented as
"measured at exactly +34 on four separate full-tree runs", with the standing note that
closing it needs fixture teardown. 23 of those 34 are these `ForkSrc-*` rows. The ceiling
is calibrated just above the leak, so the tripwire has never fired on it.

### (c) ⚠️ NOT A NEW FINDING — A RE-OCCURRENCE, ONE DAY LATER

STATE already carries this, and getting the lineage right matters more than the
measurement. The 2026-09-14 entry is headed **"STOCK CLEARED, FLOW UNCHANGED"**: the
purge took `scope=core` from 1,720 to 6 rows and the two workflow-scope gates from
p50 249.4 ms / 439.3 ms to **5.3 ms / 5.8 ms**, and the entry says plainly that the
defect "was never the loop; it was 1,714 fixture rows being iterated" and that the flow
would "need repeating until the fixtures gain teardown".

**One day later the count is back to 673 and both gates fail again.** So the purge
explanation was right, was recorded, and has already expired — which is what
"stock cleared, flow unchanged" predicted.

What is new here is the producer and its rate:

- STATE measured the aggregate flow at **+34 global workflows per run** across four
  full-tree runs and left the producer unnamed.
- **23 of those 34 are `test_workflow_fork_latency`**, measured directly rather than
  inferred: 23 `ForkSrc-*` rows appear per run of that file, and 621 of the 673 current
  `scope='core'` rows carry that name.

And the preliminary's figures should be read accordingly: its **261.9 ms / 466.4 ms** were
a row-count reading taken at one moment, not a property of the endpoint. A budget derived
from them would be measuring test hygiene.

**(d) These two failures are not caused by this change, and that was checked rather than
argued.** The HEAD version of the file was restored over the working copy and run against
the SAME database state: both tests fail at HEAD too, `core` at `p50=118.4ms` and
`core+used_by` at `p50=205.7ms`. The working copy then went back. They passed in this
session's full-tree baseline because that baseline ran before the day's measurement runs
had added their rows — a state difference, not a code difference.

⚠️ And a plain admission: this session's own measurement runs of that file are a
substantial share of the 621. The gate's fixture is the producer; running it ~20 times to
measure GC is what fed it today.

⚠️ **One of STATE's open observations is now explained.** The 2026-09-14 entry records
`test_workflow_fork_latency` reporting `p99 = 731.2ms against 500` while "its own max is
412.2ms", and files it as the p99 extrapolation defect. Half of that is right and half is
this item: the 412.2 ms MAX was a gen-2 collection. Post-change the gate reports
`p50=6.7ms p99=8.4ms` with the pause excluded, and the extrapolation has nothing extreme
left to extrapolate from.

**(e) The p99 extrapolation defect repaired in production is still live in the tests.**
The HEAD run above reported **p99 = 746.9 ms from 20 samples whose maximum was
495.3 ms** — `statistics.quantiles(n=100)` projecting past the data, exactly the shape
fixed in `arc_telemetry` on 2026-09-14. Deliberately untouched here: raising n and
re-deriving budgets is the next item, and changing the percentile method in the same
commit as the exclusion would confound both.

⚠️ **One known property of the allocation ceilings, stated so it is not a surprise.**
`workflow-scope-core`'s gen-0 count rises with the row count — 36 at 581 rows, 55 at 627.
The ceiling (120) will eventually be crossed by litter accumulation rather than by a code
regression. That is the ceiling working: the endpoint genuinely is allocating more,
because it genuinely is processing more rows. It will read as an allocation regression,
and per (b) it will be one — just not one anybody wrote.

## 6. Controls

`tests/test_gc_latency_harness.py`, 9 controls. Three breaks, each with its own marker
count confirming the break applied, each turning the intended test red and not merely
something:

| break | marker count | went red |
|---|---|---|
| A — `endpoint_ms` returns `raw_ms` (subtraction removed) | 1 | `test_the_pause_is_SUBTRACTED_not_merely_counted`, `…LANDS_IN_THE_DISTRIBUTION…` (2 of 9) |
| B — callback returns before attributing anything | 1 | those two plus `test_a_REAL_collection_inside_a_sample_IS_ATTRIBUTED_to_it` (3 of 9) |
| C — `gc.freeze()` inside the harness | 1 | `test_the_runtime_is_UNCHANGED_during_and_after_sampling` (1 of 9) |

All three restored; `grep -c BREAK_ tests/_gc_latency.py` → 0.

⚠️ One control is worth naming separately.
`test_NOTHING_UNDER_APP_TOUCHES_THE_COLLECTOR_except_the_observer` walks the AST of every
file under `app/` and fails if application code calls `gc.collect`, `disable`, `enable`,
`freeze`, `unfreeze`, `set_threshold` or `set_debug`. It is the exclusion's load-bearing
precondition: subtracting a gen-2 pause is only honest while no application code CAUSES
one. If an endpoint ever calls `gc.collect()` itself, that cost is the endpoint's own and
the gates must stop excluding it. It is AST-based rather than a source search because a
grep for `gc.collect` finds its own docstring — the defect this file hit twice already.
