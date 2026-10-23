# Every deploy took production offline for minutes, and why 55 seeds run on boot

**2026-10-23.** James's dispatch: *"Every deploy takes production offline for about 9
minutes… Separately, report why 65 seeds run on every boot. Which ones must, and could
the rest run only when their data is missing, or move to a release step? Propose; don't
change seed behaviour without James's go."*

Every number below is measured, and each says which environment it came from.

---

## 1. The downtime, measured

| what | where | number |
|---|---|---|
| 502 window, deploy of `835ca949` | production edge | **≥ 329 s** |
| 502 window, deploy of `0289edf6` | production edge | ~540 s (observed, not sampled from t=0) |

⚠️ **The 329 s is a LOWER BOUND, not the window.** Sampling started 1 s after the first
request and the first sample was already 502, so the outage had begun before
measurement. "At least 329 seconds" is the honest form.

The 502 comes from Railway's own edge — `{"status":"error","code":502,"message":
"Application failed to respond"}` on `sunnycresterp-production.up.railway.app`, not from
Cloudflare. The container is up and nothing is listening.

**Mechanism.** `backend/railway-start.sh` holds a Postgres advisory lock (`815001`) over
a PREP phase — `alembic upgrade head`, then four fail-loud seeds, then the canonical
runner — and only then `exec uvicorn`. Railway had no healthcheck configured, so it
routed `api.getbridgeable.com` at the new container immediately and removed the old one.
Nothing served until prep finished.

⚠️ **AND THIS WAS MISREAD ONCE ALREADY, BY ME.** I pushed a notification saying
production was down and needed the dashboard. It was booting. The evidence against my
reading was already in hand: Railway reported the deployment SUCCESS, and a `pg_locks`
probe showed one holder of `815001` and **no waiter** — so it was not lock contention
between two boots, it was one slow prep. An idle `ClientRead` holder between seed
statements looks exactly like a stalled one.

### Applied: `backend/railway.toml`

```toml
[deploy]
healthcheckPath = "/api/health"
healthcheckTimeout = 900
```

Config-as-code in the API service's build root (confirmed `backend/` — its Dockerfile
does `COPY requirements.txt .`, which only resolves with that context). With a
healthcheck, Railway holds traffic on the previous deployment until the new one answers.

⚠️ **THE TIMEOUT IS MEASURED, NOT ROUND, AND A TIGHT ONE WOULD BE WORSE THAN NONE.**
Railway FAILS a deploy whose healthcheck does not pass inside the window. Boot has been
seen at 330 s and ~540 s, so a timeout near the observed boot time converts a silent
outage into a red deploy — a different failure, not a fix. 900 s is ~1.7× the slowest
boot seen, and costs nothing on a fast boot.

⚠️ **A 15-minute tolerance on a service that should bind in seconds is a place for a
real hang to hide.** If the seeds leave the boot path, bring it down.

**Not yet verified.** The next deploy is the measurement. `/tmp/measure_window.sh`
samples `/api/health` every 3 s and prints the window; the before-number above is what
it must beat.

---

## 2. Why 55 seeds run on every boot

⚠️ **55, not 65.** Derived rather than inherited:

```
68   scripts/seed_*.py
-13  declared manual (10) or local-only (3) in scripts/seed_manifest.py
     — local-only is skipped only when RAILWAY_GIT_COMMIT_SHA is set, which it is on Railway
