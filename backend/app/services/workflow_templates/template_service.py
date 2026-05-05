"""Workflow template service — CRUD + inheritance resolution +
tenant fork lifecycle.

Pattern parallels Phase 2 platform_themes + Phase 3 component
configurations: READ-time resolution, write-side versioning,
partial-unique active rows + accumulated audit trail of inactive
rows.

Key architectural difference from themes/component-config:
**tenant_workflow_forks REPLACE the inheritance chain** rather
than overlaying. Workflow canvas_state is a graph; merging two
graphs at read time has no canonical answer (which nodes win?
how do conflicting edges resolve?). Instead, the tenant
explicitly accepts upstream changes via the merge lifecycle —
their fork's canvas_state is authoritative until they accept.
This is the "locked-to-fork" semantic.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping
from sqlalchemy.orm import Session

from app.models.workflow_template import (
    SCOPE_PLATFORM_DEFAULT,
    SCOPE_VERTICAL_DEFAULT,
    TenantWorkflowFork,
    WorkflowTemplate,
)
from app.services.workflow_templates.canvas_validator import (
    validate_canvas_state,
)


logger = logging.getLogger(__name__)


_VALID_SCOPES: tuple[str, ...] = (SCOPE_PLATFORM_DEFAULT, SCOPE_VERTICAL_DEFAULT)


# ─── Exceptions ──────────────────────────────────────────────────


class WorkflowTemplateError(Exception):
    """Base for the workflow template service."""


class TemplateNotFound(WorkflowTemplateError):
    pass


class TemplateScopeMismatch(WorkflowTemplateError):
    pass


class InvalidTemplateShape(WorkflowTemplateError):
    pass


class ForkNotFound(WorkflowTemplateError):
    pass


# ─── Validation helpers ──────────────────────────────────────────


def _validate_scope_keys(scope: str, vertical: str | None) -> None:
    if scope not in _VALID_SCOPES:
        raise InvalidTemplateShape(f"scope must be one of {_VALID_SCOPES}")
    if scope == SCOPE_PLATFORM_DEFAULT and vertical is not None:
        raise TemplateScopeMismatch(
            "platform_default rows must have vertical=None"
        )
    if scope == SCOPE_VERTICAL_DEFAULT and vertical is None:
        raise TemplateScopeMismatch(
            "vertical_default rows must have vertical set"
        )


def _validate_workflow_type(workflow_type: str) -> None:
    if not isinstance(workflow_type, str) or not workflow_type:
        raise InvalidTemplateShape(
            "workflow_type must be a non-empty string"
        )
    if len(workflow_type) > 96:
        raise InvalidTemplateShape(
            f"workflow_type exceeds 96 chars: {len(workflow_type)}"
        )


# ─── Template CRUD ───────────────────────────────────────────────


def list_templates(
    db: Session,
    *,
    scope: str | None = None,
    vertical: str | None = None,
    workflow_type: str | None = None,
    include_inactive: bool = False,
    metadata_only: bool = False,
) -> list[WorkflowTemplate]:
    """Return matching templates. `metadata_only=True` doesn't
    affect what SQLAlchemy fetches (still returns full rows) but
    callers can ignore canvas_state when serializing for the list
    response — large canvas payloads don't need to round-trip
    over the API for list views."""
    q = db.query(WorkflowTemplate)
    if scope is not None:
        if scope not in _VALID_SCOPES:
            raise InvalidTemplateShape(f"scope filter invalid: {scope!r}")
        q = q.filter(WorkflowTemplate.scope == scope)
    if vertical is not None:
        q = q.filter(WorkflowTemplate.vertical == vertical)
    if workflow_type is not None:
        q = q.filter(WorkflowTemplate.workflow_type == workflow_type)
    if not include_inactive:
        q = q.filter(WorkflowTemplate.is_active.is_(True))
    return q.order_by(WorkflowTemplate.created_at.desc()).all()


def get_template(db: Session, template_id: str) -> WorkflowTemplate:
    row = (
        db.query(WorkflowTemplate)
        .filter(WorkflowTemplate.id == template_id)
        .first()
    )
    if not row:
        raise TemplateNotFound(template_id)
    return row


def _find_active_template(
    db: Session,
    *,
    scope: str,
    vertical: str | None,
    workflow_type: str,
) -> WorkflowTemplate | None:
    q = db.query(WorkflowTemplate).filter(
        WorkflowTemplate.scope == scope,
        WorkflowTemplate.workflow_type == workflow_type,
        WorkflowTemplate.is_active.is_(True),
    )
    if vertical is None:
        q = q.filter(WorkflowTemplate.vertical.is_(None))
    else:
        q = q.filter(WorkflowTemplate.vertical == vertical)
    return q.first()


def create_template(
    db: Session,
    *,
    scope: str,
    vertical: str | None = None,
    workflow_type: str,
    display_name: str,
    description: str | None = None,
    canvas_state: Mapping[str, Any] | None = None,
    actor_user_id: str | None = None,
    notify_forks: bool = True,
) -> WorkflowTemplate:
    """Create a new active template. If an active row already
    exists at the same (scope, vertical, workflow_type) tuple,
    it's deactivated first; the new row's version is
    `prior.version + 1`. When `notify_forks` is true, dependent
    tenant forks (basing on the prior version of a vertical_default
    template) are flagged with `pending_merge_available=true`.
    """
    _validate_scope_keys(scope, vertical)
    _validate_workflow_type(workflow_type)
    if not isinstance(display_name, str) or not display_name:
        raise InvalidTemplateShape("display_name must be a non-empty string")

    state = dict(canvas_state or {})
    validate_canvas_state(state)

    existing = _find_active_template(
        db,
        scope=scope,
        vertical=vertical,
        workflow_type=workflow_type,
    )
    next_version = 1
    if existing is not None:
        existing.is_active = False
        next_version = existing.version + 1

    row = WorkflowTemplate(
        scope=scope,
        vertical=vertical,
        workflow_type=workflow_type,
        display_name=display_name,
        description=description,
        canvas_state=state,
        version=next_version,
        is_active=True,
        created_by=actor_user_id,
        updated_by=actor_user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    # Notify dependent forks IF this is a vertical_default update
    # (forks are only created for vertical defaults; platform
    # defaults can't be forked directly).
    if notify_forks and scope == SCOPE_VERTICAL_DEFAULT and existing is not None:
        mark_pending_merge(
            db,
            workflow_type=workflow_type,
            vertical=vertical or "",
            new_template_id=row.id,
        )

    return row


def update_template(
    db: Session,
    template_id: str,
    *,
    display_name: str | None = None,
    description: str | None = None,
    canvas_state: Mapping[str, Any] | None = None,
    actor_user_id: str | None = None,
    notify_forks: bool = True,
) -> WorkflowTemplate:
    """Replace the active row's editable fields, deactivate the
    prior row, insert a new active row with `version + 1`. Triggers
    `mark_pending_merge` when this is a vertical_default update."""
    prior = get_template(db, template_id)
    if not prior.is_active:
        raise WorkflowTemplateError(
            f"cannot update inactive template {template_id!r}"
        )

    new_canvas = (
        dict(canvas_state) if canvas_state is not None else dict(prior.canvas_state or {})
    )
    validate_canvas_state(new_canvas)

    new_display_name = display_name if display_name is not None else prior.display_name
    new_description = description if description is not None else prior.description

    prior.is_active = False
    new_row = WorkflowTemplate(
        scope=prior.scope,
        vertical=prior.vertical,
        workflow_type=prior.workflow_type,
        display_name=new_display_name,
        description=new_description,
        canvas_state=new_canvas,
        version=prior.version + 1,
        is_active=True,
        created_by=actor_user_id,
        updated_by=actor_user_id,
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)

    if notify_forks and new_row.scope == SCOPE_VERTICAL_DEFAULT:
        mark_pending_merge(
            db,
            workflow_type=new_row.workflow_type,
            vertical=new_row.vertical or "",
            new_template_id=new_row.id,
        )

    return new_row


def get_dependent_forks(
    db: Session, template_id: str
) -> list[TenantWorkflowFork]:
    """Find every active tenant fork based on this template's
    workflow_type + vertical (any version, not just the current).
    Used by the admin UI's 'N tenant forks based on this template'
    indicator before save-and-notify."""
    template = get_template(db, template_id)
    if template.scope != SCOPE_VERTICAL_DEFAULT:
        return []
    # Every fork whose forked_from_template_id matches THIS or any
    # other version of the same (vertical, workflow_type) tuple.
    # Walk: list ALL versions of the template chain (active +
    # inactive); collect ids; filter forks.
    template_ids = [
        t.id
        for t in db.query(WorkflowTemplate)
        .filter(
            WorkflowTemplate.scope == SCOPE_VERTICAL_DEFAULT,
            WorkflowTemplate.vertical == template.vertical,
            WorkflowTemplate.workflow_type == template.workflow_type,
        )
        .all()
    ]
    if not template_ids:
        return []
    return (
        db.query(TenantWorkflowFork)
        .filter(
            TenantWorkflowFork.forked_from_template_id.in_(template_ids),
            TenantWorkflowFork.is_active.is_(True),
        )
        .all()
    )


# ─── Fork lifecycle ──────────────────────────────────────────────


def fork_for_tenant(
    db: Session,
    *,
    tenant_id: str,
    workflow_type: str,
    source_template_id: str,
    actor_user_id: str | None = None,
) -> TenantWorkflowFork:
    """Create a tenant_workflow_forks row initialized from the
    source template's canvas_state. If an active fork already
    exists at the (tenant_id, workflow_type) tuple, raise — Phase
    4 doesn't support multi-fork; tenants either have a fork or
    they don't."""
    _validate_workflow_type(workflow_type)
    source = get_template(db, source_template_id)

    existing = (
        db.query(TenantWorkflowFork)
        .filter(
            TenantWorkflowFork.tenant_id == tenant_id,
            TenantWorkflowFork.workflow_type == workflow_type,
            TenantWorkflowFork.is_active.is_(True),
        )
        .first()
    )
    if existing is not None:
        raise WorkflowTemplateError(
            f"tenant {tenant_id} already has an active fork for "
            f"{workflow_type!r}; update or delete the existing fork first"
        )

    row = TenantWorkflowFork(
        tenant_id=tenant_id,
        workflow_type=workflow_type,
        forked_from_template_id=source.id,
        forked_from_version=source.version,
        canvas_state=dict(source.canvas_state or {}),
        pending_merge_available=False,
        pending_merge_template_id=None,
        version=1,
        is_active=True,
        created_by=actor_user_id,
        updated_by=actor_user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_forks(
    db: Session,
    *,
    tenant_id: str | None = None,
    workflow_type: str | None = None,
    include_inactive: bool = False,
) -> list[TenantWorkflowFork]:
    q = db.query(TenantWorkflowFork)
    if tenant_id is not None:
        q = q.filter(TenantWorkflowFork.tenant_id == tenant_id)
    if workflow_type is not None:
        q = q.filter(TenantWorkflowFork.workflow_type == workflow_type)
    if not include_inactive:
        q = q.filter(TenantWorkflowFork.is_active.is_(True))
    return q.order_by(TenantWorkflowFork.created_at.desc()).all()


def get_fork(db: Session, fork_id: str) -> TenantWorkflowFork:
    row = (
        db.query(TenantWorkflowFork)
        .filter(TenantWorkflowFork.id == fork_id)
        .first()
    )
    if not row:
        raise ForkNotFound(fork_id)
    return row


def mark_pending_merge(
    db: Session,
    *,
    workflow_type: str,
    vertical: str,
    new_template_id: str,
) -> int:
    """Flag every active fork based on a prior version of this
    (vertical, workflow_type) template chain as having a pending
    merge available. Returns the count of forks updated.

    Called automatically by `create_template` + `update_template`
    when scope='vertical_default'. Callable directly when an
    admin uses 'Save and notify forks' to be deliberate."""
    new_template = get_template(db, new_template_id)
    if new_template.scope != SCOPE_VERTICAL_DEFAULT:
        return 0

    # Find every prior template version at the same tuple.
    prior_template_ids = [
        t.id
        for t in db.query(WorkflowTemplate)
        .filter(
            WorkflowTemplate.scope == SCOPE_VERTICAL_DEFAULT,
            WorkflowTemplate.vertical == vertical,
            WorkflowTemplate.workflow_type == workflow_type,
            WorkflowTemplate.id != new_template_id,
        )
        .all()
    ]
    if not prior_template_ids:
        return 0

    forks = (
        db.query(TenantWorkflowFork)
        .filter(
            TenantWorkflowFork.forked_from_template_id.in_(prior_template_ids),
            TenantWorkflowFork.workflow_type == workflow_type,
            TenantWorkflowFork.is_active.is_(True),
        )
        .all()
    )
    for fork in forks:
        fork.pending_merge_available = True
        fork.pending_merge_template_id = new_template_id
    if forks:
        db.commit()
    return len(forks)


def get_pending_merges(
    db: Session, *, tenant_id: str
) -> list[TenantWorkflowFork]:
    return (
        db.query(TenantWorkflowFork)
        .filter(
            TenantWorkflowFork.tenant_id == tenant_id,
            TenantWorkflowFork.is_active.is_(True),
            TenantWorkflowFork.pending_merge_available.is_(True),
        )
        .order_by(TenantWorkflowFork.updated_at.desc())
        .all()
    )


def accept_merge(
    db: Session,
    *,
    tenant_id: str,
    workflow_type: str,
    actor_user_id: str | None = None,
) -> TenantWorkflowFork:
    """Tenant accepts the upstream changes: replaces fork's
    canvas_state with the new template's canvas_state, clears the
    pending flags, increments the fork's version. Phase 4 builds
    this method but doesn't ship the tenant Workshop UI for
    invoking it (Phase 5+ surface)."""
    fork = (
        db.query(TenantWorkflowFork)
        .filter(
            TenantWorkflowFork.tenant_id == tenant_id,
            TenantWorkflowFork.workflow_type == workflow_type,
            TenantWorkflowFork.is_active.is_(True),
        )
        .first()
    )
    if fork is None:
        raise ForkNotFound(
            f"no active fork at tenant={tenant_id} workflow_type={workflow_type}"
        )
    if not fork.pending_merge_available or not fork.pending_merge_template_id:
        raise WorkflowTemplateError(
            "fork has no pending merge available"
        )

    new_template = get_template(db, fork.pending_merge_template_id)

    fork.canvas_state = dict(new_template.canvas_state or {})
    fork.forked_from_template_id = new_template.id
    fork.forked_from_version = new_template.version
    fork.pending_merge_available = False
    fork.pending_merge_template_id = None
    fork.version += 1
    fork.updated_by = actor_user_id
    db.commit()
    db.refresh(fork)
    return fork


def reject_merge(
    db: Session,
    *,
    tenant_id: str,
    workflow_type: str,
    actor_user_id: str | None = None,
) -> TenantWorkflowFork:
    """Tenant declines the upstream changes: preserves their fork's
    canvas_state, clears pending flags, and updates
    `forked_from_version` to the rejected template's version so
    future updates are tracked relative to the rejected version
    (acknowledging the change exists + skipping it)."""
    fork = (
        db.query(TenantWorkflowFork)
        .filter(
            TenantWorkflowFork.tenant_id == tenant_id,
            TenantWorkflowFork.workflow_type == workflow_type,
            TenantWorkflowFork.is_active.is_(True),
        )
        .first()
    )
    if fork is None:
        raise ForkNotFound(
            f"no active fork at tenant={tenant_id} workflow_type={workflow_type}"
        )
    if not fork.pending_merge_available or not fork.pending_merge_template_id:
        raise WorkflowTemplateError(
            "fork has no pending merge available"
        )

    rejected_template = get_template(db, fork.pending_merge_template_id)

    # canvas_state preserved verbatim — this is the load-bearing
    # property of "reject" vs "accept".
    fork.forked_from_template_id = rejected_template.id
    fork.forked_from_version = rejected_template.version
    fork.pending_merge_available = False
    fork.pending_merge_template_id = None
    fork.updated_by = actor_user_id
    db.commit()
    db.refresh(fork)
    return fork


# ─── Resolution ──────────────────────────────────────────────────


def resolve_workflow(
    db: Session,
    *,
    workflow_type: str,
    vertical: str | None = None,
    tenant_id: str | None = None,
) -> dict:
    """Return the effective canvas_state for the given context.

    Resolution order (locked-to-fork semantics):
        1. If tenant_id provided AND tenant has an active fork →
           return fork's canvas_state (REPLACES the chain)
        2. Otherwise, return vertical_default if available
        3. Otherwise, return platform_default if available
        4. Otherwise, return empty (no template authored)

    Returns:
        {
          "workflow_type": ...,
          "vertical": ...,
          "tenant_id": ...,
          "source": "tenant_fork" | "vertical_default" | "platform_default" | None,
          "source_id": <row id> or None,
          "source_version": <int> or None,
          "canvas_state": {...},
          "pending_merge_available": <bool>,
        }
    """
    _validate_workflow_type(workflow_type)

    # Tenant fork wins
    if tenant_id is not None:
        fork = (
            db.query(TenantWorkflowFork)
            .filter(
                TenantWorkflowFork.tenant_id == tenant_id,
                TenantWorkflowFork.workflow_type == workflow_type,
                TenantWorkflowFork.is_active.is_(True),
            )
            .first()
        )
        if fork is not None:
            return {
                "workflow_type": workflow_type,
                "vertical": vertical,
                "tenant_id": tenant_id,
                "source": "tenant_fork",
                "source_id": fork.id,
                "source_version": fork.version,
                "canvas_state": dict(fork.canvas_state or {}),
                "pending_merge_available": fork.pending_merge_available,
            }

    # Vertical default
    if vertical is not None:
        vrow = _find_active_template(
            db,
            scope=SCOPE_VERTICAL_DEFAULT,
            vertical=vertical,
            workflow_type=workflow_type,
        )
        if vrow is not None:
            return {
                "workflow_type": workflow_type,
                "vertical": vertical,
                "tenant_id": tenant_id,
                "source": "vertical_default",
                "source_id": vrow.id,
                "source_version": vrow.version,
                "canvas_state": dict(vrow.canvas_state or {}),
                "pending_merge_available": False,
            }

    # Platform default fallback
    prow = _find_active_template(
        db,
        scope=SCOPE_PLATFORM_DEFAULT,
        vertical=None,
        workflow_type=workflow_type,
    )
    if prow is not None:
        return {
            "workflow_type": workflow_type,
            "vertical": vertical,
            "tenant_id": tenant_id,
            "source": "platform_default",
            "source_id": prow.id,
            "source_version": prow.version,
            "canvas_state": dict(prow.canvas_state or {}),
            "pending_merge_available": False,
        }

    return {
        "workflow_type": workflow_type,
        "vertical": vertical,
        "tenant_id": tenant_id,
        "source": None,
        "source_id": None,
        "source_version": None,
        "canvas_state": {},
        "pending_merge_available": False,
    }
