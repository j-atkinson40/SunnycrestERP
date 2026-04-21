"""Workflow Arc Phase 8a — hard-fork mechanism.

Option A — Independent Copies. When a tenant clicks "Fork to customize"
on a core or vertical workflow, this service copies the source workflow
+ its steps + its platform-default step params into a new tenant-owned
workflow. Platform updates to the source do NOT propagate to the fork.

Coexists with the Option B soft-customization path:
  - WorkflowEnrollment (per-tenant opt-in to platform workflows)
  - WorkflowStepParam with company_id set (tenant overrides)

The two paths are deliberate. Documented in CLAUDE.md § Workflows.
  - Soft path: "I want to tweak a parameter but stay on the base."
  - Hard path: "I want to own this workflow outright and diverge."

Future (Phase 8h+):
  - Notification when a source workflow changes and the fork hasn't
    absorbed it ("base updated — review differences"). The
    `forked_from_workflow_id` + `forked_at` columns on the fork
    row supply the hook.
  - UI-level diff view + selective absorb ("copy these N step
    changes into my fork"). Out of scope for 8a.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.workflow import (
    Workflow,
    WorkflowStep,
    WorkflowStepParam,
)

logger = logging.getLogger(__name__)


class WorkflowForkError(Exception):
    http_status: int = 400


class ForkNotAllowed(WorkflowForkError):
    http_status = 403


class SourceNotFound(WorkflowForkError):
    http_status = 404


class AlreadyForked(WorkflowForkError):
    """Tenant already has an active fork of this source. Deleting
    the previous fork is the cleanup path; we don't silently
    double-fork because that confuses tenants and inflates the
    row count."""

    http_status = 409


def fork_workflow_to_tenant(
    db: Session,
    *,
    user: User,
    source_workflow_id: str,
    new_name: str | None = None,
) -> Workflow:
    """Copy `source_workflow_id` into a tenant-owned workflow.

    Rules:
      - Source must exist and have `scope` in ("core", "vertical").
      - Source's vertical must match caller's tenant vertical, or
        source must be scope="core" (applies to any vertical).
      - A tenant can only have ONE active fork per source. Raise
        AlreadyForked otherwise.

    Output: new Workflow row with
      - scope="tenant"
      - company_id=caller's tenant
      - forked_from_workflow_id=source.id
      - forked_at=now
      - All WorkflowSteps copied with fresh IDs
      - All platform-default WorkflowStepParams copied into the
        new workflow (company_id still null so they act as the
        fork's base defaults)
    """
    source = (
        db.query(Workflow)
        .filter(Workflow.id == source_workflow_id)
        .first()
    )
    if source is None:
        raise SourceNotFound(f"Workflow {source_workflow_id!r} not found")
    if source.scope not in ("core", "vertical"):
        raise ForkNotAllowed(
            f"Cannot fork a {source.scope!r} workflow — only core and "
            f"vertical workflows are forkable."
        )
    if source.scope == "vertical" and source.vertical:
        from app.models.company import Company

        company = (
            db.query(Company).filter(Company.id == user.company_id).first()
        )
        if company is None or company.vertical != source.vertical:
            raise ForkNotAllowed(
                f"Cannot fork a {source.vertical!r}-vertical workflow "
                f"from a tenant whose vertical is "
                f"{getattr(company, 'vertical', None)!r}."
            )

    # One active fork per source per tenant — avoids silent duplication.
    existing = (
        db.query(Workflow)
        .filter(
            Workflow.forked_from_workflow_id == source.id,
            Workflow.company_id == user.company_id,
            Workflow.is_active.is_(True),
        )
        .first()
    )
    if existing is not None:
        raise AlreadyForked(
            f"Tenant already has an active fork of workflow "
            f"{source.id!r} (fork id={existing.id!r}). Delete the "
            f"existing fork first if you want to re-fork."
        )

    # Create the fork row.
    new_id = str(uuid.uuid4())
    fork = Workflow(
        id=new_id,
        company_id=user.company_id,
        name=new_name or f"{source.name} (copy)",
        description=source.description,
        keywords=list(source.keywords or []),
        tier=4,  # tenant custom per the existing tier convention
        scope="tenant",
        vertical=source.vertical,
        trigger_type=source.trigger_type,
        trigger_config=dict(source.trigger_config or {}),
        is_active=True,
        is_system=False,
        icon=source.icon,
        command_bar_priority=source.command_bar_priority,
        created_by_user_id=user.id,
        is_coming_soon=False,
        overlay_config=(
            dict(source.overlay_config) if source.overlay_config else None
        ),
        forked_from_workflow_id=source.id,
        forked_at=datetime.now(timezone.utc),
        # agent_registry_key stays NULL — a fork runs through
        # workflow_engine; the tenant is diverging from the
        # platform's built-in agent implementation.
        agent_registry_key=None,
    )
    db.add(fork)
    db.flush()

    # Copy steps with fresh IDs. Preserve step_key so
    # WorkflowStepParam lookups still work by step_key.
    # condition_true_step_id / condition_false_step_id / next_step_id
    # are internal references — remap them via an old→new id map so
    # the fork's DAG edges land on the fork's own step rows.
    source_steps = (
        db.query(WorkflowStep)
        .filter(WorkflowStep.workflow_id == source.id)
        .order_by(WorkflowStep.step_order.asc())
        .all()
    )
    id_map: dict[str, str] = {}
    for s in source_steps:
        new_step_id = str(uuid.uuid4())
        id_map[s.id] = new_step_id
        db.add(
            WorkflowStep(
                id=new_step_id,
                workflow_id=fork.id,
                step_order=s.step_order,
                step_key=s.step_key,
                step_type=s.step_type,
                config=dict(s.config or {}),
                is_core=s.is_core,
                display_name=s.display_name,
                # Temporarily null; remapped in second pass once
                # every new id is allocated.
                next_step_id=None,
                condition_true_step_id=None,
                condition_false_step_id=None,
            )
        )
    db.flush()
    # Second pass: remap DAG edges.
    for s in source_steps:
        new_step = db.query(WorkflowStep).filter(
            WorkflowStep.id == id_map[s.id]
        ).first()
        if new_step is None:
            continue
        if s.next_step_id and s.next_step_id in id_map:
            new_step.next_step_id = id_map[s.next_step_id]
        if s.condition_true_step_id and s.condition_true_step_id in id_map:
            new_step.condition_true_step_id = id_map[s.condition_true_step_id]
        if s.condition_false_step_id and s.condition_false_step_id in id_map:
            new_step.condition_false_step_id = id_map[s.condition_false_step_id]

    # Copy platform-default step params (company_id IS NULL) into
    # the fork so tenant admins can edit them in-place. Tenant
    # overrides on the SOURCE workflow (if any via the soft-path)
    # are NOT copied — the fork starts from the platform defaults
    # so the tenant can pick their own direction.
    source_params = (
        db.query(WorkflowStepParam)
        .filter(
            WorkflowStepParam.workflow_id == source.id,
            WorkflowStepParam.company_id.is_(None),
        )
        .all()
    )
    for p in source_params:
        db.add(
            WorkflowStepParam(
                id=str(uuid.uuid4()),
                workflow_id=fork.id,
                company_id=None,  # base defaults on the fork
                step_key=p.step_key,
                param_key=p.param_key,
                label=p.label,
                description=p.description,
                param_type=p.param_type,
                default_value=p.default_value,
                current_value=p.default_value,
                is_configurable=p.is_configurable,
                validation=dict(p.validation) if p.validation else None,
            )
        )

    db.commit()
    db.refresh(fork)
    logger.info(
        "Workflow forked: source=%s tenant=%s fork_id=%s name=%s",
        source.id, user.company_id, fork.id, fork.name,
    )
    return fork


def count_tenants_using_workflow(
    db: Session, *, workflow_id: str
) -> int:
    """Count distinct tenants that are actively enrolled in this
    workflow (soft-customization path). Tenants who have forked the
    workflow are NOT counted — a fork is a separate workflow row with
    its own enrollments.

    Used by the "Used by" column in the three-tab builder UI so
    platform admins can see adoption of core / vertical workflows
    without counting tenants that diverged via fork.
    """
    from app.models.workflow import WorkflowEnrollment
    from sqlalchemy import func

    return int(
        db.query(func.count(func.distinct(WorkflowEnrollment.company_id)))
        .filter(
            WorkflowEnrollment.workflow_id == workflow_id,
            WorkflowEnrollment.is_active.is_(True),
        )
        .scalar()
        or 0
    )


__all__ = [
    "WorkflowForkError",
    "ForkNotAllowed",
    "SourceNotFound",
    "AlreadyForked",
    "fork_workflow_to_tenant",
    "count_tenants_using_workflow",
]
