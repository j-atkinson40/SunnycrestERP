# Production state re-verify, ahead of the cutover arc

**Date:** 2026-09-04 · **Read-only.** No writes, no seeds, no test bot.
**Method:** `railway run --project ad95792e… --environment production --service
SunnycrestERP` with `create_engine(url, connect_args={"options": "-c
default_transaction_read_only=on"})` — the connection-level guard, because the
session-level `SET` was proven not in force earlier in this campaign and
accepted a write. Connection string redacted via `urlparse`; host and database
name only.

Commissioned because the cutover arc's ordering depends on STATE.md's
**2026-07-29** figures, which are six weeks old and were a hypothesis about
today rather than a fact.

---

## 1. The 07-29 entry is stale on four points

| Claim (2026-07-29) | Measured 2026-09-04 |
|---|---|
| migration head `r147` | **`r174_gl_category_correction`** — 27 ahead |
| `je_lines=0` — "books are EMPTY" | **30 lines / 15 entries**, all on `sunnycrest` |
| `total_runs=0` | **17,709 `workflow_runs`** |
| Plaid "not yet loaded" | **1 `plaid_items` row on `sunnycrest`**, 36 bank transactions |
| 4 companies, 18 users | 4 / 18 — unchanged |
| 224 GL mappings on sunnycrest, 0 elsewhere | 224 / 0 — unchanged |

The two "0" figures are the load-bearing ones, because the entry's ordering
argument rests on them: *"can't reconcile without opening balances; Books Review
Phase 2 has nothing to review until cutover data exists."* Both are now
non-zero. The ordering claim needs re-deriving against real numbers rather than
inherited ones.

---

## 2. Sunnycrest — the live tenant, in full

| | |
|---|---|
| Journal entries | 15, spanning **2026-08-06 → 2026-08-09** |
| Invoices | 8 — 5 paid, 2 partial, 1 sent |
| **Open AR** | **3 invoices, $4,248.93**, dated 2026-04-11 → 2026-08-02 |
| Vendor bills | 3, **0 open AP** |
| **Sales orders** | **0** |
| Customers | 5 |
| Plaid items | 1 |
| GL mappings | 224 |

Three observations, marked as inference where they are inference:

**The journal entries sit inside a four-day window.** Fifteen entries between
6 and 9 August and nothing before or since. That is the shape of one sitting of
manual entry, not of ongoing operations. Whether they are opening balances is
NOT established here — it requires reading the entries, which this pass did not
do.

**⚠️ Zero sales orders on the live tenant.** The platform's core object, for a
burial-vault manufacturer whose stated workflow is order → delivery → invoice,
does not exist for the real customer. Eight invoices exist without any order
behind them. This is measured; what it means operationally is not — invoices may
be entered directly, or orders may live outside the platform.

**Open AR is smaller than a live-since-April business implies.** Three open
invoices totalling $4,248.93, with the oldest dated 2026-04-11. Either very
little has been billed through the platform, or historical AR was never loaded —
which is what the 07-29 entry predicted, and is still the most likely reading.

---

## 3. ⚠️ 8,192 agent jobs are sitting in `awaiting_approval` on production

The largest single finding of this pass, and it is not in any STATE entry.

```
status              count
awaiting_approval   8192
complete            2464
completed            804      ← two spellings of the same terminal state
failed               142
running                1
```

Oldest `awaiting_approval`: **2026-05-06.** Newest: **2026-09-03.**
Four months of continuous accumulation, still growing yesterday.

By tenant:

| tenant | awaiting_approval |
|---|---|
| `hopkins-fh` | **6,037** |
| `sunnycrest` | **2,046** |
| `st-marys` | 95 |
| `testco` | 14 |

Two things make this worse than a large number.

**`hopkins-fh` has 6,037 pending approvals and no data at all** — zero journal
entries, zero invoices, zero vendor bills, zero customers, zero sales orders.
The per-tenant agent sweep is manufacturing approval jobs for an empty tenant,
which means the count is not a backlog of real decisions; it is mostly noise
that a real decision would now be buried in.

**Nothing tells anyone.** This campaign already established that all eleven
triage queues fire zero notifications (STATE, 2026-05-26). So 2,046 pending
approvals on the live tenant have been accumulating for four months with no
surface reporting them. This is the saturated-signal shape at data altitude: a
queue whose contents are individually meaningful and collectively unreadable.

**Also worth a look:** `complete` (2,464) and `completed` (804) are both
present. Two spellings of one terminal state is the kind of thing that makes a
status filter silently wrong — a query for one gets a fraction of the other's
rows. Not investigated here.

---

## 4. What this changes for the cutover arc

The 07-29 entry's list of not-yet-loaded items holds up **partially**:

- **Opening balances / trial balance** — unresolved. 15 JEs exist in a four-day
  August window; whether they are the opening position is unread.
- **Open AR (aged)** — partially present. 3 invoices, $4,248.93. Whether that is
  the real aged position or an incidental artifact of live use is unread.
- **Open AP** — genuinely empty. 3 bills, 0 open.
- **Plaid on the real operating account** — connected. 1 item, 36 transactions.
  Whether the born-dry schedule was promoted is unread. Note
  `financial_accounts` totals **1** across all four tenants, which is thin for a
  cutover.
- **Historical comparison for trust** — not measured.

**The ordering argument needs re-deriving, not inheriting.** It was built on
`je_lines=0` and `total_runs=0`, and both are false now. Whether the cutover arc
still sits ahead of Books Review Phase 2 is a live question rather than a
settled one.

---

## 5. Method notes

- One column name was **guessed and wrong**: `invoices.total_amount` does not
  exist. Read off the model instead — the columns are `total`, `amount_paid`,
  `amount_credited` — and re-run. A constructed name, caught by the query
  failing loudly rather than by returning a plausible zero, which is the good
  failure mode.
- Per-query rollback isolation was used throughout, because a failed query
  aborts the transaction and makes the *next* table report an error about
  something never touched.
- Counts are rows, not lines of output.
- Everything in §2 and §3 is measured. Every interpretation is marked as
  inference and most of the interesting ones are explicitly **unread**, because
  answering them means reading tenant financial records, which was outside this
  pass's remit.
