# Seeds into CI — what it costs, what it breaks, and one thing that needs a ruling

**2026-09-23.** Step 2 of the sequenced plan in `2026-09-23-ci-coverage.md`. Closes the
structural gap that doc named: *the environment with the seeds has no suite; the
environments with a suite have no seeds.*

**Three headlines, and the second is the STOP.**

1. **The step works.** 51 seeds attempted, 51 succeeded, 0 failed on a fresh database.
   ⚠️ Cost was published here as 90s and **the real channel says 222s** — see §7. Both
   earlier figures were laptop readings.
2. ⚠️ **Two tests fail, one root, and it is NOT the `tax_jurisdictions` class that was
   expected.** On a seeded database, **eight of nine** declared automation refs on the
   accounting jobs resolve to nothing. Test-vs-seed is genuinely ambiguous. **Needs a
   ruling.**
3. ⚠️ **The documented way to stop `seed_sunnycrest` printing a password did not work**,
   and had not since it was written. Measured with the variable set: the password line
   still appeared.

---

## 1. Part 1 — the step

### `seed_dev.sh` as-is, not a CI variant

CI needs its own *step*; it does not need its own *script*. A forked CI seed sequence is a
second copy of the thing to keep in step with the first, and the entire value of this
change is that CI and local dev build the **same** database. Everything CI needed turned
out to be something `seed_dev.sh` was also getting wrong for its existing reader:

| CI needs | Status before | Also wrong for local dev? |
|---|---|---|
| Refuse a remote database | already correct | — |
| Resolve an interpreter without `backend/.venv` | already correct | — |
| **Exit non-zero when seeding fails** | printed `INCOMPLETE` and exited **0** | **yes** |
| **Not print a credential** | printed one; the documented override did not stop it | **yes** |

So both fixes landed in `seed_dev.sh` / `seed_sunnycrest.py` rather than in a CI fork.

### Verification is by produced state, never exit code

Unchanged in principle — `seed_dev.sh` already verified by counting rows, for the reason
its own comment gives (`$?` after a pipeline is the last command's, and the canonical
runner exits 0 by design). Three changes:

- The verification now **exits non-zero** when the floor is not met. Until today it
  printed `INCOMPLETE — read the log` and exited 0, so a broken database and a working
  one were the same result to everything downstream.
- The runner's **own failure count** is re-read from its `Done.` line rather than
  inherited from its exit code. `run_canonical_seeds.sh` exits 0 even when seeds fail —
  locked decision #2, correct for the staging boot path it was written for, and not a
  policy a caller whose whole job is "did seeding work" should adopt.
- `tax_jurisdictions >= 1` joins the floor. Not a round number: it is the table whose
  emptiness made three tests pass for months. A floor of 1 is the difference between
  *the seeds ran* and *the seeds produced the shape a deploy produces*.
- **The four fail-loud seeds are now checked individually.** `railway-start.sh` aborts a
  deploy when one of them fails — that is what "fail-loud" names, and it was a property of
  `railway-start.sh`, not of these seeds. Run from `seed_dev.sh` they had no such
  discipline: there is no `set -e`, so a crash printed a traceback into the log and the
  next seed ran anyway. Two of the four happen to be covered indirectly by the row floors;
  `seed_dispatch_demo` and `seed_edge_panel_inheritance` were covered by nothing.

**Break tests — two breaks, one per new failure path, each with its control:**

```
floor set to an impossible value    → exit 1, "FAILED: the database did not reach the
                                       expected state."
                                      CONTROL: "51 seeds attempted, 51 succeeded" and the
                                      migration head both printed, so the script reached
                                      the verification rather than dying early.

a fail-loud seed pointed at a       → exit 1, "FAILED: fail-loud seed(s):
module that does not exist             seed_dispatch_demo_NOPE"
                                      CONTROL: exactly ONE failure named and the canonical
                                      runner still reported 51/51, so the loop continued
                                      past the failure rather than aborting — which is
                                      what makes the report a list rather than a
                                      first-failure.

good fresh database                 → exit 0, "OK: 0 seed failures, state verified."
                                      96s, floors met, migration head r185.
```

