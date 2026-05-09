"""Phase R-6.1a — Email classification cascade package.

Three-tier classification of inbound email messages into workflow
triggers:

  Tier 1 (deterministic, sub-ms): tenant rule list, first match wins,
    fire_action.workflow_id may be null to suppress.
  Tier 2 (Haiku, ≤1s p95): AI classification into per-tenant taxonomy,
    confidence floor 0.55, mapped_workflow_id fires the workflow.
  Tier 3 (Haiku, ≤1s p95): AI selection from tenant-enrolled workflow
    registry, confidence floor 0.65, fires the picked workflow.

Falls through to ``email_unclassified_triage`` queue when no tier
dispatches. Append-only audit log via ``WorkflowEmailClassification``.

Public surface:
  - ``classify_and_fire(db, *, email_message)`` — synchronous; called
    from email ingestion Step 12. Best-effort caller wraps in try/except.
  - ``classify_only(db, *, message_id)`` — admin replay; writes new audit row.
  - ``get_latest_classification_for_message(db, *, message_id)``.
  - ``list_unclassified(db, *, tenant_id, limit)`` — feeds triage direct query.
  - ``manual_route_to_workflow(db, *, classification_id, workflow_id, user_id)``
    — operator-driven reroute from triage; fires workflow + writes new
    classification row.
  - ``CONFIDENCE_FLOOR_TIER_2`` / ``CONFIDENCE_FLOOR_TIER_3`` — module-
    level constants. Per-tenant override via
    ``Company.settings_json.classification_confidence_floors.{tier_2, tier_3}``.

Exceptions:
  - ``ClassificationError`` — base.
  - ``ClassificationNotFound`` — for cross-tenant 404 hiding.
"""

from app.services.classification.dispatch import (
    CONFIDENCE_FLOOR_TIER_2,
    CONFIDENCE_FLOOR_TIER_3,
    ClassificationError,
    ClassificationNotFound,
    ClassificationResult,
    classify_and_fire,
    classify_only,
    get_latest_classification_for_message,
    list_unclassified,
    manual_route_to_workflow,
)

__all__ = [
    "CONFIDENCE_FLOOR_TIER_2",
    "CONFIDENCE_FLOOR_TIER_3",
    "ClassificationError",
    "ClassificationNotFound",
    "ClassificationResult",
    "classify_and_fire",
    "classify_only",
    "get_latest_classification_for_message",
    "list_unclassified",
    "manual_route_to_workflow",
]
