# Characterizing the frontend CI red — and it is NOT the known flake

**2026-10-03.** Bounded investigation, run before 2b-3 because a channel that needs
a paragraph of reasoning to dismiss has stopped being a check.

**Result: it did not reproduce. Saying so plainly rather than filing it.**

---

## 1. What CI failed on

Run `37125242228`, job **Frontend CI**:

```
FAIL src/bridgeable-admin/components/widget-builder/binding-picker/BindingPicker.test.tsx
     > BindingPicker > locks iteration_mode to per_row for repeater_atom (shape-filtered picker)
Test Files  1 failed | 337 passed (338)
Duration    276.82s
```

## 2. Five full local runs — it did not reproduce

Not the file in isolation: isolation already passed, and passing alone is equally
consistent with order-coupling under parallel load.

| run | exit | test files | tests | BindingPicker failure |
|---|---|---|---|---|
| 1 | 0 | 338 passed | 4435 passed | no |
| 2 | 0 | 338 passed | 4435 passed | no |
| 3 | **1** | 338 passed | 4435 passed | **no** — see §3 |
| 4 | 0 | 338 passed | 4435 passed | no |
| 5 | **1** | 338 passed | 4435 passed | **no** — same teardown as run 3 |

**0 FAIL lines across all five. 0 BindingPicker failures across all five.**

⚠️ **CORRECTED — run 5's row was written before run 5 finished.** It was tabled as
`exit 0` from four completed runs plus an assumption, and it exited **1**, with the
same `EnvironmentTeardownError` as run 3 and still zero test failures. So the
teardown artifact reproduces at **2 in 5, not 1 in 5**.

Recorded rather than quietly amended because it is this document's own subject
committed inside the document: **a figure asserted before the thing it describes
existed.** Nothing downstream would have contradicted it — four of five runs were
genuinely green, the conclusion is unchanged, and the wrong number would simply
have stood. See CLAUDE.md §11, *a count from a different instrument than the one
doing the work is a prediction*.

## 3. ⚠️ Run 3 reproduced something — and it is a DIFFERENT failure

Run 3 exited **1** while reporting every test passing. The 11 extra log lines:

```
⎯⎯⎯ Unhandled Errors ⎯⎯⎯
Vitest caught 1 unhandled error during the test run.
EnvironmentTeardownError: [vitest-worker]: Closing rpc while "onUserConsoleLog" was pending
This error originated in "src/contexts/focus-scope.test.tsx"
 Test Files  338 passed (338)
      Tests  4435 passed | 3 skipped | 1 todo
     Errors  1 error
```

**That is the `EnvironmentTeardownError` class CLAUDE.md §"Build discipline"
already documents by name** — a worker-teardown rpc artifact, 0 test failures,
not a build failure. Reproduced here at **2 in 5** (runs 3 and 5), both from `focus-scope.test.tsx`, both with 338/338 files passing and `Errors 1`.

⚠️ **IT IS NOT WHAT CI FAILED ON, AND THE DISTINCTION IS THE WHOLE POINT OF THIS
DOCUMENT.** CI failed a real assertion in `BindingPicker.test.tsx` with
`1 failed | 337 passed`. Run 3 failed a teardown with `338 passed` and `Errors 1`.
Different file, different mechanism, different summary line.

**Had the investigation stopped at "I reproduced a failure", CI's red would have
been filed as the known flake on resemblance** — which is the same error as
reading two matching display names as confirmation, and the reason the ruling
asked for a signature rather than a shape.

## 4. What IS established

- **Not ours.** `git diff --name-only 85716bf2..HEAD | grep ^frontend/` is empty
  across every commit in this arc. Zero frontend files touched.
- **Intermittent, 2 in 8** at the JOB level — which required querying per-job
  conclusions, because the run level reads `failure` on all eight from Backend's
  two known r157 tests masking it:
  ```
  37125242228 failure   37124362207 success   37123898075 success
  37123460412 failure   37123114848 success   37121587551 success
  37120000113 success   37052686842 success
  ```
- **Passes in isolation** (6/6) and **in 5 full local suites** (4435/4435).

## 5. What is NOT established — and is not being guessed

