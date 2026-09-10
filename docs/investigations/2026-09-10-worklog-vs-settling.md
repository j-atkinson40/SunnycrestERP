# Does settling already have a live twin?

**Date:** 2026-09-10
**Status:** PRELIMINARY ANSWERED. Read-only. No code written.
**Question:** would the work log's counts and settling's past-tense fragments
derive from the same events, with the same actor attribution, differing only in
tense and in when they are read?

---

## Answer: NO — and they diverge in BOTH directions

The settled note is **not** the work log frozen at the settling hour. Settling
is not substantially built for it, and the work log is not a view over settling.

---

## Divergence 1 — settling reads what `audit_logs` does not contain

Settling's collections resolver reads the **table**:
`agent_anomalies.resolved_by`, `resolved_at`, `resolution_outcome`. It does that
because `ar_collections_adapter` writes **zero audit rows** — measured: zero
occurrences of `log_action` or `AuditLog` in that module.

Measured in production:

| | count |
|---|---|
| resolved anomalies in `agent_anomalies` | **205** |
| `audit_logs` rows with `entity_type='agent_anomaly'` | **3** |

The three come from `anomalies_widget_service`, which is the only writer of
`action="anomaly_resolved"`. **A work log built on `audit_logs` would miss
essentially every collections act.**

## Divergence 2 — the work log needs what settling structurally cannot see

`settle_note` iterates `note_fragment_renders WHERE kind = 'prompt'`. It can
therefore only ever settle **a declared prompt that rendered on that note**, and
only if that prompt's `resolved_when` has a resolver.

"4 sales orders entered" has no prompt fragment. The five registered fragments
are `anomaly_watchlist`, `compliance_flags`, `tasks_due_today`,
`collections_outstanding`, `expense_posting_map` — none is about entering a
sales order. **Settling is blind to the work log's central example by
construction, regardless of what events exist.**

That is not a gap to fill. Settling answers *"did the thing I was prompted about
get done"*; the work log answers *"did I enter that order"*. A prompt is a
precondition of the first question and irrelevant to the second.

## Where they DO overlap

Task terminal transitions, and only those. Both would read `audit_logs` —
settling via `action='task.transition'` (reading `to` out of the `changes`
payload), a work log via the same rows plus `task.task_completed` /
`task.task_cancelled`. Same actor, same timestamps. This is the one place the
"two tenses of one thing" framing holds.

---

## What the work log's own session should know

**The events exist and carry actors — locally.** `sales_service` calls
`audit_service.log_action` 19 times and passes `user_id` at every site. Local
`created` rows carry actors for `quote` (20), `invoice` (8), `customer_payment`
(7), `sales_order` (4), `vendor_bill` (3), `product` (1).

**⚠️ On production they largely do not exist.** Every audit action carrying an
actor, unbounded:

| action | n |
|---|---|
| `login` | 1922 |
| `created` | 33 |

Two. And `created` breaks down as `invoice` n=28 (**16 with an actor**),
`customer_payment` n=14 (14), `vendor_bill` n=3 (3). **No `sales_order`, no
`quote`, no `product` rows at all.**

So the work log would be near-empty on production for exactly the reason
settling is: nobody has used the platform. It is buildable and reviewable on
seeded data, and not reviewable on production data.

**And 12 of 28 invoice `created` rows carry no actor**, so even the audited path
is partially unattributed. A work log saying "you created 28 invoices" from
those rows would be claiming 12 acts it cannot attribute to anyone.

---

## Consequence for scoping

- The work log needs **its own read path** — `audit_logs` by
  `(user, tenant-local day, action, entity_type)`. That path is simple and the
  events are already written; it is a view plus a scoped click-through, not an
  event-plumbing exercise.
- It also needs a decision this investigation does not make: whether to read
  `agent_anomalies` alongside `audit_logs`, or to make the collections adapter
  write audit rows. Those produce the same surface and different amounts of
  backfill.
- **§2 of this arc is a hard dependency of it.** "Clicking *4 sales orders
  entered* lands on those four" is precisely scope-that-survives-the-URL.

## A method correction

An earlier probe this arc asked "which actions carry an actor" with `LIMIT 8`
and reported the answer as complete. Re-run unbounded, production has exactly
**two** such actions — so the bound never bit and the conclusion happened to be
right. **It was right by luck, not by method**, and the same query against the
local database would have been truncated: 11 distinct actions there.
