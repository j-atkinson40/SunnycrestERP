# The COMPANY LITTER tripwire reports on a clean database and goes quiet on a dirty one

**2026-09-22.** Read-only. Establishes the tripwire's condition from the code, enumerates
every session-level tripwire, reports what the right condition would be, and dry-runs the
cleanup. **Nothing was changed and nothing was applied.**

---

## 1. The condition, from the code rather than the message

`backend/tests/conftest.py:203`, `_company_litter_tripwire`:

```python
after = _company_count()
if after is not None and after > before:
    pytest.fail("COMPANY LITTER: the test session started with ...")
```

The condition is **`after > before`** — a delta against the run's own starting point. The
message says "were created without teardown", which reads as a statement about the database.
It is a statement about the run.

Two consequences follow, and the second is worse than the one that prompted this.

**It goes quiet once the rows exist.** A run that leaks reports; the next run starts from the
leaked state, and anything already present is invisible. The tripwire reports on the state
that does not need reporting.

⚠️ **It is blind to churn, not merely to pre-existing rows.** A run that deletes 430 rows and
creates 430 rows has `after == before` and reports clean. That is not hypothetical — it is
what happened here, measured below.

## 2. What the two runs actually did

| | companies at start | at end | tripwire |
|---|---|---|---|
| baseline run | 404 | 435 | **fired** (+31) |
| after-run | 435 | 435 | silent |

Read as a delta, the second run was clean. Read as a population, it was not:

```
total companies now                     435
  created today, 15:15–15:21             430   ← the after-run's own window
  created before today                     5
```

The five that predate today are `default`, `testco`, `st-marys`, `hopkins-fh`, `sunnycrest`
— the seeded tenants named in CLAUDE.md §7 as the canonical dev fixtures. Everything else in
the table, **430 rows, 98.9%**, was created during the run that reported clean, which means
roughly 430 pre-existing rows were deleted during that same run.

So the +31 the baseline reported is not the litter. It is the **net drift** of a population
that turns over almost completely every run. The tripwire noticed the residue and missed the
turnover.

⚠️ This corrects the premise the cleanup was scoped against: the dev database does not hold
"31 rows created by the baseline run". It holds 430 resident test companies, and 31 was only
the amount by which one run's churn failed to balance.

## 3. Every session-level tripwire, enumerated

Two `scope="session", autouse=True` fixtures exist in the tree, both in
`backend/tests/conftest.py`. There are two conftest files (`tests/conftest.py`,
`tests/tasks/conftest.py`); the second defines none.

Seventeen further `scope="session"` fixtures exist in `test_audit_comprehensive.py` and
`test_comprehensive.py`. They are data fixtures, not tripwires — none calls `pytest.fail` on
a measured condition.

**Both tripwires share the shape.**

| Fixture | Condition | Shares the shape? |
|---|---|---|
| `_company_litter_tripwire` (:203) | `after > before` | **Yes** — pure delta against the run's own start |
| `_unowned_litter_tripwire` (:174) | `after[k] - before[k] > _LEAK_CEILING[k]` | **Yes** — a delta, merely one with a ceiling on it |

The second looks stronger because it carries a ratchet ("⚠️ THE CEILING MAY ONLY BE
LOWERED"), and the ratchet is real and worth keeping. But it ratchets **the permitted
growth**, not the permitted total. Eleven unowned workflows already resident are invisible to
it forever, and a run that deletes eleven and creates eleven satisfies it exactly as the
company tripwire is satisfied.

So this is 2 of 2, not 1 of 2 — the fix is a shape, not a patch to one fixture.

## 4. What the right condition is

**State the condition against an expected value, not against the run's own starting point.**

```python
EXPECTED_COMPANIES = 5          # default, testco, st-marys, hopkins-fh, sunnycrest
...
if after > EXPECTED_COMPANIES:
    pytest.fail(...)
```

Checked at session end — after all teardown — the count should have returned to the
legitimate seeded population. An absolute condition catches the leak, the pre-existing
residue, and the churn, because all three end with more rows than there should be. The
delta catches only the first, and only once.

The number should ratchet downward exactly as `_LEAK_CEILING` does, for the same reason: an
expected value that may be raised is not a guard.

⚠️ **NOT CHANGED, AND THE REASON MATTERS.** Against the database as it stands, an absolute
condition of 5 fails immediately and keeps failing until the 430 are cleared — every run red
on a true finding. That is correct behaviour and a disruptive thing to switch on without a
decision, so it is reported rather than applied. The sequence that works is: clean first,
then switch the condition, then the guard has a floor to hold.

The same reasoning applies to `_unowned_litter_tripwire`, whose 11 would become an absolute
expected total rather than a permitted delta.

## 5. Cleanup — dry run only, nothing applied

Using the repo's own FK-safe purge order (`tests/_cleanup.py::_PURGE_STATEMENTS`, 74
statements), converted from `DELETE` to `SELECT count(*)` and run inside a rolled-back
session:

