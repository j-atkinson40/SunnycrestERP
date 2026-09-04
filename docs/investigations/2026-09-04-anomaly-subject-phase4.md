# Phase 4 — the three unlocated types are seeded demo data

**Date:** 2026-09-04 · **Read-only** against production. No writes.

The arc required these be resolved **by enumerating what writes to
`agent_anomalies`, not by searching harder for the string.** Done both ways —
data-side first, because the data knows.

**Answer: no agent emits any of the three. All three are written by
`backend/scripts/seed_accounting_demo.py`, a seed script, and the three
production rows are demo substrate rather than findings.**

---

## 1. Data-side enumeration

Every distinct `anomaly_type` joined to its writing job. **13 of 13 types
enumerated** — the count was checked against `count(DISTINCT anomaly_type)`
rather than assumed, because a grouped query that silently drops a type looks
exactly like a complete one.

| type | written by | rows |
|---|---|---:|
| `invoice_overdue` | `ar_collections` | 1 |
| `invoice_severely_overdue` | `ar_collections` | 1 |
| `uncategorized_expense` | `expense_categorization` | 1 |

All three dated 2026-08-10, all `entity_id IS NULL`, all on jobs still in
`awaiting_approval`. **Anomalies with no job link: 0** — nothing writes to this
table outside the job path.

---

## 2. Source-side, and the two ways the search could have lied

The job types point at `ar_collections_agent.py` and
`expense_categorization_agent.py`. **Neither emits any of the three.** They emit
`collections_follow_up` / `collections_escalate` / `collections_critical` and
`expense_low_confidence` / `expense_classification_failed` /
`expense_no_gl_mapping`.

⚠️ **`git log -S` returned nothing for all three, and I ran a positive control
before reporting that as absence.** Searching a literal I knew existed
(`"expense_no_gl_mapping"`) returned two commits, so the instrument sees. The
nulls were real.

⚠️ **And one apparent hit was a FALSE PRESENCE.** A whole-repo `git grep` put
`uncategorized_expense` inside `expense_categorization_agent.py`. It is
`find_uncategorized_expenses` — a **step name**, matched as a substring. No
`anomaly_type=` in `app/` produces it. Both §11 shapes appeared in one lookup,
in opposite directions, and neither was visible from the result alone.

**The real mechanism was neither construction nor deletion. It was SCOPE.** The
audit searched every `.py` under `app/` and reported honestly that nothing
matched. The writer is in `scripts/`. The audit's worry — that an f-string type
name evades a literal search — was a reasonable hypothesis and the wrong one;
its own honest framing ("deleted, elsewhere, or constructing the name") had
`elsewhere` in it, and `elsewhere` is what it was.

Worth keeping: the arc DID find a genuine constructed type name in
`tax_package_agent.py` (`anomaly_type=f"tax_package_missing_{agent_type}"`). The
mechanism is real in this codebase. It just was not this.

---

## 3. `backend/scripts/seed_accounting_demo.py`, lines 942–959

```python
_ANOMALIES = [
    # (job_type, severity, anomaly_type, description, amount)
    ("ar_collections", "warning", "invoice_overdue", ...),
    ("ar_collections", "critical", "invoice_severely_overdue", ...),
    ("expense_categorization", "info", "uncategorized_expense", ...),
    ...
]
```

The production descriptions match these literals **verbatim** — "Lakeside
Funeral Directors invoice is 121 days overdue at $3,750.00." That is
identification, not inference.

The script's own header says its first execution would be against production,
and its Phase 5 comment says `AgentJob`/`AgentAnomaly` are unguarded so it
writes them directly. It creates **one job per type**, marker-tagged.

---

## 4. ⚠️ Which also explains the null periods, and they are two populations

Production `agent_jobs` by null-period count:

```
ap_upcoming_payments       236 of 236 null     ar_aging_monitor    354 of 354 null
collections_sequence       356 of 356 null     ar_balance_recon      2 of   2 null
ar_collections               1 of 108 null     cash_receipts         1 of 172 null
expense_categorization       1 of 10394 null   month_end_close       1 of   1 null
```

**The four "exactly 1 of N" are the seed script's marker jobs** — one per type,
which is precisely what its loop creates. **The four 100%-null types are a
different population**: legacy scheduled agents that build `AgentJob` rows
directly instead of through `AgentRunner.create_job`, which requires both dates.

⚠️ **So `month_end_close`'s only production job is a seeded one, and it has no
period.** That is what made the regression in §5 live rather than theoretical.

---

## 5. ⚠️ A regression I introduced in phases 2–3 and this probe caught

`_period_subject_id()` originally **RAISED** on a null period. Its docstring
argued that `AgentRunner.create_job` requires both dates, so a null could only
come from another path — which is TRUE, and the other path is the common one.

The raise would have fired at the next run of `month_end_close` (its only
production job is null-period) and on the seeded `cash_receipts` job. **That is
removal-before-the-callers-comply — the exact error CLAUDE.md §11 records, made
inside the fix for it, by the author who had just written the entry into the
ratchet's own docstring.**

Corrected: a missing period yields `tenant_books` / tenant id rather than an
exception. **Honest, because if the job names no period the act is not
period-bounded**, and it still supersedes correctly — every unbounded run
produces the same subject rather than a fresh one.

Pinned by four tests, break-tested two ways: restoring the raise turns them red;
making the fallback run-scoped (`tenant:job_id`) also turns them red, which is
the control that matters — a fallback varying per run would pass a naive
no-raise test while reintroducing the defect the whole arc exists to remove.

---

## 6. Held for James — no writes made

**Three demo anomaly rows sit in the production anomaly table**, alongside two
more seeded types (`payment_possible_match`, `payment_unmatched_recent`) that
also appear in `_ANOMALIES`. They are dormant in `awaiting_approval`.

Whether they should be there is a disposition ruling and a WRITE, so it is not
mine. Recorded rather than acted on. It does mean any future count over
`agent_anomalies` should say whether it includes seeded rows — five of them
across four types.

---

## 7. Method notes

- Data-side before source-side, because the join answers "who wrote this"
  directly while a text search answers only "where does this string appear."
- `git log -S` was positive-controlled before its nulls were reported.
- The one apparent source hit was checked and was a substring false positive.
- Full enumeration, no `LIMIT`, and the group count checked against the distinct
  count.
- Read-only connection guard throughout; credentials never printed, only
  host/port/db.
