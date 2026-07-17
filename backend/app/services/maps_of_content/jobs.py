"""JOBS (displayed **Task**) — the entity service + the polymorphic
reference spine (Reframe R-1).

WRITE-BOUNDARY HONESTY (the named-people precedent): a ref is
existence-checked per kind AT WRITE — a stored ref can never rot silently
to nothing from day one. READ-SIDE: resolution SKIPS dead refs (plainer,
never stale — a ref whose target has since died renders nothing to
viewers) while `dead_refs` rides the payload so EDIT surfaces show them
reclaimable (the orphaned-caption grammar, at the ref tier).

REF_CHECKERS / REF_RESOLVERS — the house dispatch-dict pattern (BUILDERS /
_DIRECT_QUERIES / PEEK_BUILDERS precedents). Adding a ref kind = one
checker + one resolver + the CHECK constraint; capability/document kinds
slot in by exactly that shape.
"""
from __future__ import annotations

import uuid
from typing import Any, Callable, Sequence

from sqlalchemy.orm import Session

from app.models.moc_job import MoCJob, MoCJobRef

REF_KINDS = ("automation", "triage_queue", "focus")


class JobValidationError(ValueError):
    """A rejected job/ref write — HTTP 400 (404 on not-found)."""


# ── Existence checkers (the WRITE boundary) ─────────────────────────────


def _check_automation(db: Session, key: str) -> bool:
    from app.models.moc_task_catalog import MoCTaskCatalog

    row = db.get(MoCTaskCatalog, key)
    return row is not None and row.is_active


def _check_triage_queue(db: Session, key: str) -> bool:
    from app.services.triage.registry import platform_queue_ids

    return key in platform_queue_ids()


def _check_focus(db: Session, key: str) -> bool:
    from app.models.focus_template import FocusTemplate

    return (
        db.query(FocusTemplate)
        .filter(FocusTemplate.template_slug == key)
        .first()
        is not None
    )


REF_CHECKERS: dict[str, Callable[[Session, str], bool]] = {
    "automation": _check_automation,
    "triage_queue": _check_triage_queue,
    "focus": _check_focus,
}


# ── Resolvers (the READ side — skip-dead, never stale) ──────────────────


def _resolve_automation(db: Session, key: str) -> dict[str, Any] | None:
    from app.models.moc_task_catalog import MoCTaskCatalog
    from app.services.maps_of_content.task_catalog import resolve_task

    row = db.get(MoCTaskCatalog, key)
    if row is None or not row.is_active:
        return None
    resolved = resolve_task(db, row)
    return {
        "kind": "automation",
        "key": key,
        "label": row.name,
        "automation": resolved,
    }


def _resolve_triage_queue(db: Session, key: str) -> dict[str, Any] | None:
    from app.services.triage.registry import platform_queue_config

    cfg = platform_queue_config(key)
    if cfg is None:
        return None
    return {
        "kind": "triage_queue",
        "key": key,
        "label": cfg.queue_name,
        "icon": getattr(cfg, "icon", None),
        "href": f"/triage/{key}",
    }


def _resolve_focus(db: Session, key: str) -> dict[str, Any] | None:
    from app.models.focus_template import FocusTemplate

    tpl = (
        db.query(FocusTemplate)
        .filter(FocusTemplate.template_slug == key)
        .order_by(FocusTemplate.version.desc())
        .first()
    )
    if tpl is None:
        return None
    return {
        "kind": "focus",
        "key": key,
        "label": tpl.display_name,
        "vertical": tpl.vertical,
    }


REF_RESOLVERS: dict[str, Callable[[Session, str], dict[str, Any] | None]] = {
    "automation": _resolve_automation,
    "triage_queue": _resolve_triage_queue,
    "focus": _resolve_focus,
}


# ── CRUD (caller commits, the house pattern) ────────────────────────────


