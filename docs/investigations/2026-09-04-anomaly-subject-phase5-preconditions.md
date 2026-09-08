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

> ### ⚠️ [CORRECTED 2026-09-08] TWO CLAIMS IN THIS SECTION ARE FALSE
>
> **(1) "The 1,825 do NOT block the index."** False. That was true only of a
> predicate bounded by `entity_id IS NOT NULL`. Under the grouping the 5b
> listener actually uses — NULLs MATCH — the 1,825 are **one colliding key**.
> A default unique index disagrees (NULLs distinct), which is exactly why 5c
> must use `NULLS NOT DISTINCT`; and once it does, they block it.
>
> **(2) The excess figure of 240.** Re-derived 2026-09-08 with the predicate
> declared: **2,077 excess rows across 11 keys** under the listener's grouping,
> **252 across 9 keys** under a default index's. The difference is exactly the
> 1,825. `WHERE resolved = false AND superseded_at IS NULL`, counts **include**
> the five seeded demo rows.

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

> ### ⚠️ [CORRECTED 2026-09-08] "5b's SUPERSEDE-ON-WRITE DRAINS THE BACKLOG" IS FALSE
>
> Measured: the drain reaches **56 of 2,077** excess rows. Supersede fires only
> on a NEW WRITE OF THE SAME KEY, so a live agent is necessary and **not
> sufficient** — if the agent stops emitting that key, its duplicates are never
> superseded. `expense_categorization` has run 1,322 times in seven days and
> written nothing.
>
> ⚠️ **And the rows it does not reach are NOT STALE, which this document also
> assumed.** All 1,825 `expense_no_gl_mapping` rows say `vehicle_expense` has no
> GL mapping, and **`vehicle_expense` is still unmapped for that tenant today**.
> The condition holds; only the reporting stopped. See §13.

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

---

## 8. 5a as authored — migration `r176`, NOT RUN against production

Per ruling: authored, gate-green, **held for James at his terminal.** Verified by
upgrade → downgrade → upgrade against local `bridgeable_dev` only.

- `tenant_id` — added nullable, backfilled from `agent_jobs`, set NOT NULL, indexed.
- `entity_id` — 36 → 255.
- `superseded_at` — nullable timestamptz.
- `ix_agent_anomalies_open` — a NON-unique index on the eventual key, so 5c's
  partial unique has something to build on without 5a asserting uniqueness.

⚠️ **No unique constraint. `test_the_5c_index_is_deliberately_absent` pins that**,
so a later reader cannot "finish the job" by adding it and discover the 240
duplicates through a failed migration.

### `tenant_id` is DERIVED, not asked for

Six production sites and thirteen test/seed sites construct `AgentAnomaly`. A
`tenant_id` each supplies is one each can get wrong, and wrong here files a row
under another tenant, which the supersede key would read as another tenant's
decision. A `before_insert` listener fills it from the job. A supplied value that
DISAGREES raises rather than being silently overwritten — the disagreement is a
real bug and the quiet fix would hide it.

Side effect worth having: none of the thirteen test/seed sites needed changing.

### The reader enumeration, which the ruling required first

Eleven filter sites, all moved to `AgentAnomaly.open_filter()`:

```
triage/engine.py                4  (cash_receipts, ar_collections,
                                    expense_categorization, aftercare queues)
widgets/anomalies_widget_service 3  (list + total_unresolved + critical_count)
note/counts.py                  1
agents/approval_gate.py         1
api/routes/agents.py            1  (resolved=false now means "still open")
                                +1 deliberate `resolved.is_(True)`
```

⚠️ **The two widget count chips are exactly the overstatement risk** — they feed
a badge. Left bare, they would have counted 240 machine-replaced rows as open
work against 11 real decisions.

