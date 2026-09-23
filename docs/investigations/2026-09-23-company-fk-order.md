# The company FK purge order — what it covers, what it misses, and two ways to fix it

**2026-09-23.** Read-only. No deletes, no schema changes, no migration written.
Options are named with costs and **not chosen**.

**The headline is not the gap. It is that 85% of the rows in the blocking tables belong to
the tenants being KEPT, and only 244 belong to the ones being deleted.** A blanket delete
would destroy real seed data to remove a few hundred rows of litter.

---

## 1. Re-derived from `pg_constraint`

Every figure below was re-measured rather than inherited from the prior investigation.

```
purge statements                                    74
  DELETE target tables                              72
  UPDATE target tables                               2   (agent_schedules, customer_payments)
live tables in public schema                       492
purge targets that no longer exist                   0
FK constraints in the catalogue                   1176
tables referencing a purged table, unpurged, no CASCADE   327
  of those, non-empty                                77   holding 7,921 rows
children that DO cascade (for contrast)            113
```

The earlier figure of 7,184 rows was correct when taken; it is 7,921 now. Nothing was
deleted between the two readings — the suite churns these tables, which is the
repeatability finding showing up again. Both numbers are reported with what produced them.

**Zero ghosts.** No purge statement targets a dropped table, so the list has not rotted in
that direction. Its problem is omission, not staleness of what it names.

## 2. Ownership — measured, not asserted

Of the 77 non-empty blocking tables:

| | tables | rows |
|---|---|---|
| directly attributable (`company_id` / `tenant_id`) | 68 | 4,319 |
| need a join through a parent | 9 | 3,602 |

Within the 4,319 directly attributable rows:

```
belong to the five KEPT tenants     3,685   (85.3%)
belong to the 430 doomed companies    244   ( 5.6%)
neither — null or orphaned            390   ( 9.0%)
```

The two largest parent-join tables, attributed through their real FK columns (read from
`pg_constraint`, after two guessed column names failed):

```
workflow_run_steps            3,410 rows   kept 2,759   doomed   651
vendor_payment_applications      33 rows   kept    33   doomed     0
```

⚠️ **SO THE BLOCKING SET IS SMALL AND THE HAZARD IS LARGE.** The rows that actually block
the purge are the doomed ones — roughly **895** across everything attributed so far (244 +
651). The other ~6,400 are kept-tenant data sitting in the same tables, and a
table-level `DELETE` takes them too. The largest single casualty would be
`price_list_items` at **2,095 rows, every one belonging to a kept tenant**, followed by
`urn_products` (259 kept), `agent_anomalies` (256 kept), `intelligence_executions` (233
kept), `cemetery_plots` (160 kept).

That is the quantification the dispatch asked for, and it inverts the intuition: these
tables are mostly full of legitimate seed data, and the litter inside them is a minority.

### The seven that still cannot be attributed

`intelligence_prompt_versions` (103), `document_template_versions` (41),
`licensee_transfers` (4), `user_permission_overrides` (4, attributed: 4 kept),
`employee_profiles` (5, attributed: 5 doomed), `document_share_events` (1),
`document_shares` (1).

These have no single company-bearing parent — they hang off `users`, off documents, or off
two parents at once. Each needs a hand-written, reviewed predicate. **They are 155 rows and
they are the part of this that cannot be generated.**

## 3. The two remedies

The 327 split cleanly, and the split is the useful finding: **they do not need the same
fix.**

```
reference ONLY companies            147   -> schema-level ON DELETE CASCADE
reference other purged tables too   180   -> need ordering
```

### Option A — cascade the 147 at the schema level

An `r184`-style migration. That precedent is exact: `r184_tenant_column_company_fks`
states *"The remaining 20 tenant-scoped columns get a companies FK, ON DELETE CASCADE"*,
and `r183` did the same for `tenant_health_scores`. Twenty-one columns already went this
way.

**What it buys, and it is the only option that buys this:** each of the 147 stops needing
to appear in any list, generated or hand-written, forever. This is the removal criterion —
the wrong thing becomes unexpressible rather than discouraged. It reduces what has to be
correct instead of relocating it.

**Cost:** one migration over 147 constraints, each dropped and recreated. Mechanical, and
`op.create_foreign_key` with `ondelete="CASCADE"` is already the established shape.