def create_job(
    db: Session,
    *,
    name: str,
    scope: str = "vertical_default",
    vertical: str | None = None,
    icon: str | None = None,
    description: str | None = None,
    task_type: str | None = None,
    display_order: int = 0,
) -> MoCJob:
    if scope == "platform_default":
        if vertical is not None:
            raise JobValidationError("a platform_default job is vertical-less")
    elif scope == "vertical_default":
        if vertical is None:
            raise JobValidationError("a vertical_default job requires its vertical")
    else:
        raise JobValidationError(f"scope {scope!r} is not a job tier (option A)")
    dup = (
        db.query(MoCJob)
        .filter(
            MoCJob.scope == scope, MoCJob.vertical == vertical,
            MoCJob.name == name, MoCJob.is_active.is_(True),
        )
        .first()
    )
    if dup is not None:
        raise JobValidationError(f"a job named {name!r} already exists in this scope")
    job = MoCJob(
        id=str(uuid.uuid4()), scope=scope, vertical=vertical, name=name,
        icon=icon, description=description, task_type=task_type,
        display_order=display_order,
    )
    db.add(job)
    db.flush()
    return job


def add_ref(
    db: Session, *, job_id: str, ref_kind: str, ref_key: str,
    label: str | None = None, display_order: int = 0,
) -> MoCJobRef:
    """THE WRITE BOUNDARY — the ref must exist NOW, per kind. A dangling
    write is refused loudly; decay after the fact is the read side's
    skip-and-reclaim problem."""
    job = db.get(MoCJob, job_id)
    if job is None or not job.is_active:
        raise JobValidationError("job not found")
    if ref_kind not in REF_KINDS:
        raise JobValidationError(f"ref_kind must be one of {REF_KINDS}")
    if not REF_CHECKERS[ref_kind](db, ref_key):
        raise JobValidationError(
            f"{ref_kind} {ref_key!r} does not resolve — refusing to store a "
            "dead reference"
        )
    ref = MoCJobRef(
        id=str(uuid.uuid4()), job_id=job_id, ref_kind=ref_kind,
        ref_key=ref_key, label=label, display_order=display_order,
    )
    db.add(ref)
    db.flush()
    return ref


def remove_ref(db: Session, *, ref_id: str) -> bool:
    ref = db.get(MoCJobRef, ref_id)
    if ref is None:
        return False
    db.delete(ref)
    db.flush()
    return True


def list_jobs(
    db: Session, *, vertical: str | None, include_platform: bool = True
) -> list[MoCJob]:
    q = db.query(MoCJob).filter(MoCJob.is_active.is_(True))
    if include_platform:
        q = q.filter(
            (
                (MoCJob.scope == "vertical_default") & (MoCJob.vertical == vertical)
            )
            | (MoCJob.scope == "platform_default")
        )
    else:
        q = q.filter(MoCJob.scope == "vertical_default", MoCJob.vertical == vertical)
    return q.order_by(MoCJob.display_order, MoCJob.name).all()


def resolve_job(db: Session, job: MoCJob) -> dict[str, Any]:
    """The job + its refs resolved per kind. DEAD REFS SKIP the resolved
    list (viewers see the plainer truth) and surface in `dead_refs`
    (the edit surface's reclaim list — id + kind + key, enough to remove
    or repoint)."""
    resolved: list[dict[str, Any]] = []
    dead: list[dict[str, Any]] = []
    for ref in job.refs:
        payload = REF_RESOLVERS[ref.ref_kind](db, ref.ref_key)
        if payload is None:
            dead.append({"id": ref.id, "kind": ref.ref_kind, "key": ref.ref_key})
            continue
        if ref.label:
            payload["label"] = ref.label  # authored label wins
        payload["ref_id"] = ref.id
        resolved.append(payload)
    return {
        "id": job.id,
        "scope": job.scope,
        "vertical": job.vertical,
        "name": job.name,
        "icon": job.icon,
        "description": job.description,
        "task_type": job.task_type,
        "display_order": job.display_order,
        "refs": resolved,
        "dead_refs": dead,
    }