**Pinned by a scanner, not a convention**:
`test_no_read_site_filters_on_resolved_alone` fails on any new bare filter, with
`resolved.is_(True)` allowed as the different question it is. Break-tested three
ways — a returning bare filter, an `open_filter` that checks only `resolved`, and
a derivation that overwrites instead of raising — each turning its own check red.

### Classifier output validated at the write site

`proposed_category` was `result.get("category", "other_expense")`, used verbatim,
and it BECOMES A SUBJECT. Now coerced to the 15-item vocabulary, out-of-vocabulary
values logged. The length hazard was the visible half; **the identity hazard is
worse** — a hallucinated spelling creates a subject naming nothing, and a second
spelling creates a second, which is `complete`/`completed` arriving through a
field nobody treated as a key.

---

## 9. ⚠️ Two things the enumeration turned up, neither fixed

**`anomaly_resolution_task`'s done-hook is dead.** At
`app/services/tasks/plugins/types/anomaly_resolution_task.py:67` it does
`if anomaly is not None and hasattr(anomaly, "is_resolved"): anomaly.is_resolved = True`.
**The model attribute is `resolved`.** `hasattr` returns False, so the branch
never runs — the hook loads the anomaly and does nothing, silently, with no
exception and no log. Its module docstring claims it "updates
AgentAnomaly.is_resolved=True via existing service path."

Not fixed, because fixing it is a **behaviour change**: completing such a task
would start resolving anomalies that today stay open. That is an
operator-visible change and deserves its own decision, not a ride-along in a
migration commit. It is the complete-machinery-behind-an-unprovisioned-entrance
shape with a `hasattr` guard making it undetectable.

**`tests/_tenant.py`'s docstring advertises an import that does not exist.** It
says `from tests._tenant import canonical_tenant`; the module exports
`make_canonical_tenant_fixture`. Cost one failed import. Expired premise —
correct when written, silent when it stopped being true.

---

## 10. The three deploy questions — answered, and one of them changed the migration

### Q1. The exact command — there isn't a standalone one, and that matters

`backend/railway-start.sh` runs `alembic upgrade head` **inside the deploy**,
under a Postgres advisory boot lock, **before uvicorn starts**, and fails the
deploy on error (R-3.1.3 fail-loud). So the production migration path is:

```
! git push origin main        # 8 commits; Railway deploys from main
```

There is no separate migrate step to run. `railway run … alembic upgrade head`
would technically work — it injects production's `DATABASE_URL` — but it would
apply the schema **while the deployed code is still the old code**, which is
precisely the failure Q2 turned out to be about. **The deploy path is the right
one; the ad-hoc one is the trap.**

### Q2. ⚠️ Yes it rides a deploy — AND THE QUESTION FOUND A DEFECT

Railway keeps the **old container serving while the new one boots and migrates.**
So there is a window in which the NEW SCHEMA is live and the OLD CODE is taking
traffic. The old code does not set `tenant_id` and has no `before_insert`
listener.

**As originally authored, r176 set `tenant_id NOT NULL`. That would have failed
every anomaly insert for the length of that window** — against
`expense_categorization` on a `*/15` cron plus the nightly agents.

**This is the same defect canonised earlier today**: a guard reasoned about in
isolation from who else is running. I reasoned about the migration and not about
the deploy choreography — the sample was "the schema after", the population was
"every writer during".

**Fixed as expand/contract.** r176 leaves `tenant_id` **nullable**; NOT NULL
moves to 5c, many deploys downstream of the listener. Correctness meanwhile does
not rest on the constraint — the listener fills it on every insert, and
`test_tenant_id_is_nullable_on_purpose_until_5c` pins the reasoning so a later
reader does not "tidy it up".

The deploy window itself is unchanged by r176: same rolling deploy, and the
~5-minute outage seen earlier today is a property of the deploy, not of this
migration.

### Q3. Reversible — verified against a POPULATED table, which is a different test

The earlier round-trip ran against an effectively empty table, which is exactly
the objection. Re-run against 68 pre-existing rows plus 7 seeded probe rows
across **two tenants**:

