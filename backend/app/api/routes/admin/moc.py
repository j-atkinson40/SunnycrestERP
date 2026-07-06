"""Maps of Content — admin platform router (MoC Phase 1).

Mounted at `/api/platform/admin/moc` (get_current_platform_user). A thin
realm layer over the realm-agnostic `maps_of_content` service — auth +
response shaping live here; the service takes operational primitives only,
so a future tenant router (`/api/v1/moc/*`, get_current_user) reuses it
unchanged.

    GET    /                 — list pages (scope / vertical / tenant filters)
    GET    /read             — resolved page for a context (3-tier walk),
                               references resolved for rendering
    POST   /                 — create a page
    GET    /{page_id}        — single raw page (authoring editor)
    GET    /{page_id}/read   — resolved page by id (references resolved)
    PATCH  /{page_id}        — update title/description/slug/sections
    DELETE /{page_id}        — soft-delete (frees the identity tuple)
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.moc_page import MoCPage
from app.models.platform_user import PlatformUser
from app.services import maps_of_content as moc
from app.services.maps_of_content import trigger_events as trigger_events_svc
from app.services.maps_of_content import triggers as triggers_svc
from app.services.maps_of_content import vocabulary as vocab
from app.services.maps_of_content.task_catalog import (
    TaskValidationError,
    create_task,
    delete_task,
    patch_task,
    resolve_task_catalog,
)

logger = logging.getLogger(__name__)
router = APIRouter()

Scope = Literal["platform_default", "vertical_default", "tenant_override"]


# ─── Task vocabulary (Task Editing 2a) — constrained-editable value store ──


class _CreateVocab(BaseModel):
    kind: Literal["frequency", "type"]
    value: str
    scope: Scope = "platform_default"
    vertical: str | None = None
    display_order: int = 0


@router.get("/vocabulary")
def admin_list_vocabulary(
    kind: Literal["frequency", "type"] | None = Query(None),
    vertical: str | None = Query(None),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """The active vocabulary for the picker — platform values + (if given) the
    vertical's. The constrained set a task's frequency/type must come from."""
    rows = vocab.list_values(db, kind=kind, vertical=vertical)
    return [
        {"id": r.id, "kind": r.kind, "value": r.value, "scope": r.scope,
         "vertical": r.vertical, "display_order": r.display_order,
         "is_active": r.is_active}
        for r in rows
    ]


@router.post("/vocabulary", status_code=201)
def admin_add_vocabulary(
    body: _CreateVocab,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Add a value (find-or-create; reactivates a soft-deleted match). The
    editable part — a new value is a row, no code change."""
    try:
        row = vocab.add_value(
            db, kind=body.kind, value=body.value, scope=body.scope,
            vertical=body.vertical, display_order=body.display_order,
            actor_id=admin.id,
        )
        db.commit()
    except vocab.VocabularyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"id": row.id, "kind": row.kind, "value": row.value, "scope": row.scope,
            "vertical": row.vertical, "is_active": row.is_active}


@router.delete("/vocabulary/{value_id}", status_code=200)
def admin_deactivate_vocabulary(
    value_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Soft-delete (is_active=False) — tasks referencing the value don't orphan."""
    try:
        row = vocab.deactivate_value(db, value_id=value_id, actor_id=admin.id)
        db.commit()
    except vocab.VocabularyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"id": row.id, "is_active": row.is_active}


# ─── Task catalog CRUD (Task Editing 2a) ──────────────────────────────


class _CreateTask(BaseModel):
    vertical: str
    name: str
    scope: Scope = "vertical_default"
    tenant_id: str | None = None
    icon: str | None = None
    frequency: str | None = None
    task_type: str | None = None
    description: str | None = None
    workflow_template_id: str | None = None
    focus_template_ids: list[str] = []
    display_order: int = 0


class _PatchTask(BaseModel):
    # All optional; only the fields the client SENDS are applied (model_fields_set).
    name: str | None = None
    icon: str | None = None
    frequency: str | None = None
    task_type: str | None = None
    description: str | None = None
    workflow_template_id: str | None = None
    focus_template_ids: list[str] | None = None
    display_order: int | None = None


