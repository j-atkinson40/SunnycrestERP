# The local walk-throughs, and when each last ran green

⚠️ **THIS FILE EXISTS BECAUSE A WALK WENT RED FOR FIVE DAYS AND NOBODY KNEW.**
`5dd34500` ("PR C: the shell Susan gets — no sidebar") changed the shell an
area-limited user gets. `payroll-week44-walkthrough.spec.ts` asserted the
sidebar, died on its third assertion, and **checked nothing past that point
from 2026-11-18 to 2026-11-23** — the main walk for Susan's weekly payroll,
reporting a shell change as a payroll failure.

Nothing connected the two. The shell change was correct, the walk was correct
when written, and no instrument in the repo related them.

⚠️ **AND IT WAS REPORTED ONCE AS "PRE-EXISTING" BEFORE BEING FIXED.** "Fails
identically with and without my change" is true, and it answers *did I break
this* rather than *is this working*. CLAUDE.md §11's standing question — WHEN
DID THIS LAST PASS? — is owed to a walk the moment it goes red; here the answer
was a date and a commit, not noise.

## What the guard does, and what it deliberately does NOT do

These walks need two local servers, a seeded database and a real payroll export
that is not in the repository. **CI cannot run them, and pretending otherwise
would be the worse answer** — a job that cannot run is a channel that cannot
report.

So the guard is not "run the walks". It is: **nothing a walk depends on may
change without the walk being re-run.** Each entry below stamps a
**content hash of every file the walk depends on**, taken when it was last seen
green. `walk-freshness.test.ts` recomputes them and fails when any has moved,
NAMING the path.

On `5dd34500` that check goes red, because `limited-shell.tsx` is in the 5a
walk's dependency set — it would have fired on the PR that caused the problem.

⚠️ **HASHES, NOT COMMIT SHAs, AND THE FIRST VERSION USED SHAs AND CI CAUGHT
IT.** `git merge-base --is-ancestor` reads better and fails twice off a
laptop: `actions/checkout@v4` is shallow, so the stamped commits are not in the
clone (CI said so, correctly, by refusing rather than passing); and **this repo
squash-merges**, so a SHA stamped on a branch is unreachable from `main`
afterwards and the guard would have gone permanently red one commit after
landing. A hash over the bytes answers the same question and never asks about
history. `verified_at_commit` is kept as provenance for a human and is not an
input to the check.

⚠️ **NO TIME COMPONENT, DELIBERATELY.** A "re-run every N days" rule would go
red whenever nobody happened to run them, which is most weeks — and a check
that is usually red is the dark channel this file is about. The trigger is a
CHANGE, not a calendar.

## How to re-stamp

Run the walk, confirm it green, then:

    npm run walks:stamp            # prints the block
    node scripts/stamp-walks.mjs --write   # or rewrites WALKS.md in place

⚠️ **STAMP ONLY AFTER THE WALKS HAVE ACTUALLY RUN GREEN.** The script reads
bytes off disk and cannot know whether anybody ran anything, so this is the one
step a person has to mean. A stamp taken from a tree nobody walked is a green
check over an unverified surface — the exact condition the guard exists to
detect. The commit is read from `git rev-parse HEAD`, never typed.

    cd backend && python scripts/seed_week44_walkthrough.py     # prints week_id
    cd ../frontend
    PW_WEEK_ID=<the id it printed> PW_BASE_URL=http://localhost:5199 \
      PW_HOURS_PDF=~/Downloads/Payentry_Employee_Hours_2026-10-25_to_10-31.pdf \
      SECRET_KEY=... DATABASE_URL=postgresql://localhost:5432/note5a_clean \
      npx playwright test -c playwright.local.config.ts <walk>

⚠️ `PW_BASE_URL` is needed because vite binds IPv6 `localhost` while the config
defaults to `127.0.0.1`, which refuses the connection. `SECRET_KEY` and
`DATABASE_URL` are needed by the walks that shell out to the database — without
them those walks fail with a raw "Command failed", which reads as a product
failure and is a missing variable.

⚠️ The 5a walk ANSWERS a finding, so it is not repeatable without re-running
the seed. It says so when the finding is already answered.

## The walks

