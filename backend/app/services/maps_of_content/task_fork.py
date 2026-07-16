"""The prompted fork (Tenant Ponder-Editor P2) — a tenant makes a shared
task THEIRS.

THE CHEAP-FORK FINDING (tenant_ponder_editor_investigation.md): a task fork
is a tenant task row + an enrollment — the WORKFLOW STAYS SHARED. Field-
granular param overlays keep working under it (the P1 explicit-only
semantic), vertical-default workflow improvements keep propagating, and the
tenant owns exactly what the ponder edits: schedule, captions, knobs.

WHAT COPIES: name/icon/frequency/type/description/workflow ref/focuses/
authored captions (the ponder JSONB) — their version starts as an exact
picture of what they were reading.

TRIGGERS COPY UNPROMOTED — is_live=FALSE ALWAYS, regardless of the source
(the born-unpromoted default: liveness never inherits through a fork; a
tenant's version earns its own promotion, platform-side this phase).

PROVENANCE: forked_from_task_id (r128) records the source — powers the
merged-view YIELD (their row replaces the default in THEIR view only) and
the P3 offer-reach handle.

IDEMPOTENT: forking a task you already forked returns YOUR existing row;
forking your own tenant_override row returns it unchanged (you already own
it — no prompt, no copy).
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.moc_task_catalog import MoCTaskCatalog, MoCTaskCatalogFocus
from app.models.moc_task_trigger import MoCTaskTrigger

logger = logging.getLogger(__name__)


class TaskForkError(ValueError):
    """A rejected fork (missing task / wrong scope / wrong vertical) —
    surfaces as HTTP 400/404 at the route layer."""


def fork_task_for_tenant(
    db: Session,
    *,
    task_id: str,
    company_id: str,
    company_vertical: str | None,
    actor_id: str | None = None,
) -> MoCTaskCatalog:
    """Fork a vertical-default task into the tenant's own row. Caller commits."""
    src = db.get(MoCTaskCatalog, task_id)
    if src is None or not src.is_active:
        raise TaskForkError("task not found")

    # Already theirs → no-op (the editors operate on it directly).
    if src.scope == "tenant_override" and src.tenant_id == company_id:
        return src

    # Ownership semantics: anything that isn't THEIR row or a default of
    # THEIR vertical is invisible — not-found, never a hint it exists
    # (another tenant's fork, a platform row, a foreign vertical's default).
    if (
        src.scope != "vertical_default"
        or src.tenant_id is not None
        or (src.vertical or "").lower() != (company_vertical or "").lower()
    ):
        raise TaskForkError("task not found")

    # Idempotent: an existing fork of this source is THE answer.
    existing = (
        db.query(MoCTaskCatalog)
        .filter(
            MoCTaskCatalog.scope == "tenant_override",
            MoCTaskCatalog.tenant_id == company_id,
            MoCTaskCatalog.forked_from_task_id == src.id,
            MoCTaskCatalog.is_active.is_(True),
        )
        .first()
    )
    if existing is not None:
        return existing

    fork = MoCTaskCatalog(
        scope="tenant_override",
        vertical=src.vertical,
        tenant_id=company_id,
        name=src.name,
        icon=src.icon,
        frequency=src.frequency,
        task_type=src.task_type,
        description=src.description,
        workflow_template_id=src.workflow_template_id,
        display_order=src.display_order,
        ponder=dict(src.ponder) if isinstance(src.ponder, dict) else None,
        forked_from_task_id=src.id,
        created_by=actor_id,
        updated_by=actor_id,
    )
    fork.focuses = [
        MoCTaskCatalogFocus(
            focus_template_id=f.focus_template_id, display_order=f.display_order
        )
        for f in src.focuses
    ]
    db.add(fork)
    db.flush()

    for t in src.triggers:
        db.add(MoCTaskTrigger(
            task_catalog_id=fork.id,
            kind=t.kind,
            config=dict(t.config) if isinstance(t.config, dict) else t.config,
            label=t.label,
            display_order=t.display_order,
            is_active=t.is_active,
            # BORN UNPROMOTED — always, regardless of the source's state.
            # Liveness never inherits through a fork.
            is_live=False,
            created_by=actor_id,
            updated_by=actor_id,
        ))

    # The enrollment — the tenant's relationship to the SHARED workflow
    # (the fork does not copy the workflow; overlays + propagation keep
    # working). Resolvable runtime workflow → find-or-create; a task whose
    # template has no runtime source simply has no enrollment to record.
    _ensure_enrollment(db, src.workflow_template_id, company_id)

    db.flush()
    logger.info(
        "MoC task fork: %s (%s) → tenant %s row %s",
        src.name, src.id, company_id, fork.id,
    )
    return fork


def _ensure_enrollment(
    db: Session, workflow_template_id: str | None, company_id: str
) -> None:
    if not workflow_template_id:
        return
    from app.models.workflow import WorkflowEnrollment
    from app.models.workflow_template import WorkflowTemplate

    tmpl = db.get(WorkflowTemplate, workflow_template_id)
    if tmpl is None:
        return
    wf_id = tmpl.mirrored_from_workflow_id or tmpl.compiled_workflow_id
    if not wf_id:
        return
    existing = (
        db.query(WorkflowEnrollment)
        .filter(
            WorkflowEnrollment.workflow_id == wf_id,
            WorkflowEnrollment.company_id == company_id,
        )
        .first()
    )
    if existing is None:
        db.add(WorkflowEnrollment(
            workflow_id=wf_id, company_id=company_id, is_active=True,
        ))
