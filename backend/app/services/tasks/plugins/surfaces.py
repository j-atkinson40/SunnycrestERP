"""Task surfaces plugin contract.

Per state doc §5.4 + build prompt §5.4 Contract 2.

A TaskSurface is a registration of a surface (list / detail / card /
row / creation_form) that the Visual Editor / Studio / Workshop can
introspect to know how to render or compose task UI.

In v1 the Protocol surface ships; concrete surface implementations
are visual-editor-side work scheduled for v2+. The contract is the
forward-compat anchor.

Tier R1 in-memory pattern.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


SURFACE_KINDS: tuple[str, ...] = (
    "list",
    "detail",
    "creation_form",
    "card",
    "row",
)


@runtime_checkable
class TaskSurfaceProtocol(Protocol):
    """Plugin shape for task surface registrations."""

    surface_key: str
    surface_kind: str
    accepted_task_types: tuple[str, ...]

    def render_context(
        self,
        db: Session,
        *,
        task_details_id: str,
        viewing_user_id: str,
    ) -> dict[str, Any]:
        """Returns render-context dict for the surface."""
        ...


_REGISTRY: dict[str, TaskSurfaceProtocol] = {}


def register_task_surface(surface: TaskSurfaceProtocol) -> None:
    """Register a task surface. Replaces prior registration of same key."""
    if not hasattr(surface, "surface_key") or not surface.surface_key:
        raise ValueError(
            "TaskSurface must declare a non-empty surface_key"
        )
    if surface.surface_kind not in SURFACE_KINDS:
        raise ValueError(
            f"TaskSurface.surface_kind must be one of {SURFACE_KINDS}, "
            f"got {surface.surface_kind!r}"
        )
    _REGISTRY[surface.surface_key] = surface
    logger.debug(
        "task surface registered: key=%s kind=%s",
        surface.surface_key,
        surface.surface_kind,
    )


def get_task_surface(surface_key: str) -> TaskSurfaceProtocol | None:
    return _REGISTRY.get(surface_key)


def get_task_surfaces(
    *,
    kind: str | None = None,
    task_type: str | None = None,
) -> list[TaskSurfaceProtocol]:
    """Filter surfaces by kind and/or task_type. None means "any"."""
    out: list[TaskSurfaceProtocol] = []
    for s in _REGISTRY.values():
        if kind is not None and s.surface_kind != kind:
            continue
        if task_type is not None and task_type not in s.accepted_task_types:
            continue
        out.append(s)
    return out


def list_task_surfaces() -> tuple[str, ...]:
    return tuple(_REGISTRY.keys())


def unregister_task_surface(surface_key: str) -> bool:
    return _REGISTRY.pop(surface_key, None) is not None


def reset_surfaces_for_tests() -> None:
    _REGISTRY.clear()


__all__ = [
    "SURFACE_KINDS",
    "TaskSurfaceProtocol",
    "register_task_surface",
    "get_task_surface",
    "get_task_surfaces",
    "list_task_surfaces",
    "unregister_task_surface",
    "reset_surfaces_for_tests",
]
