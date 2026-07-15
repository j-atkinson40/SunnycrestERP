"""MoC trigger event catalog service (MoC Triggers T-1a) — the curated event vocabulary.

Because no domain-event bus exists (the investigation verdict), an event-trigger
picks its event from a CURATED, seeded, EDITABLE catalog — the same
configuration-over-code philosophy as the 2a vocabulary store (`add_event`
inserts a row; no code change). Each event carries `filterable_fields`: the
fields a condition may reference, grounded in real domain columns. Scope is read
three-tier (platform events + the vertical's).

DESCRIPTIVE only: these events do NOT fire. The catalog is the menu the deferred
execution bridge (T-2) will wire to real emission.
"""
from __future__ import annotations

import uuid
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.moc_task_trigger import MoCTriggerEventCatalog

_SCOPES = ("platform_default", "vertical_default", "tenant_override")


class EventCatalogError(ValueError):
    """Invalid event-catalog write (bad scope / empty key) — HTTP 400."""


def _visible_where(vertical: str | None):
    """Platform events (vertical NULL) are always visible; vertical events only
    for the requested vertical — mirrors the vocabulary store's read scope."""
    return (MoCTriggerEventCatalog.scope == "platform_default") | (
        (MoCTriggerEventCatalog.scope == "vertical_default")
        & (MoCTriggerEventCatalog.vertical == vertical)
    )


def list_events(
    db: Session, *, vertical: str | None = None, active_only: bool = True
) -> list[MoCTriggerEventCatalog]:
    """The active event menu — platform events + (if given) the vertical's."""
    stmt = select(MoCTriggerEventCatalog)
    if active_only:
        stmt = stmt.where(MoCTriggerEventCatalog.is_active.is_(True))
    if vertical is not None:
        stmt = stmt.where(_visible_where(vertical))
    rows = list(db.execute(stmt).scalars())
    rows.sort(key=lambda e: (e.display_order, e.event_key))
    return rows


def get_event(
    db: Session, *, event_key: str, vertical: str | None = None
) -> MoCTriggerEventCatalog | None:
    """The active catalog event for `event_key` visible to `vertical` (platform
    or vertical-specific). The referential anchor the trigger validator uses."""
    stmt = (
        select(MoCTriggerEventCatalog)
        .where(MoCTriggerEventCatalog.event_key == event_key)
        .where(MoCTriggerEventCatalog.is_active.is_(True))
        .where(_visible_where(vertical))
    )
    return db.execute(stmt).scalars().first()


