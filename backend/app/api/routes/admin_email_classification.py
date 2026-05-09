"""Phase R-6.1a — Admin email classification endpoints.

11 endpoints covering Tier 1 rules CRUD, Tier 2 taxonomy CRUD, Tier
3 enrollment toggle, and audit-log + replay surfaces. All endpoints
are tenant-scoped via ``Depends(get_current_user)`` + admin-gated
where the action is consequential. Cross-tenant id lookups return
404 for existence-hiding canon (no information leakage about
existence in other tenants).

Mounted at ``/api/v1/email-classification/*`` from ``app/api/v1.py``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.email_classification import (
    TenantWorkflowEmailCategory,
    TenantWorkflowEmailRule,
    WorkflowEmailClassification,
)
from app.models.email_primitive import EmailMessage
from app.models.user import User
from app.models.workflow import Workflow
from app.services.classification import (
    ClassificationError,
    ClassificationNotFound,
    classify_only,
)


router = APIRouter()


# ── Schemas ─────────────────────────────────────────────────────────


class _RuleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    priority: int
    match_conditions: dict = Field(default_factory=dict)
    fire_action: dict = Field(default_factory=dict)
    is_active: bool = True


class _RuleUpdateRequest(BaseModel):
    name: str | None = None
    priority: int | None = None
    match_conditions: dict | None = None
    fire_action: dict | None = None
    is_active: bool | None = None


class _RuleReorderRequest(BaseModel):
    rule_ids: list[str]


class _CategoryCreateRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)
    description: str | None = None
    parent_id: str | None = None
    mapped_workflow_id: str | None = None
    position: int = 0
    is_active: bool = True


class _CategoryUpdateRequest(BaseModel):
    label: str | None = None
    description: str | None = None
    parent_id: str | None = None
    mapped_workflow_id: str | None = None
    position: int | None = None
    is_active: bool | None = None


class _Tier3EnrollmentRequest(BaseModel):
    enrolled: bool


class _ManualRouteRequest(BaseModel):
    workflow_id: str
    decision_notes: str | None = None


def _rule_to_dict(r: TenantWorkflowEmailRule) -> dict[str, Any]:
    return {
        "id": r.id,
        "tenant_id": r.tenant_id,
        "priority": r.priority,
        "name": r.name,
        "match_conditions": r.match_conditions or {},
        "fire_action": r.fire_action or {},
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _category_to_dict(c: TenantWorkflowEmailCategory) -> dict[str, Any]:
    return {
        "id": c.id,
        "tenant_id": c.tenant_id,
        "parent_id": c.parent_id,
        "label": c.label,
        "description": c.description,
        "mapped_workflow_id": c.mapped_workflow_id,
        "position": c.position,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _classification_to_dict(
    c: WorkflowEmailClassification,
) -> dict[str, Any]:
    return {
        "id": c.id,
        "tenant_id": c.tenant_id,
        "email_message_id": c.email_message_id,
        "tier": c.tier,
        "tier1_rule_id": c.tier1_rule_id,
        "tier2_category_id": c.tier2_category_id,
        "tier2_confidence": c.tier2_confidence,
        "tier3_confidence": c.tier3_confidence,
        "selected_workflow_id": c.selected_workflow_id,
        "is_suppressed": c.is_suppressed,
        "workflow_run_id": c.workflow_run_id,
        "is_replay": c.is_replay,
        "replay_of_classification_id": c.replay_of_classification_id,
        "error_message": c.error_message,
        "latency_ms": c.latency_ms,
        "tier_reasoning": c.tier_reasoning or {},
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ── Tier 1 Rules CRUD ───────────────────────────────────────────────


@router.get("/rules")
def list_rules(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        db.query(TenantWorkflowEmailRule)
        .filter(TenantWorkflowEmailRule.tenant_id == current_user.company_id)
        .order_by(TenantWorkflowEmailRule.priority.asc())
        .all()
    )
    return {"rules": [_rule_to_dict(r) for r in rows]}


@router.post("/rules", status_code=201)
def create_rule(
    body: _RuleCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # Validate fire_action.workflow_id (if set) belongs to tenant or
    # is platform-global + active.
    fa = body.fire_action or {}
    target_wf_id = fa.get("workflow_id")
    if target_wf_id is not None:
        wf = (
            db.query(Workflow)
            .filter(
                Workflow.id == target_wf_id,
                Workflow.is_active.is_(True),
                or_(
                    Workflow.company_id.is_(None),
                    Workflow.company_id == current_user.company_id,
                ),
            )
            .first()
        )
        if wf is None:
            raise HTTPException(
                status_code=400,
                detail="fire_action.workflow_id not available for this tenant",
            )

    rule = TenantWorkflowEmailRule(
        tenant_id=current_user.company_id,
        name=body.name,
        priority=body.priority,
        match_conditions=body.match_conditions,
        fire_action=body.fire_action,
        is_active=body.is_active,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _rule_to_dict(rule)


@router.patch("/rules/{rule_id}")
def update_rule(
    rule_id: str,
    body: _RuleUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rule = (
        db.query(TenantWorkflowEmailRule)
        .filter(
            TenantWorkflowEmailRule.id == rule_id,
            TenantWorkflowEmailRule.tenant_id == current_user.company_id,
        )
        .first()
    )
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    if body.name is not None:
        rule.name = body.name
    if body.priority is not None:
        rule.priority = body.priority
    if body.match_conditions is not None:
        rule.match_conditions = body.match_conditions
    if body.fire_action is not None:
        rule.fire_action = body.fire_action
    if body.is_active is not None:
        rule.is_active = body.is_active
    rule.updated_by_user_id = current_user.id
    db.commit()
    db.refresh(rule)
    return _rule_to_dict(rule)


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rule = (
        db.query(TenantWorkflowEmailRule)
        .filter(
            TenantWorkflowEmailRule.id == rule_id,
            TenantWorkflowEmailRule.tenant_id == current_user.company_id,
        )
        .first()
    )
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.is_active = False
    rule.updated_by_user_id = current_user.id
    db.commit()
    return {"deleted": True, "rule_id": rule_id}


@router.post("/rules/reorder")
def reorder_rules(
    body: _RuleReorderRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # Verify each rule belongs to this tenant.
    rows = (
        db.query(TenantWorkflowEmailRule)
        .filter(
            TenantWorkflowEmailRule.id.in_(body.rule_ids),
            TenantWorkflowEmailRule.tenant_id == current_user.company_id,
        )
        .all()
    )
    if len(rows) != len(body.rule_ids):
        raise HTTPException(
            status_code=404,
            detail="One or more rule_ids not found for this tenant",
        )
    by_id = {r.id: r for r in rows}
    for idx, rid in enumerate(body.rule_ids):
        by_id[rid].priority = idx
        by_id[rid].updated_by_user_id = current_user.id
    db.commit()
    return {"reordered": True, "count": len(rows)}


# ── Tier 2 Taxonomy CRUD ────────────────────────────────────────────


@router.get("/taxonomy")
def get_taxonomy(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        db.query(TenantWorkflowEmailCategory)
        .filter(
            TenantWorkflowEmailCategory.tenant_id == current_user.company_id
        )
        .order_by(
            TenantWorkflowEmailCategory.parent_id,
            TenantWorkflowEmailCategory.position,
        )
        .all()
    )
    return {"categories": [_category_to_dict(c) for c in rows]}


@router.post("/taxonomy/nodes", status_code=201)
def create_category(
    body: _CategoryCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if body.parent_id is not None:
        parent = (
            db.query(TenantWorkflowEmailCategory)
            .filter(
                TenantWorkflowEmailCategory.id == body.parent_id,
                TenantWorkflowEmailCategory.tenant_id == current_user.company_id,
            )
            .first()
        )
        if parent is None:
            raise HTTPException(
                status_code=400, detail="parent_id not found for this tenant"
            )
    if body.mapped_workflow_id is not None:
        wf = (
            db.query(Workflow)
            .filter(
                Workflow.id == body.mapped_workflow_id,
                Workflow.is_active.is_(True),
                or_(
                    Workflow.company_id.is_(None),
                    Workflow.company_id == current_user.company_id,
                ),
            )
            .first()
        )
        if wf is None:
            raise HTTPException(
                status_code=400,
                detail="mapped_workflow_id not available for this tenant",
            )

    cat = TenantWorkflowEmailCategory(
        tenant_id=current_user.company_id,
        parent_id=body.parent_id,
        label=body.label,
        description=body.description,
        mapped_workflow_id=body.mapped_workflow_id,
        position=body.position,
        is_active=body.is_active,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return _category_to_dict(cat)


@router.patch("/taxonomy/nodes/{node_id}")
def update_category(
    node_id: str,
    body: _CategoryUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    cat = (
        db.query(TenantWorkflowEmailCategory)
        .filter(
            TenantWorkflowEmailCategory.id == node_id,
            TenantWorkflowEmailCategory.tenant_id == current_user.company_id,
        )
        .first()
    )
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")

    if body.label is not None:
        cat.label = body.label
    if body.description is not None:
        cat.description = body.description
    if body.parent_id is not None:
        cat.parent_id = body.parent_id
    if body.mapped_workflow_id is not None:
        # Empty string means clear (workaround for nullable assignment).
        cat.mapped_workflow_id = body.mapped_workflow_id or None
    if body.position is not None:
        cat.position = body.position
    if body.is_active is not None:
        cat.is_active = body.is_active
    cat.updated_by_user_id = current_user.id
    db.commit()
    db.refresh(cat)
    return _category_to_dict(cat)


@router.delete("/taxonomy/nodes/{node_id}")
def delete_category(
    node_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    cat = (
        db.query(TenantWorkflowEmailCategory)
        .filter(
            TenantWorkflowEmailCategory.id == node_id,
            TenantWorkflowEmailCategory.tenant_id == current_user.company_id,
        )
        .first()
    )
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")
    cat.is_active = False
    cat.updated_by_user_id = current_user.id
    # Soft-cascade — descendants flip inactive too.
    descendants = (
        db.query(TenantWorkflowEmailCategory)
        .filter(
            TenantWorkflowEmailCategory.tenant_id == current_user.company_id,
            TenantWorkflowEmailCategory.parent_id == node_id,
        )
        .all()
    )
    for d in descendants:
        d.is_active = False
        d.updated_by_user_id = current_user.id
    db.commit()
    return {"deleted": True, "node_id": node_id, "descendants": len(descendants)}


# ── Tier 3 enrollment ───────────────────────────────────────────────


@router.patch("/workflows/{workflow_id}/tier3-enrollment")
def update_tier3_enrollment(
    workflow_id: str,
    body: _Tier3EnrollmentRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    wf = (
        db.query(Workflow)
        .filter(
            Workflow.id == workflow_id,
            or_(
                Workflow.company_id.is_(None),
                Workflow.company_id == current_user.company_id,
            ),
        )
        .first()
    )
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    # Only tenant admins can flip enrollment for their own workflows
    # OR for platform-global workflows (which is a tenant-scoped opt-in
    # signal — the column is per-workflow but enrollment intent is
    # tenant-scoped at the cascade level via `is_active` + tenant
    # vertical filter on assembly).
    wf.tier3_enrolled = body.enrolled
    db.commit()
    db.refresh(wf)
    return {
        "workflow_id": wf.id,
        "tier3_enrolled": wf.tier3_enrolled,
    }


# ── Audit log + replay ──────────────────────────────────────────────


@router.get("/classifications")
def list_classifications(
    tier: int | None = Query(None, ge=1, le=3),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    q = db.query(WorkflowEmailClassification).filter(
        WorkflowEmailClassification.tenant_id == current_user.company_id
    )
    if tier is not None:
        q = q.filter(WorkflowEmailClassification.tier == tier)
    rows = (
        q.order_by(WorkflowEmailClassification.created_at.desc())
        .limit(limit)
        .all()
    )
    return {"classifications": [_classification_to_dict(c) for c in rows]}


@router.get("/classifications/{classification_id}")
def get_classification(
    classification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = (
        db.query(WorkflowEmailClassification)
        .filter(
            WorkflowEmailClassification.id == classification_id,
            WorkflowEmailClassification.tenant_id == current_user.company_id,
        )
        .first()
    )
    if row is None:
        # Cross-tenant existence-hiding 404.
        raise HTTPException(status_code=404, detail="Classification not found")
    return _classification_to_dict(row)


@router.post("/messages/{message_id}/replay-classification")
def replay_classification(
    message_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = classify_only(
            db, message_id=message_id, tenant_id=current_user.company_id
        )
    except ClassificationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ClassificationError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc))

    db.commit()
    return {
        "classification_id": result.classification_id,
        "tier": result.tier,
        "selected_workflow_id": result.selected_workflow_id,
        "workflow_run_id": result.workflow_run_id,
        "is_suppressed": result.is_suppressed,
    }


@router.post("/classifications/{classification_id}/route-to-workflow")
def route_classification_to_workflow(
    classification_id: str,
    body: _ManualRouteRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.services.classification import manual_route_to_workflow

    try:
        result = manual_route_to_workflow(
            db,
            classification_id=classification_id,
            workflow_id=body.workflow_id,
            user=current_user,
            decision_notes=body.decision_notes,
        )
    except ClassificationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ClassificationError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc))

    return {
        "classification_id": result.classification_id,
        "selected_workflow_id": result.selected_workflow_id,
        "workflow_run_id": result.workflow_run_id,
    }