### Credentials — four seeds print one, and one of them matters

Enumerated across all 65 `seed_*.py`, then confirmed against the log an actual fresh run
produced:

| Seed | What it prints | Runs in CI? | Real secret? |
|---|---|---|---|
| `seed_sunnycrest.py:134` | **generated** admin password | **yes, every run** | ⚠️ **yes** |
| `seed_staging.py:230` | `admin@testco.com / TestAdmin123!` | yes | no — repo constant, in CLAUDE.md §7 |
| `seed_fh_demo.py:1506` | `admin@hopkinsfh.example.com / DemoAdmin123!` | yes | no — repo constant |
| `seed_dispatch_demo.py:867` | `dispatcher@testco.com / TestDispatch123!` | yes | no — repo constant |
| `seed_staging_api.py:173` | `admin@testco.com / TestAdmin123!` | **no** — `manual` tier | no |

Only the first is a secret: it is minted at runtime and exists nowhere else. CI's database
is fresh every run, so that branch fires on **every** CI run.

⚠️ **AND THE DOCUMENTED REMEDY DID NOT WORK.** The file's own docstring said to *"set
`SUNNYCREST_ADMIN_TEMP_PASSWORD` beforehand so nothing is generated"* — true about
generation, and false about printing, which is the half that matters:

```python
temp_password = os.environ.get("SUNNYCREST_ADMIN_TEMP_PASSWORD") or secrets.token_urlsafe(12)
...
print(f"[seed_sunnycrest] TEMP admin password for {ADMIN_EMAIL}: {temp_password}")   # unconditional
```

Setting the variable changed **which** value was printed, not whether. Measured, with it
set, against a fresh database: the password line still appeared in the log.

This is *a stated reason is checked less than an unstated one*. The sentence redirected
the reader's question from *does this work?* to *did I follow the instruction?* — and the
instruction was followed, by this session, an hour before the line was measured.

**Fixed:** the print is now conditional on having *generated* the password. Supplying one
prints a notice instead. Break-tested both ways, with the control that matters:

```
generated:  1 password line,  admin_user created   ← positive control: the branch runs
supplied:   0 password lines, 1 suppression notice, admin_user created
```

The `admin_user created` in **both** rows is the non-zero value that distinguishes
"suppressed" from "the branch never ran". Without it, `0 password lines` is satisfied by a
seed that did nothing.

### The CI step

CI generates an ephemeral password per run with `openssl rand`, so no credential value is
stored, committed, or passed through a session, and the database it belongs to dies with
the runner. A second step then asserts the log is clean — **reading the positive control
first**, because "no password line" is satisfied by a seed that never ran.

### Cost — 90 seconds, not 12

⚠️ **The ~12s figure in `2026-09-23-staging-suite-gap.md` §4 was measured on the
idempotent path and does not describe what CI does.** CI's database is fresh every run.
Measured on a genuinely fresh database:

```
seed_dev.sh, end to end          90s and 96s on two fresh databases
  of which canonical runner      70s across 51 seeds
  51 attempted, 51 succeeded, 0 failed, 13 skipped (both runs)
```

⚠️ **SUPERSEDED BY THE REAL CHANNEL 2026-10-01 — 222s, not 90s.** See §7. Both figures
above are laptop readings; the step had never executed in a GitHub runner when they were
taken, which §6 listed as an open item. It is ~2.5× slower there.

---

## 2. Part 2 — what breaks, measured before anything was fixed

Method: two fresh databases, identical in every respect except seeding, both run against
the **169-file CI manifest** — not the full tree, because this question is about CI.

```
BARE   (migrations only — what CI does today)   2333 passed, 0 failed, 0 errors, 28 skipped
SEEDED (migrations + seeds — the proposed step) 2354 passed, 2 failed, 0 errors,  5 skipped
```

Denominator: **169 of 446 test files (38%)**, the manifest's own scope.

