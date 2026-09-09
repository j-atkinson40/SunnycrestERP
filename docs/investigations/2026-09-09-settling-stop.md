# STOP — the settled note cannot be generated from recorded events

**Date:** 2026-09-09
**Session:** note arc session 4 (settling + deferral)
**Status:** STOPPED before any code. Nothing built.

Triggered by STOP line 1 of the dispatch — *"Any fragment type whose past-tense
form cannot be generated from recorded events"* — for **all three** prompt
fragments, on the same underlying fact.

---

## The finding in one line

**Every `past_tense` template is first-person, and not one recorded event in
production carries an actor.**

```
tasks_due_today          "you completed {count} task{plural} due today"
collections_outstanding  "you worked {count} outstanding balance{plural}"
expense_posting_map      "you recorded a posting account for {count} categor{plural}"
```

---

## Measured against production (READ-ONLY, connection-level guard)

`create_engine(url, connect_args={"options": "-c default_transaction_read_only=on"})`.
Credentials never printed — host/port/db only via `urlparse`.

**`task_details` — 2,345 rows, every one `current_state='created'`.**
No `assigned`, no `done`, no `cancelled`, no `dismissed`. `completed_at` set on
**zero** rows. Earliest `task.task_created` audit row is 2026-05-25. **No task
has ever reached a terminal state in production**, in three and a half months.

**`audit_logs` task events — one action only.**

| action | n | window | with actor |
|---|---|---|---|
| `task.task_created` | 2,345 | 2026-05-25 .. 2026-09-08 | **0** |

No `task_status_changed`. No `task_completed`. The emitter exists
(`tasks/lifecycle.py:185`, *"every transition fires task_status_changed"*) and
the subscriber exists (`audit_subscriber.py:55`); nothing has ever transitioned.

**`agent_anomalies` — resolution is timestamped but unattributed.**
205 resolved · 205 with `resolved_at` · **0 with `resolved_by`** · latest
2026-08-10. The column exists and is NULL on every row.

**The whole `audit_logs` table.** 4,315 rows, 1,955 carrying a `user_id`. The
only actions that ever carry an actor are `login` (1,922) and `created` (33).

**`expense_posting_map`** emits zero by construction — its condition is grounded
on blocked work and there is none. Its own declaration already records that the
surface where a category's posting account is chosen does not exist.

---

## Why this is a STOP rather than a smaller sentence

The design is sound and session 1 built it correctly. `EndTransition` holds
`resolved_when` + `past_tense` as **data** precisely so *"the settled note be
generated from events that actually occurred rather than from a re-run of the
condition."* That is the right architecture. Session 4 is its first consumer —
`resolved_when` and `past_tense` are declared and, until now, never read.

The problem is not the templates or the plumbing. It is that **the events the
plumbing would read do not exist, and where they exist they cannot say who.**

Three separate failures, one consequence:

1. **No transitions at all** (tasks). Not "few" — zero, ever.
2. **Transitions without an actor** (anomalies). 205 resolutions, no `resolved_by`.
3. **A prompt that cannot emit** (expense posting map), so it can never resolve.

Approximating any of these produces a settled note that says *you* did something
the record cannot attribute to anyone. That is the failure mode the surface's own
premise forbids — it is the same class as a link that shows today's data under
yesterday's sentence, arriving in the verb instead of the href.

### A secondary finding worth separating

Even given events, `tasks_due_today` would **overclaim**. Its resolution is
`task_reaches_terminal_state`, and the terminal states are
`('acknowledged', 'cancelled', 'dismissed', 'done')` — measured, not assumed.
Only `done` is completion. A task **cancelled** today resolves the prompt, and
"you completed 1 task" would be false. The honest generation counts `done`
alone, which means a prompt can resolve and produce no settled record — a gap
that has to be a deliberate ruling, not a side effect.

---

## The three claims the dispatch said not to inherit

| Claim | Verdict |
|---|---|
| The day identity exists as the `user_day` subject | **Confirmed.** `subject_id=f"{user.id}:{today.isoformat()}"` (`platform_defaults.py:335`), and `instance_key = f"{fragment_id}:{subject_kind}:{subject_id}"` (`emission.py:71`). Reusable as-is. |
| Condition inputs are enumerable and snapshottable | **Confirmed.** All five registered fragments populate `condition_inputs` (lines 170, 241, 347, 448, 523). |
| Non-prompts keep dismiss, and `signal_service` depends on that distinction | **NOT as described.** `signal_service` persists dismiss as `{component_key, time_of_day, work_areas_at_dismiss}` and has **no concept of prompt vs non-prompt** and no reference to the fragment contract. The distinction is real but enforced in the contract itself — `end_transition` is required for `prompt` and forbidden for `non_prompt` — not in `signal_service`. Nothing breaks; the dependency named in the dispatch is not the one that exists. |

---

## What the note surface has actually done

`note_fragment_renders` in production holds **3 rows**, all 2026-09-09:
`collections_outstanding` (prompt) ×2, `anomaly_watchlist` (non-prompt) ×1.
`daily_notes` holds 3 notes, 2026-09-04 .. 2026-09-09.

So the live surface has rendered one prompt type and one non-prompt type, twice
and once. A settling job run tonight would have one prompt to settle and no
recorded resolution to settle it from.

---

## What is buildable, and what it depends on

**§2 deferral is buildable and §1 is not, but they are coupled.** Deferral is an
action taken *in the note surface*, so the surface is the writer and records the
actor itself — no dependency on anyone else's events. The condition-input
snapshot has its source (confirmed above), and the wake-on-divergence diff is
straightforward against it.

The coupling is the dispatch's own line: *"Deferral is RECORDED on the day's
settled note."* If there is no settled note, that record has nowhere to land.
Deferral can be built to record onto the day's note without the past-tense
summary existing — but that is a scope decision, not something to assume.

**§3's idempotency discipline** (identity keyed on subject, never on run) applies
to whatever settling eventually does and is not itself blocked.

---

## Method note

The first production probe queried `note_fragment_renders.rendered_at`. That
column does not exist — the column is `note_date`. It raised `ProgrammingError`
rather than returning a plausible empty result, so the constructed name was
caught by the database rather than by me. Had the column existed under a
different meaning, the zero would have been reportable and wrong.