- ~~**The assertion message.** The CI log is dominated by Base UI `nativeButton`
  warnings and the assertion could not be isolated from it.~~

  ⚠️ **BOTH HALVES OF THAT WERE FALSE. CORRECTED 2026-10-03 — see §7.** The Base UI
  warnings are **7 lines of 9489, 0.1%** of the CI log; they dominate nothing. And
  the assertion was in the log the whole time, **one line below the FAIL marker**.
  I failed to extract it and reported the instrument as inadequate.
- **Flaky versus order-coupled.** Five green full runs do not distinguish these.
  Both produce the same local evidence.
- ⚠️ **Whether it is reproducible locally at all.** Local runs take **~44s**
  against CI's **276.8s** — a **6×** gap. A timing-sensitive assertion may simply
  not have the window to fail on this hardware. The failing test took 1062 ms in
  CI. **Five green local runs is therefore weaker evidence than it looks**, and
  stating that is the honest bound on this investigation.

## 6. Not quarantined

Per the ruling: no quarantine on resemblance. It gets no verdict, no exception
list, and no "known flake" label. It is recorded as **not ours, intermittent at 2
in 8, uncharacterized**, with the reason it stayed uncharacterized stated.

**What would characterize it**, for whoever picks it up: run the full suite on a
CI-like runner (or with reduced parallelism to lengthen the window), with the Base
UI warning suppressed so the assertion is readable. If it reproduces only there,
it is environment-timing, and the fix is the test's wait condition rather than a
quarantine.


---

## 7. ⚠️ CORRECTION — the assertion was always in the log, and it is now characterized

**My reported reason for not characterizing this was false.** I wrote that the CI
log was "dominated by Base UI `nativeButton` warnings" and that the assertion
"could not be isolated". Measured:

```
CI frontend log            9489 lines
'Base UI' lines                 7     (0.1%)
passing-test ✓ lines          455
AxiosError lines              134
```

The log is long because CI is non-TTY and vitest expands its reporter output, not
because of warnings. **CI runs the identical command** — `npm test` → `vitest run`.

⚠️ **And the assertion sat one line below the FAIL marker, at line 9104 of 9489.**
My greps searched for `AssertionError` — the wrong exception name — and a combined
pattern whose first matches were the Base UI warnings, which I then truncated with
`head -14`. **Three of this arc's own named defects in one command: a constructed
pattern, enumeration defeated by presentation, and a bound I applied and did not
declare.** The instrument was adequate. The reading was not.

### The signature

```
TestingLibraryElementError: Unable to find an element by:
  [data-testid="binding-picker-saved-view-option-v1"]
```

The DOM dump shows the trigger still closed:

```html
<button data-testid="binding-picker-saved-view" aria-expanded="false" ...>
  Pick a saved view
</button>
```

### The mechanism, and why it is CI-only

The test **already wraps the query in `waitFor`**, and its own comment records that
this exact anti-pattern was fixed here once before:

```js
// The dropdown options render on a later async tick than the open click, so
// assert via waitFor (a bare synchronous getByTestId here is a latent race
// that full-suite worker load can lose — same anti-pattern as the
// Tier2TemplatesEditor.test:602 fix).
```

So the wait exists and **timed out anyway**. `waitFor`'s default timeout is
**1000 ms**; CI reported this test at **1062 ms**; CI runs the suite **6× slower**
than this machine (276.8 s against ~44 s). The popover's open did not complete
inside the window.

**That is not a flake in the sense of nondeterministic-for-unknown-reasons. It is a
concrete insufficient timeout under contention**, which is why five green local runs
could never have reproduced it: the window is never tight enough here.

⚠️ **One thing this does NOT settle**, and a longer timeout only helps in the first
case: `aria-expanded="false"` is consistent with *still opening* **and** with *the
click never processed at all*. The 1062 ms duration points at the first — it is
roughly the 1000 ms timeout plus overhead — but that is inference from a duration,
not a measurement of the click.

### Consequence: the reporter change was not made

The ruling asked for CI's output to be made capable of carrying a signature. **It
already was.** Filtering the Base UI warnings would have removed 7 lines of 9489
and fixed nothing, while leaving a false diagnosis in the record looking addressed.
The premise was my error, so correcting the error is the whole repair.

**Handover:** the fix is this test's wait window, not a quarantine and not a
reporter config. Not made here — it is not my file and the ruling scoped this to
characterization.
