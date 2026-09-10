# STOP — `past_tense` as landed cannot carry the settled note

**Date:** 2026-09-10
**Session:** note arc, the settling session
**Status:** STOPPED before building settling. No settling code written.

Two STOP lines fire, and a third is avoided rather than triggered.

---

## STOP 5 — one template, many outcomes

`EndTransition` has exactly three fields, verified at HEAD:

```
entity_kind: str    resolved_when: str    past_tense: str
```

**One past-tense template per fragment type.** Every registered prompt has more
than one way to end, and the ways mean different things.

### `tasks_due_today` — four terminal outcomes

Terminal states measured from the lifecycle tables, not assumed:
`('acknowledged', 'cancelled', 'dismissed', 'done')`. Events emitted on reaching
each, enumerated from `events_for_transition`:

| shape | reaches | events emitted |
|---|---|---|
| action | `done` | `task_completed`, `task_status_changed` |
| action | `cancelled` | `task_cancelled`, `task_status_changed`, `task_unblocked` |
| reminder | `acknowledged` | `task_status_changed` **only** |
| reminder | `dismissed` | `task_status_changed` **only** |

Its template: `"you completed {count} task{plural} due today"`.

A task **cancelled** today resolves this prompt. So does one **dismissed**.
Neither was completed.

⚠️ **A per-fragment wording fix cannot resolve this.** Any single phrase either
flattens the four into one — "you closed 4 tasks", which the ruling forbids —
or picks one outcome and states it falsely about the other three. The fragment
does not have a wording problem; it has more outcomes than the contract has
slots.

⚠️ **And two of the four have no dedicated event.** `acknowledged` and
`dismissed` emit only `task_status_changed`, so they are distinguishable solely
by reading the `to` field inside `task.transition`'s `changes` JSON. Even a
per-event design would need to look inside a payload for half the cases.

### `collections_outstanding` — two resolving acts with opposite meanings

Enumerated from the adapter, and one correction to my own first reading:
`request_review_customer` does **not** resolve — it stamps a note and leaves the
item queued (`anomaly_resolved: False`). Two acts resolve:

| act | what it writes |
|---|---|
| `send_customer_email` | `resolution_note = "Sent via triage — {tier} tier collection email to {recipient}"` |
| `skip_customer` | `resolution_note = "Skipped via triage — {reason}"` |

Its template: `"you worked {count} outstanding balance{plural}"`.

**"You worked 3 outstanding balances" when all three were SKIPPED is the
flattening the ruling forbids.** Skipping is not working, and the settled note
is what "what did I decide Tuesday" reads.

⚠️ **The discriminator exists only as free text.** The two acts differ by a
`resolution_note` prefix — "Sent via triage" / "Skipped via triage" — not by a
structured outcome field. So even a contract that could hold two templates would
have to select between them by prefix-matching prose, which is the substring
failure the note surface rejected for span marking.

### So the finding is the CONTRACT, not a fragment quirk

Both prompts that can actually settle have more outcomes than `past_tense` can
express. This is not "fix the wording on `tasks_due_today`."

**The shape of the fix, stated and not taken:** `past_tense` becomes per-outcome
— a mapping keyed on an outcome discriminator — and the resolving acts gain a
structured outcome field so the key is read rather than parsed out of prose.
That is a change to the fragment contract and to two adapters, and it belongs to
whoever owns that contract.

---

## STOP 1 — `expense_posting_map` can never generate a past tense

Measured on the canonical tenant today: it emits **0 instances**. Its own
declaration records why — the surface where a category's posting account is
chosen does not exist, so `category_posting_account_recorded` can never occur.

A prompt that never emits never resolves, and a resolution that never happens
generates no record. Its `past_tense` is unreachable by construction, not by
absence of data.

---

## The production-writer STOP — avoided, not triggered

Settling runs at a tenant-configured hour. Registering it would mean an
`add_job` in `app/scheduler.py`, which runs on every deploy — a **scheduled
writer against production**, which is a different authorization from anything
this arc has had.

**Nothing was scheduled. No settling hour setting was added** — there is none in
the codebase today (`settling_hour` / `settle_hour` return nothing). The
existing precedent for per-user local timing is the briefings sweep: one global
`CronTrigger(minute="*/15")` plus a per-user preference check in application
code, resolving `Company.timezone` with an `America/New_York` fallback.

That is the shape settling would take, and it is James's to authorize.

---

## What this session did not build, and what would have worked

No settling service, no scheduler entry, no migration.

Had the contract been able to carry it, `collections_outstanding` is the one
fragment with everything else in place: real emission (5 instances on the
canonical tenant today), a resolution recorded with `resolved_at` AND
`resolved_by`, and a subject that maps cleanly to the anomalies that resolve it.
It is blocked only on saying which of the two acts occurred.

`tasks_due_today` has the richer event record — `task.transition` with from/to
and an actor, plus dedicated `task_completed` / `task_cancelled` — and is
blocked on the same thing plus the two eventless reminder outcomes.

## What the probe established, restated so it is not mistaken for a blocker

The events are real and carry actors. Production has none of them because
nobody has used the platform — verified by exercising a transition, not
inferred from the absence. **Settling is buildable and reviewable on seeded
data, and not reviewable on production data.** An empty production settled note
would mean neither that the feature works nor that it fails.

## Claims verified rather than inherited

| Claim | Verdict |
|---|---|
| `past_tense` is reachable / unconsumed | **Confirmed unconsumed at HEAD.** Zero references outside `types.py` and `platform_defaults.py`. This session is genuinely its first consumer. |
| The day identity works as described | **Confirmed.** `DailyNote.subject_id` = `f"{user_id}:{note_date}"`; `note_date` is a tenant-local `Date`. |
| The probe's event list is complete | **Extended.** The probe named `task.transition`, `task_completed`, `task_cancelled`. Re-enumerated: `task_status_changed` is also emitted on every transition, `task_unblocked` fires on cancellation from `blocked`, and the two reminder terminals emit nothing else. The probe's list was correct and not exhaustive. |
