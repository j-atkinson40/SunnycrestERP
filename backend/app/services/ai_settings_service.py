"""AI settings service — feature flag checks, per-user overrides, usage tracking."""

import uuid as _uuid
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models.ai_settings import AiSettings, UserAiPreferences

# Tier hierarchy for command bar action validation
_TIER_ORDER = {"view_only": 0, "review": 1, "auto": 2}


def get_settings(db: Session, tenant_id: str) -> AiSettings:
    """Load or create default AI settings for a tenant."""
    settings = db.query(AiSettings).filter(AiSettings.tenant_id == tenant_id).first()
    if not settings:
        settings = AiSettings(id=str(_uuid.uuid4()), tenant_id=tenant_id)
        db.add(settings)
        db.flush()
    return settings


def get_effective_settings(db: Session, tenant_id: str, user_id: str | None = None) -> dict:
    """Get merged settings: tenant defaults + user overrides."""
    settings = get_settings(db, tenant_id)
    result = _settings_to_dict(settings)

    if user_id and settings.allow_per_user_settings:
        prefs = (
            db.query(UserAiPreferences)
            .filter(UserAiPreferences.tenant_id == tenant_id, UserAiPreferences.user_id == user_id)
            .first()
        )
        if prefs:
            for field in ("briefing_narrative_enabled", "briefing_narrative_tone",
                          "voice_memo_enabled", "voice_commands_enabled", "pattern_alerts_enabled"):
                val = getattr(prefs, field, None)
                if val is not None:
                    # Only allow override if the tenant-level feature is enabled
                    tenant_val = getattr(settings, field, None)
                    if isinstance(tenant_val, bool) and not tenant_val:
                        continue  # Tenant disabled it — user can't override
                    result[field] = val

            # Command bar tier: clamp to tenant max
            if prefs.command_bar_action_tier:
                tenant_max = _TIER_ORDER.get(settings.command_bar_action_tier, 1)
                user_tier = _TIER_ORDER.get(prefs.command_bar_action_tier, 1)
                result["command_bar_action_tier"] = prefs.command_bar_action_tier if user_tier <= tenant_max else settings.command_bar_action_tier

    return result


def is_enabled(db: Session, tenant_id: str, feature_key: str, user_id: str | None = None) -> bool:
    """Quick boolean check for a feature flag."""
    settings = get_effective_settings(db, tenant_id, user_id)
    return settings.get(f"{feature_key}_enabled", False)


def track_usage(db: Session, tenant_id: str, usage_type: str, amount: int = 1) -> None:
    """Increment usage counter. Resets monthly."""
    settings = get_settings(db, tenant_id)
    today = date.today()

    # Reset if new month
    if not settings.usage_reset_date or settings.usage_reset_date.month != today.month:
        settings.google_places_calls_month = 0
        settings.transcription_minutes_month = 0
        settings.claude_api_calls_month = 0
        settings.usage_reset_date = today.replace(day=1)

    if usage_type == "google_places":
        settings.google_places_calls_month = (settings.google_places_calls_month or 0) + amount
    elif usage_type == "transcription":
        settings.transcription_minutes_month = (settings.transcription_minutes_month or 0) + amount
    elif usage_type == "claude_api":
        settings.claude_api_calls_month = (settings.claude_api_calls_month or 0) + amount


def _settings_to_dict(s: AiSettings) -> dict:
    """Convert AiSettings to dict for API response."""
    return {
        "briefing_narrative_enabled": s.briefing_narrative_enabled,
        "briefing_narrative_tone": s.briefing_narrative_tone,
        "briefing_narrative_sections": s.briefing_narrative_sections,
        "weekly_summary_enabled": s.weekly_summary_enabled,
        "weekly_summary_day": s.weekly_summary_day,
        "weekly_summary_time": s.weekly_summary_time,
        "pattern_alerts_enabled": s.pattern_alerts_enabled,
        "pattern_alerts_sensitivity": s.pattern_alerts_sensitivity,
        "prep_notes_enabled": s.prep_notes_enabled,
        "seasonal_intelligence_enabled": s.seasonal_intelligence_enabled,
        "conversational_lookup_enabled": s.conversational_lookup_enabled,
        "natural_language_filters_enabled": s.natural_language_filters_enabled,
        "smart_followup_enabled": s.smart_followup_enabled,
        "duplicate_detection_enabled": s.duplicate_detection_enabled,
        "auto_enrichment_enabled": s.auto_enrichment_enabled,
        "upsell_detector_enabled": s.upsell_detector_enabled,
        "account_rescue_enabled": s.account_rescue_enabled,
        "relationship_scoring_enabled": s.relationship_scoring_enabled,
        "payment_prediction_enabled": s.payment_prediction_enabled,
        "new_customer_intelligence_enabled": s.new_customer_intelligence_enabled,
        "command_bar_enabled": s.command_bar_enabled,
        "command_bar_action_tier": s.command_bar_action_tier,
        "voice_memo_enabled": s.voice_memo_enabled,
        "voice_commands_enabled": s.voice_commands_enabled,
        "allow_per_user_settings": s.allow_per_user_settings,
        "after_call_intelligence_enabled": s.after_call_intelligence_enabled,
        "commitment_detection_enabled": s.commitment_detection_enabled,
        "tone_analysis_enabled": s.tone_analysis_enabled,
        "founding_licensee": s.founding_licensee,
        "usage": {
            "google_places_calls": s.google_places_calls_month or 0,
            "transcription_minutes": s.transcription_minutes_month or 0,
            "claude_api_calls": s.claude_api_calls_month or 0,
            "reset_date": s.usage_reset_date.isoformat() if s.usage_reset_date else None,
        },
    }
