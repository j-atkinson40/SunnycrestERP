"""Maps of Content — task-catalog service (MoC-2a, backend-only, realm-agnostic).

Reads a vertical's task catalog and resolves each task's ONE workflow + MANY
focuses through the SAME resolver path the MoC cards use — `BUILDERS` from
`maps_of_content.service` (the public export of `_resolve_workflow` /
`_resolve_focus`). So a task's workflow/focus cells carry byte-identical
`routing` to the cards' entries → the frontend's `mocDeepLink` produces the
SAME hrefs (the deep-link-reuse keystone, per the Phase-0 investigation). No
parallel deep-link path.

Operates on primitives (db + vertical/tenant) — realm-agnostic, so either
router consumes it identically. `upsert_task` is the idempotent find-or-create
the seed + assembly test build on (find by (scope, vertical, tenant_id, name);
update + replace focuses if present).

OUT OF SCOPE here (later phases): the read API / typed cells (2b), the table
component (2c), authoring UI.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.models.moc_task_catalog import MoCTaskCatalog, MoCTaskCatalogFocus
from app.services.maps_of_content.service import BUILDERS

_WORKFLOWS = "workflows"
_FOCUSES = "focuses"


def resolve_task(db: Session, task: MoCTaskCatalog) -> dict[str, Any]:
    """One catalog row → its rendered shape, with workflow + focuses resolved
    through the cards' BUILDERS path ({exists, available, label, routing})."""
    # Include artifact_id alongside the resolved {exists,available,label,
    # routing}: the frontend's mocDeepLink keys the FOCUS route on artifact_id
    # (tier=2&template=<id>), so the cell needs the template id, not just
    # routing. Same shape the cards' rows carry (builder + artifact_id +
    # routing).
    workflow = (
        {
            **BUILDERS[_WORKFLOWS](db, task.workflow_template_id, task.name),
            "artifact_id": task.workflow_template_id,
        }
        if task.workflow_template_id
        else None
    )
    focuses = [
        # authored label "" → the resolver returns the template's display_name.
        {
            **BUILDERS[_FOCUSES](db, f.focus_template_id, ""),
            "artifact_id": f.focus_template_id,
        }
        for f in task.focuses
    ]
    return {
        "id": task.id,
        "name": task.name,
        "icon": task.icon,
        "frequency": task.frequency,
        "task_type": task.task_type,
        "description": task.description,
        "display_order": task.display_order,
        "workflow": workflow,
        "focuses": focuses,
    }


def resolve_task_catalog(
    db: Session,
    *,
    vertical: str,
    scope: str = "vertical_default",
    tenant_id: str | None = None,
) -> list[dict[str, Any]]:
    """A vertical's active task catalog, each task resolved (workflow + focuses
    via the cards' resolver). Ordered by display_order then name."""
    rows = (
        db.query(MoCTaskCatalog)
        .filter(
            MoCTaskCatalog.scope == scope,
            MoCTaskCatalog.vertical == vertical,
            MoCTaskCatalog.tenant_id == tenant_id,
            MoCTaskCatalog.is_active.is_(True),
        )
        .order_by(MoCTaskCatalog.display_order, MoCTaskCatalog.name)
        .all()
    )
    return [resolve_task(db, t) for t in rows]


def upsert_task(
    db: Session,
    *,
    vertical: str,
    name: str,
    scope: str = "vertical_default",
    tenant_id: str | None = None,
    icon: str | None = None,
    frequency: str | None = None,
    task_type: str | None = None,
    description: str | None = None,
    workflow_template_id: str | None = None,
    focus_template_ids: Sequence[str] = (),
    display_order: int = 0,
    actor_id: str | None = None,
) -> MoCTaskCatalog:
    """Idempotent find-or-create by (scope, vertical, tenant_id, name) — the
    seed + assembly test build on this. On a re-run, updates mutable fields +
    REPLACES the focus set (so re-seeding to the same shape is a no-op net of
    timestamps). Caller commits."""
    task = (
        db.query(MoCTaskCatalog)
        .filter(
            MoCTaskCatalog.scope == scope,
            MoCTaskCatalog.vertical == vertical,
            MoCTaskCatalog.tenant_id == tenant_id,
            MoCTaskCatalog.name == name,
            MoCTaskCatalog.is_active.is_(True),
        )
        .first()
    )
    if task is None:
        task = MoCTaskCatalog(
            scope=scope, vertical=vertical, tenant_id=tenant_id, name=name,
            created_by=actor_id,
        )
        db.add(task)

    task.icon = icon
    task.frequency = frequency
    task.task_type = task_type
    task.description = description
    task.workflow_template_id = workflow_template_id
    task.display_order = display_order
    task.updated_by = actor_id
    # Replace the focus set (delete-orphan cascade clears the old join rows).
    task.focuses = [
        MoCTaskCatalogFocus(focus_template_id=fid, display_order=i)
        for i, fid in enumerate(focus_template_ids)
    ]
    db.flush()
    return task


# ── Full CRUD (Task Editing 2a) — the editable write path ──────────────

_UNSET: Any = object()


class TaskValidationError(ValueError):
    """A rejected task write (bad vocabulary value / unresolved ref) — HTTP 400."""


