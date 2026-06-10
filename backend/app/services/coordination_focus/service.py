"""Job Coordination Focus — service layer (JCF-1, backend-only).

Implements the settled decisions (DECISIONS.md 2026-06-10):
- ENTRY = order-launched: `ensure_instance_for_order` is the idempotent
  spawn/offer for the landing sales_order. It CONSUMES the live
  create_vault_order path's output (the order row) — it does NOT modify
  that path; callers (the e2e today; the Order Station offer + workflow
  triggers in JCF-2+) invoke it against the landed order.
- ACCESS = FocusShare (DocumentShare clone): the read-guard `can_access`
  passes for the owner tenant, or for a grantee with an ACTIVE share
  (company-wide or person-scoped), preconditioned at grant time on an
  active PlatformTenantRelationship (the same
  `has_active_relationship` helper the document grant uses).
- COMMS = the in-platform Focus-scoped thread: post/list authorized
  through the SAME read-guard as the Focus itself.
- Decision-bounded closure: `close_instance` revokes all active shares;
  the jcf task-subscriber calls it when the bound task completes (riding
  the same task-completion event family as focus_subscriber).

Realm note: tenant-realm consumers pass the acting User; the service
operates on company_id + user_id primitives (realm-agnostic per CLAUDE.md).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.models.coordination_focus import (
    CoordinationFocusInstance,
    FocusShare,
    FocusShareEvent,
    JCFThreadMessage,
)
from app.models.focus_template import FocusTemplate
from app.services.documents.document_sharing_service import (
    has_active_relationship,
)

JCF_TEMPLATE_SLUG = "job-coordination"


class AccessDenied(Exception):
    """The caller has no path to this Focus instance (no ownership, no
    active share). Routes translate to 404 (existence not disclosed)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _record_event(
    db: Session,
    share: FocusShare,
    event_type: str,
    *,
    actor_user_id: str | None,
    actor_company_id: str | None,
    detail: dict | None = None,
) -> None:
    db.add(
        FocusShareEvent(
            share_id=share.id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            actor_company_id=actor_company_id,
            detail=detail,
        )
    )


# ── Instance lifecycle ──────────────────────────────────────────────


def ensure_instance_for_order(
    db: Session,
    sales_order_id: str,
    *,
    title: str | None = None,
    source_fh_company_id: str | None = None,
    task_id: str | None = None,
) -> CoordinationFocusInstance:
    """Idempotent order-launched spawn: one instance per landing order.

    Reads the order row (raw SQL, matching create_vault_order's
    light-touch discipline) to derive the owner tenant + a default title.
    Re-calling returns the existing instance unchanged.
    """
    existing = (
        db.query(CoordinationFocusInstance)
        .filter(CoordinationFocusInstance.sales_order_id == sales_order_id)
        .first()
    )
    if existing:
        return existing

    row = db.execute(
        sql_text(
            "SELECT company_id, order_number, deceased_name "
            "FROM sales_orders WHERE id = :id"
        ),
        {"id": sales_order_id},
    ).first()
    if row is None:
        raise ValueError("sales_order not found")

    instance = CoordinationFocusInstance(
        id=str(uuid.uuid4()),
        company_id=row.company_id,
        sales_order_id=sales_order_id,
        source_fh_company_id=source_fh_company_id,
        title=title
        or f"Job coordination — {row.order_number or sales_order_id[:8]}"
        + (f" ({row.deceased_name})" if row.deceased_name else ""),
        status="active",
        task_id=task_id,
    )
    db.add(instance)
    db.commit()
    db.refresh(instance)
    return instance


def get_instance(
    db: Session, instance_id: str
) -> CoordinationFocusInstance | None:
    return (
        db.query(CoordinationFocusInstance)
        .filter(CoordinationFocusInstance.id == instance_id)
        .first()
    )


def close_instance(
    db: Session,
    instance: CoordinationFocusInstance,
    *,
    actor_user_id: str | None = None,
    reason: str = "job_completed",
) -> int:
    """Close the instance + AUTO-REVOKE every active share (the
    decision-bounded expiry). Idempotent. Returns revoked-share count."""
    revoked = 0
    if instance.status != "closed":
        instance.status = "closed"
        instance.closed_at = _now()
    shares = (
        db.query(FocusShare)
        .filter(
            FocusShare.instance_id == instance.id,
            FocusShare.revoked_at.is_(None),
        )
        .all()
    )
    for share in shares:
        share.revoked_at = _now()
        share.revoked_by_user_id = actor_user_id
        share.revoke_reason = reason
        _record_event(
            db,
            share,
            "revoked",
            actor_user_id=actor_user_id,
            actor_company_id=instance.company_id,
            detail={"auto": actor_user_id is None, "reason": reason},
        )
        revoked += 1
    db.commit()
    return revoked


# ── Share lifecycle (the DocumentShare-clone grant) ─────────────────


