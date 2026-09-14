# Latency gates: classification and budget preliminary

**2026-09-14. Read-only. No gate changed.** Deliverable for review per the dispatch's
"the classification and budget table first."

---

## 0. The scope figures, re-derived. Four counts, and the dispatch used one.

| what | count | how derived |
|---|---|---|
| files calling `quantiles(n=100)` | **16** | grep, all forms |
| …of which are test files | **15** | the 16th is `app/services/arc_telemetry.py` — **production** |
| test files named `*latency*` | **15** | independent enumeration by name; same set |
| **gate invocations** | **30** | test functions reaching a p99 assert, directly or via a shared helper |
| **distinct p99 budget constants** | **21** | module-level `TARGET_*_P99_MS` |

The dispatch says "15 blocking gates" and "Fifteen budgets." **Fifteen is the FILE
count.** Half the gates hide behind shared helpers (`_run_next_item_gate`,
`_assert_budget`) called by several test functions each — `test_phase8c_triage_latency`
alone holds 6, `test_workflow_scope_latency_phase8a` holds 5. Item 1's workload is 21
budgets, not 15.

⚠️ A third enumeration by *content* (any test mentioning p50/p95/p99/latency) returned
**40** files. The extra 25 were checked: none asserts a timing budget — they assert that
a latency field was recorded. So no gate hides outside the metric-based scope. The check
mattered because the scope was constructed from the metric, not from the gates.

---

## ⚠️ 0a. The same defect is in PRODUCTION code, not just tests

`app/services/arc_telemetry.py::_percentile` is the 16th file and it is not a test. It
serves the admin telemetry surface via `/api/platform/admin/arc-telemetry`, fed by
`command_bar.py`, `triage.py`, `nl_creation.py`, `saved_views.py`.

It calls `statistics.quantiles(samples, n=100)` on a rolling buffer capped at 1000 —
**which fills from empty on every deploy.** Measured, one slow request among fast ones:

| samples in buffer | observed max | p99 reported | inflation |
|---|---|---|---|
| 2 | 450ms | 867ms | **+93%** |
| 10 | 450ms | 833ms | +85% |
| 30 | 450ms | 747ms | +66% |
| 50 | 450ms | 661ms | +47% |
| 99 | 450ms | 450ms | ok |
| 1000 | 450ms | 20ms | ok |

So an operator reading the telemetry dashboard sees an inflated p99 for any endpoint with
fewer than 99 samples buffered — **every endpoint after every deploy, and permanently for
low-traffic endpoints.** This is a live surface, not a test.

**p50 verified sound at every n** (matches the true median exactly, n=2…1000). The
dispatch's claim is confirmed by measurement, not inherited.

---

## 1. Classification — 29 TAIL, 1 TYPICAL, and that is not the useful cut

Every gate except one exercises an endpoint a person is waiting on: command bar (Cmd+K
while typing), peek (hover preview), triage next-item/apply-action across six queue
families (a user clicking through a workspace), saved-view execute and preview (live
preview while editing filters), quote preview, NL creation (300ms-debounced while typing),
AI question (user asks and waits), workflow scope/fork and spaces (admin page loads).

**TYPICAL — `briefing-generate`.** `POST /api/v1/briefings/v2/generate` has **no frontend
caller** (enumerated across four name forms). Its production path is the 15-minute sweep.
Nobody waits.

⚠️ **And the gate is on the wrong endpoint.** The interactive sibling
`POST /briefings/briefing/refresh` — which `morning-briefing-card.tsx:882` and
`morning-briefing-mobile.tsx:313` call when a user clicks refresh — **has no gate at
all.** The batch path is guarded; the path a person waits on is not.

The TAIL/TYPICAL split turns out not to be the decision that matters. The one below is.

---

## 2. ⚠️ 17 of 30 gates CANNOT FIRE

Budgets were not derived. Two round pairs — 100/300 and 200/500 — are applied almost
uniformly regardless of what the endpoint does. Against measured behaviour:

| gate | p50 | budget | headroom | max | budget | headroom |
|---|---|---|---|---|---|---|
| ai-question | 3.9ms | 1500ms | **429×** | 5.0ms | 3000ms | **667×** |
| nl-creation | 5.1ms | 600ms | 122× | 6.9ms | 1200ms | 214× |
| briefing-generate | 20.8ms | 2000ms | 103× | 21.6ms | 5000ms | 239× |
| spaces-with-system | 2.4ms | 100ms | 43× | 2.9ms | 300ms | 103× |
| catalog-fetch next_item | 2.9ms | 100ms | 34× | 3.4ms | 300ms | 97× |
| …12 more at ≥20× on both | | | | | | |

**17 of 30 have ≥20× headroom on both statistics.** They pass everything. Two more fail
on p50 (below). So the suite as it stands is wrong in both directions *before* any
renaming — which is the failure mode the dispatch names for the repair, already present in
the thing being repaired.

