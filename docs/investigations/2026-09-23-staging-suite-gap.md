# No suite runs against a seeded database anywhere

**2026-09-23.** Read-only. Nothing built. Establishes what it would take for a test suite to
run against staging, and whether the jurisdiction conflict is detectable without one.

**The answer is smaller and worse than "staging has no suite": the pytest suite has never
run against a fully-seeded database in any environment.** That is why the conflict survived,
and it is fixable in CI for about twelve seconds of runtime.

---

## 1. Where the suite runs today, and what its database contains

| | database | seeds run | suite |
|---|---|---|---|
| **local dev** | `bridgeable_dev` | **3 of 65** until 2026-09-23; all of them now | whole tree, 446 files |
| **CI** (`ci.yml`) | ephemeral `postgres:16-alpine` | **none** — `alembic upgrade head`, then pytest | `tests/ci_gate.txt`, **169 files** |
| **staging** | Railway Postgres | **all**, via `railway-start.sh` + `run_canonical_seeds.sh` | **none** — Playwright only, against the HTTP surface |

So the two things never meet. The environment with the seeds has no suite; the environments
with a suite have no seeds.

⚠️ **CI RUNS NO SEEDS AT ALL.** `ci.yml` goes migrations → pytest. `tax_jurisdictions` is
empty there for the same reason it was empty locally, so the three tests that were
green-because-empty were green in CI too, permanently, and would have stayed that way.

⚠️ **CI ALSO RUNS 169 OF 446 FILES — 38%.** That is the denominator rule in CLAUDE.md §11
applying to this repo's own gate. Four of the five files involved in this arc are in the
manifest; `test_integrations_area` is not, so its failure could never have appeared in CI
whatever the database held.

## 2. The conflict is undetectable by any existing automation

Not "nobody looked" — **no configured job could have seen it**:

- CI would need the seeds to produce the conflicting row. It does not run them.
- Playwright exercises staging over HTTP. It asserts on rendered pages and API responses, not
  on what a test fixture would insert, so it cannot observe a fixture colliding with seeded
  data. The collision only exists inside a pytest process.
- Staging's own boot runs every seed and then starts a server. Nothing asserts.

It surfaced only because a local database was, for the first time, seeded the way a deployed
one is.

## 3. There is a second, unmeasured consequence in CI right now

`make_canonical_tenant_fixture` (`tests/_tenant.py:151`) ensures `testco` exists, creating it
when absent. CI has no seeds, so CI creates that tenant **during the run** — making it minutes
old.

That is exactly the condition that broke the nine completeness tests locally: `review()` owes
nothing for a period before `_tenant_start`, and those tests hard-coded `2026-08-13`. Both
completeness files are in `ci_gate.txt`.

⚠️ **So those nine were almost certainly failing in CI as well, and CI has been red for 30
consecutive runs.** This is stated as a strong inference, not a measurement — confirming it
means reading a CI log from before today's fix, which is a cheap next step and was not done
here. If it holds, today's anchor fix removes nine failures from the CI gate as a side effect.

## 4. What it would take

### Option A — seed CI before pytest (small, and it is the real fix)

Add one step to `ci.yml` between `alembic upgrade head` and the pytest step:

```yaml
- name: Seed the canonical set
  run: bash scripts/seed_dev.sh
```

**Cost:** ~12s of runtime (measured: 4.55s migrations + 7.9s seeds on a laptop). `seed_dev.sh`
already refuses a non-local `DATABASE_URL`, so that guard needs widening to permit CI's
`localhost:5432/test_db` — it already would, since CI's URL is `localhost`.

**What it buys:** the suite starts testing against the database shape that deploys actually
produce. Every defect of the class found today becomes visible on the first run.

**What it costs beyond runtime, and this is the honest part:** it will surface failures. The
three tax/zip tests and nine completeness tests were the local yield; CI's manifest is a
different 38% of the tree and will have its own. That is the point of the change and it should
be expected rather than treated as a regression — the same reading the 54-then-42 progression
needed.

### Option B — run the suite against staging

Rejected on inspection rather than on principle. The suite writes: it creates tenants, inserts
jurisdictions, deletes rows. `_cleanup.py` and the litter tripwires exist because it leaks even
locally. Pointing it at a deployed database means test fixtures writing into the environment
the September demo runs on. Option A gets the same signal against a throwaway database.

### Option C — a bespoke detector

A script comparing seeded state against test assumptions — "which tests insert into a table the
seeds also populate". That is the `suspects = users − clearers` filter from CLAUDE.md §11,
already available, already run: it narrowed `tax_jurisdictions` to two candidates. It is worth
keeping as triage, but it predicts candidates rather than finding defects, and Option A finds
them by running.

## 5. What this does not establish

- Whether the nine completeness tests were in fact failing in CI. §3 is inference from the
  fixture's behaviour and the manifest's contents; the CI logs would settle it.
- What CI's 30-run red streak is actually composed of. The last green was 2026-09-08 and the
  newest failure is TypeScript plus a backend gate exit 1 — the backend portion is
  unenumerated.
- Whether `seed_dev.sh` completes inside a GitHub runner. It has only been run on macOS
  against a local Postgres.
