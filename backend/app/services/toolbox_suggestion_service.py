"""Toolbox talk suggestion engine — evaluates signals and generates suggestions."""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.toolbox_talk import ToolboxTalk
from app.models.toolbox_talk_suggestion import ToolboxTalkSuggestion
from app.models.tenant_training_schedule import TenantTrainingSchedule

logger = logging.getLogger(__name__)

# Signal priority order
SIGNAL_PRIORITY = [
    "recent_incident",
    "inspection_failure",
    "seasonal",
    "monthly_training",
    "compliance_gap",
    "topic_overdue",
]

# Northern states for seasonal signal filtering
NORTHERN_STATES = {
    "ME", "NH", "VT", "MA", "RI", "CT", "NY", "NJ", "PA",
    "OH", "IN", "IL", "MI", "WI", "MN", "IA", "ND", "SD",
    "NE", "KS", "MO", "WY", "CO", "UT", "ID", "MT", "WA", "OR", "NV",
}

SEASONAL_SIGNALS = [
    {
        "topic_title": "Spring Startup Safety — After Winter Layoff",
        "topic_category": "seasonal",
        "trigger_description": (
            "Spring startup after winter shutdown is one of the highest-incident "
            "periods of the year. Equipment has been sitting, crews are rusty on "
            "procedures, and conditions change quickly."
        ),
        "months": [3, 4],
        "region_filter": "northern",
    },
    {
        "topic_title": "Heat Illness Prevention — Summer Operations",
        "topic_category": "seasonal",
        "trigger_description": (
            "Heat illness risk peaks in summer months. Outdoor precast work and "
            "hot production areas create serious risk, especially during heat advisories."
        ),
        "months": [6, 7, 8],
        "region_filter": None,
    },
    {
        "topic_title": "Cold Weather Safety and Winter Hazards",
        "topic_category": "seasonal",
        "trigger_description": (
            "Winter brings ice, cold concrete, and cold stress risks. Slip and "
            "fall incidents increase significantly in cold weather."
        ),
        "months": [11, 12, 1, 2],
        "region_filter": "northern",
    },
    {
        "topic_title": "Severe Weather Preparedness",
        "topic_category": "seasonal",
        "trigger_description": (
            "Spring severe weather season. Review emergency action plan, shelter "
            "locations, and outdoor work protocols during lightning or high wind events."
        ),
        "months": [4, 5],
        "region_filter": None,
    },
]


# ---------------------------------------------------------------------------
# Signal evaluation
# ---------------------------------------------------------------------------


def get_active_suggestion(db: Session, tenant_id: str) -> ToolboxTalkSuggestion | None:
    """Get the current active suggestion for a tenant, if any."""
    return (
        db.query(ToolboxTalkSuggestion)
        .filter(
            ToolboxTalkSuggestion.tenant_id == tenant_id,
            ToolboxTalkSuggestion.status == "active",
        )
        .order_by(ToolboxTalkSuggestion.suggestion_date.desc())
        .first()
    )


def evaluate_signals(
    db: Session, tenant_id: str, tenant_state: str | None = None,
) -> dict[str, Any] | None:
    """Evaluate all signals in priority order. Returns the highest-priority signal or None."""
    now = datetime.now(timezone.utc)
    today = date.today()
    fourteen_days_ago = today - timedelta(days=14)

    # Check if a recent active suggestion exists
    active = (
        db.query(ToolboxTalkSuggestion)
        .filter(
            ToolboxTalkSuggestion.tenant_id == tenant_id,
            ToolboxTalkSuggestion.status == "active",
            ToolboxTalkSuggestion.suggestion_date >= fourteen_days_ago,
        )
        .first()
    )
    if active:
        return None

    current_month = today.month
    current_year = today.year

    # SIGNAL 1 — Recent incident
    try:
        from app.models.safety_incident import SafetyIncident

        recent_incident = (
            db.query(SafetyIncident)
            .filter(
                SafetyIncident.tenant_id == tenant_id,
                SafetyIncident.incident_date >= fourteen_days_ago,
            )
            .order_by(SafetyIncident.incident_date.desc())
            .first()
        )
        if recent_incident:
            # Check if a follow-up talk was already logged
            follow_up = (
                db.query(ToolboxTalk)
                .filter(
                    ToolboxTalk.tenant_id == tenant_id,
                    ToolboxTalk.topic_category == "incident_followup",
                    ToolboxTalk.conducted_at >= recent_incident.incident_date,
                )
                .first()
            )
            if not follow_up:
                desc = getattr(recent_incident, "brief_description", "workplace incident")
                return {
                    "trigger_type": "recent_incident",
                    "topic_title": f"Incident Follow-up — {desc[:60]}",
                    "topic_category": "incident_followup",
                    "trigger_description": (
                        f"A workplace incident occurred recently. A toolbox talk "
                        f"following an incident reinforces awareness and helps "
                        f"prevent recurrence."
                    ),
                    "trigger_entity_type": "incident",
                    "trigger_entity_id": recent_incident.id,
                }
    except ImportError:
        pass

    # SIGNAL 2 — Inspection failure
    try:
        from app.models.inspection_record import InspectionRecord

        recent_failure = (
            db.query(InspectionRecord)
            .filter(
                InspectionRecord.tenant_id == tenant_id,
                InspectionRecord.overall_result == "fail",
                InspectionRecord.inspected_at >= now - timedelta(days=14),
            )
            .order_by(InspectionRecord.inspected_at.desc())
            .first()
        )
        if recent_failure:
            follow_up = (
                db.query(ToolboxTalk)
                .filter(
                    ToolboxTalk.tenant_id == tenant_id,
                    ToolboxTalk.topic_category == "equipment",
                    ToolboxTalk.conducted_at >= recent_failure.inspected_at,
                )
                .first()
            )
            if not follow_up:
                return {
                    "trigger_type": "inspection_failure",
                    "topic_title": "Equipment Safety — Failed Inspection Review",
                    "topic_category": "equipment",
                    "trigger_description": (
                        "Equipment failed its recent inspection. This is a good "
                        "time to review safe operation practices with the crew."
                    ),
                    "trigger_entity_type": "inspection_record",
                    "trigger_entity_id": recent_failure.id,
                }
    except ImportError:
        pass

    # SIGNAL 3 — Seasonal hazard
    is_northern = (tenant_state or "").upper() in NORTHERN_STATES
    for signal in SEASONAL_SIGNALS:
        if current_month not in signal["months"]:
            continue
        if signal["region_filter"] == "northern" and not is_northern:
            continue
        # Check if seasonal topic was already covered this season
        season_start = today.replace(month=signal["months"][0], day=1)
        if season_start > today:
            season_start = season_start.replace(year=season_start.year - 1)
        existing = (
            db.query(ToolboxTalk)
            .filter(
                ToolboxTalk.tenant_id == tenant_id,
                ToolboxTalk.topic_category == "seasonal",
                ToolboxTalk.conducted_at >= season_start,
            )
            .first()
        )
        if not existing:
            return {
                "trigger_type": "seasonal",
                "topic_title": signal["topic_title"],
                "topic_category": "seasonal",
                "trigger_description": signal["trigger_description"],
                "trigger_entity_type": None,
                "trigger_entity_id": None,
            }

    # SIGNAL 4 — Monthly training reinforcement
    training = (
        db.query(TenantTrainingSchedule)
        .filter(
            TenantTrainingSchedule.tenant_id == tenant_id,
            TenantTrainingSchedule.month_number == current_month,
            TenantTrainingSchedule.year == current_year,
        )
        .first()
    )
    if training:
        reinforcement = (
            db.query(ToolboxTalk)
            .filter(
                ToolboxTalk.tenant_id == tenant_id,
                ToolboxTalk.linked_training_topic_id == training.topic_id,
                func.date(ToolboxTalk.conducted_at) >= today.replace(day=1),
            )
            .first()
        )
        if not reinforcement:
            topic_title = training.topic.title if training.topic else "Monthly Training"
            return {
                "trigger_type": "monthly_training",
                "topic_title": f"Training Reinforcement — {topic_title}",
                "topic_category": "training_reinforcement",
                "trigger_description": (
                    f"This month's OSHA training covers {topic_title}. "
                    f"A toolbox talk this week reinforces what employees "
                    f"learned in the formal training."
                ),
                "trigger_entity_type": "training_schedule",
                "trigger_entity_id": training.id,
            }

    # SIGNAL 5 — Topic overdue fallback
    # Find least recently covered general safety topic
    last_talk = (
        db.query(ToolboxTalk)
        .filter(ToolboxTalk.tenant_id == tenant_id)
        .order_by(ToolboxTalk.conducted_at.desc())
        .first()
    )
    days_since = (
        (today - last_talk.conducted_at.date()).days if last_talk else 999
    )
    if days_since > 14:
        return {
            "trigger_type": "topic_overdue",
            "topic_title": "General Safety Refresher",
            "topic_category": "hazard_awareness",
            "trigger_description": (
                "No toolbox talk has been logged recently. Regular refreshers "
                "on core safety topics keep awareness high."
            ),
            "trigger_entity_type": None,
            "trigger_entity_id": None,
        }

    return None