= 55 execute per production boot   (51 through run_canonical_seeds.sh + 4 fail-loud, run earlier)
```

**It is a discovery design, not a decision.** `run_canonical_seeds.sh` globs
`seed_*.py`, sorts, and runs everything the manifest has not excluded. Nothing asks
whether a seed's data is already present — each seed answers that itself, in its own
Python process, after paying the import cost.

### Where the time goes (local, against an already-seeded database — production's steady state)

| measurement | value |
|---|---|
| 51 runner seeds, total | **118.1 s** |
| `seed_onboarding_checklists` alone | 42.9 s |
| the other 50 | 75.2 s → **1.5 s each** |
| bare interpreter (`python -c pass`) | 0.02 s |
| `import app.database` + `import app.models` | **0.9 s** |
| one idempotent no-op seed, end to end | 1.6 s |

**So ~0.9 s of every 1.5 s seed is importing SQLAlchemy and the 157 model modules —
about 46 s of the local total is the same imports, 51 times, before any seed does
anything.** The SQL is not the cost.

⚠️ **THE 42.9 s IS A LOCAL ARTIFACT AND I ALMOST REPORTED IT AS A PRODUCTION COST.**
`seed_onboarding_checklists` iterates every company. Local has **2224** companies (test
litter — CLAUDE.md §11's company-litter class). Production has **4**. On production it
costs about what the others do.

Production's 330–540 s against the local 118 s is not accounted for here. Each seed also
opens its own connection to the database, and I did not measure that from inside a
container — `railway run` executes locally, so timing it would measure my laptop's
latency to Railway, not the container's. **Unmeasured, and the proposal below makes it
moot rather than needing the number.**

---

## 3. Which must run — the classification

**(a) Platform defaults that ship WITH code — must be applied on every deploy (≈40).**
Intelligence prompts (9 `seed_intelligence*` plus triage, intake, email-classification,
personalization, workflow-authoring, and the Opas door's own prompt), managed email
templates, Maps of Content, focus templates, workflow templates, the Plaid category map,
NY tax jurisdictions, onboarding checklists.

These are code artifacts stored in rows. A deploy that skips them leaves new code running
against old data — **this very deploy needed one**: `seed_opas_order_list_prompt` had to
move the door's prompt v1 → v2 → v3, and did, 214 s into the boot. They are correctly on
the deploy path. They are **not** correctly in the serving container's startup.

**(b) Demo and sample data — should not reach production (6).** `seed_jcf_demo`,
`seed_nl_demo_data`, `seed_quotes`, `seed_saved_orders`, `seed_demo_artifact_focuses`,
`seed_demo_artifact_workflows`. Only `seed_jcf_demo` carries an `ENVIRONMENT` guard.

⚠️ **I EXPECTED TO FIND DEMO DATA IN THE REAL TENANT AND IT IS NOT THERE.** `pick_tenant`
in both `seed_quotes` and `seed_saved_orders` prefers `testco` and otherwise takes *the
first active company with the sales module*, whose own comment reads **"When Sunnycrest
onboards, relocate deliberately"** — a deferred decision never made, and Sunnycrest is
live. Measured on production: that fallback would choose **sunnycrest** (created
2026-03-27, sales enabled). But **`testco` exists on production** (created 2026-04-07),
so the preferred branch wins and the data landed there: 8 quotes and 2 saved orders, all
in `testco`, none in `sunnycrest`.

So this is a **latent hazard, not a current defect**: deleting `testco` from production
would silently redirect demo quotes and saved orders into the real company's books on the
next deploy. Reported rather than fixed, per the dispatch.

**(c) One-time backfills and tenant activations (≈5).** `seed_sunnycrest` (the real
tenant — must run), `seed_personalization_availability`, `seed_moc_*backfill*`,
`seed_so_audit_planning`. These are the ones that genuinely only need to run when their
data is missing.

**(d) Not a seed at all (1).** `seed_manifest` is the manifest MODULE, caught by the
`seed_*.py` glob and executed as a seed on every boot. Harmless — it prints the manifest
and exits in 0.02 s — but it shows the glob is indiscriminate about what it picks up.

---

## 4. Proposals — none applied

**P1 — move prep to Railway's `preDeployCommand`. The structural fix.** Schema-confirmed:
`preDeployCommand` plus `preDeployTimeoutSeconds` (1–3600). Railway runs it before the
new deployment goes live and **fails the deploy on non-zero**, which preserves the
R-1.6.3 and R-3.1.3 fail-loud rulings exactly. `railway-start.sh` becomes `exec uvicorn`
and binds in seconds.

Two bonuses: the healthcheck timeout can come back down to something that would catch a
real hang, and the boot-prep advisory lock becomes unnecessary — its whole purpose was
serializing overlapping container boots (the C-10 postmortem).

⚠️ One thing to check first: a pre-deploy container must reach the same database and the
same env. It does on Railway, but it is a different container, so anything prep relies on
from the app image needs confirming rather than assuming.

**P2 — one process instead of 51.** A runner that imports once and calls each seed's
`main()` in-process removes ~46 s of repeated imports locally and proportionally more on
production. **Blocked, not free: 12 of the 51 modules call `sys.exit()`**, which would
end the batch. Needs per-seed isolation plus a rule that no seed exits the interpreter —
real work, not a flag.

**P3 — declare the 5 unguarded demo seeds `manual`.** They start a Python process each
to decide they have nothing to do, and the hazard in (b) above disappears with them. ~8 s
locally, and it removes a way for demo data to reach the real tenant.

**P4 — stop running `seed_manifest` as a seed.** Rename it or exclude it by name.

**P1 is the one that matters.** P2–P4 make a nine-minute boot into a shorter one; P1
takes it out of the serving path, which is the thing James actually asked for.
