# The subject defect is 45 of 75 write sites across 12 agents — STOP

**Date:** 2026-09-04 · **Read-only.** No code written. The writer fix is held.

The dispatch scoped one writer and instructed re-measurement rather than
inheriting the preliminary's figures. Re-measured, the defect is not one writer,
and the preliminary's central claim was false.

---

## 1. ⚠️ Correcting my own claim first

The preliminary (`11af0dd5`) stated: *"Every other anomaly type carries an entity
reference on every row. This one carries it on none."*

**The second sentence is true. The first is false.** It came from a query ending
`ORDER BY 2 DESC LIMIT 6` — I measured the six largest types and reported a
universal claim. Bounded by my view, not by the thing.

This is the shape canonised the same day in CLAUDE.md §11, *The constructed count
— magnitude is a claim too*, whose test is "what bounded this count — the thing,
or my view of it?" The entry existed, was written hours earlier, and I did not
apply it. The dispatch's instruction not to inherit the claim is the only reason
it was caught.

Corrected in place in the preliminary, original wording preserved.

---

## 2. What is actually true — all anomaly types, resolved and unresolved

| anomaly_type | resolved | rows | with entity_id |
|---|---|---:|---:|
| `expense_no_gl_mapping` | false | 1,825 | **0** |
| `payment_unmatched_recent` | true | 204 | 204 |
| `expense_classification_failed` | false | 192 | 192 |
| `collections_critical` | false | 24 | 24 |
| `collections_follow_up` | false | 23 | 23 |
| `ar_balance_drift` | false | 5 | 5 |
| `payment_unmatched_stale` | false | 4 | 4 |
| `high_unmatched_ratio` | false | 3 | **0** |
| `payment_unmatched_recent` | false | 3 | **2 of 3** |
| `uncategorized_expense` | false | 1 | **0** |
| `collections_escalate` | false | 1 | 1 |
| `payment_possible_match` | false | 1 | **0** |
| `invoice_severely_overdue` | false | 1 | **0** |
| `invoice_overdue` | false | 1 | **0** |
| `payment_possible_match` | true | 1 | 1 |

**Six types carry zero entity ids**, not one. And `payment_unmatched_recent`
carries them on **2 of 3** unresolved rows while carrying them on all 204
resolved ones — partial coverage *within a single type*, a third state the
preliminary did not consider and which no per-type summary would reveal.

`expense_no_gl_mapping` re-measured at **1,825** unresolved, `entity_type` also
null on all of them.

---

## 3. ⚠️ STOP — the defect is at the call site, and it is the majority

Counting `_make_anomaly(` / `self.add_anomaly(` call sites per agent, and how
many pass `entity_id` within six lines of the call. Occurrences, not lines:

| agent | call sites | with entity_id | lacking |
|---|---:|---:|---:|
| `month_end_close_agent` | 12 | 7 | 5 |
| `inventory_reconciliation_agent` | 10 | 7 | 3 |
| `year_end_close_agent` | 8 | 1 | **7** |
| `prep_1099_agent` | 7 | 2 | **5** |
| `cash_receipts_agent` | 6 | 4 | 2 |
| `tax_package_agent` | 6 | **0** | **6** |
| `unbilled_orders_agent` | 6 | 4 | 2 |
| `estimated_tax_prep_agent` | 5 | **0** | **5** |
| `ar_collections_agent` | 4 | 3 | 1 |
| `budget_vs_actual_agent` | 4 | **0** | **4** |
| `expense_categorization_agent` | 4 | 2 | 2 |
| `annual_budget_agent` | 3 | **0** | **3** |
| **total** | **75** | **30** | **45** |

**Forty-five of seventy-five write sites — 60% — record no subject.** Four
agents pass one at zero of their call sites: `tax_package`,
`estimated_tax_prep`, `budget_vs_actual`, `annual_budget`.

`expense_no_gl_mapping` is one of forty-five. Fixing it repairs 1/45 of the
defect and leaves the class intact, which is the STOP: *any other anomaly type
found to share this defect.*

⚠️ **The 45 is a lower bound on the count and an upper bound on confidence.**
It counts `entity_id=` appearing within six lines of a call — a heuristic. A
call passing it on line seven reads as lacking; a call in a helper that sets it
downstream reads as lacking. Verify per-site before editing any of them. What is
NOT heuristic is the production data: six types with zero coverage across every
row is measured, not inferred.

