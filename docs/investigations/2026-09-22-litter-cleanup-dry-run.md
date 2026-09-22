# Litter cleanup — two dry runs, and the namespace that guarantees recurrence

**2026-09-22.** Read-only. **Nothing applied.** Dry-runs for the two litter classes, plus
the enumeration behind the namespace proposal. Part 2 (tightening the tripwires) is not
started — it waits on authorisation to clean.

**No STOP line was triggered.** Both predicates are provenance-based and neither reaches a
row it cannot account for.

---

## 1. `platform_users` — predicate from the minting code

### What the minting code writes

Twenty-five test files construct `PlatformUser`. Not five — the earlier figure came from
grepping one email shape rather than the constructor.

Every one writes an address on a **`.test` TLD**: twenty-four use `@bridgeable.test`, one
(`test_verticals.py`) uses `@verticals.test`. The local parts vary widely — `platform-`,
`p-`, `plugin-reg-`, `openapi-test-`, `studio-inv-`, `platform-class-`, `platform-dl-`,
`platform-chrome-`, `platform-substrate-`, `platform-typography-`, `saw-`, `saw-t-`, `fv-`,
`icon-`, `plan-a-`, `plan-b-`, `moc2b-`, `taskedit-`, `trig-`, `p1-`, `r5-platform-`,
`platform-comp-`, `e2e-test-`.

**So the predicate is the domain, not the local part.** `.test` is RFC 6761
reserved-for-testing, and CLAUDE.md §7 already records that `email-validator` — the library
Pydantic's `EmailStr` uses — *rejects* it, which is precisely why the demo seeds were moved
to `.example.com` in R-1.6.10. A real platform user cannot hold a `.test` address, because
the validator would refuse it at the boundary.

That is provenance, not pattern-matching: the rows are identifiable as test-created by a
property the production path cannot produce.

### Dry run

```
platform_users total                7790
would delete  (email LIKE '%.test') 7786
would keep                             4
```

The four kept, in full, all `role=super_admin`:

```
admin@bridgeable.com
dev-admin@bridgeable.internal
dev-moc@example.com
shell-witness@example.com
```

**STOP check: no kept row matches the predicate, and no row matching the predicate is a real
platform user.** The two `@example.com` rows are the reserved-for-documentation domain and
are dev accounts, not test-run debris — they are kept because the predicate does not reach
them, which is the conservative outcome rather than a judgment call.

### ⚠️ Two corrections to figures in the committed investigation (488967c4)

Both made my own risk estimate wrong, in the same direction — too alarming.

**The population was over-counted.** I reported "4,483 test-pattern rows" using
`platform-%@bridgeable.test`. That prefix over-matches: it swallows `platform-class-`,
`platform-dl-`, `platform-chrome-`, `platform-substrate-`, `platform-typography-` and
`platform-comp-`, which are *separate* namespaces that do not collide with the bare one.
The actual bare colliding namespace, by exact regex `^platform-[0-9a-f]{6}@bridgeable\.test$`,
holds **3,707** rows.

**The keyspace was wrong.** The suffix is `uuid.uuid4().hex[:6]` — **hexadecimal**, so the
space is 16⁶ = 16,777,216, not the 10⁶ I assumed from "six-digit".

Corrected collision probability, 3,707 resident over 16⁶:

| inserts in a run | at least one collision |
|---|---|
| 10 | 0.22% |
| 50 | 1.10% |
| 200 | 4.32% |

⚠️ **The conclusion survives and the arithmetic did not.** The rate is ~14× lower than I
reported and still rises monotonically with every run, still has no upper bound, and still
produced a real failure. But the committed figures (0.45% / 20% / 59%) are wrong and should
not be quoted.

A consistency check that the shapes are understood rather than assumed: the grouped prefix
scan reports 4,467 rows under bare `platform-<suffix>@…`, against 3,707 for the exact
bridgeable.test regex. The difference is **760**, which is exactly the `verticals.test`
row count — the grouping spans both domains. The two numbers agree.

## 2. `companies` — provenance from the seed code

### The five, each identified by what creates it

| slug | provenance |
|---|---|
| `testco` | `scripts/seed_staging.py:53` — `COMPANY_SLUG = "testco"` |
| `hopkins-fh` | `scripts/seed_fh_demo.py:1384` — slug aligned to canonical docs |
| `st-marys` | `scripts/seed_fh_demo.py:1442` — same |
| `sunnycrest` | `scripts/seed_fh_demo.py:1456` — **queried, not created**; the production tenant, which the FH seed looks up and skips if absent |
| `default` | ⚠️ **no creator found** in `app/` or `scripts/` |

