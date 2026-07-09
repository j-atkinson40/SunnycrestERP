"""MoC Planning — the personal build-backlog service (r123).

CRUD over moc_planning_item, owner-stamped on create and OWNER-CHECKED on
patch/delete (you edit only yours — the personal scope enforced at the
service, not just the render). Loud-reject validation on kind / status /
scope-vertical coherence, per the 2a discipline.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.moc_planning_item import (
    PLANNING_KINDS,
    PLANNING_STATUSES,
    MoCPlanningItem,
)

_UNSET: Any = object()


class PlanningValidationError(Exception):
    """Bad shape or not-yours — message names the problem."""


def _validate_scope(scope: str, vertical: str | None) -> None:
    if scope == "platform_default":
        if vertical is not None:
            raise PlanningValidationError(
                "a platform_default planning item is vertical-less"
            )
    elif scope == "vertical_default":
        if not vertical:
            raise PlanningValidationError(
                "a vertical_default planning item requires a vertical"
            )
    else:
        raise PlanningValidationError(f"invalid scope {scope!r}")


def _validate_kind(kind: str) -> None:
    if kind not in PLANNING_KINDS:
        raise PlanningValidationError(
            f"invalid kind {kind!r} (one of: {', '.join(PLANNING_KINDS)})"
        )


def _validate_status(status: str) -> None:
    if status not in PLANNING_STATUSES:
        raise PlanningValidationError(
            f"invalid status {status!r} (one of: {', '.join(PLANNING_STATUSES)})"
        )


def list_items(
    db: Session, *, owner_user_id: str, scope: str, vertical: str | None
) -> list[MoCPlanningItem]:
    """THE PERSONAL LENS: only the asking user's items, only this map's tier."""
    q = db.query(MoCPlanningItem).filter(
        MoCPlanningItem.owner_user_id == owner_user_id,
        MoCPlanningItem.scope == scope,
    )
    if scope == "vertical_default":
        q = q.filter(MoCPlanningItem.vertical == vertical)
    return q.order_by(
        MoCPlanningItem.display_order, MoCPlanningItem.created_at
    ).all()


def create_item(
    db: Session,
    *,
    owner_user_id: str,
    scope: str,
    vertical: str | None,
    kind: str,
    title: str,
    description: str | None = None,
    status: str = "planned",
    display_order: int = 0,
) -> MoCPlanningItem:
    _validate_scope(scope, vertical)
    _validate_kind(kind)
    _validate_status(status)
    if not title or not title.strip():
        raise PlanningValidationError("title is required")
    item = MoCPlanningItem(
        owner_user_id=owner_user_id,
        scope=scope,
        vertical=vertical,
        kind=kind,
        title=title.strip(),
        description=(description or "").strip() or None,
        status=status,
        display_order=display_order,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _owned(db: Session, item_id: str, owner_user_id: str) -> MoCPlanningItem:
    item = db.get(MoCPlanningItem, item_id)
    if item is None or item.owner_user_id != owner_user_id:
        # Not-found for another user's item too — existence isn't leaked.
        raise PlanningValidationError(f"planning item {item_id!r} not found")
    return item


def patch_item(
    db: Session,
    *,
    item_id: str,
    owner_user_id: str,
    title: Any = _UNSET,
    description: Any = _UNSET,
    kind: Any = _UNSET,
    status: Any = _UNSET,
    display_order: Any = _UNSET,
) -> MoCPlanningItem:
    item = _owned(db, item_id, owner_user_id)
    if kind is not _UNSET:
        _validate_kind(kind)
        item.kind = kind
    if status is not _UNSET:
        _validate_status(status)
        item.status = status
    if title is not _UNSET:
        if not title or not str(title).strip():
            raise PlanningValidationError("title cannot be emptied")
        item.title = str(title).strip()
    if description is not _UNSET:
        item.description = (str(description or "")).strip() or None
    if display_order is not _UNSET:
        item.display_order = int(display_order)
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, *, item_id: str, owner_user_id: str) -> None:
    item = _owned(db, item_id, owner_user_id)
    db.delete(item)
    db.commit()


def to_payload(item: MoCPlanningItem) -> dict:
    return {
        "id": item.id,
        "scope": item.scope,
        "vertical": item.vertical,
        "kind": item.kind,
        "title": item.title,
        "description": item.description,
        "status": item.status,
        "display_order": item.display_order,
        "created_artifact_slug": item.created_artifact_slug,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }
