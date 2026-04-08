"""RotationService — location-aware rotation assignment for union jobs.

Used by DisintermentService and the funeral scheduling flow. Finds the
applicable rotation list for a given trigger and assigns the next member.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.models.union_rotation import (
    UnionRotationAssignment,
    UnionRotationList,
    UnionRotationMember,
)

logger = logging.getLogger(__name__)


def get_applicable_list(
    db: Session,
    company_id: str,
    location_id: str | None,
    trigger_type: str,
    *,
    scheduled_date: datetime | None = None,
    has_hazard_pay: bool = False,
) -> UnionRotationList | None:
    """Find the rotation list matching the trigger criteria.

    For hazard_pay: returns the list if has_hazard_pay is True.
    For day_of_week: matches scheduled_date's day name against trigger_config.days.
    For manual: always returns the list (caller decides when to invoke).
    """
    q = db.query(UnionRotationList).filter(
        UnionRotationList.company_id == company_id,
        UnionRotationList.trigger_type == trigger_type,
        UnionRotationList.active.is_(True),
        UnionRotationList.deleted_at.is_(None),
    )

    # Location filter: match specific location or NULL (all-locations list)
    if location_id:
        q = q.filter(
            (UnionRotationList.location_id == location_id)
            | (UnionRotationList.location_id.is_(None))
        )
    else:
        q = q.filter(UnionRotationList.location_id.is_(None))

    candidates = q.all()
    if not candidates:
        return None

    for lst in candidates:
        if trigger_type == "hazard_pay":
            if has_hazard_pay:
                return lst
        elif trigger_type == "day_of_week":
            if scheduled_date:
                day_name = scheduled_date.strftime("%A").lower()
                config_days = [d.lower() for d in (lst.trigger_config or {}).get("days", [])]
                if day_name in config_days:
                    return lst
        elif trigger_type == "manual":
            return lst

    return None


def get_next_member(
    db: Session, list_id: str
) -> UnionRotationMember | None:
    """Get the next member in rotation — ordered by last_assigned_at ASC NULLS FIRST,
    then rotation_position ASC. Returns the first active member.
    """
    member = (
        db.query(UnionRotationMember)
        .filter(
            UnionRotationMember.list_id == list_id,
            UnionRotationMember.active.is_(True),
        )
        .order_by(
            UnionRotationMember.last_assigned_at.asc().nullsfirst(),
            UnionRotationMember.rotation_position.asc(),
        )
        .first()
    )
    return member


def get_next_and_assign(
    db: Session,
    company_id: str,
    location_id: str | None,
    trigger_type: str,
    assignment_type: str,
    assignment_id: str,
    assigned_by_user_id: str | None = None,
    *,
    scheduled_date: datetime | None = None,
    has_hazard_pay: bool = False,
) -> UnionRotationAssignment | None:
    """Find applicable list → get next member → create assignment.

    Returns None if no rotation list matches (no rotation needed).
    """
    rotation_list = get_applicable_list(
        db,
        company_id,
        location_id,
        trigger_type,
        scheduled_date=scheduled_date,
        has_hazard_pay=has_hazard_pay,
    )
    if not rotation_list:
        return None

    member = get_next_member(db, rotation_list.id)
    if not member:
        logger.warning(
            "Rotation list %s (%s) has no active members",
            rotation_list.id,
            rotation_list.name,
        )
        return None

    now = datetime.now(timezone.utc)

    # Create assignment record
    assignment = UnionRotationAssignment(
        id=str(uuid.uuid4()),
        list_id=rotation_list.id,
        member_id=member.id,
        assignment_type=assignment_type,
        assignment_id=assignment_id,
        assigned_at=now,
        assigned_by_user_id=assigned_by_user_id,
    )
    db.add(assignment)

    # Update member tracking
    member.last_assigned_at = now
    member.last_assignment_id = assignment_id
    member.last_assignment_type = assignment_type

    db.flush()

    logger.info(
        "Rotation assignment: list=%s member=%s (user=%s) → %s %s",
        rotation_list.name,
        member.id,
        member.user_id,
        assignment_type,
        assignment_id,
    )
    return assignment