⚠️ **`default` (Default Company, 2026-03-25, `vertical=None`) has no established
provenance.** It predates every other row, nothing in the tree is recorded as creating it,
and it is kept on the conservative side of the STOP line: the rule forbids *deleting* what
cannot be identified by provenance, and keeping an unattributed row breaks nothing. It is
flagged rather than resolved — finding its author is a separate task.

### Dry run

```
would delete   440 companies
would keep       5
child rows      2148   across 29 tables   (LOWER BOUND)
```

Largest: `roles` 622, `users` 449, `company_modules` 256, `tasks` 78, `audit_logs` 55,
`vault_items` 36, `vaults` 25.

**2 of the 74 purge statements are not a plain `DELETE FROM <table> WHERE …` shape** and
could not be converted to a count, so 2,148 is a floor.

⚠️ **`platform_users` is not among the 74.** The company purge would not touch it even
after the cleanup; it needs its own statement, which is the omission that let 7,786 rows
accumulate.

### ⚠️ The company count moved between two measurements in this session

`435` when the tripwire investigation was written; `445` now. One full-tree run separates
them. That is the repeatability finding demonstrating itself inside the document that
records it — a figure taken before a gate run and quoted after one is a reading of a
different world. Both numbers are stated with what produced them rather than reconciled.

## 3. The namespace — why more digits does not fix it

### Enumeration

Twenty-five files construct `PlatformUser`. **Six share one namespace**, the bare
`platform-{suffix}@bridgeable.test`:

```
test_component_configurations_phase3.py        ← the file that failed
test_edge_panel_inheritance_admin_api.py
test_focus_template_inheritance_admin_api.py
test_platform_themes_phase2.py
test_themes_tenant_phase_r25.py
test_workflow_templates_phase4.py
```

The other nineteen each mint into their own prefix and therefore collide only with
themselves — smaller populations, same unbounded shape.

**None of the twenty-five deletes what it creates.** `platform_users` appears in no purge
statement and in no tripwire.

### Why the suffix is the wrong lever

A random suffix drawn from a fixed space into a table that is never emptied has a collision
probability that is a function of accumulated rows. That function only increases. Widening
16⁶ to 16¹² moves the failure years out and changes nothing structural — the same graph with
a gentler slope, and no bound at any point.

The variable that should be bounded is **how long a name has to stay unique**, not how many
values it is drawn from. Today it must stay unique against every row any run has ever
written. It only needs to stay unique within its own run.

### Proposal — a per-run namespace, not a wider one

1. **One run id per pytest session.** A session-scoped fixture in `tests/conftest.py`
   computes it once — `uuid4().hex[:8]` is ample when it only has to be unique against
   concurrently-running sessions, of which there is normally one.
2. **Every minted identifier carries it**, e.g. `platform-{run_id}-{suffix}@bridgeable.test`.
   The 25 files change one f-string each; the prefixes they already use are kept, so
   per-file intent survives.
3. **Teardown keys on it**, not on a name pattern: a session-scoped finaliser deletes
   `WHERE email LIKE 'platform-{run_id}-%'`. It cannot over-reach into another run's rows or
   into a real user, because the run id is not guessable and not shared.
4. **The tripwire becomes absolute and meaningful** — after teardown, zero rows should carry
   this run's id, which is a check on *this run's* behaviour rather than on the table's
   history.

What it would take: one fixture, twenty-five single-line edits, one finaliser, one purge
statement. The risk is missing a file, which the absolute tripwire would then catch — the
guard and the fix reinforce each other rather than overlapping.

⚠️ **Not implemented.** Reported for a decision, per the dispatch.

⚠️ **Order matters.** Per-run teardown removes only rows created *after* it ships. The 7,786
already resident are unreachable by it and still need the §1 cleanup. Namespace first would
leave the existing debris and the existing collision rate untouched.

## 4. What this does not establish

- Who creates the `default` company.
- Whether any of the other nineteen prefixes has accumulated enough rows to be near its own
  threshold. Only the bare namespace was measured against the failure that occurred.
- Whether the two unconvertible purge statements would delete rows the count missed.
