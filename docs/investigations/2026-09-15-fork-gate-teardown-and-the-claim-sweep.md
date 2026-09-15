# The fork gate's teardown, and a sweep for the claim rather than the leak

**2026-09-15.** One false safety claim repaired, the leak it hid closed and measured to
zero, the residual attributed test-by-test, and a suite-wide sweep for the shape.

No figure below is inherited. The 23, the 34, the 621 and the 673 were all re-derived and
two of them had moved — they have a slope, and this session's own earlier work is part of
it. Every count carries the time it was taken.

---

## 1. The defect, re-measured

`backend/tests/test_workflow_scope_latency_phase8a.py::test_workflow_fork_latency` creates
`_SAMPLE_COUNT + _WARMUP_COUNT` global `scope="core"` workflows with three steps each, and
deletes none of them. Its docstring said:

> *"we delete the fork after measurement"*

That had been false since it was written. It also understated the scope of what it was
claiming: the test creates **sources as well as forks**, and neither was deleted.

**Counts, 2026-09-15 13:54:56 UTC**, against `localhost:5432/bridgeable_dev`:

| | rows |
|---|---|
| `workflows` total | 1,373 |
| `company_id IS NULL` | 813 |
| **global non-canonical** (the tripwire's class) | **777** |
| `scope='core'` | 724 |

The purge on 2026-09-14 left `scope='core'` at 6. ⚠️ These rows have `company_id IS NULL`,
so no company-scoped foreign key reaches them — r183 and r184 do not close this class, and
the purge could only clear stock.

⚠️ **The counts move while you read them, and a large share of the movement is this
session.** Measuring GC yesterday and today meant running that file roughly twenty times.
A figure from this table is a reading, not a constant.

---

## 2. Why it blocked the budgets

`GET /api/v1/workflows?scope=core` fires an aggregate per row, and
`test_workflow_scope_core_latency` — a different test **in the same file** — measures it.
So one gate manufactured the input of another gate, monotonically, forever.

Measured directly, three consecutive runs of the file on 2026-09-15:

| | `scope='core'` | `workflow-scope-core` p50 |
|---|---|---|
| before | 581 | 117.2 ms |
| +1 run | 604 | 121.8 ms |
| +2 runs | 627 | — |

**+23 rows and roughly +4.6 ms per run.** The preliminary's 261.9 ms and 466.4 ms were a
row-count reading taken at one moment, not a property of the endpoint.

---

## 3. The repair

A function-scoped fixture, `created_workflow_ids`. The test registers every id it creates
— sources after their commit, forks as the endpoint returns them — and the fixture's
teardown deletes exactly those.

**By id, not by name.** A `name LIKE 'ForkSrc-%'` sweep would be a constructed scope: it
would miss anything renamed, match rows this run did not create, and stop matching
silently the day the name changes. This arc has been caught by four constructed patterns
already.

**It runs on failure.** Fixture finalisation happens whether the test passed, failed or
raised. A `try/finally` in the test body would too, but only from the point the `try` is
entered — and the first failure before that would have reinstated the leak permanently.

**The FK behaviour was read, not assumed.** From the catalogue: `workflow_steps` and
`workflow_step_params` are `ON DELETE CASCADE` from `workflows`, so they go with the
parent; `workflows.forked_from_workflow_id` is `SET NULL`, so a fork does **not** disappear
with its source and has to be recorded in its own right. Three children —
`workflow_enrollments`, `workflow_runs`, `workflow_schedules` — are `NO ACTION` and would
raise rather than orphan, which is the correct behaviour if this test ever starts creating
them.

**A control on the teardown itself.** The fixture asserts that the number of rows deleted
equals the number recorded. The whole reason it exists is that nobody was checking.

**And a control on the control.** `_fork_id()` asserts the fork response carries an `id`.
If the serializer ever stopped returning one, teardown would register nothing, the leak
would return, and the fixture would still be sitting there looking correct — this file's
own failure mode repeating one level up.

### Verified by measurement, not by reading

The docstring already claimed what the code did not do, so the repair is verified the
same way the defect was found: by counting rows.

| | global non-canonical workflows |
|---|---|
| three consecutive runs of the file, before | +23, +23, +23 |
| three consecutive runs, after | **0, 0, 0** |
| full tree, before | +34 |
| full tree, after | **+11** |

⚠️ **Teardown-on-failure, break-tested.** An `assert False` was inserted after the rows
exist (marker count 1, confirming the break applied). The test failed; the leak delta was
**0**. Break removed, marker count back to 0.

---

## 4. The residual: +11, and it is NOT the same shape

Attributed per test on a full-tree run, by the row class the tripwire defines rather than
by any name pattern:

| rows | producer |
|---|---|
| **23** | `test_workflow_scope_latency_phase8a::test_workflow_fork_latency` |
| 4 | `test_workflow_scope_phase8a` — `TestForkEndpoint` ×3, `TestCountTenantsUsingWorkflow` ×1 |
| 5 | `tasks/test_b3_consumer_integration::TestWorkflowNodeTypes` ×5 |
| 1 | `test_moc_ponder::TestScriptAssembly::test_registry_workflow_gets_the_queue_beat` |
| 1 | `test_classification_tier_3_registry::test_assemble_registry_includes_platform` |
| 1 | `test_moc_tenant_map::test_01_both_tenants_see_the_shared_default` |
| −1 | `test_moc_tenant_map::test_13_wrong_vertical_task_is_invisible` |
| **34** | **total, matching STATE's "+34 every time" exactly** |

Post-fix the same enumeration returns the same twelve rows minus the fork gate: **+11**.

⚠️ **STOP — the remainder has a different cause and should be its own item.** The fork
gate's shape was *claims cleanup, has none*. None of the five remaining producers claims
to clean up these rows at all:

- `test_workflow_scope_phase8a` (+4) has **no row-deleting teardown of any kind** and makes
  no cleanup claim. Unclaimed and unfixed.
- `tasks/test_b3_consumer_integration` (+5), `test_moc_ponder` (+1) and `test_moc_tenant_map`
  (+1, net 0) each have substantial teardown — 2, 9 and 16 row-deleting calls — that does
  not reach these particular rows.
- `test_classification_tier_3_registry` (+1) creates its row through the shared helper
  `tests/_classification_fixtures.make_workflow(db, None, ...)`.

⚠️ **The shared-helper hypothesis was tested and does not hold.** `make_workflow` looked
like a common cause worth fixing once. Enumerated from the AST across `tests/` — because
`make_workflow(db, None)` and `make_workflow(db, tenant=None)` are one call in two shapes
and a text pattern would have to guess both — there are **33 call sites in 7 files and
exactly one** passes a null tenant. It is one call site, not a class.

---

## 5. The ratchet, lowered with two controls

`tests/conftest.py::_LEAK_CEILING["global_workflows"]` **34 → 11**, the measured residual,
with the attribution table recorded beside it.

A ratchet asserts an absence, and an absence looks identical whether the instrument works
or not, so both halves were shown:

| control | result |
|---|---|
| the counter SEES | ceiling temporarily 4, a file that leaks 5 → fires, reporting `global_workflows: +5 (ceiling 4)` |
| the ceiling DECIDES | same file, ceiling back at 11 → silent |

Marker counts confirmed the temporary edit applied (1) and was removed (0). A return of
the 23-row regression exceeds 11 by the same comparison these two controls exercised.

⚠️ **A latent defect in the tripwire, surfaced and NOT fixed.** The failure comprehension
reads `_LEAK_CEILING[k]` for its message while the condition reads `_LEAK_CEILING.get(k, 0)`.
If `orphaned_health_scores` — which has no entry, deliberately — ever grew, the guard
would raise `KeyError` instead of printing its own explanation. The session still fails,
so the guard is not silent, but it would fail unreadably. One character. Not this item's.

---

## 6. The sweep: the claim as the search key

A leak is invisible until it accumulates. A sentence saying *"we clean up"* is greppable
today. Two false ones had been found in two different contexts — this docstring and the
purge script's *"every row it is about to delete"* — which is the argument for looking for
a third by the claim rather than by the damage.

**Stage 1 — enumerate.**

| | |
|---|---|
| population | **549** `.py` files under `backend/tests/` and `backend/scripts/`, walked from the filesystem |
| texts | **15,391** docstrings + comments — docstrings via `ast` (found by structure, not by quoting style), comments via `tokenize` (so a `#` inside a string is not mistaken for one) |
| vocabulary | **54** forms, inflections included, enumerated before the pattern was written |
| hits | **841** texts contain at least one form |

**Stage 2 — narrow, then read.** Most of the 841 describe the *subject under test*
("deletes the invoice"), not the test's own housekeeping. Requiring a self-referential
marker as well leaves **127 files making a cleanup claim about themselves**. Of those,
**104** contain something that deletes a row; **23** do not, and those 23 were read
individually.

⚠️ **THE NARROWING WAS WRONG TWICE, AND THE POSITIVE CONTROL IS WHAT SAID SO.**
The known false claim must land in the survivor set or the sweep proves nothing.

- **v1** counted `finally:` and a bare `yield` as cleanup. The fork gate has
  `finally: db.close()` around the block that **creates** its rows, so it landed in
  "has a mechanism", the survivor set came back at 4 — all false positives — and the one
  file known to be guilty was absent. *A narrowing that loses its own control proves
  nothing, and it looked like a clean result.*
- **v2** matched `\.delete\(\)` with literal parentheses and missed every call written
  `.delete(\n    synchronize_session=False)`. Third constructed pattern in this arc.
- **v3** passes the control.

**Result: one false claim in 127 — the fork gate.** The other 22 survivors, classified by
reading each one:

| | |
|---|---|
| prose about the SUBJECT under test, not about housekeeping | 9 |
| rollback-based teardown the row-delete matcher does not recognise | 3 |
| teardown delegated to `make_canonical_tenant_fixture(child_tables=…)` | 3 |
| non-row state teardown (an advisory lock, an app reload, a scheduler reset) — true | 3 |
| this arc's own new docstrings | 2 |
| true by construction — the file has zero database references | 1 |
| a claim about a DIFFERENT file's behaviour | 1 |
| **total** | **22** |

Each of the five rollback cases was opened and confirmed rather than waved through —
`test_ar_invoice_posting_legs` restores `settings_json` explicitly on top of its rollback;
`test_zip_alarm` and `test_tax_exemption_surface` both say in terms that rollback is *not*
sufficient for one committing service and add `make_canonical_tenant_fixture(child_tables=…)`;
`test_scheduler_wrapper_ratchet`'s `remove_all_jobs()` is present in both setup and
teardown as claimed; `test_cr3_completeness_reachability`'s "no DB, no Company rows, no
litter" is true by construction — zero database references in the file.

⚠️ **WHAT THIS SWEEP DOES NOT COVER, stated so the negative means something.** A file whose
mechanism exists but cleans the *wrong rows* is invisible to it — the mechanism test is
"does anything here delete a row", not "does it delete the rows the sentence promises".
`tasks/test_b3_consumer_integration` is exactly that case and was found by the row
attribution, not by the sweep. The two instruments are complementary and neither is
sufficient.

---

## 7. Two things surfaced, neither this item's

**(a) ⚠️ The company-litter tripwire has been firing on every full-tree run today, and it
is reported as an error against an unrelated test.** Three runs:

| session start → end | growth |
|---|---|
| 435 → 1,886 | +1,451 |
| 2,109 → 3,547 | +1,438 |
| 3,563 → 5,001 | +1,438 |

It is attributed as `ERROR at teardown of test_zip_ambiguity::…::test_the_resolvable_straddles_still_agree_on_their_rate`
— the last test in the session, which has nothing to do with it. ⚠️ **This commit's author
mis-read that id earlier the same day**, recording it in a test-id diff as a
`test_zip_ambiguity` error rather than as the session tripwire riding on the last test.
The guard works; its attribution is misleading, and it cost one wrong reading already.

Unlike the workflow class, this one is **loud** — it fails the session every time. It is a
different item, and a large one.

**(b) The flow is closed; the stock is not.** `scope='core'` stood at 775 after the repair,
against 16 real `wf_sys_*`. The fix stops the growth; it does not remove what has
accumulated, and `workflow-scope-core` and `core-used-by` still fail their p50 budgets
because of it. Clearing stock is a destructive write to the development database and is
James's call, not this item's. **The budgets cannot be derived until it happens** — the
flow being closed is the precondition, not the remedy.
