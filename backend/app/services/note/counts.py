"""Live counts for standing entries — of DISTINCT SUBJECTS, never of raw rows.

⚠️ WHERE THIS CONSTRAINT BINDS, AND WHY IT IS HERE. `operational_layer_service`
performs no data access at all: it emits `component_key`s and each widget
self-fetches through its own tenant-scoped endpoint. So the layer service never
sees a number, and the distinct-subject rule cannot bind there. It binds at count
RESOLUTION, which is this module.

⚠️ WHY THE RULE EXISTS, MEASURED RATHER THAN ARGUED. Production, 2026-09-04:
`agent_anomalies` holds 2,084 unresolved rows. Of those, `expense_no_gl_mapping`
is 1,825 rows carrying ONE distinct description, and `expense_classification_failed`
is 192 rows carrying ONE. The actionable content is roughly 50 distinct
conditions.

    raw row count      ->  ~2,084
    distinct subjects  ->  ~50

A forty-fold divergence on the FIRST standing entry the operational layer
produces. A register rendering 2,084 would train its only reader to ignore it
inside a week — and that is not hypothetical either: 2,179 unread notifications
already sit on that tenant, reporting those same two conditions.

⚠️ A FAILED COUNT RENDERS AS NO COUNT, NEVER AS ZERO. Zero is a claim —
"nothing needs you" — and a count that failed has not earned it.
"""

from __future__ import annotations

import logging
from typing import Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)


def _anomalies_distinct(db: Session, user: User) -> int:
    """Unresolved anomalies for this tenant, counted by DISTINCT SUBJECT.

    The subject is the CONDITION — `(anomaly_type, description)` — not the row.
    Tenant isolation follows the same path the widget uses: `agent_anomalies`
    carries no `company_id`, so scope flows `agent_job_id` -> `AgentJob.tenant_id`.
    """
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly

    rows = (
        db.query(AgentAnomaly.anomaly_type, AgentAnomaly.description)
        .join(AgentJob, AgentJob.id == AgentAnomaly.agent_job_id)
        .filter(
            AgentJob.tenant_id == user.company_id,
            AgentAnomaly.open_filter(),
        )
        .distinct()
        .count()
    )
    return int(rows or 0)


#: `count_source` -> resolver. A source with no resolver renders no count, which
#: makes registering one deliberate rather than implicit.
COUNT_RESOLVERS: dict[str, Callable[[Session, User], int]] = {
    "anomalies": _anomalies_distinct,
}


def resolve_count(
    db: Session, user: User, count_source: str | None
) -> tuple[int | None, str]:
    """Resolve one entry's live count. Returns `(count, state)`.

    ⚠️ THE STATE IS THE POINT. "A failed count renders as no count" is right and,
    alone, made a deliberate blank indistinguishable from a silent failure — so
    the two are separated here even though both render without a number. An
    operator reviewing the surface must be able to tell "this line has no count"
    from "this line's count broke".

    Never raises into the caller: a standing set that cannot render because one
    count failed is worse than one with a single count missing.
    """
    if not count_source:
        return None, "absent"
    fn = COUNT_RESOLVERS.get(count_source)
    if fn is None:
        # A declared source with no resolver is a wiring gap, not a blank line.
        logger.warning(
            "standing entry declares count_source %r with no resolver "
            "registered — rendering unavailable, not zero",
            count_source,
        )
        return None, "unavailable"
    try:
        return int(fn(db, user)), "ok"
    except Exception:
        logger.exception("count resolution failed for %r", count_source)
        return None, "unavailable"  # NOT zero — zero is a claim
