"""Task substrate v1 — subscriber registry.

Per state doc §5.7 + build prompt §5.3:

- **7 event types** emitted by lifecycle transitions.
- **6 subscribers** registered in v1 (some no-op until v1.5).
- **Sync execution** within the task transaction (operator Lock 3).
- **Try/except per subscriber** — one subscriber failure logs + continues.
- **Deterministic registration order** — first-registered fires first.
- Persistent log of subscriber dispatches deferred to v2c.

Subscriber idempotency is the subscriber's own responsibility (state
doc §5.7); the registry simply dispatches.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Any, Callable

from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


# ── Event vocabulary (frozen) ───────────────────────────────────────


EVENT_TYPES: tuple[str, ...] = (
    "task_created",
    "task_assigned",
    "task_status_changed",
    "task_completed",
    "task_blocked",
    "task_unblocked",
    "task_cancelled",
)


# ── Subscriber registration ─────────────────────────────────────────


SubscriberHandler = Callable[[Session, dict[str, Any]], None]


class _Subscriber:
    """In-memory subscriber record."""

    __slots__ = ("name", "handler", "event_types")

    def __init__(
        self,
        name: str,
        handler: SubscriberHandler,
        event_types: tuple[str, ...],
    ) -> None:
        self.name = name
        self.handler = handler
        self.event_types = event_types


# OrderedDict preserves registration order — deterministic dispatch order.
_REGISTRY: "OrderedDict[str, _Subscriber]" = OrderedDict()


def register_subscriber(
    name: str,
    handler: SubscriberHandler,
    *,
    event_types: tuple[str, ...] = EVENT_TYPES,
) -> None:
    """Register a subscriber.

    Idempotent over name — re-registering the same name replaces the
    prior handler (supports test isolation + hot-reload-style patterns).
    """
    for ev in event_types:
        if ev not in EVENT_TYPES:
            raise ValueError(
                f"Unknown event_type {ev!r} for subscriber {name!r}"
            )
    _REGISTRY[name] = _Subscriber(name, handler, event_types)
    logger.debug("task subscriber registered: %s (events=%s)", name, event_types)


def unregister_subscriber(name: str) -> bool:
    """Remove a subscriber. Returns True if removed; False if absent.

    Test-isolation affordance.
    """
    return _REGISTRY.pop(name, None) is not None


def get_subscribers() -> tuple[str, ...]:
    """Returns registered subscriber names in registration order."""
    return tuple(_REGISTRY.keys())


def is_registered(name: str) -> bool:
    return name in _REGISTRY


# ── Event dispatch ──────────────────────────────────────────────────


def emit_event(
    db: Session,
    *,
    event_type: str,
    task_details_id: str,
    actor_user_id: str | None,
    payload: dict[str, Any],
) -> None:
    """Dispatches event to all subscribers registered for event_type.

    Subscribers fire synchronously in registration order. Each subscriber
    wraps its body in try/except so a single failure doesn't break the
    pipeline. Task transaction commits regardless of subscriber outcome
    (operator Lock 3 sync semantics).
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown event_type: {event_type!r}")

    event_payload: dict[str, Any] = {
        "event_type": event_type,
        "task_details_id": task_details_id,
        "actor_user_id": actor_user_id,
        **payload,
    }

    for sub in list(_REGISTRY.values()):
        if event_type not in sub.event_types:
            continue
        try:
            sub.handler(db, event_payload)
        except Exception:
            logger.exception(
                "task subscriber %r failed on event %r — continuing",
                sub.name,
                event_type,
            )


def reset_registry_for_tests() -> None:
    """Clears all registered subscribers. ONLY for test fixtures."""
    _REGISTRY.clear()


__all__ = [
    "EVENT_TYPES",
    "SubscriberHandler",
    "register_subscriber",
    "unregister_subscriber",
    "get_subscribers",
    "is_registered",
    "emit_event",
    "reset_registry_for_tests",
]
