"""WorkflowReviewItem adapter — Phase R-6.0a.

Single canonical resume path for ``invoke_review_focus`` workflow
steps. Triage action handlers (workflow_review.approve / .reject /
.edit_and_approve) flow through ``commit_decision``, which:

  1. Validates the item (must exist, must belong to caller's tenant,
     must not already be decided).
  2. Stamps the decision fields (decision, edited_data, decision_notes,
     decided_by_user_id, decided_at).
  3. Calls ``workflow_engine.advance_run(db, run_id=item.run_id,
     step_input={review_focus_id: payload})``.

The advance_run call resumes the underlying workflow with the
decision payload as the next step's input — downstream steps
reference it via the new ``workflow_input`` parameter binding
prefix or via ``input.<review_focus_id>.<field>`` for legacy-shape
references.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models.workflow_review_item import WorkflowReviewItem
from app.services import workflow_engine

logger = logging.getLogger(__name__)


class WorkflowReviewError(Exception):
    """Base for workflow-review-adapter failures."""


class WorkflowReviewItemNotFound(WorkflowReviewError):
    pass


class WorkflowReviewItemAlreadyDecided(WorkflowReviewError):
    pass


Decision = Literal["approve", "reject", "edit_and_approve"]


def commit_decision(
    db: Session,
    *,
    item_id: str,
    decision: Decision,
    user_id: str,
    company_id: str,
    edited_data: dict[str, Any] | None = None,
    decision_notes: str | None = None,
) -> WorkflowReviewItem:
    """Stamp the review item's decision + advance its workflow run.

    Tenant-scoped: ``company_id`` MUST match the item's company_id;
    cross-tenant requests raise ``WorkflowReviewItemNotFound``
    (existence-hiding 404 semantics matching the rest of the
    triage substrate).

    Returns the mutated WorkflowReviewItem (committed).

    Raises:
        WorkflowReviewItemNotFound: item_id missing or cross-tenant.
        WorkflowReviewItemAlreadyDecided: item already has a decision.
    """
    if decision not in ("approve", "reject", "edit_and_approve"):
        raise ValueError(
            f"Invalid decision='{decision}'. "
            f"Must be one of: approve / reject / edit_and_approve."
        )

    item = (
        db.query(WorkflowReviewItem)
        .filter(
            WorkflowReviewItem.id == item_id,
            WorkflowReviewItem.company_id == company_id,
        )
        .first()
    )
    if item is None:
        raise WorkflowReviewItemNotFound(
            f"WorkflowReviewItem id='{item_id}' not found in tenant."
        )

    if item.decision is not None:
        raise WorkflowReviewItemAlreadyDecided(
            f"WorkflowReviewItem id='{item_id}' already decided "
            f"(decision={item.decision} at {item.decided_at})."
        )

    item.decision = decision
    item.edited_data = edited_data if decision == "edit_and_approve" else None
    item.decision_notes = decision_notes
    item.decided_by_user_id = user_id
    item.decided_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)

    # Build the resume payload: advance_run merges keys into
    # WorkflowRun.input_data, keyed by review_focus_id so downstream
    # steps can reference the decision via {input.<review_focus_id>.X}
    # (legacy syntax) OR {workflow_input.X} (new R-6.0 syntax that
    # resolves against the previous step's output_data).
    if decision == "approve":
        resume_payload: dict[str, Any] = {"decision": "approve"}
        # Pass the canonical input_data through so downstream steps
        # see "the data the reviewer approved." This is the canonical
        # shape — operator-edited variants live under decision="edit_and_approve".
        if isinstance(item.input_data, dict):
            resume_payload.update(item.input_data)
    elif decision == "edit_and_approve":
        resume_payload = {"decision": "edit_and_approve"}
        if isinstance(edited_data, dict):
            resume_payload.update(edited_data)
    else:  # reject
        resume_payload = {"decision": "reject", "decision_notes": decision_notes}

    step_input = {item.review_focus_id: resume_payload}

    logger.info(
        "workflow_review_adapter.commit_decision: item=%s decision=%s "
        "review_focus_id=%s run_id=%s",
        item.id,
        decision,
        item.review_focus_id,
        item.run_id,
    )

    workflow_engine.advance_run(db, run_id=item.run_id, step_input=step_input)
    return item


__all__ = [
    "Decision",
    "WorkflowReviewError",
    "WorkflowReviewItemNotFound",
    "WorkflowReviewItemAlreadyDecided",
    "commit_decision",
]
