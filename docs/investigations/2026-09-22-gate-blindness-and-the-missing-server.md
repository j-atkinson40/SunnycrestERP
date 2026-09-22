# Was the gate blind where r185 lives?

**2026-09-22.** Two checks before pushing r185, and one strengthening.
**Part 1 fired, and was then closed empirically. Part 2's cause is
environmental. r185 is NOT pushed** — see the last section.

---

## Part 1 — yes, the gate was blind exactly there

### The 118 errors, grouped by what they raise

| cause | count |
|---|---|
| `httpcore.ConnectError: [Errno 61] Connection refused` | **117** |
| company-litter tripwire, at teardown of the session's last test | 1 |

Across three files: `test_audit_comprehensive.py` (76), `test_comprehensive.py`
(41), `test_zip_ambiguity.py` (1 — the tripwire, misattributed to an unrelated
test, as recorded in the gap map).

### ⚠️ Erroring tests DID cover the areas named

Both erroring files are HTTP integration suites:
`BASE_URL = os.environ.get("STAGING_URL", "http://localhost:8000")`. They call
the real API over the wire. Among the 117:

| erroring test | what it exercises |
|---|---|
| `TestPrograms::test_programs_personalization_get` | `GET /api/v1/programs/vault/personalization` |
| `TestPrograms::test_programs_personalization_pricing_mode` | `PATCH …/personalization` |
| `TestPrograms::test_programs_personalization_option` | `PATCH …/personalization` — the option/`applicable_product_ids` surface |
| `TestPrograms::test_programs_personalization_custom` | custom option create |
| `TestPrograms::test_programs_enroll` / `_products` | the enrollment row that holds `personalization_config` |
| `TestConfigurableItems` ×7 | the registry and tenant-override layer whose vocabulary this change replaces |

**That is the availability surface.** An erroring test asserts nothing, so the
change was unverified precisely where it matters. The STOP was correct.

### How it was closed

Nothing was listening on `:8000` and `STAGING_URL` was unset. A local backend was
started and the two files re-run:

```
114 passed, 3 skipped, 7 xfailed in 2.65s
```

**Zero errors, zero failures** — every personalization, configurable-item and
programs test now runs and passes *with this change in place*. The gap is closed
by measurement, not by argument.

---

## Part 2 — the cause is environmental, and it is not subtle

`117 / 118` errors are one exception: connection refused to
`http://localhost:8000`. These suites need a live server. One was running when
the `a2baa437` baseline was taken and is not running now — this session's own
task log shows background commands **"Start backend on the freed port"** and
**"Start a single frontend on 5173"** being killed.

Proof by restoration rather than by inference — full tree, server running:

| | failed | passed | errors |
|---|---|---|---|
| `a2baa437`, as quoted | 44 | 6,535 | 1 |
| this session, no server | 51 | 6,421 | **118** |
| this session, server up | **44** | **6,556** | **1** |

The numbers return to the `a2baa437` shape. `+21 passed` is exactly this work's
21 controls. **Not code.** No commit between `a2baa437` and `eecba049` is
implicated, and none needed to be bisected to show it.

⚠️ **"Pre-existing" was doing work it could not carry.** The in-session diff
(zero new, zero gone) was correct and was not evidence of coverage: 118 tests
were unchecked in both runs, so agreeing about them proved nothing.

---

## Part 3 — the round trip now compares what each task carries

The old proof compared task **sets**, which is why `{"symbol": "Cross"}`
degrading to the answer `other` passed it: still a `vinyl` task, set unchanged.

`v1_carried_values()` / `v2_carried_values()` read the value each task carries —
which symbol, which series — normalising vinyl symbols to their display label so
both sides are comparable whichever form v1 stored. Break-tested: removing the
display-form acceptance now turns the carried-value proof **red**, where the
set-only proof stayed green.

**The fallback is reported, never silent.** An unrecognised symbol still becomes
`other` with its original text preserved as free text, and now also increments
`unrecognised_symbol_count` and logs a warning naming the symbol. r185 prints the
count on the deploy log when it is non-zero.

**All eight display labels map to their ids** — asserted exactly, not sampled, so
the fallback is for genuinely unknown symbols rather than half the catalogue.

### `legacy_v1_options` — two rules, one enforced by a test

1. **Nothing but `to_v1` may read it.** It is a copy and goes stale the moment a
   migrated record's answers are edited; a later downgrade would restore the old
   choice and silently drop the edit.
2. **It is removed once r185 is confirmed on production.** Until then, no record
   carrying it should have its answers edited.

Rule 1 is enforced by `test_NOTHING_BUT_THE_DOWNGRADE_READS_legacy_v1_options`,
which enumerates from the AST across `app/`, `scripts/` and `alembic/` — **both
the literal and the constant**, because anyone reading it would sensibly use the
constant, which a literal search cannot see. Loads only; the definition is not a
use. Break-tested by adding a reader in another module.

---

## ⚠️ r185 IS NOT PUSHED

Part 1's instruction was *"If ANY does: STOP. Do not push."* Any did. The
blocker has since been removed — the area is now verified and clean — but the
condition as written was evaluated at enumeration time, and it failed then.

Pushing on the strength of my own remediation is a judgement about whether the
condition is satisfied, and r185 writes to production. That is James's to
release, not mine to infer. Everything needed is above; the push is one word.

**The local backend on `:8000` was started by this session and is still
running.** It is the thing whose absence produced the 118 errors, and leaving it
up keeps the suite honest.
