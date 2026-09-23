# Should the dev database be dropped and re-seeded instead of surgically cleaned?

**2026-09-23.** Read-only against `bridgeable_dev`. Nothing deleted. The seeds were run
against a **scratch database** (`bridgeable_reseed_test`), never against dev.

**Answer: yes, re-seed is viable — 12.4 seconds, zero errors, and it produces exactly the
five kept tenants. It has one real cost, and it is not the one the surgical plan was
protecting.**

---

## 1. What a drop-and-reseed produces, measured

Scratch database, created empty, then `alembic upgrade head` + the three seeds:

```
alembic upgrade head   4.55s        seed_staging      2.98s
seed_fh_demo           3.14s        seed_sunnycrest   1.75s
                                    ─────────────────────────
                                    total            12.42s
```

Result, verified against the database rather than against exit codes:

```
tables            492      (dev: 492)          identical
migration head    r185_personalization_record_v2   identical to dev
companies           5      default, hopkins-fh, st-marys, sunnycrest, testco
```

⚠️ **The five companies a reseed produces are EXACTLY the five the surgical plan was
keeping.** That is not a coincidence — it is the same list arrived at from the other
direction, and it means the 430 doomed companies have no counterpart in a fresh database.

| | scratch (reseed) | dev today |
|---|---|---|
| companies | 5 | 435 |
| users | 13 | 484 |
| products | 25 | 34 (kept tenants) |
| price_list_items | 25 | 2,095 |
| cemetery_plots | 160 | 160 |
| funeral_cases | 2 | 1 |
| urn_products | 0 | 259 |
| platform_users | 0 | 4 |

⚠️ **I ALMOST READ THE SEED EXIT CODES THROUGH A PIPE.** Each seed ran as
`/usr/bin/time -p … | tail -N`, and `$?` after that is **`tail`'s** status, not the
command's. All four reported `0` and would have done so had every seed crashed. The
evidence above is the resulting database state — 492 tables, the r185 head, five named
companies — which cannot be faked by a failed run. CLAUDE.md §11 names this exact defect;
I wrote it anyway and caught it on re-reading.

## 2. What is NOT reproducible — and it is a short list

### The only genuine loss: four platform admin accounts

```
admin@bridgeable.com            super_admin   has logged in
dev-admin@bridgeable.internal   super_admin   has logged in
dev-moc@example.com             super_admin   has logged in
shell-witness@example.com       super_admin   has logged in
```

A reseed produces **zero** `platform_users`. No seed creates them; all four have
`last_login_at` set, so all four are in real use.

Partial recovery exists: `app/main.py:250` creates **one** platform super-admin at startup
from `PLATFORM_ADMIN_EMAIL` + `PLATFORM_ADMIN_PASSWORD`. That restores access, not the four
accounts, and ⚠️ **setting those values is James's — a credential may not transit a
session in either direction.**

**This is the decision point.** Everything else below is recoverable or worthless.

### 259 urn_products — ingestion output, regenerable, low quality

All on `default`, all `source_type=drop_ship`, all created **2026-04-09** in a single run.
No script creates `UrnProduct`; only `wilbert_ingestion_service.py` does. So they are
Wilbert PDF-ingestion output, reproducible by re-running that pipeline.

Their quality argues against preserving them regardless — the names carry parser artifacts:
`"with gold tree"`, `"| Wilbert Cremation Choices Catalog: Vo…"`, `"Serene Blue Gray"`.
This is pipeline test output, not curated catalog data.

### Everything else is accumulated test residue

`price_list_items` is the clearest case: a reseed produces **25**; dev holds **2,095**, and
they arrive in daily batches —

```
2026-09-23   60      2026-09-22  360      2026-09-15  240
2026-09-14  900      2026-09-11  210
```

They belong to `testco`, whose seeder is explicitly *clean-and-reseed*, so they are not
seeded state. They are what test runs left behind. The same pattern covers
`tax_certificates` (121), `kb_documents` (70), `kb_chunks` (69), `user_actions` (138),
`tenant_item_config` (70).

⚠️ **THIS CORRECTS MY OWN FRAMING FROM THE PREVIOUS INVESTIGATION.** I reported that 85% of
the rows in the blocking tables belong to kept tenants, and let that stand as "legitimate
seed data a blanket delete would destroy". The ownership figure is right; the
characterisation was not. Much of it is **test residue sitting ON the kept tenants** —
2,070 of the 2,095 `price_list_items` are not in a fresh database. The surgical plan was
protecting a mixture of seed data and litter, and I described the whole mixture as seed
data.

### `sunnycrest` holds nothing that matters

4 `agent_anomalies` and 1 user. The operator has not authored content into dev's
sunnycrest.

This is worth stating because `seed_sunnycrest.py` is *"strictly ensure-only,
preserve-aware… the tenant's CONTENT is the operator's to author… his authored work must
survive every future boot."* That docstring describes a real hazard — on **staging**, where
the tenant was created by hand. On dev it is empty, so the hazard does not apply here.
⚠️ **The same reseed against staging would be a different decision entirely.**

## 3. A correction: `default` IS seed-reproducible

The previous investigation recorded that `default` "has no established provenance —
nothing in `app/` or `scripts/` is recorded as creating it", and kept it on the
conservative side of the STOP.

