# The Playwright channel has been dark for 99 runs

**Date:** 2026-09-04 · **HEAD:** `543a9c5c` · **Read-only — no code changed.**

Found while running the sweep the operator asked for before note-arc session 1
lands anything. The sweep is not a gate. It has produced no green result in the
entire recorded history of the workflow.

---

## 1. The measurement

`gh run list --workflow=playwright-staging.yml --limit 100`:

| | |
|---|---|
| Completed runs examined | **99** |
| Successes | **0** |
| Failures | **99** |
| Oldest run in range | **2026-07-28** |
| Most recent green | **none in range** |

Unit note: these are workflow *runs*, counted from the JSON `conclusion` field,
not lines of `gh run list` output.

The run for `d50094de` fired automatically on push and was still in progress at
the time of writing; every completed run before it failed.

---

## 2. The cause is singular

From run `33797881778` (`--log-failed`):

```
Error: Platform admin login failed: 401 {"detail":"Invalid email or password"}
```

Every spec in all three jobs — Maps of Content, runtime-editor, Claude-API e2e
— fails at authentication, before exercising anything. Failures are ~400ms
each, which is the shape of an auth rejection rather than a test.

⚠️ **What is NOT established:** whether the stored password is stale or the CI
bot PlatformUser is absent from staging entirely. A 401 is consistent with
both, and staging's database was not queried. The remedy in §4 covers both, so
the distinction did not need resolving to act — but it is not known, and should
not be reported as known.

---

## 3. Why it will not self-heal

CLAUDE.md §7 documents the rotation procedure and its failure mode: "Failing to
update the secret invalidates the Playwright CI run on next push." That is
exactly what is observed.

What the procedure does not say is that **nothing re-creates the bot**:

- `backend/railway-start.sh` runs `alembic upgrade head`, then
  `seed_staging.py --idempotent`, then `seed_fh_demo.py --apply --idempotent`,
  then uvicorn. It does **not** run `provision_ci_bot`.
- `seed_staging.py` contains **zero** references to `ci-bot`, `ci_bot`, or
  `PlatformUser` (grep over the file; zero hits).

So the credential the entire Playwright gate depends on is created by a
one-time manual script, lives in GitHub Secrets, and is re-created by no deploy
path and no seed. Any staging database reset, or any rotation not mirrored into
Secrets, ends the channel permanently and silently.

**This is the "complete machinery behind an unprovisioned entrance" shape
(CLAUDE.md §11), at the CI layer.** Three jobs, 54 spec files, a deploy-gate
poll that waits for the right SHA, trace and screenshot upload on failure — a
fully built gate whose authentication has no provisioning path.

---

## 4. Remedy — requires operator authorization, not performed here

1. `python -m scripts.provision_ci_bot --rotate` against staging, capturing the
   new password.
2. Update `STAGING_CI_BOT_PASSWORD` (and `STAGING_CI_BOT_EMAIL` if it moved) in
   GitHub Secrets, in lockstep.
3. Re-run the workflow via `workflow_dispatch`.

Not performed by the investigator: this rotates a live credential and writes a
repository secret. Both are operator actions.

**Durability fix, separate and worth its own decision:** either add
`provision_ci_bot --ensure` to `railway-start.sh` alongside the two seeds, or
have `seed_staging.py` ensure the bot PlatformUser. Without one of these, the
next staging reset reproduces this exactly, and the next detection will again
be incidental.

---

## 5. ⚠️ What this invalidates

Per CLAUDE.md §11, *Saturated signal*:

> A CI channel red for N consecutive runs on a known cause is dark for those N
> runs, and the window's length is not knowable from inside it. When such a
> channel is repaired, the first green run is a BASELINE, not a confirmation —
> everything that landed during the dark window remains unverified by that
> channel regardless of what the first run says.

N is at least 99, spanning 2026-07-28 to 2026-09-04 — **five and a half weeks.**
Everything merged in that window is unverified by Playwright. That includes the
entire Sales & Orders campaign, the RingCentral work, and the fragment
contract.

**And the premise was load-bearing in dispatches.** Build dispatches through
this period instructed "Run the full gated suite plus Playwright and Claude API
end-to-end tests" as a gate. For at least 99 runs that instruction asked for a
signal that could not be produced. The instruction was not wrong when written;
it expired, and nothing announced the expiry — CLAUDE.md §11, *Expired
premise*.