def _validate_task_refs(
    db: Session,
    *,
    vertical: str | None,
    frequency: str | None,
    task_type: str | None,
    workflow_template_id: str | None,
    focus_template_ids: Sequence[str],
) -> None:
    """Referential guard (NOT a silent-accept): frequency/type must exist in the
    vocabulary visible to `vertical`; the workflow/focus refs must resolve. None
    skips (clearing a field is valid)."""
    from app.services.maps_of_content import vocabulary

    if frequency is not None and not vocabulary.value_exists(
        db, kind="frequency", value=frequency, vertical=vertical
    ):
        raise TaskValidationError(
            f"frequency {frequency!r} is not in the vocabulary for vertical "
            f"{vertical!r} — add it to the vocabulary first"
        )
    if task_type is not None and not vocabulary.value_exists(
        db, kind="type", value=task_type, vertical=vertical
    ):
        raise TaskValidationError(
            f"task_type {task_type!r} is not in the vocabulary for vertical "
            f"{vertical!r} — add it to the vocabulary first"
        )
    if workflow_template_id is not None and db.execute(
        sql_text("SELECT 1 FROM workflow_templates WHERE id = :id"),
        {"id": workflow_template_id},
    ).first() is None:
        raise TaskValidationError(
            f"workflow_template_id {workflow_template_id!r} does not resolve"
        )
    for fid in focus_template_ids:
        if db.execute(
            sql_text("SELECT 1 FROM focus_templates WHERE id = :id"), {"id": fid}
        ).first() is None:
            raise TaskValidationError(f"focus_template_id {fid!r} does not resolve")


def get_task(db: Session, *, task_id: str) -> MoCTaskCatalog | None:
    return db.get(MoCTaskCatalog, task_id)


def create_task(
    db: Session,
    *,
    vertical: str,
    name: str,
    scope: str = "vertical_default",
    tenant_id: str | None = None,
    icon: str | None = None,
    frequency: str | None = None,
    task_type: str | None = None,
    description: str | None = None,
    workflow_template_id: str | None = None,
    focus_template_ids: Sequence[str] = (),
    display_order: int = 0,
    actor_id: str | None = None,
) -> MoCTaskCatalog:
    """Validate + insert a NEW task (rejects a duplicate name in the same scope —
    distinct from upsert_task's find-or-create). Caller commits."""
    dup = (
        db.query(MoCTaskCatalog)
        .filter(
            MoCTaskCatalog.scope == scope,
            MoCTaskCatalog.vertical == vertical,
            MoCTaskCatalog.tenant_id == tenant_id,
            MoCTaskCatalog.name == name,
            MoCTaskCatalog.is_active.is_(True),
        )
        .first()
    )
    if dup is not None:
        raise TaskValidationError(f"a task named {name!r} already exists in this scope")
    _validate_task_refs(
        db, vertical=vertical, frequency=frequency, task_type=task_type,
        workflow_template_id=workflow_template_id, focus_template_ids=focus_template_ids,
    )
    return upsert_task(
        db, vertical=vertical, name=name, scope=scope, tenant_id=tenant_id,
        icon=icon, frequency=frequency, task_type=task_type, description=description,
        workflow_template_id=workflow_template_id,
        focus_template_ids=focus_template_ids, display_order=display_order,
        actor_id=actor_id,
    )


def patch_task(
    db: Session,
    *,
    task_id: str,
    name: Any = _UNSET,
    icon: Any = _UNSET,
    frequency: Any = _UNSET,
    task_type: Any = _UNSET,
    description: Any = _UNSET,
    workflow_template_id: Any = _UNSET,
    focus_template_ids: Any = _UNSET,
    display_order: Any = _UNSET,
    actor_id: str | None = None,
) -> MoCTaskCatalog:
    """Partial update by id. _UNSET = leave alone; None = clear. Validates only
    the fields being SET. Caller commits."""
    task = db.get(MoCTaskCatalog, task_id)
    if task is None or not task.is_active:
        raise TaskValidationError(f"task {task_id!r} not found")

    new_focus = None if focus_template_ids is _UNSET else list(focus_template_ids)
    _validate_task_refs(
        db,
        vertical=task.vertical,
        frequency=None if frequency is _UNSET else frequency,
        task_type=None if task_type is _UNSET else task_type,
        workflow_template_id=None if workflow_template_id is _UNSET else workflow_template_id,
        focus_template_ids=new_focus or (),
    )

    if name is not _UNSET:
        task.name = name
    if icon is not _UNSET:
        task.icon = icon
    if frequency is not _UNSET:
        task.frequency = frequency
    if task_type is not _UNSET:
        task.task_type = task_type
    if description is not _UNSET:
        task.description = description
    if workflow_template_id is not _UNSET:
        task.workflow_template_id = workflow_template_id
    if display_order is not _UNSET:
        task.display_order = display_order
    if new_focus is not None:
        task.focuses = [
            MoCTaskCatalogFocus(focus_template_id=fid, display_order=i)
            for i, fid in enumerate(new_focus)
        ]
    task.updated_by = actor_id
    db.flush()
    return task


def delete_task(db: Session, *, task_id: str) -> bool:
    """Hard-delete the task; the focus-join rows clear via delete-orphan cascade.
    Returns False if the task didn't exist. Caller commits."""
    task = db.get(MoCTaskCatalog, task_id)
    if task is None:
        return False
    db.delete(task)
    db.flush()
    return True
