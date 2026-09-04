# Phase 5 preconditions — the key shape transfers, its ENFORCEMENT does not

**Date:** 2026-09-04 · **Read-only** against production. No writes, no migration.

The arc's STOP line: *"Any finding that the 2026-09-01 supersede entry's
prescribed key shape does not transfer to `agent_anomalies` once a subject
exists."* Established rather than assumed. **It half-transfers, and the half that
fails needs a production migration and a disposition write — both James's.**

---

## 1. The shape transfers. All four components have counterparts.

The Task substrate's composite idempotency key is
`(provenance_kind, provenance_ref_type, provenance_ref_id, event_kind)`.

| Task component | `agent_anomalies` counterpart | exists? |
|---|---|---|
| `provenance_ref_type` | `entity_type` — the subject kind | ✅ |
| `provenance_ref_id` | `entity_id` — the subject id | ✅ |
| `event_kind` | `anomaly_type` | ✅ |
| `provenance_kind` | constant for this table (`anomaly_detection`, already a legal Task value) | ✅ n/a |

Phases 2–3 are what made this possible: before them, two of four components were
null at 34 of 64 sites.

---

## 2. ⚠️ Blocker one — there is no tenant column, and it is not cosmetic

`agent_anomalies` reaches its tenant only through
`agent_job_id → agent_jobs.tenant_id`. **A partial unique index cannot span
tables.**

This would be a mere inconvenience if subjects were globally unique. **After
phases 2–3 they deliberately are not.** `fiscal_year:2026`,
`tax_year:2026`, `accounting_period:2026-08-01:2026-08-31`,
`expense_category:utilities` are byte-identical across tenants — that is what
makes them stable subjects rather than run artifacts.

⚠️ **So a key without a tenant column would collapse two tenants' anomalies into
one row.** That is a cross-tenant defect, not a missing index. **Three tenants
write anomalies in production today** (2,266 / 14 / 9 rows), so it is live, not
hypothetical.

**Requires: `tenant_id` on `agent_anomalies`, backfilled from the job, then NOT
NULL.**

---

## 3. ⚠️ Blocker two — `entity_id` is varchar(36), and 36 is already in use

The column was sized for UUIDs. A UUID is exactly 36 characters, and the longest
`entity_id` in production today is **exactly 36**.

Phases 2–3 introduced composite subjects that land on the same ceiling:

```
total_expenses:2026-08-01:2026-08-31   = 36   ← fits by ONE character
total_revenue:2026-08-01:2026-08-31    = 35
```

⚠️ **And `expense_no_gl_mapping` now writes unvalidated model output into it.**
`proposed_category = result.get("category", "other_expense")` is taken straight
from the classifier and **is never checked against the 15-item
`EXPENSE_CATEGORIES` list** it was asked to choose from. Bounded in practice —
the vocabulary's longest is `repairs_maintenance` at 19, and production's longest
category in use is 20 — and unbounded by construction, on a `*/15` cron.

**Requires: widen `entity_id`. And validating the classifier's category against
the vocabulary is worth doing on its own merits** — a hole with a guard on it
versus no hole.

---

## 4. ⚠️ Blocker three — the index is not buildable on today's data, and the
reason is the finding

A partial unique on `(tenant_id, anomaly_type, entity_type, entity_id)
WHERE NOT resolved AND entity_id IS NOT NULL` **would fail to create**: 9
colliding groups.

| type | subject | rows |
|---|---|---:|
| `expense_classification_failed` | one `vendor_bill_line` | **192** |
| `collections_critical` | one `customer` | 24 |
| `collections_follow_up` | one `customer` | 14 |
| `collections_follow_up` | one `customer` | 9 |
| `ar_balance_drift` · `payment_unmatched_*` (5 groups) | one entity each | 2 each |

**251 unresolved subjected rows collapse to 11 distinct decisions.** 240 rows are
pure duplication.

⚠️ **This is the sharpest argument phase 5 has, and it inverts an assumption the
arc was carrying.** Every one of those 192 rows **already has a subject** —
`entity_type='vendor_bill_line'`, a real UUID. They were never part of the 34.
**So subjects do not prevent duplication; only supersede does.** The 1,825
`expense_no_gl_mapping` rows were the visible instance because they had no
subject at all, and fixing that was necessary and is not sufficient.

**The 1,825 do NOT block the index** — all 1,825 have `entity_id IS NULL`, so
the partial index excludes them. The index is buildable without touching them,
which keeps James's disposition ruling open rather than forcing it.

Coverage: 251 rows covered, 1,833 excluded for null subject, 205 excluded as
resolved, 2,289 total.

---

## 5. Recommended sequencing — and it is this arc's own lesson applied

The index is the removal step: it makes a duplicate **unexpressible**. Canon says
removal is LAST, after the callers comply. The 240 existing duplicates are the
non-compliant callers.

```
5a  MIGRATION, structural only, blocks nothing:
      + tenant_id on agent_anomalies (backfill from job, then NOT NULL)
      + widen entity_id
      + validate proposed_category against EXPENSE_CATEGORIES
5b  SUPERSEDE ON WRITE, application level:
      before insert, mark prior unresolved same-key rows superseded.
      Self-healing: one run per agent collapses that agent's backlog.
5c  THE UNIQUE INDEX, once 5b has drained the 240.
      This is the removal, and it comes last for the same reason the
      signature change does.
```

⚠️ **5b needs a `superseded` state that does not exist.** `resolved` is a
boolean with `resolved_by` / `resolved_at` / `resolution_note` — marking a
duplicate `resolved=true` would **claim a human resolved it**, which is a lie in
the audit trail and would corrupt any "what did operators act on" query. Needs
either a `superseded_at` column or a `resolution_note` convention, and the column
is the honest one.

---

## 6. ⚠️ STOP — what needs James, and why I did not proceed

1. **A production migration** adding a column to a live table and backfilling
   2,289 rows.
2. **A new lifecycle state** (`superseded_at`), which changes what every existing
   anomaly query means.
3. **Whether 5b's supersede should touch the 240 existing duplicates** — that is
   a WRITE to production data, and the same class of ruling as the 1,825.

Held. Nothing written, no migration authored.

---

## 7. Method notes

- The transfer question was answered by reading the schema as BUILT
  (`information_schema`), not as modelled — the two can disagree.
- The collision count is the real one: a `GROUP BY … HAVING count(*) > 1` over
  the exact predicate the index would use, not an estimate.
- Read-only connection guard throughout; only host/port/db printed.
- Every count here states its population, per the rule landed this session.
  None of these figures include the five seeded demo rows except the 2,289
  total, which is the whole table and says so.
