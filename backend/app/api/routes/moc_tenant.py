"""The Bridgeable Map — tenant MoC router (Tenant Ponder-Editor P2).

Mounted at `/api/v1/moc` (tenant realm). A thin realm layer over the SAME
realm-agnostic maps_of_content services the admin router consumes — the
canon pattern: auth + company scoping live here; the services take
operational primitives only.

COMPANY SCOPING THROUGHOUT (the isolation pins):
  * tasks    — the tenant's MERGED view (their vertical's defaults, with
               forked defaults YIELDING to their versions, plus their own
               rows). A task outside that set is NOT FOUND — never a hint
               it exists (the ownership semantics).
  * ponder   — derived company-scoped: their param overrides in the
               effective chain, their people in audience counts, their
               fires in the garnish.
  * users    — the audience typeahead searches THEIR company only.
  * writes   — require_admin; trigger/caption writes land on THEIR
               tenant_override rows only (a shared task forks first — the
               prompted fork); NO tenant live-promotion this phase (the
               tenant trigger PATCH shape simply has no is_live field).

VIEW for all tenant users; EDIT for tenant admins (require_admin — the
cheap `automations.edit` permission key is a later refinement).
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.company import Company
from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.user import User
from app.services.maps_of_content import trigger_events as trigger_events_svc
from app.services.maps_of_content import triggers as triggers_svc
from app.services.maps_of_content.task_catalog import resolve_task, resolve_task_catalog
from app.services.maps_of_content.task_fork import TaskForkError, fork_task_for_tenant

logger = logging.getLogger(__name__)
router = APIRouter()


def _company(db: Session, user: User) -> Company:
    company = db.get(Company, user.company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def _visible_task(db: Session, task_id: str, company: Company) -> MoCTaskCatalog:
    """A task the tenant can SEE: their vertical's defaults or their own
    rows. Anything else is NOT FOUND — never a hint it exists."""
    task = db.get(MoCTaskCatalog, task_id)
    if task is None or not task.is_active:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.scope == "tenant_override" and task.tenant_id == company.id:
        return task
    if (
        task.scope == "vertical_default"
        and task.tenant_id is None
        and (task.vertical or "").lower() == (company.vertical or "").lower()
    ):
        return task
    raise HTTPException(status_code=404, detail="Task not found")


def _owned_task(db: Session, task_id: str, company: Company) -> MoCTaskCatalog:
    """A task the tenant can EDIT: their own tenant_override row. A visible-
    but-shared task answers 403 with the fork nudge (the frontend prompts
    the fork BEFORE reaching here — this is defense in depth)."""
    task = _visible_task(db, task_id, company)
    if task.scope != "tenant_override" or task.tenant_id != company.id:
        raise HTTPException(
            status_code=403,
            detail="This is the shared version — create your own version to customize it",
        )
    return task


# ─── The map read (view for ALL tenant users) ───────────────────────────────


@router.get("/tasks")
def tenant_list_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The tenant's MERGED task view — their vertical's defaults (forked ones
    yielding to their versions) + their own rows, each resolved."""
    company = _company(db, current_user)
    tasks = resolve_task_catalog(db, vertical=company.vertical, tenant_id=company.id)
    # P3 offer-reach: the quiet badge state on THEIR forked rows (pending →
    # badge; declined → the recallable gap chip). Their offers only.
    from app.services.maps_of_content import task_offers

    fork_ids = [t["id"] for t in tasks if t["scope"] == "tenant_override"]
    states = task_offers.offer_states_for_forks(
        db, company_id=company.id, fork_task_ids=fork_ids
    )
    for t in tasks:
        if t["id"] in states:
            t["offer_state"] = states[t["id"]]
    return {"vertical": company.vertical, "tasks": tasks}


@router.get("/ponder/users")
def tenant_ponder_user_search(
    q: str = "",
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """The audience typeahead — THEIR company's active users only."""
    term = (q or "").strip()
    if len(term) < 2:
        return []
    query = db.query(User).filter(
        User.is_active.is_(True),
        User.company_id == current_user.company_id,
    )
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
            "company_name": None,  # always theirs — no cross-tenant labeling
        }
        for u in rows
    ]


