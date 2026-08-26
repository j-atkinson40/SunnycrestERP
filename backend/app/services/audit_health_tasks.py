"""HC-1 A-3 — audit health findings become tasks.

`run_health_check` computes correct findings and is reachable from two on-demand
API routes. Nothing pushes it. Production carried 15 stale draft journal entries
for twenty days with a working "Review Drafts" action nobody was told about
(measured 2026-08-26, AP-1).

Nothing needed building to DETECT the backlog or to CLEAR it. The gap was
delivery, and this is the delivery.

WHY TASKS RATHER THAN THE COMPLETENESS REVIEW. CR-2 models an obligation: a
recurring duty whose proof is rows ARRIVING in a source table within a period.
A health finding is not that shape, and the test that settles it is whether a
tenant declining it produces a coherent statement. "We don't run a delivery
fleet" is scope. "We don't post journal entries" is an admission — and CR-3's
D-2 would render it as a satisfied grey pill, which is the exact failure CR-3
shipped to prevent. The tell underneath: every `matters_because` in CR-2 is
about AMBIGUITY ("a day with no log cannot be distinguished from a day with no
production"). Fifteen entries, correctly recorded, in a known state, are not
ambiguous. The review resolves absence; this is not absence.

GENERAL BY CONSTRUCTION. Five checks today. A bridge built for `stale_drafts`
alone is one somebody rebuilds for `never_reconciled` next week, so this reads
the findings list and knows nothing about any particular code.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#: Provenance for every task this raises. `anomaly_detection` rather than
#: `system_internal`: the health check detects an anomalous CONDITION, which is
#: what the reader of the task is being asked about.
PROVENANCE_KIND = "anomaly_detection"
PROVENANCE_REF_TYPE = "health_finding"
EVENT_KIND = "audit_health_finding_raised"
TASK_TYPE_KEY = "anomaly_resolution_task"

#: `anomaly_resolution_task` is COHORT-ROUTED: the notification subscriber raises
#: ValueError("Producer site is misconfigured") if this is absent, which is how
#: the omission was caught rather than shipped. Matches the key its siblings use
#: (`workflow_engine.py:1129`, `classification/dispatch.py:404`).
#:
#: ⚠️ THIS ROUTES TO ADMINS ONLY, AND THE NATURAL READER IS THE ACCOUNTANT.
#: CR-3 measured it: the accountant role holds 43 permissions on testco and NONE
#: of them is `admin`; the admin role passes only via the `is_system and
#: slug == "admin"` shortcut in `user_has_permission`. Stale journal entries and
#: unreconciled accounts are an accountant's work. Flagged rather than widened
#: here, because choosing a cohort is a permissions decision with its own blast
#: radius and CR-3 spent an arc on exactly that question.
NOTIFICATION_PERMISSION_KEY = "admin"

#: Severity → task priority. Green never becomes a task; it is the absence of
#: work, and raising a task saying "nothing is wrong" is noise with a lifecycle.
_PRIORITY = {"red": "high", "amber": "normal"}


def _terminal_states() -> set[str]:
    """States from which a task cannot move.

    DERIVED from the transition tables rather than restated. A second list of
    terminal states is two derivations of one fact, which is this repository's
    recurring defect — and it would silently stop suppressing if a new terminal
    state were added to the table and not here.
    """
    from app.services.tasks.lifecycle import ACTION_TRANSITIONS, REMINDER_TRANSITIONS

    both = {**ACTION_TRANSITIONS, **REMINDER_TRANSITIONS}
    return {state for state, onward in both.items() if not onward}


def _episode_counts(db: Session, tenant_id: str) -> dict[str, int]:
    """How many tasks this tenant has ever had per finding code.

    Used as the episode number in `provenance_ref_id` so a condition resolved
    and recurring ON THE SAME DAY still raises. Keying on the date alone was the
    first implementation and this is the test that caught it: same code, same
    check_date, so the idempotency key collided and returned the DONE task.
    """
    from app.models.task_details import TaskDetails
    from app.models.vault_item import VaultItem

    counts: dict[str, int] = {}
    rows = (
        db.query(TaskDetails.provenance_ref_id)
        .join(VaultItem, VaultItem.id == TaskDetails.vault_item_id)
        .filter(
            VaultItem.company_id == tenant_id,
            TaskDetails.provenance_kind == PROVENANCE_KIND,
            TaskDetails.provenance_ref_type == PROVENANCE_REF_TYPE,
        )
        .all()
    )
    for (ref,) in rows:
        if ref:
            code = ref.split("@", 1)[0]
            counts[code] = counts.get(code, 0) + 1
    return counts


def _open_finding_codes(db: Session, tenant_id: str) -> set[str]:
    """Finding codes that already have a NON-terminal task for this tenant.

    ⚠️ THIS IS THE LOAD-BEARING PART AND THE OBVIOUS IMPLEMENTATION IS WRONG.

    `create_task_with_provenance` is idempotent on
    `(provenance_kind, provenance_ref_type, provenance_ref_id, event_kind)`, and
    the DB index behind it is `WHERE provenance_ref_id IS NOT NULL` — NOT
    filtered by state. So keying on the bare finding code would mean: task
    raised, human resolves it, condition RECURS, and the next run returns the
    existing DONE task instead of raising a new one. The recurrence would be
    invisible — the fail-open shape this whole arc has been closing.

    So `provenance_ref_id` carries the check date, making every run's key
    distinct and letting the index do exactly what it is for (two runs on the
    same day cannot double-raise), and RECURRENCE is governed here instead: at
    most one OPEN task per (tenant, code), a new one only once the last closed.

    `suppression_key` exists on the model and would look like the right tool.
    It is written and never read — no consumer anywhere in `app/`. Building on
    it would be building on nothing.
    """
    from app.models.task_details import TaskDetails
    from app.models.vault_item import VaultItem

    rows = (
        db.query(TaskDetails.provenance_ref_id)
        .join(VaultItem, VaultItem.id == TaskDetails.vault_item_id)
        .filter(
            VaultItem.company_id == tenant_id,
            TaskDetails.provenance_kind == PROVENANCE_KIND,
            TaskDetails.provenance_ref_type == PROVENANCE_REF_TYPE,
            TaskDetails.current_state.notin_(_terminal_states()),
        )
        .all()
    )
    # ref_id is "<code>@<check_date>"; the code is what identifies the condition.
    return {r[0].split("@", 1)[0] for r in rows if r[0]}


def raise_tasks_for_health_findings(
    db: Session, tenant_id: str, *, created_by_user_id: str | None = None
) -> dict[str, Any]:
    """Run the health check and raise a task per actionable finding.

    ⚠️ RUNS THE CHECK. It deliberately does not read `GET /reports/audit-health`,
    which returns the latest STORED `AuditHealthCheck` row and only computes when
    none exists — so it can serve a months-old result with `check_date` present
    and nothing forcing a reader to look at it. Raising a task from that would be
    the stale-status defect in a new place.

    ⚠️ THIS COMMITS, and that is not the convention `create_task_with_provenance`
    documents ("caller is responsible for the surrounding transaction"). Two
    reasons, both measured rather than assumed:

      * `run_health_check` ALREADY commits mid-flight to upsert its
        `AuditHealthCheck` row, so a caller-owned transaction spanning this call
        does not exist to be honoured.
      * `scheduler._run_per_tenant` calls `func(db, tid)` and then `db.close()`
        with NO commit. Leaving the commit to it would mean every task created
        here is silently discarded — built, correct, and gone. There is a test
        that closes the session the way the scheduler does and asserts the tasks
        survive.

    Returns what happened, per code, so a scheduler logging this can say
    something specific.
    """
    from app.services.financial_report_service import run_health_check
    from app.services.tasks.service import create_task_with_provenance

    result = run_health_check(db, tenant_id)
    check_date = result["check_date"]
    already_open = _open_finding_codes(db, tenant_id)
    episodes = _episode_counts(db, tenant_id)

    created: list[str] = []
    suppressed: list[str] = []
    failed: list[str] = []

    for finding in result["findings"]:
        severity = finding.get("severity")
        if severity == "green":
            continue
        code = finding.get("code")
        if not code:
            continue
        if code in already_open:
            suppressed.append(code)
            continue
        try:
            create_task_with_provenance(
                db,
                company_id=tenant_id,
                provenance_kind=PROVENANCE_KIND,
                provenance_ref_type=PROVENANCE_REF_TYPE,
                # code@date#episode. The episode number is what makes a
                # same-day recurrence distinct; suppression is governed by
                # `_open_finding_codes`, not by this key.
                provenance_ref_id=f"{code}@{check_date}#{episodes.get(code, 0)}",
                event_kind=EVENT_KIND,
                task_type_key=TASK_TYPE_KEY,
                title=finding.get("message") or code,
                description=(
                    f"Audit health check on {check_date} raised '{code}'.\n\n"
                    f"{finding.get('message', '')}\n\n"
                    f"Action: {finding.get('action_label') or 'Review'} — "
                    f"{finding.get('action_url') or ''}"
                ).strip(),
                created_by_user_id=created_by_user_id,
                priority=_PRIORITY.get(severity, "normal"),
                metadata={
                    "notification_permission_key": NOTIFICATION_PERMISSION_KEY,
                    "finding_code": code,
                    "severity": severity,
                    "category": finding.get("category"),
                    "action_label": finding.get("action_label"),
                    "action_url": finding.get("action_url"),
                    "check_date": check_date,
                },
            )
            created.append(code)
        except Exception:
            # One finding failing to become a task must not cost the others.
            # Reported, never swallowed into a clean-looking return — which is
            # the defect A-2 removed from the producer feeding this.
            logger.exception(
                "HC-1: could not raise a task for finding %r (tenant=%s)", code, tenant_id
            )
            failed.append(code)

    db.commit()

    return {
        "tenant_id": tenant_id,
        "check_date": check_date,
        "created": created,
        "suppressed": suppressed,
        "failed": failed,
        "overall_score": result["overall_score"],
    }
