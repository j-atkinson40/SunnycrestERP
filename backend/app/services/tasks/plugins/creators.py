"""Task creators plugin contract.

Per state doc §5.4 + build prompt §5.4 Contract 1.

A TaskCreator is a per-provenance_kind plugin that knows how to
materialize a task from caller-specific input. Concrete creators
register at module-import time against the registry; the service
layer dispatches via `dispatch_creator(provenance_kind, ...)`.

In v1, the default `create_task_with_provenance` in
`app.services.tasks.service` covers the common case — the registry
exists so type-behavior plugins or downstream features can override
creation logic per provenance_kind without changing core paths.

Tier R1 in-memory pattern matching PLUGIN_CONTRACTS.md "Intake adapters".
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Protocol, runtime_checkable

from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


@runtime_checkable
class TaskCreatorProtocol(Protocol):
    """Plugin shape for creating tasks from producer sites.

    Concrete creators per provenance_kind.
    """

    provenance_kind: str
    task_type_default: str

    def create(
        self,
        db: Session,
        *,
        company_id: str,
        provenance_ref_type: str,
        provenance_ref_id: str,
        event_kind: str,
        title: str,
        description: str | None = None,
        assignee_user_id: str | None = None,
        priority: str = "normal",
        due_date: date | None = None,
        suppression_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create task; return task_details_id; raise on duplicate."""
        ...


_REGISTRY: dict[str, TaskCreatorProtocol] = {}


def register_task_creator(creator: TaskCreatorProtocol) -> None:
    """Register a task creator. Replaces prior registration for the
    same provenance_kind (supports test isolation + override patterns).
    """
    if not hasattr(creator, "provenance_kind") or not creator.provenance_kind:
        raise ValueError(
            "TaskCreator must declare a non-empty provenance_kind"
        )
    _REGISTRY[creator.provenance_kind] = creator
    logger.debug(
        "task creator registered: provenance_kind=%s task_type_default=%s",
        creator.provenance_kind,
        getattr(creator, "task_type_default", "(unset)"),
    )


def get_task_creator(provenance_kind: str) -> TaskCreatorProtocol | None:
    """Return registered creator for provenance_kind, or None."""
    return _REGISTRY.get(provenance_kind)


def list_task_creators() -> tuple[str, ...]:
    """List registered provenance_kinds."""
    return tuple(_REGISTRY.keys())


def unregister_task_creator(provenance_kind: str) -> bool:
    """Remove a creator. Returns True if removed; False if absent."""
    return _REGISTRY.pop(provenance_kind, None) is not None


def reset_creators_for_tests() -> None:
    _REGISTRY.clear()


def dispatch_creator(
    db: Session,
    *,
    provenance_kind: str,
    company_id: str,
    provenance_ref_type: str,
    provenance_ref_id: str,
    event_kind: str,
    title: str,
    description: str | None = None,
    assignee_user_id: str | None = None,
    priority: str = "normal",
    due_date: date | None = None,
    suppression_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str | None:
    """Dispatch to the registered creator. Returns task_details_id
    or None if no creator registered for provenance_kind.

    Callers wanting a hard error on missing creator should check
    `get_task_creator(...)` first.
    """
    creator = _REGISTRY.get(provenance_kind)
    if creator is None:
        return None
    return creator.create(
        db,
        company_id=company_id,
        provenance_ref_type=provenance_ref_type,
        provenance_ref_id=provenance_ref_id,
        event_kind=event_kind,
        title=title,
        description=description,
        assignee_user_id=assignee_user_id,
        priority=priority,
        due_date=due_date,
        suppression_key=suppression_key,
        metadata=metadata,
    )


__all__ = [
    "TaskCreatorProtocol",
    "register_task_creator",
    "get_task_creator",
    "list_task_creators",
    "unregister_task_creator",
    "reset_creators_for_tests",
    "dispatch_creator",
]
