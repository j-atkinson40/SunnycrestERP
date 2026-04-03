"""AiSettings + UserAiPreferences — per-tenant and per-user AI feature flags."""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AiSettings(Base):
    __tablename__ = "ai_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, unique=True)

    # Morning briefing
    briefing_narrative_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    briefing_narrative_tone: Mapped[str] = mapped_column(String(20), server_default="concise")
    briefing_narrative_sections: Mapped[dict] = mapped_column(JSONB, server_default="'{}'")
    weekly_summary_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    weekly_summary_day: Mapped[str] = mapped_column(String(10), server_default="monday")
    weekly_summary_time: Mapped[str] = mapped_column(String(5), server_default="07:00")
    pattern_alerts_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    pattern_alerts_sensitivity: Mapped[str] = mapped_column(String(20), server_default="moderate")
    prep_notes_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    seasonal_intelligence_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")

    # CRM intelligence
    conversational_lookup_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    natural_language_filters_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    smart_followup_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    duplicate_detection_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    auto_enrichment_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    upsell_detector_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    account_rescue_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    relationship_scoring_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    payment_prediction_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    new_customer_intelligence_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")

    # Command bar
    command_bar_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    command_bar_action_tier: Mapped[str] = mapped_column(String(20), server_default="review")

    # Voice
    voice_memo_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    voice_commands_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")

    # Per-user
    allow_per_user_settings: Mapped[bool] = mapped_column(Boolean, server_default="false")

    # Call intelligence
    after_call_intelligence_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    commitment_detection_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    tone_analysis_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")

    # Cost/usage
    founding_licensee: Mapped[bool] = mapped_column(Boolean, server_default="false")
    google_places_calls_month: Mapped[int] = mapped_column(Integer, server_default="0")
    transcription_minutes_month: Mapped[int] = mapped_column(Integer, server_default="0")
    claude_api_calls_month: Mapped[int] = mapped_column(Integer, server_default="0")
    usage_reset_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class UserAiPreferences(Base):
    __tablename__ = "user_ai_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    briefing_narrative_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    briefing_narrative_tone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    command_bar_action_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    voice_memo_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    voice_commands_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    pattern_alerts_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