⚠️ **The bare run reproduces CI's own reported numbers exactly** — the pre-fix CI run
`35747156571` reported `2333 passed, 28 skipped`. That is the control on the whole
experiment: the local bare axis is genuinely CI-shaped, so the seeded axis is measuring
the change and not the laptop.

Seeding converts **23 skips into runs**. 21 of them pass. Two fail.

### The two failures are one root

```
FAILED tests/test_map_accounting_content_r157.py::TestTheGuardProtectsOperatorEdits::test_a_partial_ref_deletion_is_NOT_refilled_by_the_seed
FAILED tests/test_map_accounting_content_r157.py::TestTheGuardProtectsOperatorEdits::test_rerunning_is_idempotent
```

Both fail on a **precondition**, not on what they assert:

```
assert len(before) == 2, f"expected 2 seeded refs, got {before}"
E  AssertionError: expected 2 seeded refs, got {('triage_queue', 'ar_collections_triage')}
```

The job has one ref where the test expects two. The missing one is the `automation` ref.

**The seed says why, in its own output, on the fresh run:**

```
[seed_accounting_jobs] skip ref: automation 'Cash Receipts Matching' absent on this DB
[seed_accounting_jobs] skip ref: automation 'Month-End Close' absent on this DB
[seed_accounting_jobs] skip ref: automation 'Monthly Statement Run' absent on this DB
[seed_accounting_jobs] skip ref: automation 'AR Collections' absent on this DB
   … ten such lines …
[seed_accounting_jobs] ok — created 6, filled 1 ref-less
```

`seed_accounting_jobs` resolves `automation` refs by **name** against `moc_task_catalog`
(vertical=`manufacturing`, `is_active`). On a seeded database that table holds **6 rows**,
and **one** of the nine names the accounting jobs declare is among them:

```
End-of-Day Draft Invoices · Funeral Home Billing · MoC Witness Marker (T-2.1b)
New Legacy Order · Pull Bank Transactions · Quote Auto-Expiry
```

So **8 of 9 declared automation refs resolve to nothing on every seeded database** — dev,
CI, and staging, which runs this same canonical runner on every boot.

⚠️ **And the seed's guard means it never self-heals.** The opening is deliberately *"no
refs at all"* rather than *"missing the ones we declare"* — so a job that got its
`triage_queue` ref and lost its `automation` ref has refs, is treated as the operator's,
and is skipped forever. That guard is correct and its own test defends it; the
consequence is that the gap is permanent once created.

**Why it passes on bare:** there the jobs do not pre-exist, so the test's own fixture
creates them — in a session where other fixtures have already written the catalog rows.
The test is coupled to a database where the job is born inside the test.

⚠️ **AND WHY IT PASSES ON DEV, WHICH IS THE MORE ALARMING HALF.** This file is **not**
among the 39 known local failures. It passes against `bridgeable_dev`. Measured:

```
                              moc_task_catalog rows   of the 9 names the refs declare
bridgeable_dev (long-lived)            39                          8
ci_final (fresh, fully seeded)          6                          1
```

Dev has **33 catalog rows that no seed creates** — written by test runs against a
long-lived database and never cleaned up. The test passes there because accumulated test
residue happens to supply what the seeds do not.

That is *a test can pass because data is MISSING*, run in reverse: **a test passing
because data is PRESENT that no seed path reproduces.** The local 39-failure baseline is
therefore partly a measurement of accumulated residue, and the CI-shaped 2 is the truer
reading of what a database built only from seeds does. It is also the second time in two
days that a defect was invisible because the only database anyone ran the suite against
had drifted from the shape a deploy produces — which is the entire argument for this
step.

### ⚠️ STOP — this one needs a ruling

It is genuinely ambiguous, which is why it is not resolved here:

- **The test is wrong** in that it asserts a precondition that only holds on an unseeded
  database. Relaxing it to tolerate 1 ref would make CI green.
- **The seed is wrong** in that a seeded database does not end up with the refs the seed
  declares. Relaxing the test would **hide a live production gap** — staging's accounting
  jobs are missing 8 of 9 automation links right now.

