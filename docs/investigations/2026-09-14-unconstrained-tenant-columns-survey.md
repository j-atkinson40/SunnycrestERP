# The 20 unconstrained tenant columns — survey

**2026-09-14. Read-only, before the dispatch.** Readings timestamped; this population
changes as the suite runs.

---

## ⚠️ The partition in the brief would have been wrong

The dispatch anticipated scoping this as **14 cheap (empty) + 6 needing checks
(populated)**. That is not the seam. Measured:

| | count | |
|---|---|---|
| **leaf tables** | **19** | nothing references them — r183's reasoning applies unchanged |
| **non-leaf** | **1** | `platform_incidents`, two referrers, both `ON DELETE NO ACTION` |

**Leaf-vs-not cuts across empty-vs-populated entirely.** `agent_anomalies` has 206 rows and
is a leaf; `ai_agent_runs` has 0 rows and is also a leaf. The expensive question is
referrers, and only one table has any.

⚠️ The class is **20, not 21** — `tenant_health_scores` left it at r183.

---

## ⚠️ One systemic cause, not twenty instances

**Zero of the 20 declare a foreign key in the ORM.** Not one. The database is not out of
sync with the models; the models never declared it either.

So this is not migration drift and not twenty independent oversights — it is a convention
that wrote `Mapped[str] = mapped_column(String(36))` for a tenant reference, repeatedly,
across 14 models. Six of the 20 have **no model at all**.

A corollary: fixing this class is a model change plus a migration, or the next table added
by the same convention rejoins it.

---

## What each column actually is

All 20 are `character varying(36)`, matching `companies.id`. There is no type barrier.

⚠️ An earlier pass of this survey reported them as `character(36)` and hypothesised that
type was the common cause. **That was a display bug in the probe** — `"character varying"`
truncated to `"character"` with the length appended. Nothing in the schema said it.

Value shapes were checked and the check was discarded as useless: a uuid-shape test flags
150 of `agent_anomalies`' 206 rows as "not a company id", but they are `staging-test-001` —
the seeded tenant, whose id is not a uuid. **The orphan check is the only predicate that
discriminates**, and it needs no name or shape assumptions.

---

## ⚠️ Constraining one table DISPLACES the leak; it does not close it

This is the finding that most changes the class item's shape, and it arrived by doing it.

r183 constrained `tenant_health_scores`. Two tests in `test_responders.py` had been passing
a fabricated `tenant_id` into an incident whose responder then wrote a health score, so they
started failing. The fix gave them a real company and deleted it in teardown.

**Measured immediately afterwards: +2 orphaned `platform_incidents` rows per run of that
file.** The company was deleted; the incident was not; `platform_incidents.tenant_id` has no
FK, so nothing cascaded.

Then it broke its own test: with enough accumulated `infra` incidents the responder
escalates rather than resolving, and `test_infra_probe_resolves` began failing on state its
own fixture had left.

**The producer is not per-table.** It is a shared shape — *a test creates a company, writes
a child row, deletes the company* — and **every unconstrained child of that company inherits
the orphan.** Constrain one table and the litter moves to the next unconstrained sibling.

Fixed by deleting notifications → incidents → company in FK order
(`platform_notifications.incident_id` is `NO ACTION` and raises otherwise). Verified: 0
orphans, stable across repeated runs.

---

## Per-table, at 2026-09-14 ~19:15 UTC