def grant_share(
    db: Session,
    instance: CoordinationFocusInstance,
    *,
    target_company_id: str,
    target_user_id: str | None = None,
    granted_by_user_id: str | None = None,
    source_module: str = "coordination_focus",
) -> FocusShare:
    """Grant the cross-tenant read. Preconditions: the instance is active;
    an ACTIVE PlatformTenantRelationship links the tenants (the same
    precondition the document grant enforces). Idempotent on an
    already-active equivalent grant."""
    if instance.status != "active":
        raise ValueError("cannot grant on a closed instance")
    if target_company_id == instance.company_id:
        raise ValueError("target is the owner tenant")
    if not has_active_relationship(
        db, instance.company_id, target_company_id
    ):
        raise ValueError("no active tenant relationship")

    existing = (
        db.query(FocusShare)
        .filter(
            FocusShare.instance_id == instance.id,
            FocusShare.target_company_id == target_company_id,
            FocusShare.target_user_id == target_user_id,
            FocusShare.revoked_at.is_(None),
        )
        .first()
    )
    if existing:
        return existing

    share = FocusShare(
        id=str(uuid.uuid4()),
        instance_id=instance.id,
        owner_company_id=instance.company_id,
        target_company_id=target_company_id,
        target_user_id=target_user_id,
        permission="read",
        granted_by_user_id=granted_by_user_id,
        source_module=source_module,
    )
    db.add(share)
    db.flush()
    _record_event(
        db,
        share,
        "granted",
        actor_user_id=granted_by_user_id,
        actor_company_id=instance.company_id,
    )
    db.commit()
    db.refresh(share)
    return share


def revoke_share(
    db: Session,
    share: FocusShare,
    *,
    revoked_by_user_id: str | None = None,
    reason: str | None = None,
) -> FocusShare:
    if share.revoked_at is None:
        share.revoked_at = _now()
        share.revoked_by_user_id = revoked_by_user_id
        share.revoke_reason = reason
        _record_event(
            db,
            share,
            "revoked",
            actor_user_id=revoked_by_user_id,
            actor_company_id=share.owner_company_id,
            detail={"auto": False, "reason": reason},
        )
        db.commit()
    return share


def get_active_share(
    db: Session,
    instance_id: str,
    company_id: str,
    user_id: str | None = None,
) -> FocusShare | None:
    """The active share that admits (company_id, user_id): a person-scoped
    share for this user, or a company-wide share (target_user_id NULL)."""
    q = db.query(FocusShare).filter(
        FocusShare.instance_id == instance_id,
        FocusShare.target_company_id == company_id,
        FocusShare.revoked_at.is_(None),
    )
    shares = q.all()
    for s in shares:
        if s.target_user_id is None or s.target_user_id == user_id:
            return s
    return None


# ── The read-guard ──────────────────────────────────────────────────


def can_access(
    db: Session,
    instance: CoordinationFocusInstance,
    *,
    company_id: str,
    user_id: str | None = None,
) -> bool:
    """Owner tenant always; grantee iff an ACTIVE share admits them.
    A revoked/expired share fails closed."""
    if company_id == instance.company_id:
        return True
    return (
        get_active_share(db, instance.id, company_id, user_id) is not None
    )


def _resolve_template(db: Session) -> dict[str, Any] | None:
    """The job-coordination FocusTemplate (composition) — JCF-1 proves the
    template RESOLVES (rows/placements returned); rendering is JCF-2.
    First-match by scope specificity over the seeded slug."""
    row = (
        db.query(FocusTemplate)
        .filter(FocusTemplate.template_slug == JCF_TEMPLATE_SLUG)
        .order_by(FocusTemplate.scope.desc())  # vertical_default > platform_default lexically
        .first()
    )
    if row is None:
        return None
    return {
        "template_id": row.id,
        "template_slug": row.template_slug,
        "scope": row.scope,
        "rows": row.rows,
        "canvas_config": row.canvas_config,
    }


def read_instance(
    db: Session,
    instance_id: str,
    *,
    company_id: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    """The guarded Focus read: instance + the resolved composition template.
    Cross-tenant reads record an 'accessed' audit event on the admitting
    share. Raises AccessDenied (route → 404) when no path admits."""
    instance = get_instance(db, instance_id)
    if instance is None:
        raise AccessDenied()
    if company_id != instance.company_id:
        share = get_active_share(db, instance.id, company_id, user_id)
        if share is None:
            raise AccessDenied()
        _record_event(
            db,
            share,
            "accessed",
            actor_user_id=user_id,
            actor_company_id=company_id,
        )
        db.commit()
    return {
        "instance": {
            "id": instance.id,
            "company_id": instance.company_id,
            "sales_order_id": instance.sales_order_id,
            "source_fh_company_id": instance.source_fh_company_id,
            "title": instance.title,
            "status": instance.status,
            "task_id": instance.task_id,
            "created_at": instance.created_at.isoformat(),
            "closed_at": instance.closed_at.isoformat()
            if instance.closed_at
            else None,
        },
        "composition": _resolve_template(db),
        "is_owner": company_id == instance.company_id,
    }


# ── The Focus-scoped thread ─────────────────────────────────────────


def post_message(
    db: Session,
    instance_id: str,
    *,
    company_id: str,
    user_id: str,
    body: str,
) -> JCFThreadMessage:
    """Post iff the SAME read-guard admits the author (owner or active
    share). Closed instances are read-only."""
    instance = get_instance(db, instance_id)
    if instance is None or not can_access(
        db, instance, company_id=company_id, user_id=user_id
    ):
        raise AccessDenied()
    if instance.status != "active":
        raise ValueError("instance is closed")
    if not body or not body.strip():
        raise ValueError("empty message")
    msg = JCFThreadMessage(
        id=str(uuid.uuid4()),
        instance_id=instance_id,
        author_company_id=company_id,
        author_user_id=user_id,
        body=body.strip(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def list_messages(
    db: Session,
    instance_id: str,
    *,
    company_id: str,
    user_id: str | None = None,
    limit: int = 100,
) -> list[JCFThreadMessage]:
    instance = get_instance(db, instance_id)
    if instance is None or not can_access(
        db, instance, company_id=company_id, user_id=user_id
    ):
        raise AccessDenied()
    return (
        db.query(JCFThreadMessage)
        .filter(JCFThreadMessage.instance_id == instance_id)
        .order_by(JCFThreadMessage.created_at.asc())
        .limit(limit)
        .all()
    )
