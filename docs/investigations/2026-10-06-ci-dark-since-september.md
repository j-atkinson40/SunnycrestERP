# CI has been dark since 2026-09-23 — 42 runs, 89 commits

**Measured 2026-10-06, after pushing eleven commits into it without looking.**

## The numbers

| | |
|---|---|
| last CI success | **2026-09-23T15:00:16Z**, sha `fc78b587` |
| runs since | **42**, none successful |
| commits on `main` since | **89** |
| successes in the last 200 runs | 86 — so the channel *worked*, then stopped |

⚠️ **This is a SATURATED signal, not an absent one.** It passed 86 times and has
been red for 42. CLAUDE.md §11 draws that distinction and it matters here: there
is a known-good baseline to return to, and the history is readable.

## ⚠️ The failure I should have reported eleven commits ago

I pushed eleven commits today, each with a "VERIFIED" line in its body, and every
one of those lines is true of a **local** run. None was true of CI, because CI
could not have told me — an already-red check cannot report a new failure.

**The question that would have caught it is the one CLAUDE.md §11 says has no
natural trigger: *when did this last pass?*** I asked it only when a deploy failed
to appear, which is the entry's own prediction of how it goes wrong: a broken
instrument produces the same silence as a healthy one nobody consulted.

## What is actually failing, and it is not today's work

Both halves fail, on areas untouched today (26 files changed, **0** in either):

**Backend CI** — `tests/test_map_accounting_content_r157.py`, two tests in
`TestTheGuardProtectsOperatorEdits`:
`test_a_partial_ref_deletion_is_NOT_refilled_by_the_seed` and
`test_rerunning_is_idempotent`.

⚠️ **They PASS LOCALLY** — 13/13 in that file. So this is the
environment-divergence class §11 names: CI runs migrations then pytest with **no
seeds**, while a local database is seeded, and a test whose subject is a *seed
guard* is exactly the kind that would diverge. **That is a hypothesis, not a
finding** — I have not established the cause, only that the two environments
disagree.

**Frontend CI** — axios `Network Error` in runtime-editor tests. Also untouched
today. Cause not established.

## What this does and does not invalidate

**Does not:** the local runs happened and their numbers are real. Migrations
round-tripped, drift checks passed, tsc and vitest ran clean locally.

**Does:** every claim of the form "CI is green" — I made none, which is the only
reason this is a process failure rather than a false claim. But eleven commits
went out with no independent check, and the one that carried a production
migration (r198) went out the same way.

⚠️ **And the deploy is gated on CI**, which is why r198's head still reads
`r197_capture_answered_fields` in production. The migration has not run and will
not until CI is green — so the dark channel is now blocking a merge, not merely
failing to observe one.

## Owed

1. **Fix or quarantine the two backend tests**, with their exact failure
   signature recorded — a quarantine without one is a saturated signal by policy
   (§11).
2. **Diagnose the frontend network error.** `Network Error` in a test suite
   usually means an unmocked client; it is not obviously environmental.
3. **Then re-read the deploy head**, because r198 is waiting behind it.

## Method note

Enumerated the full 200-run history rather than the default page. ⚠️ My first
pass reported "no success in the last 40 runs" from an `awk` over 40 rows and I
nearly wrote "no success ever" — there are 86. The dark window is 42 runs, and
the figure came from finding the last success and counting forward, not from the
first screen.
