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
    # is_mirror (T-2.1c): the compiled-vs-mirror discriminator the Live toggle
    # needs — a MIRROR task can't go live (the §6 double-fire guard; the sweep's
    # `_resolve_go_live` forces dry-run even when is_live=True), so the frontend
    # must DISABLE the toggle rather than render a control that silently stays
    # dry. Same discriminator the resolver + sweep use:
    # template.mirrored_from_workflow_id.
    schedule_authority = "moc"
    runtime_schedule_summary = None
    if workflow is not None:
        from app.models.workflow import Workflow
        from app.models.workflow_template import WorkflowTemplate

        tmpl = db.get(WorkflowTemplate, task.workflow_template_id)
        workflow["is_mirror"] = (
            tmpl is not None and tmpl.mirrored_from_workflow_id is not None
        )
        # T-0 — WHO makes this task fire (the honesty badges key on it).
        if workflow["is_mirror"]:
            from app.services.maps_of_content.ponder import (
                _when_text, schedule_authority as _authority,
            )

            runtime = db.get(Workflow, tmpl.mirrored_from_workflow_id)
            schedule_authority = _authority(runtime)
            if schedule_authority == "runtime_scheduler":
                runtime_schedule_summary = _when_text(runtime).rstrip(".")
    focuses = [
        # authored label "" → the resolver returns the template's display_name.
        # Stored id FIRST, then the resolution spread: the resolver's rebound
        # `artifact_id` (the lineage's ACTIVE row after a version bump — the
        # ref-decay rebind) must win over the stored, possibly-stale join id
        # so the cell's deep-link opens the live version.
        {
            "artifact_id": f.focus_template_id,
            **BUILDERS[_FOCUSES](db, f.focus_template_id, ""),
        }
        for f in task.focuses
    ]
    # The DESCRIPTIVE triggers (MoC Triggers T-1b) + the derived Frequency —
    # both reuse the shipped `summarize_trigger` / `humanize_schedule` helpers so
    # the frontend never re-implements the humanize logic. `derived_frequency`
    # is the first ACTIVE schedule trigger's summary (None → the manual 2a
    # frequency stands; the non-destructive coexistence). Lazy import mirrors the
    # vocabulary import in _validate_task_refs (avoids an import cycle).
    from app.services.maps_of_content import triggers as _triggers

    active_triggers = sorted(
        (t for t in task.triggers if t.is_active), key=lambda t: t.display_order
    )
    trigger_payloads = [
        {
            "id": t.id,
            "kind": t.kind,
            "config": t.config,
            "label": t.label,
            "display_order": t.display_order,
            # T-2.1c: the live-promotion state (r117) — drives the Live/Dry-run
            # badge + toggle. The sweep only fires live when this AND the task
            # is compiled (see workflow.is_mirror above).
            "is_live": t.is_live,
            "summary": _triggers.summarize_trigger(t.kind, t.config),
        }
        for t in active_triggers
    ]
    schedule_trigger = next((t for t in active_triggers if t.kind == "schedule"), None)
    derived_frequency = (
        _triggers.humanize_schedule(schedule_trigger.config)
        if schedule_trigger
        else None
    )
    return {
        "id": task.id,
        "name": task.name,
        "icon": task.icon,
        "frequency": task.frequency,
        "derived_frequency": derived_frequency,
        "task_type": task.task_type,
        "description": task.description,
        "display_order": task.display_order,
        # Scope identity (MoC Tenant View): the merged tenant view labels
        # tenant_override rows so they're never confused with the defaults.
        "scope": task.scope,
        "tenant_id": task.tenant_id,
        "forked_from_task_id": task.forked_from_task_id,
        # T-0 authority badges (the map's truth chip).
        "schedule_authority": schedule_authority,
        "runtime_schedule_summary": runtime_schedule_summary,
        # Map Home — the recency rule reads change-time against engagement.
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "workflow": workflow,
        "focuses": focuses,
        "triggers": trigger_payloads,
    }


def resolve_task_catalog(
    db: Session,
    *,
    vertical: str | None,
    scope: str = "vertical_default",
    tenant_id: str | None = None,
) -> list[dict[str, Any]]:
    """A vertical's active task catalog, each task resolved (workflow + focuses
    via the cards' resolver). Ordered by display_order then name.

    TENANT VIEW (MoC Tenant View, 2026-07): passing `tenant_id` returns the
    MERGED set — the vertical's default rows PLUS that tenant's tenant_override
    rows — mirroring the schedule sweep's own fan-out (`_fanout_companies`): the
    honest "what fires for this tenant". Defaults order first, then the tenant's
    rows (each group display_order, name). Without `tenant_id`, byte-identical
    to the pre-tenant-view behavior (vertical_default only — non-regressive).

    (Pre-2026-07 the tenant_id param was an EXACT-match filter — vertical_default
    AND tenant_id=X, which matches nothing since default rows carry tenant_id
    NULL. Nothing depended on that always-empty path.)"""
    from sqlalchemy import and_, or_

    q = db.query(MoCTaskCatalog).filter(
        MoCTaskCatalog.vertical == vertical,
        MoCTaskCatalog.is_active.is_(True),
    )
    if tenant_id is None:
        q = q.filter(
            MoCTaskCatalog.scope == scope,
            MoCTaskCatalog.tenant_id.is_(None),
        )
    else:
        # THE YIELD (Tenant Ponder-Editor P2): a default this tenant has
        # FORKED is superseded by their version in THEIR merged view —
        # excluded here and only here. Every other tenant's read (and the
        # admin vertical read above) is untouched: the fork changes one
        # tenant's view, never the default itself.
        forked_source_ids = (
            db.query(MoCTaskCatalog.forked_from_task_id)
            .filter(
                MoCTaskCatalog.scope == "tenant_override",
                MoCTaskCatalog.tenant_id == tenant_id,
                MoCTaskCatalog.is_active.is_(True),
                MoCTaskCatalog.forked_from_task_id.isnot(None),
            )
        )
        q = q.filter(
            or_(
                and_(
                    MoCTaskCatalog.scope == "vertical_default",
                    MoCTaskCatalog.tenant_id.is_(None),
                    MoCTaskCatalog.id.notin_(forked_source_ids),
                ),
                and_(
                    MoCTaskCatalog.scope == "tenant_override",
                    MoCTaskCatalog.tenant_id == tenant_id,
                ),
            )
        )
    rows = q.order_by(
        # defaults first, then the tenant's overrides; stable within each group
        (MoCTaskCatalog.scope == "tenant_override").asc(),
        MoCTaskCatalog.display_order,
        MoCTaskCatalog.name,
    ).all()
    return [resolve_task(db, t) for t in rows]


def upsert_task(
    db: Session,
    *,
    vertical: str | None,
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
    vertical: str | None,
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
    distinct from upsert_task's find-or-create). Caller commits.

    SCOPE COHERENCE (MoC Hierarchy H-2): a platform_default task is
    vertical-LESS (it fans out to every tenant — `_fanout_companies`); a
    vertical/tenant task requires its vertical. Validated here so the platform
    page's Add-task can't author an incoherent row."""
    if scope == "platform_default":
        if vertical is not None:
            raise TaskValidationError(
                "a platform_default task is vertical-less — omit `vertical`"
            )
    elif vertical is None:
        raise TaskValidationError(f"scope {scope!r} requires a vertical")
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