```
companies deleted   430        companies kept   5
child rows          2098       across 29 tables
```

Largest contributors: `roles` 602, `users` 429, `tasks` 78, `audit_logs` 55, `vault_items`
36, `vaults` 25, `invoices` 22, `task_details` 21, `customer_payments` 18, `notifications`
18, `customer_payment_applications` 15, `workflow_steps` 13, `vendor_bills` 13,
`company_modules` 256.

**2 of the 74 statements could not be converted** to a count by the regex used (they are not
a plain `DELETE FROM <table> WHERE …` shape) and are excluded from the 2098. The total is
therefore a **lower bound**, not an exact figure.

⚠️ A FALSE ZERO WAS PRODUCED AND DISCARDED ON THE WAY TO THIS TABLE. The first attempt
treated `_PURGE_STATEMENTS` as a list of table names, built `SELECT count(*) FROM DELETE
FROM …`, caught every resulting exception, and reported **0 child rows across 430
companies**. It was rejected for being too clean rather than by any error surfacing — the
exception handler had swallowed 74 failures in a row. See CLAUDE.md §11, *a result that is
too clean is a claim about the instrument*.

To apply, the command is the existing helper against the same keep-list; it is deliberately
not written out here, because the decision to run it is not this investigation's to make.

## 6. The litter is now failing tests, and both tripwires are blind to the table doing it

A third full-tree run, taken after the work above, produced **one new failure by test-id
diff** — `test_component_configurations_phase3.py::TestApiCrud::test_create_invalid_prop_returns_400`:

```
psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint
"ix_platform_users_email"
DETAIL:  Key (email)=(platform-748396@bridgeable.test) already exists.
```

It is not caused by the work in this session. It is caused by the litter.

```
platform_users, total rows                                7790
  matching the test pattern platform-%@bridgeable.test    4483
platform_users in tests/_cleanup.py's purge order?         NO
```

The fixtures mint `platform-{suffix}@bridgeable.test` with a six-digit suffix, in at least
five test files sharing one namespace (`test_component_configurations_phase3`,
`test_platform_themes_phase2`, `test_focus_template_inheritance_admin_api`,
`test_edge_panel_inheritance_admin_api`, and others). Against 4,483 resident rows over a
10⁶ space:

| inserts in a run | chance of at least one collision |
|---|---|
| 10 | 4.4% |
| 50 | 20.1% |
| 200 | 59.3% |

⚠️ **THIS IS A FLAKE WHOSE RATE RISES MONOTONICALLY WITH THE LITTER.** It failed on this run
and not the two before it by chance. Every run adds rows, so the probability increases and
never falls. The test file dates from 2026-06-03 and has not changed.

⚠️ **AND IT IS INVISIBLE TO BOTH TRIPWIRES.** `_company_litter_tripwire` counts `companies`.
`_unowned_litter_tripwire` counts orphaned health scores and global workflows.
`platform_users` is in neither, and it is not in the purge order either — so no per-file
teardown reaches it, no session check reports it, and 7,790 rows have accumulated without
anything ever saying so.

That is the practical argument for the absolute condition in §4, and it is stronger than the
repeatability argument: a delta-based guard did not merely fail to report the debris, it let
the debris reach the point of breaking an unrelated test. The cleanup in §5 should extend to
`platform_users`, whose omission from `_PURGE_STATEMENTS` looks like the original oversight.

## 7. What this does not establish

Which fixtures create the 430 is not enumerated here. The tripwire names no offender, and
attributing them requires per-fixture accounting that this pass did not do. The population is
measured; its authorship is not.
