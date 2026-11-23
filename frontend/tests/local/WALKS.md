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
change without the walk being re-run.** Each entry below stamps the commit the
walk was last seen green at, plus the files it depends on.
`walk-freshness.test.ts` fails when a dependency has commits the stamp does not
contain, and NAMES them.

On `5dd34500` that check would have gone red on the PR that caused the problem,
because `limited-shell.tsx` is in the 5a walk's dependency set.

⚠️ **NO TIME COMPONENT, DELIBERATELY.** A "re-run every N days" rule would go
red whenever nobody happened to run them, which is most weeks — and a check
that is usually red is the dark channel this file is about. The trigger is a
CHANGE, not a calendar.

## How to re-stamp

Run the walk, confirm it green, then put the commit you ran it at in
`verified_at`. ⚠️ **READ THE SHA FROM `git rev-parse HEAD`. Never type or
construct one** — that rule has been broken twice, five days apart.

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
    "verified_at": "86fe0e1224737fd79a0ecd99bc5935cccfb06bca",
    "verified_on": "2026-11-23",
    "depends_on": [
      "src/components/layout/limited-shell.tsx",
      "src/components/layout/tenant-shell.tsx",
      "src/components/payroll/WeeklyPayrollCore.tsx",
      "src/components/payroll/panes/panes.tsx",
      "src/components/payroll/panes/PayrollPaneStack.tsx",
      "src/lib/payroll/focus-api.ts"
    ]
  },
  {
    "walk": "opas-shell-walkthrough.spec.ts",
    "what": "The shell she gets and Opas as her only entrance: no sidebar, the sphere quiet, payroll-only capabilities, cmd-K.",
    "verified_at": "86fe0e1224737fd79a0ecd99bc5935cccfb06bca",
    "verified_on": "2026-11-23",
    "depends_on": [
      "src/components/layout/limited-shell.tsx",
      "src/components/layout/tenant-shell.tsx",
      "src/components/opas"
    ]
  },
  {
    "walk": "union-form-walkthrough.spec.ts",
    "what": "The R-115: filling to sent, the print view, the copies record, and a copy going stale underneath a figure.",
    "verified_at": "86fe0e1224737fd79a0ecd99bc5935cccfb06bca",
    "verified_on": "2026-11-23",
    "depends_on": [
      "src/components/payroll/UnionFormCore.tsx",
      "src/lib/payroll/focus-api.ts"
    ]
  },
  {
    "walk": "employee-status-walkthrough.spec.ts",
    "what": "Recording an employee's payroll status, and the union form's line 1 coming off its check-counting fallback.",
    "verified_at": "86fe0e1224737fd79a0ecd99bc5935cccfb06bca",
    "verified_on": "2026-11-23",
    "depends_on": [
      "src/components/payroll/panes/EmployeeStatusRow.tsx",
      "src/components/payroll/panes/panes.tsx",
      "src/components/payroll/panes/PayrollPaneStack.tsx",
      "src/components/payroll/UnionFormCore.tsx",
      "src/lib/payroll/focus-api.ts"
    ]
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
