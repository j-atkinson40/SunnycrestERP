# Design — the Monday 6:00 Payentry pull (NOT BUILT)

Payroll 3 Phase 4. **Design only, by instruction.** Nothing in this document
is implemented. It is the first time Bridgeable would sign in somewhere using
James's own Payentry login, so the storage and use are reviewed before the code
exists.

Everything before this phase works from uploaded files, so the weekly Focus can
run on real hours either way.

---

## 1. What the job would do

A scheduled job, Mondays at 06:00 local, in the existing `PlaywrightScript`
seam (`app/services/playwright_scripts/base.py`). One script,
`payentry_time_reports`, with `service_key = "payentry"`.

```
sign in to Payentry Time Management
  -> Reports -> Employee Hours      -> download PDF  (last Sun..Sat week)
  -> Reports -> Punch Location      -> download XLS  (same week)
  -> hand both to the SAME parsers the upload uses
  -> store as two import batches, one per source_kind
```

The seam's contract is already the right shape:
`execute(inputs, credentials: dict[str, str])`. The job supplies
`{"week_end_date": ...}` as inputs and the credentials come from the secret
store — never from the database, never from a request.

⚠️ **ONE PARSER, NOT TWO.** `hours_import.import_hours` and
`punch_parser.parse_punch_location` take **bytes**, not a request. The pull
hands them exactly what the upload hands them, so there is no second code path
to drift. That was decided in Phase 3 for this reason.

---

## 2. The secrets it needs

James sets these himself in Railway. **They never pass through chat, a prompt,
a log line, a test, a commit or a response body.**

| secret | what it is |
|---|---|
| `PAYENTRY_USERNAME` | James's Payentry sign-in |
| `PAYENTRY_PASSWORD` | his password |
| `PAYENTRY_COMPANY_CODE` | the company selector, if the login asks for one |

Read with `os.environ` at the moment of use and passed straight into
`credentials`. Three rules the implementation must follow:

- **Never logged, never echoed, never put in a finding.** A failure says *which
  step* failed, never what was typed.
- **Never written to the database.** Unlike `Settings → External Accounts`,
  which stores per-tenant credentials, this is one human's personal login and
  it stays in the environment.
- **Absent means the job does not run.** Missing secrets are a declared skip
  with a reason, not an attempted sign-in with empty strings.

---

## 3. ⚠️ When Payentry asks for a code, the job stops

Payentry can challenge a sign-in with a one-time code. The job **cannot** and
**must not** try to satisfy that.

```
detect the challenge  ->  stop immediately
                      ->  log `payentry_pull_blocked_mfa` (no credential, no code)
                      ->  the weekly Focus shows Susan the upload card
```

The upload card is the fallback that already works: Susan downloads the two
reports and uploads them through `POST /weeks/upload`. So a challenged sign-in
degrades to the manual path that Phases 1–3 built, rather than to a week with
no hours.

⚠️ **The job must not retry a challenged sign-in.** Repeated automated
attempts against a payroll provider look like an attack on James's account and
can lock it — which would block the manual path too, turning a minor failure
into a payroll that cannot run.

---

## 4. ⚠️ Screenshots are the sharp edge in this seam

`PlaywrightScript._take_screenshot` writes the page to `/tmp` on failure, which
is right for a Uline order and **wrong here**. A Payentry Time Management page
shows names, hours, departments and pay. A failure screenshot taken after
sign-in is a payroll data leak onto the filesystem, in a directory nothing
cleans up, for a problem that does not need an image to diagnose.

The design: **no screenshots after the sign-in step.** If one is taken at all
it is on the login or challenge page only, before any employee data is on
screen — and even there the value is low, because the useful information is
"which step" and that is already in `PlaywrightScriptError.step`.

This is a change to how the seam is used, not to the seam, and it needs stating
in the implementation PR because the base class makes the unsafe thing the
convenient one.

---

## 5. What gets logged

**On success** — one audit row per import batch, the same shape the upload
writes:

```
payroll_hours_pulled   source_kind, week_end_date, filename, sha256,
                       rows_parsed, import_id, duration_ms
```

Plus the import batch's own stored `report`: findings, totals by pay type,
employee ids, anyone listed without hours. ⚠️ No employee names in the audit
row — the batch holds the detail and the audit row says a pull happened.

**On failure** — one row, naming the step and nothing else:

```
payroll_pull_failed          step, error class, duration_ms
payroll_pull_blocked_mfa     step="challenge", and the Focus card is raised
payroll_pull_skipped         reason="secrets absent"
```

⚠️ **A failed pull must not look like a quiet week.** If Monday 06:00 produces
no batch and no failure row, nothing distinguishes "the job never ran" from
"there were no hours" — so the job writes a row on every outcome including the
skip, and the Focus reads the absence of any row for the week as its own
finding.

---

## 6. What would still be open after building it

- **The week to pull.** The job assumes the Sunday–Saturday week that just
  ended. A Monday holiday, or a Payentry report not yet finalised at 06:00,
  would pull an incomplete week — and an incomplete week imports cleanly and
  looks fine. Worth a check that the pulled week's dates are all present
  before it is fed to a calculation.
- **Report-menu drift.** The navigation is to two named menu items. Payentry
  renaming or moving either breaks the pull, and the failure should name the
  step so it is obvious what changed rather than looking like a login problem.
- **Whether the pull should write a week at all**, or only store the raw
  batches and leave the week feed to a person. Phase 3's `import_hours` takes
  `write_week`, so both are available; the safer default for an unattended job
  is to store and not feed.