⚠️ **The pytest gate is unaffected and remains real.** It runs in
`.github/workflows/ci.yml` against a fresh Postgres, it has been exercised
throughout, and the 2243-passing figure from the fragment contract commit
stands. This finding is scoped to the Playwright channel only. Nothing here
argues the backend gate was compromised.

---

## 6. How this was found, and how it was not

It was found by running `gh run list` before claiming a Playwright number —
prompted by the operator's instruction to run the sweep independently before
session 1.

It was **not** found by:

- the workflow failing, which it did 99 times, loudly, with traces uploaded;
- any dispatch, several of which named Playwright as a required gate;
- this investigator, who declined to run Playwright pre-push on the correct
  grounds that staging served the pre-change bundle — correct reasoning that
  would have kept the channel's death hidden one more cycle, because it stopped
  short of asking whether the channel worked at all.

The near-miss is the reusable part. "Do not report a green with no contact with
the change" prevented a false claim, and would have gone on preventing anyone
from noticing that no claim was possible. **A reason not to read an instrument
is not a reason to assume it works.**

---

## 7. What the record actually claimed — enumerated 2026-09-04

The operator's question: dispatches named Playwright as a required gate through
the dark window, so did session reports (a) claim a number that did not come
from Playwright, (b) omit it unnoticed, or (c) run it against a different
target? Case (a) would be a false claim in the record needing correction more
urgently than the credential.

**Answer: (b), cleanly. There are no false Playwright claims in the record.**

### Commits

252 commits since 2026-07-28. **6** mention Playwright in their bodies (bodies
grepped per-commit, counted as commits, not as matching lines):

| Commit | Date | What it claims |
|---|---|---|
| `6b9a9b70` | 09-04 | this investigation |
| `d50094de` | 09-04 | explicitly NOT run, with the reason |
| `2d749ad1` | 09-03 | e2e Close **skipped on purpose**, with the reason |
| `f16482a4` | 08-25 | about coverage documented before it existed |
| `b7fd25f6` | 08-25 | incidental — dependency pinning example |
| `799e2859` | 08-04 | incidental — untracking screenshots |

**Zero claim a pass.**

### STATE.md

171 occurrences of "Playwright" (occurrences, not lines). Restricting to
entries dated on or after 2026-07-28 leaves **4** lines, of which:

- **`STATE.md:860`** (from `2d749ad1`, 09-03) — the only genuine in-window
  claim, and it is honest: *"THE CLOSE WAS INCOMPLETE BY CHOICE... The
  dispatch's staging seed + Playwright/Claude-API run was not performed."*
- **`:1051`, `:1058`, `:1067`** — sit under `## Active deferred items`, an
  undated section. All three were introduced by `8504f924` on **2026-05-13**,
  ten weeks before the window opened.

⚠️ **A false accusation was nearly made here, and the near-miss is the
methodological point.** `:1067` reads *"53 of 56 Playwright gates pass"* — a
specific pass count, which under the first pass of this analysis appeared to be
an in-window false claim. It is not. The date attribution came from a script
that carried the last-seen dated bullet downward, and the nearest such bullet
was 634 lines above, in an unrelated September entry. `git log -S` on the
literal string returned 2026-05-13.

The claim is **stale, not false** — accurate when written, never revised, and
sitting in a section whose entries carry no dates of their own. Reporting it as
a September falsehood would have put a fabricated integrity finding into the
record while investigating an integrity finding.

The generalisation: a date inferred from document position is a constructed
name. `git log -S` is the enumeration.

### The sub-finding that matters more than the answer

`STATE.md:860` recorded, on 2026-09-03, that *"Playwright had failed six
consecutive runs on an unchanged `STAGING_CI_BOT_PASSWORD`."*

Every clause is correct except the count, which was **six against an actual ~95**,
and the classification. The credential was already correctly identified as the
cause. What was not asked was when the channel last passed — and the answer,
never, would have converted "a known red to skip around" into "a gate that has
never worked," which is a different finding with a different urgency.

So the channel's death was detected six days before this investigation,
recorded honestly, and under-scoped by a factor of sixteen because the
last-pass question was not part of the check. That is the entry now landed in
CLAUDE.md §11 as *Absent signal*.

