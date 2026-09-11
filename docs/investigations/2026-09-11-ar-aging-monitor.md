# `ar_aging_monitor` — what it does when it fails, and what it never fed

**Date:** 2026-09-11 · **HEAD:** `c8d6f051` · **Read-only. No fix applied.**

Nothing is inherited from the dispatch — not the 157, not the 3-of-4, not the
one-message claim, not the date/datetime diagnosis. Every figure re-measured
against production through a connection-level read-only guard, one statement per
connection.

---

## 0. Headline

**Q3's premise is wrong, and that is the good news.** The collections findings
the note surface renders do **not** derive from `ar_aging_monitor`. They are
written by `ar_collections_agent`, which computes aging **correctly** from
`Invoice` directly and reads nothing this job produces. **No collections finding
on production was computed from a partial or stale aging result.** The STOP does
not fire.

**Q2's answer is that it produces nothing, and never has.** Zero `ar_aging_*`
alerts have ever been written. Zero collection sequences exist. The failure
occurs on the first invoice of the loop, before any write.

**The real finding is Q4.** The `agent_jobs` table records 163 failures. The
scheduler's own `job_runs` table records **264 runs, every one `completed`, every
one `error_count=0`**. This is not a saturated signal — it is an **inverted** one.

---

## 1. Q1 — the defect

```python
now = date.today()                                   # agent_service.py:86
days_overdue = (now - inv.due_date).days if inv.due_date else 0   # :100
```

`Invoice.due_date` is `DateTime(timezone=True), nullable=False`
(`models/invoice.py:46-48`). `date - datetime` raises.

Measured on production — 163 failed jobs, **one** distinct `error_message`,
grouped per row and unbounded:

```
unsupported operand type(s) for -: 'datetime.date' and 'datetime.datetime'
```

⚠️ **The subtraction is the FIRST statement in the loop body**, before the
`days_overdue <= 0: continue` guard. Every invoice trips it. There is no subset
of invoices that works.

**The correct form already exists in this codebase**, in the agent that computes
the same thing (`ar_collections_agent.py:114-117`):

```python
due_ref = inv.due_date or inv.invoice_date
due_date_only = due_ref.date() if hasattr(due_ref, "date") else due_ref
days_out = (today - due_date_only).days
```

Two agents, one computation, one source table, and only one of them normalises.

---

## 2. Q2 — what a failing run produces, and what distinguishes the success

**A failing run writes nothing but its own job row.** The exception precedes
every write. Measured on production, across the entire table:

```
ar_aging_*  alerts ever written ......... 0
agent_collection_sequences rows ......... 0
```

This matters because `create_alert` calls `db.commit()` per alert, so a failure
*later* in the loop WOULD have committed partial results. It never gets there.
The reassurance is structural, not accidental — but it is thinner than it looks:
one guard moved above the subtraction and the same job would leave half-written
aging alerts behind.

**What distinguishes the 1-in-4 success — measured, per tenant:**

```
tenant 36fe9f40…   completed=0     failed=87    open_invoices=3
tenant 090e7eeb…   completed=12    failed=49    open_invoices=3
tenant f60ef8de…   completed=0     failed=27    open_invoices=2
tenant 52759c22…   completed=207   failed=0     open_invoices=0
```

⚠️ **"Fails 3 of 4 runs" is really "fails for 3 of 4 TENANTS, every night."**
The fourth tenant has **no open invoices**, so its loop body never executes and
the job completes. It has never failed and never will while that holds. Its 207
completions are the reason the job looks partly healthy.

The 12 completions on `090e7eeb` are the same effect in time rather than across
tenants: completions begin 2026-05-07, failures begin 2026-07-16. The job worked
while there was nothing to iterate. **The first open invoice broke it
permanently, per tenant.**

---

## 3. Q3 — what consumes it: nothing

The note's `collections_outstanding` fragment reads `AgentAnomaly` where
`entity_type='customer'` and `anomaly_type IN (collections_escalate,
collections_critical, collections_follow_up)`, joined to `AgentJob`.

Measured on production, grouped by the writing job type:

```
job_type=ar_collections    collections_follow_up    37
job_type=ar_collections    collections_critical     31
job_type=ar_collections    collections_escalate      1
```

**All 69 come from `ar_collections`. None from `ar_aging_monitor`.** And
`ar_aging_monitor` has written zero alerts and zero sequences, so there is
nothing of its output for anything to consume even in principle.

**The numbers James has been reading on the note for a week are computed
independently, from `Invoice` directly, by the agent that normalises correctly.**

⚠️ Consumers of AR aging beyond collections: **none found**, and the absence is
from enumerating what the job writes (two tables, both empty) rather than from
searching for readers. A job that writes nothing has no consumers by
construction.

---

## 4. Q4 — the signal is inverted, not saturated

The dispatch asked whether the saturated-signal reading still holds. Per-row over
the error text, unbounded: **163 failures, 1 distinct message.** So yes — a
genuinely different failure in that window would have been invisible, and none
occurred.

But the layer above is worse:

```
job_runs  AR_AGING_MONITOR   completed  206 runs   success=4  errors=0
job_runs  AR_AGING_MONITOR   completed   58 runs   success=2  errors=0
                             failed       0 runs
```

**264 recorded runs. Every one `completed`. Every one `error_count=0`.**

The mechanism is in the code, not the data. `run_ar_aging_monitor` catches its
own exception, calls `_complete_job(..., error=...)`, and **returns
`{"error": str(e)}` rather than re-raising** (`agent_service.py:163-166`). The
wrapper counts a tenant as successful when the function returns without raising
(`scheduler.py:101-105`), then records the run as
`"completed" if errors == 0 else "failed"`.

⚠️ So the table an operator would consult to ask *"did the nightly jobs run
OK?"* has said yes, 264 times, for a job that has aborted on three of four
tenants every night since 2026-07-16. The truth is one table over, in
`agent_jobs`, which nobody queries to check on the scheduler.

**This is the failure the taxonomy does not yet name.** A saturated signal emits
a real red that hides new reds. An absent signal emits nothing. This one emits
**green**, derived from a real measurement of the wrong quantity — "did the
function return?" standing in for "did the work happen?"

---

## 5. My own errors in this investigation

1. **I queried `job_runs` for `job_type='ar_aging_monitor'` and got zero rows.**
   The scheduler passes `"AR_AGING_MONITOR"` uppercase (`scheduler.py:148`). A
   constructed name producing a clean false absence — and it would have supported
   the conclusion I was already forming (that no scheduler record existed).
   Re-derived by enumerating all 26 distinct `job_type` values.
2. **My "non-comment lines" diff filter matched only `#` prefixes**, so docstring
   body lines showed as non-comment changes. A constructed pattern inside the
   verification of a comment-only change.

---

## 6. What the fix will need, when it is authorised

Not applied here, per the dispatch. What the blast-radius work established:

- The change is one line, and the correct form is already written twice over in
  `ar_collections_agent.py:116`.
- **Nothing downstream depends on the current (empty) output**, so fixing it
  cannot break a consumer. It can only start producing alerts and sequences that
  have never existed.
- ⚠️ **That is the actual risk.** On first successful run the job will create
  `ar_aging_31/61/90` alerts and `AgentCollectionSequence` rows for every overdue
  invoice across three tenants — a backlog accumulated since 2026-07-16, arriving
  at once. Eight open invoices today, so the volume is small, but the shape
  ("first green run emits a backlog") is worth expecting rather than discovering.
- The `job_runs` green is a **separate** fix and arguably the more important one,
  since it is not specific to this job: any agent that swallows its exception and
  returns is recorded as a successful run.