| table | col | rows | leaf | note |
|---|---|---|---|---|
| `activity_log` | tenant_id | 11 | ✓ | |
| `agent_anomalies` | tenant_id | 206 | ✓ | ids include `staging-test-001` |
| `ai_agent_runs` | tenant_id | 0 | ✓ | no model |
| `ai_company_insights` | tenant_id | 0 | ✓ | **no model, no reference in app/ or scripts/** |
| `ai_name_suggestions` | tenant_id | 0 | ✓ | |
| `ai_pattern_alerts` | tenant_id | 0 | ✓ | |
| `ai_rescue_drafts` | tenant_id | 0 | ✓ | no model |
| `ai_upsell_insights` | tenant_id | 0 | ✓ | no model |
| `cash_flow_forecasts` | tenant_id | 0 | ✓ | **no model, no reference in app/ or scripts/** |
| `company_migration_reviews` | tenant_id | 0 | ✓ | |
| `duplicate_reviews` | tenant_id | 0 | ✓ | no model |
| `extension_widgets` | tenant_id | 0 | ✓ | |
| `legacy_proof_photos` | company_id | 0 | ✓ | |
| `legacy_proof_versions` | company_id | 0 | ✓ | |
| `order_personalization_photos` | company_id | 0 | ✓ | |
| **`platform_incidents`** | tenant_id | 514 | **✗** | self-ref + `platform_notifications.incident_id`, both `NO ACTION` |
| `platform_notifications` | tenant_id | 201 | ✓ | **all 201 rows have `tenant_id` NULL** |
| `ponder_engagement` | company_id | 11 | ✓ | |
| `user_ai_preferences` | tenant_id | 0 | ✓ | |
| `user_widget_layouts` | tenant_id | 2 | ✓ | |

All at **0 orphans** as of this reading, after the `test_responders` fix. That is a state,
not a property — see above.

---

## The producer, measured — and a correction to how I framed it

**Question asked:** is the create-and-delete pattern a shared helper (fix it once) or
independent copies (needs a guard)?

**Answer: both, roughly evenly.** 98 test files delete a company:

| | files |
|---|---|
| via the shared `purge_companies_by_slug` | **51** |
| via a hand-rolled `DELETE FROM companies` | **42** |
| both | 2 |

⚠️ 302 files *create* a company, but creation is not the producer — the COMPANY LITTER
tripwire proves companies do not net-leak, and `make_canonical_tenant_fixture` reuses the
canonical tenant rather than making one. **Deletion is the producer**, because deleting a
company is what strands its unconstrained children.

### The shared half does not help

`purge_companies_by_slug` issues DELETEs against **72** tables. Of the 20 unconstrained
tables it covers exactly **one** — `activity_log`. Nineteen are absent.

That is not an oversight anyone made recently. The helper's own docstring says it: *"of 387
tables with a FK path to companies, this helper covered 58 … ⚠️ THE OTHER 322 ARE STILL
UNCOVERED. This helper is a hand-maintained list over a 387-table surface, and it fails on
whichever table a new test first populates — silently."*

So fixing the helper is not the producer fix either. It would need the 20 added, and it
re-drifts when table 21 appears.

### ⚠️ CORRECTION TO THE SECTION ABOVE

The earlier text here said *"constraints alone do not close this class."* **That is true of
a PARTIAL application and false of a complete one**, and the distinction matters for the
dispatch.

What I measured was displacement *within* the unconstrained set: `tenant_health_scores` got
a constraint, `platform_incidents` did not, and the litter moved between them. But an orphan
can only land in a table with **no** constraint. Constrain all 20 with `CASCADE` and
deleting a company cascades everywhere — there is nothing left to displace to.

**So the constraint half IS the producer fix, provided it is applied to the whole class.**
What survives it is not a second project but a single residual: **table 21**, added under
the same ORM convention that produced these twenty.

### Which makes the durable piece a guard, not a fix

A test asserting that every `company_id`/`tenant_id` column has a foreign key to
`companies.id` would make table 21 impossible to add silently — and it is the same shape as
the ratchets already in this codebase. It also subsumes the hand-maintained helper's problem
rather than inheriting it.

Not proposed as a decision; it is what the measurement points at.

⚠️ **Probe defect, recorded.** A first pass extracted the helper's table list with
`"([a-z_]+)"` and concluded it covered **none** of the 370 FK'd tables — impossible for a
helper that works. The list is a sequence of `"DELETE FROM <table> WHERE …"` strings, so the
regex matched whole statements. Re-extracted with `DELETE FROM\s+([a-z_]+)`. Third probe
defect in this survey, and the second caught by a result being too strong rather than wrong.

## Questions the dispatch will need to answer

1. **`platform_incidents` is the only hard one.** CASCADE on its `tenant_id` deletes
   incidents, which then hit two `NO ACTION` referrers and raise. Either those become
   CASCADE too, or this table takes a different rule.
2. **Two tables have no model and no caller.** `ai_company_insights` and
   `cash_flow_forecasts` are created by a migration and referenced nowhere. Constraining a
   table nobody writes is work; dropping it is a different decision.
3. **The producer needs fixing or the class re-forms.** Constraints stop orphans in the
   constrained table; they do not stop fixtures deleting companies out from under
   unconstrained children. `platform_notifications.tenant_id` is entirely NULL today, which
   means it is not yet exposed — not that it is safe.
4. **The ORM convention is the root.** Twenty columns, zero declarations.
