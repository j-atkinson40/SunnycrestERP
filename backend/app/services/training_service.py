"""Employee training service — profiles, procedures, explanations, coaching."""

import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.training import (
    CoachingObservation,
    ContextualExplanation,
    GuidedFlowSession,
    TrainingCurriculumTrack,
    TrainingProcedure,
    UserLearningProfile,
    UserTrackProgress,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Learning Profiles
# ---------------------------------------------------------------------------


def create_learning_profile(db: Session, tenant_id: str, user_id: str, training_role: str) -> UserLearningProfile:
    existing = db.query(UserLearningProfile).filter(UserLearningProfile.tenant_id == tenant_id, UserLearningProfile.user_id == user_id).first()
    if existing:
        return existing

    profile = UserLearningProfile(id=str(uuid.uuid4()), tenant_id=tenant_id, user_id=user_id, training_role=training_role)
    db.add(profile)

    # Assign curriculum track
    track = db.query(TrainingCurriculumTrack).filter(TrainingCurriculumTrack.tenant_id == tenant_id, TrainingCurriculumTrack.training_role == training_role, TrainingCurriculumTrack.is_active.is_(True)).first()
    if track:
        profile.curriculum_track_id = track.id
        progress = UserTrackProgress(id=str(uuid.uuid4()), tenant_id=tenant_id, user_id=user_id, track_id=track.id)
        db.add(progress)

    db.commit()
    db.refresh(profile)
    return profile


def get_learning_profile(db: Session, tenant_id: str, user_id: str) -> dict | None:
    profile = db.query(UserLearningProfile).filter(UserLearningProfile.tenant_id == tenant_id, UserLearningProfile.user_id == user_id).first()
    if not profile:
        return None

    days_on_platform = (date.today() - profile.employee_start_date).days if profile.employee_start_date else 0

    return {
        "user_id": profile.user_id,
        "training_role": profile.training_role,
        "is_new_employee": profile.is_new_employee,
        "days_on_platform": days_on_platform,
        "guided_flows_completed": profile.guided_flows_completed or [],
        "procedures_viewed": profile.procedures_viewed or {},
        "show_contextual_explanations": profile.show_contextual_explanations,
        "show_guided_flow_offers": profile.show_guided_flow_offers,
        "show_new_employee_briefing": profile.show_new_employee_briefing,
        "curriculum_track_id": profile.curriculum_track_id,
    }


def is_new_employee(db: Session, tenant_id: str, user_id: str) -> bool:
    profile = db.query(UserLearningProfile).filter(UserLearningProfile.tenant_id == tenant_id, UserLearningProfile.user_id == user_id).first()
    if not profile:
        return False
    return profile.is_new_employee and profile.employee_start_date and (date.today() - profile.employee_start_date).days <= 90


def record_coaching_observation(db: Session, tenant_id: str, user_id: str, observation_type: str, data: dict | None = None, is_positive: bool = False) -> None:
    """Fire-and-forget — never block workflow."""
    try:
        obs = CoachingObservation(id=str(uuid.uuid4()), tenant_id=tenant_id, user_id=user_id, observation_type=observation_type, observation_data=data or {}, is_positive=is_positive)
        db.add(obs)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to record coaching observation: {e}")
        db.rollback()


# ---------------------------------------------------------------------------
# Track Progress
# ---------------------------------------------------------------------------


def get_track_progress(db: Session, tenant_id: str, user_id: str) -> dict | None:
    progress = db.query(UserTrackProgress).filter(UserTrackProgress.tenant_id == tenant_id, UserTrackProgress.user_id == user_id).order_by(desc(UserTrackProgress.started_at)).first()
    if not progress:
        return None

    track = db.query(TrainingCurriculumTrack).filter(TrainingCurriculumTrack.id == progress.track_id).first()

    return {
        "track_id": progress.track_id,
        "track_name": track.track_name if track else "Unknown",
        "training_role": track.training_role if track else None,
        "status": progress.status,
        "current_module_index": progress.current_module_index,
        "module_completions": progress.module_completions or [],
        "total_modules": track.total_modules if track else 0,
        "modules": track.modules if track else [],
    }


def complete_module(db: Session, tenant_id: str, user_id: str, module_key: str, comprehension_passed: bool) -> dict:
    progress = db.query(UserTrackProgress).filter(UserTrackProgress.tenant_id == tenant_id, UserTrackProgress.user_id == user_id).first()
    if not progress:
        return {"error": "No track progress found"}

    completions = list(progress.module_completions or [])
    completions.append({
        "module_key": module_key,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "comprehension_passed": comprehension_passed,
    })
    progress.module_completions = completions
    progress.current_module_index = len(completions)

    # Check if all modules complete
    track = db.query(TrainingCurriculumTrack).filter(TrainingCurriculumTrack.id == progress.track_id).first()
    if track and progress.current_module_index >= track.total_modules:
        progress.status = "completed"
        progress.completed_at = datetime.now(timezone.utc)
        # Auto-mark as competent
        profile = db.query(UserLearningProfile).filter(UserLearningProfile.tenant_id == tenant_id, UserLearningProfile.user_id == user_id).first()
        if profile:
            profile.is_new_employee = False

    db.commit()
    record_coaching_observation(db, tenant_id, user_id, "curriculum_module_completed", {"module_key": module_key}, is_positive=True)
    return {"status": "ok", "modules_completed": len(completions)}


# ---------------------------------------------------------------------------
# Procedures
# ---------------------------------------------------------------------------


def get_procedures(db: Session, tenant_id: str, category: str | None = None, role: str | None = None) -> list[dict]:
    query = db.query(TrainingProcedure).filter(TrainingProcedure.tenant_id == tenant_id, TrainingProcedure.is_active.is_(True))
    if category:
        query = query.filter(TrainingProcedure.category == category)
    procedures = query.order_by(TrainingProcedure.sort_order, TrainingProcedure.title).all()

    results = []
    for p in procedures:
        if role and role not in (p.applicable_roles or []):
            continue
        results.append({
            "procedure_key": p.procedure_key,
            "title": p.title,
            "category": p.category,
            "applicable_roles": p.applicable_roles,
            "overview": p.overview,
            "steps": p.steps,
            "related_procedure_keys": p.related_procedure_keys,
            "content_generated": p.content_generated,
        })
    return results


def get_procedure(db: Session, tenant_id: str, procedure_key: str) -> dict | None:
    p = db.query(TrainingProcedure).filter(TrainingProcedure.tenant_id == tenant_id, TrainingProcedure.procedure_key == procedure_key).first()
    if not p:
        return None
    return {
        "procedure_key": p.procedure_key, "title": p.title, "category": p.category,
        "applicable_roles": p.applicable_roles, "overview": p.overview, "steps": p.steps,
        "related_procedure_keys": p.related_procedure_keys, "content_generated": p.content_generated,
        "last_edited_at": p.last_edited_at.isoformat() if p.last_edited_at else None,
    }


# ---------------------------------------------------------------------------
# Contextual Explanations
# ---------------------------------------------------------------------------


def get_explanation(db: Session, tenant_id: str, explanation_key: str) -> dict | None:
    e = db.query(ContextualExplanation).filter(ContextualExplanation.tenant_id == tenant_id, ContextualExplanation.explanation_key == explanation_key, ContextualExplanation.is_active.is_(True)).first()
    if not e:
        return None
    return {"explanation_key": e.explanation_key, "headline": e.headline, "explanation": e.explanation, "trigger_context": e.trigger_context}


# ---------------------------------------------------------------------------
# Guided Flows
# ---------------------------------------------------------------------------


def should_offer_flow(db: Session, tenant_id: str, user_id: str, flow_key: str) -> bool:
    profile = db.query(UserLearningProfile).filter(UserLearningProfile.tenant_id == tenant_id, UserLearningProfile.user_id == user_id).first()
    if not profile or not profile.show_guided_flow_offers or not profile.is_new_employee:
        return False

    session = db.query(GuidedFlowSession).filter(GuidedFlowSession.tenant_id == tenant_id, GuidedFlowSession.user_id == user_id, GuidedFlowSession.flow_key == flow_key).first()
    if session:
        if session.status == "completed":
            return False
        if session.status == "skipped" and session.offer_count >= 3:
            return False
        if session.status == "in_progress":
            return True
    return True


def start_flow(db: Session, tenant_id: str, user_id: str, flow_key: str, total_steps: int) -> dict:
    session = db.query(GuidedFlowSession).filter(GuidedFlowSession.tenant_id == tenant_id, GuidedFlowSession.user_id == user_id, GuidedFlowSession.flow_key == flow_key).first()
    if not session:
        session = GuidedFlowSession(id=str(uuid.uuid4()), tenant_id=tenant_id, user_id=user_id, flow_key=flow_key)
        db.add(session)
    session.status = "in_progress"
    session.started_at = datetime.now(timezone.utc)
    session.total_steps = total_steps
    session.current_step = 0
    db.commit()
    return {"session_id": session.id, "status": "in_progress"}


def complete_flow(db: Session, tenant_id: str, user_id: str, flow_key: str) -> dict:
    session = db.query(GuidedFlowSession).filter(GuidedFlowSession.tenant_id == tenant_id, GuidedFlowSession.user_id == user_id, GuidedFlowSession.flow_key == flow_key).first()
    if session:
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)

    # Update learning profile
    profile = db.query(UserLearningProfile).filter(UserLearningProfile.tenant_id == tenant_id, UserLearningProfile.user_id == user_id).first()
    if profile:
        flows = list(profile.guided_flows_completed or [])
        if flow_key not in flows:
            flows.append(flow_key)
            profile.guided_flows_completed = flows

    db.commit()
    record_coaching_observation(db, tenant_id, user_id, "guided_flow_completed", {"flow_key": flow_key}, is_positive=True)
    return {"status": "completed"}


