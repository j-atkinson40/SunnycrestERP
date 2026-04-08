"""CRUD service for union rotation lists and members."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.union_rotation import (
    UnionRotationAssignment,
    UnionRotationList,
    UnionRotationMember,
)
from app.models.user import User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


def list_rotation_lists(
    db: Session, company_id: str
) -> list[dict]:
    """Return all rotation lists for a tenant with member counts."""
    lists = (
        db.query(UnionRotationList)
        .filter(
            UnionRotationList.company_id == company_id,
            UnionRotationList.deleted_at.is_(None),
        )
        .order_by(UnionRotationList.name)
        .all()
    )

    results = []
    for lst in lists:
        member_count = (
            db.query(func.count(UnionRotationMember.id))
            .filter(
                UnionRotationMember.list_id == lst.id,
                UnionRotationMember.active.is_(True),
            )
            .scalar()
        ) or 0

        last_assignment = (
            db.query(UnionRotationAssignment.assigned_at)
            .filter(UnionRotationAssignment.list_id == lst.id)
            .order_by(UnionRotationAssignment.assigned_at.desc())
            .first()
        )

        location_name = None
        if lst.location_id and lst.location:
            location_name = lst.location.name

        results.append(
            {
                "id": lst.id,
                "company_id": lst.company_id,
                "location_id": lst.location_id,
                "location_name": location_name,
                "name": lst.name,
                "description": lst.description,
                "trigger_type": lst.trigger_type,
                "trigger_config": lst.trigger_config or {},
                "assignment_mode": lst.assignment_mode,
                "active": lst.active,
                "member_count": member_count,
                "last_assignment_at": last_assignment[0] if last_assignment else None,
                "created_at": lst.created_at,
            }
        )
    return results


def get_rotation_list(
    db: Session, list_id: str, company_id: str
) -> UnionRotationList:
    lst = (
        db.query(UnionRotationList)
        .filter(
            UnionRotationList.id == list_id,
            UnionRotationList.company_id == company_id,
            UnionRotationList.deleted_at.is_(None),
        )
        .first()
    )
    if not lst:
        raise HTTPException(status_code=404, detail="Rotation list not found")
    return lst


def create_rotation_list(
    db: Session, company_id: str, data
) -> UnionRotationList:
    lst = UnionRotationList(
        id=str(uuid.uuid4()),
        company_id=company_id,
        location_id=data.location_id,
        name=data.name,
        description=data.description,
        trigger_type=data.trigger_type,
        trigger_config=data.trigger_config or {},
        assignment_mode=data.assignment_mode,
    )
    db.add(lst)
    db.commit()
    db.refresh(lst)
    logger.info("Created rotation list %s: %s", lst.id, lst.name)
    return lst


def update_rotation_list(
    db: Session, list_id: str, company_id: str, data
) -> UnionRotationList:
    lst = get_rotation_list(db, list_id, company_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(lst, field, value)
    db.commit()
    db.refresh(lst)
    return lst


def soft_delete_rotation_list(
    db: Session, list_id: str, company_id: str
) -> None:
    lst = get_rotation_list(db, list_id, company_id)
    lst.deleted_at = datetime.now(timezone.utc)
    db.commit()


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


def get_members(
    db: Session, list_id: str, company_id: str
) -> list[dict]:
    """Return members with user names, ordered by rotation_position."""
    # Validate list belongs to tenant
    get_rotation_list(db, list_id, company_id)

    members = (
        db.query(UnionRotationMember)
        .options(joinedload(UnionRotationMember.user))
        .filter(UnionRotationMember.list_id == list_id)
        .order_by(UnionRotationMember.rotation_position)
        .all()
    )
    return [
        {
            "id": m.id,
            "list_id": m.list_id,
            "user_id": m.user_id,
            "user_name": f"{m.user.first_name} {m.user.last_name}" if m.user else None,
            "rotation_position": m.rotation_position,
            "last_assigned_at": m.last_assigned_at,
            "last_assignment_id": m.last_assignment_id,
            "last_assignment_type": m.last_assignment_type,
            "active": m.active,
        }
        for m in members
    ]


def replace_members(
    db: Session, list_id: str, company_id: str, members_data: list[dict]
) -> list[dict]:
    """Full replacement of member roster (drag-drop save).

    Expects: [{user_id, rotation_position, active?}]
    Deactivates members not in the new list, upserts the rest.
    """
    get_rotation_list(db, list_id, company_id)

    existing = {
        m.user_id: m
        for m in db.query(UnionRotationMember)
        .filter(UnionRotationMember.list_id == list_id)
        .all()
    }

    incoming_user_ids = {m["user_id"] for m in members_data}

    # Deactivate removed members
    for uid, member in existing.items():
        if uid not in incoming_user_ids:
            member.active = False

    # Upsert incoming
    for entry in members_data:
        user_id = entry["user_id"]
        position = entry["rotation_position"]
        active = entry.get("active", True)

        if user_id in existing:
            existing[user_id].rotation_position = position
            existing[user_id].active = active
        else:
            db.add(
                UnionRotationMember(
                    id=str(uuid.uuid4()),
                    list_id=list_id,
                    user_id=user_id,
                    rotation_position=position,
                    active=active,
                )
            )

    db.commit()
    return get_members(db, list_id, company_id)


def toggle_member_active(
    db: Session, list_id: str, member_id: str, company_id: str, active: bool
) -> dict:
    get_rotation_list(db, list_id, company_id)

    member = (
        db.query(UnionRotationMember)
        .filter(
            UnionRotationMember.id == member_id,
            UnionRotationMember.list_id == list_id,
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    member.active = active
    db.commit()
    db.refresh(member)
    return {
        "id": member.id,
        "user_id": member.user_id,
        "active": member.active,
    }


# ---------------------------------------------------------------------------
# Assignment history
# ---------------------------------------------------------------------------


def get_assignment_history(
    db: Session,
    list_id: str,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Paginated assignment history for a rotation list."""
    get_rotation_list(db, list_id, company_id)

    q = (
        db.query(UnionRotationAssignment)
        .options(
            joinedload(UnionRotationAssignment.member).joinedload(
                UnionRotationMember.user
            ),
            joinedload(UnionRotationAssignment.assigned_by),
        )
        .filter(UnionRotationAssignment.list_id == list_id)
        .order_by(UnionRotationAssignment.assigned_at.desc())
    )

    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "items": [
            {
                "id": a.id,
                "list_id": a.list_id,
                "member_id": a.member_id,
                "member_name": (
                    f"{a.member.user.first_name} {a.member.user.last_name}"
                    if a.member and a.member.user
                    else None
                ),
                "assignment_type": a.assignment_type,
                "assignment_id": a.assignment_id,
                "assigned_at": a.assigned_at,
                "assigned_by_user_id": a.assigned_by_user_id,
                "assigned_by_name": (
                    f"{a.assigned_by.first_name} {a.assigned_by.last_name}"
                    if a.assigned_by
                    else None
                ),
                "notes": a.notes,
            }
            for a in items
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }
