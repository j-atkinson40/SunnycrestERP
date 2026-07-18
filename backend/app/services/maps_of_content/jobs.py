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


# ── THE JOB PONDER (Reframe R-2) — the whole job's story ─────────────────
#
# A feeder on the landed composition-deriver contract (the same overlay,
# the same script shape): AUTHORED FRAMING (derived-honest placeholder
# until the operator's R-3 voice; captions on job.ponder JSONB, the
# caption-editor pattern) → AUTOMATION beats from the refs (essence +
# honest WHEN with T-0 authority truth + a ponder deep-link to the
# automation's full walkthrough) → HUMAN-WORK beats (the QUEUE beat with
# the permission-aware live pending count + the /triage deep link; the
# FOCUS beat via focus_miniature — the exhibit grammar) → closing (the
# area page). Dead refs skip plainer (R-1's read semantics).


def _first_sentence(text: str | None, limit: int = 140) -> str | None:
    if not text:
        return None
    head = text.strip().split(". ")[0].strip().rstrip(".")
    if not head:
        return None
    if len(head) > limit:
        head = head[: limit - 1].rstrip() + "…"
    return head


def build_job_ponder_script(
    db: Session, *, job_id: str, company_id: str | None = None, user=None,
) -> dict[str, Any]:
    """The job's staged walkthrough. `user` (the tenant read) scopes the
    queue counts permission-aware — no access, no count, never a lie."""
    job = db.get(MoCJob, job_id)
    if job is None or not job.is_active:
        raise JobValidationError("job not found")
    resolved = resolve_job(db, job)
    captions: dict = dict((job.ponder or {}).get("captions") or {})

    autos = [r for r in resolved["refs"] if r["kind"] == "automation"]
    queues = [r for r in resolved["refs"] if r["kind"] == "triage_queue"]
    focuses = [r for r in resolved["refs"] if r["kind"] == "focus"]

    beats: list[dict] = []

    def _beat(key: str, kind: str, derived: str, **extra) -> None:
        authored = captions.get(key)
        beats.append({
            "key": key, "kind": kind,
            "text": authored or derived,
            "derived_text": derived,
            "authored": bool(authored),
            **extra,
        })

    # THE FRAMING — the operator's voice in R-3; a derived-honest
    # placeholder meanwhile (the description + the composition summary).
    pieces = []
    if job.description:
        pieces.append(job.description.rstrip("."))
    counts = []
    if autos:
        counts.append(f"{len(autos)} automation{'s' if len(autos) != 1 else ''}")
    if queues:
        counts.append(
            f"{len(queues)} review surface{'s' if len(queues) != 1 else ''}"
        )
    if counts:
        pieces.append(f"{' and '.join(counts)} work this job")
    _beat("opening", "opening", (". ".join(pieces) + ".") if pieces else job.name)

    # THE AUTOMATION BEATS — the means, each deep-linking its full ponder.
    for r in autos:
        a = r["automation"]
        essence = _first_sentence(a.get("description"))
        when = a.get("runtime_schedule_summary") if (
            a.get("schedule_authority") == "runtime_scheduler"
        ) else (a.get("derived_frequency") or a.get("frequency"))
        parts = [a["name"]]
        if essence:
            parts.append(essence)
        if when:
            parts.append(str(when).rstrip("."))
        _beat(
            f"automation:{r['key']}", "task", ". ".join(parts) + ".",
            ponder_ref={
                "overlay_id": r["key"],
                "label": f"Walk {a['name']}",
            },
        )

    # THE QUEUE BEATS — where the exceptions land; the count is the truth
    # of NOW, permission-aware (no access → no number, never a lie).
    for r in queues:
        count = None
        if user is not None:
            from app.services.triage.engine import queue_count

            try:
                count = queue_count(db, user=user, queue_id=r["key"])
            except Exception:
                count = None  # no access / no queue → honest absence
        derived = (
            f"{r['label']} — where the exceptions land for a person to decide."
        )
        if count is not None:
            derived += (
                f" {count} waiting now." if count else " Nothing waiting now."
            )
        _beat(
            f"queue:{r['key']}", "downstream", derived,
            queue_id=r["key"], queue_label=r["label"],
            link={"href": r["href"], "label": f"Open {r['label']}"},
        )

    # THE FOCUS BEATS — the resolved miniature (the exhibit grammar).
    for r in focuses:
        from app.services.maps_of_content.ponder import focus_miniature

        artifact = focus_miniature(
            db, template_slug=r["key"], vertical=r.get("vertical"),
            display_name=r["label"],
        )
        if artifact is None:
            continue  # unresolvable → skip honestly
        _beat(
            f"focus:{r['key']}", "focus",
            f"The work happens in {r['label']} — this job opens it ready to go.",
            artifact=artifact,
        )

    # THE CLOSING — home is the area page.
    area = job.task_type or "General"
    _beat(
        "closing", "closing",
        f"This task lives in {area} — its automations and the rest of the "
        "area are one click away.",
        link={"href": f"/bridgeable-map/{area}", "label": f"Open the {area} page"},
    )

    live_keys = {b["key"] for b in beats}
    orphaned = {k: v for k, v in captions.items() if k not in live_keys}

    return {
        "task_id": f"job:{job.id}",
        "task_name": job.name,
        "workflow_name": "",
        "beats": beats,
        "orphaned_captions": orphaned,
        "mirror_drift": [],
        "is_live": False,
        "vertical": job.vertical,
        "workflow_id": None,
        "fires": None,
        "task_scope": "platform_default",
        "owned": False,
        "schedule_authority": "moc",
    }


def save_job_caption(
    db: Session, *, job_id: str, beat_key: str, text: str | None
) -> dict[str, str]:
    """Author (or clear) a framing caption — platform pedagogy on the job
    row's ponder JSONB (the task-ponder semantics verbatim). Admin only."""
    job = db.get(MoCJob, job_id)
    if job is None:
        raise JobValidationError("job not found")
    block = dict(job.ponder or {})
    captions = dict(block.get("captions") or {})
    if text is None or not text.strip():
        captions.pop(beat_key, None)
    else:
        captions[beat_key] = text.strip()
    block["captions"] = captions
    job.ponder = block  # reassign — JSONB change detection
    db.commit()
    return captions


def job_card_payload(
    db: Session, job: MoCJob, *, user=None
) -> dict[str, Any]:
    """The area page's job CARD shape — resolve_job + the honest composition
    glance: automation count, live rollup, and the queue's live pending
    count where linked (permission-aware via `user`; no access → None,
    rendered as honest absence)."""
    resolved = resolve_job(db, job)
    autos = [r for r in resolved["refs"] if r["kind"] == "automation"]
    live = sum(
        1 for r in autos
        if any(
            t.get("is_live") and t.get("is_active") is not False
            for t in (r["automation"].get("triggers") or [])
        )
    )
    pending = None
    if user is not None:
        from app.services.triage.engine import queue_count

        total = 0
        counted = False
        for r in resolved["refs"]:
            if r["kind"] != "triage_queue":
                continue
            try:
                total += queue_count(db, user=user, queue_id=r["key"])
                counted = True
            except Exception:
                continue  # no access → this queue contributes no number
        pending = total if counted else None
    resolved["glance"] = {
        "automation_count": len(autos),
        "live_count": live,
        "queue_pending": pending,
    }
    return resolved