def add_event(
    db: Session,
    *,
    event_key: str,
    label: str,
    filterable_fields: Sequence[dict[str, Any]] = (),
    entity: str | None = None,
    scope: str = "platform_default",
    vertical: str | None = None,
    display_order: int = 0,
    actor_id: str | None = None,
) -> MoCTriggerEventCatalog:
    """Find-or-create (reactivates + refreshes metadata on a soft-deleted match).
    Caller commits."""
    event_key = event_key.strip()
    if not event_key:
        raise EventCatalogError("event_key must be non-empty")
    if scope not in _SCOPES:
        raise EventCatalogError(f"invalid scope {scope!r}")
    if scope == "vertical_default" and not vertical:
        raise EventCatalogError("vertical_default scope requires a vertical")

    existing = db.execute(
        select(MoCTriggerEventCatalog)
        .where(MoCTriggerEventCatalog.event_key == event_key)
        .where(MoCTriggerEventCatalog.scope == scope)
        .where(
            MoCTriggerEventCatalog.vertical.is_(None)
            if vertical is None
            else MoCTriggerEventCatalog.vertical == vertical
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.is_active = True
        existing.label = label
        existing.entity = entity
        existing.filterable_fields = list(filterable_fields)
        if display_order:
            existing.display_order = display_order
        if actor_id:
            existing.updated_by = actor_id
        return existing

    row = MoCTriggerEventCatalog(
        id=str(uuid.uuid4()), event_key=event_key, label=label, entity=entity,
        filterable_fields=list(filterable_fields), scope=scope, vertical=vertical,
        display_order=display_order, created_by=actor_id, updated_by=actor_id,
    )
    db.add(row)
    return row


def deactivate_event(
    db: Session, *, event_id: str, actor_id: str | None = None
) -> MoCTriggerEventCatalog:
    """Soft-delete (is_active=False). Existing triggers referencing the event keep
    it (structural validation only fires on writes)."""
    row = db.get(MoCTriggerEventCatalog, event_id)
    if row is None:
        raise EventCatalogError(f"event {event_id!r} not found")
    row.is_active = False
    if actor_id:
        row.updated_by = actor_id
    return row


# ── The curated seed — real lifecycle events grounded in witnessed columns ──
#
# filterable_fields are the REAL columns a condition can reference (the
# investigation's witnessed status/type columns). NOTE the "legacy" nuance:
# order.created filters on order_type ∈ {funeral, retail, wholesale} — there is
# NO order_type == 'legacy' (legacy is a product-line/personalization concept,
# a rich-phase relational condition). Platform-scope (shared across every MoC).
_SEED: Sequence[dict[str, Any]] = (
    {
        "event_key": "order.created", "label": "Order created",
        "entity": "sales_order", "display_order": 0,
        "filterable_fields": [
            {"field": "order_type", "type": "enum", "values": ["funeral", "retail", "wholesale"]},
            {"field": "status", "type": "string"},
        ],
    },
    {
        "event_key": "order.completed", "label": "Order completed",
        "entity": "sales_order", "display_order": 1,
        "filterable_fields": [
            {"field": "order_type", "type": "enum", "values": ["funeral", "retail", "wholesale"]},
            {"field": "total", "type": "number"},
        ],
    },
    {
        "event_key": "invoice.sent", "label": "Invoice sent",
        "entity": "invoice", "display_order": 2,
        "filterable_fields": [
            {"field": "status", "type": "string"},
            {"field": "total", "type": "number"},
        ],
    },
    {
        "event_key": "invoice.paid", "label": "Invoice paid",
        "entity": "invoice", "display_order": 3,
        "filterable_fields": [
            {"field": "status", "type": "string"},
            {"field": "total", "type": "number"},
        ],
    },
    {
        "event_key": "delivery.completed", "label": "Delivery completed",
        "entity": "delivery", "display_order": 4,
        "filterable_fields": [{"field": "status", "type": "string"}],
    },
    {
        "event_key": "case.opened", "label": "Case opened",
        "entity": "fh_case", "display_order": 5,
        "filterable_fields": [{"field": "status", "type": "string"}],
    },
    {
        "event_key": "urn_order.proof_pending", "label": "Urn proof pending",
        "entity": "urn_order", "display_order": 6,
        "filterable_fields": [{"field": "status", "type": "string"}],
    },
    {
        "event_key": "certificate.approved", "label": "Certificate approved",
        "entity": "social_service_certificate", "display_order": 7,
        "filterable_fields": [{"field": "status", "type": "string"}],
    },
    {
        # H1 escalation hook — emitted at the _fail_run chokepoint
        # (workflows/run_escalation.py). Matchable: operators can author
        # event-triggers on run failures with zero further work.
        "event_key": "run.failed", "label": "Workflow run failed",
        "entity": "workflow_run", "display_order": 8,
        "filterable_fields": [
            {"field": "workflow_id", "type": "string"},
            {"field": "workflow_name", "type": "string"},
            {"field": "trigger_source", "type": "string"},
        ],
    },
)


def seed_events(db: Session) -> int:
    """Idempotent platform-scope seed of the curated event catalog. Commits.
    Returns count ensured. Adding an event is an add_event (a row), not code."""
    for spec in _SEED:
        add_event(
            db,
            event_key=spec["event_key"], label=spec["label"],
            entity=spec["entity"], filterable_fields=spec["filterable_fields"],
            scope="platform_default", vertical=None,
            display_order=spec["display_order"],
        )
    db.commit()
    return len(_SEED)
