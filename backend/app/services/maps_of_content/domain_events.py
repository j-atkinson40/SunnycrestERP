"""Domain-event emission (Canvas↔Runtime Bridge T-2.2a) — the transactional
outbox writer.

`emit_event()` records a domain event as a `moc_domain_event` row IN THE
CALLER'S TRANSACTION (add + flush — the CALLER commits). That is the entire
reliability model: the event commits iff the mutation commits — no lost events
(mutation committed, event lost), no phantom events (event recorded, mutation
rolled back). Call it AT the mutation site, BEFORE the site's commit.

DELIBERATELY LOUD: no try/except. An emission failure fails the mutation —
better a visible mutation failure than a trigger that silently never fires
(the silent-swallow at emission scale). Do NOT wrap calls in a swallow.

`payload` is the condition-evaluation snapshot: the values of the fields the
event's catalog entry declares in `filterable_fields`, as of the mutation. The
T-2.2b matcher evaluates trigger conditions against this payload ONLY (it never
re-reads domain entities); a condition on a field absent from the payload is a
no-match. Keep emit-site payloads in sync with the catalog's filterable_fields.

T-2.2a wires the four clean-chokepoint catalog events:
  case.opened · delivery.completed · certificate.approved ·
  urn_order.proof_pending
The scattered events (order.created ≥6 sites, order.completed, invoice.sent,
invoice.paid ×2) are the T-2.2d audited wiring pass — until wired, an event-
trigger on them is descriptive-only (the T-2.2b matcher logs a warning for
triggers referencing never-emitted events).

Nothing consumes the rows this phase (inert, like r115's descriptive triggers);
the matcher sweep is T-2.2b.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.moc_domain_event import MoCDomainEvent

logger = logging.getLogger(__name__)


def emit_event(
    db: Session,
    *,
    company_id: str,
    event_key: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> MoCDomainEvent:
    """Record a domain event in the caller's transaction (transactional outbox).

    add + flush only — the CALLER's commit makes it durable, atomically with
    the mutation it records. Loud by design: raises on failure (never swallow)."""
    event = MoCDomainEvent(
        company_id=company_id,
        event_key=event_key,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload or {},
    )
    db.add(event)
    db.flush()
    logger.debug(
        "MoC domain event emitted: %s (company=%s entity=%s/%s)",
        event_key, company_id, entity_type, entity_id,
    )
    return event
