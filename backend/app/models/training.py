"""Employee training and competency models."""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserLearningProfile(Base):
    __tablename__ = "user_learning_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_learning_profile"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    training_role: Mapped[str] = mapped_column(String(30), nullable=False)
    is_new_employee: Mapped[bool] = mapped_column(Boolean, server_default="true")
    employee_start_date: Mapped[date] = mapped_column(Date, default=date.today)
    guided_flows_completed: Mapped[list] = mapped_column(JSONB, server_default="[]")
    procedures_viewed: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    curriculum_track_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tasks_completed_independently: Mapped[int] = mapped_column(Integer, server_default="0")
    tasks_completed_with_agent: Mapped[int] = mapped_column(Integer, server_default="0")
    coaching_moments_count: Mapped[int] = mapped_column(Integer, server_default="0")
    last_coaching_summary_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    show_contextual_explanations: Mapped[bool] = mapped_column(Boolean, server_default="true")
    show_guided_flow_offers: Mapped[bool] = mapped_column(Boolean, server_default="true")
    show_new_employee_briefing: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", foreign_keys=[user_id])


class TrainingCurriculumTrack(Base):
    __tablename__ = "training_curriculum_tracks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("companies.id"), nullable=True)
    track_name: Mapped[str] = mapped_column(String(100), nullable=False)
    training_role: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    modules: Mapped[list] = mapped_column(JSONB, server_default="[]")
    total_modules: Mapped[int] = mapped_column(Integer, server_default="0")
    estimated_weeks: Mapped[int] = mapped_column(Integer, server_default="4")
    content_generated: Mapped[bool] = mapped_column(Boolean, server_default="false")
    content_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_edited_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class UserTrackProgress(Base):
    __tablename__ = "user_track_progress"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "track_id", name="uq_track_progress"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    track_id: Mapped[str] = mapped_column(String(36), ForeignKey("training_curriculum_tracks.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="in_progress")
    current_module_index: Mapped[int] = mapped_column(Integer, server_default="0")
    module_completions: Mapped[list] = mapped_column(JSONB, server_default="[]")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    track = relationship("TrainingCurriculumTrack", foreign_keys=[track_id])


class TrainingProcedure(Base):
    __tablename__ = "training_procedures"
    __table_args__ = (UniqueConstraint("tenant_id", "procedure_key", name="uq_procedure_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("companies.id"), nullable=True)
    procedure_key: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    applicable_roles: Mapped[list] = mapped_column(ARRAY(String(30)), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    overview: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[list] = mapped_column(JSONB, server_default="[]")
    related_procedure_keys: Mapped[list | None] = mapped_column(ARRAY(String(100)), nullable=True)
    related_feature_urls: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    content_generated: Mapped[bool] = mapped_column(Boolean, server_default="false")
    content_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_edited_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ContextualExplanation(Base):
    __tablename__ = "contextual_explanations"
    __table_args__ = (UniqueConstraint("tenant_id", "explanation_key", name="uq_explanation_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    explanation_key: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_context: Mapped[str] = mapped_column(String(200), nullable=False)
    headline: Mapped[str] = mapped_column(String(200), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    applicable_roles: Mapped[list | None] = mapped_column(ARRAY(String(30)), nullable=True)
    content_generated: Mapped[bool] = mapped_column(Boolean, server_default="false")
    content_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_edited_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class GuidedFlowSession(Base):
    __tablename__ = "guided_flow_sessions"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "flow_key", name="uq_guided_flow"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    flow_key: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="offered")
    current_step: Mapped[int] = mapped_column(Integer, server_default="0")
    total_steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    offer_count: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CoachingObservation(Base):
    __tablename__ = "coaching_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    observation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    observation_data: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    is_positive: Mapped[bool] = mapped_column(Boolean, server_default="false")
    included_in_summary: Mapped[bool] = mapped_column(Boolean, server_default="false")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TrainingAssistantConversation(Base):
    __tablename__ = "training_assistant_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    messages: Mapped[list] = mapped_column(JSONB, server_default="[]")
    page_context: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