```
UPGRADE    74 rows backfilled, 0 NULL; every row's tenant_id == its job's
           a 70-char entity_id accepted (old column was 36)
DOWNGRADE  columns dropped, 75 rows intact, the 70-char subject survives
           entity_id deliberately left at 255 -- narrowing would FAIL on it
RE-UPGRADE 0 NULL, long subject still 70 chars
```

Probe rows removed afterward; `agent_anomalies` back to 68.

⚠️ **The one asymmetry, stated because it is not true forever.** Downgrade is
lossless *today* only because nothing writes `superseded_at` yet. **After 5b it
is not**: rolling back would destroy the record of which rows were superseded,
and every one of them would reappear as open work in every count. So the
downgrade is a safe escape hatch for 5a and stops being one the moment 5b lands.

⚠️ **And rollback has an order.** New code references `tenant_id` and
`superseded_at`, so a schema downgrade under new code breaks it. Roll back the
DEPLOY first, then the migration.

---

## 11. For 5c — make a wrong-tenant anomaly UNEXPRESSIBLE, not merely unlikely

**Proposed, proven locally, NOT applied anywhere.** Raised because the operator's
observation is exactly right: the tenant listener's failure mode is **silent**.
`tenant_id` is nullable until 5c, so a row filed under the wrong tenant — or
none — inserts cleanly, becomes somebody else's open work, and raises nothing.
Watching one night's run catches it once; a constraint catches it forever.

The listener already *raises* on a supplied tenant that disagrees with the job.
It cannot catch a tenant it DERIVED wrongly, because nothing cross-checks the
derivation. A composite foreign key does:

```sql
ALTER TABLE agent_jobs
  ADD CONSTRAINT uq_agent_jobs_id_tenant UNIQUE (id, tenant_id);

ALTER TABLE agent_anomalies
  ADD CONSTRAINT fk_agent_anomalies_job_tenant
  FOREIGN KEY (agent_job_id, tenant_id) REFERENCES agent_jobs (id, tenant_id);
```

**Proven against local `bridgeable_dev`, then reverted**: an insert naming a
tenant that is not the job's is refused with `ForeignKeyViolation`; the correct
tenant still inserts. That is the removal criterion applied to the arc's own
newest guard — *a validated field is a hole with a guard on it; a field the
database will not accept a wrong value for is not a hole.*

**Viability on production, re-derived rather than inherited** (read-only,
2026-09-08; 2,301 rows, **count includes the five seeded demo rows**):

| check | result |
|---|---:|
| anomalies whose `tenant_id` disagrees with their job | **0** |
| anomalies with a NULL `tenant_id` | **0** |
| orphaned `agent_job_id` | **0** |
| duplicate `agent_jobs.id` (the UNIQUE target) | **0** |

**Buildable today.**

⚠️ **AND THE LISTENER IS BYPASSABLE, WHICH THE FK IS NOT — demonstrated by
accident.** Seeding the 5c verification via raw SQL skipped both `before_insert`
listeners: `tenant_id` stayed NULL and two tenants' rows collapsed into a single
key. That is exactly the failure the composite FK prevents and the listener
cannot, produced without trying to produce it. A guard at the ORM layer is
simply absent for anything that does not go through the ORM — every
`db.execute(text(...))`, every migration, every `psql` session. It strengthens
the FK's case rather than being incidental to it: the listener is the ergonomic
half and the constraint is the load-bearing half.

⚠️ **It belongs with 5c's `NOT NULL`, and not before it.** A composite FK
defaults to `MATCH SIMPLE`, under which a row with ANY null in the key passes
unchecked — so on its own it would let a NULL-tenant row straight through. The
FK and the `NOT NULL` are one guard in two statements, and shipping the FK alone
would be a guard that looks complete and has a hole in exactly the case the
listener is most likely to produce.