It is created by **`alembic/versions/a2f3b4c5d6e7_add_multi_tenancy.py:48`** — a migration.
The scratch database has it after `alembic upgrade head`, before any seed ran.

⚠️ The failure was mine and it was an enumeration failure, not a search failure: I swept
`app/` and `scripts/` and never swept `alembic/versions/`. Migrations write data as well as
schema, and "what creates this row" has three homes in this repo, not two. The earlier
conclusion — keep it — was right by luck.

## 4. Does anything depend on dev holding its current state?

Nothing found, with the qualifications above:

- **Platform admin access** — the four accounts in §2, the one real dependency.
- The 430 doomed companies have no dependents; they are test output.
- The migration head matches, so no migration is mid-flight.
- No uncommitted fixture or scratch state was found referencing specific dev row ids.

⚠️ Not establishable from inside a session: whether anyone is mid-way through a manual
test, or is relying on a browser session bound to a dev tenant. That is James's to confirm.

## 5. What this does to the FK-order item

If re-seed is taken, the topological order **stops being urgent**. It was needed to delete
430 companies safely; a reseed deletes them by not creating them, with no ordering problem
at all, in 12 seconds.

It remains worth having for **test teardown at scale** — the 52-of-283 files that purge
today, and the per-run pattern from `tests/_ids.py`. That is a different job with a
different urgency, and it is not blocking anything. The 147-constraint cascade audit is
likewise unaffected and still worth doing on its own terms, because it reduces what any
future order has to encode.

## 6. Restore and reproduction

A pre-clean dump already exists, outside `/tmp` deliberately:

```
~/bridgeable-restore/bridgeable_dev-pre-litter-clean-20260923-070332.dump
5.0 MB, 3,694 objects, verified readable with pg_restore -l
```

The scratch database was dropped after measurement; recreating it is the 12.4 seconds
above.

---

# ADDENDUM — the reseed was applied, and my enumeration of "the seeds" was wrong

**2026-09-23, after the reseed.** Two STOP lines fired. Recorded here because the
investigation above is what authorised the action, and its central claim was incomplete.

## What happened

The reseed executed cleanly against dev: 492 tables, head `r185`, five tenants,
`platform_users` 0, app starts without the platform-admin env vars. Every STOP check in
the apply step passed.

Then the suite ran:

```
before reseed   43 failed | 6585 passed | 0 errors
after  reseed   90 failed | 6534 passed | 1 error
                +47 new failures, 3 gone
```

The 47 cluster in `test_briefing_vertical_terminology.py` and
`test_ai_question_prompt_terminology.py`. Cause:

```
intelligence_prompts            3 rows
intelligence_prompt_versions    3 rows
```

The seeded Intelligence prompt catalogue is not there.

## The defect: I enumerated "the seeds" as three

**There are 65 `scripts/seed_*.py`. I ran 3.**

`seed_staging`, `seed_fh_demo` and `seed_sunnycrest` build the *tenants*. The prompt
catalogue is built by a separate family — `seed_intelligence_phase2c`,
`seed_intelligence_followup2`, `seed_intelligence_phase6`, `seed_triage_phase8b`,
`seed_triage_phase8d1`, and others — none of which I ran or listed.

⚠️ **AND THE SCRATCH-DATABASE TEST INHERITED THE SAME OMISSION.** §1 above reports the
scratch DB as evidence that a reseed produces a working database. It ran the same three
seeds, so it demonstrated that those three succeed — not that the result is a working dev
database. The measurement was sound and the conclusion drawn from it was wider than the
measurement.

⚠️ `seed_dispatch_demo.py` is *named in CLAUDE.md §7* as part of testco's setup and I
missed it too, while reading that same section for the tenant list.

One command — `ls scripts/seed_*.py` — would have shown 65. This is the third enumeration
failure in this session and the first with a consequence: the `alembic/versions/` miss
produced a wrong provenance claim, this one dropped a database.

## STOP lines fired

1. **Row delta non-zero.** Companies went `5 → 435` across one suite run. The reseed
   reset the resident count; it did nothing about the per-run leak, exactly as predicted
   before the run — 231 of 283 company-creating files do not purge, and companies carry no
   run id. `platform_users` held at `0 → 0` with `deleted 81` reported, so Part 1's
   mechanism works.
2. **The company tripwire consequently cannot go absolute.** It fired on `5 → 435`, which
   is now a *true and useful* report rather than the silence it gave on a littered
   database. Part 3 is not attempted: an absolute condition would fail every run for a
   cause nobody can act on until companies carry a run id.

## Current state of dev

```
companies 435   users 442   platform_users 0
intelligence_prompts 3   products 26
```

Neither the old state nor a correct new one.

## Two ways out, not chosen

- **Restore.** `~/bridgeable-restore/bridgeable_dev-pre-reseed-20260923-074706.dump`
  (4.8 MB, 3,694 objects, verified readable) returns the pre-reseed database including the
  four platform accounts and the full prompt catalogue.
- **Forward-fix.** Run the missing seeds. ⚠️ **Which of the 65 constitute a correct dev
  seed is not documented anywhere I found**, and that absence is the underlying defect —
  it is why three looked like a complete answer. Establishing that list is the real
  deliverable, and it should be written down as an ordered, runnable sequence rather than
  reconstructed by the next session.

⚠️ Whichever is taken, the post-reseed baseline in this addendum is **not** a floor. It
was measured against an incompletely seeded database.