@router.get("/ponder/document-preview")
def tenant_ponder_document_preview(
    template_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The document beat's exhibit — the ONE preview path (platform templates
    only; same render the admin ponder shows)."""
    from app.services.maps_of_content import ponder

    try:
        return ponder.render_document_preview(db, template_key)
    except ponder.PonderError as e:
        code = 404 if "not found" in str(e).lower() else 422
        raise HTTPException(status_code=code, detail=str(e))


@router.get("/ponder/{task_id}")
def tenant_get_ponder_script(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The live-derived walkthrough, company-scoped: their params, their
    people, their fires."""
    from app.services.maps_of_content import ponder

    company = _company(db, current_user)
    task = _visible_task(db, task_id, company)
    try:
        script = ponder.build_ponder_script(db, task.id, company_id=company.id)
    except ponder.PonderError as e:
        raise HTTPException(status_code=404, detail=str(e))
    # P3 — the H1 composition: can THIS user follow a failed fire into
    # Decision Triage? Mapped from the queue's own config; the frontend
    # renders the deep link iff true (never a dead link).
    script["can_follow_reviews"] = ponder.user_can_follow_reviews(db, current_user)
    return script


# ─── The edit grammar (tenant admins; owned rows only) ─────────────────────


class _SaveCaption(BaseModel):
    beat_key: str
    text: str | None = None


