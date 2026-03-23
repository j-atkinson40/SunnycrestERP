import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ToolboxTalk(Base):
    __tablename__ = "toolbox_talks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    conducted_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    conducted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    topic_title: Mapped[str] = mapped_column(String(200), nullable=False)
    topic_category: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="other"
    )  # safety_procedure, equipment, hazard_awareness, housekeeping, emergency, other
    linked_training_topic_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("safety_training_topics.id"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attendees = mapped_column(JSONB, nullable=True)  # array of user IDs
    attendees_external = mapped_column(JSONB, nullable=True)  # array of free-text names
    attendee_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_from_suggestion_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("toolbox_talk_suggestions.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    conductor = relationship("User", foreign_keys=[conducted_by])
    linked_topic = relationship("SafetyTrainingTopic", foreign_keys=[linked_training_topic_id])
    suggestion = relationship("ToolboxTalkSuggestion", foreign_keys=[generated_from_suggestion_id])