Relaxing the test is the move that makes the failure go away and the defect stay. That is
`shape 9` — teaching the check the defect as the specification. It should not be taken
without a decision.

Two candidate repairs, neither applied:

1. **Create the missing catalog entries.** Requires knowing whether those nine automations
   are supposed to exist as `moc_task_catalog` rows at all, or whether the skeleton names
   things that were renamed. Not established here.
2. **Re-run the ref attachment after the catalog is populated.** `seed_accounting_jobs` is
   alphabetical position **2** of 65; the catalog seeds run later. But ordering alone does
   not fix it, because the names are absent at the *end* of a full run too — measured.

⚠️ I initially diagnosed this as an ordering fault and the data refuted it: the names are
still absent after the complete sequence finishes. Recorded because the ordering
explanation is plausible, was written down, and is wrong.

### What did NOT break: the `tax_jurisdictions` class

Expected, and absent. The three tax tests that this class broke locally were fixed earlier
in this arc, and they now pass on **both** axes. The class is real; it had already been
paid.

---

## 3. A second seeding defect, found by the break test rather than looked for

⚠️ **`seed_dev.sh` run twice destroys data the first run created.** Measured:

```
after ONE seed run    tax_jurisdictions 1 · Cayuga tax_rates 1
after TWO seed runs   tax_jurisdictions 0 · Cayuga tax_rates 0 · marked quotes 4 (survive)
```

Mechanism, confirmed rather than inferred: `seed_staging._seed_quotes` guards on a **quote
marker** and returns early when marked quotes exist. The Cayuga `TaxRate` and
`TaxJurisdiction` are created **inside that function, after the guard**. The seed's
cleanup pass deletes them (both FK to `companies`); the quotes survive the cleanup by
marker; the next run sees the marker, returns early, and never recreates the tax rows.

A guard keyed on one artifact protecting the creation of a different artifact that a
different mechanism deletes — the same shape as §2's ref guard, one table over.

**This does not affect CI**, whose database is fresh every run. It does mean a developer
who runs `seed_dev.sh` twice gets a database missing the tax substrate, and — now that the
floor includes `tax_jurisdictions` — will see `seed_dev.sh` fail on the second run. **That
red is true**, not a false alarm: the database really is incomplete.

Not fixed here; it is a `seed_staging` change with a staging blast radius and belongs with
the §2 ruling.

---

## 4. Part 3 — the two creators, reported not resolved

Two things create `testco`, and they disagree about when the tenant began.

| | `created_at` | When it runs |
|---|---|---|
| `scripts/seed_staging.py:337` (`_seed_company`) | `NOW` — `datetime.now(timezone.utc)` | boot / deploy / `seed_dev.sh` |
| `tests/_tenant.py:102` (`ensure_company`) | `_BEGAN` — **2026-04-22 15:05Z** | only when the row is **absent** |

They have never both run in the same place. That is what this change alters: with seeds in
CI, `seed_staging` creates the row first, `ensure_company` finds it present and returns
`False`, and **`_BEGAN` stops applying in CI entirely**. It remains live on the bare axis —
a developer running one test file against an unseeded scratch database.

### Which should win: the seed

`created_at` on `companies` is not fixture bookkeeping. `completeness.review` reads it via
`_tenant_start` and refuses to owe anything for a period before the tenant existed — a
real business rule. The tenant's start date should be whatever the thing that creates
tenants says it is, and the thing that creates tenants in every deployed environment is
the seed.

`_BEGAN` is the fixture asserting a different start date so that tests written against an
older database keep passing. That is the same move the 2026-09-23 ruling already rejected
one layer over — *"fix the tests, do not backdate the seed — backdating makes the fixture
lie about when the tenant started, to suit a test."* The ruling was applied to the seed.
`_BEGAN` is the fixture doing exactly the thing the ruling named, and it survived because
nobody looked at it.

### And it may already be redundant

