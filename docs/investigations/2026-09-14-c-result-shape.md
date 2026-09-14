# Item (c) — the result shape

**Date:** 2026-09-14 · **Design, not built.** Follows the survey
(`2026-09-14-c-natural-unit-survey.md`) and the rulings of the same date:
Option C, `completed_with_errors`, boundary marked, `generate_draft_invoices`
included.

Population: **13** — the 12 swallowing targets plus `generate_draft_invoices`,
which joins on a different basis (its `-> None` annotation forecloses all three
states regardless of how failures travel).

---

## The shape

```python
@dataclass(frozen=True)
class JobOutcome:
    """What a scheduled job's target reports back.

    ⚠️ THE STATE IS DERIVED, NEVER SUPPLIED. There is no field to set, so
    "succeeded" alongside a nonzero failure count is not a combination the
    wrapper has to reject — it cannot be expressed. Removal, not validation.
    """
    succeeded: int = 0
    failed: int = 0
    #: Job-specific payload. The wrapper NEVER reads this — it exists so the
    #: rich returns that already exist (`invoices_checked`, `alerts_created`)
    #: survive the migration instead of being flattened into two integers.
    detail: Mapping[str, Any] = field(default_factory=dict)
    #: Set only by `aborted()`.
    reason: str | None = None

    @classmethod
    def nothing_to_do(cls, **detail) -> "JobOutcome": ...
    @classmethod
    def worked(cls, *, succeeded: int, failed: int = 0, **detail) -> "JobOutcome": ...
    @classmethod
    def aborted(cls, reason: str, **detail) -> "JobOutcome": ...

    @property
    def state(self) -> str:
        if self.reason is not None:        return "aborted"
        if self.failed:                    return "completed_with_errors"
        if self.succeeded:                 return "ok"
        return "no_work"
```

**Four states, three constructors.** `ok` and `completed_with_errors` are the
same constructor separated by the data, which is what makes the bad combination
unrepresentable rather than merely refused.

### Why `aborted` is separate from `completed_with_errors`

"I tried nine hundred items and four failed" is not "I could not run." 0a
already draws that line — a target that *reports* an error ran, a target that
*raised* died — and this keeps it. `aborted()` subsumes the ad-hoc
`{"error": str(e)}` marker the three whole-body swallowers return today, making
it typed rather than a convention.

### What it does not use

⚠️ **`skipped` appears nowhere.** It already means a boolean "the run was
skipped" in `run_tax_filing_prep` and a count of "n items skipped" in
`suggest_cemetery_connections_for_new_tenants`. Adopting it would inherit the
ambiguity into the shape built to remove one.

### Why counts and a state, not one or the other

`_run_per_tenant` already counts tenants, so a target doing one thing per tenant
(`run_reorder_suggestion_job`) has no count of its own worth reporting — it needs
`nothing_to_do()` or `worked(succeeded=1)`. A target iterating nine hundred items
needs both. A state alone cannot say "four of nine hundred failed"; a count alone
cannot distinguish "zero because nothing was due" from "zero because everything
broke."

---

## What the wrapper does with it

Per tenant, `_run_per_tenant` maps the outcome; across tenants it aggregates:

- any tenant **raised** → run is `failed` (unchanged)
- any tenant returned **`aborted`** → run is `failed` (this is 0a's path, typed)
- any tenant returned **`completed_with_errors`** → run is `completed_with_errors`
- every tenant returned **`no_work`** → run is `completed`, `success_count=0`
- otherwise → `completed`

`_run_global` maps the single outcome directly.

⚠️ **`error_count` becomes meaningful on every path.** It is NULL on 93% of rows
today because `_run_global`'s success path passes no counts — sparseness that
maps exactly onto which wrapper wrote the row. Under this shape both wrappers
pass counts always, so a future reader can tell `0` from "not recorded" going
forward.

---

## Sequencing — three commits, removal last

Per the removal rule: you cannot remove a method while its callers still use it.

1. **Introduce `JobOutcome` and a ratchet.** Nothing migrated. The ratchet
   asserts the number of the 13 not yet returning a `JobOutcome` may only
   shrink, with today's count as the ceiling. Both wrappers accept the old
   shapes and the new one.
2. **Migrate the 13**, in whatever grouping keeps each commit reviewable. Each
   moves the ceiling down. `test_NONE_IS_STILL_SUCCESS` goes red in the commit
   that migrates the last `None`-returning target and is deleted there — it is
   the pin being removed, not a regression.
3. **Remove.** The wrappers stop accepting anything but a `JobOutcome` from the
   13. At that point `return None` from one of them is a type error rather than
   a silent success.

⚠️ **Step 3 cannot precede step 2.** A wrapper that refuses `None` before its
callers are migrated converts a latent ambiguity into a nightly `TypeError`
against live tenants — the failure mode this project has recorded for exactly
this ordering.

---

## The boundary, per the ruling

`completed_with_errors` starts being written on a specific date. That date goes
in **STATE** and in **`JobRun`'s model docstring**, because a reader comparing
`completed` counts across it will otherwise see a shape change with no cause.
Before it, an all-failed run recorded `completed`; after, it does not. Nothing
in the table marks that.

`job_runs.status` has **no CHECK constraint** — verified against production, only
a primary key on the table — so the new value needs no migration.

---

## What stays out

The 15 targets that raise. Their failures already reach the wrapper and are
already recorded `failed`; migrating them would be churn against no defect. They
may adopt `JobOutcome` later for uniformity, but not as part of (c).