⚠️ **And it is a production DDL change on a live table — James's**, like every
other write in this arc. Recorded here so 5c's dispatch can rule on it rather
than rediscovering it.

---

## 12. ⚠️ The drain covers 2.7% of the backlog — measured, and it inverts §5

**Read-only against production, 2026-09-08.** The operator asked whether
something in the duplicate set will fail to drain. It does, and it is almost all
of it.

```
colliding keys: 11        excess open rows: 2,077

  2,019  ⚠️ AGENT LIVE, KEY STALE  -> will NOT drain
     56  WILL DRAIN
      2  ⚠️ AGENT NOT RUNNING      -> will NOT drain
```

| anomaly_type | writer | excess | last emitted | agent last ran | verdict |
|---|---|---:|---|---|---|
| `expense_no_gl_mapping` | `expense_categorization` | 1,824 | 2026-08-31 | 2026-09-08 | stale key |
| `expense_classification_failed` | `expense_categorization` | 191 | 2026-08-25 | 2026-09-08 | stale key |
| `collections_critical` | `ar_collections` | 27 | 2026-09-07 | 2026-09-07 | **drains** |
| `collections_follow_up` ×2 | `ar_collections` | 29 | 2026-09-07 | 2026-09-07 | **drains** |
| `ar_balance_drift` ×2 | `ar_balance_reconciliation` | 2 | 2026-08-11 | 2026-08-11 | agent dead |
| `payment_unmatched_*`, `high_unmatched_ratio` ×4 | `cash_receipts_matching` | 4 | 2026-07-16 | 2026-09-07 | stale key |

⚠️ **THE MECHANISM, WHICH §5 ASSUMED AWAY.** Supersede fires only on a **new
write of the same key**. A live agent is necessary and **not sufficient**: if
the underlying condition has stopped holding, the agent never re-emits that key,
so its duplicates are never superseded. `expense_categorization` runs every 15
minutes and has emitted nothing since 2026-08-31 — the condition resolved and
the findings about it did not.

**So "self-healing" is true and much narrower than it sounded.** It heals what is
still recurring. Everything else is a fossil, and fossils are exactly what a
unique index trips over.

### ⚠️ And my own "240 duplicates" figure was wrong

It came from a query bounded by `entity_id IS NOT NULL`, which excluded the
1,825 NULL-subject `expense_no_gl_mapping` rows. Under the grouping the 5b
listener actually uses — `IS NOT DISTINCT FROM`, where NULLs match — those
1,825 are **one colliding key**, not excluded rows. The real figure is **2,077
excess rows across 11 keys.** Sixth instance in this arc of a figure bounded by
its query rather than by the thing.

### ⚠️ A semantic disagreement 5c must resolve

The 5b listener treats NULL subjects as EQUAL (`IS NOT DISTINCT FROM`). **A
default PostgreSQL unique index treats them as DISTINCT.** Verified on
PostgreSQL 16.13: a plain `UNIQUE (a, b)` accepts two `('t', NULL)` rows;
`UNIQUE (a, b) NULLS NOT DISTINCT` refuses the second.

**5c must use `NULLS NOT DISTINCT`**, or the two halves of the guard disagree
about what a duplicate is — the listener refusing to write one while the index
permits it, which is worse than either behaviour alone.

⚠️ It also means the 1,825 **do** block the index once the predicate matches the
listener. §4 said they were excluded and buildable-around; that was true of the
`entity_id IS NOT NULL` predicate and is **false** of a predicate that agrees
with 5b.

### What this makes 5c

Not "add the index after the drain." **The drain removes 56 rows. A disposition
ruling has to remove ~2,021 before the index can build** — dominated by the
1,825 orphans, which were already held. So the orphans stopped being a
housekeeping item and became 5c's blocking dependency.

Held, unchanged: every row of that disposition is a production write.

---

## 13. Phase 5c Part 1 — the downstream check, and two STOPs

