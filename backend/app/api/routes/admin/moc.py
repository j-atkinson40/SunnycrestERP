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
    # None = a platform_default (vertical-less) task — H-2's platform page.
    vertical: str | None = None
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


# ─── Planning items (r123) — the personal build-backlog ──────────────
# (declared before the page `/{page_id}` catch-all)


# ── The Ponder (P1) — the derived walkthrough script + caption authoring ────


@router.get("/ponder/document-preview")
def admin_ponder_document_preview(
    template_key: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Lazy live-render of a template's REAL body for the ponder's document
    beat (Ponder Enrichment). Resolved at request time — never cached stale;
    a template edit in Studio reflects on the next open. Delegates to the
    ONE preview path (P2 — the tenant router shares it)."""
    from app.services.maps_of_content import ponder

    try:
        return ponder.render_document_preview(db, template_key)
    except ponder.PonderError as e:
        code = 404 if "not found" in str(e).lower() else 422
        raise HTTPException(status_code=code, detail=str(e))


class _SaveCaption(BaseModel):
    beat_key: str
    text: str | None = None  # None/blank clears → derived fallback returns


@router.get("/ponder/users")
def admin_ponder_user_search(
    q: str = "",
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Typeahead for the audience picker's specific-people chips (Tenant
    Ponder-Editor P1 rider). Active users by name/email, capped at 8."""
    from app.models.company import Company
    from app.models.user import User

    term = (q or "").strip()
    if len(term) < 2:
        return []
    query = (
        db.query(User, Company.name)
        .outerjoin(Company, Company.id == User.company_id)
        .filter(User.is_active.is_(True))
    )
    # Every typed word must match SOME field — "alex acc" finds Alex
    # Accountant (natural first-last typing), not nothing.
    for word in term.split():
        like = f"%{word}%"
        query = query.filter(
            (User.first_name.ilike(like))
            | (User.last_name.ilike(like))
            | (User.email.ilike(like)),
        )
    rows = query.order_by(User.first_name, User.last_name).limit(8).all()
    return [
        {
            "id": u.id,
            "name": f"{u.first_name} {u.last_name}".strip() or u.email,
            "email": u.email,
            "company_name": company_name,
        }
        for u, company_name in rows
    ]


@router.get("/ponder/{task_id}")
def admin_get_ponder_script(
    task_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """The live-derived ponder script for a task's workflow (never baked)."""
    from app.services.maps_of_content import ponder

    try:
        return ponder.build_ponder_script(db, task_id)
    except ponder.PonderError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/ponder/{task_id}/captions")
def admin_save_ponder_caption(
    task_id: str,
    body: _SaveCaption,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Author (or clear) one beat's caption — platform pedagogy, admin-scoped."""
    from app.services.maps_of_content import ponder

    try:
        captions = ponder.save_caption(db, task_id, body.beat_key, body.text)
    except ponder.PonderError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"captions": captions}


# ─── Task offer-reach (Tenant Ponder-Editor P3) — the deliberate boundary ────


@router.get("/tasks/{task_id}/offer-preview")
def admin_task_offer_preview(
    task_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """What 'offer this change to tenant versions' would do — the forks +
    each one's field diff, shown BEFORE the deliberate act."""
    from app.services.maps_of_content import task_offers

    try:
        return task_offers.offer_preview(db, task_id=task_id)
    except task_offers.TaskOfferError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/area-ponder/{vertical}/{area}")
def admin_area_ponder(
    vertical: str,
    area: str,
    tenant_id: str | None = None,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """The area overview ponder, platform view (optionally through a
    tenant's merged lens via tenant_id). The caption editor mounts here —
    the philosophy layer is platform pedagogy."""
    from app.services.maps_of_content import area_ponder

    try:
        return area_ponder.build_area_ponder_script(
            db, vertical=vertical, area=area, company_id=tenant_id,
        )
    except area_ponder.AreaPonderError as e:
        raise HTTPException(status_code=404, detail=str(e))


class _AreaCaption(BaseModel):
    beat_key: str
    text: str | None = None


@router.patch("/area-ponder/{vertical}/{area}/captions")
def admin_save_area_caption(
    vertical: str,
    area: str,
    body: _AreaCaption,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Author (or clear) a philosophy caption — platform-admin only; the
    composition row is created on first authoring."""
    from app.services.maps_of_content import area_ponder

    captions = area_ponder.save_area_caption(
        db, vertical=vertical, area=area, beat_key=body.beat_key, text=body.text,
    )
    return {"captions": captions}


@router.post("/tasks/{task_id}/adopt-schedule", status_code=201)
def admin_adopt_schedule(
    task_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Transfer T-1 — THE ATOMIC ADOPT: schedule authority moves runtime→moc
    in one transaction (the carried trigger promotes; the runtime schedule
    retires). ONE-WAY — de-promoting the MoC trigger is the off switch; the
    runtime entry does not resurrect. The confirm surface gates this
    operator-side; per-task, operator-initiated."""
    from app.services.maps_of_content import adopt

    try:
        return adopt.adopt_schedule(db, task_id=task_id, actor_id=admin.id)
    except adopt.AdoptError as e:
        raise HTTPException(status_code=400, detail=str(e))


class _PublishTaskOffer(BaseModel):
    patch_notes: str | None = None


@router.post("/tasks/{task_id}/offer", status_code=201)
def admin_publish_task_offer(
    task_id: str,
    body: _PublishTaskOffer,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """THE DELIBERATE MOMENT (the V-2 publish pattern at the task tier):
    an explicit act with a note — never offer-on-every-save. Creates one
    pending offer per fork that actually differs; supersedes prior live
    offers per edge. Task-row fields only — the WORKFLOW is shared under
    forks and needs no offer."""
    from app.services.maps_of_content import task_offers

    try:
        return task_offers.publish_task_update(
            db, task_id=task_id, patch_notes=body.patch_notes, actor_id=admin.id,
        )
    except task_offers.TaskOfferError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


class _SetWorkflowParam(BaseModel):
    value: Any = None


@router.put("/ponder/workflows/{workflow_id}/params/{step_key}/{param_key}")
def admin_set_workflow_param(
    workflow_id: str,
    step_key: str,
    param_key: str,
    body: _SetWorkflowParam,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Tenant Ponder-Editor P1 — set (or clear, value=null) the PLATFORM-level
    live value of a declared step param. Writes `current_value` on the
    company_id-NULL row: the engine seam merges it into step config at fire
    time for every tenant without their own override; the ponder derivation
    reflects it immediately (one resolution path). Only DECLARED,
    is_configurable params accept a value; validation failures are LOUD
    (400 with the named reason — never a silent fallback)."""
    from app.models.workflow import WorkflowStepParam
    from app.services.workflows.step_params import (
        StepParamValidationError, validate_param_value,
    )

    row = (
        db.query(WorkflowStepParam)
        .filter(
            WorkflowStepParam.workflow_id == workflow_id,
            WorkflowStepParam.step_key == step_key,
            WorkflowStepParam.param_key == param_key,
            WorkflowStepParam.company_id.is_(None),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Param not declared on this step")
    if not row.is_configurable:
        raise HTTPException(status_code=400, detail="Param is not configurable")
    try:
        validate_param_value(
            param_type=row.param_type, validation=row.validation,
            value=body.value, label=f"{step_key}.{param_key}",
        )
    except StepParamValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # user_multi_select: existence-check at the boundary (a db lives here;
    # fire-time validation stays pure). An unknown id is rejected LOUDLY —
    # never stored to resolve-to-nothing later.
    if row.param_type == "user_multi_select" and isinstance(body.value, list) and body.value:
        from app.models.user import User

        found = {
            u for (u,) in db.query(User.id).filter(User.id.in_([str(v) for v in body.value]))
        }
        unknown = [v for v in body.value if str(v) not in found]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"{step_key}.{param_key}: unknown user id(s) {unknown}",
            )
    row.current_value = body.value
    db.commit()
    return {
        "saved": True,
        "platform_value": row.current_value,
        "effective_value": (
            row.current_value if row.current_value is not None else row.default_value
        ),
        "live": row.current_value is not None,
    }


class _CreatePlanningItem(BaseModel):
    scope: Literal["platform_default", "vertical_default"] = "vertical_default"
    vertical: str | None = None
    kind: str
    title: str
    description: str | None = None
    status: str = "planned"
    display_order: int = 0


class _PatchPlanningItem(BaseModel):
    title: str | None = None
    description: str | None = None
    kind: str | None = None
    status: str | None = None
    display_order: int | None = None


@router.get("/planning")
def admin_list_planning(
    scope: Scope = Query("vertical_default"),
    vertical: str | None = Query(None),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """THE PERSONAL LENS: the authenticated user's items for this map only."""
    from app.services.maps_of_content import planning

    items = planning.list_items(
        db, owner_user_id=admin.id, scope=scope, vertical=vertical
    )
    return [planning.to_payload(i) for i in items]


@router.post("/planning", status_code=201)
def admin_create_planning(
    body: _CreatePlanningItem,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    from app.services.maps_of_content import planning

    try:
        item = planning.create_item(
            db, owner_user_id=admin.id, scope=body.scope,
            vertical=body.vertical, kind=body.kind, title=body.title,
            description=body.description, status=body.status,
            display_order=body.display_order,
        )
    except planning.PlanningValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return planning.to_payload(item)


@router.patch("/planning/{item_id}")
def admin_patch_planning(
    item_id: str,
    body: _PatchPlanningItem,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Partial update — only sent fields apply; OWNER-CHECKED (yours only)."""
    from app.services.maps_of_content import planning

    kwargs = {k: getattr(body, k) for k in body.model_fields_set}
    try:
        item = planning.patch_item(
            db, item_id=item_id, owner_user_id=admin.id, **kwargs
        )
    except planning.PlanningValidationError as exc:
        db.rollback()
        code = 404 if "not found" in str(exc) else 400
        raise HTTPException(status_code=code, detail=str(exc))
    return planning.to_payload(item)


@router.delete("/planning/{item_id}", status_code=200)
def admin_delete_planning(
    item_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    from app.services.maps_of_content import planning

    try:
        planning.delete_item(db, item_id=item_id, owner_user_id=admin.id)
    except planning.PlanningValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    return {"deleted": True, "id": item_id}


# ─── Focus variations (Focus Variations V-1) — the guided flow ──────────
# (declared before the page `/{page_id}` catch-all so `/focus-variations`
# resolves)


class _CreateFocusVariation(BaseModel):
    core_id: str
    display_name: str
    verticals: list[str]
    task_ids: list[str] = []


@router.post("/focus-variations", status_code=201)
def admin_create_focus_variation(
    body: _CreateFocusVariation,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """One call materializes the guided flow: the Tier 2 variation (core-
    version pinned), the multi-vertical join rows, the task wiring (the focus
    join from the FOCUS side), and the auto-authored refs on each chosen
    vertical's map — creation lights the maps."""
    from app.services.maps_of_content.focus_variations import (
        FocusVariationError,
        create_focus_variation,
    )

    try:
        return create_focus_variation(
            db,
            core_id=body.core_id,
            display_name=body.display_name,
            verticals=body.verticals,
            task_ids=body.task_ids,
            actor_id=admin.id,
        )
    except FocusVariationError as exc:
        db.rollback()
        code = 404 if "not found" in str(exc) else 400
        raise HTTPException(status_code=code, detail=str(exc))
    except TaskValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


# ─── Offered updates (Focus Variations V-2) — publish / offers ───────────
# (declared before the page `/{page_id}` catch-all)


class _PublishCore(BaseModel):
    core_id: str
    patch_notes: str | None = None


class _AcceptOffer(BaseModel):
    # {chrome_field: "keep" | "take"} — take-new drops the target's override
    # so the new default shows through; keep-mine (default) touches nothing.
    choices: dict[str, str] = {}


def _translate_update_error(exc) -> HTTPException:
    detail: Any = str(exc)
    if getattr(exc, "latest_offer_id", None):
        detail = {"message": str(exc), "latest_offer_id": exc.latest_offer_id}
    code = 404 if "not found" in str(exc) else 409
    return HTTPException(status_code=code, detail=detail)


@router.get("/focus-publishes/preview")
def admin_focus_publish_preview(
    core_id: str = Query(...),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """The unpublished delta + the derived patch-notes scaffold."""
    from app.services.artifact_updates import (
        ArtifactUpdateError,
        get_publish_preview,
    )

    try:
        return get_publish_preview(db, core_id=core_id)
    except ArtifactUpdateError as exc:
        raise _translate_update_error(exc)


@router.post("/focus-publishes", status_code=201)
def admin_publish_core(
    body: _PublishCore,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """The explicit release: records the publish, stamps the boundary,
    creates one pending offer per downstream variation (superseding any
    prior live offers — the chain-collapse rule)."""
    from app.services.artifact_updates import (
        ArtifactUpdateError,
        publish_core_update,
    )

    try:
        return publish_core_update(
            db, core_id=body.core_id, patch_notes=body.patch_notes,
            actor_id=admin.id,
        )
    except ArtifactUpdateError as exc:
        db.rollback()
        raise _translate_update_error(exc)


@router.get("/update-offers/state")
def admin_offer_states(
    target_slugs: str = Query(..., description="comma-separated template slugs"),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Per-slug offer state for the map's pills (badge = pending; gap
    chip = behind-but-quiet)."""
    from app.services.artifact_updates import offer_states_for_targets

    slugs = [s.strip() for s in target_slugs.split(",") if s.strip()]
    return offer_states_for_targets(db, target_slugs=slugs)


@router.get("/update-offers/{offer_id}")
def admin_get_offer(
    offer_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    from app.services.artifact_updates import ArtifactUpdateError, get_offer

    try:
        return get_offer(db, offer_id)
    except ArtifactUpdateError as exc:
        raise _translate_update_error(exc)


@router.post("/update-offers/{offer_id}/accept")
def admin_accept_offer(
    offer_id: str,
    body: _AcceptOffer,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    from app.services.artifact_updates import ArtifactUpdateError, accept_offer

    try:
        return accept_offer(
            db, offer_id=offer_id, choices=body.choices, actor_id=admin.id
        )
    except ArtifactUpdateError as exc:
        db.rollback()
        raise _translate_update_error(exc)


@router.post("/update-offers/{offer_id}/decline")
def admin_decline_offer(
    offer_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    from app.services.artifact_updates import ArtifactUpdateError, decline_offer

    try:
        return decline_offer(db, offer_id=offer_id, actor_id=admin.id)
    except ArtifactUpdateError as exc:
        db.rollback()
        raise _translate_update_error(exc)


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
    vertical: str | None = Query(None),
    tenant_id: str | None = Query(None),
    scope: str = Query("vertical_default"),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """The vertical's task catalog (MoC-2b). Each task's ONE workflow + MANY
    focuses are resolved through the SAME `BUILDERS` path the cards use, so the
    frontend's `mocDeepLink` produces byte-identical hrefs. A reference that
    doesn't exist yet resolves orphan-tolerant (workflow null / focus
    available=False) — never errors. Empty list when no tasks are seeded."""
    return resolve_task_catalog(db, vertical=vertical, tenant_id=tenant_id, scope=scope)


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
