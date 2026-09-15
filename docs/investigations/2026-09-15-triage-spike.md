# The ~365ms triage spike: it is generation-2 garbage collection

**2026-09-15. Read-only investigation, no fix.** Two STOP lines fire; both are at the end.

---

## 0. Re-measurement — the item still exists, and one prior claim was wrong

All earlier observations predate the litter purge and the FK work. Re-measured
**2026-09-15 ~11:37 UTC** against the cleaned database (6 core workflows, 0 orphans):

| run | argmax | max | samples over 100ms |
|---|---|---|---|
| 1 | 16 | 400ms | 1 |
| 2 | 18 | 367ms | 1 |
| 3 | 18 | 365ms | 1 |

**It survived**, which makes it a stronger finding than before: it is unaffected by a
material change to the data.

⚠️ **But "index 18, three runs" was a coincidence of three samples.** The position varies —
16, 18, 18 here — and the preliminary's fixed-index claim overstated it.

---

## 1. Position, not tail: it tracks allocation, not time and not the endpoint

Varied deliberately, as the dispatch required.

| variation | argmax | total call index | reads as |
|---|---|---|---|
| warm=3, no sleep | 16–18 | ~20–22 | baseline |
| warm=3, **+5s sleep** | 18, 18 | ~22 | **unmoved by 5 seconds** |
| **warm=20**, no sleep | 1, 1 | ~22 | moved by exactly the extra calls |

Five seconds of elapsed time moved nothing; seventeen extra calls moved it seventeen
places. **Not time-based** — so no scheduled task, no time-based cache expiry.

**And it is one-time, not periodic.** At 60 samples: one spike. At 120 samples: one spike.
So: no recurring page boundary, no cache refilling every N, no pool cycle.

### Where the time goes — measured, not inferred

Instrumented per-call SQL statement count and SQL time:

```
call#0 : total=21ms   stmts=86  sql_ms=9  NON_SQL=12ms
call#16: total=400ms  stmts=86  sql_ms=9  NON_SQL=390ms   <-- the spike
call#29: total=19ms   stmts=86  sql_ms=8  NON_SQL=11ms
```

**The same 86 statements. The same 9ms of SQL.** The entire 390ms is outside the database.
Not an N+1, not a slow query, not the endpoint at all.

### The cause, established by removal and then timed directly

```
GC enabled : spike present (395ms), gen-2 collections during sampling = 1
GC disabled: max 21ms and 26ms, spikes = 0, collections = 0      (two runs)
```

Then timed at the source via `gc.callbacks`:

> **`PROBE gc pauses >50ms: [(2, 380)]`** — one generation-2 collection, **380 ms**,
> landing in a call that measured 391ms of non-SQL time.

⚠️ Everything the variation showed follows from this and from nothing else: allocation-
counted (not time), one-time in a short window (gen-2 is rare), pure Python, and
endpoint-independent.

---

## 2. The cross-file claim, verified rather than inherited

`month-end-close apply_action` — different queue, different file, different fixture:

```
GC on : p50=8.7ms  max=355.3ms
GC off: p50=7.6ms  max=9.1ms      <-- spike gone
```

With GC disabled, **all six gates in that file pass.** And only ever ONE of the six spikes
per run — exactly what a single gen-2 collection landing in whichever call is in flight
produces.

The constraint the preliminary drew from the cross-file appearance was right, and is now
explained: it is not a property of one queue's data. It is not a property of the triage
path either. **It is the runtime.**

---

## ⚠️ 3. STOP — IT IS IN A SHARED DEPENDENCY

The dispatch's second STOP: *any finding that the spike is in a shared dependency rather
than the triage path.* It is in the Python runtime, which is as shared as it gets. Every
endpoint is equally exposed; triage is simply where a gate happened to be watching.

## ⚠️ 4. STOP — AND IT IS NOT ONLY A TEST ARTIFACT

The dispatch anticipated that an operator does not make 22 calls in a tight loop, so the
answer might be no. The measurement says it is more complicated than that.

```
tracked objects after importing app.main alone : 2,082,954
adding one test module                         : +9,011  (0.4%)
gc thresholds                                  : (2000, 10, 10)  — Python defaults
files under app/ that reference gc             : 0
```

**The heap is the application's, not the test suite's**, and production runs the same
default thresholds with no tuning anywhere. A generation-2 collection walks that heap
wherever it runs, and it costs what it costs.

So the honest statement has two halves:

- **The POSITION is a test artifact.** 21 allocation-heavy calls inside 400ms is a rate no
  operator produces. Nothing about "the 21st triage call" transfers.
- **The PAUSE is not.** A ~380ms gen-2 collection over a 2M-object heap is a property of
  the deployed application, and it lands on whichever request is in flight. At production
  traffic the frequency is different; the cost per occurrence is the same.

⚠️ **NOT MEASURED: whether production actually exhibits this, or at what frequency.** That
needs instrumentation on the running service and was out of scope. The inference rests on
heap size and default thresholds being identical — which was measured — not on any
production observation. Do not quote a production pause figure from this document; there
isn't one.

This is why it is a STOP rather than a gate-hygiene note: if it holds, it is a
service-wide latency characteristic invisible to per-endpoint budgeting, and the question
is GC posture for the whole service, not a number for one gate.

---

## What this means for the 21 budgets, stated but not decided

Every p99 in the suite is computed from ≤50 samples in a window where exactly one gen-2
collection may land. When it lands, that single sample is ~20× the median and — because
`quantiles(n=100)` extrapolates below 99 samples — it is then inflated further.

`month-end-close apply_action` is the worked example: **p50 8.7ms, max 355ms, reported p99
593ms**. Two independent defects stacked on one gate, neither of them about the endpoint.

No fix here, per scope. Recorded for the budget dispatch.