`_BEGAN`'s own comment states its purpose: a tenant born `now()` makes August-dated tests
see an empty window. **That is precisely what the anchor fix already solved** —
`_completeness_anchor._anchor()` derives the scenario's "today" from the tenant's own
`created_at` and walks forward until every cadence is genuinely due, so a tenant born
`now()` is fine.

If that holds, the disagreement does not need resolving by choosing a winner: `_BEGAN` can
simply become `now()`, both creators agree, and nothing is lying.

**And it does hold.** Measured on the bare axis — a fresh migrated database with no seeds,
so `ensure_company` genuinely creates the row and `_BEGAN` genuinely applies:

```
_BEGAN = 2026-04-22 (as shipped)      94 passed
_BEGAN = datetime.now(timezone.utc)   94 passed
```

Across `test_completeness_review.py`, `test_completeness_declining.py` and
`test_cr3_completeness_reachability.py` — **the three files `_BEGAN`'s own comment names as
the reason it exists.** The backdate no longer changes any outcome there.

⚠️ **SCOPE, because this is a claim about a population.** That is 94 tests in 3 files, not
the 446-file tree. `ensure_company` is the canonical tenant fixture for many suites, and
whether any *other* test depends on the backdate was **not measured** — establishing that
needs a full-tree run with `_BEGAN` patched, which was not done. So the finding is "not
load-bearing for the tests it was written for", not "unused".

### Recommendation, not applied

Change `_BEGAN` to `datetime.now(timezone.utc)` — or drop the argument and take the model
default — so both creators agree, and neither is asserting a start date to suit a test.
Gate it on a full-tree run with the patch in place.

Not done here. The dispatch's instruction was to report before touching either, and *"do
not resolve it by making the test pass"* — and the change was reverted after measuring
(`tests/_tenant.py` is unmodified in this commit; verified by restoring from a copy taken
before the edit and confirming the backdated literal is present).

---

## 5. Gates

Server up, preflight and postflight both **200**. Bare `python` confirmed on PATH before
the run — see the correction below for why that control exists.

```
backend, full tree    40 failed · 6584 passed · 12 skipped · 1 error · 480s
                      denominator: 446 test files
frontend              tsc -b 0 errors · 4435 passed / 338 files · build clean 5.89s
```

**New failures by test-id diff against the recorded 39 baseline (`g18`), normalised to
strip pytest's `- …` truncation so ids compare by identity rather than by rendering:**

```
NEW   FAILED tests/test_vertical_inventory.py::TestRecentEdits::test_editor_email_resolved_when_user_present
NEW   ERROR  tests/test_zip_ambiguity.py::…::test_the_resolvable_straddles_still_agree_on_their_rate
GONE  (none)
```

- The `test_vertical_inventory` one is the **known ±1 oscillator** — bounded by
  `_RECENT_EDITS_LIMIT = 10` over a 7-day window. 39↔40 has oscillated across this arc.
- The `ERROR` is the session-scoped **COMPANY LITTER** tripwire. See below.

**Neither is attributable to this change.** `seed_dev.sh` is executed by no test; `ci.yml`
is referenced only by `conftest.py`; `seed_sunnycrest` is imported only by
`test_sunnycrest_workshop.py`. All 17 tests across those files pass.

### ⚠️ CORRECTION — I attributed the litter error to the wrong cause

My first full-tree run was **void**: pytest was invoked via `.venv/bin/python` with the
venv *not* on PATH, and three red results shared one cause — `test_seed_hygiene.py`
shells out to a bare `python`. One of those tests,
`test_keep_list_survives_a_live_apply`, performs a **real `--apply` purge of the dev
database**, so its crash left 1450 fixture companies standing. Re-run with PATH corrected:
10 passed.

I then reported the COMPANY LITTER error as a symptom of that same PATH fault. **That was
wrong.** It fires with PATH correct too:

```
g18 baseline (0 errors)   ended where it started      → delta 0    → SILENT
PATH-broken run           435 → 1885  (purge skipped) → delta 1450 → fires
clean run                 5   → 435   (purge ran)     → delta 430  → fires
```