⚠️ **WHICH OF THE 147 WOULD BE UNSAFE TO CASCADE — NOT ESTABLISHED, AND IT IS THE GATING
QUESTION.** A cascade is correct only where the child genuinely cannot outlive its company.
Candidates for *not* cascading, from their names, are the audit and ledger-shaped tables:
`audit_logs`, `document_template_audit_log`, `intelligence_prompt_audit_log`,
`licensee_transfers` (a transfer references two companies and may need to outlive one),
`platform_tenant_relationships` (same — it is the relationship, not one side's property).
Deciding this is a per-table judgment about retention, not a mechanical sweep, and this
investigation did not make it. **It is the work that has to happen before the migration is
written, and it is a larger job than the migration itself.**

### Option B — generate the order for the 180 from `pg_constraint` at runtime

The design is already proven at small scale: the helper's two UPDATE statements null FKs
before deleting, which is exactly the null-then-delete shape a generated order needs.

**Generated vs hand-maintained, which is the real decision:**

The failure that produced all of this was not ordinary staleness. Nobody forgot to update
the list — `quotes` gained an FK to `customers` and **no signal existed** that the list
needed changing. A generated order removes that failure mode entirely, because there is
nothing to forget.

But the two fail differently, and the difference matters more than the maintenance cost:

- **A hand-written list is wrong loudly.** `purge_test_companies` raised on `quotes` and
  deleted nothing. That is how this was discovered.
- **A generated order can be wrong quietly** — it completes, and deletes the wrong rows.
  Given §2, the wrong rows are overwhelmingly kept-tenant seed data.

⚠️ So the useful distinction is not generated-versus-listed. It is **generate the ORDER,
never generate the SCOPE.** The topological sort is a pure function of the catalogue and is
mechanically checkable: assert no cycles remain after the declared nulling, assert every
emitted table is reachable from `companies`, assert the emitted set covers every blocking
table. That has a right answer and a machine can confirm it. What must not be generated is
the `WHERE` clause: a predicate inferring ownership through a join is precisely where the
3,685 kept rows die. The 294 directly-attributable tables can carry a generated
`company_id = ANY(:ids)` safely, because that predicate is unambiguous. The 33 needing a
parent join — 155 rows — need hand-written predicates that a person has read.

**Validation available before committing to it:** run the generated order against the
existing hand-written list and diff them. Where they agree, the generator is validated
against a list that worked for years; where they disagree is the review surface, and it is
small enough to read — unlike the 399-table order itself.

### Option C — leave the order alone and narrow what creates the mess

Not asked for, recorded because §2 makes it defensible: 244 doomed rows across 68 tables
is a small enough population that per-fixture teardown, as 52 of the 283 company-creating
files already do, would keep it at zero without touching the order at all. This does
nothing for the 430 existing companies and is the cheapest thing that stops the growth.

## 4. The cycles, and how each is broken

A pure topological order **does not exist** — the graph has 8 cycles. Identifying them
changed the design, because most are not real obstacles:

| cycle | how it resolves |
|---|---|
| `documents` ↔ `intelligence_executions` | both FKs are `SET NULL` — self-resolving |
| `documents` ↔ `fh_cases` | `SET NULL` — self-resolving |
| `documents` ↔ `disinterment_cases` | `SET NULL` — self-resolving |
| `signature_envelopes` ↔ `documents` | `CASCADE` one way, `SET NULL` the other — self-resolving |
| **`companies` ↔ `users`** | **the real one.** `users.company_id → companies` is NOT NULL, `NO ACTION`; `companies.created_by` and `companies.modified_by → users` are nullable, `NO ACTION`. Broken by nulling the two nullable columns on `companies` first, then deleting `users`, then `companies`. |
| `companies.parent_company_id` self-ref | nullable — null it first |
| `users.created_by` / `users.modified_by` self-refs | nullable — null them first |

So: **three nullable columns on `companies` and two on `users` are the entire manual
breaking cost.** Everything else the schema already handles.

## 5. What the helper claims, against what it does

The docstring claims *"a single ordered list covers the union of tables the suites
touch"* — scoped to the suites, not the schema. That claim was true when written and
became false when a suite touched `quotes`.

CLAUDE.md said it *"encodes the FK-safe deletion order in one place"* — a completeness
claim about the schema, which was never true. **That is the line that was corrected**,
because it is the one a session read and trusted. The docstring's narrower claim is left
as written with the measured gap recorded beside it.

Helper last changed **2026-09-10**. `r183` and `r184` landed **2026-09-15**, `r185` on
**2026-09-22** — all after.

## 6. What this does not establish

- Which of the 147 are unsafe to cascade. Named as the gating question in §3; not decided.
- Ownership of 155 rows across seven tables with no single company-bearing parent.
- Whether the 390 null/orphaned rows are litter or legitimately company-less.
- Whether a generated order matches the hand-written one. The diff in §3 is proposed, not
  run.
