"""Task type behaviors plugin contract.

Per state doc §5.4 + build prompt §5.4 Contract 3.

A TaskTypeBehavior is a per-task_type_key plugin declaring:

- default lifecycle_shape (action / reminder)
- default routing_mode (direct_user / round_robin) — read by v1.5 routing
- default priority + visibility
- on_status_change hook (no-op default)
- render_default_payload (Pulse / briefings payload shape)

Five v1 plugins live in `types/`:
- generic_task
- review_approval_task
- scheduled_recurring_task
- customer_communication_task
- anomaly_resolution_task

Tier R1 in-memory pattern.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


@runtime_checkable
class TaskTypeBehaviorProtocol(Protocol):
    """Plugin shape for task-type-specific behaviors."""

    task_type_key: str
    default_lifecycle_shape: str
    default_routing_mode: str
    default_priority: str
    default_visibility: str

    def on_status_change(
        self,
        db: Session,
        *,
        task_details_id: str,
        from_state: str,
        to_state: str,
        actor_user_id: str | None,
    ) -> None:
        """Hook fired post-transition. Default: no-op."""
        ...

    def render_default_payload(
        self,
        db: Session,
        *,
        task_details_id: str,
    ) -> dict[str, Any]:
        """Per-task-type Pulse / briefing payload shape."""
        ...


_REGISTRY: dict[str, TaskTypeBehaviorProtocol] = {}


def register_task_type_behavior(behavior: TaskTypeBehaviorProtocol) -> None:
    if (
        not hasattr(behavior, "task_type_key")
        or not behavior.task_type_key
    ):
        raise ValueError(
            "TaskTypeBehavior must declare a non-empty task_type_key"
        )
    _REGISTRY[behavior.task_type_key] = behavior
    logger.debug(
        "task type behavior registered: %s lifecycle=%s routing=%s",
        behavior.task_type_key,
        behavior.default_lifecycle_shape,
        behavior.default_routing_mode,
    )


def get_task_type_behavior(
    task_type_key: str,
) -> TaskTypeBehaviorProtocol | None:
    return _REGISTRY.get(task_type_key)


def list_task_type_behaviors() -> tuple[str, ...]:
    return tuple(_REGISTRY.keys())


def unregister_task_type_behavior(task_type_key: str) -> bool:
    return _REGISTRY.pop(task_type_key, None) is not None


def reset_type_behaviors_for_tests() -> None:
    _REGISTRY.clear()


__all__ = [
    "TaskTypeBehaviorProtocol",
    "register_task_type_behavior",
    "get_task_type_behavior",
    "list_task_type_behaviors",
    "unregister_task_type_behavior",
    "reset_type_behaviors_for_tests",
]