@router.patch("/ponder/{task_id}/captions")
def tenant_save_ponder_caption(
    task_id: str,
    body: _SaveCaption,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Author (or clear) a caption on THEIR task. A shared task 403s with
    the fork nudge — captions on the default are platform pedagogy."""
    from app.services.maps_of_content import ponder

    company = _company(db, current_user)
    task = _owned_task(db, task_id, company)
    try:
        captions = ponder.save_caption(db, task.id, body.beat_key, body.text)
    except ponder.PonderError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"captions": captions}


# ─── The Map Home campaign — area ponders, onboarding, engagement, rail ────


@router.get("/jobs")
def tenant_list_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The tenant's JOBS (displayed Tasks) — the area pages' leading unit
    (Reframe R-2). Refs resolved; the card glance carries the live rollup +
    the permission-aware queue pending count."""
    from app.services.maps_of_content import jobs as jobs_svc

    company = _company(db, current_user)
    return {
        "vertical": company.vertical,
        "jobs": [
            jobs_svc.job_card_payload(db, j, user=current_user)
            for j in jobs_svc.list_jobs(db, vertical=company.vertical)
        ],
    }


@router.get("/job-ponder/{job_id}")
def tenant_job_ponder(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """THE JOB PONDER — the whole job's story (framing → automations →
    the human-work surfaces → the area). Queue counts are THIS user's
    permission-aware truth. View for everyone; the framing is platform
    pedagogy (authored platform-side)."""
    from app.services.maps_of_content import jobs as jobs_svc

    company = _company(db, current_user)
    try:
        return jobs_svc.build_job_ponder_script(
            db, job_id=job_id, company_id=company.id, user=current_user,
        )
    except jobs_svc.JobValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/area-ponder/{area}")
def tenant_area_ponder(
    area: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The AREA OVERVIEW PONDER — philosophy (platform pedagogy, VIEW only
    tenant-side) → one short beat per task (live-derived from THEIR merged
    view) → the closing deep link. Everyone views; nobody authors here."""
    from app.services.maps_of_content import area_ponder

    company = _company(db, current_user)
    try:
        return area_ponder.build_area_ponder_script(
            db, vertical=company.vertical, area=area, company_id=company.id,
        )
    except area_ponder.AreaPonderError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/onboarding/{key}")
def tenant_onboarding_ponder(
    key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """An onboarding composition, rendered through the same overlay."""
    from app.services.maps_of_content import area_ponder

    _company(db, current_user)
    try:
        return area_ponder.build_onboarding_script(db, key=key)
    except area_ponder.AreaPonderError as e:
        raise HTTPException(status_code=404, detail=str(e))


class _Engagement(BaseModel):
    ponder_key: str
    event: str  # viewed | completed | dismissed


@router.post("/engagement", status_code=201)
def tenant_record_engagement(
    body: _Engagement,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """THE QUIET WRITE — one upsert, timestamps set once, nothing else."""
    from app.services.maps_of_content import engagement

    company = _company(db, current_user)
    try:
        engagement.record(
            db, user_id=current_user.id, company_id=company.id,
            ponder_key=body.ponder_key, event=body.event,
        )
    except engagement.EngagementError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.get("/suggestions")
def tenant_suggestions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The rail — rule-based v1, each card carrying its honest why.
    Empty-honest when no rule genuinely fires."""
    from app.models.role import Role
    from app.services.maps_of_content import engagement

    company = _company(db, current_user)
    role = db.query(Role).filter(Role.id == current_user.role_id).first()
    role_slug = role.slug if role else None
    return engagement.build_suggestions(
        db, user_id=current_user.id, company_id=company.id,
        vertical=company.vertical, role_slug=role_slug,
        is_admin=bool(role and role.is_system and role.slug == "admin"),
    )


@router.get("/vocabulary")
def tenant_list_vocabulary(
    kind: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The vocabulary visible to THIS tenant's vertical (platform values +
    the vertical's) — the add dialog's type/frequency options. Read-only."""
    from app.services.maps_of_content import vocabulary

    company = _company(db, current_user)
    try:
        values = vocabulary.list_values(db, kind=kind, vertical=company.vertical)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return [
        {"id": v.id, "kind": v.kind, "value": v.value, "vertical": v.vertical}
        for v in values
    ]


class _CreateTask(BaseModel):
    name: str
    description: str | None = None
    task_type: str | None = None
    frequency: str | None = None
    icon: str | None = None


@router.post("/tasks", status_code=201)
def tenant_create_task(
    body: _CreateTask,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """TENANT ADD (The Sunnycrest Workshop) — a tenant admin authors a NEW
    task on THEIR map. THE COHERENCE GUARD, server-side and absolute: the
    scope is FORCED to tenant_override + THIS company — no client field can
    land a tenant add on the vertical/core tiers (pinned). Born bare
    (no workflow ref — the ponder honestly refuses until one is attached
    admin-side); triggers/captions/editors work from the start."""
    from app.services.maps_of_content import task_catalog as task_svc

    company = _company(db, current_user)
    try:
        task = task_svc.create_task(
            db,
            vertical=company.vertical,
            name=body.name,
            scope="tenant_override",          # forced — never client-chosen
            tenant_id=company.id,             # forced — always THEIR row
            description=body.description,
            task_type=body.task_type,
            frequency=body.frequency,
            icon=body.icon,
            actor_id=current_user.id,
        )
        db.commit()
    except task_svc.TaskValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return resolve_task(db, task)


@router.post("/tasks/{task_id}/fork", status_code=201)
def tenant_fork_task(
    task_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """THE PROMPTED FORK — make the shared task theirs: a tenant task row
    (fields + captions + focuses copied; triggers copied BORN UNPROMOTED)
    + the enrollment. The workflow stays shared; the vertical default is
    untouched for every other tenant. Idempotent."""
    company = _company(db, current_user)
    try:
        fork = fork_task_for_tenant(
            db, task_id=task_id, company_id=company.id,
            company_vertical=company.vertical, actor_id=current_user.id,
        )
        db.commit()
    except TaskForkError as e:
        db.rollback()
        code = 404 if "not found" in str(e) else 400
        raise HTTPException(status_code=code, detail=str(e))
    return resolve_task(db, fork)


# ─── Offer-reach (P3) — the standard's improvements reach their version ─────


@router.get("/offers/{offer_id}")
def tenant_get_offer(
    offer_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """One offer, THEIRS only (target_tenant_id — not-found semantics).
    Viewing is for everyone (the badge is on their map); deciding is admin."""
    from app.services.maps_of_content import task_offers

    company = _company(db, current_user)
    try:
        return task_offers.get_offer(db, offer_id=offer_id, company_id=company.id)
    except task_offers.TaskOfferError as e:
        raise HTTPException(status_code=404, detail=str(e))


class _AcceptOffer(BaseModel):
    # {field: "keep"} keeps their value; unspecified diff fields apply.
    choices: dict[str, str] = {}


@router.post("/offers/{offer_id}/accept")
def tenant_accept_offer(
    offer_id: str,
    body: _AcceptOffer,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from app.services.maps_of_content import task_offers

    company = _company(db, current_user)
    try:
        return task_offers.accept_offer(
            db, offer_id=offer_id, company_id=company.id,
            choices=body.choices, actor_id=current_user.id,
        )
    except task_offers.TaskOfferError as e:
        db.rollback()
        code = 404 if "not found" in str(e) else 409
        detail = {"message": str(e)}
        if e.latest_offer_id:
            detail["latest_offer_id"] = e.latest_offer_id
        raise HTTPException(status_code=code, detail=detail)


@router.post("/offers/{offer_id}/decline")
def tenant_decline_offer(
    offer_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from app.services.maps_of_content import task_offers

    company = _company(db, current_user)
    try:
        return task_offers.decline_offer(
            db, offer_id=offer_id, company_id=company.id, actor_id=current_user.id,
        )
    except task_offers.TaskOfferError as e:
        db.rollback()
        code = 404 if "not found" in str(e) else 409
        raise HTTPException(status_code=code, detail=str(e))


class _AddTrigger(BaseModel):
    kind: Literal["schedule", "event", "manual"]
    config: dict[str, Any] = {}
    label: str | None = None
    display_order: int = 0


class _PatchTrigger(BaseModel):
    # Deliberately NO is_live field — tenant live-promotion is not in P2.
    # Promotion stays platform-side; forked triggers are born unpromoted.
    kind: Literal["schedule", "event", "manual"] | None = None
    config: dict[str, Any] | None = None
    label: str | None = None
    display_order: int | None = None
    is_active: bool | None = None


def _trigger_payload(trig) -> dict:
    return {
        "id": trig.id, "task_catalog_id": trig.task_catalog_id, "kind": trig.kind,
        "config": trig.config, "label": trig.label,
        "display_order": trig.display_order, "is_active": trig.is_active,
        "is_live": trig.is_live,
        "summary": triggers_svc.summarize_trigger(trig.kind, trig.config),
    }


@router.get("/trigger-events")
def tenant_list_trigger_events(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The event catalog for the composer's picker — their vertical's view."""
    company = _company(db, current_user)
    rows = trigger_events_svc.list_events(db, vertical=company.vertical)
    return [
        {"id": r.id, "event_key": r.event_key, "label": r.label,
         "entity": r.entity, "filterable_fields": r.filterable_fields or []}
        for r in rows
    ]


@router.post("/tasks/{task_id}/triggers", status_code=201)
def tenant_add_trigger(
    task_id: str,
    body: _AddTrigger,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    company = _company(db, current_user)
    task = _owned_task(db, task_id, company)
    try:
        trig = triggers_svc.add_trigger(
            db, task_catalog_id=task.id, kind=body.kind, config=body.config,
            label=body.label, display_order=body.display_order,
            actor_id=current_user.id,
        )
        db.commit()
    except triggers_svc.TriggerValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return _trigger_payload(trig)


def _owned_trigger(db: Session, trigger_id: str, company: Company):
    from app.models.moc_task_trigger import MoCTaskTrigger

    trig = db.get(MoCTaskTrigger, trigger_id)
    if trig is None:
        raise HTTPException(status_code=404, detail="Trigger not found")
    task = db.get(MoCTaskCatalog, trig.task_catalog_id)
    if (
        task is None
        or task.scope != "tenant_override"
        or task.tenant_id != company.id
    ):
        # Not theirs → not found (ownership semantics — never a hint).
        raise HTTPException(status_code=404, detail="Trigger not found")
    return trig


@router.patch("/triggers/{trigger_id}")
def tenant_patch_trigger(
    trigger_id: str,
    body: _PatchTrigger,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    company = _company(db, current_user)
    _owned_trigger(db, trigger_id, company)
    kwargs = {k: getattr(body, k) for k in body.model_fields_set}
    try:
        trig = triggers_svc.patch_trigger(
            db, trigger_id=trigger_id, actor_id=current_user.id, **kwargs
        )
        db.commit()
    except triggers_svc.TriggerValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return _trigger_payload(trig)


@router.delete("/triggers/{trigger_id}", status_code=200)
def tenant_delete_trigger(
    trigger_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    company = _company(db, current_user)
    _owned_trigger(db, trigger_id, company)
    triggers_svc.delete_trigger(db, trigger_id=trigger_id)
    db.commit()
    return {"deleted": True, "id": trigger_id}