# ---------------------------------------------------------------------------
# Employee Overview (Manager View)
# ---------------------------------------------------------------------------


def get_all_employees_learning(db: Session, tenant_id: str) -> list[dict]:
    profiles = db.query(UserLearningProfile).filter(UserLearningProfile.tenant_id == tenant_id).order_by(UserLearningProfile.employee_start_date.desc()).all()
    results = []
    for p in profiles:
        progress = db.query(UserTrackProgress).filter(UserTrackProgress.tenant_id == tenant_id, UserTrackProgress.user_id == p.user_id).first()
        user = p.user
        days = (date.today() - p.employee_start_date).days if p.employee_start_date else 0

        # Recent coaching observations
        recent_obs = db.query(CoachingObservation).filter(
            CoachingObservation.tenant_id == tenant_id, CoachingObservation.user_id == p.user_id,
            CoachingObservation.occurred_at >= datetime.now(timezone.utc) - timedelta(days=7),
        ).all()

        results.append({
            "user_id": p.user_id,
            "user_name": f"{user.first_name} {user.last_name}" if user else "Unknown",
            "training_role": p.training_role,
            "is_new_employee": p.is_new_employee,
            "days_on_platform": days,
            "track_modules_completed": progress.current_module_index if progress else 0,
            "track_total_modules": 0,  # loaded from track if needed
            "guided_flows_completed": len(p.guided_flows_completed or []),
            "procedures_viewed_count": len(p.procedures_viewed or {}),
            "recent_positive": sum(1 for o in recent_obs if o.is_positive),
            "recent_coaching": sum(1 for o in recent_obs if not o.is_positive),
        })
    return results