**Read-only against production, 2026-09-08.** Every count below states the
`WHERE` clause that produced it, because the "240" was wrong precisely for
lacking one.

### Readers — enumerated, not inherited

The 5a pass found eleven **filter** sites. This is the wider question, so it was
re-enumerated from scratch: **33 modules** name `AgentAnomaly` or
`agent_anomalies`. Of those, **13 mention only** (comment or import), **6 write**,
and **14 read**. Classified by whether they use `open_filter()` or restate:

| reader | predicate | effect of the mark |
|---|---|---|
| `triage/engine.py` ×4 (queues) | `open_filter()` | correct — queues shrink |
| `widgets/anomalies_widget_service` ×3 (list + 2 count chips) | `open_filter()` | correct |
| `note/counts.py` | `open_filter()` | correct |
| `agents/approval_gate.py` | `open_filter()` | correct |
| `api/routes/agents.py` (`resolved=false`) | `open_filter()` | correct |
| `api/routes/agents.py` (no filter) | **none** | returns superseded rows unlabelled |
| `agents/tax_package_agent.py:554` | **restates**, no state filter at all | blind to the mark |
| `triage/ai_question.py:533` | **restates**, no state filter | blind to the mark |
| 6 adapter/lookup sites | by `id` | unaffected |

**Nothing counts, bills or reports against superseded rows as such** — because
**nothing reads `superseded_at` except `open_filter()`**.

⚠️ **`AgentAnomalyResponse` does not expose `superseded_at`.** No API consumer
can tell a replaced row from a live one. The two restating readers and the
unfiltered route are blind for the same reason.

⚠️ **The two restating readers are not affected by THIS mark** — measured: they
scope to `month_end_close` job ids, and the marked population is
`expense_categorization` / `cash_receipts_matching` / `ar_balance_reconciliation`.
**No overlap.** They are still wrong post-5b for agent-driven supersedes, which
is a smaller live defect and is not this dispatch's to fix.

### The population, every count with its predicate

| what | `WHERE` | n | demo rows |
|---|---|---:|---|
| whole table | `true` | 2,301 | **includes** the 5 |
| the seeded demo rows | `description IN (…5 literals…)` | 5 | — |
| open | `resolved = false AND superseded_at IS NULL` | 2,096 | includes |
| already superseded | `superseded_at IS NOT NULL` | 0 | — |
| excess, **listener** grouping | open, `GROUP BY tenant,type,etype,eid HAVING count(*)>1` | **2,077** over 11 keys | includes |
| excess, **default-index** grouping | same + `etype IS NOT NULL AND eid IS NOT NULL` | **252** over 9 keys | includes |

The two groupings differ by exactly **1,825** — the NULL-subject set.

---

### ⚠️ STOP 1 — the rows are not stale, and staleness was not establishable

The dispatch's ruling assumed a stale population. **It is not stale.**

My first attempt to establish staleness compared each key's last write to the
last write of its **type**. Every key returned `key_last == type_last`, so the
test could not separate *"this condition stopped holding"* from *"this agent
stopped emitting anything"* — the conflation the STOP line names, reproduced by
the check written to avoid it.

Establishing it from the condition instead: all 1,825 rows say

> Category **`vehicle_expense`** has no GL account mapping for this tenant.

and `tenant_gl_mappings` has **zero rows** for `platform_category =
'vehicle_expense'`, for that tenant or any other. **The condition holds today.**
The agent went quiet on 2026-08-31 because it finds no uncategorized lines to
classify, so it never reaches the mapping check — it has run **1,322 times in
seven days reporting `anomaly_count = 0` and writing 0 rows**, internally
consistent and therefore not silently broken.

**So marking them "stale" would delete the only record of a live problem.**