---

## 4. Three production anomaly types have no locatable writer

`uncategorized_expense`, `invoice_severely_overdue` and `invoice_overdue` exist
as unresolved rows in production. Searching every `.py` under `app/` for each
type's quoted literal returns **no match anywhere**.

⚠️ **Stated as a failed lookup, not an absence.** A writer constructing the type
name — an f-string, a mapping, a variable — evades a literal search entirely,
which is the constructed-name shape and is exactly how the five false absences in
the Sales & Orders census happened. The honest claim is: *no literal occurrence
exists in `app/`*, and the writer is either deleted, elsewhere, or constructing
the name. Which of those is unestablished and is not worth resolving before the
disposition ruling below.

---

## 5. Item 5 — the contract gap is real, and it is the absent-signal shape

Probed directly rather than reasoned about. A declaration whose condition always
yields `subject_id=""`:

```
REGISTRATION: ACCEPTED — registers fine
EMISSION:     REFUSED   — FragmentEmissionError, instance dropped, logged
```

So a null subject never reaches a user, which is the important half. But the
resulting behaviour is: **the fragment registers, runs on every note, emits
nothing, forever — and is indistinguishable from a fragment whose condition is
legitimately false.**

That is the same class IDENTITY was landed to close, one step earlier in the
chain, and it is specifically an absent signal: a permanently broken fragment
and a quiet one produce identical output. It is not silent in logs —
`emit_for_user` logs the rejection at exception level — but today established
that a log nobody reads is not a signal.

**Proposed fix, ~6 lines, NOT implemented per the dispatch's instruction.** In
`emit_for_user`, track per-fragment whether a condition returned instances and
*all* of them were rejected; log that case at ERROR with a distinct message
naming the fragment. It converts "quiet" into "loudly broken" at the one point
where the two are distinguishable — the condition returned something and nothing
survived validation. Registration cannot detect this without executing the
condition, so emission is the only place it can be caught.

⚠️ **None of the three shipped fragment types has this defect** — all declare a
subject that resolves. The gap is that nothing would have stopped one that
didn't, and session 2 declares four more.

---

## 6. Held — and what the ruling needs to cover

**No code written.** The writer fix is not started.

The category ruling stands and is right — subject is the thing the decision is
about, affected lines are attributes, resolution is category-scoped. What the
ruling did not anticipate is that it now has to be applied 45 times, or once in
a place that covers 45.

Three shapes the fix could take, offered as the decision rather than as a
recommendation:

1. **Fix `expense_no_gl_mapping` only**, as dispatched. Repairs the largest
   source. Leaves 44 sites and four zero-coverage agents intact, and leaves the
   class alive to reappear.
2. **Require a subject at `add_anomaly`** — make `entity_type`/`entity_id`
   mandatory parameters, so a call site that omits one fails at import or at
   first run rather than writing a subjectless row. This is the removal-over-
   recognition move: an anomaly without a subject becomes unexpressible rather
   than discouraged. It also breaks 45 call sites at once, each needing a
   per-site judgement about what its subject is, and four agents would need
   subjects invented rather than lifted.
3. **Require it for new sites, grandfather the existing 45**, with the
   grandfathered list enumerated and recorded so the debt has a direction.

Shape 2 is what the day's canon argues for and is the largest change. The
per-site judgement in 45 places is not mechanical: for `tax_package` and
`annual_budget`, which pass a subject nowhere, what the subject *is* has never
been decided.

**The 1,825 orphans remain untouched**, per the dispatch. Re-measured at 1,825
at time of work. No deletion, no update, no marking.

**The `*/15` cron remains untouched**, per the dispatch.

---

## 7. Method notes

- Every figure re-measured; nothing inherited from the preliminary or the
  dispatch, including the 1,825 and the only-one-type claim, both of which the
  dispatch explicitly flagged. One was confirmed and one was false.
- Call-site counts are occurrences of the call, not lines of grep output; the
  `entity_id` proximity check is a stated heuristic with its failure modes named.
- The three unlocated types are reported as a failed literal lookup, not an
  absence.
- Item 5 was probed by execution, not by reading the validator.
- Read-only against production throughout. No writes.