The **430-row leak is identical and pre-existing in every run**. Only the starting count
differs, and the tripwire is a delta. The baseline's silence was not a cleaner run — it
was `after == before` cancellation, which is precisely the churn blindness recorded in
CLAUDE.md §11 (*"a run that deletes 430 rows and creates 430 rows satisfies
`after == before` exactly… 430 of the 435 companies then resident were created"*). Same
430, same table, same instrument.

So the tripwire firing here is the instrument working, and the baseline's zero was the
instrument failing to discriminate. That is the right direction, and it means **the 39
baseline's error count of 0 was never evidence of no leak.**

## 6. What this does not establish

- Whether the nine `moc_task_catalog` automation names are supposed to exist. §2 shows
  they do not; it does not show whether that is the defect or the design.
- What the other 277 test files do under seeding. This measured the **169-file manifest**,
  because that is what CI runs.
- Whether staging's accounting-job refs are missing *in fact*. The mechanism is
  established on three local databases and staging runs the same runner, but staging was
  not read.
- Whether `seed_dev.sh` completes inside a GitHub runner. It has now been run four times
  on macOS against local Postgres. **The simulation is not the reading.**

---

## 7. The real channel, 2026-10-01 — first execution outside a laptop

Pushed as `6c28748e` (in `2a205d0d`). CI run `36911452737`, job `110534820722`.

```
Seed Idempotency Gate              success
Frontend CI                        success    tsc, vitest, build all green
Backend CI                         FAILURE    on the two predicted tests, nothing else
Playwright Staging                 failure    unprovisioned ci-bot, unrelated and expected
```

**Both new steps passed.**

```
✓ Seed the canonical set
✓ Assert no credential reached the seed log
X Run scoped test gate
```

### What the steps actually reported

```
[seed-dev] python : python                     ← setup-python's alias, as intended
[seed-dev] --- verification (state, not exit codes) ---
  migration head      r185_personalization_record_v2
  companies                5   (expect >= 5)  ok
  intelligence_prompts    96   (expect >= 50)  ok
  tax_jurisdictions        1   (expect >= 1)  ok
  RESULT: usable
[seed-runner] Done. 51 seeds attempted, 51 succeeded, 0 failed, 13 skipped.
[seed-dev] OK: 0 seed failures, state verified.

suppression notices: 1   (positive control, must be >= 1)
password lines:      0   (must be 0)
```

The control is non-zero, so the zero beside it is suppression rather than a seed that never
ran. ⚠️ **`tax_jurisdictions = 1` in CI is the whole point of this step**: the row that was
absent for months, present now in the environment the suite runs in.

### The gate failed exactly as predicted, to the test id and the count

```
CI       2 failed, 2354 passed, 5 skipped, 218 warnings in 675.42s
LOCAL    2 failed, 2354 passed, 5 skipped, 221 warnings
```

Same two ids, same three counts. That is the strongest available evidence that the
CI-shaped local axis in §2 was genuinely CI-shaped, and it means §2's STOP is not a local
artefact — **8 of 9 automation refs resolve to nothing in CI too, and the two tests that
depend on them are now red on the real channel.** The ruling is what unblocks it; relaxing
the tests would make this green and leave the gap.

### ⚠️ The cost figure was wrong, and it was wrong in the direction that matters

```
~12s   first estimate   — idempotent path, not the path CI takes
 90s   second           — fresh LOCAL database
222s   THE READING      — fresh database, in the runner, 2026-10-01
```

Backend CI went **12m54s → 17m08s**. The gate itself is unchanged (675s here vs 668s on the
pre-seed run); the whole delta is seeding. §6 listed "whether `seed_dev.sh` completes inside
a GitHub runner" as unestablished, and the honest reading of that is that **every timing
figure published before today was a simulation**. The step works; it costs 2.5× what the
laptop said.

## 8. Still open after this run

- §2's STOP, now reproduced in CI rather than only locally.
- §4's `_BEGAN` recommendation. `tests/_tenant.py` is still unmodified.
- Playwright remains blocked on `provision_ci_bot --ensure`, which is owner-gated and
  unrelated to this change.
