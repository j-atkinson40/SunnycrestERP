"""AI & Intelligence settings API."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.ai_settings import UserAiPreferences
from app.models.user import User
from app.services import ai_settings_service

router = APIRouter()


@router.get("")
def get_ai_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full AI settings for current tenant (admin view)."""
    settings = ai_settings_service.get_settings(db, current_user.company_id)
    db.commit()
    return ai_settings_service._settings_to_dict(settings)


@router.patch("")
def update_ai_settings(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update AI settings for current tenant."""
    settings = ai_settings_service.get_settings(db, current_user.company_id)

    # Updatable fields
    allowed = {
        "briefing_narrative_enabled", "briefing_narrative_tone", "briefing_narrative_sections",
        "weekly_summary_enabled", "weekly_summary_day", "weekly_summary_time",
        "pattern_alerts_enabled", "pattern_alerts_sensitivity",
        "prep_notes_enabled", "seasonal_intelligence_enabled",
        "conversational_lookup_enabled", "natural_language_filters_enabled",
        "smart_followup_enabled", "duplicate_detection_enabled",
        "auto_enrichment_enabled", "upsell_detector_enabled",
        "account_rescue_enabled", "relationship_scoring_enabled",
        "payment_prediction_enabled", "new_customer_intelligence_enabled",
        "command_bar_enabled", "command_bar_action_tier",
        "voice_memo_enabled", "voice_commands_enabled",
        "allow_per_user_settings",
        "after_call_intelligence_enabled", "commitment_detection_enabled", "tone_analysis_enabled",
    }
    for field, value in data.items():
        if field in allowed:
            setattr(settings, field, value)

    db.commit()
    return ai_settings_service._settings_to_dict(settings)


@router.get("/me")
def get_my_ai_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get effective AI settings for current user (tenant defaults + user overrides)."""
    return ai_settings_service.get_effective_settings(db, current_user.company_id, current_user.id)


@router.patch("/me")
def update_my_ai_preferences(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update own AI preferences. Only works if tenant allows per-user settings."""
    settings = ai_settings_service.get_settings(db, current_user.company_id)
    if not settings.allow_per_user_settings:
        raise HTTPException(status_code=403, detail="Per-user AI settings are not enabled for this account")

    import uuid as _uuid
    prefs = (
        db.query(UserAiPreferences)
        .filter(UserAiPreferences.tenant_id == current_user.company_id, UserAiPreferences.user_id == current_user.id)
        .first()
    )
    if not prefs:
        prefs = UserAiPreferences(
            id=str(_uuid.uuid4()),
            tenant_id=current_user.company_id,
            user_id=current_user.id,
        )
        db.add(prefs)

    allowed = {"briefing_narrative_enabled", "briefing_narrative_tone", "command_bar_action_tier",
               "voice_memo_enabled", "voice_commands_enabled", "pattern_alerts_enabled"}
    for field, value in data.items():
        if field in allowed:
            setattr(prefs, field, value)

    db.commit()
    return ai_settings_service.get_effective_settings(db, current_user.company_id, current_user.id)


@router.get("/users")
def list_user_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all users with custom AI preferences."""
    prefs = (
        db.query(UserAiPreferences)
        .filter(UserAiPreferences.tenant_id == current_user.company_id)
        .all()
    )
    return [
        {
            "user_id": p.user_id,
            "briefing_narrative_enabled": p.briefing_narrative_enabled,
            "briefing_narrative_tone": p.briefing_narrative_tone,
            "command_bar_action_tier": p.command_bar_action_tier,
            "voice_memo_enabled": p.voice_memo_enabled,
            "voice_commands_enabled": p.voice_commands_enabled,
            "pattern_alerts_enabled": p.pattern_alerts_enabled,
        }
        for p in prefs
    ]


@router.delete("/users/{user_id}")
def reset_user_preferences(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reset a user to tenant defaults by deleting their preferences."""
    db.query(UserAiPreferences).filter(
        UserAiPreferences.tenant_id == current_user.company_id,
        UserAiPreferences.user_id == user_id,
    ).delete()
    db.commit()
    return {"reset": True}