⚠️ **A larger defect found underneath, out of scope and James's.** The classifier
emits 15 platform categories; this tenant has 13 mapped; **the overlap is one**
(`other_expense`). Fourteen of fifteen are unmappable by construction — and
`delivery_costs` (classifier) vs `delivery_cost` (mapped) is the
`complete`/`completed` shape a third time, in a third table.

### What the authored script does instead

`backend/scripts/mark_duplicate_anomalies_superseded.py` — **dedup, not
staleness.** Keeps the **newest** open row per key, supersedes the older ones.
That needs no staleness claim: an older duplicate genuinely *was* replaced by a
later occurrence of the same finding, which is the rule 5b already applies
forward. Every distinct condition stays visible as exactly one open row — 1,825
copies of one sentence become one copy of that sentence — and it is precisely
what the index needs and no more.

Predicate-based, never an id list. Order-independent with respect to tonight's
drain: whichever runs first, the end state is identical. Writes `superseded_at`
alone. Dry-run by default.

**Verified against a local database seeded with representative rows** through the
ORM — a first attempt seeded via raw SQL, which **bypasses both `before_insert`
listeners**, left `tenant_id` NULL and collapsed two tenants into one key. (That
is worth keeping: the listener guard is bypassable by raw SQL; the proposed
composite FK would not be.) Eleven assertions, all passing: single-row keys
untouched, resolved rows untouched, newest kept per key including the
NULL-subject shape, no cross-tenant collapse, and `resolved` / `resolved_at` /
`resolution_note` never written. Before → after: 21 colliding keys → **0 under
both groupings**.

**Reversal verified on the populated table, not an empty one**: 26 rows marked,
26 restored by `UPDATE … SET superseded_at = NULL WHERE superseded_at = '<T>'`,
nothing else moved. Cost is the UPDATE. It depends entirely on **T being
recorded**, so the script now prints it prominently.

---

### ⚠️ STOP 2 — `superseded_at` alone cannot distinguish a bulk mark

The only separator is an **artifact**: this script writes one transaction
timestamp to every row, while the listener stamps each row with its own
`datetime.now()`. It works, and it is inference from a coincidence of
implementation rather than a recorded fact. In three months, *"what did the
machine replace"* returns ~2,000 rows no machine replaced, and nobody will know
to exclude a magic timestamp.

Two closures, both James's, **neither taken**: accept the shared timestamp and
write it into STATE.md so the exclusion is discoverable; or record the operation
in `audit_logs` so the discriminator is a row somebody wrote. A
`superseded_reason` column is the honest schema fix and was **not** added,
because adding one unilaterally is what the dispatch forbade.

**The script should not run until this is settled.**

---

## 14. The `audit_logs` question, answered — it fits, and the vocabulary exists

STOP 2 asked whether the bulk mark belongs in `audit_logs`, which depended on
what that table is currently for and whether anything reads it. Both established
read-only, 2026-09-08.

**It is read, by three surfaces.** `GET /api/v1/audit` + `/audit/{id}` is a
tenant-scoped viewer filterable by user / action / entity_type / entity_id /
date; `vault_accounting` reads `period_locked` / `period_unlocked` rows for the
Periods & Locks "Recent Activity" panel; `audit_service.get_audit_log` fetches
one by id. So a row written here is not written into a void.

**What it holds in production: 4,310 rows, 2026-05-07 to 2026-09-07, across
five distinct (action, entity_type) pairs.**

| action | entity_type | n |
|---|---|---:|
| `task.task_created` | `task_details` | 2,343 |
| `login` | `session` | 1,922 |
| `created` | `invoice` | 28 |
| `created` | `customer_payment` | 14 |
| `created` | `vendor_bill` | 3 |

⚠️ **There are ~90 `log_action` call sites in the code and five pairs in the
data.** Most of that vocabulary has never fired here. Stated as measured, not as
a defect — `period_locked` has a writer at `vault_accounting.py:247` and zero
rows because no period has ever been locked, which is an unexercised path rather
than a broken one.