<!-- walks:begin -->
```json
[
  {
    "walk": "payroll-week44-walkthrough.spec.ts",
    "what": "Susan's week, start to finish: sign in, the note, both entrances, the finding, a correction, approve, the deduction list, the panes. Plus a real Employee Hours export through the real input.",
    "verified_on": "2026-11-23",
    "verified_at_commit": "3188424ebb87c21585c7e89be0dc2ce79e94e049",
    "fingerprints": {
      "src/App.tsx": "991b7ac4e5dd873bad9fa734e25ee4ab6c122447877cf2de1bee5b1d2d722b49",
      "src/components/layout/limited-shell.tsx": "768c5ddc6adc319d9065adc2471c3d44d816c8c2563e47689a2206840d397074",
      "src/components/layout/tenant-shell.tsx": "91b2f54ed5e5bd9f60adcfed4403f0c699c54f169cd48c02f2675fd4a258b5e5",
      "src/components/payroll/WeeklyPayrollCore.tsx": "170b2488dd7a187c77a4770325b8d36b63597e7f45e51b5659209d31b2535b5a",
      "src/components/payroll/panes/PayrollPaneStack.tsx": "d4d31133681d201c82d43f3deca9204935257669b29320d2b7294706ec368aba",
      "src/components/payroll/panes/VacationPaneBody.tsx": "baa400a5c1b6d6ada22b2b55d7cd79327c68406c26e9b106390fe77bf44dbba5",
      "src/components/payroll/panes/panes.tsx": "06c720cfab5bb57ae3464fb42377a25ae9cd0d84ee20e2ed31d30775fe79ba87",
      "src/lib/payroll/focus-api.ts": "140c12bd7a453e3927a3a5761e22eeec5572bdf8077bd78e2433d85257510eea",
      "tests/local/payroll-week44-walkthrough.spec.ts": "887e2a51fdc8e578d7f878aa6f0e0e97b2e155f3adeb6f55e6467b1ba63ae57b"
    }
  },
  {
    "walk": "opas-shell-walkthrough.spec.ts",
    "what": "The shell she gets and Opas as her only entrance: no sidebar, the sphere quiet, payroll-only capabilities, cmd-K.",
    "verified_on": "2026-11-23",
    "verified_at_commit": "3188424ebb87c21585c7e89be0dc2ce79e94e049",
    "fingerprints": {
      "src/App.tsx": "991b7ac4e5dd873bad9fa734e25ee4ab6c122447877cf2de1bee5b1d2d722b49",
      "src/components/layout/limited-shell.tsx": "768c5ddc6adc319d9065adc2471c3d44d816c8c2563e47689a2206840d397074",
      "src/components/layout/tenant-shell.tsx": "91b2f54ed5e5bd9f60adcfed4403f0c699c54f169cd48c02f2675fd4a258b5e5",
      "src/components/opas": "cf7cddfafca39d51d5b133419814948332749d94e4fd924beb9a1af547e985c1",
      "tests/local/opas-shell-walkthrough.spec.ts": "7ed54f8dc27e0ca863d7dc40529863c541f23970ef4a80f768c6d321d0e727c7"
    }
  },
  {
    "walk": "union-form-walkthrough.spec.ts",
    "what": "The R-115: filling to sent, the print view, the copies record, and a copy going stale underneath a figure.",
    "verified_on": "2026-11-23",
    "verified_at_commit": "3188424ebb87c21585c7e89be0dc2ce79e94e049",
    "fingerprints": {
      "src/components/payroll/UnionFormCore.tsx": "ee6b33022247d82100dc886c4dd51d052637361e200a285c477625b51ca44c35",
      "src/lib/payroll/focus-api.ts": "140c12bd7a453e3927a3a5761e22eeec5572bdf8077bd78e2433d85257510eea",
      "tests/local/union-form-walkthrough.spec.ts": "068f82b413439d00f2fd52a55051942d1482dc74bbddde4aaaffd54cdbb8acd1"
    }
  },
  {
    "walk": "employee-status-walkthrough.spec.ts",
    "what": "Recording an employee's payroll status, and the union form's line 1 coming off its check-counting fallback.",
    "verified_on": "2026-11-23",
    "verified_at_commit": "3188424ebb87c21585c7e89be0dc2ce79e94e049",
    "fingerprints": {
      "src/components/payroll/UnionFormCore.tsx": "ee6b33022247d82100dc886c4dd51d052637361e200a285c477625b51ca44c35",
      "src/components/payroll/panes/EmployeeStatusRow.tsx": "b46eceb5f4abe7c4f725ec7a928711d5df5b3a8ba5dd606293bada9d1ab0f908",
      "src/components/payroll/panes/PayrollPaneStack.tsx": "d4d31133681d201c82d43f3deca9204935257669b29320d2b7294706ec368aba",
      "src/components/payroll/panes/panes.tsx": "06c720cfab5bb57ae3464fb42377a25ae9cd0d84ee20e2ed31d30775fe79ba87",
      "src/lib/payroll/focus-api.ts": "140c12bd7a453e3927a3a5761e22eeec5572bdf8077bd78e2433d85257510eea",
      "tests/local/employee-status-walkthrough.spec.ts": "47c7d40455d76de59142f54834e29a6e6e07d7bdcc8c67d42d8ff0855695ceb5"
    }
  },
  {
    "walk": "vacation-pay-walkthrough.spec.ts",
    "what": "Vacation pay: the note line, the working with the rate's derivation (900.46 + 75.00 at a rate truncated to 4dp), approving both lines, and the line withdrawing afterwards.",
    "verified_at_commit": "3188424ebb87c21585c7e89be0dc2ce79e94e049",
    "verified_on": "2026-11-23",
    "fingerprints": {
      "src/components/payroll/VacationPayCore.tsx": "0a345ca7e9da0c2ffac328d03a37ef0757acb1b1c7dd862982ea79f993a2e528",
      "src/components/payroll/panes/VacationPaneBody.tsx": "baa400a5c1b6d6ada22b2b55d7cd79327c68406c26e9b106390fe77bf44dbba5",
      "src/lib/payroll/focus-api.ts": "140c12bd7a453e3927a3a5761e22eeec5572bdf8077bd78e2433d85257510eea",
      "src/pages/note/NotePage.tsx": "f09773b2350e5acf865653c0616a418ba92c7fbed6c4f8064535a35e683d5e7b",
      "tests/local/vacation-pay-walkthrough.spec.ts": "4911151e4dae7a0f35d22a52b34cd7cb4dc5a6e0b1472501b5490c8fbd79bf94"
    }
  }
]
```
<!-- walks:end -->

## Not walks, and deliberately not stamped

`focus-contrast.spec.ts`, `grey-contrast.spec.ts` and `dark-mode-probe.spec.ts`
are measurement harnesses, not walks: they photograph and measure rather than
asserting a journey, and they are re-run when a token moves. The guard's
membership check covers `*-walkthrough.spec.ts` only, which is the boundary it
states rather than one a reader has to infer.
