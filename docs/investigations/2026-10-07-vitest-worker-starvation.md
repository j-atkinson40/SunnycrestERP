# The vitest flake: worker starvation, memory exhaustion, and one lost dataset

**Status: STUB. The per-run dataset is LOST and is NOT reconstructed here.**
Written 2026-10-12. Measurements were taken 2026-10-07.

⚠️ **PROVENANCE IS MARKED PER CLAIM.** Everything below is either `COMMITTED` — it
was written into `STATE.md` on the day and survives in git — or `LOST`. Nothing is
restated from memory. CLAUDE.md §11 *Reconstruction recovers errors first*: a
reconstruction that reads as cleanly as the original is the more dangerous
artifact, so this file is a stub naming what it covered and what a re-run must
produce.

## What was lost, and why

⚠️ **64 run logs, a results table, and two measurement scripts were written to the
session scratchpad under `/private/tmp/` and are gone.** Five days passed and the
directory rotated. The surviving directory holds one empty `v2/`.

This is the exact failure CLAUDE.md records TWICE — once as the rule
("Investigation output written to /tmp is destroyed at the next boot… go to
`docs/investigations/` and are committed"), and once as the reason the rule was
moved out of DECISIONS into CLAUDE.md after a second loss happened underneath it.
**It has now happened a third time, to the author of the paragraph above.** The
rule was known, correct, and not followed, because the scratchpad is where the
tool points and committing an investigation artifact was never the next thing to
do. See CLAUDE.md §11 *a rule that is read and violated is placed wrong, not
worded wrong*.

What was mitigated: the numbers that drove the conclusion were written into
`STATE.md` the same day, so the conclusion remains auditable. What is gone is the
per-run table — 64 rows of (arm, run, exit, load average, duration, file total,
test total, errors) — which is the only thing that could have supported a
*quantitative* claim about caps. No such claim was made, which is the one piece of
luck here.

## COMMITTED findings

**The mechanism, in vitest's own words.** One run reported:

    Test Files  338 passed (338)
         Tests  4493 passed | 5 skipped | 1 todo (4499)
        Errors  6 errors
      Duration  962.33s
    Error: [vitest-pool]: Failed to start forks worker for test files …
    Caused by: Error: [vitest-pool-runner]: Timeout waiting for worker to respond

962 seconds instead of ~50; **six test files never ran**; `338 passed (338)`
presents the shrunken count as the total. Baseline that day: 344 files / 4549
tests. Only a separately-recorded expected total caught it.

**The first experiment was invalid by design.** Arms ran SEQUENTIALLY — 20×cap4
(14:28–14:50), 20×cap6 (14:50–16:09), 20×default (16:09–17:28) — and duration
degraded monotonically across that window regardless of arm. cap6's first nine
runs were the fastest in the whole experiment (53–64s); its last two the worst
(898s, 1026s). Arm and wall-clock were perfectly confounded.

**The cause is memory, not a cap.** A round-robin redesign returned a **999.04s
cap4 run** from a settled load average, where cap4 had been 20/20 clean at 59–83s
hours earlier. Measured on the host: 4263 of 5120 MB of swap consumed, ~223 MB of
pages free, 8.2 GB in the compressor, 29 days of uptime, and
`pmset -g therm` recording no thermal warning. Each worker is a forked Node
process carrying a jsdom environment; forking one against a swapping machine is
what the pool timeout reports.

**Run-to-run variance at a FIXED cap: 46.59s to 999.04s — 21×.** An order of
magnitude larger than any plausible cap effect. No cap was proposed, and the
round-robin run was stopped after one run rather than spending two more hours
producing an authoritative-looking number.

## LOST

- The 64 per-run rows (arm, run index, exit code, 1-minute load average, duration,
  file total, test total, error count, failing test names).
- The names of five of the six files that failed to start workers.
  ⚠️ `HierarchicalEditorBrowser.test.tsx` survives because it was quoted in
  `STATE.md`. `root-redirect.test.tsx` was named only in a chat message, which is
  not a durable artifact, and is therefore recorded here as RECALLED, NOT MEASURED.
- The distribution of failing test names across the nine default-arm runs that had
  assertion failures. Roughly thirty distinct failures with little repetition was
  the shape; **the exact set is gone and the word "roughly" is doing real work.**
- `measure.sh` and `measure2.sh`.

## What a re-run must produce

1. A host with memory to spare — reboot first; 34 days of uptime and 77% of swap
   consumed was the state as of 2026-10-12.
2. **Round-robin** the arms (one run of each per round), never arm-at-a-time.
3. A **settle** step before each run on the 1-minute load average.
4. **Per-run positive controls: the file total and the test total**, recorded for
   every run. The 962s run is green on every other reading.
5. The results table written **into this directory and committed**, not to a
   scratchpad.

## What was built instead

`frontend/scripts/assert-suite-size.mjs` + `frontend/fixtures/suite-size.json`: a
committed floor on the file and test totals, asserted in frontend CI with
`if: always()`. It cannot diagnose starvation, and it is not meant to — it makes a
run that tested less than it claims unable to pass. See the commit that adds it for
the seven break tests, including the one that matters: six real files excluded,
`vitest` exits **0** with `Test Files 339 passed (339)`, and the guard exits 1.