### The shape fits, with three consequences

**`entity_type="agent_anomaly"` already exists in this vocabulary.**
`anomalies_widget_service.py:209` writes `action="anomaly_resolved"`,
`entity_type="agent_anomaly"`, `entity_id=<the row>`. Auditing an anomaly state
change is precedented, so the bulk mark is an addition to an established
vocabulary rather than a new one.

1. **`company_id` is NOT NULL**, and the mark spans three tenants. The operation
   becomes **three rows**, one per tenant, not one row naming the operation.
2. **`entity_id` is a single `String(36)`** and cannot name 2,077 rows. It would
   be NULL — precedented, since 1,922 login rows already have a NULL entity_id —
   with the superseding timestamp and per-type counts in `changes` (Text/JSON).
   **That is the discriminator STOP 2 needs**: a row somebody wrote, naming the
   timestamp, rather than a pattern somebody has to notice.
3. **`user_id` would be NULL.** Also precedented — NULL on 2,355 of 4,310 rows.

⚠️ **One thing James should decide rather than inherit: the viewer is
TENANT-FACING.** `GET /api/v1/audit` scopes to `current_user.company_id`, so a
tenant admin would see a maintenance operation on their data appear in their own
audit log. That is arguably correct — it is their data and the honest thing is
to say so — but it is a visible change to a surface they read, and it is a
decision rather than a detail.

> **[SUPERSEDED 2026-09-08 — the closure was ruled and is implemented below.]**
> Original wording: *"Still not written. The question is answered; the closure is
> James's."*

---

## 15. STOP 2 closed — the audit write, tenant-visible, three rows

**Ruled: write it, tenant-visible.** The reasoning is worth keeping because it
inverts what looked like a privacy question. **The visibility is the feature.**
An audit log a tenant reads is a record of what happened to their data, and a
platform operation touching their rows is something that happened to their data.
Omitting it would make the log a partial record that reads as a complete one —
the same defect as a gate that selects and reports as coverage. And a tenant
admin who later finds 2,077 rows superseded with nothing in the log has been
handed a mystery; the row is the answer to a question they would otherwise have
to ask.

### The action name names the actor

```
action      = platform_maintenance.anomalies_deduplicated
entity_type = agent_anomaly     entity_id = NULL     user_id = NULL
```

⚠️ **Deliberately not a sibling of `anomaly_resolved`.** That existing entry
means *a person decided something*. This resolved nothing, and a reader who
conflates the two will believe decisions were made on their books. The
`platform_maintenance.` prefix says Bridgeable operated on their data rather than
their own system doing routine work. 43 characters against a `String(50)` column.

### `changes` is written for someone who has never heard of this arc

It is the only explanation they will ever get, so it leads with plain language
rather than counts: what was done, why it was done, what they may notice, that
**nothing was resolved, deleted or edited**, who performed it, and that it is
reversible. The counts (`duplicate_rows_retired`,
`distinct_findings_still_open`, `retired_by_finding_type`) come after the
sentences, and `marked_at` carries the timestamp.

⚠️ **`marked_at` IS THE DISCRIMINATOR STOP 2 ASKED FOR** — a row somebody wrote,
naming the operation, rather than a shared-timestamp pattern somebody has to
notice. The implementation coincidence is still there; it is no longer what the
answer depends on.

### Verified end to end against a local populated database

4 rows superseded across 2 tenants; **one audit row per tenant**; action,
entity_type, entity_id and user_id as above; the payload carrying all nine keys.
**Tenant scoping confirmed through the real read path** —
`audit_service.get_audit_logs` returns each tenant exactly one row and not the
other's. **Reversal clean**: 4 anomalies un-superseded, 2 audit rows deleted, 0
residue. Both reversal statements are printed by the script at run time.

### Ships with no reader today, which is the argument for getting it right now

Nobody is using the platform. The first tenant to read this log reads it after
the fact, so there is no iteration available — the wording is the deliverable,
not a first draft.