# ---------------------------------------------------------------------------
# Suggestion creation
# ---------------------------------------------------------------------------


def create_suggestion(
    db: Session, tenant_id: str, signal: dict[str, Any],
) -> ToolboxTalkSuggestion:
    """Create a suggestion record from an evaluated signal."""
    today = date.today()
    suggestion = ToolboxTalkSuggestion(
        tenant_id=tenant_id,
        suggestion_date=today,
        topic_title=signal["topic_title"],
        topic_category=signal["topic_category"],
        trigger_type=signal["trigger_type"],
        trigger_description=signal["trigger_description"],
        trigger_entity_type=signal.get("trigger_entity_type"),
        trigger_entity_id=signal.get("trigger_entity_id"),
        status="active",
        next_suggestion_after=today + timedelta(days=14),
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    return suggestion


def dismiss_suggestion(
    db: Session, suggestion_id: str, tenant_id: str, user_id: str,
) -> bool:
    """Dismiss an active suggestion."""
    suggestion = (
        db.query(ToolboxTalkSuggestion)
        .filter(
            ToolboxTalkSuggestion.id == suggestion_id,
            ToolboxTalkSuggestion.tenant_id == tenant_id,
            ToolboxTalkSuggestion.status == "active",
        )
        .first()
    )
    if not suggestion:
        return False
    suggestion.status = "dismissed"
    suggestion.dismissed_at = datetime.now(timezone.utc)
    suggestion.dismissed_by = user_id
    db.commit()
    return True


def resolve_suggestion_on_talk_logged(
    db: Session, talk: ToolboxTalk, tenant_id: str,
) -> None:
    """Auto-resolve active suggestion when a matching talk is logged."""
    active = get_active_suggestion(db, tenant_id)
    if not active:
        return

    topic_matches = (
        talk.generated_from_suggestion_id == active.id
        or (
            active.topic_title
            and talk.topic_title
            and active.topic_title.lower().split(" ")[0]
            in talk.topic_title.lower()
        )
        or (
            active.trigger_entity_type == "training_schedule"
            and talk.linked_training_topic_id
            and str(talk.linked_training_topic_id) == str(active.trigger_entity_id)
        )
    )

    if topic_matches:
        active.status = "used"
        active.used_at = datetime.now(timezone.utc)
        active.used_in_toolbox_talk_id = talk.id
        db.commit()