⚠️ **`ai-question` and `nl-creation` are worse than over-budgeted: their measurement
excludes the dominant cost.** `ai-question` monkey-patches Intelligence ("we measure
orchestration, not the model"); `nl-creation` empties `ANTHROPIC_API_KEY` to force the
no-AI path. Their budgets (1500/3000 and 600/1200) were set for the *real* call. The gate
measures one thing and the budget describes another. **Classification genuinely ambiguous
— STOP.**

---

## 3. What n=100 costs

Derived from measured per-sample cost, not estimated.

| | sampling time |
|---|---|
| current (n = 10…50) | **20.9s** |
| at n=100 everywhere | **94.6s** |
| delta | **+73.6s** |

Measured wall clock for all 15 files as they stand: **184.4s**. Sampling is only **11%**
of that; the rest is fixtures and imports. So n=100 everywhere is **+40%** on the latency
suite.

⚠️ **75% of that increase is two gates** — `workflow-scope core` (+20.0s) and
`core+used_by` (+35.1s) — **which are the two already failing on p50.** Exclude them and
n=100 costs **+18.5s**, which the suite absorbs without comment.

**So the cost question answers itself:** raising n is cheap everywhere except the gates
that need a performance fix rather than more samples.

---

## 4. Proposed budgets — headroom DERIVED, not picked

Three full passes over all 15 files (90 gate runs). Run-to-run spread:

- p50: median **1.05×**, worst **1.22×**
- max: median **1.08×**, worst **1.43×**

Intra-day drift, measured: `cash-receipts` max was **445.8ms** this morning and
**374.3ms** now — **1.19×**.

**1.43 × 1.19 = 1.70× of pure noise.** A **3× headroom** leaves ~1.76× for a genuine
regression before firing. Every factor is measured; none is chosen for roundness.

Proposed budget = worst observed across three passes × 3, rounded up to the next of
{10, 25, 50, 100, 250, 500, 1000, 2500}.

Full table: `docs/investigations/2026-09-14-latency-budget-table.txt`.

---

## 5. ⚠️ FOUR STOPS

**(a) `workflow-scope core` — fails p50 at 261.9ms against a 100ms budget (2.6×).**
**(b) `workflow-scope core+used_by` — fails p50 at 466.4ms against 100ms (4.7×).**

p50 is the sound statistic. These are not measurement artifacts — they are a genuine
performance problem, pre-existing and present in the last full-tree baseline. The endpoint
is `GET /api/v1/workflows?scope=core[&include_used_by=true]`, and the test's own comment
says "each row fires an aggregate." **A latency finding, not a naming decision.**

**(c) `cash-receipts next_item` — honest tail budget would be 2500ms against a current 300ms.**
**(d) `month-end-close apply_action` — 2500ms against a current 500ms.**

Both carry a ~365ms spike on endpoints whose p50 is 8–19ms. An honest statistic cannot be
budgeted at 300ms while that spike exists. See §6 — the spike is not a tail.

---

## 6. §2 of the dispatch — what is known about the "tail", without investigating it

**It is not a tail. It is deterministic.**

Instrumented (temporarily, reverted) to record each sample's position:

```
run 1  argmax_index=18 of 30   seq= 20 20 19 20 19 ... 19 20 20 19 [401] 22 20 19 ...
run 2  argmax_index=18 of 30   seq= 20 20 19 21 19 ... 19 18 18 18 [373] 20 19 19 ...
run 3  argmax_index=18 of 30   seq= 20 20 19 20 20 ... 19 20 19 19 [393] 20 19 18 ...
```

**Index 18, all three runs.** 29 samples at ~19ms and exactly one at ~390ms, always in the
same position. All responses HTTP 200 — it is **not** the queue-exhaustion path (40
anomalies seeded, 33 consumed). A warm-up loop of 3 precedes sampling, so it is not a
naive cold start.

The same shape appears in `month-end-close apply_action` (max ~365ms on an 8.8ms p50), a
different queue in a different file — suggesting a shared cause in the triage path rather
than anything endpoint-specific.

⚠️ **A single deterministic 20× spike is not something a p99 should be asked to describe
in either direction.** Reporting it inflates the number; suppressing it hides a real
event. Not investigated further per the dispatch's scope line. Recorded for its own
session.

---

## 7. Two standing properties worth a ruling

**Every one of the 15 files has an environment-variable off switch** — 10 distinct vars
(`TRIAGE_LATENCY_DISABLE` covers 4 files). **None is set anywhere in the repo, and none is
set in this session**, so all gates are live. But CLAUDE.md's precedent is explicit —
"THE FIX IS NEVER TO SET THAT FLAG IN CI" — and if raising n is judged expensive, these
switches are the obvious wrong exit.

**`grep -c` counts lines, not occurrences; `AnnAssign` is not `Assign`.** Both traps from
the dispatch were live here: the sample-count constants are `_SAMPLE_COUNT: int = 30`
(annotated), which an `ast.Assign` walk misses entirely, and a first pass over this
population reported **"0 files below 100"** — the exact opposite of the truth — before a
fifth method returned the data.

---

## Recommendation, for the ruling

1. **Fix `workflow-scope` before touching its gate.** 2.6× and 4.7× over budget on p50.
2. **Rule on `ai-question` / `nl-creation`:** is the gate guarding orchestration (budget
   ~25ms) or end-to-end (then it must stop stubbing the model)?
3. **Rule on `briefing-generate`:** move the gate to `/briefing/refresh`, or gate both.
4. **Then** raise n to 100 on the remaining 26 gates (+18.5s) and re-derive their budgets
   from the table.
5. **Separately:** `arc_telemetry._percentile` is production and inflates by up to +93%.