**The script is now runnable. It is James's to run**: three tenants,
`superseded_at` only, one open row surviving per key.

---

## 16. Where the dedup runs from — and it is not the migration answer

Asked before anyone runs anything, because *"deploy is the migration path"* was
established earlier and generalising it here would be wrong.

**The script runs LOCALLY against the production connection. No deploy, no push,
no deploy window.** It imports nothing from `app/` — only `sqlalchemy`, and
`DATABASE_URL` from the environment — so there is no deployed code for it to
depend on. Verified 2026-09-08 by running its dry-run against production.

```
cd backend
railway run --project ad95792e-6625-4bf5-ad61-ead9c291bdf9 \
  --environment production --service SunnycrestERP \
  .venv/bin/python -m scripts.mark_duplicate_anomalies_superseded          # rehearse
railway run --project ad95792e-6625-4bf5-ad61-ead9c291bdf9 \
  --environment production --service SunnycrestERP \
  .venv/bin/python -m scripts.mark_duplicate_anomalies_superseded --apply  # write
```

### What the rehearsal returns today, measured

```
open rows                                             2,096
colliding keys (listener grouping, NULLs MATCH)       11   excess 2,077
colliding keys (default-index grouping)                9   excess   252
rows this would supersede                             2,077   -> 19 left open

expense_no_gl_mapping         1,824      ar_balance_drift            2
expense_classification_failed   191      payment_unmatched_stale     2
collections_follow_up            29      payment_unmatched_recent    1
collections_critical             27      high_unmatched_ratio        1
```

Counts **include** the five seeded demo rows.

⚠️ `collections_*` still shows 56 because tonight's `ar_collections` run has not
happened. Either order is fine — whichever runs first, the end state is the same.

### ⚠️ Three cautions that differ from the migration case

1. **What runs is the local working tree**, not a deployed artifact — the exact
   inverse of a migration, where the deployed code is fixed at deploy time. The
   tree must be the intended commit, and an edit changes what the next run does.
2. **`--apply` drops the read-only connection guard** the dry-run applies. The
   flag is the only thing between a rehearsal and a write.
3. **It is a local process writing to production**, adjacent to CLAUDE.md §7's
   *never point local `DATABASE_URL` at Railway production*. `railway run`
   injects into that one subprocess and writes no `.env`, so the letter holds —
   but the **read** form is what this session has used throughout, and a
   **write** through the same path is a different act, taken deliberately.

---

## 17. Expected end state — written down BEFORE the run, so the check is a diff

Measured read-only 2026-09-08, immediately before handing over. Recorded here so
verifying the run is a comparison against a stated prediction rather than a
judgement made afterwards against nothing.

```
rows superseded                 2,077
rows left open                     19
audit_logs rows written             3      one per tenant WITH duplicates
```

Per tenant, rows retired:

| tenant | anomalies (all) | retired |
|---|---:|---:|
| `090e7eeb-…` | 2,274 | 2,056 |
| `f60ef8de-…` | 18 | 17 |
| `36fe9f40-…` | 9 | 4 |

⚠️ **Three audit rows, and the reason is worth stating** because the script
writes one per tenant **with duplicates**, not one per tenant with anomalies.
Those happen to be the same three here — checked rather than assumed, since a
run producing one row where three were expected would read as a scoping failure.

⚠️ **These figures move if `ar_collections` fires first.** Its nightly run
supersedes its own 56 duplicates, after which `collections_*` drops out of the
retired set and the totals fall by that much. **The end state is identical either
way** — one open row per key — only the attribution differs. A smaller number
after a nightly run is not a discrepancy.

Confirm afterwards with `scripts/verify_supersede_drain.py`, whose checks 4a and
4b cover exactly this: no key holding more than one open row, and the audit rows
present, one per tenant, none filed against a tenant whose anomalies were never
touched.
