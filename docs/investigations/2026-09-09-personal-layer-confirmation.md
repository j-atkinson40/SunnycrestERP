# `personal_layer_service` — the confirmation, and the risk it was carrying is smaller

**Date:** 2026-09-09 · Read-only against the repo; no production writes.

This service was named as carrying the arc's remaining risk: *"more streams than
the anomaly service that set the estimate, and synthesis cost is per-fragment and
does not amortize."* **Measured, the premise does not hold.**

---

## 1. Stream counts, counted rather than inherited

| service | streams declared | streams LIVE |
|---|---:|---:|
| `anomaly_layer_service` (set the estimate) | 2 | 2 |
| `personal_layer_service` | 2 | **1** |

`personal_layer_service` does not have more streams. It has the same number, and
**half of it is dead code**: `_build_approvals_item` opens with an unconditional
`return None`, deferred 2026-05-04 to a "Phase W-4b" that has not shipped. Its
query survives below the early return as scaffolding, explicitly so the builder
can be MOVED rather than recreated.

⚠️ **So it should not be migrated to a fragment at all.** Turning dead
scaffolding into a live fragment would ship the surface the deferral exists to
avoid, and the deferral's reasoning — do not ship transitional UI that retires in
five weeks — is still the right call four months later.

---

## 2. The one live stream is already covered, and where it is not, it is a REPORT

`_build_tasks_item` reads `VaultItem` JOIN `task_details` filtered by
`company_id`, `assignee_user_id`, visibility, and non-terminal lifecycle states,
limit 20. `TASKS_DUE_TODAY` — registered in session 1 — reads the same substrate
with the same tenant and assignee filters.

**It is a strict subset**: `TASKS_DUE_TODAY` adds `due_date == today`. So the
live stream splits cleanly against the tightened admission test:

- **due today** → a bounded decision → already a prompt fragment. Done.
- **everything else assigned to you** → a list read on a rhythm → **a report**,
  and reports arrive as prompts in their own session.

**Neither half is new fragment work for this arc.**

---

## 3. Answering the confirmation's four questions

| question | answer |
|---|---|
| how many fragments? | **zero new** — the live stream's note-shaped half already ships |
| how many standing entries? | **zero** |
| queries reused verbatim? | yes — `TASKS_DUE_TODAY` already reads the same substrate with the same filters |
| did synthesis move as for `anomaly_layer_service`? | yes, and it was already server-side from session 1 |

**Materially harder? No — materially easier.** The five-session estimate does not
break here. The risk this service was thought to carry was a stream count that
included a builder returning `None`.

---

## 4. ⚠️ But the confirmation found a live defect in session 1's fragment

`TASKS_DUE_TODAY` filtered `completed_at IS NULL`.

`lifecycle.py` sets `completed_at` **only** when `to_state == "done"`. The four
terminal states are `done`, `cancelled`, `acknowledged`, `dismissed` — so
**three of the four leave it NULL**, and the fragment would have prompted a
person about a task somebody had already cancelled.

The filter reads as "not finished" and means "not marked done". The layer
service always filtered on the state itself; the fragment **paraphrased** it, and
the paraphrase was wrong in a way that looks right.

**Corrected** to `current_state NOT IN (terminal)`, with the terminal set
**derived from `ACTION_TRANSITIONS` / `REMINDER_TRANSITIONS`** — a state with no
outgoing transitions is terminal by construction — rather than listed here,
so a new terminal state cannot leave this filter behind.

Three tests, break-tested with the substitution count asserted first.

⚠️ **This is the argument for the confirmation deliverable existing.** It was
scoped to size the remaining work and it found a shipped fragment prompting
people about cancelled tasks. Nothing about that filter looked wrong.

---

## 5. Two fixture errors of mine, both the same shape

The bill-line fixture invented `bill_number` and a nullable vendor FK; the real
columns are `number` and a NOT NULL vendor. The task fixture omitted
`vault_items.vault_id`, which is NOT NULL. Both failed loudly, which is the right
failure — but both came from writing a shape from memory instead of reading the
model, twice in one file.
