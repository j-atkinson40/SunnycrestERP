"""What a scheduled job's target reports back.

Item (c) of the 2026-09-10 held-work list. The residual 0a left open: a tolerant
loop in which every item fails returns normally and is recorded as a clean run.
Tolerance built for one bad row is silent for a broken world.

──────────────────────────────────────────────────────────────────────────
⚠️ THE STATE IS DERIVED, NEVER SUPPLIED

There is no `state` field. `ok` alongside a nonzero failure count is not a
combination a wrapper has to reject — it CANNOT BE WRITTEN. That is the removal
the item asked for rather than validation against it, and it means no author
ever decides which state their run is in: `ok` and `completed_with_errors` come
from the same constructor, separated by the data.

──────────────────────────────────────────────────────────────────────────
⚠️ `skipped` APPEARS NOWHERE, DELIBERATELY

It already means two things in this codebase. `run_tax_filing_prep` returns
`{"skipped": True, "reason": ...}` — a boolean, the whole run was skipped.
`suggest_cemetery_connections_for_new_tenants` returns `{"created": n,
"skipped": n}` — a count of items. One key, two questions. Adopting it would
inherit an ambiguity into the type built to remove one. The third state is
`nothing_to_do`.

──────────────────────────────────────────────────────────────────────────
WHY COUNTS *AND* A STATE

`_run_per_tenant` already counts tenants, so a target that does one thing per
tenant — `run_reorder_suggestion_job` produces at most one suggestion — has no
count of its own worth reporting; it needs a state. A target iterating nine
hundred invoices needs both. A state alone cannot say "four of nine hundred
failed"; a count alone cannot distinguish "zero because nothing was due" from
"zero because everything broke."

──────────────────────────────────────────────────────────────────────────
⚠️ `aborted` CARRIES COUNTS, AND THAT IS A FINDING RATHER THAN A DEFAULT

Measured 2026-09-14. The three whole-body swallowers — `run_ar_aging_monitor`,
`run_collections_sequence`, `run_ap_upcoming_payments` — all hold live progress
counters at the point they catch (`alerts_created`, `drafts_created`,
`sequences_started`), and all reach `create_alert`, which COMMITS each alert as
it goes. So work done before an abort is durable and countable, and
`aborted(reason)` with an implicit zero would understate real committed rows.

`aborted` stays authoritative over the counts: a run that did four things and
then died is aborted, not `completed_with_errors`. 0a already draws that line —
a target that REPORTS an error ran, one that RAISED died — and this keeps it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

#: The four states, in the order a reader meets them.
STATE_NO_WORK = "no_work"
STATE_OK = "ok"
STATE_COMPLETED_WITH_ERRORS = "completed_with_errors"
STATE_ABORTED = "aborted"


@dataclass(frozen=True)
class JobOutcome:
    """A target's report. Build with the classmethods, not the constructor."""

    succeeded: int = 0
    failed: int = 0
    #: Job-specific payload. ⚠️ THE WRAPPER NEVER READS THIS. It exists so the
    #: rich returns that already exist — `invoices_checked`, `alerts_created`,
    #: `period_key` — survive the migration instead of being flattened into two
    #: integers. A migration that loses information is a migration that gets
    #: skipped.
    detail: Mapping[str, Any] = field(default_factory=dict)
    #: Set only by `aborted()`. Its presence IS the aborted state.
    reason: str | None = None

    # ── constructors ────────────────────────────────────────────────────
    @classmethod
    def nothing_to_do(cls, **detail: Any) -> "JobOutcome":
        """Ran, found nothing that needed doing. Not a failure."""
        return cls(detail=detail)

    @classmethod
    def worked(cls, *, succeeded: int, failed: int = 0, **detail: Any) -> "JobOutcome":
        """Did work. `failed` decides between `ok` and `completed_with_errors`.

        ⚠️ Both states come from here on purpose. An author reporting
        `succeeded=0, failed=900` cannot accidentally label it a success,
        because they do not label it at all.
        """
        if succeeded < 0 or failed < 0:
            raise ValueError("counts are not negative")
        return cls(succeeded=succeeded, failed=failed, detail=detail)

    @classmethod
    def aborted(cls, reason: str, *, succeeded: int = 0, failed: int = 0,
                **detail: Any) -> "JobOutcome":
        """Could not finish. Counts record what was durably done first."""
        if not reason:
            raise ValueError("an abort states its reason")
        return cls(succeeded=succeeded, failed=failed, detail=detail, reason=reason)

    # ── derived ─────────────────────────────────────────────────────────
    @property
    def state(self) -> str:
        if self.reason is not None:
            return STATE_ABORTED
        if self.failed:
            return STATE_COMPLETED_WITH_ERRORS
        if self.succeeded:
            return STATE_OK
        return STATE_NO_WORK