def _task_payload(task) -> dict:
    return {
        "id": task.id, "vertical": task.vertical, "scope": task.scope,
        "name": task.name, "icon": task.icon, "frequency": task.frequency,
        "task_type": task.task_type, "description": task.description,
        "workflow_template_id": task.workflow_template_id,
        "focus_template_ids": [f.focus_template_id for f in task.focuses],
        "display_order": task.display_order,
    }


@router.post("/tasks", status_code=201)
def admin_create_task(
    body: _CreateTask,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Create a task (validates frequency/type against the vocabulary + the
    workflow/focus refs). 400 on a bad value (never silently accepted)."""
    try:
        task = create_task(
            db, vertical=body.vertical, name=body.name, scope=body.scope,
            tenant_id=body.tenant_id, icon=body.icon, frequency=body.frequency,
            task_type=body.task_type, description=body.description,
            workflow_template_id=body.workflow_template_id,
            focus_template_ids=body.focus_template_ids,
            display_order=body.display_order, actor_id=admin.id,
        )
        db.commit()
    except TaskValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return _task_payload(task)


@router.patch("/tasks/{task_id}")
def admin_patch_task(
    task_id: str,
    body: _PatchTask,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Partial update — only the sent fields apply (a sent null clears a field)."""
    kwargs = {k: getattr(body, k) for k in body.model_fields_set}
    try:
        task = patch_task(db, task_id=task_id, actor_id=admin.id, **kwargs)
        db.commit()
    except TaskValidationError as exc:
        db.rollback()
        code = 404 if "not found" in str(exc) else 400
        raise HTTPException(status_code=code, detail=str(exc))
    return _task_payload(task)


@router.delete("/tasks/{task_id}", status_code=200)
def admin_delete_task(
    task_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Delete a task; the focus-join rows + triggers clear via delete-orphan +
    the FK's ON DELETE CASCADE."""
    deleted = delete_task(db, task_id=task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="task not found")
    db.commit()
    return {"deleted": True, "id": task_id}


# ─── Trigger event catalog (MoC Triggers T-1a) — curated editable vocabulary ──
# (declared before the page `/{page_id}` catch-all so `/trigger-events` resolves)


class _AddEvent(BaseModel):
    event_key: str
    label: str
    entity: str | None = None
    filterable_fields: list[dict[str, Any]] = []
    scope: Scope = "platform_default"
    vertical: str | None = None
    display_order: int = 0


def _event_payload(ev) -> dict:
    return {
        "id": ev.id, "event_key": ev.event_key, "label": ev.label,
        "entity": ev.entity, "filterable_fields": ev.filterable_fields,
        "scope": ev.scope, "vertical": ev.vertical, "is_active": ev.is_active,
        "display_order": ev.display_order,
    }


@router.get("/trigger-events")
def admin_list_trigger_events(
    vertical: str | None = Query(None),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """The curated event menu for the event-trigger picker — platform events +
    (if given) the vertical's. Each carries its filterable_fields."""
    return [_event_payload(e) for e in trigger_events_svc.list_events(db, vertical=vertical)]


@router.post("/trigger-events", status_code=201)
def admin_add_trigger_event(
    body: _AddEvent,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Add a catalog event (find-or-create). The editable vocabulary — a new
    event is a row, no code change. (It does NOT fire — descriptive metadata.)"""
    try:
        ev = trigger_events_svc.add_event(
            db, event_key=body.event_key, label=body.label, entity=body.entity,
            filterable_fields=body.filterable_fields, scope=body.scope,
            vertical=body.vertical, display_order=body.display_order,
            actor_id=admin.id,
        )
        db.commit()
    except trigger_events_svc.EventCatalogError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return _event_payload(ev)


@router.delete("/trigger-events/{event_id}", status_code=200)
def admin_deactivate_trigger_event(
    event_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Soft-delete — triggers referencing the event don't orphan."""
    try:
        ev = trigger_events_svc.deactivate_event(db, event_id=event_id, actor_id=admin.id)
        db.commit()
    except trigger_events_svc.EventCatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"id": ev.id, "is_active": ev.is_active}


# ─── Task triggers CRUD (MoC Triggers T-1a) — the descriptive trigger collection


class _AddTrigger(BaseModel):
    kind: Literal["schedule", "event", "manual"]
    config: dict[str, Any] = {}
    label: str | None = None
    display_order: int = 0


class _PatchTrigger(BaseModel):
    kind: Literal["schedule", "event", "manual"] | None = None
    config: dict[str, Any] | None = None
    label: str | None = None
    display_order: int | None = None
    is_active: bool | None = None
    # T-2.1b live-promotion. Setting true does NOT alone make a fire live — the
    # sweep additionally requires the task to be a COMPILED (non-mirror) workflow.
    is_live: bool | None = None


def _trigger_payload(trig) -> dict:
    return {
        "id": trig.id, "task_catalog_id": trig.task_catalog_id, "kind": trig.kind,
        "config": trig.config, "label": trig.label,
        "display_order": trig.display_order, "is_active": trig.is_active,
        "is_live": trig.is_live,
        # The chip label (reuses the shipped humanize helper — same summary the
        # task-read path computes, so the panel + table agree with no TS drift).
        "summary": triggers_svc.summarize_trigger(trig.kind, trig.config),
    }


@router.get("/tasks/{task_id}/triggers")
def admin_list_task_triggers(
    task_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """A task's DESCRIPTIVE triggers (schedule|event|manual). They do NOT fire —
    metadata for the deferred execution bridge."""
    return [_trigger_payload(t) for t in triggers_svc.list_triggers(db, task_catalog_id=task_id)]


@router.post("/tasks/{task_id}/triggers", status_code=201)
def admin_add_task_trigger(
    task_id: str,
    body: _AddTrigger,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Attach a trigger (validates SHAPE — schedule spec / event+conditions-list /
    manual). 400 on a bad shape (never silently accepted); 404 if the task is
    unknown."""
    try:
        trig = triggers_svc.add_trigger(
            db, task_catalog_id=task_id, kind=body.kind, config=body.config,
            label=body.label, display_order=body.display_order, actor_id=admin.id,
        )
        db.commit()
    except triggers_svc.TriggerValidationError as exc:
        db.rollback()
        code = 404 if "not found" in str(exc) else 400
        raise HTTPException(status_code=code, detail=str(exc))
    return _trigger_payload(trig)


@router.patch("/triggers/{trigger_id}")
def admin_patch_trigger(
    trigger_id: str,
    body: _PatchTrigger,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Partial update — only the sent fields apply; re-validates the resulting
    (kind, config)."""
    kwargs = {k: getattr(body, k) for k in body.model_fields_set}
    try:
        trig = triggers_svc.patch_trigger(db, trigger_id=trigger_id, actor_id=admin.id, **kwargs)
        db.commit()
    except triggers_svc.TriggerValidationError as exc:
        db.rollback()
        code = 404 if "not found" in str(exc) else 400
        raise HTTPException(status_code=code, detail=str(exc))
    return _trigger_payload(trig)


@router.delete("/triggers/{trigger_id}", status_code=200)
def admin_delete_trigger(
    trigger_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Delete a trigger."""
    if not triggers_svc.delete_trigger(db, trigger_id=trigger_id):
        raise HTTPException(status_code=404, detail="trigger not found")
    db.commit()
    return {"deleted": True, "id": trigger_id}


# ─── Schedule-fire run log (T-2.1a observability) — see what fired dry-run ──


@router.get("/schedule-runs")
def admin_list_schedule_runs(
    limit: int = Query(50, ge=1, le=200),
    trigger_id: str | None = Query(None),
    company_id: str | None = Query(None),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Recent MoC schedule fires + their "would do X" records. `trigger_id`
    (T-2.1c) scopes to one trigger — the go-live confirm fetches the latest
    preview (limit=1) for the trigger being promoted, so the confirm shows the
    REAL previewed effect. (Fidelity caveat: a dry-run fire whose branching
    depends on a suppressed effect-step's output may not perfectly predict live.)"""
    from app.services.maps_of_content.schedule_sweep import list_schedule_runs

    return list_schedule_runs(
        db, limit=limit, trigger_id=trigger_id, company_id=company_id
    )


# ─── Pydantic shapes ─────────────────────────────────────────────


class _PageResponse(BaseModel):
    id: str
    scope: str
    vertical: str | None
    tenant_id: str | None
    slug: str
    title: str
    description: str | None
    sections: list[Any]


class _CreatePage(BaseModel):
    scope: Scope = "vertical_default"
    vertical: str | None = None
    tenant_id: str | None = None
    slug: str
    title: str
    description: str | None = None
    sections: list[Any] = []


class _UpdatePage(BaseModel):
    title: str | None = None
    description: str | None = None
    slug: str | None = None
    sections: list[Any] | None = None


def _row_to_response(row: MoCPage) -> _PageResponse:
    return _PageResponse(
        id=row.id,
        scope=row.scope,
        vertical=row.vertical,
        tenant_id=row.tenant_id,
        slug=row.slug,
        title=row.title,
        description=row.description,
        sections=row.sections or [],
    )


# ─── Endpoints ───────────────────────────────────────────────────


@router.get("/", response_model=list[_PageResponse])
def admin_list_pages(
    scope: Scope | None = Query(None),
    vertical: str | None = Query(None),
    tenant_id: str | None = Query(None),
    include_inactive: bool = Query(False),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    rows = moc.list_pages(
        db,
        scope=scope,
        vertical=vertical,
        tenant_id=tenant_id,
        include_inactive=include_inactive,
    )
    return [_row_to_response(r) for r in rows]


@router.get("/read")
def admin_read_for_context(
    vertical: str | None = Query(None),
    tenant_id: str | None = Query(None),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """The resolved page for a (vertical, tenant) context — the 3-tier walk
    + reference resolution. The page surface's read path. 404 when no page
    resolves for the context."""
    view = moc.read_for_context(db, vertical=vertical, tenant_id=tenant_id)
    if view is None:
        raise HTTPException(status_code=404, detail="no MoC page for context")
    return view


@router.get("/tasks")
def admin_read_task_catalog(
    vertical: str = Query(...),
    tenant_id: str | None = Query(None),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """The vertical's task catalog (MoC-2b). Each task's ONE workflow + MANY
    focuses are resolved through the SAME `BUILDERS` path the cards use, so the
    frontend's `mocDeepLink` produces byte-identical hrefs. A reference that
    doesn't exist yet resolves orphan-tolerant (workflow null / focus
    available=False) — never errors. Empty list when no tasks are seeded."""
    return resolve_task_catalog(db, vertical=vertical, tenant_id=tenant_id)


@router.post("/", response_model=_PageResponse, status_code=201)
def admin_create_page(
    body: _CreatePage,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    try:
        row = moc.create_page(
            db,
            scope=body.scope,
            vertical=body.vertical,
            tenant_id=body.tenant_id,
            slug=body.slug,
            title=body.title,
            description=body.description,
            sections=body.sections,
            actor_id=admin.id,
        )
    except moc.InvalidReference as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _row_to_response(row)


@router.get("/{page_id}", response_model=_PageResponse)
def admin_get_page(
    page_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    row = moc.get_page(db, page_id)
    if row is None:
        raise HTTPException(status_code=404, detail="page not found")
    return _row_to_response(row)


@router.get("/{page_id}/read")
def admin_read_page(
    page_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    view = moc.read_page(db, page_id)
    if view is None:
        raise HTTPException(status_code=404, detail="page not found")
    return view


@router.patch("/{page_id}", response_model=_PageResponse)
def admin_update_page(
    page_id: str,
    body: _UpdatePage,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    try:
        row = moc.update_page(
            db,
            page_id,
            actor_id=admin.id,
            title=body.title,
            description=body.description,
            slug=body.slug,
            sections=body.sections,
        )
    except moc.InvalidReference as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if row is None:
        raise HTTPException(status_code=404, detail="page not found")
    return _row_to_response(row)


@router.delete("/{page_id}", status_code=204)
def admin_delete_page(
    page_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    ok = moc.delete_page(db, page_id, actor_id=admin.id)
    if not ok:
        raise HTTPException(status_code=404, detail="page not found")
