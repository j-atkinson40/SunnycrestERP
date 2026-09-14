# workflow-scope latency: cause established, and two STOPs

**2026-09-14. Read-only. Nothing changed.** The dispatch's preliminary, reporting before
any fix.

---

## 1. The cause IS per-row queries. The comment is right — and incomplete.

Two-point measurement through the same loop, `scope=core` (1,608 rows) against
`scope=vertical` (91 rows), counting SQL statements per request:

| path | rows | total SQL | step-count | used_by | fixed |
|---|---|---|---|---|---|
| `scope=core` | 1,608 | 1,612 | 1,608 | 0 | 4 |
| `scope=vertical` | 91 | 95 | 91 | 0 | 4 |
| `scope=core&include_used_by=true` | 1,608 | 3,220 | 1,608 | 1,608 | 4 |
| `scope=tenant` | 0 | 4 | 0 | 0 | 4 |

**Slope = 1.00 queries per row. Intercept = 4.0.** A pure N+1, not a fixed cost and not
one slow query. The test's comment — *"each row fires an aggregate"* — is correct.

⚠️ **But it names the wrong aggregate, and that is why BOTH gates fail.** The comment sits
on the `include_used_by` test and attributes the per-row cost to that flag. The
`WorkflowStep` count at `workflows.py:271` is **unconditional** — it fires for every row on
every path, `include_used_by` or not. `used_by` is a *second* N+1 stacked on top, which is
why `core+used_by` is ~1.8× the plain `core`.

A fix aimed only at `include_used_by` would have left `scope=core` exactly as slow.

---

## 2. ⚠️ The magnitude is TEST LITTER, not production shape

`scope=core` returns **1,608 rows** on this database. CLAUDE.md describes core as "the 16
`wf_sys_*` workflows."

Six of the 1,608 are genuine platform workflows: AR Collections, Cash Receipts Matching,
Compliance Sync, Expense Categorization, Month-End Close, Monthly Statement Run. The rest
are test fixtures that were never cleaned up:

| fixture name | rows |
|---|---|
| `ForkSrc-0` … `ForkSrc-22` | 50 each |
| `CountTest` | 77 |
| `SrcForDouble` | 75 |
| `Chain test` | 75 |
| `Platform workflow` | 69 |
| `Ponder Fixture <hex>` | 1 per test run, ~150 distinct |

**Growth, by creation date:** +573 today · +196 on 09-11 · +306 on 09-10.

The gate's timing is therefore a function of how many times the suite has been run, and it
degrades monotonically. This is the `company_litter` class from CLAUDE.md — but there is no
tripwire for workflow rows, so nothing has been counting.

⚠️ **`is_system` does NOT separate production rows from litter.** My first attempt at the
split used it and reported 1,383 "real" rows. The fixtures set `is_system=True` as well —
visible the moment the names were printed. A constructed discriminator, believed for one
query.

---

## 3. A candidate fix, measured — but see §4 before acting on it

Batch the per-row counts into one `GROUP BY`:

```python
counts = dict(db.query(WorkflowStep.workflow_id, func.count(WorkflowStep.id))
                .filter(WorkflowStep.workflow_id.in_(ids))
                .group_by(WorkflowStep.workflow_id).all())
# .get(w.id, 0) — NOT counts[w.id]
```

**Result equivalence verified over all 1,608 rows: IDENTICAL.** ⚠️ 72 rows have zero steps,
so `.get(w.id, 0)` is load-bearing — a join or a bare lookup would drop or crash on them.
A query-count win that changed the result set would be a correctness regression.

| rows | current (N+1) | batched | speedup |
|---|---|---|---|
| 6 *(production shape)* | 0.8ms | 0.2ms | 4.4× |
| 16 | 2.2ms | 0.3ms | 8.1× |
| 200 | 28.3ms | 1.1ms | 24.8× |
| 1,608 *(this database)* | 230.9ms | 7.2ms | **32.3×** |

The endpoint measured 280.6ms end-to-end; removing 231ms of step counting would bring it to
roughly 56ms.

---

## 4. ⚠️ STOP — NEITHER GATED PATH HAS A PRODUCTION CALLER

Enumerated across seven name forms in the frontend and across the backend.

**Nothing in the application calls `GET /api/v1/workflows`.** The settings page that
CLAUDE.md describes as the consumer — the three-tab builder — fetches
`/workflows/library/all`, a different endpoint. The only `"/workflows"` call in the
frontend is a **POST** in `WorkflowBuilder.tsx:298`.

`include_used_by` is worse: it appears in the endpoint definition, in this latency test,
and in one unit test. **Nowhere else, in any language.** CLAUDE.md's claim that it serves
"the three-tab builder UI" is stale.

The only non-test consumers of `?scope=` are Playwright specs hitting `STAGING_BACKEND`,
which are not part of the local gate.

So the dispatch's conditional applies: *"If nothing calls the slower path, that changes the
fix from optimization to a question about why it is gated."* It applies to **both** paths,
not just the slower one.

**Options, none of which are mine to pick:**

- **Delete `include_used_by`.** It is a per-row aggregate, gated by a BLOCKING test, serving
  a "Used by N tenants" column that does not exist.
- **Delete both gates**, and the N+1 with them if the endpoint is genuinely dead.
- **Wire the builder to it**, if the adoption column is still wanted — then optimize, because
  it would finally have a reader.
- **Fix the N+1 anyway.** Defensible on its own terms: 8× at 16 rows, and `library/all`
  may carry the same shape. Not verified — out of scope.

---

## 5. ⚠️ STOP — SHARED CAUSE WITH THE OTHER GATES

The dispatch asks me to stop if these two share a cause with others in the 21. They do, at
the level of mechanism: **the test database grows within and across sessions.** STATE
already records this as the environmental half of the p99 problem
(`cash-receipts` max 445.8ms in the morning against 374.3ms the same afternoon).

Here it is not a contributing factor — it is the dominant term. 1,602 of 1,608 rows.

**Deriving 21 budgets against this database would encode the litter into the budgets.** A
budget derived at 1,608 core rows is wrong at 6, wrong at 2,200 next week, and wrong in
production. That is a sequencing consequence for the budget item, not a finding about these
two gates.

---

## What I did not do

No fix. No budget change. No litter cleanup — deleting ~1,602 rows from a shared
development database is a destructive act on state I did not create, and the litter deserves
its own item with a tripwire rather than a one-off purge.
