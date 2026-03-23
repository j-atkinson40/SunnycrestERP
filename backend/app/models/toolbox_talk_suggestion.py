"""Toolbox talk suggestion model — AI-generated topic suggestions."""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ToolboxTalkSuggestion(Base):
    __tablename__ = "toolbox_talk_suggestions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    suggestion_date: Mapped[date] = mapped_column(Date, nullable=False)
    topic_title: Mapped[str] = mapped_column(String(200), nullable=False)
    topic_category: Mapped[str] = mapped_column(String(30), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(30), nullable=False)
    trigger_description: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    trigger_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    talking_points: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    talking_points_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )  # active, used, dismissed
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    used_in_toolbox_talk_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("toolbox_talks.id"), nullable=True
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dismissed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    next_suggestion_after: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    used_in_talk = relationship("ToolboxTalk", foreign_keys=[used_in_toolbox_talk_id])
    dismisser = relationship("User", foreign_keys=[dismissed_by])
