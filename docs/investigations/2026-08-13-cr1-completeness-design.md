# CR-1 — the completeness review: design

**Status:** design, not built. Written 2026-08-13, after the period-closure
projection (`17b765c4`, `d8e8ccbf`) made the window expressible.

**Why this file exists at all.** CR-1's rulings were made in conversation and
recorded nowhere. A CR-1 investigation earlier this week read a STATE line that
had been true on 2026-08-05, was fixed since, and was never marked — and reported
a closed defect as a live blocker. Rulings that live only in a transcript are the
same hazard one layer up. So they are written here first.

---

## 1. The question

> For this period, did everything that was supposed to arrive, arrive?

Not "what did we receive" — that question can always be answered and is never
alarming. The whole value is in naming what is *absent*, and absence is not in
the data by construction.

## 2. The three rulings

### 2a. Expectations are DECLARED, not learned

A learned baseline ("we normally get twelve invoices from Hopkins") cannot
distinguish **they stopped sending** from **they never sent**. Both read as a
low number against a thin history, and a brand-new obligation has no history at
all — so the case where you most need the alarm is the case the model is
quietest about.

This is the week's recurring defect in another costume. `drafts_generated`
returned `0` for a key that did not exist, and a gate read that zero as *none*
when it meant *absent*. A declared expectation makes the same distinction
structural: the row exists whether or not anything arrived against it.

### 2b. People are sources

Completeness is not only a machine property. A month is incomplete if the
production manager never filed the pour log, exactly as it is if an integration
never posted. Modelling only system-to-system flows answers a smaller question
than the one being asked, and answers it reassuringly.

### 2c. A source is a ROLE'S OBLIGATION — not a person, not a workflow

- **Not a person.** People leave. An obligation attached to `user_id` disappears
  with the account, and the gap it was guarding goes quiet at the exact moment
  turnover makes it most likely.
- **Not a workflow.** A workflow is the *mechanism*, not the duty. r163 deleted
  the Social Service Certificate workflow three days ago; the certificate is
  still owed, still generated, still service-owned. Had the obligation been
  modelled as "this workflow runs," deleting the workflow would have deleted the
  expectation — and the deletion would have looked like completion.

So: **whoever holds role R owes deliverable D for period P by date T.** Roles
survive staffing changes and mechanism changes, which is the point.

## 3. Why the window had to come first

Completeness is only meaningful against a window that can be *final*. Before this
week, `closed` was half-true — the button stopped journal entries and left every
AR path writing — so "nothing else is coming" was not a fact the system could
state. Now:

| period state | what completeness means |
|---|---|
| `open` | provisional — a gap may still fill |
| `partially_closed` | mixed, and the locked days are reportable |
| `closed` | final — a gap is now permanent |

The same refusal to collapse three states into two applies here, for the same
reason: "incomplete but still open" and "incomplete and shut" are different
facts, and merging them either cries wolf or misses the wolf.

## 4. The design constraint the week earned

**The output is a list of EXPECTATIONS, each with a verdict — never a list of
what arrived.**

Twice on 2026-08-13 the signal died in tolerant code:

- `PERIOD_BADGE[status] || PERIOD_BADGE.open` rendered a partly-locked month as
  fully open, silently, with its actions gone.
- The mirror seed logged `not found — skip` and carried on; only an expected
  *total* made an incomplete deletion fail out loud.

**The graceful path is where the signal dies.** Both were caught by something
that insisted on a number. So CR-1 must not have a graceful path: a missing
deliverable produces a ROW with a `missing` verdict. There is no branch in which
nothing is emitted.

## 5. Four verdicts, not two

`arrived` · `partial` · `missing` · `not_yet_due`

`not_yet_due` is load-bearing and is the one a two-state design would eat. A
deliverable due on the 20th is not missing on the 5th, and reporting it as
missing trains operators to ignore the report — which is a slower version of not
having it.

## 6. Shape (sketch — not ratified)

- `completeness_expectation` — the declaration: `role_slug`, `deliverable_kind`,
  `cadence`, `due_day_offset`, scope (`vertical` / `tenant_id`), `is_active`.
  Authored, not inferred. Deleting the mechanism must not delete the row.
- `completeness_observation` — what satisfied it: `expectation_id`, `period`,
  `satisfied_at`, `satisfied_by`, evidence ref.
- The review is a LEFT JOIN from expectation to observation over a period. The
  join direction is the design: expectations drive, observations decorate.

## 7. Open questions for the build

1. **Who authors expectations?** Platform-default per vertical, tenant-override
   — the three-scope pattern used by themes, workflows and documents — or
   tenant-only? Defaults make it useful on day one; over-declaring makes it
   noisy on day one.
2. **What counts as satisfying a human obligation?** A filed pour log is
   evidence; "the manager says they did it" is not. Needs a rule before build.
3. **Does a `closed` period freeze its verdicts?** Probably yes — a permanent
   gap is a fact worth keeping — but that is a ruling, not a default.

## 8. What CR-1 is NOT

Not an alerting system, not a nag, and not a second place where a period's state
is decided. It READS `period_locks` through the projection like everything else.
A completeness review that kept its own idea of whether a period was closed would
be the exact defect this week was spent removing.
