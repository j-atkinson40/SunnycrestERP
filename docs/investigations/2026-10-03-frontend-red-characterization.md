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
| 5 | 0 | 338 passed | 4435 passed | no |

**0 FAIL lines across all five. 0 BindingPicker failures across all five.**

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
not a build failure. Reproduced here at **1 in 5**.

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

- **The assertion message.** The CI log is dominated by Base UI `nativeButton`
  warnings and the assertion could not be isolated from it. A test name plus a DOM
  dump is not a signature and does not qualify for quarantine.
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
