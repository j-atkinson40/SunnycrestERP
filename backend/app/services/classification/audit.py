"""Phase R-6.1a — Email classification audit log writer.

Writes ``WorkflowEmailClassification`` rows. Append-only by service
contract — no UPDATE / DELETE paths. Replays + manual reroutes write
NEW rows; the original classification remains visible. The latest
classification per message is fetched via
``ORDER BY created_at DESC LIMIT 1`` filtered on ``email_message_id``.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.email_classification import WorkflowEmailClassification

logger = logging.getLogger(__name__)


def write_classification_audit(
    db: Session,
    *,
    tenant_id: str,
    email_message_id: str,
    tier: int | None,
    tier1_rule_id: str | None = None,
    tier2_category_id: str | None = None,
    tier2_confidence: float | None = None,
    tier3_confidence: float | None = None,
    selected_workflow_id: str | None = None,
    is_suppressed: bool = False,
    workflow_run_id: str | None = None,
    is_replay: bool = False,
    replay_of_classification_id: str | None = None,
    error_message: str | None = None,
    latency_ms: int | None = None,
    tier_reasoning: dict[str, Any] | None = None,
) -> WorkflowEmailClassification:
    """Write an audit row + flush. Caller is responsible for the
    enclosing commit (so the row is part of the same transaction as
    the workflow run insert when applicable).

    Every classification path writes one of these — never silently
    skip. If the cascade exhausts without a dispatch, ``tier=None``
    + ``selected_workflow_id=None`` + ``is_suppressed=False`` is the
    canonical "unclassified" shape feeding the triage queue.
    """
    row = WorkflowEmailClassification(
        tenant_id=tenant_id,
        email_message_id=email_message_id,
        tier=tier,
        tier1_rule_id=tier1_rule_id,
        tier2_category_id=tier2_category_id,
        tier2_confidence=tier2_confidence,
        tier3_confidence=tier3_confidence,
        selected_workflow_id=selected_workflow_id,
        is_suppressed=is_suppressed,
        workflow_run_id=workflow_run_id,
        is_replay=is_replay,
        replay_of_classification_id=replay_of_classification_id,
        error_message=error_message,
        latency_ms=latency_ms,
        tier_reasoning=tier_reasoning or {},
    )
    db.add(row)
    db.flush()
    return row
