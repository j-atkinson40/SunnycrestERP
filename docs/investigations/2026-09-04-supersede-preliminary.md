# Session 2 preliminary check — STOP. Supersede never shipped, and the anomaly has no subject to supersede on.

**Date:** 2026-09-04 · **Read-only.** No code written. Session 2's build is held.

The dispatch made this a hard STOP: prose composed over a writer that
manufactures its own volume would have the composition gate correctly
suppressing it, which looks like the gate working while the defect grows. Both
STOP conditions are met, and the second was not anticipated.

---

## 1. The canon citation is real, and near-verbatim

The dispatch reported it as reported. Verified — `DECISIONS.md:1282`:

> ## 2026-09-01 — Anomaly supersede is a condition of shipping any anomaly-writing fix
>
> The expense classifier has accumulated 1,299 unresolved `expense_no_gl_mapping`
> anomalies against 3 bill lines, re-created every run with no supersede. Any fix
> that touches an anomaly-writing path ships supersede in the same pass. Shipping
> a posting path while leaving a permanent unrelated alarm hands an operator a
> working feature plus a standing lie about their data, and a duplicate-generating
> anomaly writer is the same class of defect as whatever is being fixed. The Task
> substrate's composite idempotency key — `(provenance_kind, provenance_ref_type,
> provenance_ref_id, event_kind)` — is the shape to match.

Nothing fabricated. The entry says what the dispatch attributed to it.

**One figure has moved.** The entry cites 1,299; measured today the same
condition is **1,825 unresolved rows**, created 2026-08-10 through 2026-08-31.
Since the last row predates the entry by a day, the 1,299 was measured some days
before it was written rather than at writing time. Not a contradiction — a stale
figure in canon, which is what the dating and supersession rules exist for.

---

## 2. ⚠️ STOP 1 — supersede did not ship, and the writer is live

**It did not ship.** `BaseAgent.add_anomaly` (`base_agent.py:210-230`) appends an
`AnomalyItem` and increments `job.anomaly_count`. No supersede, no dedup, no
existence check, no idempotency key. `expense_categorization_agent.py:380-388`
writes `expense_no_gl_mapping` through that path with no guard of its own.

Enumerated across `app/services/agents/` and `app/services/workflows/`: the only
supersede implementation in either tree is `catalog_fetch_adapter.py`, which
supersedes `UrnCatalogSyncLog.publication_state` — a different table, a different
path, and not the one canon named.

**The writer is live.** `default_workflows.py:1505` still carries
`"cron": "*/15 * * * *"` — 96 runs per day per tenant.

**It is quiet for a reason that is not a fix.** No rows since 2026-08-31, which
matches the approval-queue finding: growth collapsed on 09-01 because the
uncategorized line cleared, not because anything changed. The next unmapped
category resumes it at 96/day with no supersede, exactly as before.

So the condition canon made mandatory three days ago is unmet, on a path that is
scheduled, unguarded, and currently idle only by accident.

---

## 3. ⚠️ STOP 2 — the anomaly has no subject, so there is nothing to supersede ON

This was not anticipated by the dispatch and is the more serious of the two.

Measured, unresolved anomalies, `entity_id` coverage:

| anomaly_type | rows | with entity_id |
|---|---:|---:|
| **`expense_no_gl_mapping`** | **1,825** | **0** |
| `expense_classification_failed` | 192 | 192 |
| `collections_critical` | 24 | 24 |
| `collections_follow_up` | 23 | 23 |
| `ar_balance_drift` | 5 | 5 |
| `payment_unmatched_stale` | 4 | 4 |

> ## ⚠️ [CORRECTED 2026-09-04] — THE CLAIM BELOW IS FALSE AS WRITTEN
>
> The original text read: *"Every other anomaly type carries an entity reference
> on every row. This one carries it on none."* The second sentence is true. **The
> first is false**, and it was produced by a query with `LIMIT 6` — a universal
> claim bounded by my view of the data rather than by the data.
>
> Re-measured across ALL types, resolved and unresolved: **six types carry zero
> entity ids**, and `payment_unmatched_recent` carries them on 2 of 3 unresolved
> rows — partial coverage within one type, a third state the original did not
> consider. See `2026-09-04-anomaly-subject-audit.md` for the full enumeration
> and for the 45-of-75 call-site finding that supersedes this section's framing
> entirely.
>
> Original wording preserved below.

**Every other anomaly type carries an entity reference on every row. This one
carries it on none.** The write site passes no `entity_type` and no `entity_id`,
and the description is category-scoped rather than line-scoped:

    f"Category '{proposed_category}' has no GL account mapping "
    f"for this tenant. Add a mapping in Settings → GL Accounts "
    f"before this can post."

Which is why there is exactly **one distinct description across 1,825 rows** —
the text names a category, never a bill line. 1,825 rows referring to a thing
none of them identifies.

### Three consequences, each blocking something different

**Canon's prescribed fix is not directly applicable.** The entry names the task
substrate's `(provenance_kind, provenance_ref_type, provenance_ref_id,
event_kind)` as the shape to match. `provenance_ref_id` requires a ref. There is
none. Supersede cannot be keyed until the anomaly is given a subject — which is
a data-model change to the writer, not the dedup pass canon describes.

**The IDENTITY declaration cannot be satisfied for a fragment over this source.**
Per DECISIONS 2026-09-04, a fragment's key must derive from what the condition is
about. This condition is about a bill line the anomaly does not record. A
fragment would have to key on the category — coarser than the real subject, and
it would collapse genuinely distinct unmapped lines into one instance.

**Session 2's synthesis requirement cannot be met on this path.** "Every factual
claim is a link, and the link is the provenance mark" requires the synthesizer to
hold entity ids. Here there are none to hold. This is the dispatch's own STOP
line — *any place server-side synthesis cannot obtain the entity ids a link
requires* — and it is met at the largest single anomaly source in production.

⚠️ **The entry's "against 3 bill lines" cannot be verified from the anomaly
table.** With `entity_id` null on all 1,825 rows, nothing in `agent_anomalies`
records which lines these are. That figure must have come from reading the bill
lines directly. It may well be right; it is not checkable from the rows the entry
is about, which is itself a symptom of the same defect.

---

## 4. What this changes about the composition gate

The gate as specified would work, and that is the problem the dispatch
anticipated.

A non-prompt renders only on CHANGE against the previous note's state for its
IDENTITY. With 1,825 rows collapsing to one subject, the second day's evaluation
matches the first, the fragment is correctly withheld, and the note stays quiet
while the writer keeps producing. **The gate would suppress the symptom and
report nothing.** Correct behaviour, invisible defect — which is why this check
came first.

---

## 5. Held, and what unblocks it

**Session 2 is not started.** No code written.

The remedy is a production write and a data-model change to a live anomaly
writer, so it is James's. In dependency order:

1. **Give the anomaly a subject.** Pass `entity_type`/`entity_id` for the bill
   line at the write site. Nothing else is possible until this exists — supersede,
   IDENTITY and linkable prose all need it.
2. **Then supersede,** keyed on that subject, per the 09-01 entry's shape.
3. **Then the 1,825 existing rows,** which have no subject and cannot be
   retroactively given one from the rows themselves.
4. **Then decide the `*/15` cron,** which is the volume multiplier behind this
   and behind the 11,930 `workflow_runs` in `awaiting_input`.

Steps 1 and 2 together are what canon meant by "ships supersede in the same
pass"; the entry did not anticipate that step 1 was missing.

**Session 2 could proceed on other sources.** ⚠️ [CORRECTED 2026-09-04] — this
sentence rested on the falsified claim above. Six types lack entity ids, not one. But
the dispatch's STOP is explicit, the largest source in production is the affected
one, and building prose that must exclude the biggest thing on the surface is a
decision rather than an implementation detail. Held for that ruling.

---

## 6. Method notes

- The canon entry was quoted from the file, not restated.
- Supersede absence claimed from enumeration across `app/services/agents/` and
  `app/services/workflows/`, not from a miss on a constructed name; the one
  implementation found is named and distinguished.
- Counts are rows, from `agent_anomalies`, bounded by the full table.
- `entity_id` coverage measured per type rather than in aggregate, which is what
  made the single-source anomaly visible — an aggregate would have shown 1,825
  of 2,084 missing and read as a general problem rather than one writer.
- Read-only throughout; no production write.
